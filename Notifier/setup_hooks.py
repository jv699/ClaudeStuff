#!/usr/bin/env python3
"""
One-time setup script: wires notifier.py into ~/.claude/settings.json
and creates ~/.claude/notifier.json with defaults if it doesn't exist.

Usage:
    python3 setup_hooks.py
"""

import json
import pathlib
import sys

SETTINGS_PATH = pathlib.Path.home() / ".claude" / "settings.json"
CONFIG_PATH   = pathlib.Path.home() / ".claude" / "notifier.json"
NOTIFIER_PATH = (pathlib.Path(__file__).parent / "notifier.py").resolve()

DEFAULT_CONFIG = {
    "enabled": True,
    "cooldown_seconds": 30,
    "ringcentral": {
        "enabled": False,
        "client_id": "",
        "client_secret": "",
        "jwt_token": "",
        "from_number": "",
        "to_number": ""
    },
    "messages": {
        "Stop": "Claude is done thinking in session: {session_name}",
        "Notification": "Claude needs your attention in session: {session_name} — {message}"
    }
}

HOOK_COMMAND = f"python3 {NOTIFIER_PATH}"
HOOK_EVENTS  = ["Stop", "Notification"]


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        text = SETTINGS_PATH.read_text().strip()
        return json.loads(text) if text else {}
    except Exception as e:
        print(f"Warning: could not read settings.json ({e}), starting fresh")
        return {}


def hook_already_present(hooks_list: list) -> bool:
    """Return True if any entry in the hooks list already points at notifier.py."""
    for entry in hooks_list:
        for hook in entry.get("hooks", []):
            if str(NOTIFIER_PATH) in hook.get("command", ""):
                return True
    return False


def add_hooks(settings: dict) -> dict:
    settings.setdefault("hooks", {})
    for event in HOOK_EVENTS:
        settings["hooks"].setdefault(event, [])
        if hook_already_present(settings["hooks"][event]):
            print(f"  {event}: already configured, skipping")
        else:
            settings["hooks"][event].append({
                "hooks": [{"type": "command", "command": HOOK_COMMAND}]
            })
            print(f"  {event}: hook added")
    return settings


def setup_notifier_config() -> None:
    if CONFIG_PATH.exists():
        print(f"Config already exists at {CONFIG_PATH}, leaving it unchanged")
    else:
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        print(f"Created {CONFIG_PATH} — edit it to configure RingCentral credentials")


def main() -> None:
    if not NOTIFIER_PATH.exists():
        print(f"Error: notifier.py not found at {NOTIFIER_PATH}")
        print("Run setup_hooks.py from the same directory as notifier.py")
        sys.exit(1)

    print(f"Notifier script : {NOTIFIER_PATH}")
    print(f"Settings file   : {SETTINGS_PATH}")
    print()

    settings = load_settings()
    print("Wiring hooks:")
    settings = add_hooks(settings)

    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2))
    print()
    print("Updated settings.json:")
    print(json.dumps(settings.get("hooks", {}), indent=2))
    print()

    print("Setting up notifier config:")
    setup_notifier_config()
    print()
    print("Done. Restart Claude Code for hooks to take effect.")


if __name__ == "__main__":
    main()
