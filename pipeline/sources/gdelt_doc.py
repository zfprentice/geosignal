"""
GDELT 2.0 DOC API — article headline fetcher.

Fetches article metadata (title, URL, source country, language, tone)
for a given country and time window using the GDELT Document API.
No API key required; the API is public.

Spec reference: §2.1 (GDELT 2.0 DOC API, hourly cadence).

Output: appends headline rows to a headlines cache file used by:
  - pipeline/signals/thematic.py (embedding clustering)
  - pipeline/publishing/build_countries_json.py (recent headlines field)

Standalone usage:
    python pipeline/sources/gdelt_doc.py [--window 7d|30d] [--country NER]
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


def fetch(
    country_iso2: Optional[str] = None,
    window: str = "7d",
    max_records: int = 1000,
) -> pd.DataFrame:
    """Fetch article headlines from the GDELT 2.0 DOC API.

    Args:
        country_iso2: ISO 2-letter country code to filter by source country.
                      None fetches global headlines.
        window: Lookback window — '7d' or '30d'.
        max_records: Maximum number of articles to return per call.

    Returns:
        DataFrame with columns:
            url, title, domain, language, seendate, socialimage,
            sourcecountry, sourcelang, tone, themes
    """
    raise NotImplementedError


def fetch_all_countries(window: str = "7d") -> pd.DataFrame:
    """Fetch headlines for all ~180 countries in the universe.

    Iterates over the country list, calls fetch() per country, and
    concatenates results into a single DataFrame.

    Returns:
        DataFrame with same schema as fetch(), plus iso3 column.
    """
    raise NotImplementedError


def save_headlines_cache(df: pd.DataFrame, cache_dir: Path = Path("hist/headlines")) -> Path:
    """Append today's headlines to the dated cache parquet.

    Args:
        df: DataFrame from fetch_all_countries().
        cache_dir: Directory for headline cache parquet files.

    Returns:
        Path to the written parquet file.
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch GDELT DOC headlines")
    parser.add_argument("--window", default="7d", choices=["7d", "30d"])
    parser.add_argument("--country", default=None, help="ISO2 country code (omit for all)")
    args = parser.parse_args()

    df = fetch(country_iso2=args.country, window=args.window)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out = Path(f"hist/headlines-{today}.parquet")
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df)} rows to {out}")
