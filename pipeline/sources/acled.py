"""
ACLED — Armed Conflict Location & Event Data fetcher.

Pulls conflict events, actor types, and fatality counts from the ACLED
REST API for the past week. ACLED data is used to supplement GDELT's
protest and conflict event counts with fatality information.

Spec reference: §2.1 (ACLED, weekly cadence, free academic access).

Required env vars:
    ACLED_API_KEY
    ACLED_EMAIL

Expected output columns:
    event_id_cnty, event_date, year, time_precision,
    event_type, sub_event_type,
    actor1, assoc_actor_1, inter1,
    actor2, assoc_actor_2, inter2,
    country, iso, iso3,
    region, admin1, admin2, admin3,
    location, latitude, longitude,
    geo_precision, source, source_scale,
    notes, fatalities, timestamp

Standalone usage:
    python pipeline/sources/acled.py [--days 7]
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def fetch(days_back: int = 7) -> pd.DataFrame:
    """Fetch ACLED events for the past N days.

    Args:
        days_back: Number of days to look back from today.

    Returns:
        DataFrame with ACLED event schema (see module docstring).
    """
    raise NotImplementedError


def aggregate_by_country(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw ACLED events to country-day summary statistics.

    Args:
        df: Raw ACLED events DataFrame from fetch().

    Returns:
        DataFrame indexed by (iso3, date) with columns:
            events_total, fatalities_total, protest_events,
            battle_events, riot_events
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ACLED conflict data")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    df = fetch(days_back=args.days)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out = Path(f"hist/acled-{today}.parquet")
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df)} rows to {out}")
