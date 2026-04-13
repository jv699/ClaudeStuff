# Claude Code Notifier — Setup Guide

Sends you a RingCentral SMS when Claude finishes a response or needs your attention. Hooks into Claude Code's event system with no background process required.

## Prerequisites

- Python 3.7+
- Claude Code installed and configured
- A RingCentral account with API access (see step 3)

## Step 1 — Clone / place the files

Both files need to be in the same directory:

```
notifier.py
setup_hooks.py
```

The directory can be anywhere on your machine. The setup script uses its own location to resolve the absolute path to `notifier.py`, so moving the files later will require re-running setup.

## Step 2 — Wire the hooks

From the directory containing both files, run:

```bash
python3 setup_hooks.py
```

This does two things:
1. Adds `Stop` and `Notification` hook entries to `~/.claude/settings.json` pointing at `notifier.py`
2. Creates `~/.claude/notifier.json` with default configuration if it doesn't already exist

The script is idempotent — safe to re-run; it won't add duplicate hooks.

**Restart Claude Code after running setup** for the hooks to take effect.

## Step 3 — Get RingCentral API credentials

You need a RingCentral app with SMS permissions and a JWT credential. If your company already has a RingCentral developer account, ask your admin for access to the Developer Portal. Otherwise:

1. Go to the [RingCentral Developer Portal](https://developers.ringcentral.com) and log in
2. Create a new app (or use an existing one):
   - Platform type: **Server/Backend**
   - Auth type: **JWT auth flow**
   - Permissions: **SMS**
3. Note the app's **Client ID** and **Client Secret** from the app's credentials tab
4. Create a JWT credential:
   - In the Developer Portal, go to **Credentials** > **Create JWT**
   - Scope it to your app
   - Copy the generated JWT string — it won't be shown again

> **Sandbox vs Production:** New RingCentral apps start in Sandbox. Sandbox credentials work against `platform.devtest.ringcentral.com` instead of `platform.ringcentral.com`. The notifier uses the production URL by default. If testing in Sandbox, temporarily change the URLs in `notifier.py` (`_rc_get_token` and `_rc_send_sms`) to use the sandbox base URL.

## Step 4 — Configure the notifier

Edit `~/.claude/notifier.json`:

```json
{
  "enabled": true,
  "cooldown_seconds": 30,
  "ringcentral": {
    "enabled": true,
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "jwt_token": "YOUR_JWT_TOKEN",
    "from_number": "+15551234567",
    "to_number": "+15557654321"
  },
  "messages": {
    "Stop": "Claude is done thinking in session: {session_name}",
    "Notification": "Claude needs your attention in session: {session_name} — {message}"
  }
}
```

| Field | Description |
|---|---|
| `enabled` | Master on/off switch. Set to `false` to silence all notifications without removing hooks. |
| `cooldown_seconds` | Minimum seconds between notifications of the same type. Prevents SMS spam during rapid back-and-forth. Default: `30`. |
| `ringcentral.enabled` | Must be `true` for SMS to send. Set to `false` to disable SMS while keeping hooks active. |
| `from_number` | The RingCentral number SMS is sent from (must be on your account). E164 format: `+1XXXXXXXXXX`. |
| `to_number` | The phone number to receive the SMS. E164 format: `+1XXXXXXXXXX`. |
| `messages.Stop` | Template sent when Claude finishes its turn. |
| `messages.Notification` | Template sent when Claude needs input or permission. |

### Message templates

Two placeholders are available:

- `{session_name}` — the first ~50 characters of your opening message in the session, or a short session ID if unavailable
- `{message}` — the notification text from Claude (only present for `Notification` events; empty for `Stop`)

## Step 5 — Test it

**Test without RingCentral (config check only):**

```bash
echo '{"session_id":"test-1234","transcript_path":"","hook_event_name":"Stop","stop_hook_active":true}' \
  | python3 notifier.py
```

You should see no output (all logging goes to stderr). Run it again immediately — the second run should log the cooldown message:

```bash
# Run twice quickly to verify cooldown
echo '{"session_id":"test-1234","transcript_path":"","hook_event_name":"Stop","stop_hook_active":true}' \
  | python3 notifier.py 2>&1
```

**Test the Notification event:**

```bash
echo '{"session_id":"test-1234","transcript_path":"","hook_event_name":"Notification","message":"Permission needed to run a command"}' \
  | python3 notifier.py 2>&1
```

**Test with RingCentral enabled:**

Set `ringcentral.enabled` to `true` in `~/.claude/notifier.json` with your credentials filled in, then run the Stop test above. You should receive an SMS within a few seconds.

**Reset cooldown between tests:**

```bash
rm /tmp/claude_notifier_state.json   # macOS / Linux
del %TEMP%\claude_notifier_state.json  # Windows
```

## Troubleshooting

**No SMS received after a Claude session ends**

1. Check that `setup_hooks.py` was run and hooks appear in `~/.claude/settings.json` under `hooks.Stop` and `hooks.Notification`
2. Confirm `ringcentral.enabled` is `true` in `~/.claude/notifier.json`
3. Run the manual stdin test above with `2>&1` to see stderr logs — missing fields or auth errors will be printed there
4. Verify `from_number` is a real SMS-capable number on your RingCentral account

**`RingCentral not configured — missing fields`**

All five fields (`client_id`, `client_secret`, `jwt_token`, `from_number`, `to_number`) must be non-empty strings. Check for accidental whitespace or empty values.

**`RingCentral SMS failed: HTTP Error 401`**

The JWT token has expired or the client credentials are wrong. Re-generate the JWT in the Developer Portal and update `~/.claude/notifier.json`.

**`RingCentral SMS failed: HTTP Error 403`**

The app lacks SMS permission, or the `from_number` is not authorized on the account. Check the app's permission scopes in the Developer Portal.

**Notifications fire but feel spammy**

Increase `cooldown_seconds` in `~/.claude/notifier.json`. The cooldown is tracked per event type (`Stop` and `Notification` independently), so both can fire in the same window if they're different event types.

**Moved the notifier files to a new location**

Re-run `python3 setup_hooks.py` from the new location. The old hook entry will remain in `settings.json` pointing at the old path — remove it manually from `~/.claude/settings.json` under `hooks.Stop` and `hooks.Notification`.
