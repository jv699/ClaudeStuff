#!/usr/bin/env python3
"""
Claude Code Notifier — hook handler for Stop and Notification events.
Invoked by Claude Code via hooks configured in ~/.claude/settings.json.
Receives event JSON on stdin and sends a RingCentral SMS.
"""

import sys
import json
import os
import platform
import pathlib
import datetime
import tempfile
import base64
import urllib.request
import urllib.parse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

CONFIG_PATH = pathlib.Path.home() / ".claude" / "notifier.json"
STATE_PATH  = pathlib.Path(tempfile.gettempdir()) / "claude_notifier_state.json"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    sys.stderr.write(f"[claude-notifier] {msg}\n")
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def get_default_config() -> dict:
    return {
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


def create_default_config() -> dict:
    defaults = get_default_config()
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(defaults, indent=2))
        log(f"Created default config at {CONFIG_PATH}")
    except Exception as e:
        log(f"Could not write default config: {e}")
    return defaults


def load_config() -> dict:
    defaults = get_default_config()
    if not CONFIG_PATH.exists():
        return create_default_config()
    try:
        loaded = json.loads(CONFIG_PATH.read_text())
        # Merge: defaults provide missing top-level keys; nested dicts merged one level deep
        for key, val in defaults.items():
            if key not in loaded:
                loaded[key] = val
            elif isinstance(val, dict) and isinstance(loaded.get(key), dict):
                for subkey, subval in val.items():
                    loaded[key].setdefault(subkey, subval)
        return loaded
    except Exception as e:
        log(f"Could not load config ({e}), using defaults")
        return defaults


# ---------------------------------------------------------------------------
# Payload Parsing
# ---------------------------------------------------------------------------

def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            log("Empty stdin — run via Claude Code hooks, not directly")
            sys.exit(0)
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"Invalid JSON on stdin: {e}")
        sys.exit(0)


def get_session_name(payload: dict) -> str:
    session_id = payload.get("session_id", "unknown")
    short_id = session_id[:8] if len(session_id) >= 8 else session_id

    transcript_path = payload.get("transcript_path", "")
    if not transcript_path:
        return short_id

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(10):
                line = f.readline()
                if not line:
                    break
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") == "user":
                    msg = entry.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, str) and content.strip():
                        snippet = content.strip()[:50]
                        return snippet if len(content.strip()) <= 50 else snippet + "…"
    except Exception as e:
        log(f"Could not read transcript for session name: {e}")

    return short_id


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------

def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    try:
        if platform.system() == "Windows":
            STATE_PATH.write_text(json.dumps(state))
        else:
            tmp = STATE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(state))
            tmp.rename(STATE_PATH)
    except Exception as e:
        log(f"Could not save state: {e}")


def is_within_cooldown(state: dict, event_type: str, cooldown_seconds: int) -> bool:
    key = f"last_notification_{event_type}"
    timestamp_str = state.get(key)
    if not timestamp_str:
        return False
    try:
        last = datetime.datetime.fromisoformat(timestamp_str)
        now = datetime.datetime.utcnow()
        return (now - last).total_seconds() < cooldown_seconds
    except Exception:
        return False


def update_cooldown(state: dict, event_type: str) -> dict:
    state[f"last_notification_{event_type}"] = datetime.datetime.utcnow().isoformat()
    return state


# ---------------------------------------------------------------------------
# Message Templating
# ---------------------------------------------------------------------------

def build_message(template: str, session_name: str, message: str = "") -> str:
    try:
        return template.format(session_name=session_name, message=message)
    except (KeyError, IndexError):
        return template


# ---------------------------------------------------------------------------
# RingCentral SMS
# ---------------------------------------------------------------------------

def _http_post(url: str, headers: dict, body: bytes) -> dict:
    """POST helper that uses requests if available, else urllib."""
    if HAS_REQUESTS:
        resp = requests.post(url, headers=headers, data=body, timeout=10)
        resp.raise_for_status()
        return resp.json()
    else:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())


def _rc_get_token(rc_cfg: dict) -> str:
    credentials = base64.b64encode(
        f"{rc_cfg['client_id']}:{rc_cfg['client_secret']}".encode()
    ).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": rc_cfg["jwt_token"],
    }).encode()
    result = _http_post(
        "https://platform.ringcentral.com/restapi/oauth/token",
        headers,
        body,
    )
    token = result.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in response: {result}")
    return token


def _rc_send_sms(rc_cfg: dict, token: str, text: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = json.dumps({
        "from": {"phoneNumber": rc_cfg["from_number"]},
        "to":   [{"phoneNumber": rc_cfg["to_number"]}],
        "text": text,
    }).encode()
    _http_post(
        "https://platform.ringcentral.com/restapi/v1.0/account/~/extension/~/sms",
        headers,
        body,
    )
    log("RingCentral SMS sent")


def send_ringcentral_sms(config: dict, text: str) -> None:
    rc_cfg = config.get("ringcentral", {})
    if not rc_cfg.get("enabled", False):
        return
    required = ["client_id", "client_secret", "jwt_token", "from_number", "to_number"]
    missing = [k for k in required if not rc_cfg.get(k, "").strip()]
    if missing:
        log(f"RingCentral not configured — missing fields: {', '.join(missing)}")
        return
    try:
        token = _rc_get_token(rc_cfg)
        _rc_send_sms(rc_cfg, token, text)
    except Exception as e:
        log(f"RingCentral SMS failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        payload    = read_payload()
        event      = payload.get("hook_event_name", "Unknown")
        config     = load_config()

        if not config.get("enabled", True):
            sys.exit(0)

        state = load_state()
        cooldown = config.get("cooldown_seconds", 30)
        if is_within_cooldown(state, event, cooldown):
            log(f"Within cooldown window for {event}, skipping")
            sys.exit(0)

        session  = get_session_name(payload)
        raw_msg  = payload.get("message", "")
        template = config.get("messages", {}).get(event, "Claude event: {session_name}")
        text     = build_message(template, session, raw_msg)

        send_ringcentral_sms(config, f"Claude Code: {text}")

        save_state(update_cooldown(state, event))

    except Exception as e:
        log(f"Unhandled error: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
