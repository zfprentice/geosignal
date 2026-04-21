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

Output is scaled 0–10 by percentile rank against the universe
(10 = most at-risk country this week, not an absolute threshold).

Signal feed ranking formula (spec §1.2):
    Score_rank = 0.5 * |z_deviation| + 0.3 * trend_slope + 0.2 * contagion
    (all components z-scored against 180-country universe)

Spec reference: §2.3 (Watchlist Index), §1.2 (signal ranking).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_weights(config_path: Path = CONFIG_PATH) -> dict[str, float]:
    """Load index weights from config.yaml.

    Returns:
        Dict with keys: w1, w2, w3, w4.
    """
    raise NotImplementedError


def compute_watchlist(
    deviation: pd.Series,
    trend: pd.Series,
    contagion: pd.Series,
    fragility: pd.Series,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Compute Watchlist Index for all countries.

    Args:
        deviation: Deviation scores indexed by iso3.
        trend: Trend scores indexed by iso3.
        contagion: Contagion scores indexed by iso3.
        fragility: Fragility scores indexed by iso3.
        weights: Dict with w1-w4. None loads from config.yaml.

    Returns:
        DataFrame indexed by iso3 with columns:
            watchlist, watchlist_percentile,
            component_deviation, component_trend,
            component_contagion, component_fragility
    """
    raise NotImplementedError


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
        watchlist_df: Output of compute_watchlist().
        deviation: Raw deviation scores.
        trend: Raw trend slopes.
        contagion: Raw contagion scores.

    Returns:
        Series indexed by iso3 with Score_rank values (higher = more anomalous).
    """
    raise NotImplementedError


def scale_to_percentile(raw_scores: pd.Series) -> pd.Series:
    """Convert raw composite scores to 0-10 percentile rank.

    Args:
        raw_scores: Series of raw scores indexed by iso3.

    Returns:
        Series of scores in [0, 10] based on rank within universe.
    """
    raise NotImplementedError


if __name__ == "__main__":
    print("Run via daily.yml workflow, not directly.")
    print("Import compute_watchlist() for standalone use.")
