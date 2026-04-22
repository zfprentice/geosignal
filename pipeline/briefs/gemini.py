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
    """Initialise and return an authenticated Gemini GenerativeModel.

    Returns:
        google.generativeai.GenerativeModel configured for gemini-1.5-flash.

    Raises:
        EnvironmentError: If GEMINI_API_KEY is not set.
        ImportError: If google-generativeai is not installed.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set. "
            "Set it before calling any Gemini functions."
        )
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ImportError(
            "google-generativeai is required. "
            "Install with: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


def generate_cluster_label(representative_headlines: list[str]) -> str:
    """Generate a 2-3 word theme label for a cluster of headlines.

    Args:
        representative_headlines: Up to 5 representative headlines from
                                  the cluster (selected by proximity to
                                  cluster centroid).

    Returns:
        2-3 word theme label string (e.g., 'coup-risk', 'energy-security').
        Falls back to 'unknown-theme' if the API call fails.
    """
    model = get_client()
    prompt = (
        "Give a 2-3 word hyphenated theme label for this cluster of news "
        "headlines. Return only the label — no explanation, no punctuation "
        "beyond hyphens.\n\n"
        + "\n".join(f"- {h}" for h in representative_headlines[:5])
    )
    try:
        response = model.generate_content(prompt)
        label = response.text.strip().strip('"').strip("'").lower().replace(" ", "-")
        return label
    except Exception:
        return "unknown-theme"


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
        ~60-word prose brief string. Returns a minimal fallback on API error.
    """
    model = get_client()

    direction = "rose" if watchlist_delta >= 0 else "fell"
    abs_delta = abs(watchlist_delta)
    dominant = max(components, key=components.get) if components else "instability"

    headlines_text = "\n".join(f"- {h}" for h in top_headlines[:5])
    prompt = (
        f"Write a 60-word analytical brief (dry, data-first tone, no moralising) "
        f"for {country_name} ({iso3}). "
        f"The Watchlist Index {direction} by {abs_delta:.1f} points this week. "
        f"The dominant driver was {dominant}. "
        f"Recent headlines:\n{headlines_text}\n\n"
        f"Return only the brief text. Do not include any numbers from the scores."
    )
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return (
            f"{country_name}'s risk signal {direction} this week, "
            f"driven by elevated {dominant}."
        )


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
        Returns minimal fallback string on API error.
    """
    model = get_client()

    signals_text = ""
    for i, s in enumerate(signals[:5], 1):
        signals_text += (
            f"\n{i}. {s.get('country_name', s.get('iso3', ''))}\n"
            f"   Tags: {', '.join(s.get('tags', []))}\n"
            f"   Brief: {s.get('brief', '')}\n"
            f"   Key counterparty: {s.get('counterparty', 'N/A')}\n"
        )

    prompt = (
        "Write an 800-1000 word Substack post in a dry, analytical, data-first "
        "style (think The Economist crossed with a quant desk research note). "
        "No moralising. No speculation beyond what the data shows. No alarmism.\n\n"
        "Structure:\n"
        "1. Headline (one line)\n"
        "2. TL;DR (exactly 2 sentences)\n"
        "3. One section per country signal below (100-150 words each)\n\n"
        f"This week's top signals:\n{signals_text}\n\n"
        "Format as Markdown. Do not include any Watchlist Index numbers or scores."
    )
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        countries = ", ".join(
            s.get("country_name", s.get("iso3", "")) for s in signals[:5]
        )
        return (
            f"# GeoSignal Weekly — Top Signals\n\n"
            f"**TL;DR**: This week's elevated risk signals span {countries}. "
            f"Multiple indicators point to heightened instability across these regions.\n\n"
            f"*(Full draft unavailable — Gemini API error)*"
        )
