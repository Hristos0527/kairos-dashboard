#!/usr/bin/env python3
"""Merge RepairDesk + Shopify profit data into data/latest.json."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from repairdesk_revenue import build_profit_block
from shopify_revenue import build_shopify_block

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "latest.json"
SHOPIFY_CACHE = ROOT / "data" / "shopify_orders_cache.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Update profit block in Kairos latest.json")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON, help="Path to latest.json")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    profit = build_profit_block(target)

    shopify_orders: list[dict] = []
    if SHOPIFY_CACHE.exists():
        shopify_orders = json.loads(SHOPIFY_CACHE.read_text(encoding="utf-8"))
    profit["shopify"] = build_shopify_block(shopify_orders, target)

    path = args.json
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {}
    data["profit"] = profit
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {path}")
    print(f"  repairdesk: {profit['repairdesk']['status']} — today {profit['repairdesk'].get('today',{}).get('total',0):,.0f} Ft")
    print(f"  shopify:    {profit['shopify']['status']} — today {profit['shopify']['today']['revenue']:,.0f} Ft revenue, {profit['shopify']['today']['profit']:,.0f} Ft profit, {profit['shopify']['today']['orders']} orders")


if __name__ == "__main__":
    main()
