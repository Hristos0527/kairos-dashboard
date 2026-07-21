#!/usr/bin/env python3
"""RepairDesk cash-basis revenue (payments received) for Kairos profit block.

Auth model:
- The team secret ``repairdesk_api`` is the master key (Bearer auth) used to
  list store locations via ``/appointment/locations``.
- Each location exposes its own ``api_key`` in that response. Per-store invoice
  listings require that store-specific key as a query parameter
  (``?api_key=<store_key>``); Bearer auth returns an empty result for them.
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
from typing import Any

BASE_URL = "https://api.repairdesk.co/api/web/v1"
DEFAULT_STORES = ("Allee", "Etele", "Duna")


@dataclass
class StoreRevenue:
    name: str
    today: float = 0.0
    month_to_date: float = 0.0
    invoice_count: int = 0


@dataclass
class RevenueTotals:
    today: float = 0.0
    month_to_date: float = 0.0
    by_store: dict[str, StoreRevenue] = field(default_factory=dict)
    invoice_count: int = 0


def master_key() -> str:
    return (
        os.environ.get("repairdesk_api", "").strip()
        or os.environ.get("Repairdesk", "").strip()
    )


def _master_request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call RepairDesk with the master key using Bearer auth."""
    key = master_key()
    if not key:
        raise RuntimeError("Missing repairdesk_api secret")

    q = urllib.parse.urlencode(params or {})
    url = f"{BASE_URL}{path}" + (f"?{q}" if q else "")
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
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
        msg = payload.get("message") or (payload.get("data") or {}).get("message")
        raise RuntimeError(f"RepairDesk API {code}: {msg}")
    return payload


def _store_request(path: str, store_key: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call RepairDesk with a per-store key as query param (Bearer returns empty)."""
    q = dict(params or {})
    q["api_key"] = store_key
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
        msg = payload.get("message") or (payload.get("data") or {}).get("message")
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


def short_store_name(full_name: str) -> str:
    """'LCDFIX Allee' → 'Allee'."""
    raw = (full_name or "").strip()
    if not raw:
        return "Unknown"
    lowered = raw.lower()
    for prefix in ("lcdfix ", "lcd fix "):
        if lowered.startswith(prefix):
            return raw[len(prefix):].strip() or raw
    return raw


def fetch_locations() -> list[dict[str, str]]:
    """Return list of {id, name, api_key} for each store location."""
    payload = _master_request("/appointment/locations")
    data = payload.get("data")
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("locations") or data.get("locationData") or []
    else:
        items = []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = item.get("api_key") or ""
        name = item.get("name") or item.get("store_name") or ""
        lid = str(item.get("id") or "")
        if key and name:
            out.append({"id": lid, "name": short_store_name(name), "api_key": key})
    return out


def fetch_store_invoices(store_key: str, from_ts: int, to_ts: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = _store_request(
            "/invoices",
            store_key,
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
        pagination = data.get("pagination") or {}
        if not pagination.get("next_page_exist"):
            break
        page = int(pagination.get("next_page") or page + 1)
        if page > 50:
            break
    return rows


def sum_store_in_range(
    invoices: list[dict[str, Any]],
    day_start: int,
    day_end: int,
    month_start: int,
    month_end: int,
) -> tuple[float, float, int]:
    today_total = 0.0
    mtd_total = 0.0
    count = 0
    for row in invoices:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else row
        created = int(summary.get("created_date") or 0)
        amount = parse_money(
            summary.get("amount_paid")
            or summary.get("total_without_symbol")
            or summary.get("total")
        )
        if month_start <= created <= month_end:
            mtd_total += amount
            count += 1
            if day_start <= created <= day_end:
                today_total += amount
    return today_total, mtd_total, count


def build_profit_block(target: date | None = None) -> dict[str, Any]:
    target = target or date.today()
    day_start, day_end = day_bounds(target)
    month_start, month_end = month_bounds(target)

    try:
        locations = fetch_locations()
        if not locations:
            raise RuntimeError(
                "No store locations returned — check repairdesk_api master key"
            )

        by_store: dict[str, StoreRevenue] = {}
        for loc in locations:
            invoices = fetch_store_invoices(loc["api_key"], month_start, month_end)
            today, mtd, cnt = sum_store_in_range(
                invoices, day_start, day_end, month_start, month_end
            )
            by_store[loc["name"]] = StoreRevenue(
                name=loc["name"], today=today, month_to_date=mtd, invoice_count=cnt
            )

        today_total = round(sum(s.today for s in by_store.values()), 2)
        mtd_total = round(sum(s.month_to_date for s in by_store.values()), 2)
        invoice_total = sum(s.invoice_count for s in by_store.values())

        return {
            "status": "ok",
            "currency": "HUF",
            "as_of": target.isoformat(),
            "repairdesk": {
                "status": "ok",
                "basis": "cash",
                "note": "Üzletenkénti API kulcs (locations → api_key). Befizetés összeg + számla dátum.",
                "locations": [s.name for s in by_store.values()],
                "today": {
                    "total": today_total,
                    "by_store": {k: round(v.today, 2) for k, v in by_store.items()},
                },
                "month_to_date": {
                    "total": mtd_total,
                    "by_store": {k: round(v.month_to_date, 2) for k, v in by_store.items()},
                },
                "invoice_count": invoice_total,
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
                    "Master kulcs (repairdesk_api) Bearer auth → /appointment/locations "
                    "→ üzletenkénti api_key query paraméterrel."
                ),
            },
        }


def main() -> None:
    print(json.dumps(build_profit_block(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
