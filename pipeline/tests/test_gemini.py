"""
Unit tests for pipeline/briefs/gemini.py.

Strategy: patch get_client() to return a MagicMock model — no real network
calls, no GEMINI_API_KEY required.  Each test verifies one of three things:

  1. The happy path returns the model's text as a plain string.
  2. The fallback path returns a plain string when generate_content raises.
  3. The prompt sent to the model satisfies the hard invariant: Gemini is
     never asked to produce numeric scores, and the prompt contains the
     structural constraints specified in §2.5 and §5.1.

Hard invariant (spec §2.5):
    generate_country_brief and generate_substack_draft must instruct Gemini
    NOT to output Watchlist scores.  The fallback strings must also be
    score-free.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from pipeline.briefs.gemini import (
    generate_cluster_label,
    generate_country_brief,
    generate_substack_draft,
    get_client,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _model(text: str = "mock response") -> MagicMock:
    """Mock GenerativeModel whose generate_content returns text."""
    m = MagicMock()
    resp = MagicMock()
    resp.text = text
    m.generate_content.return_value = resp
    return m


def _model_raises(exc: Exception = RuntimeError("api error")) -> MagicMock:
    """Mock GenerativeModel whose generate_content raises exc."""
    m = MagicMock()
    m.generate_content.side_effect = exc
    return m


def _prompt(model: MagicMock) -> str:
    """Extract the prompt string passed to generate_content."""
    return model.generate_content.call_args[0][0]


# ---------------------------------------------------------------------------
# get_client — key validation and SDK wiring
# ---------------------------------------------------------------------------

class TestGetClient:
    def test_raises_when_key_absent(self):
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(EnvironmentError, match="GEMINI_API_KEY"):
                get_client()

    def test_empty_string_key_also_raises(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with pytest.raises(EnvironmentError):
                get_client()

    def test_configures_sdk_and_returns_model(self):
        genai = pytest.importorskip("google.generativeai")
        mock_model = MagicMock()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch.object(genai, "configure") as cfg:
                with patch.object(genai, "GenerativeModel", return_value=mock_model) as cls:
                    result = get_client()
        cfg.assert_called_once_with(api_key="test-key")
        cls.assert_called_once_with("gemini-1.5-flash")
        assert result is mock_model


# ---------------------------------------------------------------------------
# generate_cluster_label
# ---------------------------------------------------------------------------

HEADLINES = [
    "Niger military seizes power in overnight coup",
    "France evacuates nationals from Niamey",
    "ECOWAS threatens military intervention",
    "Junta suspends constitution, closes borders",
    "Protests in capital split along ethnic lines",
]


class TestGenerateClusterLabel:
    def test_returns_string(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model("coup-risk")):
            assert isinstance(generate_cluster_label(HEADLINES), str)

    def test_strips_and_lowercases_response(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model("  Coup Risk  ")):
            result = generate_cluster_label(HEADLINES)
        assert result == "coup-risk"

    def test_strips_surrounding_quotes(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model('"sahel-security"')):
            result = generate_cluster_label(HEADLINES)
        assert result == "sahel-security"

    def test_prompt_requests_hyphenated_label(self):
        m = _model("theme")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_cluster_label(HEADLINES)
        assert "hyphenated" in _prompt(m).lower()

    def test_prompt_contains_all_five_headlines(self):
        m = _model("theme")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_cluster_label(HEADLINES)
        p = _prompt(m)
        for h in HEADLINES:
            assert h in p

    def test_only_first_five_headlines_used(self):
        many = [f"headline-{i}" for i in range(10)]
        m = _model("theme")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_cluster_label(many)
        p = _prompt(m)
        for i in range(5):
            assert f"headline-{i}" in p
        for i in range(5, 10):
            assert f"headline-{i}" not in p

    def test_fallback_is_unknown_theme(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model_raises()):
            assert generate_cluster_label(HEADLINES) == "unknown-theme"

    def test_fallback_is_string_on_any_exception(self):
        for exc in [ValueError("v"), ConnectionError("c"), TimeoutError("t")]:
            with patch("pipeline.briefs.gemini.get_client", return_value=_model_raises(exc)):
                result = generate_cluster_label(HEADLINES)
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# generate_country_brief
# ---------------------------------------------------------------------------

_BRIEF_KWARGS = dict(
    iso3="NER",
    country_name="Niger",
    watchlist=7.8,
    watchlist_delta=1.4,
    components={"deviation": 2.3, "trend": 0.8, "contagion": 1.2, "fragility": 1.9},
    top_headlines=[
        "Coup leader consolidates control in Niamey",
        "France withdraws ambassador from Niger",
    ],
)

_SCORE_STRINGS = ["7.8", "1.4", "2.3", "0.8", "1.2", "1.9"]


class TestGenerateCountryBrief:
    def test_returns_model_text_stripped(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model("  brief text  ")):
            assert generate_country_brief(**_BRIEF_KWARGS) == "brief text"

    def test_prompt_contains_country_name_and_iso3(self):
        m = _model("brief")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_country_brief(**_BRIEF_KWARGS)
        p = _prompt(m)
        assert "Niger" in p
        assert "NER" in p

    def test_prompt_encodes_rising_direction(self):
        m = _model("brief")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_country_brief(**_BRIEF_KWARGS)  # delta=+1.4
        assert "rose" in _prompt(m)

    def test_prompt_encodes_falling_direction(self):
        m = _model("brief")
        kwargs = {**_BRIEF_KWARGS, "watchlist_delta": -0.8}
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_country_brief(**kwargs)
        assert "fell" in _prompt(m)

    def test_prompt_forbids_numeric_score_output(self):
        """Hard invariant from spec §2.5."""
        m = _model("brief")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_country_brief(**_BRIEF_KWARGS)
        assert "Do not include any numbers from the scores" in _prompt(m)

    def test_prompt_caps_headlines_at_five(self):
        m = _model("brief")
        kwargs = {**_BRIEF_KWARGS, "top_headlines": [f"headline-{i}" for i in range(10)]}
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_country_brief(**kwargs)
        p = _prompt(m)
        for i in range(5):
            assert f"headline-{i}" in p
        for i in range(5, 10):
            assert f"headline-{i}" not in p

    def test_fallback_is_string_containing_country_name(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model_raises()):
            result = generate_country_brief(**_BRIEF_KWARGS)
        assert isinstance(result, str)
        assert "Niger" in result

    def test_fallback_contains_no_numeric_scores(self):
        """Score values must never appear in the fallback string."""
        with patch("pipeline.briefs.gemini.get_client", return_value=_model_raises()):
            result = generate_country_brief(**_BRIEF_KWARGS)
        for score in _SCORE_STRINGS:
            assert score not in result, f"Score {score!r} leaked into fallback"

    def test_zero_delta_treated_as_rose(self):
        m = _model("brief")
        kwargs = {**_BRIEF_KWARGS, "watchlist_delta": 0.0}
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_country_brief(**kwargs)
        assert "rose" in _prompt(m)

    def test_empty_components_does_not_raise(self):
        m = _model("brief")
        kwargs = {**_BRIEF_KWARGS, "components": {}}
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            result = generate_country_brief(**kwargs)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# generate_substack_draft
# ---------------------------------------------------------------------------

_SIGNALS = [
    {"iso3": "NER", "country_name": "Niger", "tags": ["coup-risk"], "brief": "...", "counterparty": "FRA"},
    {"iso3": "SDN", "country_name": "Sudan", "tags": ["conflict"], "brief": "...", "counterparty": "EGY"},
    {"iso3": "UKR", "country_name": "Ukraine", "tags": ["war"], "brief": "...", "counterparty": "RUS"},
]


class TestGenerateSubstackDraft:
    def test_returns_model_text_stripped(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model("  # Draft  ")):
            assert generate_substack_draft(_SIGNALS) == "# Draft"

    def test_prompt_forbids_watchlist_numbers(self):
        """Hard invariant from spec §2.5."""
        m = _model("draft")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_substack_draft(_SIGNALS)
        assert "Do not include any Watchlist Index numbers or scores" in _prompt(m)

    def test_prompt_requests_tl_dr(self):
        m = _model("draft")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_substack_draft(_SIGNALS)
        assert "TL;DR" in _prompt(m)

    def test_prompt_requests_markdown(self):
        m = _model("draft")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_substack_draft(_SIGNALS)
        assert "Markdown" in _prompt(m)

    def test_prompt_includes_all_provided_signals(self):
        m = _model("draft")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_substack_draft(_SIGNALS)
        p = _prompt(m)
        for s in _SIGNALS:
            assert s["country_name"] in p

    def test_only_first_five_signals_used(self):
        many = [
            {"iso3": f"C{i:02d}", "country_name": f"Country{i}", "tags": [], "brief": "", "counterparty": ""}
            for i in range(8)
        ]
        m = _model("draft")
        with patch("pipeline.briefs.gemini.get_client", return_value=m):
            generate_substack_draft(many)
        p = _prompt(m)
        for i in range(5):
            assert f"Country{i}" in p
        for i in range(5, 8):
            assert f"Country{i}" not in p

    def test_fallback_starts_with_markdown_heading(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model_raises()):
            result = generate_substack_draft(_SIGNALS)
        assert result.startswith("#")

    def test_fallback_contains_no_numeric_scores(self):
        signals_with_scores = [
            {**s, "watchlist": 7.8, "watchlist_delta": 1.4}
            for s in _SIGNALS
        ]
        with patch("pipeline.briefs.gemini.get_client", return_value=_model_raises()):
            result = generate_substack_draft(signals_with_scores)
        for score in ["7.8", "1.4"]:
            assert score not in result, f"Score {score!r} leaked into fallback"

    def test_empty_signals_list_returns_string(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model("draft")):
            assert isinstance(generate_substack_draft([]), str)

    def test_fallback_on_empty_signals_still_valid_string(self):
        with patch("pipeline.briefs.gemini.get_client", return_value=_model_raises()):
            result = generate_substack_draft([])
        assert isinstance(result, str)
        assert len(result) > 0
