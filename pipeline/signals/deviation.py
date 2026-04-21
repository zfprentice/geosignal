"""
Signal Primitive 1 — Robust deviation score (MAD z-score).

For each (country, feature) pair at time t, computes how far today's
value is from the country's own 365-day trailing baseline using
median absolute deviation rather than standard deviation.

Formula (spec §2.2, Primitive 1):
    median_i = median(X[i, t-365 : t-1])
    mad_i    = median(|X[i, t-365 : t-1] - median_i|)
    z_robust = (X[i, t] - median_i) / (1.4826 * mad_i + epsilon)

Why MAD over std: geopolitical data has heavy tails. Syria's baseline
has lots of violence — using std would let one extreme month dominate.
MAD is resistant to outliers; 1.4826 makes it consistent with std
under normality (Rousseeuw & Croux, 1993).

epsilon = 1.0 prevents division-by-zero for near-zero-baseline countries
(e.g., Luxembourg, Bhutan).

The Deviation component of the Watchlist Index is the mean of robust
z-scores across conflict and protest features, clipped to [-5, 5].
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EPSILON = 1.0
BASELINE_WINDOW = 365


def robust_zscore(series: pd.Series, current_value: float) -> float:
    """Compute MAD-based robust z-score for a single observation.

    Args:
        series: Historical baseline values (up to 365 days).
        current_value: Today's observed value.

    Returns:
        Robust z-score: (current - median) / (1.4826 * MAD + epsilon)
    """
    raise NotImplementedError


def compute_deviation_scores(
    panel: pd.DataFrame,
    date: pd.Timestamp,
    features: list[str],
) -> pd.DataFrame:
    """Compute robust z-scores for all countries and features on a given date.

    Args:
        panel: Long-format DataFrame with columns [iso3, date, feature, value].
        date: The date to compute scores for.
        features: Feature names to include (e.g., ['conflict_events', 'tone_mean']).

    Returns:
        DataFrame with columns [iso3, feature, z_robust] for the given date.
    """
    raise NotImplementedError


def aggregate_deviation(scores: pd.DataFrame) -> pd.Series:
    """Aggregate per-feature z-scores into a single Deviation component.

    Averages z_robust across conflict and protest features, clips to [-5, 5].

    Args:
        scores: Output of compute_deviation_scores().

    Returns:
        Series indexed by iso3 with the aggregate Deviation score.
    """
    raise NotImplementedError
