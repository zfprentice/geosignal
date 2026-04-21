"""
Signal Primitive 6 — Thematic exposure via embedding clustering.

Run once per week:
  1. Pull all Reuters/GDELT headlines from the past 7 days.
  2. Embed via sentence-transformers/all-MiniLM-L6-v2.
  3. HDBSCAN clustering.
  4. For each cluster, send top 5 representative headlines to Gemini
     with prompt: "give a 2-3 word theme label". Cache for the week.
  5. For each country, compute thematic exposure = share of its
     headlines in each cluster.

Spec reference: §2.2 Primitive 6.

Note: Gemini is used only for 2-3 word label generation (not for scores).
The cluster membership and exposure shares are computed deterministically.

Outputs:
  - docs/data/themes.json (cluster labels + top headlines)
  - thematic_exposure column per country (for signal cards + globe filter)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MIN_CLUSTER_SIZE = 5


def embed_headlines(headlines: list[str]) -> np.ndarray:
    """Embed headlines using all-MiniLM-L6-v2.

    Args:
        headlines: List of headline strings.

    Returns:
        Array of shape (n_headlines, 384) — MiniLM output dimension.
    """
    raise NotImplementedError


def cluster_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """Run HDBSCAN clustering on headline embeddings.

    Args:
        embeddings: Array of shape (n, 384) from embed_headlines().

    Returns:
        Array of integer cluster labels, length n. -1 = noise.
    """
    raise NotImplementedError


def label_clusters(
    headlines: list[str],
    labels: np.ndarray,
    gemini_client,
) -> dict[int, str]:
    """Generate 2-3 word theme labels for each cluster via Gemini.

    Sends top 5 representative headlines per cluster.
    Gemini returns a theme label only — no scores.

    Args:
        headlines: Original headline strings.
        labels: Cluster assignments from cluster_embeddings().
        gemini_client: Initialised Gemini client from pipeline/briefs/gemini.py.

    Returns:
        Dict mapping cluster_id → theme label string.
    """
    raise NotImplementedError


def compute_country_exposure(
    headlines_df: pd.DataFrame,
    labels: np.ndarray,
    cluster_labels: dict[int, str],
) -> pd.DataFrame:
    """Compute per-country thematic exposure shares.

    Args:
        headlines_df: DataFrame with columns [iso3, headline].
        labels: Cluster assignments matching headlines_df rows.
        cluster_labels: Output of label_clusters().

    Returns:
        DataFrame [iso3, theme, share] — share of country's headlines
        in each theme cluster.
    """
    raise NotImplementedError


def build_themes_json(
    cluster_labels: dict[int, str],
    headlines: list[str],
    labels: np.ndarray,
    out_path: Path = Path("docs/data/themes.json"),
) -> None:
    """Write themes.json with cluster labels and top representative headlines.

    Args:
        cluster_labels: Output of label_clusters().
        headlines: All headline strings.
        labels: Cluster assignments.
        out_path: Output file path.
    """
    raise NotImplementedError
