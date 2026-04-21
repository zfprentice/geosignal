"""
IMF WEO — World Economic Outlook macro indicators fetcher.

Fetches semi-annual IMF World Economic Outlook data:
  - Inflation (CPI, percent change)
  - General government fiscal balance (% of GDP)
  - Current account balance (% of GDP)

Used in the structural Fragility layer of the Watchlist Index.
Data is semi-annual; re-fetched when new WEO edition releases (Apr/Oct).

Spec reference: §2.1 (IMF WEO, semi-annual, free).
                §2.3 Fragility component.

No API key required — IMF data portal is public.

Standalone usage:
    python pipeline/sources/imf.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def fetch(year: int | None = None) -> pd.DataFrame:
    """Fetch IMF WEO indicators for all countries.

    Args:
        year: WEO year to fetch. Defaults to most recent.

    Returns:
        DataFrame with columns: iso3, year, edition,
        inflation_cpi, fiscal_balance_gdp, current_account_gdp
    """
    raise NotImplementedError


def write_snapshot(df: pd.DataFrame, out_dir: Path = Path("hist")) -> Path:
    """Write IMF snapshot to parquet.

    Returns:
        Path to written file.
    """
    raise NotImplementedError


if __name__ == "__main__":
    df = fetch()
    path = write_snapshot(df)
    print(f"Wrote {len(df)} rows to {path}")
