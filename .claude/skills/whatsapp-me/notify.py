#!/usr/bin/env python3
"""Send a WhatsApp message to Mattia via the bedigital-omni notify endpoint.

Stdlib only, so it runs from any project without a venv.

Usage:
    python notify.py "tests passed"
    pytest 2>&1 | tail -40 | python notify.py --stdin
    python notify.py --stdin --prefix "TESTS FAILED"

Exit codes:
    0  delivered
    1  endpoint refused or delivery failed (message NOT delivered)
    2  usage / configuration problem (no secret, empty message)
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://api.bedigital-omni.com/notify"
SECRET_FILE = Path.home() / ".claude" / ".omni-notify-secret"
TIMEOUT = 30


def die(msg, code):
    print(msg, file=sys.stderr)
    sys.exit(code)


def resolve_secret() -> str:
    """Env var wins; otherwise the user-level secret file."""
    secret = os.environ.get("OMNI_NOTIFY_SECRET", "").strip()
    if secret:
        return secret
    if SECRET_FILE.is_file():
        secret = SECRET_FILE.read_text(encoding="utf-8").strip()
        if secret:
            return secret
    die(
        f"whatsapp-me: no secret found.\n"
        f"  Set $OMNI_NOTIFY_SECRET, or put the secret in {SECRET_FILE}",
        2,
    )


def post(url: str, secret: str, text: str) -> tuple[int, str]:
    # json.dumps handles quotes, newlines and backslashes. Never build this
    # payload by string interpolation - test output is exactly the input that
    # breaks that.
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "X-Notify-Secret": secret,
            "Content-Type": "application/json",
            # Cloudflare fronts this host and blocks urllib's default UA with
            # "error code: 1010" - which looks exactly like an auth failure.
            "User-Agent": "whatsapp-me/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        die(f"whatsapp-me: FAILED - could not reach {url} ({e.reason})", 1)


def explain(status: int, body: str) -> str:
    """Turn a non-200 into something actionable rather than a bare code."""
    hints = {
        403: "The secret is wrong or missing. Check $OMNI_NOTIFY_SECRET / "
             f"{SECRET_FILE}.",
        400: "The endpoint rejected the body - the message was probably empty.",
        502: "WhatsApp refused delivery (Meta's error is in the body above).\n"
             "  Most likely the 24-hour window: if Mattia hasn't messaged the\n"
             "  number in the last 24h, Meta blocks the send. That is WhatsApp\n"
             "  policy, not a bug. Fix: Mattia sends any message to the number,\n"
             "  then retry. Until then this ping will NOT arrive - tell him in\n"
             "  the terminal instead of assuming it went through.",
    }
    hint = hints.get(status, "Unexpected status - the message was not delivered.")
    # A Cloudflare block ("error code: 1010") mimics an auth failure. The app
    # always answers with JSON, so a non-JSON body means we never reached it.
    if not body.lstrip().startswith("{"):
        hint = (
            "This did not come from the app (its errors are JSON) - the CDN in\n"
            "  front of it blocked the request. Check the User-Agent header."
        )
    return f"whatsapp-me: FAILED (HTTP {status})\n  {body}\n  {hint}"


def main() -> int:
    p = argparse.ArgumentParser(
        prog="notify.py",
        description="Send a WhatsApp message to Mattia.",
    )
    p.add_argument("text", nargs="*", help="Message text.")
    p.add_argument(
        "--stdin",
        action="store_true",
        help="Read the message from stdin instead of argv (use for piped output).",
    )
    p.add_argument(
        "--prefix",
        default="",
        help="Line prepended to the message, e.g. --prefix 'TESTS FAILED'.",
    )
    p.add_argument("--url", default=os.environ.get("OMNI_NOTIFY_URL", DEFAULT_URL))
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the exact JSON payload without sending.",
    )
    args = p.parse_args()

    if args.stdin:
        text = sys.stdin.read()
    else:
        text = " ".join(args.text)
    text = text.strip()

    if args.prefix:
        text = f"{args.prefix}\n{text}" if text else args.prefix

    if not text:
        die("whatsapp-me: refusing to send an empty message.", 2)

    if args.dry_run:
        print(json.dumps({"text": text}, ensure_ascii=False))
        return 0

    status, body = post(args.url, resolve_secret(), text)

    if status != 200:
        print(explain(status, body.strip()), file=sys.stderr)
        return 1

    try:
        truncated = json.loads(body).get("truncated", False)
    except json.JSONDecodeError:
        truncated = False
    print("whatsapp-me: sent" + (" (truncated by the endpoint)" if truncated else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
