"""
Structural Fragility layer — static country risk score.

Computes a composite structural fragility score from slow-moving
institutional and macro indicators. Unlike the dynamic signal primitives,
this layer changes quarterly and represents baseline vulnerability
independent of recent events.

Components (spec §2.3, Fragility_i):
    - World Bank Worldwide Governance Indicators:
        voice, political stability, rule of law
    - Debt-to-GDP ratio (World Bank WDI)
    - EMBI+ spread where available (FRED)
    - IMF inflation rate (WEO)

Each component is z-scored against the global country universe.
The composite is a simple mean of available z-scores, clipped to [-3, 3].

Fragility is scaled to [0, 10] via percentile rank within the universe.
Updated quarterly; cached between updates.

Spec reference: §2.3 (Fragility component, w4=0.15).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


FRAGILITY_INDICATORS = [
    "stability",       # WB: Political Stability and Absence of Violence
    "voice",           # WB: Voice and Accountability
    "rule_of_law",     # WB: Rule of Law
    "debt_gdp",        # WB WDI: Debt-to-GDP
    "embi_spread",     # FRED: EMBI+ (where available)
    "inflation_cpi",   # IMF WEO: CPI inflation
]


def compute_fragility(
    wb_data: pd.DataFrame,
    imf_data: pd.DataFrame,
    fred_data: pd.DataFrame,
) -> pd.Series:
    """Compute composite Fragility score for all countries.

    Args:
        wb_data: World Bank indicators DataFrame (from pipeline/sources/worldbank.py).
        imf_data: IMF WEO DataFrame (from pipeline/sources/imf.py).
        fred_data: FRED DataFrame (from pipeline/sources/fred.py) — EMBI+ only.

    Returns:
        Series indexed by iso3 with Fragility score in [0, 10]
        (10 = most structurally fragile).
    """
    raise NotImplementedError


def load_cached_fragility(cache_path: Path = Path("hist/fragility.parquet")) -> pd.Series:
    """Load the most recently computed Fragility scores from cache.

    Returns:
        Series indexed by iso3 with cached Fragility scores.
    """
    raise NotImplementedError


def save_fragility(scores: pd.Series, cache_path: Path = Path("hist/fragility.parquet")) -> None:
    """Persist Fragility scores to cache parquet.

    Args:
        scores: Output of compute_fragility().
        cache_path: File to write.
    """
    raise NotImplementedError
