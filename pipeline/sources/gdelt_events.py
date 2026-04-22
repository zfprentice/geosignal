"""
GDELT 2.0 Events — BigQuery client for CAMEO-coded event data.

Queries the public BigQuery dataset `gdelt-bq.gdeltv2.events` to pull
CAMEO-coded events with actor information, Goldstein tone scores, and
source/target country codes for a given date.

Spec reference: §2.1 (GDELT 2.0 Events via BigQuery, daily cadence).
                §2.2 Primitive 4 (dyadic aggregation inputs).

Authentication:
    Set GCP_SA_KEY_JSON env var to the full JSON text of a Google Cloud
    service account key that has BigQuery Data Viewer + Job User roles on
    the project.  The gdelt-bq.gdeltv2 dataset is public; any project's
    service account can query it at no data cost (within BQ free tier).

Output schema:
    GlobalEventID (int64), Day (int64, YYYYMMDD),
    Actor1CountryCode, Actor1Name,
    Actor2CountryCode, Actor2Name,
    EventCode, EventBaseCode, EventRootCode,
    GoldsteinScale (float), NumMentions (int), NumSources (int),
    NumArticles (int), AvgTone (float),
    ActionGeo_CountryCode, SOURCEURL

Standalone usage:
    python pipeline/sources/gdelt_events.py [--date 2026-04-21]
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

EVENTS_TABLE = "gdelt-bq.gdeltv2.events"

# Columns to select — avoids pulling the full 60-column schema
SELECT_COLS = """
    CAST(GlobalEventID AS INT64)          AS GlobalEventID,
    CAST(Day AS INT64)                    AS Day,
    Actor1CountryCode,
    Actor1Name,
    Actor2CountryCode,
    Actor2Name,
    EventCode,
    EventBaseCode,
    EventRootCode,
    CAST(GoldsteinScale AS FLOAT64)       AS GoldsteinScale,
    CAST(NumMentions AS INT64)            AS NumMentions,
    CAST(NumSources AS INT64)             AS NumSources,
    CAST(NumArticles AS INT64)            AS NumArticles,
    CAST(AvgTone AS FLOAT64)              AS AvgTone,
    ActionGeo_CountryCode,
    SOURCEURL
""".strip()

PARQUET_SCHEMA_COLS = [
    "GlobalEventID", "Day",
    "Actor1CountryCode", "Actor1Name",
    "Actor2CountryCode", "Actor2Name",
    "EventCode", "EventBaseCode", "EventRootCode",
    "GoldsteinScale", "NumMentions", "NumSources", "NumArticles", "AvgTone",
    "ActionGeo_CountryCode", "SOURCEURL",
]


def _get_bq_client():
    """Return an authenticated BigQuery client from GCP_SA_KEY_JSON env var.

    Raises:
        EnvironmentError: If GCP_SA_KEY_JSON is not set.
        Exception: If the JSON is malformed or credentials are invalid.
    """
    sa_json = os.environ.get("GCP_SA_KEY_JSON")
    if not sa_json:
        raise EnvironmentError(
            "GCP_SA_KEY_JSON env var is not set. "
            "Set it to the full JSON text of a GCP service account key."
        )
    from google.cloud import bigquery
    from google.oauth2 import service_account

    sa_info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(credentials=creds, project=sa_info["project_id"])


def fetch(date: datetime | None = None) -> pd.DataFrame:
    """Pull CAMEO events from BigQuery for a given date.

    Args:
        date: Date to fetch (UTC). Defaults to yesterday.

    Returns:
        DataFrame with PARQUET_SCHEMA_COLS schema.
        Rows where both Actor1CountryCode and Actor2CountryCode are NULL
        are excluded (no useful dyadic signal).
    """
    if date is None:
        date = datetime.utcnow() - timedelta(days=1)

    # GDELT stores Day as YYYYMMDD integer
    day_int = int(date.strftime("%Y%m%d"))

    query = f"""
        SELECT {SELECT_COLS}
        FROM `{EVENTS_TABLE}`
        WHERE Day = {day_int}
          AND (
            Actor1CountryCode IS NOT NULL
            OR Actor2CountryCode IS NOT NULL
          )
    """
    client = _get_bq_client()
    print(f"  Querying GDELT events for {date.strftime('%Y-%m-%d')} …")
    df = client.query(query).to_dataframe()
    print(f"  Got {len(df):,} events")
    return df[PARQUET_SCHEMA_COLS]


def fetch_date_range(start: datetime, end: datetime) -> pd.DataFrame:
    """Pull events over a date range — used for backtest historical pulls.

    Makes a single BigQuery query spanning the full range rather than
    one query per day, to minimise slot usage.

    Args:
        start: Start date (inclusive).
        end: End date (inclusive).

    Returns:
        Concatenated DataFrame across all dates in [start, end].
    """
    start_int = int(start.strftime("%Y%m%d"))
    end_int = int(end.strftime("%Y%m%d"))

    query = f"""
        SELECT {SELECT_COLS}
        FROM `{EVENTS_TABLE}`
        WHERE Day BETWEEN {start_int} AND {end_int}
          AND (
            Actor1CountryCode IS NOT NULL
            OR Actor2CountryCode IS NOT NULL
          )
    """
    client = _get_bq_client()
    n_days = (end - start).days + 1
    print(f"  Querying GDELT events for {n_days} days ({start.date()} → {end.date()}) …")
    df = client.query(query).to_dataframe()
    print(f"  Got {len(df):,} events")
    return df[PARQUET_SCHEMA_COLS]


def write_parquet(df: pd.DataFrame, date: datetime, out_dir: Path = Path("hist")) -> Path:
    """Write events DataFrame to a dated parquet file.

    Args:
        df: Events DataFrame from fetch() or fetch_date_range().
        date: The date the data represents (used for filename).
        out_dir: Directory for parquet output.

    Returns:
        Path to the written file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"gdelt-events-{date.strftime('%Y-%m-%d')}.parquet"
    df.to_parquet(out, index=False)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch GDELT events from BigQuery")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--out-dir", default="hist")
    args = parser.parse_args()

    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d")
        if args.date
        else datetime.utcnow() - timedelta(days=1)
    )
    df = fetch(date=target_date)
    path = write_parquet(df, target_date, Path(args.out_dir))
    print(f"Wrote {len(df):,} rows to {path}")
