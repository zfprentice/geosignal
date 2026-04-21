# GeoSignal v2 — Engineering & Product Specification

**Classification**: Owner-facing build spec
**Audience**: Claude Code (build executor) and Zach (reviewer)
**Replaces**: `geopolitics-dashboard-engineering-guide.md` (v1)
**Build model**: Claude-Code-first. Human interventions enumerated in §9.

---

## 0. Strategic brief

GeoSignal is a **global geopolitical signal monitor** that continuously scores ~180 countries on a forward-looking Watchlist Index built from GDELT's event record and public macro indicators. It does the thing MAP doesn't do in-house — systematic quantitative monitoring of slow-building instability — and is positioned as a public portfolio piece attached to a Substack.

The product has three audiences, in priority order:

1. **MAP partners reviewing Zach's application.** They need to see that he can define a signal, estimate it robustly, backtest it, and communicate it. Every design choice optimises for this review.
2. **Substack subscribers.** The site generates the raw material for weekly posts and hosts the charts those posts reference.
3. **General curious readers.** They get a beautiful globe and a clear narrative of what's happening.

**Explicit design rules that follow from this**:

- Scoring is **deterministic and auditable**. Gemini writes prose briefs; Gemini never assigns scores. The formula is published on the site.
- The homepage leads with a **"Signals" feed**, not the globe. The globe is secondary geography; signals are the product.
- A **public backtest page** demonstrates the model flagged known events (Niger 2023, Sudan 2023, Kazakhstan 2022, Myanmar 2021) before mainstream coverage. Without this the project is unfalsifiable.
- Everything is **versioned in git as flat files**. No backend, no database. History is queryable via `git log`.
- The **Substack-draft pipeline** is part of the system, not an afterthought — a weekly GH Action produces a publish-ready draft with figures.

---

## 1. Product specification

### 1.1 Information architecture

The site has five views, all URL-addressable:

1. `/` — **Signals**. Hero page. Top 5-10 anomalies of the past 7 days, each with sparkline, dyadic context, and a one-paragraph auto-generated brief. Like a Bloomberg Terminal's news cut, geopolitical edition.
2. `/globe` — **Globe**. 3D globe coloured by current Watchlist Index. Click a country → detail view.
3. `/country/:iso3` — **Country detail**. Full time series (90d, 1y, 5y), CAMEO breakdown, dyadic partners, thematic exposure, peer comparisons.
4. `/matrix` — **Dyadic matrix**. Interactive heatmap of source-country × target-country tone. Shows US-China, Russia-Europe, Iran-Israel relational dynamics as a grid.
5. `/backtest` — **Backtest validator**. For each of 8-10 pre-selected historical events, shows what the model said at T-30, T-14, T-7, T-0. This is the MAP credibility page.

Plus `/methodology` (explains the formula) and `/about` (Zach's bio + Substack CTA).

### 1.2 The Signals feed — hero specification

Each signal card contains:

- Country name + flag + ISO3
- Watchlist Index value + week-on-week delta (e.g., `6.8 ▲ +1.4`)
- Sparkline — 90-day Watchlist trajectory
- Tag set — thematic frames the anomaly is in (e.g., `coup-risk`, `energy`, `election`)
- One-paragraph auto-generated brief (Gemini, given deterministic inputs)
- "Primary dyadic counterparty" — the country directing most of the anomalous activity
- Timestamp of last update

Ranking logic for which signals appear on the hero page:

```
Score_rank = 0.5 · |z_deviation| + 0.3 · trend_slope + 0.2 · contagion
```

where all three components are z-scored against a 180-country universe. Top 10 by `Score_rank` appear; ties broken by WoW delta.

### 1.3 The backtest page — MAP credibility

For each historical event in the library, show:

- Event label (e.g., "Niger coup, 26 July 2023")
- A chart of the country's Watchlist Index over the 180 days around T-0
- Markers at T-30, T-14, T-7, T-0 with the model's numeric outputs
- A binary: "Did the system flag this >2σ above baseline before T-0?" (true/false)
- Short prose: what signals drove it, what the false-positive history looks like

This page is the single highest-leverage item for MAP credibility. Build it second, after the Signals feed.

Events library (initial, expand over time): Niger coup Jul 2023; Sudan RSF conflict Apr 2023; Kazakhstan protests Jan 2022; Myanmar coup Feb 2021; Russia-Ukraine Feb 2022; Wagner mutiny Jun 2023; October 7 2023; Turkey attempted coup Jul 2016 (stretch — data coverage thinner).

### 1.4 Out of scope (v2)

- User accounts, authentication
- Paywalled content
- Realtime streaming (hourly refresh is enough)
- Mobile-first design (desktop-first; mobile should not break)
- ML models trained on proprietary data (every technique used must be explainable in a paragraph)

---

## 2. Analytical engine

This is the heart of the project. Every component is deterministic, auditable, and implementable in <200 lines of Python. Gemini is used only for natural language (thematic labels, prose briefs).

### 2.1 Data sources

| Source | What we pull | Cadence | Cost |
|---|---|---|---|
| GDELT 2.0 DOC API | Article headlines per country, 7d/30d windows | Hourly | Free |
| GDELT 2.0 Events (GKG) via BigQuery public dataset | CAMEO-coded events, actor-target dyads | Daily | Free (within BQ free tier) |
| ACLED | Conflict events, actor types, fatalities | Weekly | Free (academic) |
| World Bank WDI | GDP, debt-to-GDP, governance indicators | Annual snapshot | Free |
| IMF WEO | Inflation, fiscal balance | Semi-annual | Free |
| FRED | EMBI+ spreads, VIX, commodity prices | Daily | Free |
| Reuters RSS | Headlines for theme clustering | Hourly | Free |
| Gemini 1.5 Flash | Theme labels + prose briefs | Weekly | ~$1/month |

Do **not** add paid sources in v2. The whole point is that this is reproducible.

### 2.2 Core signal primitives

All primitives operate on a country × day panel `X[i, t]` where `i ∈ countries`, `t ∈ days`. The canonical feature vector per country-day is:

```
events_total          # count of GDELT events
tone_mean             # mean Goldstein tone over events
conflict_events       # count of CAMEO 14-20 (material conflict)
cooperation_events    # count of CAMEO 01-07 (verbal + material cooperation)
protest_events        # count of CAMEO 14 (protest)
dyadic_inbound_tone   # mean tone of events where target = i
dyadic_inbound_count  # count of events where target = i
```

Baselines are estimated per `(country, feature)` over a 365-day trailing window.

**Primitive 1 — Robust deviation score**

For each `(country, feature)` at time `t`:

```
median_i = median(X[i, t-365 : t-1])
mad_i    = median(|X[i, t-365 : t-1] - median_i|)
z_robust = (X[i, t] - median_i) / (1.4826 * mad_i + epsilon)
```

Robust z because geopolitical data has heavy tails and occasional outliers (Syria baseline has lots of violence). Using mean/std here would either ignore routine escalations or be dominated by historical extremes. MAD is the standard robust dispersion estimate; 1.4826 makes it consistent with std under normality.

`epsilon = 1.0` prevents division-by-zero for countries with near-zero baselines (Luxembourg, Bhutan).

**Primitive 2 — Trend slope (Theil-Sen)**

For each `(country, feature)` over the last 30 days:

```
slope = theil_sen(X[i, t-30 : t])
```

Theil-Sen (median of pairwise slopes) is the robust cousin of OLS. One absurdly high GDELT day from a breaking story won't dominate the estimate.

**Primitive 3 — Change-point detection (lightweight CUSUM)**

Run a CUSUM on the 180-day series per country. When the cumulative deviation exceeds a threshold (~4σ), flag a regime change and reset. Store the dates of regime changes and display them on country charts.

Useful because it gives the model persistent memory: Syria in 2024 is not "newly anomalous", but Niger in late July 2023 was.

**Primitive 4 — CAMEO dyadic aggregation**

Build the dyadic tensor `D[source, target, t]` = sum of Goldstein tone from events where `source` acted on `target` on day `t`. Aggregate weekly. This powers the matrix view and the "primary counterparty" field on signal cards.

**Primitive 5 — Contagion term**

For each country `i`:

```
contagion_i = Σ_j  (w_geo(i,j) · w_dyad(i,j) · instability_j) / Σ_j (w_geo · w_dyad)
```

where `w_geo = exp(-distance_km / 2000)` and `w_dyad = normalised dyadic event volume over last 30d`. Countries that share borders *and* have dense event dyads contaminate each other; distant uninvolved countries don't.

This captures the Sahel intuition: Niger's 2023 coup was preceded by Mali-Burkina-Guinea contagion well before Niger itself escalated.

**Primitive 6 — Thematic exposure (embedding clustering)**

Once per week:

1. Pull all Reuters/GDELT headlines from the past 7 days.
2. Embed via `sentence-transformers/all-MiniLM-L6-v2` (free, runs in GH Actions in <2 min for 10k headlines).
3. HDBSCAN clustering.
4. For each cluster, send top 5 representative headlines to Gemini with prompt: "give a 2-3 word theme label". Cache these for the week.
5. For each country, its thematic exposure vector = share of its headlines in each cluster.

Powers the tag pills on signal cards and the thematic filters on the globe view.

### 2.3 The Watchlist Index

The final composite that colours the globe and ranks signals:

```
Watchlist_i = w1 · Deviation_i + w2 · Trend_i + w3 · Contagion_i + w4 · Fragility_i
```

where:

- `Deviation_i` = mean of robust z-scores across conflict and protest features, clipped at ±5
- `Trend_i` = normalised 30-day Theil-Sen slope on conflict events
- `Contagion_i` = as above, scaled 0-1
- `Fragility_i` = static structural layer: z-score of composite of World Bank Worldwide Governance Indicators (voice, stability, rule of law), debt-to-GDP, and EMBI+ spread where available. Updated quarterly.

Initial weights (justified in `/methodology`, tuned via backtest in §2.4):

```
w1 = 0.40   # Deviation (what's anomalous now)
w2 = 0.25   # Trend (direction)
w3 = 0.20   # Contagion (neighborhood)
w4 = 0.15   # Fragility (structural)
```

Output is scaled to 0–10 by percentile rank against the universe (so 10 means "most at-risk country this week" rather than an absolute threshold).

### 2.4 Backtest as tuning loop

Before freezing weights, run the model on 2020–2024 historical GDELT and compute, for each of the 8–10 events in §1.3:

- `max_Watchlist` in the 30 days preceding the event
- `percentile_rank` at T-7 globally
- whether the model flagged the country in its top-20 signals at any point in the preceding 60 days

Grid-search `(w1, w2, w3, w4)` over a simplex to maximise average percentile rank at T-7 across the event library. This is the only parameter tuning done; keep it published in the repo as `backtest_results.json`.

Do **not** over-fit. 8 events is too few for confident tuning — keep weights near-uniform and use the backtest as validation, not training.

### 2.5 What Gemini does

Gemini is used for three things, none of which produce numbers:

1. **Cluster labels** — once per week, 30-50 API calls.
2. **Country briefs** — one per country per day, 180 calls. Input includes the deterministic scores + top 5 headlines. Output: 60-word brief.
3. **Weekly Substack draft** — one call per week with the top 10 signals as structured input.

Explicit negative: Gemini never outputs the Watchlist Index, deviation scores, or any other number that appears on a chart.

---

## 3. Data pipeline architecture

### 3.1 Repo layout

```
geosignal/
├── .github/workflows/
│   ├── hourly.yml              # lightweight: GDELT headlines, update briefs
│   ├── daily.yml               # heavy: recompute all signals, regenerate countries.json
│   ├── weekly.yml              # thematic clustering + Substack draft
│   └── backtest.yml            # manual trigger only
├── pipeline/
│   ├── sources/
│   │   ├── gdelt_doc.py        # article headline API
│   │   ├── gdelt_events.py     # BigQuery client for CAMEO events
│   │   ├── acled.py
│   │   ├── worldbank.py
│   │   ├── imf.py
│   │   ├── fred.py
│   │   └── reuters_rss.py
│   ├── signals/
│   │   ├── deviation.py        # primitive 1
│   │   ├── trend.py            # primitive 2
│   │   ├── changepoint.py      # primitive 3
│   │   ├── dyadic.py           # primitive 4
│   │   ├── contagion.py        # primitive 5
│   │   └── thematic.py         # primitive 6 (uses Gemini)
│   ├── scoring/
│   │   ├── fragility.py        # structural layer
│   │   ├── watchlist.py        # composite index
│   │   └── config.yaml         # weights, thresholds
│   ├── briefs/
│   │   └── gemini.py           # prose generation only
│   ├── publishing/
│   │   ├── build_countries_json.py
│   │   ├── build_signals_feed.py
│   │   ├── build_matrix_json.py
│   │   └── draft_substack.py
│   ├── backtest/
│   │   ├── events.yaml          # the 8-10 events
│   │   ├── run_backtest.py
│   │   └── tune_weights.py
│   ├── storage/
│   │   └── parquet_writer.py   # hist/ is a directory of daily parquet snapshots
│   └── tests/
│       └── test_signals.py     # unit tests on synthetic data
├── hist/
│   └── YYYY-MM-DD.parquet      # one file per day, full panel
├── docs/                       # served by GitHub Pages
│   ├── index.html              # /signals
│   ├── globe.html
│   ├── country/
│   ├── matrix.html
│   ├── backtest.html
│   ├── methodology.html
│   ├── data/
│   │   ├── countries.json      # current state
│   │   ├── signals.json        # top signals feed
│   │   ├── matrix.json
│   │   ├── backtest.json
│   │   ├── themes.json         # weekly cluster labels
│   │   └── history/
│   │       └── YYYY-MM-DD.json # one snapshot per day
│   └── assets/
│       ├── css/
│       ├── js/
│       └── img/
├── posts/
│   └── YYYY-MM-DD-draft.md     # auto-generated weekly drafts
├── requirements.txt
├── README.md                   # reader-facing
└── CLAUDE.md                   # instructions for Claude Code
```

### 3.2 Data contracts

**countries.json** (the current-state file):

```json
{
  "generated_at": "2026-04-21T14:00:00Z",
  "universe_size": 178,
  "weights_version": "2026-04-01",
  "countries": [
    {
      "iso3": "NER",
      "name": "Niger",
      "watchlist": 7.8,
      "watchlist_wow_delta": 1.4,
      "watchlist_percentile": 96,
      "components": {
        "deviation": 2.3,
        "trend": 0.8,
        "contagion": 1.2,
        "fragility": 1.9
      },
      "cameo_summary": {
        "verbal_cooperation_7d": 12,
        "material_cooperation_7d": 3,
        "verbal_conflict_7d": 24,
        "material_conflict_7d": 41,
        "protest_7d": 8
      },
      "primary_counterparty": {"iso3": "FRA", "tone_7d": -4.2},
      "themes": ["coup-risk", "sahel-security", "france-withdrawal"],
      "changepoint_dates": ["2023-07-26"],
      "sparkline_90d": [0.3, 0.4, 0.4, ..., 7.8],
      "brief": "Niger's Watchlist rose sharply this week...",
      "last_updated": "2026-04-21T14:00:00Z"
    },
    ...
  ]
}
```

**signals.json** (the hero feed):

```json
{
  "generated_at": "2026-04-21T14:00:00Z",
  "window": "7d",
  "signals": [
    {
      "rank": 1,
      "iso3": "NER",
      "title": "Niger — material conflict events 3.2σ above baseline",
      "score_rank": 2.8,
      "tags": ["coup-risk", "sahel-security"],
      "counterparty": "FRA",
      "brief": "...",
      "chart_data": {...}
    },
    ...
  ]
}
```

**backtest.json**: array of events, each with date-indexed Watchlist values around T-0 and flag/miss boolean.

### 3.3 Pipeline schedule

- **Hourly** (`hourly.yml`): fetch GDELT DOC, update headlines cache. Very lightweight, no scoring changes. Purpose: keep the "last news" field fresh on country cards.
- **Daily 06:00 UTC** (`daily.yml`): full recompute. Pull GDELT events (previous day), run all primitives, recompute Watchlist, generate briefs via Gemini, write countries.json and signals.json, snapshot to `hist/`, commit and push. Run time target: <8 minutes.
- **Weekly Mon 06:30 UTC** (`weekly.yml`): thematic clustering, backtest refresh, Substack draft generation, email notification to Zach.
- **Manual** (`backtest.yml`): re-run full backtest on demand after weight changes.

### 3.4 Storage strategy

- `hist/YYYY-MM-DD.parquet` is the archival record: full panel for that day, ~180 countries × ~20 features = ~3600 rows × 20 cols. File size ~50KB parquet. One year of history ≈ 18MB total. Trivial for git.
- `docs/data/history/YYYY-MM-DD.json` is the frontend-queryable subset (per-country 90-day sparkline slices) used for country detail pages.
- `countries.json` is the latest-state view, rewritten every daily run.

Version history via `git log` means *every* historical state is reproducible. No separate database needed.

---

## 4. Frontend specification

### 4.1 Technology choice

- Static HTML/CSS/vanilla JS. No React/Vue/Svelte.
- `globe.gl` for the globe (already in v1).
- `d3.js` for sparklines, matrix heatmap, backtest charts.
- `plotly.js` only where interactivity on complex charts is needed (country detail page).
- Typography: `Space Mono` + `Syne` (as in v1 — the aesthetic works).

Rationale: static site is faster, cheaper, and sends a "this person can build" signal. A full React SPA for a data dashboard is over-engineered here.

### 4.2 Signals feed page (the hero)

Above the fold layout:

```
┌──────────────────────────────────────────────────────────────┐
│  ◈ GEOSIGNAL          • LIVE    Updated 14:00 UTC 21 Apr 26  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  THIS WEEK'S SIGNALS              View: [Globe] [Matrix] [↻] │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ 01  NIGER                              7.8 ▲ +1.4    │    │
│  │     ▁▁▂▂▃▄▆▇█  coup-risk · sahel · france-withdrawal │    │
│  │     Material conflict events 3.2σ above 365d baseline│    │
│  │     Primary counterparty: France (tone -4.2)         │    │
│  └──────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ 02  LEBANON                            7.1 ▲ +0.9    │    │
│  │     ▁▂▂▃▃▄▅▆▇  regional-spillover · hezbollah        │    │
│  │     ...                                              │    │
│  └──────────────────────────────────────────────────────┘    │
│  ...                                                         │
└──────────────────────────────────────────────────────────────┘
```

- Each card is clickable → country detail.
- Sparklines are pure SVG, rendered client-side from `sparkline_90d` field.
- The hero list re-ranks on every page load (not cached stale).

Mobile: single column, sparklines inline, tags wrap.

### 4.3 Country detail page

URL: `/country/NER`

Layout sections, in order:

1. Header with country name, flag, current Watchlist, percentile.
2. 90-day time series of Watchlist Index + components (stacked area: deviation, trend, contagion, fragility). Toggle for 1y, 5y.
3. CAMEO breakdown — stacked bar chart, past 30 days, verbal/material × cooperation/conflict.
4. Top 5 dyadic counterparties — tone heatmap, past 30 days.
5. Thematic exposure — horizontal bar chart of topic shares.
6. Recent headlines — last 20, with source and date.
7. Peer comparison — 3 countries with most similar 90-day Watchlist trajectories (cosine similarity on the trajectory vector, computed at daily build time and cached).
8. Prose brief (Gemini).
9. Changepoint markers overlaid on all time series.

### 4.4 Backtest page

URL: `/backtest`

One panel per event. Each panel:

- Event title and date
- 180-day window chart (90 pre, 90 post) of the country's Watchlist
- Vertical rule at T-0
- Model-call annotations at T-30, T-14, T-7
- Binary badge: `FLAGGED` / `MISSED`
- Short paragraph: what drove the signal, what the false-positive rate around this period looked like

Below the panels, a summary table: event | percentile at T-7 | flagged? | max watchlist in 30d pre-event.

This page should be *aggressively honest*. If the model missed an event, say so, and explain why. A backtest page that shows 8/10 flagged is more credible than one that shows 10/10.

### 4.5 Matrix page

URL: `/matrix`

Dyadic heatmap:
- 20 × 20 grid of major countries (G20 + EU majors + key conflict states)
- Cell color = mean Goldstein tone, source → target, last 30 days
- Hover: exact value + event count
- Toggle: 7d / 30d / 90d windows
- Toggle: actor-actor (state-state) vs. including non-state actors

### 4.6 Globe page

URL: `/globe`

Essentially v1's globe with three additions:
- Tags filter: click `coup-risk` and only countries with that theme exposure light up
- Time slider: drag to view historical coloring (pulls from `/docs/data/history/`)
- Click → redirects to `/country/ISO3` detail page (not a slide-out panel)

### 4.7 Methodology page

Plain HTML essay. Document every formula in §2. This is the page you link to when someone on LinkedIn asks "how does the score work?" It also lets you say, in the Substack footer: "Read the methodology at geosignal.xyz/methodology."

---

## 5. Automation for publishing

### 5.1 Weekly Substack draft

Every Monday 06:30 UTC, `weekly.yml` runs `pipeline/publishing/draft_substack.py`:

1. Load `signals.json`, take top 5.
2. For each, pull chart images (rendered with matplotlib, saved as PNG).
3. Call Gemini with a templated prompt:

   > "You are writing a Monday briefing for a Substack called Sentinel. Audience: finance professionals, geopolitical analysts. Tone: dry, data-first, analytical, New Yorker-adjacent prose. Avoid alarmism. Lead with the signal, not the context. Do not moralise. Here are this week's top 5 anomalies and their quantitative drivers: [structured data]. Write an 800-1000 word post with a headline, a 2-sentence TL;DR, and sections for each signal."

4. Save as `posts/YYYY-MM-DD-draft.md`.
5. Email Zach via SMTP (Gmail app password in secrets) with the draft inlined + a link to review.

Zach edits for 15-20 minutes, publishes to Substack. Drafts are versioned in git — you can look back at how the model's framing has evolved.

### 5.2 Threshold alerts

A lightweight script in `daily.yml` checks for:

- Any country where `|watchlist_wow_delta| > 2.0` (large weekly swing)
- Any country newly entering the top 10 globally
- Any changepoint detected in the last 24 hours

If any hit, send a single combined email to Zach with the list. Limit to ≤1 email/day.

### 5.3 Minimal manual touches

Philosophy: if you find yourself doing the same thing twice, move it into a workflow. The only manual tasks in steady state are:

- Weekly 15-minute Substack edit + publish
- Monthly review of weights (do new events motivate a re-tune?)
- Quarterly: add 1-2 new historical events to the backtest library

Every other piece of maintenance should be automated or run by Claude Code.

---

## 6. Build plan — Claude Code first

The build is structured so that Claude Code does >90% of the work. Each phase has an explicit handoff back to Zach only where account creation, secret management, or ambiguous product calls require it.

### Phase 0 — Human setup (30-45 min, Zach only)

Cannot be automated because they require a human at a keyboard signing into services.

- [ ] Create GitHub repo `geosignal` (public).
- [ ] Sign up / sign in: GitHub, Google AI Studio, Google Cloud (for BigQuery free tier), ACLED (register, wait 24-48h for credentials), FRED (free API key), Gmail (app password for SMTP).
- [ ] Collect credentials in 1Password.
- [ ] Add secrets to GitHub repo:
  - `GEMINI_API_KEY`
  - `GCP_SA_KEY_JSON` (BigQuery service account)
  - `ACLED_API_KEY`, `ACLED_EMAIL`
  - `FRED_API_KEY`
  - `SMTP_USER`, `SMTP_PASS`, `ALERT_EMAIL_TO`
- [ ] Enable GitHub Pages on the repo, source = `/docs` folder, branch = `main`.

**Deliverable**: empty repo with secrets populated, ready for Claude Code.

### Phase 1 — Scaffolding (Claude Code, one session)

Claude Code creates:

- Full directory structure from §3.1.
- `requirements.txt`, `.gitignore`, `README.md`, `CLAUDE.md`.
- Stub files for every module with docstrings but no implementation.
- Empty GH Actions YAMLs with correct triggers.

Zach reviews the PR (15 min), merges.

### Phase 2 — Data sources (Claude Code, one session)

Implement `pipeline/sources/*.py`. Each file:
- Fetches raw data
- Writes to `hist/` as parquet
- Has a `__main__` block that lets you run it standalone

End-of-phase acceptance test: Claude Code runs all source scripts locally in the container, and produces a dated parquet file with expected schema.

Zach: review PR, no merge blocker unless a schema looks wrong.

### Phase 3 — Signal primitives (Claude Code)

Implement `pipeline/signals/*.py`. Includes unit tests on synthetic data (constant baseline → deviation = 0; linearly increasing series → positive trend; etc.).

Zach reviews: are formulas right? Do the unit tests test what they should? If yes, merge.

### Phase 4 — Scoring + briefs (Claude Code)

Implement `pipeline/scoring/*`, `pipeline/briefs/gemini.py`, `pipeline/publishing/build_countries_json.py`.

Run end-to-end once locally. Zach eyeballs `countries.json`: do Niger/Ukraine/Syria have high scores? Do Switzerland/Norway have low scores? Yes → merge.

### Phase 5 — Backtest (Claude Code)

Implement backtest system. Run against 8-10 events. Generate `backtest.json`.

Zach reviews: if a surprising number of events were missed, why? Either the model is wrong or the event library has bad T-0 dates. Debug before moving on.

### Phase 6 — Frontend (Claude Code, largest phase)

Build five pages (§1.1) + methodology + about. Use mock data initially, then wire to real JSON.

Zach reviews aesthetic decisions. This is the one phase where subjective taste matters. Expect 2-3 round trips.

### Phase 7 — Publishing automation (Claude Code)

Weekly Substack draft generator, threshold alerts, email SMTP.

Zach: one dry-run with test email, then enable.

### Phase 8 — GH Actions go live (Claude Code + human verification)

Enable all four workflows. Monitor first 24h of hourly and daily runs. Fix anything that breaks.

**Steady state**: Zach spends ~20 min/week (Substack edit) + occasional review of alerts. Everything else is automated.

### Suggested timeline

- Phase 0: 1 day (mostly waiting for ACLED email approval)
- Phases 1-3: 1 weekend day of Claude Code work + review
- Phases 4-5: 1 weekend day
- Phase 6: 2 weekend days (frontend iteration)
- Phases 7-8: half a weekend day

**Total realistic wall-clock**: 2 weekends + 1 weekday evening. **Total active Zach time**: 6-10 hours, almost all review.

Deliberately front-loaded so the system is running by late April; during exam season (5-28 May) the site maintains itself.

---

## 7. Things explicitly not in v2 (and why)

- **User accounts**: no one needs to log in to a portfolio site. Subscribing is handled by Substack.
- **Proprietary ML**: a neural model on GDELT data would not be more predictive than the primitives above for 90% of signals, and would kill the auditability pitch.
- **Realtime streaming**: daily updates are enough. Hourly headlines are a nice-to-have, not a requirement.
- **Mobile-first design**: MAP partners review on desktop. Mobile should not break, but do not invert the design hierarchy for mobile.
- **Paid data sources**: the project's selling point is reproducibility. Every source is free.
- **Crypto / forex widgets**: this isn't a trading terminal. Keep the product focused.

---

## 8. Success criteria

Before you ship, the site should satisfy all of:

- [ ] A MAP partner opening `geosignal.xyz` on Monday morning can, within 90 seconds, answer: "what moved this week, and why does the model think so?"
- [ ] The methodology page is complete enough that an adversarial statistician could reproduce every number on the site from the described formulas and public data.
- [ ] The backtest page includes ≥1 miss, honestly reported.
- [ ] The weekly Substack draft is of a quality where Zach edits <25% of the words before publishing.
- [ ] The daily GH Action has run for 7 consecutive days without manual intervention.
- [ ] Clicking any country on the globe loads its detail page in <500ms.
- [ ] Zach can answer, in one sentence, "how is this different from GDELT's own dashboard?" — and the answer is visible on the homepage.

---

## 9. What Zach actually has to do

A ruthless enumeration, so there is no ambiguity:

1. Complete Phase 0 account setup (one sitting, 45 min).
2. Review each Claude Code PR (7 PRs, ~15 min each = ~1.75 hours).
3. Make the aesthetic calls in Phase 6 (2-3 rounds of taste feedback).
4. Write the `/about` page copy once.
5. Edit the weekly Substack draft (20 min × 52 weeks, but that's a writing habit not a build cost).
6. Respond to alert emails (rare, <1/week expected after steady state).

Everything else — every line of Python, every CSS rule, every workflow config — is Claude Code's job.

---

## 10. Open product decisions

These need Zach's call before Phase 6:

- **Name**: is "GeoSignal" final, or should we find a name that isn't used by other geospatial-intel brands? Candidates: `Sentinel` (already his internal name), `Verges`, `Sounding`, `Watchpoint`, `Threshold`. Stylistic preference?
- **Domain**: `geosignal.xyz`, `sentinel.fyi`, custom? Budget for ~£10/year.
- **Substack integration**: CTA button ("Subscribe to the Monday briefing") on every page, or only on `/about`?
- **Signal cards — anonymity option**: should signal cards that are politically sensitive (e.g., flagging a specific government) carry a small disclaimer, or is the methodology page sufficient?

Flag these to Zach after Phase 5 review, before Phase 6 starts.

---

**End of spec.**
