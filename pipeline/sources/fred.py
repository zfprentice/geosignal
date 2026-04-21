"""
FRED — Federal Reserve Economic Data fetcher.

Pulls daily market stress indicators used as global context inputs:
  - VIX (CBOE Volatility Index) — global risk appetite
  - EMBI+ spreads (Emerging Market Bond Index) — EM sovereign risk
  - Commodity price indices (oil, food) — macro stress vectors

These are global series, not country-level. They feed into the
contagion and fragility components as external shock proxies.

Spec reference: §2.1 (FRED, daily cadence, free API key).
                §2.3 Fragility component (EMBI+ spreads).

Required env var:
    FRED_API_KEY

Standalone usage:
    python pipeline/sources/fred.py [--days 7]
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


SERIES = {
    "VIXCLS": "vix",
    "DCOILWTICO": "oil_price_wti",
    "PFOODINDEXM": "food_price_index",
}


def fetch(days_back: int = 7) -> pd.DataFrame:
    """Fetch FRED series for the past N days.

    Args:
        days_back: Number of days to look back.

    Returns:
        DataFrame with columns: date, vix, oil_price_wti, food_price_index
    """
    raise NotImplementedError


def write_parquet(df: pd.DataFrame, out_dir: Path = Path("hist")) -> Path:
    """Write FRED data to dated parquet.

    Returns:
        Path to written file.
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch FRED macro indicators")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    df = fetch(days_back=args.days)
    path = write_parquet(df)
    print(f"Wrote {len(df)} rows to {path}")
