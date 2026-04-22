"""
Watchlist Index — composite scoring and ranking.

Assembles the four signal components into the final Watchlist Index
that colours the globe and ranks the signals feed.

Formula (spec §2.3):
    Watchlist_i = w1 * Deviation_i + w2 * Trend_i
                + w3 * Contagion_i + w4 * Fragility_i

Default weights (from pipeline/scoring/config.yaml):
    w1 = 0.40  # Deviation  (what's anomalous now)
    w2 = 0.25  # Trend      (direction)
    w3 = 0.20  # Contagion  (neighbourhood)
    w4 = 0.15  # Fragility  (structural)

Components are z-scored against the universe before combining so that
each has mean 0 and unit variance — making the weighted sum sensible
regardless of each component's natural scale.

Output is scaled 0–10 by percentile rank against the universe
(10 = most at-risk country this week, not an absolute threshold).

Signal feed ranking formula (spec §1.2):
    Score_rank = 0.5 * |z_deviation| + 0.3 * trend_slope + 0.2 * contagion
    (all components z-scored against 180-country universe; ties broken by WoW delta)

Spec reference: §2.3 (Watchlist Index), §1.2 (signal ranking).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml


CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_weights(config_path: Path = CONFIG_PATH) -> dict[str, float]:
    """Load index weights from config.yaml.

    Returns:
        Dict with keys: w1, w2, w3, w4.
    """
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    w = cfg["weights"]
    return {
        "w1": float(w["w1"]),
        "w2": float(w["w2"]),
        "w3": float(w["w3"]),
        "w4": float(w["w4"]),
    }


def _zscore_series(s: pd.Series) -> pd.Series:
    """Z-score a series; NaN-safe, returns 0 if constant."""
    mu = s.mean()
    sigma = s.std(ddof=1)
    if pd.isna(sigma) or sigma < 1e-9:
        return pd.Series(0.0, index=s.index)
    return (s - mu) / sigma


def scale_to_percentile(raw_scores: pd.Series) -> pd.Series:
    """Convert raw composite scores to 0-10 percentile rank.

    Rank 1 = lowest raw score → 0.0; rank N = highest → 10.0.

    Args:
        raw_scores: Series of raw scores indexed by iso3.

    Returns:
        Series of scores in [0, 10] based on rank within universe.
    """
    n = len(raw_scores)
    if n == 0:
        return raw_scores
    ranked = raw_scores.rank(method="average")
    return ((ranked - 1) / max(n - 1, 1) * 10).clip(0.0, 10.0)


def compute_watchlist(
    deviation: pd.Series,
    trend: pd.Series,
    contagion: pd.Series,
    fragility: pd.Series,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Compute Watchlist Index for all countries.

    Each component is z-scored against the universe before weighting,
    so the weighted sum is on a comparable scale regardless of each
    component's natural units.

    Args:
        deviation: Deviation scores indexed by iso3 (clipped ±5).
        trend: Trend scores indexed by iso3 (normalised [0,1]).
        contagion: Contagion scores indexed by iso3 ([0, ∞) neighbourhood score).
        fragility: Fragility scores indexed by iso3 ([0,10] structural layer).
        weights: Dict with w1-w4. None loads from config.yaml.

    Returns:
        DataFrame indexed by iso3 with columns:
            watchlist (0-10), watchlist_percentile (0-100),
            component_deviation, component_trend,
            component_contagion, component_fragility
    """
    if weights is None:
        weights = load_weights()

    # Align all series to the union of iso3 codes
    idx = (deviation.index
           .union(trend.index)
           .union(contagion.index)
           .union(fragility.index))

    dev = deviation.reindex(idx).fillna(0.0)
    tre = trend.reindex(idx).fillna(0.0)
    con = contagion.reindex(idx).fillna(0.0)
    fra = fragility.reindex(idx).fillna(0.0)

    # Z-score each component against the universe
    z_dev = _zscore_series(dev)
    z_tre = _zscore_series(tre)
    z_con = _zscore_series(con)
    z_fra = _zscore_series(fra)

    raw = (
        weights["w1"] * z_dev
        + weights["w2"] * z_tre
        + weights["w3"] * z_con
        + weights["w4"] * z_fra
    )

    watchlist = scale_to_percentile(raw)

    # Percentile rank as integer 0-100
    n = len(raw)
    percentile = (raw.rank(method="average") / n * 100).clip(0, 100).round(0).astype(int)

    return pd.DataFrame({
        "watchlist": watchlist.round(2),
        "watchlist_percentile": percentile,
        "component_deviation": dev.round(4),
        "component_trend": tre.round(4),
        "component_contagion": con.round(4),
        "component_fragility": fra.round(4),
    })


def compute_signal_rank(
    watchlist_df: pd.DataFrame,
    deviation: pd.Series,
    trend: pd.Series,
    contagion: pd.Series,
) -> pd.Series:
    """Compute the signal feed ranking score.

    Score_rank = 0.5 * |z_deviation| + 0.3 * trend_slope + 0.2 * contagion
    All components z-scored against the universe before combining.

    Args:
        watchlist_df: Output of compute_watchlist() (used for iso3 index).
        deviation: Raw deviation scores.
        trend: Raw trend slopes.
        contagion: Raw contagion scores.

    Returns:
        Series indexed by iso3 with Score_rank values (higher = more anomalous).
    """
    idx = watchlist_df.index

    dev = deviation.reindex(idx).fillna(0.0)
    tre = trend.reindex(idx).fillna(0.0)
    con = contagion.reindex(idx).fillna(0.0)

    z_dev = _zscore_series(dev)
    z_tre = _zscore_series(tre)
    z_con = _zscore_series(con)

    return (0.5 * z_dev.abs() + 0.3 * z_tre + 0.2 * z_con).round(4)


if __name__ == "__main__":
    print("Run via daily.yml workflow, not directly.")
    print("Import compute_watchlist() for standalone use.")
