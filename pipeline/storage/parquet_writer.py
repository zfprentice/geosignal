"""
Parquet snapshot writer and reader for the hist/ archive.

The hist/ directory is the archival record: one dated parquet per day,
containing the full country × feature panel for that day.

File format: hist/YYYY-MM-DD.parquet
Schema (~180 countries × ~20 features = ~3600 rows):
    iso3                    str     ISO3 country code
    date                    date    snapshot date
    events_total            int     total GDELT events
    tone_mean               float   mean Goldstein tone
    conflict_events         int     CAMEO 14-20 events
    cooperation_events      int     CAMEO 01-07 events
    protest_events          int     CAMEO 14 (protest) events
    dyadic_inbound_tone     float   mean tone of events targeting this country
    dyadic_inbound_count    int     count of events targeting this country
    z_deviation             float   robust z-score (Primitive 1)
    trend_slope             float   Theil-Sen 30d slope (Primitive 2)
    contagion               float   neighbourhood spillover score (Primitive 5)
    fragility               float   structural fragility score
    watchlist               float   composite Watchlist Index (0-10)
    watchlist_percentile    int     global percentile rank
    watchlist_wow_delta     float   week-on-week change

Spec reference: §3.4 (Storage strategy). File size target: ~50KB/day.

Standalone usage:
    python pipeline/storage/parquet_writer.py --date 2026-04-21
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd


HIST_DIR = Path("hist")

PANEL_COLUMNS = [
    "iso3", "date",
    "events_total", "tone_mean", "conflict_events",
    "cooperation_events", "protest_events",
    "dyadic_inbound_tone", "dyadic_inbound_count",
    "z_deviation", "trend_slope", "contagion", "fragility",
    "watchlist", "watchlist_percentile", "watchlist_wow_delta",
]


def write_snapshot(panel: pd.DataFrame, date: datetime, hist_dir: Path = HIST_DIR) -> Path:
    """Write the full country panel for a given date to parquet.

    Args:
        panel: DataFrame with columns matching PANEL_COLUMNS.
        date: The date this snapshot represents.
        hist_dir: Directory to write into.

    Returns:
        Path to the written parquet file.
    """
    path = Path(hist_dir)
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / f"{date.strftime('%Y-%m-%d')}.parquet"
    panel.to_parquet(file_path, index=False)
    return file_path


def read_snapshot(date: datetime, hist_dir: Path = HIST_DIR) -> pd.DataFrame:
    """Read the parquet snapshot for a given date.

    Args:
        date: Date to read.
        hist_dir: Directory containing parquet files.

    Returns:
        DataFrame with PANEL_COLUMNS schema.

    Raises:
        FileNotFoundError: If no snapshot exists for the given date.
    """
    file_path = Path(hist_dir) / f"{date.strftime('%Y-%m-%d')}.parquet"
    if not file_path.exists():
        raise FileNotFoundError(
            f"No snapshot for {date.strftime('%Y-%m-%d')}: {file_path}"
        )
    return pd.read_parquet(file_path)


def read_country_history(
    iso3: str,
    start: datetime,
    end: datetime,
    hist_dir: Path = HIST_DIR,
) -> pd.DataFrame:
    """Read daily snapshots for a single country over a date range.

    Used to construct sparklines and time series for country detail pages.

    Args:
        iso3: Country ISO3 code.
        start: Start date (inclusive).
        end: End date (inclusive).
        hist_dir: Directory containing parquet files.

    Returns:
        DataFrame with PANEL_COLUMNS filtered to the given country,
        sorted by date ascending.
    """
    dates = list_available_dates(hist_dir)
    frames = []
    for d in dates:
        if start <= d <= end:
            try:
                df = read_snapshot(d, hist_dir)
                rows = df[df["iso3"] == iso3]
                if not rows.empty:
                    frames.append(rows)
            except FileNotFoundError:
                pass
    if not frames:
        return pd.DataFrame(columns=PANEL_COLUMNS)
    return (
        pd.concat(frames, ignore_index=True)
        .sort_values("date")
        .reset_index(drop=True)
    )


def list_available_dates(hist_dir: Path = HIST_DIR) -> list[datetime]:
    """Return sorted list of dates for which snapshots exist.

    Args:
        hist_dir: Directory to scan.

    Returns:
        List of datetime objects, sorted ascending.
    """
    path = Path(hist_dir)
    if not path.exists():
        return []
    result = []
    for f in sorted(path.glob("????-??-??.parquet")):
        try:
            result.append(datetime.strptime(f.stem, "%Y-%m-%d"))
        except ValueError:
            pass
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parquet snapshot utility")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD to read")
    args = parser.parse_args()

    if args.date:
        date = datetime.strptime(args.date, "%Y-%m-%d")
        df = read_snapshot(date)
        print(f"Snapshot {args.date}: {len(df)} rows, {df.columns.tolist()}")
    else:
        dates = list_available_dates()
        if dates:
            print(f"{len(dates)} snapshots available: {dates[0].date()} → {dates[-1].date()}")
        else:
            print("No snapshots available in hist/")
