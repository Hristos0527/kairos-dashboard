#!/usr/bin/env python3
"""Merge RepairDesk (and later Shopify/Ads) profit data into data/latest.json."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from repairdesk_revenue import build_profit_block

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "latest.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Update profit block in Kairos latest.json")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON, help="Path to latest.json")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    profit = build_profit_block(target)

    path = args.json
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {}

    data["profit"] = profit
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {path} — profit.status={profit.get('status')}")


if __name__ == "__main__":
    main()
