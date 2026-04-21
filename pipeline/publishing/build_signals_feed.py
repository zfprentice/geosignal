"""
Build docs/data/signals.json — the hero signals feed.

Ranks all countries by Score_rank (spec §1.2), takes the top 10, and
assembles the signals.json payload consumed by the homepage.

Ranking formula:
    Score_rank = 0.5 * |z_deviation| + 0.3 * trend_slope + 0.2 * contagion
    (all components z-scored against the 180-country universe; ties broken by WoW delta)

Also runs threshold alert checks (spec §5.2) and sends email if triggered:
    - Any country with |watchlist_wow_delta| > 2.0
    - Any country newly entering the top 10
    - Any changepoint detected in last 24h

Data contract (spec §3.2 signals.json):
  - generated_at: ISO 8601 UTC timestamp
  - window: '7d'
  - signals: list of ranked signal objects

Standalone usage:
    python pipeline/publishing/build_signals_feed.py [--alerts]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


OUTPUT_PATH = Path("docs/data/signals.json")


def rank_signals(countries: list[dict]) -> list[dict]:
    """Rank countries by Score_rank and return top 10 as signal objects.

    Args:
        countries: List of country dicts from countries.json.

    Returns:
        List of signal dicts matching signals.json schema (spec §3.2),
        sorted descending by score_rank.
    """
    raise NotImplementedError


def check_alerts(
    countries: list[dict],
    previous_countries: list[dict],
) -> list[str]:
    """Check threshold conditions and return alert messages.

    Args:
        countries: Current countries list.
        previous_countries: Previous day's countries list for comparison.

    Returns:
        List of alert message strings (empty if no alerts triggered).
    """
    raise NotImplementedError


def send_alert_email(messages: list[str]) -> None:
    """Send a single combined alert email via SMTP.

    Uses SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO env vars.
    At most one email per daily run.

    Args:
        messages: List of alert message strings from check_alerts().
    """
    raise NotImplementedError


def build(countries_path: Path = Path("docs/data/countries.json")) -> dict:
    """Assemble signals.json payload.

    Args:
        countries_path: Path to current countries.json.

    Returns:
        Dict matching the signals.json schema.
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build signals feed")
    parser.add_argument("--alerts", action="store_true", help="Run alert checks")
    args = parser.parse_args()

    payload = build()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(payload['signals'])} signals to {OUTPUT_PATH}")
