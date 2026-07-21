#!/usr/bin/env python3
"""RepairDesk cash-basis revenue (payments received) for Kairos profit block."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

BASE_URL = "https://api.repairdesk.co/api/web/v1"
DEFAULT_STORES = ("Allee", "Etele", "Duna")


@dataclass
class RevenueTotals:
    total: float = 0.0
    by_store: dict[str, float] | None = None


def api_key() -> str:
    return (
        os.environ.get("repairdesk_api", "").strip()
        or os.environ.get("Repairdesk", "").strip()
    )


def _request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise RuntimeError("Missing repairdesk_api secret")

    q = dict(params or {})
    q["api_key"] = key
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; KairosProfit/1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"RepairDesk HTTP {exc.code}: {body}") from exc

    if not payload.get("success"):
        code = payload.get("statusCode")
        msg = payload.get("message") or payload.get("data", {}).get("message")
        raise RuntimeError(f"RepairDesk API {code}: {msg}")
    return payload


def parse_money(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    # Keep digits, comma, dot, minus
    cleaned = re.sub(r"[^\d,.\-]", "", text.replace(" ", ""))
    if not cleaned:
        return 0.0
    # European: 1.234,56 → 1234.56
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


def normalize_store(name: str, aliases: dict[str, str]) -> str:
    raw = (name or "").strip() or "Unknown"
    lower = raw.lower()
    for key, label in aliases.items():
        if key.lower() in lower:
            return label
    return raw


def sum_payments_in_range(
    invoices: list[dict[str, Any]],
    start_ts: int,
    end_ts: int,
    aliases: dict[str, str],
) -> RevenueTotals:
    by_store: dict[str, float] = {}
    total = 0.0

    for row in invoices:
        summary = row.get("summary") or row
        store = normalize_store(summary.get("store_name", ""), aliases)
        payments = row.get("payments") or []
        if payments:
            for payment in payments:
                ts = int(payment.get("payment_date") or payment.get("created_on") or 0)
                if ts < start_ts or ts > end_ts:
                    continue
                amount = parse_money(payment.get("amount"))
                total += amount
                by_store[store] = by_store.get(store, 0.0) + amount
        else:
            # Fallback: paid invoice created in range
            created = int(summary.get("created_date") or 0)
            if start_ts <= created <= end_ts:
                amount = parse_money(summary.get("amount_paid") or summary.get("total"))
                total += amount
                by_store[store] = by_store.get(store, 0.0) + amount

    return RevenueTotals(total=total, by_store=by_store)


def fetch_paid_invoices(from_ts: int, to_ts: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 0
    while True:
        payload = _request(
            "/invoices",
            {
                "page": page,
                "pagesize": 100,
                "status": "Paid",
                "from_date": from_ts,
                "to_date": to_ts,
                "sort_order": "DESC",
            },
        )
        data = payload.get("data") or {}
        batch = data.get("invoiceData") or data.get("invoices") or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        if page > 200:
            break
    return rows


def fetch_locations() -> list[str]:
    try:
        payload = _request("/appointment/locations")
    except RuntimeError:
        return []
    data = payload.get("data") or {}
    locations = data.get("locations") or data.get("locationData") or data
    if isinstance(locations, list):
        names = []
        for item in locations:
            if isinstance(item, dict):
                names.append(item.get("name") or item.get("store_name") or str(item))
            else:
                names.append(str(item))
        return [n for n in names if n]
    return []


def build_profit_block(target: date | None = None) -> dict[str, Any]:
    target = target or date.today()
    aliases = {
        "allee": "Allee",
        "etele": "Etele",
        "duna": "Duna",
        "plaza": "Duna",
    }

    day_start, day_end = day_bounds(target)
    month_start, month_end = month_bounds(target)

    try:
        locations = fetch_locations()
        invoices_month = fetch_paid_invoices(month_start, month_end)
        month_totals = sum_payments_in_range(invoices_month, month_start, month_end, aliases)
        day_totals = sum_payments_in_range(invoices_month, day_start, day_end, aliases)

        return {
            "status": "ok",
            "currency": "HUF",
            "as_of": target.isoformat(),
            "repairdesk": {
                "status": "ok",
                "basis": "cash",
                "locations": locations or list(DEFAULT_STORES),
                "today": {
                    "total": round(day_totals.total, 2),
                    "by_store": {k: round(v, 2) for k, v in (day_totals.by_store or {}).items()},
                },
                "month_to_date": {
                    "total": round(month_totals.total, 2),
                    "by_store": {k: round(v, 2) for k, v in (month_totals.by_store or {}).items()},
                },
                "invoice_count": len(invoices_month),
            },
        }
    except Exception as exc:  # noqa: BLE001 — surface API errors in dashboard JSON
        return {
            "status": "error",
            "currency": "HUF",
            "as_of": target.isoformat(),
            "repairdesk": {
                "status": "error",
                "message": str(exc),
                "hint": (
                    "RepairDesk → Store Settings → API key: másold be a repairdesk_api secretbe. "
                    "Ha 401: új kulcs generálás szükséges."
                ),
            },
        }


def main() -> None:
    print(json.dumps(build_profit_block(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
