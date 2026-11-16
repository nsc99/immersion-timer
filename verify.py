"""Check the source plist and decode Apple's signed archive to confirm signing kept it intact."""
from pathlib import Path
import json
import plistlib
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
source = plistlib.loads((ROOT / 'Immersion.wflow').read_bytes())
versions = json.loads((ROOT / 'versions.json').read_text())
allowed = {'is.workflow.actions.' + n for n in (
    'comment', 'gettext', 'downloadurl', 'getvalueforkey', 'count', 'conditional',
    'getitemfromlist', 'date', 'format.date', 'notification', 'list', 'choosefromlist')}
seen, stack = set(), []


def check(value):
    if isinstance(value, dict):
        if 'OutputUUID' in value:
            assert value['OutputUUID'] in seen, 'forward or missing output reference'
        for item in value.values():
            check(item)
    elif isinstance(value, list):
        for item in value:
            check(item)


for action in source['WFWorkflowActions']:
    assert action['WFWorkflowActionIdentifier'] in allowed, action['WFWorkflowActionIdentifier']
    p = action['WFWorkflowActionParameters']
    check(p)
    assert p['UUID'] not in seen
    seen.add(p['UUID'])
    if 'GroupingIdentifier' in p:
        mode, group = p['WFControlFlowMode'], p['GroupingIdentifier']
        if mode == 0:
            stack.append(group)
        elif mode == 1:
            assert stack[-1] == group
        else:
            assert stack.pop() == group
assert not stack
for question in source['WFWorkflowImportQuestions']:
    target = source['WFWorkflowActions'][question['ActionIndex']]
    assert target['WFWorkflowActionIdentifier'] == 'is.workflow.actions.gettext'
    assert question['ParameterKey'] == 'WFTextActionText'
assert source['WFWorkflowClientVersion'] == versions['authoring_client']
assert source['WFWorkflowMinimumClientVersion'] == versions['minimum_client']
requests = [a for a in source['WFWorkflowActions'] if a['WFWorkflowActionIdentifier'] == 'is.workflow.actions.downloadurl']
assert len(requests) == 3, 'timers query, stop mutation, create mutation'
for request in requests:
    p = request['WFWorkflowActionParameters']
    assert p['WFHTTPMethod'] == 'POST' and p['WFHTTPBodyType'] == 'JSON'
    header = p['WFHTTPHeaders']['Value']['WFDictionaryFieldValueItems'][0]
    assert header['WFKey']['Value']['string'] == 'Authorization'
    assert header['WFValue']['Value']['string'].startswith('traggo ')

signed = ROOT / 'Immersion.shortcut'
assert signed.is_file(), 'sign the shortcut before verification'
blob = signed.read_bytes()
assert blob[:4] == b'AEA1'
profile, size = struct.unpack_from('<II', blob, 4)
assert profile == 0
metadata = plistlib.loads(blob[12:12 + size])
with tempfile.TemporaryDirectory(prefix='immersion-verify-') as directory:
    directory = Path(directory)
    public_key = directory / 'public.hex'
    if 'SigningPublicKey' in metadata:
        public_key.write_text('hex:' + metadata['SigningPublicKey'].hex())
    else:
        certificate = directory / 'certificate.der'
        certificate.write_bytes(metadata['SigningCertificateChain'][0])
        public_key.write_bytes(subprocess.check_output(
            ['openssl', 'x509', '-inform', 'DER', '-in', str(certificate), '-pubkey', '-noout']))
    archive = directory / 'payload.aa'
    subprocess.run(['aea', 'decrypt', '-i', str(signed), '-o', str(archive), '-sign-pub', str(public_key)], check=True)
    output = directory / 'extracted'
    output.mkdir()
    subprocess.run(['aa', 'extract', '-i', str(archive), '-d', str(output)], check=True)
    files = list(output.glob('*.wflow'))
    assert len(files) == 1
    actual = plistlib.loads(files[0].read_bytes())
assert actual['WFWorkflowActions'] == source['WFWorkflowActions'], 'signer changed actions'
assert actual['WFWorkflowImportQuestions'] == source['WFWorkflowImportQuestions']
assert actual['WFWorkflowMinimumClientVersion'] == versions['minimum_client']
print(json.dumps({
    'source_authoring_client': source['WFWorkflowClientVersion'],
    'signed_authoring_client': actual['WFWorkflowClientVersion'],
    'signed_minimum_client': actual['WFWorkflowMinimumClientVersion'],
    'action_count': len(actual['WFWorkflowActions']),
}, indent=2))
