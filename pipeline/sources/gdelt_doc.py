"""
GDELT 2.0 DOC API — article headline fetcher.

Fetches article metadata (title, URL, source country, tone) using the
GDELT Document API.  No API key required; the API is public.

IMPORTANT — country codes: GDELT uses FIPS 10-4 two-letter codes, which
differ from ISO2 for many countries (e.g., Germany = GM not DE, Russia = RS
not RU, Japan = JA not JP, South Korea = KS not KR).  See FIPS_TO_ISO3.

API limits: max 250 records per artlist query.  Rate-limit is undocumented;
0.5 s sleep between country requests keeps us safe in practice.

Tone field: -100 to +100 sentiment score (NOT Goldstein scale, which lives
in the CAMEO events from gdelt_events.py).

Spec reference: §2.1 (GDELT 2.0 DOC API, hourly cadence).

Output schema:
    url, title, domain, language, seendate (datetime),
    sourcecountry (FIPS str), tone (float), themes (str),
    fetched_at (datetime), iso3 (str)

Standalone usage:
    python pipeline/sources/gdelt_doc.py [--window 7d|30d] [--country NER]
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

GDELT_DOC_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
RATE_LIMIT_SLEEP = 0.5  # seconds between requests
REQUEST_TIMEOUT = 30    # seconds

# FIPS 10-4 → ISO3.  Covers ~180 countries.  Many FIPS codes differ from ISO2.
FIPS_TO_ISO3: dict[str, str] = {
    "AF": "AFG", "AL": "ALB", "AG": "DZA", "AN": "AND", "AO": "AGO",
    "AC": "ATG", "AR": "ARG", "AM": "ARM", "AS": "AUS", "AU": "AUT",
    "AJ": "AZE", "BF": "BHS", "BA": "BHR", "BG": "BGD", "BB": "BRB",
    "BO": "BLR", "BE": "BEL", "BH": "BLZ", "BN": "BEN", "BT": "BTN",
    "BL": "BOL", "BK": "BIH", "BC": "BWA", "BR": "BRA", "BX": "BRN",
    "BU": "BGR", "UV": "BFA", "BY": "BDI", "CB": "KHM", "CM": "CMR",
    "CA": "CAN", "CV": "CPV", "CT": "CAF", "CD": "TCD", "CI": "CHL",
    "CH": "CHN", "CO": "COL", "CN": "COM", "CF": "COD", "CG": "COG",
    "CS": "CRI", "IV": "CIV", "HR": "HRV", "CU": "CUB", "CY": "CYP",
    "EZ": "CZE", "DA": "DNK", "DJ": "DJI", "DO": "DMA", "DR": "DOM",
    "EC": "ECU", "EG": "EGY", "ES": "SLV", "EK": "GNQ", "ER": "ERI",
    "EN": "EST", "WZ": "SWZ", "ET": "ETH", "FJ": "FJI", "FI": "FIN",
    "FR": "FRA", "GB": "GAB", "GA": "GMB", "GG": "GEO", "GM": "DEU",
    "GH": "GHA", "GR": "GRC", "GJ": "GRD", "GT": "GTM", "GV": "GIN",
    "PU": "GNB", "GY": "GUY", "HA": "HTI", "HO": "HND", "HU": "HUN",
    "IC": "ISL", "IN": "IND", "ID": "IDN", "IR": "IRN", "IZ": "IRQ",
    "EI": "IRL", "IS": "ISR", "IT": "ITA", "JM": "JAM", "JA": "JPN",
    "JO": "JOR", "KZ": "KAZ", "KE": "KEN", "KR": "KIR", "KN": "PRK",
    "KS": "KOR", "KU": "KWT", "KG": "KGZ", "LA": "LAO", "LG": "LVA",
    "LE": "LBN", "LT": "LSO", "LI": "LBR", "LY": "LBY", "LS": "LIE",
    "LH": "LTU", "LU": "LUX", "MA": "MDG", "MI": "MWI", "MY": "MYS",
    "MV": "MDV", "ML": "MLI", "MT": "MLT", "RM": "MHL", "MR": "MRT",
    "MP": "MUS", "MX": "MEX", "FM": "FSM", "MD": "MDA", "MN": "MCO",
    "MG": "MNG", "MJ": "MNE", "MO": "MAR", "MZ": "MOZ", "BM": "MMR",
    "WA": "NAM", "NR": "NRU", "NP": "NPL", "NL": "NLD", "NZ": "NZL",
    "NU": "NIC", "NG": "NER", "NI": "NGA", "MK": "MKD", "NO": "NOR",
    "MU": "OMN", "PK": "PAK", "PS": "PLW", "PM": "PSE", "PA": "PAN",
    "PP": "PNG", "PG": "PRY", "PE": "PER", "RP": "PHL", "PL": "POL",
    "PO": "PRT", "QA": "QAT", "RO": "ROU", "RS": "RUS", "RW": "RWA",
    "SC": "KNA", "ST": "LCA", "VC": "VCT", "WS": "WSM", "SM": "SMR",
    "TP": "STP", "SA": "SAU", "SG": "SEN", "RI": "SRB", "SE": "SYC",
    "SL": "SLE", "SN": "SGP", "LO": "SVK", "SI": "SVN", "BP": "SLB",
    "SO": "SOM", "SF": "ZAF", "OD": "SSD", "SP": "ESP", "CE": "LKA",
    "SU": "SDN", "NS": "SUR", "SW": "SWE", "SZ": "CHE", "SY": "SYR",
    "TW": "TWN", "TI": "TJK", "TZ": "TZA", "TH": "THA", "TT": "TLS",
    "TO": "TGO", "TN": "TON", "TD": "TTO", "TS": "TUN", "TU": "TUR",
    "TX": "TKM", "TV": "TUV", "UG": "UGA", "UP": "UKR", "AE": "ARE",
    "UK": "GBR", "US": "USA", "UY": "URY", "UZ": "UZB", "NH": "VUT",
    "VE": "VEN", "VM": "VNM", "YM": "YEM", "ZA": "ZMB", "ZI": "ZWE",
}

# Reverse map: ISO3 → FIPS for building queries by ISO3
ISO3_TO_FIPS: dict[str, str] = {v: k for k, v in FIPS_TO_ISO3.items()}

ARTICLE_COLUMNS = [
    "url", "title", "domain", "language", "seendate",
    "sourcecountry", "tone", "themes", "fetched_at", "iso3",
]


def fetch(
    country_fips: Optional[str] = None,
    window: str = "7d",
    max_records: int = 250,
) -> pd.DataFrame:
    """Fetch article headlines from the GDELT 2.0 DOC API.

    Args:
        country_fips: FIPS 2-letter country code to filter by source country.
                      None fetches global headlines (no country filter).
        window: Lookback window — '7d', '30d', '1h', '24h', etc.
        max_records: Maximum records per call (API hard cap: 250).

    Returns:
        DataFrame with columns: url, title, domain, language, seendate,
        sourcecountry, tone, themes, fetched_at, iso3.
        Empty DataFrame if the API returns no results.
    """
    params: dict = {
        "mode": "artlist",
        "format": "json",
        "timespan": window,
        "maxrecords": min(max_records, 250),
        "sort": "hybridrel",
    }
    if country_fips:
        params["query"] = f"sourcecountry:{country_fips}"
    else:
        params["query"] = ""

    try:
        resp = requests.get(GDELT_DOC_BASE, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            print(f"  Rate limited for {country_fips}; sleeping 5s")
            time.sleep(5)
            return pd.DataFrame(columns=ARTICLE_COLUMNS)
        print(f"  HTTP error for {country_fips}: {exc}")
        return pd.DataFrame(columns=ARTICLE_COLUMNS)
    except Exception as exc:
        print(f"  Error fetching {country_fips}: {exc}")
        return pd.DataFrame(columns=ARTICLE_COLUMNS)

    articles = data.get("articles") or []
    if not articles:
        return pd.DataFrame(columns=ARTICLE_COLUMNS)

    df = pd.DataFrame(articles)

    # normalise column presence
    for col in ["url", "title", "domain", "language", "seendate",
                "sourcecountry", "tone", "themes"]:
        if col not in df.columns:
            df[col] = None

    df["tone"] = pd.to_numeric(df["tone"], errors="coerce")
    df["seendate"] = pd.to_datetime(df["seendate"], format="%Y%m%dT%H%M%SZ", errors="coerce")
    df["fetched_at"] = datetime.utcnow()
    df["iso3"] = FIPS_TO_ISO3.get(country_fips or "", "") or df["sourcecountry"].map(FIPS_TO_ISO3)

    return df[ARTICLE_COLUMNS].copy()


def fetch_by_iso3(iso3: str, window: str = "7d") -> pd.DataFrame:
    """Fetch headlines for a country identified by ISO3 code.

    Converts ISO3 → FIPS automatically.

    Args:
        iso3: ISO3 country code (e.g., 'NER', 'DEU').
        window: Lookback window.

    Returns:
        DataFrame with ARTICLE_COLUMNS schema.
    """
    fips = ISO3_TO_FIPS.get(iso3)
    if not fips:
        print(f"  No FIPS code for {iso3}; skipping")
        return pd.DataFrame(columns=ARTICLE_COLUMNS)
    return fetch(country_fips=fips, window=window)


def fetch_all_countries(window: str = "7d", delay: float = RATE_LIMIT_SLEEP) -> pd.DataFrame:
    """Fetch headlines for all countries in the FIPS→ISO3 universe.

    Makes one API call per country with a delay between calls.
    At 0.5 s/call × ~180 countries ≈ 90 s total — acceptable for daily runs.

    Args:
        window: Lookback window passed to each fetch() call.
        delay: Seconds to sleep between country requests.

    Returns:
        Concatenated DataFrame with ARTICLE_COLUMNS + iso3 column.
    """
    frames: list[pd.DataFrame] = []
    countries = list(FIPS_TO_ISO3.keys())
    total = len(countries)

    for i, fips in enumerate(countries, 1):
        iso3 = FIPS_TO_ISO3[fips]
        if (i % 20) == 0:
            print(f"  Progress: {i}/{total} countries")
        df = fetch(country_fips=fips, window=window)
        if not df.empty:
            df["iso3"] = iso3
            frames.append(df)
        time.sleep(delay)

    if not frames:
        return pd.DataFrame(columns=ARTICLE_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def save_headlines_cache(df: pd.DataFrame, cache_dir: Path = Path("hist")) -> Path:
    """Write today's headlines to a dated parquet file.

    Args:
        df: DataFrame from fetch() or fetch_all_countries().
        cache_dir: Directory for output.

    Returns:
        Path to the written parquet file.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out = cache_dir / f"gdelt-doc-{today}.parquet"
    df.to_parquet(out, index=False)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch GDELT DOC headlines")
    parser.add_argument("--window", default="7d")
    parser.add_argument(
        "--country", default=None,
        help="ISO3 country code (e.g. NER). Omit for all countries.",
    )
    parser.add_argument("--out-dir", default="hist", help="Output directory")
    args = parser.parse_args()

    if args.country:
        df = fetch_by_iso3(args.country, window=args.window)
    else:
        print("Fetching all countries (this takes ~90 s)…")
        df = fetch_all_countries(window=args.window)

    out = save_headlines_cache(df, Path(args.out_dir))
    print(f"Wrote {len(df)} rows to {out}")
