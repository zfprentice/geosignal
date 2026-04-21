"""
Signal Primitive 2 — Theil-Sen trend slope (30-day window).

For each (country, feature), estimates the linear trend over the past
30 days using the Theil-Sen estimator: the median of all pairwise slopes.

Formula (spec §2.2, Primitive 2):
    slope = theil_sen(X[i, t-30 : t])

Why Theil-Sen over OLS: a single GDELT day spiked by breaking news
(e.g., a major attack) would dominate an OLS regression. The median
of pairwise slopes is robust to such outliers.

The Trend component of the Watchlist Index is the Theil-Sen slope on
conflict events, normalised across the country universe.

scipy.stats.theilslopes is the reference implementation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


TREND_WINDOW = 30


def theil_sen_slope(series: pd.Series) -> float:
    """Compute Theil-Sen slope for a time series.

    Args:
        series: Ordered time series values (most recent last).
                Must have at least 2 non-NaN observations.

    Returns:
        Median of all pairwise slopes (units: value per day).
        Returns NaN if fewer than 2 observations.
    """
    raise NotImplementedError


def compute_trend_scores(
    panel: pd.DataFrame,
    date: pd.Timestamp,
    feature: str = "conflict_events",
) -> pd.Series:
    """Compute 30-day Theil-Sen slopes for all countries on a given date.

    Args:
        panel: Long-format DataFrame with columns [iso3, date, feature, value].
        date: The date to compute trends for.
        feature: Feature column to compute trend on.

    Returns:
        Series indexed by iso3 with Theil-Sen slope values.
    """
    raise NotImplementedError


def normalise_trend(slopes: pd.Series) -> pd.Series:
    """Normalise Theil-Sen slopes to a 0-1 scale across the country universe.

    Args:
        slopes: Series of raw Theil-Sen slopes indexed by iso3.

    Returns:
        Series of normalised trend scores in [0, 1].
    """
    raise NotImplementedError
