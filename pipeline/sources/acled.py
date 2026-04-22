"""
ACLED — Armed Conflict Location & Event Data fetcher.

Pulls conflict events, actor types, and fatality counts from the ACLED
REST API.  Data supplements GDELT's protest and conflict event counts with
precise fatality information and sub-event typing.

Spec reference: §2.1 (ACLED, weekly cadence, free academic access).

Authentication (classic key+email approach — matches spec env var names):
    ACLED_API_KEY   — API key from https://developer.acleddata.com
    ACLED_EMAIL     — Email registered with ACLED

API endpoint: https://api.acleddata.com/acled/read
    Docs: https://acleddata.com/api-documentation/acled-endpoint/
    Pagination: page parameter, up to 5000 rows per request.

Output schema (raw events):
    event_id_cnty, event_date (date), year (int),
    disorder_type, event_type, sub_event_type,
    actor1, actor2, assoc_actor_1, assoc_actor_2,
    inter1, inter2, interaction,
    iso, iso3, country, region,
    admin1, admin2, admin3, location,
    latitude (float), longitude (float),
    source, notes, fatalities (int), timestamp

Aggregated schema (per country-day):
    iso3, date, events_total, fatalities_total,
    protest_events, battle_events, riot_events

Standalone usage:
    python pipeline/sources/acled.py [--days 7] [--aggregate]
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

ACLED_API_URL = "https://api.acleddata.com/acled/read"
PAGE_SIZE = 5000
REQUEST_TIMEOUT = 60

RAW_COLUMNS = [
    "event_id_cnty", "event_date", "year",
    "disorder_type", "event_type", "sub_event_type",
    "actor1", "actor2", "assoc_actor_1", "assoc_actor_2",
    "inter1", "inter2", "interaction",
    "iso", "iso3", "country", "region",
    "admin1", "admin2", "admin3", "location",
    "latitude", "longitude",
    "source", "notes", "fatalities", "timestamp",
]


def _get_credentials() -> tuple[str, str]:
    """Load ACLED credentials from environment.

    Returns:
        (api_key, email) tuple.

    Raises:
        EnvironmentError: If either var is not set.
    """
    api_key = os.environ.get("ACLED_API_KEY")
    email = os.environ.get("ACLED_EMAIL")
    if not api_key or not email:
        raise EnvironmentError(
            "ACLED_API_KEY and ACLED_EMAIL env vars must both be set. "
            "Register at https://developer.acleddata.com to get credentials."
        )
    return api_key, email


def fetch(days_back: int = 7) -> pd.DataFrame:
    """Fetch ACLED events for the past N days.

    Paginates automatically until all records for the date range are fetched.

    Args:
        days_back: Number of days to look back from today (UTC).

    Returns:
        DataFrame with RAW_COLUMNS schema.  event_date is a Python date.

    Raises:
        EnvironmentError: If credentials are not set.
        requests.HTTPError: If the API returns a non-2xx status.
    """
    api_key, email = _get_credentials()

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days_back)

    all_rows: list[dict] = []
    page = 1

    while True:
        params = {
            "key": api_key,
            "email": email,
            "event_date": f"{start_date}|{end_date}",
            "event_date_where": "BETWEEN",
            "limit": PAGE_SIZE,
            "page": page,
        }
        resp = requests.get(ACLED_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()

        if not body.get("success"):
            msgs = body.get("messages", [])
            raise RuntimeError(f"ACLED API error: {msgs}")

        rows = body.get("data", [])
        if not rows:
            break

        all_rows.extend(rows)
        print(f"  ACLED page {page}: {len(rows)} rows (total so far: {len(all_rows)})")

        # ACLED returns fewer rows than PAGE_SIZE on the last page
        if len(rows) < PAGE_SIZE:
            break
        page += 1

    if not all_rows:
        return pd.DataFrame(columns=RAW_COLUMNS)

    df = pd.DataFrame(all_rows)

    # coerce types
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date
    df["year"] = pd.to_numeric(df.get("year"), errors="coerce").astype("Int64")
    df["fatalities"] = pd.to_numeric(df.get("fatalities"), errors="coerce").fillna(0).astype(int)
    df["latitude"] = pd.to_numeric(df.get("latitude"), errors="coerce")
    df["longitude"] = pd.to_numeric(df.get("longitude"), errors="coerce")

    # ensure all schema columns are present (ACLED may omit sparse fields)
    for col in RAW_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[RAW_COLUMNS].copy()


def fetch_date_range(start: datetime, end: datetime) -> pd.DataFrame:
    """Fetch ACLED events for an arbitrary date range (used by backtest).

    Args:
        start: Start date (inclusive).
        end: End date (inclusive).

    Returns:
        DataFrame with RAW_COLUMNS schema.
    """
    api_key, email = _get_credentials()

    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    all_rows: list[dict] = []
    page = 1

    while True:
        params = {
            "key": api_key,
            "email": email,
            "event_date": f"{start_str}|{end_str}",
            "event_date_where": "BETWEEN",
            "limit": PAGE_SIZE,
            "page": page,
        }
        resp = requests.get(ACLED_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
        rows = body.get("data", [])
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        page += 1

    if not all_rows:
        return pd.DataFrame(columns=RAW_COLUMNS)

    df = pd.DataFrame(all_rows)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date
    df["fatalities"] = pd.to_numeric(df.get("fatalities"), errors="coerce").fillna(0).astype(int)
    df["latitude"] = pd.to_numeric(df.get("latitude"), errors="coerce")
    df["longitude"] = pd.to_numeric(df.get("longitude"), errors="coerce")

    for col in RAW_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[RAW_COLUMNS].copy()


def aggregate_by_country(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw ACLED events to country-day summary statistics.

    ACLED event_type values include: 'Battles', 'Protests', 'Riots',
    'Violence against civilians', 'Explosions/Remote violence',
    'Strategic developments'.

    Args:
        df: Raw ACLED events DataFrame from fetch().

    Returns:
        DataFrame with columns:
            iso3, date, events_total, fatalities_total,
            protest_events, battle_events, riot_events
    """
    if df.empty:
        return pd.DataFrame(columns=[
            "iso3", "date", "events_total", "fatalities_total",
            "protest_events", "battle_events", "riot_events",
        ])

    df = df.copy()
    df["date"] = pd.to_datetime(df["event_date"]).dt.date

    agg = df.groupby(["iso3", "date"]).agg(
        events_total=("event_id_cnty", "count"),
        fatalities_total=("fatalities", "sum"),
        protest_events=("event_type", lambda s: (s == "Protests").sum()),
        battle_events=("event_type", lambda s: (s == "Battles").sum()),
        riot_events=("event_type", lambda s: (s == "Riots").sum()),
    ).reset_index()

    return agg


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ACLED conflict data")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--aggregate", action="store_true", help="Also write aggregated parquet")
    parser.add_argument("--out-dir", default="hist")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")

    df = fetch(days_back=args.days)
    raw_path = out_dir / f"acled-{today}.parquet"
    df.to_parquet(raw_path, index=False)
    print(f"Wrote {len(df)} raw rows to {raw_path}")

    if args.aggregate:
        agg = aggregate_by_country(df)
        agg_path = out_dir / f"acled-agg-{today}.parquet"
        agg.to_parquet(agg_path, index=False)
        print(f"Wrote {len(agg)} aggregated rows to {agg_path}")
