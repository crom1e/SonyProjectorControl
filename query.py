#!/usr/bin/env python3
"""
query.py — read Sony VPL-FH30 power status from its web UI.

Defaults:
  IP:       192.168.250.1
  Status:   http://<IP>/info_data.htm  (no auth)

Exit codes:
  0 = ON
  2 = OFF (treats STANDBY as OFF)
  3 = COOLING / WARMUP
  4 = UNKNOWN / parse or network error
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
import urllib.error
import re

STATUS_RE = re.compile(r"var\s+info_status_value\s*=\s*\[([^\]]*)\]", re.IGNORECASE)
QUOTED_ITEM_RE = re.compile(r"'([^']*)'")  # pull 'STANDBY' etc.

def fetch(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fh30-query/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    # the page is tiny; treat as ASCII/latin-1 if charset is missing
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")

def parse_info_status(html: str) -> tuple[str | None, list[str]]:
    """
    Returns (status_first_element, full_array_items).
    status_first_element is the first string in info_status_value JS array, or None if not found.
    """
    # Collapse newlines (the regex would work either way, but this helps when printing snippets)
    compact = html.replace("\r", "").replace("\n", "")
    m = STATUS_RE.search(compact)
    if not m:
        return None, []
    array_content = m.group(1)
    items = QUOTED_ITEM_RE.findall(array_content)
    first = items[0] if items else None
    return first, items

def normalize_status(s: str | None) -> str:
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

def main():
    p = argparse.ArgumentParser(description="Query Sony VPL-FH30 power status.")
    p.add_argument("--ip", default="192.168.250.1", help="Projector IP (default: 192.168.250.1)")
    p.add_argument("--url", help="Override status URL (default: http://<IP>/info_data.htm)")
    p.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout seconds (default: 5.0)")
    p.add_argument("--debug", action="store_true", help="Print parsing details to stderr")
    args = p.parse_args()

    url = args.url or f"http://{args.ip}/info_data.htm"

    try:
        html = fetch(url, args.timeout)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print("UNKNOWN")
        if args.debug:
            print(f"[debug] fetch error: {e}", file=sys.stderr)
        sys.exit(4)

    first, items = parse_info_status(html)
    status = normalize_status(first)

    # Optional debug info
    if args.debug:
        print(f"[debug] url={url}", file=sys.stderr)
        snippet = STATUS_RE.search(html.replace("\r", "").replace("\n", ""))
        if snippet:
            print(f"[debug] matched: {snippet.group(0)[:300]}...", file=sys.stderr)
        print(f"[debug] items={items!r}", file=sys.stderr)
        print(f"[debug] first='{first}'  -> normalized='{status}'", file=sys.stderr)

    print(status)

    # Exit codes as agreed
    if status == "ON":
        sys.exit(0)
    if status == "OFF":
        sys.exit(2)
    if status == "COOLING":
        sys.exit(3)
    sys.exit(4)

if __name__ == "__main__":
    main()
