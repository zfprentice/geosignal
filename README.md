# GeoSignal

**Global geopolitical signal monitor.** Scores ~180 countries weekly on a forward-looking Watchlist Index built from GDELT event records and public macro indicators.

→ [geosignal.xyz](https://geosignal.xyz) · [Subscribe to the Monday briefing](https://substack.com)

## What it does

Each week, GeoSignal identifies which countries are moving anomalously — not just "there is conflict", but "conflict events are 3σ above that country's own baseline and trending upward". The signals are deterministic, auditable, and documented in the [methodology](/docs/methodology.html).

## Pages

| URL | Description |
|---|---|
| `/` | Signals feed — top 5-10 anomalies of the past 7 days |
| `/globe` | 3D globe coloured by Watchlist Index |
| `/country/:iso3` | Country detail: full time series, CAMEO breakdown, dyadic context |
| `/matrix` | Dyadic heatmap — who is acting on whom, and how |
| `/backtest` | Historical validation: did the model flag known events before they happened? |
| `/methodology` | Every formula, every weight, every data source |

## Data sources

All free and reproducible: GDELT 2.0, ACLED, World Bank WDI, IMF WEO, FRED. Prose briefs via Gemini 1.5 Flash (Gemini never assigns scores).

## Build

See [`geosignal-v2-spec.md`](geosignal-v2-spec.md) for the full engineering specification.

```bash
pip install -r requirements.txt
python pipeline/sources/gdelt_doc.py        # fetch headlines
python pipeline/scoring/watchlist.py        # compute index
pytest pipeline/tests/                      # run unit tests
```

## Automation

Four GitHub Actions workflows: hourly (headlines), daily 06:00 UTC (full recompute), weekly Mon 06:30 UTC (clustering + Substack draft), manual (backtest).
