"""
Signal Primitive 5 — Contagion / neighbourhood spillover.

Formula (spec §2.2, Primitive 5):
    contagion_i = Σ_j (w_geo(i,j) · w_dyad(i,j) · instability_j)
                  ─────────────────────────────────────────────────
                  Σ_j (w_geo(i,j) · w_dyad(i,j))

    w_geo  = exp(-distance_km(i, j) / 2000)
    w_dyad = normalised dyadic event volume over last 30 days

Captures the Sahel effect: Niger's 2023 coup was preceded by
Mali-Burkina-Guinea instability well before Niger itself escalated.
Countries that share borders AND have dense event dyads contaminate each
other; distant uninvolved countries have near-zero combined weight.

load_geo_distances() computes great-circle distances from hardcoded country
centroids (lat, lon) using the haversine formula — no external data file needed.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

GEO_DECAY_KM = 2000.0

# Approximate country centroids (latitude, longitude).
# ~180 country universe; sufficient for all signal primitives.
_CENTROIDS: dict[str, tuple[float, float]] = {
    "AFG": (33.9, 67.7), "ALB": (41.1, 20.2), "DZA": (28.0, 1.7),
    "AND": (42.5, 1.5),  "AGO": (-11.2, 17.9), "ATG": (17.1, -61.8),
    "ARG": (-38.4, -63.6), "ARM": (40.1, 45.0), "AUS": (-25.3, 133.8),
    "AUT": (47.5, 14.6),  "AZE": (40.1, 47.6), "BHS": (25.0, -77.4),
    "BHR": (26.0, 50.6),  "BGD": (23.7, 90.4), "BRB": (13.2, -59.6),
    "BLR": (53.7, 28.0),  "BEL": (50.5, 4.5),  "BLZ": (17.2, -88.5),
    "BEN": (9.3, 2.3),    "BTN": (27.5, 90.4), "BOL": (-16.3, -63.6),
    "BIH": (44.2, 17.9),  "BWA": (-22.3, 24.7), "BRA": (-14.2, -51.9),
    "BRN": (4.5, 114.7),  "BGR": (42.7, 25.5), "BFA": (12.4, -1.6),
    "BDI": (-3.4, 29.9),  "CPV": (16.0, -24.0), "KHM": (12.6, 104.9),
    "CMR": (3.9, 11.5),   "CAN": (56.1, -106.3), "CAF": (6.6, 20.9),
    "TCD": (15.5, 18.7),  "CHL": (-35.7, -71.5), "CHN": (35.9, 104.2),
    "COL": (4.1, -72.9),  "COM": (-11.7, 43.3), "COD": (-4.0, 21.8),
    "COG": (-0.2, 15.8),  "CRI": (9.7, -83.8),  "CIV": (7.5, -5.5),
    "HRV": (45.1, 15.2),  "CUB": (21.5, -80.0), "CYP": (35.1, 33.4),
    "CZE": (49.8, 15.5),  "DNK": (56.3, 9.5),   "DJI": (11.8, 42.6),
    "DMA": (15.4, -61.4), "DOM": (18.7, -70.2),  "ECU": (-1.8, -78.2),
    "EGY": (26.8, 30.8),  "SLV": (13.8, -88.9),  "GNQ": (1.6, 10.3),
    "ERI": (15.2, 39.8),  "EST": (58.6, 25.0),   "SWZ": (-26.5, 31.5),
    "ETH": (9.1, 40.5),   "FJI": (-17.7, 178.1), "FIN": (64.0, 26.0),
    "FRA": (46.2, 2.2),   "GAB": (-0.8, 11.6),   "GMB": (13.4, -15.3),
    "GEO": (42.3, 43.4),  "DEU": (51.2, 10.5),   "GHA": (7.9, -1.0),
    "GRC": (39.1, 21.8),  "GRD": (12.1, -61.7),  "GTM": (15.8, -90.2),
    "GIN": (11.0, -10.9), "GNB": (11.8, -15.2),  "GUY": (4.9, -58.9),
    "HTI": (19.0, -72.3), "HND": (15.2, -86.2),  "HUN": (47.2, 19.5),
    "ISL": (64.9, -19.0), "IND": (20.6, 79.1),   "IDN": (-0.8, 113.9),
    "IRN": (32.4, 53.7),  "IRQ": (33.2, 43.7),   "IRL": (53.4, -8.2),
    "ISR": (31.0, 34.9),  "ITA": (41.9, 12.6),   "JAM": (18.1, -77.3),
    "JPN": (36.2, 138.3), "JOR": (30.6, 36.2),   "KAZ": (48.0, 66.9),
    "KEN": (0.0, 37.9),   "KIR": (1.3, 173.0),   "PRK": (40.3, 127.5),
    "KOR": (35.9, 127.8), "KWT": (29.3, 47.5),   "KGZ": (41.2, 74.8),
    "LAO": (17.9, 102.5), "LVA": (56.9, 24.6),   "LBN": (33.9, 35.9),
    "LSO": (-29.6, 28.2), "LBR": (6.4, -9.4),    "LBY": (26.3, 17.2),
    "LIE": (47.2, 9.6),   "LTU": (55.2, 24.0),   "LUX": (49.8, 6.1),
    "MDG": (-18.8, 46.9), "MWI": (-13.3, 34.3),  "MYS": (2.5, 109.5),
    "MDV": (3.2, 73.2),   "MLI": (17.6, -4.0),   "MLT": (35.9, 14.4),
    "MHL": (7.1, 171.2),  "MRT": (21.0, -10.9),  "MUS": (-20.3, 57.6),
    "MEX": (23.6, -102.6), "FSM": (7.4, 150.6),  "MDA": (47.4, 28.4),
    "MCO": (43.7, 7.4),   "MNG": (46.9, 103.8),  "MNE": (42.7, 19.4),
    "MAR": (31.8, -7.1),  "MOZ": (-18.7, 35.5),  "MMR": (17.1, 96.9),
    "NAM": (-22.0, 17.1), "NRU": (-0.5, 166.9),  "NPL": (28.4, 84.1),
    "NLD": (52.1, 5.3),   "NZL": (-40.9, 174.9), "NIC": (12.9, -85.2),
    "NER": (17.6, 8.1),   "NGA": (9.1, 8.7),     "MKD": (41.6, 21.7),
    "NOR": (60.5, 8.5),   "OMN": (21.5, 55.9),   "PAK": (30.4, 69.3),
    "PLW": (7.5, 134.6),  "PSE": (31.9, 35.3),   "PAN": (8.5, -80.8),
    "PNG": (-6.3, 143.9), "PRY": (-23.4, -58.4), "PER": (-9.2, -75.0),
    "PHL": (12.9, 121.8), "POL": (51.9, 19.1),   "PRT": (39.4, -8.2),
    "QAT": (25.4, 51.2),  "ROU": (45.9, 24.9),   "RUS": (61.5, 105.3),
    "RWA": (-1.9, 29.9),  "KNA": (17.4, -62.8),  "LCA": (13.9, -60.9),
    "VCT": (13.3, -61.2), "WSM": (-13.8, -172.1), "SMR": (43.9, 12.5),
    "STP": (0.2, 6.6),    "SAU": (23.9, 45.1),   "SEN": (14.5, -14.5),
    "SRB": (44.0, 21.0),  "SYC": (-4.7, 55.5),   "SLE": (8.5, -11.8),
    "SGP": (1.4, 103.8),  "SVK": (48.7, 19.7),   "SVN": (46.1, 14.8),
    "SLB": (-9.6, 160.2), "SOM": (5.2, 46.2),    "ZAF": (-30.6, 22.9),
    "SSD": (6.9, 31.3),   "ESP": (40.5, -3.7),   "LKA": (7.9, 80.8),
    "SDN": (12.9, 30.2),  "SUR": (3.9, -56.0),   "SWE": (60.1, 18.6),
    "CHE": (46.8, 8.2),   "SYR": (34.8, 38.9),   "TWN": (23.7, 121.0),
    "TJK": (38.9, 71.3),  "TZA": (-6.4, 34.9),   "THA": (15.9, 100.9),
    "TLS": (-8.9, 125.7), "TGO": (8.6, 0.8),     "TON": (-21.2, -175.2),
    "TTO": (10.7, -61.2), "TUN": (34.0, 9.0),    "TUR": (38.9, 35.2),
    "TKM": (38.1, 57.0),  "TUV": (-7.5, 179.2),  "UGA": (1.4, 32.3),
    "UKR": (48.4, 31.2),  "ARE": (23.4, 53.8),   "GBR": (55.4, -3.4),
    "USA": (37.1, -95.7), "URY": (-32.5, -55.8), "UZB": (41.4, 64.6),
    "VUT": (-15.4, 166.9), "VEN": (6.4, -66.6),  "VNM": (14.1, 108.3),
    "YEM": (15.6, 48.5),  "ZMB": (-13.1, 27.8),  "ZWE": (-19.0, 29.2),
}


def geo_weight(distance_km: float) -> float:
    """Geographic proximity weight: exp(-distance_km / 2000).

    Args:
        distance_km: Great-circle distance between country centroids.

    Returns:
        Value in (0, 1]; 1.0 at distance 0, ~0.37 at 2000 km.
    """
    return math.exp(-distance_km / GEO_DECAY_KM)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points (km)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(min(a, 1.0)))


def load_geo_distances() -> pd.DataFrame:
    """Compute pairwise great-circle distances between all country centroids.

    Returns:
        DataFrame with columns [iso3_i, iso3_j, distance_km].
        Excludes self-pairs (iso3_i == iso3_j).
    """
    countries = list(_CENTROIDS.keys())
    rows: list[dict] = []
    for iso3_i in countries:
        lat1, lon1 = _CENTROIDS[iso3_i]
        for iso3_j in countries:
            if iso3_i == iso3_j:
                continue
            lat2, lon2 = _CENTROIDS[iso3_j]
            rows.append({
                "iso3_i": iso3_i,
                "iso3_j": iso3_j,
                "distance_km": _haversine_km(lat1, lon1, lat2, lon2),
            })
    return pd.DataFrame(rows)


def build_dyadic_weights(
    dyadic: pd.DataFrame,
    window_days: int = 30,
) -> pd.DataFrame:
    """Normalise dyadic event volumes to contagion weights.

    For each target country, the weights across all source countries sum to 1.

    Args:
        dyadic: Output of pipeline/signals/dyadic.build_dyadic_tensor().
        window_days: Restrict to the most recent N days of data.

    Returns:
        DataFrame [source_iso3, target_iso3, w_dyad] where w_dyad sums to 1
        per target_iso3.
    """
    df = dyadic.copy()
    df["date"] = pd.to_datetime(df["date"])

    if df.empty:
        return pd.DataFrame(columns=["source_iso3", "target_iso3", "w_dyad"])

    cutoff = df["date"].max() - pd.Timedelta(days=window_days)
    recent = df[df["date"] >= cutoff]

    agg = (
        recent.groupby(["source_iso3", "target_iso3"])["event_count"]
        .sum()
        .reset_index()
        .rename(columns={"event_count": "volume"})
    )

    target_totals = agg.groupby("target_iso3")["volume"].transform("sum")
    agg["w_dyad"] = agg["volume"] / target_totals.clip(lower=1)

    return agg[["source_iso3", "target_iso3", "w_dyad"]].copy()


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
        Series indexed by iso3 with contagion scores.
        0.0 for countries with no weighted neighbours.
    """
    # Build fast lookup dicts
    geo_lookup: dict[tuple[str, str], float] = {
        (row["iso3_i"], row["iso3_j"]): row["distance_km"]
        for _, row in geo_distances.iterrows()
    }
    dyad_lookup: dict[tuple[str, str], float] = {
        (row["source_iso3"], row["target_iso3"]): row["w_dyad"]
        for _, row in dyadic_weights.iterrows()
    }

    results: dict[str, float] = {}
    countries = list(instability.index)

    for iso3_i in countries:
        weighted_sum = 0.0
        weight_total = 0.0

        for iso3_j in countries:
            if iso3_j == iso3_i:
                continue

            # geo distance: try (i,j) then (j,i) (matrix is symmetric)
            dist = geo_lookup.get((iso3_i, iso3_j)) or geo_lookup.get((iso3_j, iso3_i))
            if dist is None:
                continue

            w_g = geo_weight(dist)
            w_d = dyad_lookup.get((iso3_j, iso3_i), 0.0)

            combined = w_g * w_d
            inst_j = float(instability.get(iso3_j, 0.0))

            weighted_sum += combined * inst_j
            weight_total += combined

        results[iso3_i] = weighted_sum / weight_total if weight_total > 0.0 else 0.0

    return pd.Series(results)
