# Claude Code Notifier — Setup Guide

Posts a message to RingCentral team messaging when Claude finishes a response or needs your attention. Uses an incoming webhook — no API credentials or OAuth required.

## Prerequisites

- Python 3.7+
- Claude Code installed and configured
- Access to RingCentral (web, desktop, or mobile)

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

## Step 3 — Create a RingCentral incoming webhook

Each person sets up their own webhook pointing to a conversation of their choice (personal chat, a shared team channel, etc.).

1. Open RingCentral (web or desktop)
2. Navigate to the conversation you want notifications delivered to
3. Click the **Integrations** or **+** icon at the top of the conversation (the exact label varies by client version)
4. Select **Incoming Webhook**
5. Give it a name (e.g. "Claude Code")
6. Copy the generated webhook URL — it looks like:
   `https://hooks.ringcentral.com/webhook/v2/...`

> **Team setup:** For a shared channel, whoever manages the channel creates one webhook and shares the URL with the team. Everyone uses the same `webhook_url` and notifications go to the channel. For personal notifications, each person creates their own webhook in their own DM with themselves or a personal channel.

## Step 4 — Configure the notifier

Edit `~/.claude/notifier.json`:

```json
{
  "enabled": true,
  "cooldown_seconds": 30,
  "ringcentral": {
    "enabled": true,
    "webhook_url": "https://hooks.ringcentral.com/webhook/v2/..."
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
| `cooldown_seconds` | Minimum seconds between notifications of the same type. Prevents message spam during rapid back-and-forth. Default: `30`. |
| `ringcentral.enabled` | Must be `true` for messages to send. |
| `ringcentral.webhook_url` | The webhook URL copied from step 3. |
| `messages.Stop` | Template sent when Claude finishes its turn. |
| `messages.Notification` | Template sent when Claude needs input or permission. |

### Message templates

Two placeholders are available:

- `{session_name}` — the first ~50 characters of your opening message in the session, or a short session ID if unavailable
- `{message}` — the notification text from Claude (only present for `Notification` events; empty for `Stop`)

## Step 5 — Test it

**Simulate a Stop event:**

```bash
echo '{"session_id":"test-1234","transcript_path":"","hook_event_name":"Stop","stop_hook_active":true}' \
  | python3 notifier.py 2>&1
```

You should see `[claude-notifier] RingCentral webhook message sent` in the output and a message appear in your RingCentral conversation.

**Simulate a Notification event:**

```bash
echo '{"session_id":"test-1234","transcript_path":"","hook_event_name":"Notification","message":"Permission needed to run a command"}' \
  | python3 notifier.py 2>&1
```

**Test cooldown** — run either command twice quickly. The second run should print `Within cooldown window for Stop, skipping` and not post a message.

**Reset cooldown between tests:**

```bash
rm /tmp/claude_notifier_state.json        # macOS / Linux
del %TEMP%\claude_notifier_state.json     # Windows
```

## Troubleshooting

**No message received after a Claude session ends**

1. Check that `setup_hooks.py` was run and hooks appear in `~/.claude/settings.json` under `hooks.Stop` and `hooks.Notification`
2. Confirm `ringcentral.enabled` is `true` in `~/.claude/notifier.json`
3. Run the manual test above — errors are printed to stderr and will show with `2>&1`
4. Verify the webhook URL is correct and hasn't been deleted or regenerated in RingCentral

**`RingCentral not configured — webhook_url is empty`**

The `webhook_url` field in `~/.claude/notifier.json` is missing or blank. Paste the URL from step 3.

**`RingCentral webhook failed: HTTP Error 404`**

The webhook was deleted or regenerated in RingCentral. Create a new one and update `webhook_url` in `~/.claude/notifier.json`.

**Notifications feel spammy**

Increase `cooldown_seconds` in `~/.claude/notifier.json`. The cooldown is tracked per event type (`Stop` and `Notification` independently).

**Moved the notifier files to a new location**

Re-run `python3 setup_hooks.py` from the new location. Remove the old hook entry manually from `~/.claude/settings.json` under `hooks.Stop` and `hooks.Notification`.
