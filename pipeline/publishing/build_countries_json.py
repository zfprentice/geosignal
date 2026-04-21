"""
Build docs/data/countries.json — the current-state file.

Assembles the full country panel JSON from:
  - Watchlist Index scores (pipeline/scoring/watchlist.py)
  - Component scores (deviation, trend, contagion, fragility)
  - CAMEO breakdown summary (pipeline/signals/dyadic.py)
  - Primary counterparty (pipeline/signals/dyadic.py)
  - Thematic tags (pipeline/signals/thematic.py)
  - Changepoint dates (pipeline/signals/changepoint.py)
  - 90-day sparkline (from hist/ parquet files)
  - Gemini prose brief (pipeline/briefs/gemini.py)

Data contract (spec §3.2 countries.json):
  - generated_at: ISO 8601 UTC timestamp
  - universe_size: int
  - weights_version: date string of last weight update
  - countries: list of country objects

Each country object schema is defined in spec §3.2.

Run by daily.yml after all signal primitives have been computed.

Standalone usage:
    python pipeline/publishing/build_countries_json.py [--date 2026-04-21]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


OUTPUT_PATH = Path("docs/data/countries.json")


def build(date: datetime | None = None) -> dict:
    """Assemble the full countries.json payload for a given date.

    Args:
        date: Date to build for. Defaults to today UTC.

    Returns:
        Dict matching the countries.json schema from spec §3.2.
    """
    raise NotImplementedError


def write(payload: dict, out_path: Path = OUTPUT_PATH) -> None:
    """Write the countries.json payload to disk.

    Args:
        payload: Output of build().
        out_path: Destination path.
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build countries.json")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    date = datetime.strptime(args.date, "%Y-%m-%d") if args.date else None
    payload = build(date=date)
    write(payload)
    print(f"Wrote {len(payload['countries'])} countries to {OUTPUT_PATH}")
