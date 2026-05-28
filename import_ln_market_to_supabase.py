"""
Import Book1_evaluated_penalty_18m.xlsx into Supabase tables for the LiDex LN market dashboard.

Install:
    pip install pandas openpyxl httpx python-dotenv

Environment variables:
    SUPABASE_URL=https://xxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

Run:
    python import_ln_market_to_supabase_ssl_off.py --excel Book1_evaluated_penalty_18m.xlsx

Important:
    Use the SERVICE ROLE key only on your local machine or backend job.
    Never put the service role key in Next.js client code.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import httpx
import pandas as pd
from dotenv import load_dotenv


EVAL_SHEET_CANDIDATES = ["Evaluation Inputs", "Sheet1", "Main", "LN Evaluation"]
PUBLISHER_SHEET_CANDIDATES = ["Publisher Activity", "Publishers"]
BOOKS_SHEET_CANDIDATES = ["Licensed Books", "Books", "Licensed Book"]
IMPORT_NOTE = "Imported from evaluated LN workbook for LiDex market dashboard"


def snake(name: str) -> str:
    name = str(name).strip()
    name = re.sub(r"[^\w\s]+", " ", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name)
    return name.lower().strip("_")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null", "nat"}:
        return None
    return text


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    text = text.replace(",", "")
    text = text.replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value: Any) -> int | None:
    f = to_float(value)
    if f is None:
        return None
    return int(round(f))


def to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return bool(int(value))
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "có"}:
        return True
    if text in {"0", "false", "no", "n", "không"}:
        return False
    return None


def to_date_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = clean_text(value)
    if not text:
        return None
    dt = pd.to_datetime(text, errors="coerce", dayfirst=False)
    if pd.isna(dt):
        dt = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        return None
    return dt.date().isoformat()


def to_datetime_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.to_pydatetime().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day).isoformat()
    text = clean_text(value)
    if not text:
        return None
    dt = pd.to_datetime(text, errors="coerce", dayfirst=False)
    if pd.isna(dt):
        dt = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        return None
    return dt.to_pydatetime().isoformat()


def parse_drop_probability(value: Any) -> float | None:
    """
    Store drop probability as 0-1.
    Handles values such as 0.237, 23.7, "23.7%", "0.237".
    """
    if value is None:
        return None
    text = str(value).strip()
    has_percent = "%" in text
    n = to_float(value)
    if n is None:
        return None
    if has_percent or n > 1:
        n = n / 100.0
    return clamp(n, 0.0, 0.99)


def clamp(value: float | None, lo: float = 0.0, hi: float = 10.0) -> float | None:
    if value is None:
        return None
    return max(lo, min(hi, float(value)))


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def pick(row: pd.Series, aliases: Iterable[str]) -> Any:
    for col in aliases:
        if col in row.index:
            return row[col]
    lower_map = {str(c).lower().strip(): c for c in row.index}
    for col in aliases:
        key = col.lower().strip()
        if key in lower_map:
            return row[lower_map[key]]
    return None


def choose_sheet(xls: pd.ExcelFile, candidates: list[str], required: bool) -> str | None:
    exact = {s.lower(): s for s in xls.sheet_names}
    for candidate in candidates:
        if candidate.lower() in exact:
            return exact[candidate.lower()]
    if required:
        raise ValueError(f"Could not find any of these sheets: {candidates}. Available: {xls.sheet_names}")
    return None


def parse_json_cell(value: Any) -> Any:
    text = clean_text(value)
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


def risk_band(drop_probability: float | None, evaluation: str | None) -> str | None:
    if evaluation == "Completed":
        return "0–10%"
    if drop_probability is None:
        return None
    if drop_probability <= 0.10:
        return "0–10%"
    if drop_probability <= 0.35:
        return "11–35%"
    if drop_probability <= 0.65:
        return "36–65%"
    if drop_probability <= 0.85:
        return "66–85%"
    return "86–99%"


def publisher_reliability(activity: str | None, releases_24m: int | None) -> float:
    base = {
        "Active": 8.0,
        "Moderate": 6.5,
        "Low": 4.5,
        "Inactive": 2.0,
    }.get(activity or "", 5.0)
    bonus = min((releases_24m or 0) / 50.0 * 2.0, 2.0)
    return clamp(base + bonus) or 5.0


def release_speed_score(avg_gap_months: float | None, months_since_last: float | None) -> float:
    # Gap/cadence component
    if avg_gap_months is None:
        gap_score = 5.0
    elif avg_gap_months <= 4:
        gap_score = 9.5
    elif avg_gap_months <= 6:
        gap_score = 8.5
    elif avg_gap_months <= 12:
        gap_score = 6.5
    elif avg_gap_months <= 18:
        gap_score = 4.5
    elif avg_gap_months <= 24:
        gap_score = 3.0
    else:
        gap_score = 1.5

    # Freshness component
    if months_since_last is None:
        recency_score = 5.0
    elif months_since_last <= 6:
        recency_score = 9.0
    elif months_since_last <= 12:
        recency_score = 7.0
    elif months_since_last <= 18:
        recency_score = 5.0
    elif months_since_last <= 24:
        recency_score = 3.0
    elif months_since_last <= 36:
        recency_score = 1.8
    else:
        recency_score = 1.0

    return round(0.6 * gap_score + 0.4 * recency_score, 2)


def catch_up_score(vn_volumes: int | None, jp_volumes: int | None) -> tuple[float | None, float | None]:
    if not vn_volumes or not jp_volumes or jp_volumes <= 0:
        return None, None
    ratio = vn_volumes / jp_volumes
    return round(ratio, 4), round(clamp(ratio * 10.0) or 0, 2)


def completion_safety(drop_probability: float | None, evaluation: str | None) -> float:
    if evaluation == "Completed":
        return 10.0
    if drop_probability is None:
        return 5.0
    return round(clamp((1.0 - drop_probability) * 10.0) or 0, 2)


def market_momentum(activity: str | None, releases_12m: int | None, releases_24m: int | None, months_since_last: float | None) -> float:
    activity_base = {
        "Active": 7.5,
        "Moderate": 6.0,
        "Low": 4.0,
        "Inactive": 2.0,
    }.get(activity or "", 5.0)

    recent_share = 0.0
    if releases_24m and releases_24m > 0:
        recent_share = (releases_12m or 0) / releases_24m
    recent_score = clamp(recent_share * 10.0) or 0

    if months_since_last is None:
        freshness = 5.0
    elif months_since_last <= 6:
        freshness = 8.5
    elif months_since_last <= 12:
        freshness = 6.5
    elif months_since_last <= 18:
        freshness = 4.5
    else:
        freshness = 2.0

    return round(0.45 * activity_base + 0.35 * recent_score + 0.20 * freshness, 2)


def percentile_scores(values_by_key: dict[str, int | float | None]) -> dict[str, float | None]:
    valid = [(k, float(v)) for k, v in values_by_key.items() if v is not None and not pd.isna(v)]
    if not valid:
        return {k: None for k in values_by_key}
    valid_sorted = sorted(valid, key=lambda kv: kv[1])
    n = len(valid_sorted)
    out = {k: None for k in values_by_key}
    if n == 1:
        out[valid_sorted[0][0]] = 5.0
        return out
    for rank, (k, _) in enumerate(valid_sorted, start=1):
        out[k] = round((rank - 1) / (n - 1) * 10.0, 2)
    return out


def read_books(xls: pd.ExcelFile, sheet_name: str | None) -> tuple[list[dict[str, Any]], dict[str, float | None]]:
    if not sheet_name:
        return [], {}

    df = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
    records: list[dict[str, Any]] = []
    popularity_raw: dict[str, int] = {}

    for _, row in df.iterrows():
        book_id = to_int(pick(row, ["ID", "Book ID", "book_id"]))
        title = clean_text(pick(row, ["Title", "Book Title", "title"]))
        if book_id is None or not title:
            continue

        source_series_id = to_int(pick(row, ["Series ID", "source_series_id"]))
        series_code = clean_text(pick(row, ["Series Code", "series_code"]))
        series_key = f"{source_series_id}|{series_code}" if source_series_id is not None and series_code else None
        view_count = to_int(pick(row, ["View Count", "view_count"]))

        if series_key and view_count is not None:
            popularity_raw[series_key] = popularity_raw.get(series_key, 0) + view_count

        records.append({
            "book_id": book_id,
            "series_key": series_key,
            "source_series_id": source_series_id,
            "series_code": series_code,
            "title": title,
            "translator": clean_text(pick(row, ["Translator"])),
            "price": to_float(pick(row, ["Price"])),
            "pages": to_int(pick(row, ["Pages"])),
            "summary": clean_text(pick(row, ["Summary"])),
            "isbn": clean_text(pick(row, ["ISBN"])),
            "cover_type": clean_text(pick(row, ["Cover Type"])),
            "cover_url": clean_text(pick(row, ["Cover URL"])),
            "is_tba": to_bool(pick(row, ["Is TBA"])),
            "retailers": parse_json_cell(pick(row, ["Retailers"])),
            "released_at": to_datetime_iso(pick(row, ["Released At", "Release Date", "released_at"])),
            "created_at_source": to_datetime_iso(pick(row, ["Created At"])),
            "updated_at_source": to_datetime_iso(pick(row, ["Updated At"])),
            "has_preview": to_bool(pick(row, ["Has Preview"])),
            "view_count": view_count,
        })

    popularity_scores = percentile_scores(popularity_raw)
    return records, popularity_scores


def read_publisher_activity(xls: pd.ExcelFile, sheet_name: str | None) -> list[dict[str, Any]]:
    if not sheet_name:
        return []

    df = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
    records: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        publisher = clean_text(pick(row, ["Publisher"]))
        if not publisher:
            continue

        records.append({
            "publisher": publisher,
            "total_linked_book_rows": to_int(pick(row, ["Total Linked Book Rows"])),
            "first_release": to_date_iso(pick(row, ["First Release"])),
            "last_release": to_date_iso(pick(row, ["Last Release"])),
            "months_since_last_release": to_float(pick(row, ["Months Since Last Release"])),
            "releases_last_12m": to_int(pick(row, ["Releases Last 12M"])),
            "releases_last_18m": to_int(pick(row, ["Releases Last 18M"])),
            "releases_last_24m": to_int(pick(row, ["Releases Last 24M"])),
            "approx_annual_release_rate": to_float(pick(row, ["Approx Annual Release Rate"])),
            "publisher_activity": clean_text(pick(row, ["Publisher Activity"])),
        })

    return records


def read_evaluations(
    xls: pd.ExcelFile,
    sheet_name: str,
    popularity_scores: dict[str, float | None],
) -> list[dict[str, Any]]:
    df = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
    records: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        title = clean_text(pick(row, ["Series Title", "Title", "series_title"]))
        if not title:
            continue

        source_series_id = to_int(pick(row, ["Series ID", "source_series_id"]))
        series_code = clean_text(pick(row, ["Series Code", "series_code"]))
        series_key = clean_text(pick(row, ["Key", "series_key"]))
        if not series_key and source_series_id is not None and series_code:
            series_key = f"{source_series_id}|{series_code}"
        if not series_key:
            # stable fallback for rare bad rows
            series_key = snake(title)

        publisher = clean_text(pick(row, ["Publisher"]))
        vn_volumes = to_int(pick(row, ["Number of Volumes", "VN Volumes", "volume_count"]))
        original_volumes = to_int(pick(row, ["Original Volumes", "JP Volumes"]))
        original_status = clean_text(pick(row, ["Original Status"]))
        months_since_release = to_float(pick(row, ["Months Since Series Release"]))
        avg_gap = to_float(pick(row, ["Series Avg Gap Months"]))
        publisher_releases_12m = to_int(pick(row, ["Publisher Releases Last 12M"]))
        publisher_releases_24m = to_int(pick(row, ["Publisher Releases Last 24M"]))
        publisher_activity = clean_text(pick(row, ["Publisher Activity"]))
        evaluation = clean_text(pick(row, ["Evalution", "Evaluation"]))
        drop_probability = parse_drop_probability(pick(row, ["Khả năng drop (Drop %)", "Drop %", "Drop Probability"]))
        ln_score = to_float(pick(row, ["LN Score"]))

        catch_ratio, catch_score = catch_up_score(vn_volumes, original_volumes)
        rel_speed = release_speed_score(avg_gap, months_since_release)
        pop_score = popularity_scores.get(series_key)
        if pop_score is None:
            # A neutral default keeps radar usable when the workbook has no Licensed Books sheet.
            pop_score = 5.0
        pub_reliability = publisher_reliability(publisher_activity, publisher_releases_24m)
        safety = completion_safety(drop_probability, evaluation)
        momentum = market_momentum(
            publisher_activity,
            publisher_releases_12m,
            publisher_releases_24m,
            months_since_release,
        )

        radar = {
            "release_speed": rel_speed,
            "catch_up_progress": catch_score,
            "popularity": pop_score,
            "publisher_reliability": pub_reliability,
            "completion_safety": safety,
            "market_momentum": momentum,
        }

        records.append({
            "series_key": series_key,
            "source_series_id": source_series_id,
            "series_code": series_code,
            "series_title": title,
            "publisher": publisher,
            "vn_volume_count": vn_volumes,
            "original_volume_count": original_volumes,
            "original_status": original_status,
            "series_last_release": to_date_iso(pick(row, ["Series Last Release"])),
            "months_since_series_release": months_since_release,
            "series_avg_gap_months": avg_gap,
            "publisher_last_release": to_date_iso(pick(row, ["Publisher Last Release"])),
            "publisher_releases_last_12m": publisher_releases_12m,
            "publisher_releases_last_24m": publisher_releases_24m,
            "publisher_activity": publisher_activity,
            "evaluation": evaluation,
            "evaluation_basis": clean_text(pick(row, ["Evaluation Basis"])),
            "vn_status": clean_text(pick(row, ["Trạng thái", "Status"])),
            "drop_probability": drop_probability,
            "ln_score": ln_score,
            "score_components": clean_text(pick(row, ["Score Components"])),
            "drop_components": clean_text(pick(row, ["Drop Components"])),
            "cover_url": clean_text(pick(row, ["Cover URL"])),
            "cover_source_title": clean_text(pick(row, ["Cover Source Title"])),
            "catch_up_ratio": catch_ratio,
            "release_speed_score": rel_speed,
            "catch_up_score": catch_score,
            "popularity_score": pop_score,
            "publisher_reliability_score": pub_reliability,
            "completion_safety_score": safety,
            "market_momentum_score": momentum,
            "radar_profile": radar,
            "risk_band": risk_band(drop_probability, evaluation),
        })

    return records


def scrub_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: scrub_for_json(v) for k, v in value.items() if scrub_for_json(v) is not None}
    if isinstance(value, list):
        return [scrub_for_json(v) for v in value]
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def scrub_record(record: dict[str, Any], keep_null_keys: bool = True) -> dict[str, Any]:
    """
    PostgREST bulk insert/upsert requires every object in the JSON array to have
    exactly the same keys. Therefore, keep top-level keys with None values.
    Nested JSON values can still be cleaned normally.
    """
    cleaned: dict[str, Any] = {}
    for k, v in record.items():
        cleaned_value = scrub_for_json(v)
        if keep_null_keys or cleaned_value is not None:
            cleaned[k] = cleaned_value
    return cleaned


class SupabaseRestClient:
    """
    Minimal Supabase PostgREST client using httpx with SSL verification disabled.

    This is used because supabase-py ClientOptions supports PostgREST timeout,
    but verify=False is not always exposed by supabase-py versions.
    """

    def __init__(self, supabase_url: str, service_role_key: str, timeout: float = 60.0) -> None:
        self.base_url = supabase_url.rstrip("/")
        self.http_client = httpx.Client(
            verify=False,   # requested: disable SSL verification
            timeout=timeout,
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self.http_client.close()

    def insert(self, table: str, record: dict[str, Any]) -> None:
        url = f"{self.base_url}/rest/v1/{quote(table)}"
        response = self.http_client.post(
            url,
            headers={"Prefer": "return=minimal"},
            json=scrub_record(record, keep_null_keys=False),
        )
        self._raise_for_status(response, table)

    def upsert_many(self, table: str, records: list[dict[str, Any]], on_conflict: str) -> None:
        if not records:
            return

        url = f"{self.base_url}/rest/v1/{quote(table)}?on_conflict={quote(on_conflict)}"
        response = self.http_client.post(
            url,
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            json=[scrub_record(r, keep_null_keys=True) for r in records],
        )
        self._raise_for_status(response, table)

    @staticmethod
    def _raise_for_status(response: httpx.Response, table: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:2000]
            raise RuntimeError(f"Supabase REST request failed for table '{table}': {exc}\n{body}") from exc


def batch_upsert(
    supabase: SupabaseRestClient,
    table: str,
    records: list[dict[str, Any]],
    on_conflict: str,
    batch_size: int = 500,
) -> None:
    if not records:
        print(f"[SKIP] {table}: no records")
        return

    cleaned = [scrub_record(r, keep_null_keys=True) for r in records]
    total = len(cleaned)

    for start in range(0, total, batch_size):
        batch = cleaned[start:start + batch_size]
        supabase.upsert_many(table, batch, on_conflict=on_conflict)
        print(f"[UPSERT] {table}: {min(start + batch_size, total)}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", required=True, help="Path to Book1_evaluated_penalty_18m.xlsx")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    load_dotenv()

    url = "https://zragvkqsslfyarjbjmmz.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpyYWd2a3Fzc2xmeWFyamJqbW16Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjYzMzY4NCwiZXhwIjoyMDg4MjA5Njg0fQ.V2VYm1pzKLbylTkHS4nTX8T6dMqpRdENpMWLydC_jmE"
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables.")

    excel_path = Path(args.excel)
    if not excel_path.exists():
        raise FileNotFoundError(excel_path)

    xls = pd.ExcelFile(excel_path)
    eval_sheet = choose_sheet(xls, EVAL_SHEET_CANDIDATES, required=True)
    publisher_sheet = choose_sheet(xls, PUBLISHER_SHEET_CANDIDATES, required=False)
    books_sheet = choose_sheet(xls, BOOKS_SHEET_CANDIDATES, required=False)

    print(f"[INFO] Workbook: {excel_path}")
    print(f"[INFO] Evaluation sheet: {eval_sheet}")
    print(f"[INFO] Publisher sheet: {publisher_sheet or 'not found'}")
    print(f"[INFO] Books sheet: {books_sheet or 'not found'}")

    book_records, popularity_scores = read_books(xls, books_sheet)
    publisher_records = read_publisher_activity(xls, publisher_sheet)
    eval_records = read_evaluations(xls, eval_sheet, popularity_scores)

    print(f"[INFO] Evaluation records: {len(eval_records)}")
    print(f"[INFO] Book records: {len(book_records)}")
    print(f"[INFO] Publisher records: {len(publisher_records)}")

    supabase = SupabaseRestClient(url, key, timeout=60.0)

    try:
        # Optional import log.
        # Skipped by default because some Supabase projects do not grant insert
        # permission to this helper table unless the service_role key is used.
        #
        # supabase.insert("ln_import_batches", {
        #     "source_file": excel_path.name,
        #     "note": IMPORT_NOTE,
        # })

        # Upload base tables.
        batch_upsert(supabase, "ln_publisher_activity", publisher_records, on_conflict="publisher", batch_size=args.batch_size)
        batch_upsert(supabase, "ln_books", book_records, on_conflict="book_id", batch_size=args.batch_size)
        batch_upsert(supabase, "ln_evaluation_series", eval_records, on_conflict="series_key", batch_size=args.batch_size)
    finally:
        supabase.close()

    print("[DONE] LN market analytics data imported.")
    print("Next.js can now query:")
    print("  v_ln_dashboard_kpis")
    print("  v_ln_scatter")
    print("  v_ln_series_radar")
    print("  v_ln_publisher_leaderboard")
    print("  v_ln_market_growth")
    print("  v_ln_publisher_monthly_activity")
    print("  v_ln_top_ongoing")
    print("  v_ln_drop_risk_summary")


if __name__ == "__main__":
    main()
