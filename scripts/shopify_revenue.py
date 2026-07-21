#!/usr/bin/env python3
"""Shopify revenue + profit via ShopifyQL (Admin GraphQL shopifyqlQuery).

Uses the same Dev Dashboard client credentials as the Glux-shopify MCP:
  MYSHOPIFY_DOMAIN, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET

No per-order fetch — aggregates FROM sales (total_sales, net_sales, COGS, gross_profit).
Requires write_reports (or read_reports) on the Shopify app.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Any

API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-01")


def _env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing env {name}")
    return value


def exchange_token() -> tuple[str, str]:
    """Return (access_token, shop_domain) via client_credentials."""
    domain = _env("MYSHOPIFY_DOMAIN")
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": _env("SHOPIFY_CLIENT_ID"),
            "client_secret": _env("SHOPIFY_CLIENT_SECRET"),
        }
    ).encode()
    req = urllib.request.Request(
        f"https://{domain}/admin/oauth/access_token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Shopify token exchange returned no access_token")
    return token, domain


def graphql(domain: str, token: str, query: str) -> dict[str, Any]:
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"https://{domain}/admin/api/{API_VERSION}/graphql.json",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def shopifyql(domain: str, token: str, sql: str) -> list[dict[str, Any]]:
    query = (
        "{ shopifyqlQuery(query: %s) { parseErrors tableData { rows } } }"
        % json.dumps(sql)
    )
    data = graphql(domain, token, query)
    node = (data.get("data") or {}).get("shopifyqlQuery") or {}
    errors = node.get("parseErrors") or []
    if errors:
        raise RuntimeError(f"ShopifyQL parseErrors: {errors}")
    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    table = node.get("tableData") or {}
    return list(table.get("rows") or [])


def _money(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(row: dict[str, Any], key: str) -> int:
    try:
        return int(float(row.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def _period(row: dict[str, Any]) -> dict[str, Any]:
    net = _money(row, "net_sales")
    cogs = _money(row, "cost_of_goods_sold")
    profit = row.get("gross_profit")
    profit_f = _money(row, "gross_profit") if profit is not None else net - cogs
    return {
        "revenue": round(net, 2),
        "total_sales": round(_money(row, "total_sales"), 2),
        "gross_sales": round(_money(row, "gross_sales"), 2),
        "cogs": round(cogs, 2),
        "profit": round(profit_f, 2),
        "orders": _int(row, "orders"),
    }


def build_shopify_block(target: date | None = None) -> dict[str, Any]:
    """Fetch today + MTD sales aggregates via ShopifyQL."""
    target = target or date.today()
    day = target.isoformat()
    month_start = target.replace(day=1).isoformat()

    try:
        token, domain = exchange_token()
    except Exception as exc:  # noqa: BLE001 — surface as status for dashboard
        return {
            "status": "error",
            "currency": "HUF",
            "source": "shopifyql",
            "error": str(exc),
            "hint": "Set MYSHOPIFY_DOMAIN + SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET (same as Glux-shopify MCP).",
            "today": {"revenue": 0, "cogs": 0, "profit": 0, "orders": 0},
            "month_to_date": {"revenue": 0, "cogs": 0, "profit": 0, "orders": 0},
        }

    sql_today = (
        "FROM sales SHOW total_sales, net_sales, gross_sales, orders, "
        f"cost_of_goods_sold, gross_profit SINCE {day} UNTIL {day}"
    )
    sql_mtd = (
        "FROM sales SHOW total_sales, net_sales, gross_sales, orders, "
        f"cost_of_goods_sold, gross_profit SINCE {month_start} UNTIL {day}"
    )

    try:
        today_rows = shopifyql(domain, token, sql_today)
        mtd_rows = shopifyql(domain, token, sql_mtd)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")[:500]
        return {
            "status": "error",
            "currency": "HUF",
            "source": "shopifyql",
            "error": f"HTTP {exc.code}: {body}",
            "today": {"revenue": 0, "cogs": 0, "profit": 0, "orders": 0},
            "month_to_date": {"revenue": 0, "cogs": 0, "profit": 0, "orders": 0},
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "currency": "HUF",
            "source": "shopifyql",
            "error": str(exc),
            "today": {"revenue": 0, "cogs": 0, "profit": 0, "orders": 0},
            "month_to_date": {"revenue": 0, "cogs": 0, "profit": 0, "orders": 0},
        }

    today = _period((today_rows or [{}])[0])
    mtd = _period((mtd_rows or [{}])[0])

    return {
        "status": "ok",
        "currency": "HUF",
        "source": "shopifyql",
        "as_of": day,
        "today": today,
        "month_to_date": mtd,
        "note": (
            "ShopifyQL FROM sales (Admin API). "
            "Bevétel = net_sales, COGS = cost_of_goods_sold, Profit = gross_profit."
        ),
    }


def main() -> None:
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    print(json.dumps(build_shopify_block(target), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
