"""
World Bank WDI — governance and macro indicators fetcher.

Fetches annual snapshots of World Bank World Development Indicators used
in the structural Fragility layer of the Watchlist Index.

No API key required — the World Bank API is public.

Spec reference: §2.1 (World Bank WDI, annual snapshot).
                §2.3 Fragility component.

API docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/898599

Indicators fetched:
    PV.EST  → stability     (Political Stability & Absence of Violence, WGI)
    VA.EST  → voice         (Voice & Accountability, WGI)
    RL.EST  → rule_of_law   (Rule of Law, WGI)
    NY.GDP.PCAP.CD → gdp_pc (GDP per capita, current USD)
    GC.DOD.TOTL.GD.ZS → debt_gdp (Central government debt, % of GDP)

Pagination: WB API returns 50 rows/page by default; this module paginates
automatically using per_page=500 to minimise round-trips.

Output schema:
    iso3 (str), year (int),
    stability, voice, rule_of_law (float, WGI estimate scale ~-2.5 to +2.5),
    gdp_pc (float, USD), debt_gdp (float, %)

Standalone usage:
    python pipeline/sources/worldbank.py [--year 2023]
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

WB_API_BASE = "https://api.worldbank.org/v2"
REQUEST_TIMEOUT = 30
BATCH_SIZE = 30  # countries per request (WB supports semicolon-delimited batches)

INDICATORS: dict[str, str] = {
    "PV.EST": "stability",
    "VA.EST": "voice",
    "RL.EST": "rule_of_law",
    "NY.GDP.PCAP.CD": "gdp_pc",
    "GC.DOD.TOTL.GD.ZS": "debt_gdp",
}

OUTPUT_COLUMNS = ["iso3", "year", "stability", "voice", "rule_of_law", "gdp_pc", "debt_gdp"]

# Canonical universe of ~180 countries (ISO3 codes) that we monitor.
# Used for batched WB queries instead of the unstable country/all endpoint.
COUNTRY_UNIVERSE = [
    "AFG","ALB","DZA","AND","AGO","ATG","ARG","ARM","AUS","AUT","AZE","BHS","BHR",
    "BGD","BRB","BLR","BEL","BLZ","BEN","BTN","BOL","BIH","BWA","BRA","BRN","BGR",
    "BFA","BDI","CPV","KHM","CMR","CAN","CAF","TCD","CHL","CHN","COL","COM","COD",
    "COG","CRI","CIV","HRV","CUB","CYP","CZE","DNK","DJI","DMA","DOM","ECU","EGY",
    "SLV","GNQ","ERI","EST","SWZ","ETH","FJI","FIN","FRA","GAB","GMB","GEO","DEU",
    "GHA","GRC","GRD","GTM","GIN","GNB","GUY","HTI","HND","HUN","ISL","IND","IDN",
    "IRN","IRQ","IRL","ISR","ITA","JAM","JPN","JOR","KAZ","KEN","KIR","PRK","KOR",
    "KWT","KGZ","LAO","LVA","LBN","LSO","LBR","LBY","LIE","LTU","LUX","MDG","MWI",
    "MYS","MDV","MLI","MLT","MHL","MRT","MUS","MEX","FSM","MDA","MCO","MNG","MNE",
    "MAR","MOZ","MMR","NAM","NRU","NPL","NLD","NZL","NIC","NER","NGA","MKD","NOR",
    "OMN","PAK","PLW","PSE","PAN","PNG","PRY","PER","PHL","POL","PRT","QAT","ROU",
    "RUS","RWA","KNA","LCA","VCT","WSM","SMR","STP","SAU","SEN","SRB","SYC","SLE",
    "SGP","SVK","SVN","SLB","SOM","ZAF","SSD","ESP","LKA","SDN","SUR","SWE","CHE",
    "SYR","TWN","TJK","TZA","THA","TLS","TGO","TON","TTO","TUN","TUR","TKM","TUV",
    "UGA","UKR","ARE","GBR","USA","URY","UZB","VUT","VEN","VNM","YEM","ZMB","ZWE",
]


def _fetch_indicator(indicator_code: str, year: Optional[int] = None) -> pd.DataFrame:
    """Fetch one WB indicator for all COUNTRY_UNIVERSE countries.

    Uses batched requests (BATCH_SIZE countries per call) rather than the
    unstable country/all bulk endpoint.

    Args:
        indicator_code: WB indicator ID (e.g. 'PV.EST').
        year: Specific year.  None fetches mrv=1 (most recent value).

    Returns:
        DataFrame with columns: iso3, year, value.
    """
    all_rows: list[dict] = []

    for i in range(0, len(COUNTRY_UNIVERSE), BATCH_SIZE):
        batch = COUNTRY_UNIVERSE[i : i + BATCH_SIZE]
        batch_str = ";".join(batch)
        url = f"{WB_API_BASE}/country/{batch_str}/indicator/{indicator_code}"
        params: dict = {"format": "json", "per_page": BATCH_SIZE + 5}
        if year:
            params["date"] = str(year)
        else:
            params["mrv"] = 1

        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            print(f"  WB API error for {indicator_code} batch {i//BATCH_SIZE+1}: {exc}")
            continue

        if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
            continue

        all_rows.extend(payload[1])

    if not all_rows:
        return pd.DataFrame(columns=["iso3", "year", "value"])

    df = pd.DataFrame(all_rows)
    df = df.rename(columns={"countryiso3code": "iso3", "date": "year"})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df = df[df["iso3"].str.len() == 3].dropna(subset=["iso3", "value"])

    return df[["iso3", "year", "value"]].copy()


def fetch(countries: list[str] | None = None, year: Optional[int] = None) -> pd.DataFrame:
    """Fetch all WDI indicators and merge into a single wide DataFrame.

    Args:
        countries: Optional list of ISO3 codes to filter to.
                   None returns all countries.
        year: Year to fetch.  None uses the most recent available value
              for each indicator (years may differ slightly across indicators).

    Returns:
        DataFrame with OUTPUT_COLUMNS schema.
    """
    frames: dict[str, pd.DataFrame] = {}

    for wb_code, col_name in INDICATORS.items():
        print(f"  Fetching WB indicator {wb_code} ({col_name}) …")
        df = _fetch_indicator(wb_code, year=year)
        df = df.rename(columns={"value": col_name})
        frames[col_name] = df

    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    # merge all indicators on iso3+year using outer join (some indicators
    # have different coverage; NaN means data unavailable for that country)
    merged = None
    for col_name, df in frames.items():
        if merged is None:
            merged = df.rename(columns={col_name: col_name})
        else:
            merged = merged.merge(
                df[["iso3", col_name]],
                on="iso3",
                how="outer",
            )

    assert merged is not None
    merged["year"] = merged["year"].fillna(year or datetime.utcnow().year - 1)

    if countries:
        merged = merged[merged["iso3"].isin(countries)]

    # ensure all output columns are present
    for col in OUTPUT_COLUMNS:
        if col not in merged.columns:
            merged[col] = float("nan")

    return merged[OUTPUT_COLUMNS].copy()


def write_snapshot(df: pd.DataFrame, out_dir: Path = Path("hist")) -> Path:
    """Write WDI snapshot to parquet.

    Args:
        df: Output of fetch().
        out_dir: Directory for output.

    Returns:
        Path to written file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out = out_dir / f"worldbank-{today}.parquet"
    df.to_parquet(out, index=False)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch World Bank WDI indicators")
    parser.add_argument("--year", type=int, default=None, help="Year (default: most recent)")
    parser.add_argument("--out-dir", default="hist")
    args = parser.parse_args()

    df = fetch(year=args.year)
    path = write_snapshot(df, Path(args.out_dir))
    print(f"Wrote {len(df)} rows to {path}")
    print(df.describe())
