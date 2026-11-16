# Immersion timer

An iOS Shortcut that toggles a [Traggo](https://traggo.net) timer with one tap, meant to run from an NFC tag.

- A timer is running: stop it.
- No timer is running: ask for a label and start one tagged `immersion=<label>`.

Labels: `raw video`, `raw audio`, `sub video`, `reading`. Traggo keeps the hours, dashboards group them by the `immersion` tag.

## Traggo setup (once)

1. Sign in to Traggo and create the tag `immersion` under **Settings → Tags**. Traggo refuses time spans with unknown tags.
2. Create a non-expiring device token for the phone (replace the password; `jq` is only for readability):

   ```sh
   curl -s https://traggo.example.com/graphql -H 'Content-Type: application/json' -d \
     '{"query":"mutation { login(username: \"admin\", pass: \"PASSWORD\", deviceName: \"iphone-shortcut\", type: NoExpiry, cookie: false) { token } }"}' | jq -r .data.login.token
   ```

   The device appears under **Settings → Devices**, where it can be revoked.

## Install

1. AirDrop `Immersion.shortcut` to the iPhone and open it.
2. Answer the two import questions: the Traggo URL without a trailing slash, and the device token. Both live in the two **Text** blocks at the top of the shortcut and can be edited there later.
3. Run it once by hand: pick a label, then run it again to stop. Both show up in Traggo's list view.
4. NFC: **Shortcuts → Automation → + → NFC → Scan** a tag, name it, choose **Run Immediately**, turn **Notify When Run** off, and pick **Immersion**.

The phone must reach the Traggo URL: on the home network, or over Tailscale with *Use Tailscale DNS settings* on.

## How it works

One GraphQL query (`timers`) tells whether a timer runs. The shortcut then sends either `stopTimeSpan` or `createTimeSpan` with the current time formatted as RFC 3339, authenticated with the `Authorization: traggo <token>` header.

## Rebuild

```sh
python3 build.py
shortcuts sign --mode anyone --input Immersion.wflow --output Immersion.shortcut
python3 verify.py
```

`versions.json` pins the minimum client `900` and authoring client `4711` taken from the Apple-hosted Clock reference. `verify.py` checks the source plist (action set, output references, balanced If blocks, request shape), then decrypts the signed archive with Apple's `aea` tool and confirms signing preserved every action.
