"""
Weight tuning via grid search over the Watchlist Index simplex.

Searches (w1, w2, w3, w4) to maximise the average percentile rank
of event countries at T-7 across the events library.

Spec reference: §2.4 (Backtest as tuning loop).

IMPORTANT — do not overfit:
  8 events is too few for confident tuning. Keep weights near-uniform.
  Use this as validation, not training. If the best weights deviate
  significantly from the initial values (0.40, 0.25, 0.20, 0.15),
  investigate why before accepting them.

Grid search:
  - Sweep w1 ∈ [0.20, 0.60] in steps of 0.05
  - w2 = w3 = w4 = (1 - w1) / 3 as a baseline simplification
  - Full simplex search for final tuning (see tune_full_simplex())

Output:
  - Prints best weights and per-event performance table
  - Updates pipeline/scoring/config.yaml if --update flag is set
  - Appends results to backtest_results.json

Standalone usage:
    python pipeline/backtest/tune_weights.py [--update]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


CONFIG_PATH = Path("pipeline/scoring/config.yaml")


def grid_search_simplex(
    backtest_results: list[dict],
    n_points: int = 500,
) -> dict[str, float]:
    """Grid search over weight simplex to maximise avg percentile at T-7.

    Generates n_points random points on the 4-simplex (w1+w2+w3+w4=1,
    all wi >= 0), evaluates each against backtest_results, and returns
    the weights that maximise average event-country percentile rank at T-7.

    Args:
        backtest_results: Output of run_backtest.run_event() for all events.
        n_points: Number of simplex points to evaluate.

    Returns:
        Dict with keys w1, w2, w3, w4 (best found weights).
    """
    raise NotImplementedError


def evaluate_weights(
    weights: dict[str, float],
    backtest_results: list[dict],
) -> float:
    """Evaluate a weight vector against the events library.

    Args:
        weights: Dict with w1, w2, w3, w4.
        backtest_results: Per-event results with component scores.

    Returns:
        Mean percentile rank at T-7 across all events (higher = better).
    """
    raise NotImplementedError


def update_config(weights: dict[str, float], config_path: Path = CONFIG_PATH) -> None:
    """Write new weights to config.yaml.

    Args:
        weights: Dict with w1-w4.
        config_path: Path to config.yaml.
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tune Watchlist Index weights")
    parser.add_argument("--update", action="store_true", help="Write best weights to config.yaml")
    parser.add_argument("--points", type=int, default=500, help="Simplex sample points")
    args = parser.parse_args()

    import json
    results = json.loads(Path("backtest_results.json").read_text())
    best = grid_search_simplex(results, n_points=args.points)
    print(f"Best weights: {best}")

    if args.update:
        update_config(best)
        print(f"Updated {CONFIG_PATH}")
