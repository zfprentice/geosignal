"""
Gemini prose generation — briefs, cluster labels, Substack drafts.

IMPORTANT: Gemini never assigns scores or produces numbers used on charts.
It produces natural language only. All quantitative outputs come from
deterministic Python code in pipeline/signals/ and pipeline/scoring/.

Spec reference: §2.5 (What Gemini does).

Three use cases (all prose-only):

1. CLUSTER LABELS (weekly, ~30-50 calls)
   Input: top 5 representative headlines per cluster.
   Output: 2-3 word theme label string.
   See: pipeline/signals/thematic.py

2. COUNTRY BRIEFS (daily, ~180 calls)
   Input: deterministic scores + top 5 headlines for one country.
   Output: 60-word brief explaining what drove the score this week.
   See: pipeline/publishing/build_countries_json.py

3. WEEKLY SUBSTACK DRAFT (weekly, 1 call)
   Input: top 5 signals as structured JSON.
   Output: 800-1000 word post with headline, TL;DR, and per-signal sections.
   See: pipeline/publishing/draft_substack.py

Required env var:
    GEMINI_API_KEY

Model: gemini-1.5-flash (cost ~$1/month at these volumes).
"""

from __future__ import annotations

import os
from typing import Any


def get_client():
    """Initialise and return an authenticated Gemini client.

    Returns:
        Configured google.generativeai client.

    Raises:
        EnvironmentError: If GEMINI_API_KEY is not set.
    """
    raise NotImplementedError


def generate_cluster_label(representative_headlines: list[str]) -> str:
    """Generate a 2-3 word theme label for a cluster of headlines.

    Args:
        representative_headlines: Up to 5 representative headlines
                                  from the cluster (selected by proximity
                                  to cluster centroid).

    Returns:
        2-3 word theme label string (e.g., 'coup-risk', 'energy-security').
    """
    raise NotImplementedError


def generate_country_brief(
    iso3: str,
    country_name: str,
    watchlist: float,
    watchlist_delta: float,
    components: dict[str, float],
    top_headlines: list[str],
) -> str:
    """Generate a 60-word prose brief for a country's weekly signal.

    Gemini receives deterministic scores as context; it explains them
    in prose. It does NOT produce the numbers.

    Args:
        iso3: Country ISO3 code.
        country_name: Human-readable country name.
        watchlist: Current Watchlist Index value (0-10).
        watchlist_delta: Week-on-week change in Watchlist.
        components: Dict of component scores (deviation, trend, contagion, fragility).
        top_headlines: Up to 5 recent headlines for the country.

    Returns:
        ~60-word prose brief string.
    """
    raise NotImplementedError


def generate_substack_draft(signals: list[dict[str, Any]]) -> str:
    """Generate a weekly Substack draft from the top 5 signals.

    Prompt instructs Gemini to write in a dry, data-first, analytical style
    (New Yorker-adjacent, not alarmist, no moralising — see spec §5.1).

    Args:
        signals: Top 5 signals from signals.json, each with:
                 iso3, country_name, watchlist, watchlist_delta,
                 tags, brief, components, counterparty.

    Returns:
        800-1000 word Markdown string ready to be saved as a post draft.
        Includes: headline, 2-sentence TL;DR, per-signal sections.
    """
    raise NotImplementedError
