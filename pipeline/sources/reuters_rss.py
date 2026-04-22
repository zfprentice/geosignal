"""
Reuters RSS — headline fetcher for thematic clustering.

Pulls headlines from public RSS feeds for use in the weekly embedding-
based thematic clustering pipeline (pipeline/signals/thematic.py).

No authentication required.  Reuters' public RSS feeds are used; if
a feed returns 403 or 404, the module falls back to alternative public
news RSS sources and logs a warning rather than raising.

Spec reference: §2.1 (Reuters RSS, hourly, free).
                §2.2 Primitive 6 (thematic exposure input).

Primary feeds (Reuters):
    https://feeds.reuters.com/reuters/worldNews
    https://feeds.reuters.com/reuters/businessNews
    https://feeds.reuters.com/reuters/technologyNews

Fallback feeds (used if Reuters returns 4xx):
    https://rss.nytimes.com/services/xml/rss/nyt/World.xml
    https://feeds.bbci.co.uk/news/world/rss.xml
    https://www.aljazeera.com/xml/rss/all.xml

Output schema:
    title (str), link (str), published (datetime),
    summary (str), category (str), source (str), fetched_at (datetime)

Standalone usage:
    python pipeline/sources/reuters_rss.py [--out-dir hist]
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

import feedparser
import pandas as pd
import requests

# Browser-like headers reduce 403 responses from news sites
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# Primary → fallback feed groups.  Each list is tried in order until one succeeds.
FEED_GROUPS: dict[str, list[str]] = {
    "world": [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    ],
    "business": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    ],
    "technology": [
        "https://feeds.reuters.com/reuters/technologyNews",
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
    ],
    "geopolitics": [
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ],
}

OUTPUT_COLUMNS = ["title", "link", "published", "summary", "category", "source", "fetched_at"]


def _parse_feed(url: str, category: str) -> list[dict]:
    """Fetch and parse a single RSS feed URL.

    Args:
        url: RSS feed URL.
        category: Category label to tag entries with.

    Returns:
        List of dicts with OUTPUT_COLUMNS keys.  Empty list on failure.
    """
    try:
        # Use requests to fetch so we can set headers, then pass content to feedparser
        resp = requests.get(url, headers=_HEADERS, timeout=20, allow_redirects=True)
        if resp.status_code in (403, 404, 410):
            return []
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception:
        return []

    if feed.bozo and not feed.entries:
        return []

    # infer source name from feed metadata
    source = feed.feed.get("title", url.split("/")[2])
    fetched_at = datetime.utcnow()

    rows = []
    for entry in feed.entries:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            import time
            published = datetime(*entry.published_parsed[:6])
        rows.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": published,
            "summary": entry.get("summary", entry.get("description", "")),
            "category": category,
            "source": source,
            "fetched_at": fetched_at,
        })
    return rows


def _fetch_group(category: str, urls: list[str]) -> list[dict]:
    """Try each URL in a feed group until one returns results.

    Args:
        category: Feed category name.
        urls: Ordered list of URLs to try.

    Returns:
        Rows from the first URL that returns non-empty results.
    """
    for url in urls:
        rows = _parse_feed(url, category)
        if rows:
            print(f"  {category}: {len(rows)} articles from {url.split('/')[2]}")
            return rows
        print(f"  {category}: no data from {url.split('/')[2]}, trying next …")
    print(f"  {category}: all feeds failed — skipping")
    return []


def fetch() -> pd.DataFrame:
    """Fetch current headlines from all feed groups.

    Returns:
        DataFrame with OUTPUT_COLUMNS schema.  Published column is UTC datetime.
        May be empty if all feeds fail.
    """
    all_rows: list[dict] = []
    for category, urls in FEED_GROUPS.items():
        all_rows.extend(_fetch_group(category, urls))

    if not all_rows:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    df = pd.DataFrame(all_rows)
    df["published"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
    df = df.drop_duplicates(subset=["link"])

    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[OUTPUT_COLUMNS].copy()


def write_parquet(df: pd.DataFrame, out_dir: Path = Path("hist")) -> Path:
    """Write headlines to a dated parquet for the thematic pipeline.

    Args:
        df: Output of fetch().
        out_dir: Directory for output.

    Returns:
        Path to written file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out = out_dir / f"reuters-{today}.parquet"
    df.to_parquet(out, index=False)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch RSS headlines")
    parser.add_argument("--out-dir", default="hist")
    args = parser.parse_args()

    df = fetch()
    path = write_parquet(df, Path(args.out_dir))
    print(f"Wrote {len(df)} rows to {path}")
    if not df.empty:
        print(df[["title", "category", "source"]].head(10).to_string())
