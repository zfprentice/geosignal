"""
Build docs/data/matrix.json — the dyadic heatmap data.

Assembles tone data for the 20×20 matrix view (spec §4.5):
  - 20 countries: G20 + EU majors + key conflict states
  - Cell = mean Goldstein tone, source → target, per time window
  - Three windows: 7d, 30d, 90d

Data contract:
  {
    "generated_at": "...",
    "countries": [{"iso3": "USA", "name": "United States"}, ...],
    "windows": {
      "7d":  {"matrix": [[tone, ...], ...], "counts": [[n, ...], ...]},
      "30d": {...},
      "90d": {...}
    }
  }

Standalone usage:
    python pipeline/publishing/build_matrix_json.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


OUTPUT_PATH = Path("docs/data/matrix.json")

MATRIX_COUNTRIES = [
    "USA", "CHN", "RUS", "DEU", "FRA", "GBR", "JPN", "IND", "BRA", "CAN",
    "KOR", "AUS", "MEX", "IDN", "SAU", "ZAF", "ARG", "TUR", "IRN", "ISR",
]


def build() -> dict:
    """Assemble matrix.json payload for all three time windows.

    Returns:
        Dict matching the matrix.json schema.
    """
    raise NotImplementedError


if __name__ == "__main__":
    payload = build()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Wrote matrix.json ({len(MATRIX_COUNTRIES)}×{len(MATRIX_COUNTRIES)} grid)")
