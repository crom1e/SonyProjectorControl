#!/usr/bin/env python3
"""
on.py — power ON the Sony VPL-FH30 via its web interface.

Logic:
  1. Query http://<IP>/info_data.htm  (no auth)
  2. Parse JS array info_status_value
  3. If status is OFF/STANDBY → send GET to http://<IP>/custom/01
  4. Poll until status becomes ON / STARTUP / COOLING / TIMEOUT
"""
from __future__ import annotations
import sys
import time
import urllib.request
import urllib.error
import re

IP_DEFAULT = "192.168.250.1"
STATUS_URL_TEMPLATE = "http://{ip}/info_data.htm"
TOGGLE_URL_TEMPLATE = "http://{ip}/custom/01"
TIMEOUT_SEC = 5.0
POLL_INTERVAL = 3
MAX_WAIT = 90  # seconds total wait for ON confirmation

STATUS_RE = re.compile(r"var\s+info_status_value\s*=\s*\[([^\]]*)\]", re.IGNORECASE)
QUOTED_ITEM_RE = re.compile(r"'([^']*)'")


def fetch(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fh30-on/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def parse_info_status(html: str) -> str | None:
    """Return first element of info_status_value JS array, or None."""
    compact = html.replace("\r", "").replace("\n", "")
    m = STATUS_RE.search(compact)
    if not m:
        return None
    array_content = m.group(1)
    items = QUOTED_ITEM_RE.findall(array_content)
    return items[0] if items else None


def normalize_status(s: str | None) -> str:
    """
    Normalize projector-reported status to a small set:
    ON, OFF, COOLING, or UNKNOWN.
    """
    if s is None:
        return "UNKNOWN"
    up = s.strip().upper()
    # Treat STARTUP states as ON
    if up in ("ON", "STARTUP", "STARTUP1", "STARTUP2"):
        return "ON"
    if up in ("OFF", "STANDBY"):
        return "OFF"
    if "COOL" in up or "WARM" in up:
        return "COOLING"
    return "UNKNOWN"


def get_status(ip: str) -> str:
    url = STATUS_URL_TEMPLATE.format(ip=ip)
    try:
        html = fetch(url, TIMEOUT_SEC)
    except Exception as e:
        print(f"[warn] status fetch failed: {e}")
        return "UNKNOWN"
    s = parse_info_status(html)
    return normalize_status(s)


def toggle_power(ip: str):
    url = TOGGLE_URL_TEMPLATE.format(ip=ip)
    try:
        urllib.request.urlopen(url, timeout=TIMEOUT_SEC).read()
        print(f"[info] Sent toggle command to {url}")
    except Exception as e:
        print(f"[warn] toggle failed: {e}")


def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else IP_DEFAULT
    print(f"[info] Checking projector {ip} status...")

    status = get_status(ip)
    print(f"[info] Current status: {status}")

    if status == "ON":
        print("✅ Projector already ON or starting up.")
        sys.exit(0)

    print("[info] Sending toggle to power ON...")
    toggle_power(ip)

    start = time.time()
    while time.time() - start < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        status = get_status(ip)
        print(f"[poll] Status: {status}")
        if status == "ON":
            print("✅ Projector is now ON (or in STARTUP).")
            sys.exit(0)

    print("⚠️ Timeout waiting for projector to power ON.")
    sys.exit(1)


if __name__ == "__main__":
    main()
