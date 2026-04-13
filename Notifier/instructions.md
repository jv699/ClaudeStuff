  notifier.py — the hook handler Claude Code will call on each event. Key behaviors:
  - Reads the JSON payload from stdin, extracts event type and session info
  - Derives a human-readable session name from the first user message in the transcript (falls back to truncated session ID)
  - Checks cooldown — skips if a notification for that event type fired recently
  - Sends a desktop notification via osascript (macOS), notify-send (Linux), or PowerShell balloon tip (Windows)
  - Sends RingCentral SMS if configured and enabled
  - Always exits 0, never blocks Claude

  setup_hooks.py — run this once to activate everything.

  To activate

  python3 setup_hooks.py

  Then restart Claude Code. That's it — you should get a desktop notification next time Claude finishes a response.

  To add RingCentral later

  Edit ~/.claude/notifier.json and fill in:
  "ringcentral": {
    "enabled": true,
    "client_id": "...",
    "client_secret": "...",
    "jwt_token": "...",
    "from_number": "+15551234567",
    "to_number": "+15557654321"
  }

  You'll need to create a JWT credential in the RingCentral developer portal (scoped to SMS) to get the jwt_token.
