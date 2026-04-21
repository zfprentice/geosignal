"""
GDELT 2.0 Events — BigQuery client for CAMEO-coded event data.

Queries the public BigQuery dataset `gdelt-bq.gdeltv2.events` to pull
CAMEO-coded events with actor information, Goldstein tone scores, and
source/target country codes for the previous day's data.

Spec reference: §2.1 (GDELT 2.0 Events via BigQuery, daily cadence).
                §2.2 Primitive 4 (dyadic aggregation inputs).

Expected schema of returned DataFrame:
    GlobalEventID, Day, MonthYear, Year, FractionDate,
    Actor1Code, Actor1Name, Actor1CountryCode,
    Actor2Code, Actor2Name, Actor2CountryCode,
    EventCode, EventBaseCode, EventRootCode,
    GoldsteinScale, NumMentions, NumSources, NumArticles, AvgTone,
    ActionGeo_CountryCode, SOURCEURL

Requires:
    GCP_SA_KEY_JSON env var — service account JSON for BigQuery auth.

Standalone usage:
    python pipeline/sources/gdelt_events.py [--date 2026-04-21]
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def fetch(date: datetime | None = None) -> pd.DataFrame:
    """Pull CAMEO events from BigQuery for a given date.

    Args:
        date: Date to fetch (UTC). Defaults to yesterday.

    Returns:
        DataFrame with GDELT Events schema (see module docstring).
    """
    raise NotImplementedError


def fetch_date_range(start: datetime, end: datetime) -> pd.DataFrame:
    """Pull events over a date range — used for backtest historical pulls.

    Args:
        start: Start date (inclusive).
        end: End date (inclusive).

    Returns:
        Concatenated DataFrame across all dates.
    """
    raise NotImplementedError


def write_parquet(df: pd.DataFrame, date: datetime, out_dir: Path = Path("hist")) -> Path:
    """Write events DataFrame to a dated parquet file.

    Args:
        df: Events DataFrame.
        date: The date the data represents.
        out_dir: Directory for parquet output.

    Returns:
        Path to written file.
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch GDELT events from BigQuery")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: yesterday)")
    args = parser.parse_args()

    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d")
        if args.date
        else datetime.utcnow() - timedelta(days=1)
    )
    df = fetch(date=target_date)
    path = write_parquet(df, target_date)
    print(f"Wrote {len(df)} rows to {path}")
