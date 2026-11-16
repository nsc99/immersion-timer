"""Build the Immersion shortcut: one tap toggles a Traggo timer tagged immersion=<label>."""
from pathlib import Path
import json
import plistlib
import uuid

ROOT = Path(__file__).resolve().parent
versions = json.loads((ROOT / 'versions.json').read_text())
LABELS = ['raw video', 'raw audio', 'sub video', 'reading']
TAG = 'immersion'
RFC3339 = "yyyy-MM-dd'T'HH:mm:ssZZZZZ"
actions = []
questions = []


def uid():
    return str(uuid.uuid4()).upper()


def action(name, **params):
    params.setdefault('UUID', uid())
    actions.append({'WFWorkflowActionIdentifier': 'is.workflow.actions.' + name,
                    'WFWorkflowActionParameters': params})
    return {'Type': 'ActionOutput', 'OutputUUID': params['UUID'], 'OutputName': 'Result'}


def token(value):
    return {'Value': value, 'WFSerializationType': 'WFTextTokenAttachment'}


def text(*parts):
    result, attachments = '', {}
    for part in parts:
        if isinstance(part, dict):
            attachments['{%d, 1}' % len(result)] = part
            result += '￼'
        else:
            result += str(part)
    value = {'string': result}
    if attachments:
        value['attachmentsByRange'] = attachments
    return {'Value': value, 'WFSerializationType': 'WFTextTokenString'}


def dictionary(items):
    return {'Value': {'WFDictionaryFieldValueItems': [
        {'WFItemType': 0, 'WFKey': text(key), 'WFValue': value if isinstance(value, dict) else text(value)}
        for key, value in items.items()]}, 'WFSerializationType': 'WFDictionaryFieldValue'}


def graphql(query):
    """POST one GraphQL document to <url>/graphql with the device token."""
    return action('downloadurl', WFURL=text(url, '/graphql'), Advanced=True, ShowHeaders=True,
                  WFHTTPMethod='POST', WFHTTPBodyType='JSON',
                  WFHTTPHeaders=dictionary({'Authorization': text('traggo ', api_token)}),
                  WFJSONValues=dictionary({'query': query}))


def clock(intent):
    """Clock app intent (App Intents metadata of MobileTimerSupport.framework); stopwatch has no name."""
    actions.append({'WFWorkflowActionIdentifier': 'com.apple.clock.' + intent, 'WFWorkflowActionParameters': {
        'UUID': uid(), 'AppIntentDescriptor': {
            'TeamIdentifier': '0000000000', 'BundleIdentifier': 'com.apple.clock', 'Name': 'Clock',
            'AppIntentIdentifier': intent, 'ActionRequiresAppInstallation': True}}})


def now_rfc3339():
    now = action('date', WFDateActionMode='Current Date')
    return action('format.date', WFDate=text(now), WFDateFormatStyle='Custom', WFDateFormat=RFC3339,
                  WFTimeFormatStyle='None')


def ask(index, prompt, default):
    questions.append({'ActionIndex': index, 'Category': 'Parameter', 'ParameterKey': 'WFTextActionText',
                      'Text': prompt, 'DefaultValue': default})


action('comment', WFCommentActionText=(
    'Toggles a Traggo timer. Running timer: stop it (and stop + reset the Clock stopwatch). Otherwise: '
    f'pick a label, start one tagged {TAG}=<label> and start the Clock stopwatch so the elapsed time '
    'shows in the Live Activity. The two Text blocks below hold the Traggo URL and a device token '
    '(answered on import; edit them here to change).'))
url = action('gettext', WFTextActionText='https://traggo.example.com')
ask(len(actions) - 1, 'Traggo URL (no trailing slash)', 'https://traggo.example.com')
api_token = action('gettext', WFTextActionText='')
ask(len(actions) - 1, 'Traggo device token (see README)', '')

response = graphql('{ timers { id } }')
data = action('getvalueforkey', WFInput=token(response), WFDictionaryKey='data', WFGetDictionaryValueType='Value')
timers = action('getvalueforkey', WFInput=token(data), WFDictionaryKey='timers', WFGetDictionaryValueType='Value')
running = action('count', WFCountType='Items', Input=token(timers))

branch = uid()
action('conditional', WFInput={'Type': 'Variable', 'Variable': token(running)},
       WFCondition=2, WFNumberValue=0, GroupingIdentifier=branch, WFControlFlowMode=0)
timer = action('getitemfromlist', WFInput=token(timers), WFItemSpecifier='First Item')
timer_id = action('getvalueforkey', WFInput=token(timer), WFDictionaryKey='id', WFGetDictionaryValueType='Value')
end = now_rfc3339()
graphql(text('mutation { stopTimeSpan(id: ', timer_id, ', end: "', end, '") { id } }'))
clock('StopStopwatchIntent')
clock('ResetStopwatchIntent')
action('notification', WFNotificationActionBody='Immersion timer stopped', WFNotificationActionSound=False)

action('conditional', GroupingIdentifier=branch, WFControlFlowMode=1)
labels = action('list', WFItems=LABELS)
label = action('choosefromlist', WFInput=token(labels), WFChooseFromListActionPrompt='Immersion')
start = now_rfc3339()
graphql(text('mutation { createTimeSpan(start: "', start, f'", tags: [{{key: "{TAG}", value: "', label,
             '"}], note: "") { id } }'))
clock('StartStopwatchIntent')
action('notification', WFNotificationActionBody=text('Immersion: ', label), WFNotificationActionSound=False)
action('conditional', GroupingIdentifier=branch, WFControlFlowMode=2)

workflow = {
    'WFWorkflowClientVersion': versions['authoring_client'],
    'WFWorkflowMinimumClientVersion': versions['minimum_client'],
    'WFWorkflowMinimumClientVersionString': str(versions['minimum_client']),
    'WFWorkflowIcon': versions['icon'],
    'WFWorkflowActions': actions,
    'WFWorkflowName': 'Immersion',
    'WFWorkflowTypes': [], 'WFQuickActionSurfaces': [],
    'WFWorkflowInputContentItemClasses': [], 'WFWorkflowOutputContentItemClasses': [],
    'WFWorkflowImportQuestions': questions,
    'WFWorkflowHasShortcutInputVariables': False, 'WFWorkflowHasOutputFallback': False,
}
output = ROOT / 'Immersion.wflow'
output.write_bytes(plistlib.dumps(workflow))
print(f'Created {output.name}: {len(actions)} actions, {len(questions)} import questions.')
