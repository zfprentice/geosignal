"""
Structural Fragility layer — static country risk score.

Computes a composite structural fragility score from slow-moving
institutional and macro indicators. Unlike the dynamic signal primitives,
this layer changes quarterly and represents baseline vulnerability
independent of recent events.

Components (spec §2.3, Fragility_i):
    - World Bank Worldwide Governance Indicators:
        voice, political stability, rule of law  (lower = more fragile → negated)
    - Debt-to-GDP ratio (World Bank WDI)         (higher = more fragile)
    - IMF inflation rate (WEO)                   (higher = more fragile)

Each component is z-scored against the global country universe.
Positive z = more fragile. Mean of available z-scores, clipped to [-3, 3].
Fragility is scaled to [0, 10] via percentile rank within the universe.

Updated quarterly; cached between updates.

Spec reference: §2.3 (Fragility component, w4=0.15).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


FRAGILITY_CACHE = Path("hist/fragility.parquet")
CLIP = 3.0


def _zscore(series: pd.Series) -> pd.Series:
    """Z-score a series; return 0-filled NaN-safe result."""
    mu = series.mean()
    sigma = series.std(ddof=1)
    if sigma < 1e-9:
        return pd.Series(0.0, index=series.index)
    return (series - mu) / sigma


def compute_fragility(
    wb_data: pd.DataFrame,
    imf_data: pd.DataFrame,
    fred_data: pd.DataFrame,
) -> pd.Series:
    """Compute composite Fragility score for all countries.

    Args:
        wb_data: World Bank indicators DataFrame — columns include iso3,
                 stability, voice, rule_of_law, debt_gdp.
        imf_data: IMF WEO DataFrame — columns include iso3, inflation_cpi.
        fred_data: Ignored (FRED EMBI+ is an aggregate index, not per-country).

    Returns:
        Series indexed by iso3 with Fragility score in [0, 10]
        (10 = most structurally fragile).
    """
    components: dict[str, pd.Series] = {}

    # --- WB governance: lower score = less stable = more fragile → negate ---
    wb = wb_data.copy()
    if not wb.empty and "iso3" in wb.columns:
        wb = wb.dropna(subset=["iso3"]).set_index("iso3")
        for col in ["stability", "voice", "rule_of_law"]:
            if col in wb.columns:
                s = wb[col].dropna()
                if len(s) >= 10:
                    # negate so that high z = poor governance = more fragile
                    components[col] = -_zscore(s)

        if "debt_gdp" in wb.columns:
            s = wb["debt_gdp"].dropna()
            if len(s) >= 10:
                components["debt_gdp"] = _zscore(s)

    # --- IMF inflation: higher = more fragile ---
    imf = imf_data.copy()
    if not imf.empty and "iso3" in imf.columns and "inflation_cpi" in imf.columns:
        imf = imf.dropna(subset=["iso3", "inflation_cpi"]).set_index("iso3")
        s = imf["inflation_cpi"].dropna()
        if len(s) >= 10:
            components["inflation_cpi"] = _zscore(s)

    if not components:
        return pd.Series(dtype=float)

    # Align on the union of iso3 codes
    combined = pd.DataFrame(components)
    # Mean of available components per country (ignore NaN)
    raw = combined.mean(axis=1)
    raw = raw.clip(-CLIP, CLIP)

    # Scale to [0, 10] by percentile rank
    return _percentile_rank_0_10(raw)


def _percentile_rank_0_10(series: pd.Series) -> pd.Series:
    """Rank series into [0, 10] — 10 = highest (most fragile)."""
    n = len(series)
    if n == 0:
        return series
    ranked = series.rank(method="average")
    return ((ranked - 1) / max(n - 1, 1) * 10).clip(0, 10)


def load_cached_fragility(cache_path: Path = FRAGILITY_CACHE) -> pd.Series:
    """Load the most recently computed Fragility scores from cache.

    Returns:
        Series indexed by iso3 with cached Fragility scores.
        Empty Series if cache does not exist.
    """
    if not Path(cache_path).exists():
        return pd.Series(dtype=float, name="fragility")
    df = pd.read_parquet(cache_path)
    return df["fragility"]


def save_fragility(scores: pd.Series, cache_path: Path = FRAGILITY_CACHE) -> None:
    """Persist Fragility scores to cache parquet.

    Args:
        scores: Output of compute_fragility().
        cache_path: File to write.
    """
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = scores.rename("fragility").reset_index()
    df.columns = ["iso3", "fragility"]
    df.to_parquet(path, index=False)
