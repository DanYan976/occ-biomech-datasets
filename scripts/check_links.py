#!/usr/bin/env python3
"""
Check that every dataset's access.url still resolves.

Reads datasets/*.yaml (ignoring "_" files and entries without access.url),
requests each URL, and reports:
  - DEAD:  404/410, other 4xx/5xx, or connection failure after a retry
  - ALIVE (bot-blocked): 403/429 — the server answered, it just dislikes
    scripts (e.g. institutional repositories), so it does not fail the run

Writes a Markdown report (for a GitHub issue body) with --report PATH.
Exits 1 if any link is dead. Run from the repo root:
  python scripts/check_links.py [--report report.md]
"""
from __future__ import annotations
import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pyyaml. Run: pip install pyyaml")

ROOT = Path(__file__).resolve().parents[1]
UA = "Mozilla/5.0 (compatible; OccBiomechanics-linkcheck; +https://occbiomechanics.org)"
BOT_BLOCKED = {403, 429}
TIMEOUT = 30


def fetch_status(url: str) -> tuple[int | None, str]:
    """Return (http_status, detail). Status None means the request never got
    an HTTP answer (DNS failure, timeout, TLS error...)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:  # URLError, timeout, TLS
        return None, f"{type(e).__name__}: {e}"


def check(url: str) -> tuple[str, str]:
    """Return (verdict, detail): verdict is 'ok', 'blocked' or 'dead'."""
    status, detail = fetch_status(url)
    if status is None or status >= 500:
        time.sleep(5)  # transient? one retry
        status, detail = fetch_status(url)
    if status is not None and 200 <= status < 400:
        return "ok", f"HTTP {status}"
    if status in BOT_BLOCKED:
        return "blocked", f"HTTP {status} (bot-blocked, treated as alive)"
    return "dead", f"HTTP {status}" if status is not None else detail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path, help="write a Markdown report here")
    args = ap.parse_args()

    rows = []
    for path in sorted((ROOT / "datasets").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        entry = yaml.safe_load(path.read_text(encoding="utf-8"))
        url = ((entry or {}).get("access") or {}).get("url")
        if not url:
            continue
        verdict, detail = check(url)
        rows.append((entry["id"], url, verdict, detail))
        print(f"{verdict.upper():8} {entry['id']:40} {detail}")

    dead = [r for r in rows if r[2] == "dead"]
    blocked = [r for r in rows if r[2] == "blocked"]

    if args.report and dead:
        lines = [
            "The monthly link check found dataset links that no longer resolve.",
            "Each one needs a replacement URL (or the entry set to a new status).",
            "",
            "| Dataset | URL | Result |",
            "|---|---|---|",
        ]
        for id_, url, _, detail in dead:
            lines.append(f"| `{id_}` | {url} | {detail} |")
        if blocked:
            lines += ["", "Answered but bot-blocked (treated as alive, listed for reference):", ""]
            for id_, url, _, detail in blocked:
                lines.append(f"- `{id_}`: {url} — {detail}")
        args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nChecked {len(rows)} links: {len(dead)} dead, {len(blocked)} bot-blocked.")
    if dead:
        sys.exit(1)


if __name__ == "__main__":
    main()
