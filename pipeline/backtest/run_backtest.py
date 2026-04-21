"""
Backtest runner — validates model against the historical events library.

For each event in pipeline/backtest/events.yaml, pulls historical GDELT
data (via BigQuery) for the 180-day window around T-0 (90d pre, 90d post),
re-runs all signal primitives and Watchlist scoring on that historical data,
and records:

  - Watchlist values at T-30, T-14, T-7, T-0
  - Global percentile rank of the country at T-7
  - Whether the country appeared in the top-20 signals at any point
    in the 60 days preceding T-0
  - A binary FLAGGED / MISSED judgment (threshold: >2σ above baseline before T-0)

Outputs:
  - docs/data/backtest.json (read by backtest.html)
  - backtest_results.json (full results, committed to repo for transparency)

The backtest page (spec §4.4) should be aggressively honest.
If the model missed an event, say so and explain why.

Spec reference: §1.3, §2.4, §5 (Phase 5 acceptance criteria).

Standalone usage:
    python pipeline/backtest/run_backtest.py [--events niger_coup_2023]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml


EVENTS_PATH = Path(__file__).parent / "events.yaml"
OUTPUT_PATH = Path("docs/data/backtest.json")
RESULTS_PATH = Path("backtest_results.json")


def load_events(events_path: Path = EVENTS_PATH) -> list[dict]:
    """Load event definitions from events.yaml.

    Returns:
        List of event dicts with keys: id, label, iso3, t0, description.
    """
    raise NotImplementedError


def run_event(event: dict) -> dict:
    """Run backtest for a single historical event.

    Fetches historical GDELT data for the 180-day window,
    re-runs scoring primitives, and evaluates model performance.

    Args:
        event: Event dict from events.yaml.

    Returns:
        Dict with keys:
            event_id, label, iso3, t0,
            watchlist_series (date → value, 180 days),
            markers (T-30, T-14, T-7, T-0 values and percentiles),
            flagged (bool),
            miss_reason (str | None),
            false_positive_context (str)
    """
    raise NotImplementedError


def build_backtest_json(results: list[dict]) -> dict:
    """Assemble backtest.json payload from run_event() results.

    Args:
        results: List of run_event() outputs.

    Returns:
        Dict matching backtest.json schema, including summary table.
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run historical backtest")
    parser.add_argument(
        "--events", nargs="*", default=None,
        help="Event IDs to run (default: all). E.g. --events niger_coup_2023"
    )
    args = parser.parse_args()

    events = load_events()
    if args.events:
        events = [e for e in events if e["id"] in args.events]

    results = [run_event(e) for e in events]
    payload = build_backtest_json(results)

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2))
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    flagged = sum(r["flagged"] for r in results)
    print(f"Backtest complete: {flagged}/{len(results)} events flagged before T-0")
