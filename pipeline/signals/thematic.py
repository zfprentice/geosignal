"""
Signal Primitive 6 — Thematic exposure via embedding clustering.

Run once per week (spec §2.2, Primitive 6):
  1. Pull Reuters/GDELT headlines from the past 7 days.
  2. Embed via sentence-transformers/all-MiniLM-L6-v2.
  3. HDBSCAN clustering.
  4. Label each cluster via Gemini (2-3 word theme label — prose only, no scores).
  5. Compute per-country thematic exposure = share of headlines in each cluster.

Gemini is used ONLY for cluster label strings, never for numeric outputs.
Cluster membership and exposure shares are fully deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MIN_CLUSTER_SIZE = 5


def embed_headlines(headlines: list[str]) -> np.ndarray:
    """Embed headlines using all-MiniLM-L6-v2 (384-dimensional).

    Args:
        headlines: List of headline strings.

    Returns:
        Array of shape (n_headlines, 384).

    Raises:
        ImportError: If sentence-transformers is not installed.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is required. "
            "Install with: pip install sentence-transformers"
        ) from exc

    model = SentenceTransformer(EMBEDDING_MODEL)
    return model.encode(headlines, show_progress_bar=False)


def cluster_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """Cluster headline embeddings using HDBSCAN.

    Args:
        embeddings: Array of shape (n, 384) from embed_headlines().

    Returns:
        Integer cluster label array, length n.  -1 = noise (unclustered).

    Raises:
        ImportError: If hdbscan is not installed.
    """
    try:
        import hdbscan
    except ImportError as exc:
        raise ImportError(
            "hdbscan is required. Install with: pip install hdbscan"
        ) from exc

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        metric="euclidean",
        core_dist_n_jobs=-1,
    )
    return clusterer.fit_predict(embeddings)


def label_clusters(
    headlines: list[str],
    labels: np.ndarray,
    gemini_client,
) -> dict[int, str]:
    """Generate 2-3 word theme labels for each cluster via Gemini.

    Sends the top 5 most-central headlines (by position in the list)
    for each cluster.  Gemini returns a label string only — no numbers.

    Args:
        headlines: Original headline strings matching labels by index.
        labels: Cluster assignments from cluster_embeddings().
        gemini_client: Initialised Gemini client (from pipeline/briefs/gemini.py).

    Returns:
        Dict mapping cluster_id → theme label string.
        Noise cluster (-1) is excluded.
    """
    from collections import defaultdict

    cluster_headlines: dict[int, list[str]] = defaultdict(list)
    for i, label in enumerate(labels):
        if label == -1:
            continue
        cluster_headlines[int(label)].append(headlines[i])

    result: dict[int, str] = {}
    for cluster_id, h_list in cluster_headlines.items():
        representatives = h_list[:5]
        prompt = (
            "Give a 2-3 word theme label for this cluster of news headlines. "
            "Return only the label, no explanation.\n\n"
            + "\n".join(f"- {h}" for h in representatives)
        )
        try:
            response = gemini_client.generate_content(prompt)
            label_text = response.text.strip().strip('"').strip("'")
            result[cluster_id] = label_text
        except Exception:
            result[cluster_id] = f"theme-{cluster_id}"

    return result


def compute_country_exposure(
    headlines_df: pd.DataFrame,
    labels: np.ndarray,
    cluster_labels: dict[int, str],
) -> pd.DataFrame:
    """Compute per-country thematic exposure shares.

    For each country, the share of its headlines in each named cluster.

    Args:
        headlines_df: DataFrame with columns [iso3, headline].
                      Rows must align with labels (same order, same length).
        labels: Cluster assignments from cluster_embeddings().
        cluster_labels: Output of label_clusters().

    Returns:
        DataFrame with columns [iso3, theme, share] where share ∈ [0, 1]
        and shares sum to 1 per country (noise excluded from denominator).
    """
    df = headlines_df.copy().reset_index(drop=True)
    df["cluster_id"] = labels

    # exclude noise
    df = df[df["cluster_id"] != -1].copy()
    df["theme"] = df["cluster_id"].map(cluster_labels)

    if df.empty:
        return pd.DataFrame(columns=["iso3", "theme", "share"])

    counts = df.groupby(["iso3", "theme"]).size().reset_index(name="count")
    totals = counts.groupby("iso3")["count"].transform("sum")
    counts["share"] = counts["count"] / totals

    return counts[["iso3", "theme", "share"]].copy()


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
        labels: Cluster assignments from cluster_embeddings().
        out_path: Output file path.
    """
    from collections import defaultdict
    from datetime import datetime, timezone

    cluster_headlines: dict[int, list[str]] = defaultdict(list)
    for i, label in enumerate(labels):
        if label == -1:
            continue
        cluster_headlines[int(label)].append(headlines[i])

    clusters = []
    for cluster_id, theme in cluster_labels.items():
        reps = cluster_headlines.get(cluster_id, [])[:5]
        clusters.append({
            "id": cluster_id,
            "theme": theme,
            "size": len(cluster_headlines.get(cluster_id, [])),
            "representative_headlines": reps,
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "week": datetime.now(timezone.utc).strftime("%Y-W%W"),
        "clusters": sorted(clusters, key=lambda c: -c["size"]),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
