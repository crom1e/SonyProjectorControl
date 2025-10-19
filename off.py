#!/usr/bin/env python3
"""
off.py — power OFF the Sony VPL-FH30 via its web interface.

Logic:
  1) Query http://<IP>/info_data.htm  (no auth)
  2) Parse JS array info_status_value
  3) If status is ON/STARTUP → send GET to http://<IP>/custom/01
  4) Poll until status becomes OFF or timeout
"""
from __future__ import annotations
import sys
import time
import urllib.request
import re

IP_DEFAULT = "192.168.250.1"
STATUS_URL_TEMPLATE = "http://{ip}/info_data.htm"
TOGGLE_URL_TEMPLATE = "http://{ip}/custom/01"
TIMEOUT_SEC = 5.0
POLL_INTERVAL = 5
MAX_WAIT = 180  # cooling to OFF can take a while

STATUS_RE = re.compile(r"var\s+info_status_value\s*=\s*\[([^\]]*)\]", re.IGNORECASE)
QUOTED_ITEM_RE = re.compile(r"'([^']*)'")

def fetch(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fh30-off/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")

def parse_info_status(html: str) -> str | None:
    compact = html.replace("\r", "").replace("\n", "")
    m = STATUS_RE.search(compact)
    if not m:
        return None
    items = QUOTED_ITEM_RE.findall(m.group(1))
    return items[0] if items else None

def normalize_status(s: str | None) -> str:
    """
    Map raw projector status to: ON, OFF, COOLING, UNKNOWN.
    Treat STARTUP1/2 as ON.
    """
    if s is None:
        return "UNKNOWN"
    up = s.strip().upper()
    if up in ("ON", "STARTUP", "STARTUP1", "STARTUP2", "POWER ON"):
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
    return normalize_status(parse_info_status(html))

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

    if status == "OFF":
        print("✅ Projector already OFF.")
        sys.exit(0)

    # If cooling or warming, just wait it out to OFF (don’t toggle or we risk turning it back on)
    if status == "COOLING":
        print("[info] Projector is cooling; waiting for OFF...")

    # If it's ON (incl. STARTUP states), send the toggle to power down.
    if status == "ON":
        print("[info] Sending toggle to power OFF...")
        toggle_power(ip)

    # Poll until OFF or timeout
    start = time.time()
    while time.time() - start < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        status = get_status(ip)
        print(f"[poll] Status: {status}")
        if status == "OFF":
            print("✅ Projector is now OFF.")
            sys.exit(0)

    print("⚠️ Timeout waiting for projector to power OFF.")
    sys.exit(1)

if __name__ == "__main__":
    main()
