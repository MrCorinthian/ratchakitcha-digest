#!/usr/bin/env python3
"""Fetch the gazette, build the site, and notify when secrets exist."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ratchakitcha.pipeline import run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--offline", action="store_true", help="build from data/items without fetching")
    parser.add_argument("--no-summarize", action="store_true")
    parser.add_argument("--no-notify", action="store_true")
    args = parser.parse_args()
    run(
        args.root,
        fetch=not args.offline,
        summarize=not args.no_summarize,
        notify=not args.no_notify,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
