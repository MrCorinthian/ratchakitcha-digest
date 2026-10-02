#!/usr/bin/env python3
"""Build a preview site from the checked-in October 2026 spreadsheet fixture.

Does not write the repository data/items directory and does not use the network.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ratchakitcha.classify import classify  # noqa: E402
from ratchakitcha.site import build_site  # noqa: E402
from ratchakitcha.store import merge_items  # noqa: E402
from ratchakitcha.xlsx_source import parse_xlsx  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("/tmp/gazette-site"))
    parser.add_argument(
        "--fixture",
        type=Path,
        default=ROOT / "tests" / "fixtures" / "sample_monthly_2026-10.xlsx",
    )
    args = parser.parse_args()
    staging = args.out / "root"
    items = [classify(item) for item in parse_xlsx(args.fixture.read_bytes())]
    merge_items(staging / "data" / "items", items)
    asset_target = staging / "assets"
    asset_target.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "assets").iterdir():
        if path.is_file():
            (asset_target / path.name).write_bytes(path.read_bytes())
    site = build_site(staging, site_dir=args.out / "site")
    print(f"{len(items)} items -> {site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
