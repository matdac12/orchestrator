import json
import os
import urllib.request
from pathlib import Path

CONFIG = Path.home() / ".orchestrator" / "telegram.json"


def resolve_creds(config_path=None):
    token = os.environ.get("ORCH_TG_TOKEN")
    chat = os.environ.get("ORCH_TG_CHAT")
    if token and chat:
        return token, chat
    path = Path(config_path or os.environ.get("ORCH_TG_CONFIG") or CONFIG)
    if path.exists():
        data = json.loads(path.read_text())
        tok = data.get("token")
        cid = data.get("chat_id")
        if tok and cid is not None:
            return tok, str(cid)
    return None, None


def _http_post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)


def send(msg, title=None, config_path=None, transport=_http_post):
    text = f"*{title}*\n{msg}" if title else msg
    token, chat = resolve_creds(config_path)
    if not token or not chat:
        print(f"[notify dry-run] {text}")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    transport(url, {"chat_id": chat, "text": text, "parse_mode": "Markdown"})
    return True
