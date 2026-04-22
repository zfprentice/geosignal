"""
Signal Primitive 3 — Lightweight CUSUM change-point detection.

Formula (spec §2.2, Primitive 3):
    S[t] = max(0, S[t-1] + (x[t] - mu - k))   # upper CUSUM
    Flag when S[t] > h; reset S = 0 on detection.

    mu = mean of the series (estimated from the same window)
    k  = allowance = CUSUM_ALLOWANCE_SIGMA * σ  (default 0.5σ)
    h  = threshold  = CUSUM_THRESHOLD_SIGMA * σ  (default 5σ)

Why σ-based defaults rather than absolute: geopolitical series have very
different scales (events_total for Syria vs Luxembourg differ by orders
of magnitude). Scaling by the series' own σ makes the detector scale-free.

Why 5σ for h (not exactly 4σ from spec's "~4σ"): the spec uses "~" and
the in-sample mean correction causes k and h to be measured relative to
the same series, so 5σ gives an average run length well above 200 days
for in-control normal data (false alarm < 1 per year), matching
geopolitical update cadence.

Changepoint dates are stored in countries.json and displayed as vertical
markers on country detail charts (spec §1.2, §4.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

CUSUM_THRESHOLD_SIGMA = 6.0   # h = this * σ  (~4σ in spec, 6σ chosen for ARL > 200 with in-sample mean)
CUSUM_ALLOWANCE_SIGMA = 0.5   # k = this * σ


@dataclass
class ChangepointResult:
    iso3: str
    changepoint_dates: list[date] = field(default_factory=list)
    cusum_series: pd.Series = field(default_factory=pd.Series)


def run_cusum(
    series: pd.Series,
    k: float | None = None,
    h: float | None = None,
) -> list[int]:
    """Run upper CUSUM on a time series; return indices where threshold is crossed.

    On each crossing, the accumulator resets to zero (allows multiple detections).

    Args:
        series: Numeric time series, oldest value first.  NaNs are dropped.
        k: Allowance parameter.  Defaults to CUSUM_ALLOWANCE_SIGMA * σ.
        h: Detection threshold.  Defaults to CUSUM_THRESHOLD_SIGMA * σ.

    Returns:
        List of integer indices (in the original series) where S[t] exceeded h.
        Empty list if the series is constant or has fewer than 2 non-NaN values.
    """
    vals = np.asarray(series.dropna(), dtype=float)
    if len(vals) < 2:
        return []

    mu = float(np.mean(vals))
    sigma = float(np.std(vals, ddof=1))

    if sigma < 1e-9:
        return []  # constant series — no structural change possible

    if k is None:
        k = CUSUM_ALLOWANCE_SIGMA * sigma
    if h is None:
        h = CUSUM_THRESHOLD_SIGMA * sigma

    changepoints: list[int] = []
    S = 0.0
    for i, x in enumerate(vals):
        S = max(0.0, S + (x - mu - k))
        if S > h:
            changepoints.append(i)
            S = 0.0

    return changepoints


def detect_changepoints(
    panel: pd.DataFrame,
    iso3: str,
    value_col: str = "watchlist",
    window: int = 180,
) -> ChangepointResult:
    """Detect regime changes for a single country over the past N days.

    Args:
        panel: DataFrame with columns [iso3, date, <value_col>].
        iso3: Country ISO3 code.
        value_col: Column to run CUSUM on.
        window: Number of most-recent days to use.

    Returns:
        ChangepointResult with detected dates and the full CUSUM accumulator series.
    """
    country_data = (
        panel[panel["iso3"] == iso3]
        .sort_values("date")
        .tail(window)
        .reset_index(drop=True)
    )

    if country_data.empty or value_col not in country_data.columns:
        return ChangepointResult(iso3=iso3)

    series = country_data[value_col]
    idx = run_cusum(series)

    changepoint_dates: list[date] = []
    if "date" in country_data.columns and idx:
        date_col = pd.to_datetime(country_data["date"])
        for i in idx:
            if i < len(date_col):
                changepoint_dates.append(date_col.iloc[i].date())

    # recompute CUSUM accumulator for storage/display
    vals = np.asarray(series.dropna(), dtype=float)
    mu = float(np.mean(vals)) if len(vals) >= 2 else 0.0
    sigma = float(np.std(vals, ddof=1)) if len(vals) >= 2 else 1.0
    sigma = max(sigma, 1e-9)
    k = CUSUM_ALLOWANCE_SIGMA * sigma
    cusum_vals = []
    S = 0.0
    for x in vals:
        S = max(0.0, S + (x - mu - k))
        cusum_vals.append(S)

    cusum_series = pd.Series(cusum_vals, index=country_data["date"] if "date" in country_data.columns else None)

    return ChangepointResult(
        iso3=iso3,
        changepoint_dates=changepoint_dates,
        cusum_series=cusum_series,
    )


def detect_all_countries(panel: pd.DataFrame) -> dict[str, list[date]]:
    """Run change-point detection for all countries in the panel.

    Args:
        panel: Full country × day panel with columns [iso3, date, watchlist].

    Returns:
        Dict mapping iso3 → list of changepoint dates (may be empty).
    """
    results: dict[str, list[date]] = {}
    for iso3 in panel["iso3"].unique():
        cp = detect_changepoints(panel, iso3)
        results[iso3] = cp.changepoint_dates
    return results
