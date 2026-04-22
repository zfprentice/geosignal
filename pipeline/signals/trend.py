"""
Signal Primitive 2 — Theil-Sen trend slope (30-day window).

Formula (spec §2.2, Primitive 2):
    slope = theil_sen(X[i, t-30 : t])

The Theil-Sen estimator (median of all pairwise slopes) is the robust
cousin of OLS. One absurdly high GDELT day from a breaking story won't
dominate the estimate.

scipy.stats.theilslopes is the reference implementation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import theilslopes

TREND_WINDOW = 30  # days


def theil_sen_slope(series: pd.Series) -> float:
    """Compute Theil-Sen slope for a time series.

    Args:
        series: Ordered time series values (oldest first).
                At least 2 non-NaN observations required.

    Returns:
        Median of all pairwise slopes (value per index unit).
        NaN if fewer than 2 non-NaN observations.
    """
    vals = np.asarray(series.dropna(), dtype=float)
    if len(vals) < 2:
        return float("nan")
    result = theilslopes(vals)
    return float(result.slope)


def compute_trend_scores(
    panel: pd.DataFrame,
    date: pd.Timestamp,
    feature: str = "conflict_events",
) -> pd.Series:
    """Compute 30-day Theil-Sen slopes for all countries on a given date.

    Args:
        panel: Long-format DataFrame with columns [iso3, date, feature, value],
               OR wide-format with [iso3, date, <feature columns>].
        date: The date to compute trends for (end of the 30-day window).
        feature: Feature to trend. Used as column name in wide format or
                 as filter value for the 'feature' column in long format.

    Returns:
        Series indexed by iso3 with Theil-Sen slope values.
    """
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    date = pd.Timestamp(date)
    cutoff = date - pd.Timedelta(days=TREND_WINDOW)
    window = panel[(panel["date"] > cutoff) & (panel["date"] <= date)]

    results: dict[str, float] = {}

    if "feature" in panel.columns:
        # long format
        feat_window = window[window["feature"] == feature]
        for iso3, group in feat_window.groupby("iso3"):
            s = group.sort_values("date")["value"].reset_index(drop=True)
            results[iso3] = theil_sen_slope(s)
    else:
        # wide format
        for iso3, group in window.groupby("iso3"):
            s = group.sort_values("date")[feature].reset_index(drop=True)
            results[iso3] = theil_sen_slope(s)

    return pd.Series(results)


def normalise_trend(slopes: pd.Series) -> pd.Series:
    """Min-max normalise Theil-Sen slopes to [0, 1] across the country universe.

    Args:
        slopes: Raw Theil-Sen slopes indexed by iso3.

    Returns:
        Series of normalised scores in [0, 1].
        Returns 0.5 for all countries when all slopes are equal.
    """
    lo, hi = slopes.min(), slopes.max()
    if hi == lo:
        return pd.Series(0.5, index=slopes.index)
    return (slopes - lo) / (hi - lo)
