"""
Reuters RSS — headline fetcher for thematic clustering.

Pulls headlines from Reuters RSS feeds across topic categories
(world, politics, business, emerging markets). These headlines are
the input to the weekly embedding-based thematic clustering pipeline
in pipeline/signals/thematic.py.

No authentication required; RSS feeds are public.

Spec reference: §2.1 (Reuters RSS, hourly, free).
                §2.2 Primitive 6 (thematic exposure input).

Feed categories fetched:
    - world news
    - politics
    - business
    - emerging markets

Standalone usage:
    python pipeline/sources/reuters_rss.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


FEEDS: dict[str, str] = {
    "world": "https://feeds.reuters.com/reuters/worldNews",
    "politics": "https://feeds.reuters.com/reuters/politicsNews",
    "business": "https://feeds.reuters.com/reuters/businessNews",
}


def fetch() -> pd.DataFrame:
    """Fetch current headlines from all Reuters RSS feeds.

    Returns:
        DataFrame with columns:
            title, link, published, summary, category, fetched_at
    """
    raise NotImplementedError


def write_parquet(df: pd.DataFrame, out_dir: Path = Path("hist")) -> Path:
    """Write headlines to dated parquet for thematic pipeline.

    Returns:
        Path to written file.
    """
    raise NotImplementedError


if __name__ == "__main__":
    df = fetch()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out = Path(f"hist/reuters-{today}.parquet")
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df)} rows to {out}")
