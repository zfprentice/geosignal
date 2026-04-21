"""
Signal Primitive 5 — Contagion / neighbourhood spillover.

For each country i, computes a weighted average of its neighbours'
instability, where neighbours are weighted by both geographic proximity
and dyadic event density.

Formula (spec §2.2, Primitive 5):
    contagion_i = Σ_j (w_geo(i,j) · w_dyad(i,j) · instability_j)
                  ─────────────────────────────────────────────────
                  Σ_j (w_geo(i,j) · w_dyad(i,j))

    w_geo  = exp(-distance_km(i, j) / 2000)
    w_dyad = normalised dyadic event volume over last 30d

Why: captures the Sahel effect. Niger's 2023 coup was preceded by
Mali-Burkina-Guinea instability — countries that share borders AND
have dense event dyads contaminate each other. Distant uninvolved
countries have near-zero weight.

Geo distances are precomputed from country centroids (lookup table).
Dyadic weights come from pipeline/signals/dyadic.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


GEO_DECAY_KM = 2000.0


def geo_weight(distance_km: float) -> float:
    """Compute geographic proximity weight.

    Args:
        distance_km: Great-circle distance between country centroids.

    Returns:
        exp(-distance_km / 2000)
    """
    raise NotImplementedError


def build_dyadic_weights(
    dyadic: pd.DataFrame,
    window_days: int = 30,
) -> pd.DataFrame:
    """Normalise dyadic event volumes to use as contagion weights.

    Args:
        dyadic: Output of pipeline/signals/dyadic.build_dyadic_tensor().
        window_days: Aggregation window.

    Returns:
        DataFrame [source_iso3, target_iso3, w_dyad] where w_dyad sums to 1
        per target country.
    """
    raise NotImplementedError


def compute_contagion(
    instability: pd.Series,
    geo_distances: pd.DataFrame,
    dyadic_weights: pd.DataFrame,
) -> pd.Series:
    """Compute contagion scores for all countries.

    Args:
        instability: Series indexed by iso3 with current instability values.
        geo_distances: DataFrame [iso3_i, iso3_j, distance_km].
        dyadic_weights: Output of build_dyadic_weights().

    Returns:
        Series indexed by iso3 with contagion scores in [0, 1].
    """
    raise NotImplementedError


def load_geo_distances() -> pd.DataFrame:
    """Load precomputed great-circle distances between country centroids.

    Returns:
        DataFrame with columns [iso3_i, iso3_j, distance_km].
    """
    raise NotImplementedError
