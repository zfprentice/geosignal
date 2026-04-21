"""
Signal Primitive 4 — CAMEO dyadic aggregation.

Builds a source × target × time tensor of Goldstein tone from GDELT
CAMEO-coded events. Each cell D[source, target, t] is the sum of
Goldstein tone scores for all events where actor1_country = source
and actor2_country = target on day t.

Formula (spec §2.2, Primitive 4):
    D[source, target, t] = Σ GoldsteinScale for events where
        Actor1CountryCode = source AND Actor2CountryCode = target
        AND Day = t

Aggregated weekly for the matrix view and primary counterparty field.

Outputs:
  - Dyadic DataFrame used by pipeline/signals/contagion.py
  - matrix.json via pipeline/publishing/build_matrix_json.py
  - primary_counterparty field in countries.json

The matrix view (§1.1, §4.5) shows a 20×20 subset of major countries.
"""

from __future__ import annotations

import pandas as pd


def build_dyadic_tensor(
    events: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Aggregate GDELT events into a source-target-date tone tensor.

    Args:
        events: GDELT events DataFrame (from pipeline/sources/gdelt_events.py).
        start_date: Start of aggregation window.
        end_date: End of aggregation window.

    Returns:
        DataFrame with columns [source_iso3, target_iso3, date, tone_sum, event_count].
    """
    raise NotImplementedError


def aggregate_weekly(dyadic: pd.DataFrame) -> pd.DataFrame:
    """Collapse daily dyadic tensor to weekly averages.

    Args:
        dyadic: Output of build_dyadic_tensor().

    Returns:
        DataFrame with columns [source_iso3, target_iso3, week, tone_mean, event_count].
    """
    raise NotImplementedError


def get_primary_counterparty(dyadic: pd.DataFrame, target_iso3: str, window_days: int = 7) -> dict:
    """Find the country directing the most anomalous event tone toward target_iso3.

    Used to populate the primary_counterparty field on signal cards.

    Args:
        dyadic: Output of build_dyadic_tensor().
        target_iso3: The country receiving events.
        window_days: Lookback window in days.

    Returns:
        Dict with keys: iso3, tone_7d (the counterparty with highest |tone_sum|).
    """
    raise NotImplementedError


def build_matrix_subset(
    dyadic_weekly: pd.DataFrame,
    country_list: list[str],
    window: str = "30d",
) -> pd.DataFrame:
    """Build the N×N matrix for the matrix view page.

    Args:
        dyadic_weekly: Output of aggregate_weekly().
        country_list: List of ISO3 codes to include (20-40 countries).
        window: Aggregation window ('7d', '30d', '90d').

    Returns:
        Pivot DataFrame [source × target] with mean tone values.
    """
    raise NotImplementedError
