"""
Signal Primitive 3 — Lightweight CUSUM change-point detection.

Runs a CUSUM (cumulative sum) algorithm on each country's 180-day
Watchlist history. When the cumulative deviation exceeds ~4σ, a
regime change is flagged and the accumulator resets.

Formula (spec §2.2, Primitive 3):
    S[t] = max(0, S[t-1] + (x[t] - mu - k))   # upper CUSUM
    Flag when S[t] > h

where:
    mu = estimated mean (from 365d baseline)
    k  = allowance parameter (typically 0.5σ)
    h  = threshold (typically 4σ)

Why CUSUM: it gives the model persistent memory. Syria in 2024 is not
"newly anomalous" — its CUSUM would have long since reset and
stabilised. Niger in late July 2023 showed a fresh CUSUM breach.

Changepoint dates are stored in countries.json and displayed as
vertical markers on country detail charts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


CUSUM_THRESHOLD_SIGMA = 4.0
CUSUM_ALLOWANCE_SIGMA = 0.5


@dataclass
class ChangepointResult:
    iso3: str
    changepoint_dates: list[date]
    cusum_series: pd.Series


def run_cusum(series: pd.Series, k: float | None = None, h: float | None = None) -> list[int]:
    """Run CUSUM on a time series and return indices where threshold is crossed.

    Args:
        series: Time-indexed numeric series (e.g., daily Watchlist values).
        k: Allowance parameter. Defaults to 0.5 * series.std().
        h: Threshold. Defaults to 4.0 * series.std().

    Returns:
        List of integer indices where change was detected (accumulator reset here).
    """
    raise NotImplementedError


def detect_changepoints(
    panel: pd.DataFrame,
    iso3: str,
    value_col: str = "watchlist",
    window: int = 180,
) -> ChangepointResult:
    """Detect regime changes for a single country over the past N days.

    Args:
        panel: DataFrame with columns [iso3, date, value_col].
        iso3: Country ISO3 code.
        value_col: Column to run CUSUM on.
        window: Number of days of history to use.

    Returns:
        ChangepointResult with changepoint dates and full CUSUM series.
    """
    raise NotImplementedError


def detect_all_countries(panel: pd.DataFrame) -> dict[str, list[date]]:
    """Run change-point detection for all countries.

    Args:
        panel: Full country × day panel.

    Returns:
        Dict mapping iso3 → list of changepoint dates.
    """
    raise NotImplementedError
