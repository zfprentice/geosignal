"""
IMF WEO — World Economic Outlook macro indicators fetcher.

Fetches semi-annual IMF World Economic Outlook data via the IMF DataMapper
API.  No API key required.

Spec reference: §2.1 (IMF WEO, semi-annual, free).
                §2.3 Fragility component.

API docs: https://www.imf.org/external/datamapper/api/help
Base URL: https://www.imf.org/external/datamapper/api/v1/

Indicators fetched:
    PCPIPCH       → inflation_cpi       (Consumer prices, % change)
    GGXCNL_NGDP  → fiscal_balance_gdp  (Govt net lending/borrowing, % GDP)
    BCA_NGDPD    → current_account_gdp (Current account balance, % GDP)

The DataMapper API uses ISO3-like codes for most countries but includes
some IMF-internal group codes (e.g., ADVEC, OEMDC) which are filtered out.

Response JSON shape:
    {
        "values": {
            "PCPIPCH": {
                "USA": {"2022": 8.0, "2023": 4.1, "2024": 2.9},
                ...
            }
        }
    }

Output schema:
    iso3 (str), year (int), edition (str, e.g. "2025-Apr"),
    inflation_cpi (float), fiscal_balance_gdp (float), current_account_gdp (float)

Standalone usage:
    python pipeline/sources/imf.py [--year 2025]
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

IMF_BASE = "https://www.imf.org/external/datamapper/api/v1"
REQUEST_TIMEOUT = 60

INDICATORS: dict[str, str] = {
    "PCPIPCH": "inflation_cpi",
    "GGXCNL_NGDP": "fiscal_balance_gdp",
    "BCA_NGDPD": "current_account_gdp",
}

OUTPUT_COLUMNS = [
    "iso3", "year", "edition",
    "inflation_cpi", "fiscal_balance_gdp", "current_account_gdp",
]

# IMF uses ISO3 for most countries but includes non-country group codes.
# Real ISO3 codes are 3 uppercase letters; IMF group codes include digits
# or are longer.  We filter to 3-letter alphabetic codes only.


def _is_country_code(code: str) -> bool:
    return len(code) == 3 and code.isalpha()


def _fetch_indicator(indicator: str, year: int) -> pd.DataFrame:
    """Fetch one IMF indicator for all countries for a given year.

    Args:
        indicator: IMF indicator code (e.g. 'PCPIPCH').
        year: Year to fetch data for.

    Returns:
        DataFrame with columns: iso3, year, value.
    """
    url = f"{IMF_BASE}/{indicator}"
    params = {"periods": str(year)}

    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"  IMF API error for {indicator}: {exc}")
        return pd.DataFrame(columns=["iso3", "year", "value"])

    country_series = data.get("values", {}).get(indicator, {})
    rows = []
    for country_code, yearly in country_series.items():
        if not _is_country_code(country_code):
            continue  # skip IMF group aggregates
        value = yearly.get(str(year))
        if value is None:
            # try adjacent year if the requested one has no data
            for offset in [1, -1, 2, -2]:
                value = yearly.get(str(year + offset))
                if value is not None:
                    break
        if value is not None:
            rows.append({"iso3": country_code, "year": year, "value": float(value)})

    return pd.DataFrame(rows, columns=["iso3", "year", "value"])


def fetch(year: Optional[int] = None) -> pd.DataFrame:
    """Fetch all IMF WEO indicators for all countries.

    Args:
        year: WEO projection year.  Defaults to current year.

    Returns:
        DataFrame with OUTPUT_COLUMNS schema.
    """
    if year is None:
        year = datetime.utcnow().year

    # Edition string: e.g. "2025-Apr" for the April WEO
    month = datetime.utcnow().month
    edition_month = "Apr" if month <= 9 else "Oct"
    edition = f"{year}-{edition_month}"

    frames: dict[str, pd.DataFrame] = {}
    for imf_code, col_name in INDICATORS.items():
        print(f"  Fetching IMF {imf_code} ({col_name}) for {year} …")
        df = _fetch_indicator(imf_code, year=year)
        df = df.rename(columns={"value": col_name})
        frames[col_name] = df.set_index("iso3")

    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    # align on iso3
    all_iso3 = set()
    for df in frames.values():
        all_iso3 |= set(df.index)

    rows = []
    for iso3 in sorted(all_iso3):
        row: dict = {"iso3": iso3, "year": year, "edition": edition}
        for col_name, df in frames.items():
            row[col_name] = df.at[iso3, col_name] if iso3 in df.index else float("nan")
        rows.append(row)

    result = pd.DataFrame(rows)
    for col in OUTPUT_COLUMNS:
        if col not in result.columns:
            result[col] = float("nan")
    return result[OUTPUT_COLUMNS].copy()


def write_snapshot(df: pd.DataFrame, out_dir: Path = Path("hist")) -> Path:
    """Write IMF snapshot to parquet.

    Args:
        df: Output of fetch().
        out_dir: Directory for output.

    Returns:
        Path to written file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out = out_dir / f"imf-{today}.parquet"
    df.to_parquet(out, index=False)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch IMF WEO indicators")
    parser.add_argument("--year", type=int, default=None, help="Projection year (default: current)")
    parser.add_argument("--out-dir", default="hist")
    args = parser.parse_args()

    df = fetch(year=args.year)
    path = write_snapshot(df, Path(args.out_dir))
    print(f"Wrote {len(df)} rows to {path}")
    print(df.head(10).to_string())
