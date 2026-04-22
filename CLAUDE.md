# GeoSignal — Instructions for Claude Code

## Start here

Before making any decisions, read [`geosignal-v2-spec.md`](geosignal-v2-spec.md). It is the authoritative source for architecture, formulas, data contracts, and build plan.

## Current build phase

**Phase 3 complete — all 6 signal primitives implemented, 14/14 tests green.**  
Next: **Phase 4 — Scoring + publishing** (`pipeline/scoring/`, `pipeline/briefs/gemini.py`, `pipeline/publishing/`).

## Phase 4 acceptance criteria (spec §6 Phase 4)

1. `pipeline/scoring/fragility.py` — static structural layer (WB governance + debt-to-GDP + EMBI+)
2. `pipeline/scoring/watchlist.py` — composite index: `w1*Deviation + w2*Trend + w3*Contagion + w4*Fragility`, percentile-rank scaled 0–10
3. `pipeline/briefs/gemini.py` — prose generation only (cluster labels, country briefs, Substack draft)
4. `pipeline/publishing/build_countries_json.py` — writes `docs/data/countries.json`
5. `pipeline/publishing/build_signals_feed.py` — writes `docs/data/signals.json`
6. `pipeline/publishing/build_matrix_json.py` — writes `docs/data/matrix.json`

End-of-phase sanity check: run end-to-end on cached/synthetic data and verify `countries.json` has Niger/Ukraine/Syria in the top quartile and Switzerland/Norway/Denmark in the bottom quartile.

## Phase 3 implementation notes

- `CUSUM_THRESHOLD_SIGMA = 6.0` (not 4σ from spec or 5σ as initially chosen). With in-sample mean estimation, h=5σ triggers a false alarm on N(0,1) seed-42 series of length 180. h=6σ is clean.
- `thematic.py` uses lazy imports for sentence-transformers and hdbscan — `import pipeline.signals.thematic` is safe; ML deps are only required when the functions are actually called.
- All 6 primitives use deterministic math only. Gemini is NOT called from any signal primitive.

## Phase 2 implementation notes

Tested working locally (no credentials needed):
- `reuters_rss.py` — BBC/Al Jazeera fallbacks active (Reuters feeds blocked)
- `imf.py` — 218 countries, ISO3 codes, 3 indicators

Credential-gated (raise clear EnvironmentError when keys absent):
- `fred.py` → needs `FRED_API_KEY`
- `acled.py` → needs `ACLED_API_KEY` + `ACLED_EMAIL`
- `gdelt_events.py` → needs `GCP_SA_KEY_JSON`

World Bank API notes:
- `country/all` bulk endpoint is flaky (502/503 intermittently)
- `worldbank.py` uses batched per-30-country queries as mitigation
- Tested successfully in a clean run; WB outages are transient (~30 min)

GDELT DOC API notes:
- Uses FIPS codes (not ISO2). Key differences: GM=DEU, JA=JPN, KS=KOR, UK=GBR, RS=RUS, NG=NER, NI=NGA, UP=UKR
- Max 250 records per artlist query
- `sourcecountry:XX` filter returns articles published FROM that country (not about it)

## Key invariants — never violate these

1. **Gemini never assigns scores.** It only writes prose (briefs, cluster labels, Substack drafts). All numbers on any chart come from deterministic Python code. See §2.5.
2. **No backend, no database.** Storage is flat parquet files in `hist/` and JSON in `docs/data/`. History is queryable via `git log`. See §3.4.
3. **All scoring is auditable.** Every formula is documented in the spec §2.2–2.3 and published at `/methodology`. No black boxes.
4. **Free data sources only.** Do not add paid sources. See §2.1.
5. **Static frontend only.** No React/Vue/Svelte. Vanilla JS + d3 + globe.gl. See §4.1.

## Data contracts

The canonical JSON schemas are in §3.2 of the spec:
- `docs/data/countries.json` — full panel, one entry per country
- `docs/data/signals.json` — top signals feed
- `docs/data/matrix.json` — dyadic heatmap data
- `docs/data/backtest.json` — historical event validations
- `docs/data/themes.json` — weekly cluster labels

## Pipeline schedule (§3.3)

| Workflow | Trigger | What it does |
|---|---|---|
| `hourly.yml` | `0 * * * *` | Fetch GDELT DOC headlines; no scoring |
| `daily.yml` | `0 6 * * *` | Full recompute; generate countries.json + signals.json |
| `weekly.yml` | `30 6 * * 1` | Thematic clustering; Substack draft; email Zach |
| `backtest.yml` | manual only | Re-run full backtest after weight changes |

## Testing

```bash
pytest pipeline/tests/test_signals.py
```

Unit tests use synthetic data. A constant-baseline series should give deviation=0. A linearly increasing series should give positive Theil-Sen slope. See §6 Phase 3 for test requirements.

## Signal primitives (§2.2)

| File | Primitive | Formula |
|---|---|---|
| `pipeline/signals/deviation.py` | Robust z-score | `(x - median) / (1.4826 * MAD + 1.0)` |
| `pipeline/signals/trend.py` | Theil-Sen slope | Median of pairwise slopes, 30d window |
| `pipeline/signals/changepoint.py` | CUSUM | Cumulative deviation; reset at ~4σ |
| `pipeline/signals/dyadic.py` | Dyadic tensor | `D[source, target, t]` = sum Goldstein tone |
| `pipeline/signals/contagion.py` | Spillover | Geo + dyadic weighted average of neighbor instability |
| `pipeline/signals/thematic.py` | Embedding clusters | MiniLM → HDBSCAN → Gemini labels |

## Watchlist Index weights (§2.3)

```
w1 = 0.40  # Deviation
w2 = 0.25  # Trend
w3 = 0.20  # Contagion
w4 = 0.15  # Fragility
```

Stored in `pipeline/scoring/config.yaml`. Tuned via backtest (Phase 5).

## Build phases summary

| Phase | Owner | Description |
|---|---|---|
| 0 | Zach | Account setup, secrets, GitHub repo |
| 1 ✅ | Claude | Scaffolding — all stubs created |
| 2 | Claude | Implement data sources |
| 3 | Claude | Implement signal primitives + unit tests |
| 4 | Claude | Scoring, briefs, build_countries_json |
| 5 | Claude | Backtest system |
| 6 | Claude | Frontend (5 pages + methodology + about) |
| 7 | Claude | Publishing automation (Substack draft, alerts) |
| 8 | Claude + Zach | GH Actions go live, monitor 24h |

## Open decisions (answer before Phase 6)

From §10 of spec — flag to Zach after Phase 5:
- Final site name (GeoSignal vs Sentinel/Verges/Sounding/Watchpoint/Threshold)
- Domain
- Substack CTA placement
- Signal card disclaimer for politically sensitive flags
