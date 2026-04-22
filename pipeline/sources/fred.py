"""
FRED — Federal Reserve Economic Data fetcher.

Pulls daily market stress indicators that serve as global context inputs
to the contagion and fragility scoring components.

Spec reference: §2.1 (FRED, daily cadence, free API key).
                §2.3 Fragility component (EMBI+ spreads).

Authentication:
    FRED_API_KEY — free API key from https://fred.stlouisfed.org/docs/api/

Series fetched:
    VIXCLS       → vix            (CBOE Volatility Index, daily)
    DCOILWTICO   → oil_price_wti  (WTI crude oil price, USD/barrel, daily)
    PFOODINDEXM  → food_price_idx (IMF food price index, monthly — forward-filled to daily)

Note on EMBI+: The JPMorgan EMBI+ is not freely available via FRED.
The closest free proxy is the ICE BofA EM Bond spread (BAMLEMCBPIOAS)
available on FRED.  This is included as embi_proxy.

Output schema:
    date (date), vix (float), oil_price_wti (float),
    food_price_idx (float), embi_proxy (float)

Standalone usage:
    python pipeline/sources/fred.py [--days 30]
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

import pandas as pd

SERIES: dict[str, str] = {
    "VIXCLS": "vix",
    "DCOILWTICO": "oil_price_wti",
    "PFOODINDEXM": "food_price_idx",
    "BAMLEMCBPIOAS": "embi_proxy",       # EM sovereign spread proxy
}

OUTPUT_COLUMNS = ["date", "vix", "oil_price_wti", "food_price_idx", "embi_proxy"]


def _get_fred_client():
    """Return an authenticated fredapi.Fred client.

    Raises:
        EnvironmentError: If FRED_API_KEY is not set.
    """
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "FRED_API_KEY env var is not set. "
            "Get a free key at https://fred.stlouisfed.org/docs/api/"
        )
    from fredapi import Fred
    return Fred(api_key=api_key)


def fetch(days_back: int = 30) -> pd.DataFrame:
    """Fetch FRED market stress indicators for the past N days.

    Monthly series (PFOODINDEXM) are forward-filled to daily frequency
    so the output always has one row per day.

    Args:
        days_back: Number of calendar days to look back from today.

    Returns:
        DataFrame with OUTPUT_COLUMNS.  NaN where data is unavailable
        (e.g., weekends for VIX).

    Raises:
        EnvironmentError: If FRED_API_KEY is not set.
    """
    fred = _get_fred_client()
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days_back)

    # Build a daily date index as the spine
    date_range = pd.date_range(start=start_date, end=end_date, freq="D")
    result = pd.DataFrame({"date": date_range.date})

    for series_id, col_name in SERIES.items():
        print(f"  Fetching FRED series {series_id} ({col_name}) …")
        try:
            raw: pd.Series = fred.get_series(
                series_id,
                observation_start=start_date.strftime("%Y-%m-%d"),
                observation_end=end_date.strftime("%Y-%m-%d"),
            )
        except Exception as exc:
            print(f"  Warning: could not fetch {series_id}: {exc}")
            result[col_name] = float("nan")
            continue

        raw.index = pd.to_datetime(raw.index).date
        raw = raw.reindex(result["date"])

        # Forward-fill monthly series to daily; leave daily gaps as NaN
        if series_id in ("PFOODINDEXM",):
            raw = raw.ffill()

        result[col_name] = raw.values

    for col in OUTPUT_COLUMNS:
        if col not in result.columns:
            result[col] = float("nan")

    return result[OUTPUT_COLUMNS].copy()


def fetch_latest() -> pd.Series:
    """Fetch the most recent value for each FRED series.

    Returns:
        Series indexed by column name (vix, oil_price_wti, etc.) with
        the latest available value.
    """
    return fetch(days_back=5).iloc[-1]


def write_parquet(df: pd.DataFrame, out_dir: Path = Path("hist")) -> Path:
    """Write FRED data to a dated parquet.

    Args:
        df: Output of fetch().
        out_dir: Directory for output.

    Returns:
        Path to written file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out = out_dir / f"fred-{today}.parquet"
    df.to_parquet(out, index=False)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch FRED macro indicators")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--out-dir", default="hist")
    args = parser.parse_args()

    df = fetch(days_back=args.days)
    path = write_parquet(df, Path(args.out_dir))
    print(f"Wrote {len(df)} rows to {path}")
    print(df.tail(7).to_string())
