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

## Email setup (Gmail)

Email is an alternative channel that posts to a RingCentral conversation via its "post by email" address. Both channels can be enabled at the same time.

### Step A — Get your Gmail App Password

Google requires an App Password for SMTP access — your regular Gmail password will not work.

1. Go to your Google Account > **Security**
2. Under "How you sign in to Google", ensure **2-Step Verification** is enabled (required for App Passwords)
3. Search for **App Passwords** in the security settings
4. Select app: **Mail**, select device: **Other** (type a name like "Claude Notifier")
5. Click **Generate** — copy the 16-character password shown (no spaces)

> App Passwords are only available if 2-Step Verification is enabled on your account.

### Step B — Get the RingCentral conversation email address

1. Open the conversation in RingCentral you want notifications delivered to
2. Click the conversation name or settings icon at the top
3. Look for **Post by email** or **Email integration** — copy the address shown (it will look something like `team.xxxxxxxx@posts.ringcentral.com`)

### Step C — Configure the email section

Edit `~/.claude/notifier.json` and fill in the `email` block:

```json
"email": {
  "enabled": true,
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "you@gmail.com",
  "smtp_password": "xxxx xxxx xxxx xxxx",
  "from_address": "you@gmail.com",
  "to_address": "team.xxxxxxxx@posts.ringcentral.com"
}
```

| Field | Description |
|---|---|
| `smtp_user` | Your full Gmail address |
| `smtp_password` | The 16-character App Password from step A (spaces are fine to include or omit) |
| `from_address` | Same as `smtp_user` |
| `to_address` | The RingCentral conversation email address from step B |

### Test it

```bash
echo '{"session_id":"test-1234","transcript_path":"","hook_event_name":"Stop","stop_hook_active":true}' \
  | python3 notifier.py 2>&1
```

You should see `[claude-notifier] Email notification sent` and a message appear in the RingCentral conversation shortly after.

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

**`Email notification failed: (535, b'5.7.8 Username and Password not accepted')`**

The App Password is wrong or your regular Gmail password was used. Generate a new App Password and update `smtp_password` in `~/.claude/notifier.json`.

**`Email notification failed: ... SMTPAuthenticationError`**

2-Step Verification may not be enabled on the Google account, which is required for App Passwords. Enable it at Google Account > Security, then generate an App Password.

**Email sends but nothing appears in RingCentral**

The `to_address` may be wrong. Double-check the "post by email" address in the RingCentral conversation settings. Note that delivery can take up to a minute.

**Moved the notifier files to a new location**

Re-run `python3 setup_hooks.py` from the new location. Remove the old hook entry manually from `~/.claude/settings.json` under `hooks.Stop` and `hooks.Notification`.
