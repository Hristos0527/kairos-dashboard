#!/usr/bin/env python3
"""Shopify revenue + profit (COGS deducted) for Kairos profit block.

Data sources:
- Orders: Glux-shopify MCP ``get-orders`` (paged, filtered by date client-side)
- Product cost: ``data/product_costs.json`` (SKU → cost per unit in HUF)

Limitations:
- The Glux-shopify MCP ``get-orders`` returns oldest-first with no date filter.
  July 2026 orders need either a Pipedream Shopify connection (search-orders)
  or a Shopify Admin API token for REST filtering.
- Shopify variant ``cost`` is not exposed by the MCP; fill ``product_costs.json``.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COSTS_FILE = ROOT / "data" / "product_costs.json"


@dataclass
class ShopifyTotals:
    revenue: float = 0.0
    cogs: float = 0.0
    profit: float = 0.0
    order_count: int = 0
    by_product: dict[str, dict[str, float]] = field(default_factory=dict)


def parse_money(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    cleaned = re.sub(r"[^\d,.\-]", "", text.replace(" ", ""))
    if not cleaned:
        return 0.0
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def day_bounds(d: date) -> tuple[int, int]:
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def month_bounds(d: date) -> tuple[int, int]:
    start = datetime(d.year, d.month, 1, tzinfo=timezone.utc)
    if d.month == 12:
        next_month = datetime(d.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(d.year, d.month + 1, 1, tzinfo=timezone.utc)
    end = int(next_month.timestamp()) - 1
    return int(start.timestamp()), end


def load_costs() -> dict[str, float]:
    """Load SKU → cost per unit (HUF) from data/product_costs.json."""
    if not COSTS_FILE.exists():
        return {}
    data = json.loads(COSTS_FILE.read_text(encoding="utf-8"))
    costs: dict[str, float] = {}
    for item in data.get("products", []):
        sku = (item.get("sku") or "").strip()
        cost = parse_money(item.get("cost"))
        if sku and cost:
            costs[sku] = cost
    return costs


def order_in_range(order: dict[str, Any], start_ts: int, end_ts: int) -> bool:
    created = order.get("createdAt") or order.get("created_at") or ""
    if not created:
        return False
    try:
        ts = int(datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp())
    except (ValueError, TypeError):
        return False
    return start_ts <= ts <= end_ts


def is_paid(order: dict[str, Any]) -> bool:
    status = (order.get("financialStatus") or order.get("financial_status") or "").upper()
    return status in ("PAID", "PARTIALLY_PAID", "PARTIALLY_REFUNDED")


def sum_order(order: dict[str, Any], costs: dict[str, float]) -> tuple[float, float, float]:
    """Return (revenue, cogs, profit) for a single order."""
    revenue = parse_money((order.get("subtotalPrice") or {}).get("amount") or order.get("totalPrice", {}).get("amount"))
    cogs = 0.0
    for item in order.get("lineItems", []):
        qty = int(item.get("quantity") or 0)
        variant = item.get("variant") or {}
        sku = (variant.get("sku") or "").strip()
        unit_cost = costs.get(sku, 0.0)
        cogs += unit_cost * qty
    profit = revenue - cogs
    return revenue, cogs, profit


def build_shopify_block(
    orders: list[dict[str, Any]],
    target: date | None = None,
) -> dict[str, Any]:
    target = target or date.today()
    day_start, day_end = day_bounds(target)
    month_start, month_end = month_bounds(target)
    costs = load_costs()

    day_totals = ShopifyTotals()
    mtd_totals = ShopifyTotals()

    for order in orders:
        if not is_paid(order):
            continue
        rev, cogs, profit = sum_order(order, costs)
        created = order.get("createdAt") or ""
        try:
            ts = int(datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp())
        except (ValueError, TypeError):
            continue

        if month_start <= ts <= month_end:
            mtd_totals.revenue += rev
            mtd_totals.cogs += cogs
            mtd_totals.profit += profit
            mtd_totals.order_count += 1
            if day_start <= ts <= day_end:
                day_totals.revenue += rev
                day_totals.cogs += cogs
                day_totals.profit += profit
                day_totals.order_count += 1

    return {
        "status": "ok",
        "currency": "HUF",
        "today": {
            "revenue": round(day_totals.revenue, 2),
            "cogs": round(day_totals.cogs, 2),
            "profit": round(day_totals.profit, 2),
            "orders": day_totals.order_count,
        },
        "month_to_date": {
            "revenue": round(mtd_totals.revenue, 2),
            "cogs": round(mtd_totals.cogs, 2),
            "profit": round(mtd_totals.profit, 2),
            "orders": mtd_totals.order_count,
        },
        "cost_source": str(COSTS_FILE.name) if COSTS_FILE.exists() else "missing",
        "note": (
            "Bevétel = subtotalPrice. Profit = bevétel − COGS (SKU költség × db). "
            "Ha product_costs.json hiányzik, COGS = 0 (profit = bevétel)."
        ),
    }


def main() -> None:
    # Standalone test: load orders from a cached JSON file
    cache = ROOT / "data" / "shopify_orders_cache.json"
    if cache.exists():
        orders = json.loads(cache.read_text(encoding="utf-8"))
    else:
        orders = []
        print(f"Note: {cache} not found — populate via MCP get-orders first", flush=True)

    block = build_shopify_block(orders)
    print(json.dumps(block, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
