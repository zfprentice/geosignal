"""
Weekly Substack draft generator and email sender.

Run every Monday 06:30 UTC by weekly.yml.

Pipeline (spec §5.1):
  1. Load signals.json, take top 5.
  2. Render sparkline charts as PNG (matplotlib).
  3. Call Gemini with top 5 signals as structured input.
  4. Save as posts/YYYY-MM-DD-draft.md.
  5. Email Zach via SMTP with draft inlined + link to review.

Gemini prompt guidance (spec §5.1):
  - Tone: dry, data-first, analytical, New Yorker-adjacent
  - Do not moralise; lead with the signal
  - Target: 800-1000 words
  - Structure: headline, 2-sentence TL;DR, per-signal sections

Required env vars:
    GEMINI_API_KEY
    SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO

Standalone usage:
    python pipeline/publishing/draft_substack.py [--dry-run]
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


POSTS_DIR = Path("posts")


def render_signal_charts(signals: list[dict]) -> list[Path]:
    """Render 90-day sparkline charts for each signal as PNG files.

    Args:
        signals: Top 5 signal dicts from signals.json.

    Returns:
        List of paths to rendered PNG files.
    """
    raise NotImplementedError


def generate_draft(signals: list[dict]) -> str:
    """Call Gemini to generate the weekly Substack draft.

    Args:
        signals: Top 5 signal dicts from signals.json.

    Returns:
        Markdown string (800-1000 words) with headline, TL;DR, sections.
    """
    raise NotImplementedError


def save_draft(draft: str, date: datetime | None = None) -> Path:
    """Save draft to posts/YYYY-MM-DD-draft.md.

    Args:
        draft: Markdown string from generate_draft().
        date: Date for the filename. Defaults to today.

    Returns:
        Path to saved draft file.
    """
    raise NotImplementedError


def email_draft(draft: str, charts: list[Path], draft_path: Path) -> None:
    """Send the draft to Zach via SMTP.

    Args:
        draft: Markdown draft content.
        charts: Paths to chart PNG files to attach.
        draft_path: Path to the saved draft file (included as reference link).
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate weekly Substack draft")
    parser.add_argument("--dry-run", action="store_true", help="Generate draft but don't email")
    args = parser.parse_args()

    from pathlib import Path
    import json

    signals_path = Path("docs/data/signals.json")
    signals = json.loads(signals_path.read_text())["signals"][:5]

    charts = render_signal_charts(signals)
    draft = generate_draft(signals)
    path = save_draft(draft)
    print(f"Saved draft to {path}")

    if not args.dry_run:
        email_draft(draft, charts, path)
        print("Draft emailed.")
