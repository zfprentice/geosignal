"""
Signal Primitive 1 — Robust deviation score (MAD z-score).

Formula (spec §2.2, Primitive 1):
    median_i = median(X[i, t-365 : t-1])
    mad_i    = median(|X[i, t-365 : t-1] - median_i|)
    z_robust = (X[i, t] - median_i) / (1.4826 * mad_i + epsilon)

Why MAD over std: geopolitical data has heavy tails. Syria's baseline has
lots of violence — using std would let one extreme month dominate.
1.4826 makes MAD consistent with std under normality (Rousseeuw & Croux, 1993).

epsilon = 1.0 prevents division-by-zero for near-zero-baseline countries
(e.g., Luxembourg, Bhutan).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EPSILON = 1.0
BASELINE_WINDOW = 365  # days


def robust_zscore(series: pd.Series, current_value: float) -> float:
    """Compute MAD-based robust z-score for a single observation.

    Args:
        series: Historical baseline values (up to 365 days prior).
        current_value: Today's observed value.

    Returns:
        (current - median) / (1.4826 * MAD + epsilon).
        NaN if series is empty after dropping NaNs.
    """
    vals = np.asarray(series.dropna(), dtype=float)
    if len(vals) == 0:
        return float("nan")
    med = np.median(vals)
    mad = np.median(np.abs(vals - med))
    return float((current_value - med) / (1.4826 * mad + EPSILON))


def compute_deviation_scores(
    panel: pd.DataFrame,
    date: pd.Timestamp,
    features: list[str],
) -> pd.DataFrame:
    """Compute robust z-scores for all countries and features on a given date.

    Args:
        panel: Long-format DataFrame with columns [iso3, date, feature, value].
        date: The date to compute scores for (target day).
        features: Feature names to include (e.g. ['conflict_events', 'tone_mean']).

    Returns:
        DataFrame with columns [iso3, feature, z_robust].
    """
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    date = pd.Timestamp(date)
    cutoff = date - pd.Timedelta(days=BASELINE_WINDOW)

    baseline = panel[(panel["date"] >= cutoff) & (panel["date"] < date)]
    current = panel[panel["date"] == date]

    rows: list[dict] = []
    for iso3 in panel["iso3"].unique():
        for feature in features:
            b_vals = baseline[
                (baseline["iso3"] == iso3) & (baseline["feature"] == feature)
            ]["value"]
            c_vals = current[
                (current["iso3"] == iso3) & (current["feature"] == feature)
            ]["value"]
            if c_vals.empty:
                continue
            z = robust_zscore(b_vals, float(c_vals.iloc[0]))
            rows.append({"iso3": iso3, "feature": feature, "z_robust": z})

    return pd.DataFrame(rows, columns=["iso3", "feature", "z_robust"])


def aggregate_deviation(scores: pd.DataFrame) -> pd.Series:
    """Average per-feature z-scores to a single Deviation component, clipped to [-5, 5].

    Args:
        scores: Output of compute_deviation_scores().

    Returns:
        Series indexed by iso3.
    """
    if scores.empty:
        return pd.Series(dtype=float)
    return scores.groupby("iso3")["z_robust"].mean().clip(-5.0, 5.0)
