"""
Signal Primitive 4 — CAMEO dyadic aggregation.

Formula (spec §2.2, Primitive 4):
    D[source, target, t] = Σ GoldsteinScale  for events where
        Actor1CountryCode = source  AND  Actor2CountryCode = target
        AND  Day = t

GDELT actor country codes are FIPS 2-letter codes, converted to ISO3 via
the mapping in pipeline/sources/gdelt_doc.py.

Outputs:
  - Dyadic DataFrame consumed by pipeline/signals/contagion.py
  - matrix.json via pipeline/publishing/build_matrix_json.py
  - primary_counterparty field in countries.json
"""

from __future__ import annotations

import pandas as pd


def build_dyadic_tensor(
    events: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Aggregate GDELT events into a source × target × date tone tensor.

    Args:
        events: GDELT events DataFrame from pipeline/sources/gdelt_events.py.
                Must have columns: Day (int YYYYMMDD), Actor1CountryCode,
                Actor2CountryCode, GoldsteinScale, GlobalEventID.
        start_date: Inclusive start of the aggregation window.
        end_date: Inclusive end of the aggregation window.

    Returns:
        DataFrame with columns [source_iso3, target_iso3, date (Timestamp),
        tone_sum (float), event_count (int)].
    """
    from pipeline.sources.gdelt_doc import FIPS_TO_ISO3

    df = events.copy()
    df["date"] = pd.to_datetime(df["Day"].astype(str), format="%Y%m%d", errors="coerce")

    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    df = df[(df["date"] >= start_ts) & (df["date"] <= end_ts)].copy()

    # Keep only rows with both actor country codes (2-char FIPS)
    df = df.dropna(subset=["Actor1CountryCode", "Actor2CountryCode"])
    df = df[
        (df["Actor1CountryCode"].str.len() == 2) &
        (df["Actor2CountryCode"].str.len() == 2)
    ].copy()

    df["source_iso3"] = df["Actor1CountryCode"].map(FIPS_TO_ISO3)
    df["target_iso3"] = df["Actor2CountryCode"].map(FIPS_TO_ISO3)
    df = df.dropna(subset=["source_iso3", "target_iso3"])

    if df.empty:
        return pd.DataFrame(
            columns=["source_iso3", "target_iso3", "date", "tone_sum", "event_count"]
        )

    result = (
        df.groupby(["source_iso3", "target_iso3", "date"])
        .agg(
            tone_sum=("GoldsteinScale", "sum"),
            event_count=("GlobalEventID", "count"),
        )
        .reset_index()
    )
    return result


def aggregate_weekly(dyadic: pd.DataFrame) -> pd.DataFrame:
    """Collapse daily dyadic tensor to weekly averages.

    Args:
        dyadic: Output of build_dyadic_tensor().

    Returns:
        DataFrame with columns [source_iso3, target_iso3, week (Timestamp,
        ISO week start Monday), tone_mean (float), event_count (int)].
    """
    df = dyadic.copy()
    df["date"] = pd.to_datetime(df["date"])
    # week = Monday of the ISO week
    df["week"] = df["date"] - pd.to_timedelta(df["date"].dt.weekday, unit="D")
    df["week"] = df["week"].dt.normalize()

    return (
        df.groupby(["source_iso3", "target_iso3", "week"])
        .agg(
            tone_mean=("tone_sum", "mean"),
            event_count=("event_count", "sum"),
        )
        .reset_index()
    )


def get_primary_counterparty(
    dyadic: pd.DataFrame,
    target_iso3: str,
    window_days: int = 7,
) -> dict:
    """Find the source country with the largest |tone_sum| toward target_iso3.

    Used to populate the primary_counterparty field on signal cards.

    Args:
        dyadic: Output of build_dyadic_tensor().
        target_iso3: The country receiving events.
        window_days: Look at the most recent N days of data.

    Returns:
        Dict with keys: iso3, tone_7d.  iso3 is None if no events found.
    """
    df = dyadic.copy()
    df["date"] = pd.to_datetime(df["date"])

    if df.empty:
        return {"iso3": None, "tone_7d": 0.0}

    cutoff = df["date"].max() - pd.Timedelta(days=window_days)
    recent = df[(df["target_iso3"] == target_iso3) & (df["date"] >= cutoff)]

    if recent.empty:
        return {"iso3": None, "tone_7d": 0.0}

    agg = recent.groupby("source_iso3")["tone_sum"].sum()
    top = agg.abs().idxmax()
    return {"iso3": top, "tone_7d": round(float(agg[top]), 2)}


def build_matrix_subset(
    dyadic_weekly: pd.DataFrame,
    country_list: list[str],
    window: str = "30d",
) -> pd.DataFrame:
    """Build an N×N pivot table of mean tone for the matrix view.

    Args:
        dyadic_weekly: Output of aggregate_weekly().
        country_list: ISO3 codes to include; defines both axes.
        window: One of '7d', '30d', '90d' — restricts to the most recent N weeks.

    Returns:
        DataFrame with source_iso3 as index and target_iso3 as columns.
        Missing pairs filled with 0.0.
    """
    df = dyadic_weekly.copy()
    df["week"] = pd.to_datetime(df["week"])

    # trim to window
    days = int(window.rstrip("d"))
    cutoff = df["week"].max() - pd.Timedelta(days=days)
    df = df[df["week"] >= cutoff]

    df = df[df["source_iso3"].isin(country_list) & df["target_iso3"].isin(country_list)]

    if df.empty:
        return pd.DataFrame(0.0, index=country_list, columns=country_list)

    pivot = (
        df.groupby(["source_iso3", "target_iso3"])["tone_mean"]
        .mean()
        .unstack(fill_value=0.0)
    )
    return pivot.reindex(index=country_list, columns=country_list, fill_value=0.0)
