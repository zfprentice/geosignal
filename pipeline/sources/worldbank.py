"""
World Bank WDI — governance and macro indicators fetcher.

Fetches annual snapshots of World Bank World Development Indicators used
in the structural Fragility layer of the Watchlist Index:
  - Worldwide Governance Indicators (voice, stability, rule of law)
  - GDP per capita
  - Debt-to-GDP ratio

Data is annual and changes slowly; re-fetched quarterly and cached.

Spec reference: §2.1 (World Bank WDI, annual snapshot).
                §2.3 Fragility component.

No API key required — World Bank API is public.

Standalone usage:
    python pipeline/sources/worldbank.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


# WDI indicator codes used in fragility scoring
INDICATORS = {
    "PV.EST": "stability",          # Political Stability and Absence of Violence
    "VA.EST": "voice",              # Voice and Accountability
    "RL.EST": "rule_of_law",        # Rule of Law
    "NY.GDP.PCAP.CD": "gdp_pc",    # GDP per capita (current USD)
    "GC.DOD.TOTL.GD.ZS": "debt_gdp",  # Central government debt (% of GDP)
}


def fetch(countries: list[str] | None = None, year: int | None = None) -> pd.DataFrame:
    """Fetch WDI indicators for all countries (or a subset).

    Args:
        countries: List of ISO3 codes. None fetches all countries.
        year: Year to fetch. Defaults to most recent available.

    Returns:
        DataFrame with columns: iso3, year, stability, voice,
        rule_of_law, gdp_pc, debt_gdp
    """
    raise NotImplementedError


def write_snapshot(df: pd.DataFrame, out_dir: Path = Path("hist")) -> Path:
    """Write WDI snapshot to parquet.

    Returns:
        Path to written file.
    """
    raise NotImplementedError


if __name__ == "__main__":
    df = fetch()
    path = write_snapshot(df)
    print(f"Wrote {len(df)} rows to {path}")
