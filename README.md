# Version 1.7 · Real historical situational evidence

Version 1.7 adds a separate **Situational Evidence** dashboard tab, with a frozen audit of 688 non-tied games from 2024 through the latest available final in a pinned nflverse `games.csv` revision. The independent reconstructed research model trained on 2016–2023, was checked on 2024–2025, and had a partial 2026 holdout. **The situational model failed the validation gate and is disabled.**

The independent research is **not the Python production pipeline's validation output**, and no live score, odds, prop, play-by-play, QB or injury feed was verified. The full Python pipeline still needs a successful run on a GitHub Actions runner. Publication requires a GitHub repository that you own or can write to. Every successful refresh also writes `data/full-model-audit.json`, recording exactly which advanced feeds and validation gates were available. The connected account had no accessible writable repository on 4 November 2026. No page is currently live.

To deploy: create a public `nfl-prediction-lab` repository, upload this archive's extracted contents to repository root, set **Settings → Pages → Build and deployment → GitHub Actions**, then run **Actions → Refresh forecasts and deploy → Run workflow** (schedules-only first). Confirm the workflow logs, published source timestamp and the source refresh status before using forecasts.

**Reproducibility:** `data/situational-research.json` includes its source blob SHA and methodology. Research uses historical closing prices solely for grading, not trading returns. Later updates must be evaluated on timestamped prospective picks.

---

# NFL Prediction Lab — working MVP

A **free, GitHub Pages-ready NFL prediction dashboard** with a genuine schedule-driven Python baseline, simulated score distributions, a situational matchup radar (overtime, recovery, blowout bounces, consecutive road games), manual UK bookmaker moneyline and handicap input, upset and Favourite Ambush watchlists, historical sequential backtesting, a season-forward validation gate for situational probability effects, exploratory strategy ATS counts, immutable forward prediction snapshots, and local personal bet tracking.

> **Status:** Version 1.6 — historical closing-market reality check and schedule importer resilience, plus the earlier tactical, situational and observational QB/injury intelligence. Not a live-score service. No automated player-prop or UK bookmaker prices. QB/injury data does not alter win probabilities; models are research baselines, not validated wagering advice.

## Start locally

Requires Python 3.10+ and internet to fetch nflverse schedule data. No pip packages or Node build are required.

```bash
python scripts/update.py --schedules-only  # reliable baseline refresh; full mode below
python -m http.server 8000
```

Visit http://localhost:8000/ in your browser. If `scripts/update.py` cannot access GitHub's public NFL data release, it exits with a nonzero status and **does not fabricate predictions**. The site will show a setup-required state until the importer succeeds.

## Deploy to GitHub Pages

1. Create a **new public GitHub repository** called `nfl-prediction-lab` (do not place personal bet records in it).
2. Upload the **contents** of this project folder to its `main` branch, preserving `.github/workflows/update-and-deploy.yml` and `.nojekyll`.
3. Go to repository **Settings → Pages → Build and deployment → Source → GitHub Actions**.
4. In **Actions → Refresh forecasts and deploy → Run workflow**, start with **schedules-only** (the lightweight default). It fetches nflverse `games.csv`, computes baseline forecasts and the historical no-vig closing-market audit, preserves prospective predictions in `data/predictions-log.json`, then deploys the static site. Run **full** manually later to refresh the heavier tactical/QB/injury research data.
5. Your site is normally available at `https://YOUR_USERNAME.github.io/nfl-prediction-lab/` after successful deployment. GitHub Actions can delay scheduled jobs; last-updated timestamps are displayed.

The workflow also performs **schedules-only** refreshes four times daily when scheduled jobs run; these are not real-time updates. Historical research snapshots remain available even before the first deployed refresh. If you're concerned about write conflicts, avoid simultaneously running manual updates and automated runs.

## Data and modelling

- Source: [nflverse schedules](https://github.com/nflverse/nflverse-data/releases/tag/schedules) (`games.csv`), data attribution CC BY 4.0; verify upstream licence and terms if extending sources.
- Games are processed chronologically. Past results update the two teams' Elo ratings and their previous offensive/defensive scoring form.
- Each future fixture uses only earlier games, a home advantage adjustment, Elo win probability, shrinkage scoring form and a normal-margin approximation. Score estimates and deterministic outcome simulations are baseline illustrations, **not calibrated game-level predictions**.
- Backtests begin with season 2024 but have warm-up history from 2016 onward. These are *sequential backtests*, not actual historical archived predictions. The code does not use current injuries, weather, closing odds or final results in the corresponding future-game forecast.
- On the first scheduled run, pending fixtures get immutable forward prediction entries. After results appear, those entries can be graded without changing the original pregame probability.
- Brier score, log loss, calibration and accuracy are exposed. A fixed 50/50 baseline is also compared (not an equivalent market benchmark).

### Situational matchup intelligence (new)

The data pipeline reads the `overtime` indicator and prior results from the NFL schedule CSV. For each fixture, it calculates **full intervening calendar off-days** between previous and current games, excluding both game days (Sunday-to-Sunday = **six full off-days**), using the schedule in Eastern time. Each matchup displays both teams' prior result, overtime/regulation status and recovery period, plus named flags:

- **Empty Tank+**: team played overtime in its previous game, has at most six full off-days, while its opponent's previous game ended in regulation.
- **Thursday Road Fatigue**: team played OT on Sunday and is away on Thursday with a short turnaround.
- **Blowout Bounce**: previous defeat by 28–34 points.
- **Nuclear Bounce**: previous defeat by 35+ points.
- **Rest Advantage**: three or more extra full off-days versus the opponent.
- **Back-to-Back Road**: second consecutive away fixture (actual miles travelled are not yet calculated).
- **Favourite Ambush watch**: when you manually enter the home-team point handicap, a favourite giving 7+ is flagged **only if** it also has one of the adverse situational factors or the underdog has an opposing bounce/rest signal.

The **Situational Radar** ranks flagged games by number of active factors, and game detail explains precisely why each flag fired. The **Model Laboratory** includes retrospective ATS counts from 2016 onwards, graded against closing spread lines where available, with a 2024+ subset. These are descriptive, not forward-tested profit estimates; overlapping observations and line availability can distort apparent hit rates.

**Crucial (v1.2):** situational effects **default to zero**. A new ridge-penalised logistic model learns small conditional adjustments to the baseline log-odds, strictly from previous completed seasons. It evaluates each later season with coefficients fitted exclusively on earlier ones. The last three completed evaluation seasons select activation only when there are ≥350 games, a mean Brier improvement of at least 0.001, and positive improvements in at least two seasons. If any condition fails, all situational adjustment coefficients are set to ZERO. The Model Laboratory shows every season's baseline and situational Brier scores, learned effects and whether the gate is active.

**Validation caveat:** the evaluation seasons used to activate this model are not an untouched final test: the activation rule is selected using them. The independent proof must come from the archived, never-rewritten pre-kickoff predictions after deployment. These signals are conditional correlations, not causal fatigue estimates; closing spreads are never inputs to model training. Score projections and simulation charts stay anchored to the unchanged baseline until separate calibration validates adjusting them. They are researched factors, not automatic picks. This prevents fabricated strategy 'edges'. Missing overtime data is treated as *unknown*, not regulation. Missing old-season context is not inferred from unrelated games.

### Odds and bet tracking

Open a fixture → **Enter bookmaker odds** to input an actual available decimal **moneyline** price. The Value Radar compares it to the model probability. Expected value is `probability × decimal price - 1`. Because the model has not yet demonstrated calibration or profitability, the value figures are **hypotheses**, not proven edges. The app does not automatically fetch odds, place bets or track live market movements. You may optionally enter the **home-team handicap** (negative = home favourite), which activates the Favourite Ambush watchlist but does not produce spread expected-value calculations.

**My Bet Ledger** stores individual bets, stakes and manual win/loss/void results in your browser's `localStorage`. Use **Export ledger** to back up and **Import** to restore. The records are **not** pushed to your public repository and are **not** synchronised between devices. Browser storage can be cleared.

### Known first-release limitations

1. Not a live play-by-play system, and no in-game probability recalculation.
2. No player-prop modelling, automated UK bookmaker data, weather feed, verified gameday inactives, or validated player-absence adjustments yet. Team-level tactical data is included in v1.3, and timestamped QB/injury monitoring is included in v1.5.
3. Situational probability adjustments activate **only if the historical evaluation gate passes**; otherwise flags stay informational. Actual travel miles, coaching, injuries and weather still require integration.
4. GitHub Pages is a public static site, and GitHub Actions is scheduled/best effort rather than continuous live compute.
5. The forecasts are a **baseline research model**. Historical testing and model calibration should precede any claim of predictive or betting edge.
6. Draws/ties are not represented as a third market outcome in the moneyline interface. This matters for NFL regular season and will need proper three-way/tie handling in a future version. The model considers ties in historical calculations, but displayed two-side home/away probabilities sum to 100%; treat them as approximations rather than a complete regulated market model.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Project files

```text
index.html                        responsive static app
assets/styles.css                dashboard visual design
assets/app.js                    tabs, matchups, radar, odds, local bet ledger
scripts/model.py                 forecasting, simulations, sequential evaluation
scripts/update.py                fetch / validate / produce current data
.github/workflows/update-and-deploy.yml
                                  scheduled refresh and GitHub Pages deployment
 data/dashboard.json             generated public website dataset
 data/predictions-log.json       immutable forward picks (model snapshots)
 tests/test_model.py             regression and no-leakage checks
 tests/test_situational.py       overtime, rest, ATS and no-leakage tests
 scripts/situational_validation.py  penalised residual regression, temporal evaluation and activation gate
 tests/test_situational_validation.py  effect-sign, leakage, gate and no-effect tests
```

Roadmap: real-data validation run and archived blind forward testing; strength-of-schedule features; meaningful situational indicators; player usage forecasts; point-in-time odds; walk-forward ML ensemble; verified licensed live scores; model audit and web notifications.

The project is not affiliated with the NFL, and it is not a gambling service. Gambling involves financial risk.

## v1.3 — Tactical Matchup Intelligence (new)

The **Tactical Radar** adds a second, independent set of matchup indicators to the existing overtime, rest and bounce-back section. On the next successful workflow run, the updater retrieves `play_by_play_{season}.parquet` for recent seasons from the [nflverse PBP release](https://github.com/nflverse/nflverse-data/releases/tag/pbp). It builds compact per-game team totals and retains only **already-finished games** when constructing pregame matchup snapshots. All same-kickoff games are predicted before any updates are applied, preventing simultaneous-game information leakage.

**Signals and exact meanings**

- Passing: offensive EPA/dropback versus the opposing defence's EPA/dropback allowed, for both sides.
- Rushing: rushing EPA/play versus the opposing defence's EPA/rush allowed.
- QB-hit/sack matchup: previous recorded sacks or QB hits per passing play, on offence and defence. This is **not a measured QB pressure rate**, and it is not an individual lineman/pass-rusher assignment.
- Explosive passing: the share of pass plays gaining 20+ yards versus the defence's historical rate allowed.
- Limited strength-of-schedule adjustment: where sufficient prior data exists, passing metrics are adjusted using the opponents' **pregame** EPA baselines that were already available before the previous games. The UI explicitly labels missing opponent-adjusted estimates instead of using the current/final-season opponent rating.

Each team gets its own rolling weighted 8-game summary. Fewer than three games or inadequate play counts are labelled **insufficient**, not silently imputed. Other absent files lead to **unavailable**. Advanced coverage type (man/zone), individual blocker/defender matchups, player-specific QB pressure performance and confirmed injuries are **not integrated** by this release.

**Model selection and guardrails:** `scripts/tactical_validation.py` fits a ridge-penalised logistic correction to the established score/Elo baseline using four scaled mismatch signals. It trains on earlier completed seasons and evaluates on later seasons. It requires at least 350 evaluation games, two improved seasons and a Brier score gain of at least 0.001 to be eligible. The evaluation results are used to select the correction and **are not a blind final test**. If both tactical and situational corrections are eligible, only the better recent-season validator is permitted — they are never stacked without validation of the combined model. These corrections affect **win probabilities only**; projected scores and illustrative score distributions remain baseline numbers. No profit or outperformance is claimed before real prospective evaluation.

**Data loading:** Online updates now require the free Polars Python package. GitHub Actions installs it automatically. For local updates:

```bash
python -m pip install 'polars>=1.0,<2'
python scripts/update.py
python -m unittest discover -s tests -v
```

Downloading recent seasons of full play-by-play parquet (several files, typically tens of megabytes each) can require considerable network bandwidth; the scheduled workflow runs best-effort. Individual failed seasons are recorded under `tacticalSource.errors`, and the website reports partial/unavailable coverage rather than inventing statistics. No play-by-play files are committed to the public site — only derived compact matchup summaries are published in `data/dashboard.json`.

**v1.3 model limitations:** It does not fetch bookmakers automatically, and even fully supported tactical statistics are descriptive until the historical eligibility gate passes. A real-time game feed is not provided; source releases are updated after games, not continuously live. Although the project is free, nflverse and GitHub usage terms and data licences remain applicable. Deployment to your own GitHub account has not happened from this chat.


## v1.5 — Quarterback & Injury Intelligence

A new **QB & Injury Radar** tab and individual-matchup detail block are now included. Upcoming matchups surface the latest *observed* leading passer for a team, or a *projected* depth-chart QB if a timestamp-valid snapshot is available. Neither is a confirmed gameday starter. A change versus the previously observed leading passer is marked **QB CHANGE WATCH**, not automatically predicted as a performance drop.

**New verified-source capabilities (upon successful GitHub workflow run):**

- QB-level recent *observed* dropback EPA, completion percentage, CPOE (percentage points), passing yards per attempt, sack percentage, and hit/sack percentage from nflverse play-by-play. A rolling weighted window includes at most eight prior player appearances across the current and previous season; last-game leaders require ≥5 dropbacks.
- Current-season nflverse weekly injury and practice reports from `injuries/injuries_{season}.csv`, with per-record `date_modified` timestamps. The dashboard highlights Out, Doubtful, Questionable and limited/DNP practice reports for key positions. Every timestamp must be **no later** than both the forecast time and the game's kickoff. A missing report is not proof of player health.
- nflverse timestamped depth charts from `depth_charts/depth_charts_{season}.parquet`. From 2025 onward these are dated snapshots, not week-based lineups. The engine selects the most recent team snapshot as-of each prediction, identifies projected QB1 and rank-1 players by player ID where available, and never uses later updates.
- Player-alert badges on matchup rows, plus an explicit report-source health section (PBP, injury reports and depth charts separately show loaded/unavailable status and upstream errors).

**Important constraints:** no official gameday inactives feed, no point-in-time injury history reconstructed for old seasons, no opponent coverage data, no individual offensive-line-vs-defender block charting, no real-time injury notification, and **zero player-availability probability adjustment**. The current football prediction model still uses only the separately validated tactical/situational overlays. We deliberately do not assign fictitious point values to an absent QB or offensive lineman. Injury and depth reports can change on game day; verify against official team announcements.

The PBP importer reuses the same season parquet download for both tactical metrics and QB stats rather than downloading the file twice. Online refresh additionally attempts current-season injury CSV and depth-chart parquet downloads; each can fail independently without fabricating player reports. Python `polars>=1.0,<2` remains the sole nonstandard import dependency and is installed by the GitHub workflow.

### Further verification required

42 local Python regression tests and the JavaScript syntax test pass. A Chromium check using injected HTML confirmed the QB & Injury tab, matchup dialog and source-health panel render without JavaScript errors. Direct `file://` navigation is restricted in this environment, so it was not used as evidence of a working deployed URL. **External nflverse download URLs could not be fetched from this sandbox due to DNS restrictions**; the real GitHub Actions refresh has not been verified here. The bundled demo uses entirely invented players and injuries and is clearly marked as illustrative.

Next planned experiment: collect archived *prospective* injury/starting-QB snapshots before games and measure whether player-specific features improve the pregame Brier score on untouched seasons and forward games. Until then, the player radar is observational only.

Upstream documentation: [nflverse data schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html), [injury report field dictionary](https://nflreadr.nflverse.com/articles/dictionary_injuries.html), [2025+ depth chart dictionary](https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html).

## v1.5 Player Impact Laboratory

The new **Player Impact Lab** evaluates whether player observations improve *pregame* NFL winner probabilities, without awarding arbitrary points to a team because of an injury headline.

- **Historical QB sample:** Expected QB is read from a timestamped depth chart published before the prediction cutoff. QB metrics (EPA/dropback and sack rate) come exclusively from completed previous games; each projected QB needs ≥80 prior dropbacks.
- **Injury feature:** Only latest timestamped pregame reports are considered. The limited OUT/DOUBTFUL indicator counts *projected* depth-chart starters, not official gameday inactives. An unavailable season-level injury archive makes the feature ineligible rather than treating missing as healthy.
- **As-of controls:** Only data with timestamps before kickoff (a 2-hour cutoff used in reconstruction) can be used. 2025+ depth charts are indexed by timestamp. Pre-2025 weekly charts aren't backdated as if they had publication times.
- **Historical evaluation:** Penalised residual-logistic overlay is trained on *prior completed seasons*, then compared with the Elo/form baseline on later seasons (Brier score). The player gate requires ≥350 eligible evaluation games, ≥2 improving seasons and ≥0.001 improvement. It may remain OFF for several seasons while the 2025+ historical window grows.
- **No overlay stacking:** Only the strongest eligible selection-gated situational, tactical or player model is used. Even a globally selected player model has no effect on an individual fixture with missing player data.
- **Forward audit:** Research/selection results are not an untouched blind test. Immutable picks and subsequent actual outcomes measure the true performance after deployment.

Current injuries and depth charts are retrieved from public nflverse releases in `scripts/qb_injuries.py`. The scheduled workflow fetches historical dated archives from 2025 onward; missing files are shown as missing and do not produce invented probability changes.

For an offline UI preview, use the separate `nfl_prediction_lab_v1_5_demo.html` file. It contains **fabricated fixture and player data, explicitly marked DEMO**, to exercise all tabs without claiming actual NFL predictions. The production `data/dashboard.json` is deliberately empty until the verified data refresh runs.


## v1.6 — Real-data integration & Market Reality Check (3 November 2026)

**Completed in this version**

1. Added `scripts/audit.py`: compares sequential Elo + scoring-form **historical reconstruction** with **no-vig closing moneyline** probabilities on precisely matched completed, non-tied games. Per-year comparisons include accuracy, Brier, log loss, market data coverage, and a deterministic season-week block-bootstrap confidence interval for the paired Brier difference where sufficient data exists. Closing markets are never training inputs.
2. Added `Market Reality Check` to the dashboard, with a season-by-season audit, probability-score visualisation, historical source metadata and an Export JSON button. It explicitly distinguishes independent archived research from the recomputed GitHub refresh.
3. Added import fallback from nflverse release `games.csv` to `nflverse/nfldata/master/data/games.csv`, verifying minimum row counts and data size. Source URLs, SHA-256, parsed rows, and latest confirmed score timestamp are published. Import failure is explicit; synthetic data is never published.
4. Added `--schedules-only` mode for a quick real baseline refresh that avoids large optional PBP/injury archives; any absent advanced intelligence is labelled unavailable. Scheduled GitHub Actions jobs use lightweight schedules-only mode; manually dispatch the workflow with `full` when the larger play-by-play and player archives should be refreshed.
5. Added regression tests for missing closing prices, ties, moneyline conversion, no-leakage from closing prices, reference reconciliation and unscored games that have already started. The complete suite currently contains **68 passing tests**. An unscored kicked-off game cannot be represented as an upcoming pregame pick.
6. Added a **pinned independent audit reference** in `data/audit-reference.json` and real scheduled fixtures snapshot in `data/reference-slate.json`, captured from the `nflverse/nfldata` GitHub source as of 3 November 2026. This separate source snapshot is a historical research illustration, **not** an official Python pipeline run. The demo is created with `python scripts/preview_demo.py`. These pinned files are **never** automatically loaded by the production prediction engine.

**Initial independent research finding (not yet Python-parity verified):** In 688 non-tied games from 2024 through 3 November 2026, an independent reimplementation of the existing Elo/form formula yielded 66.4% favourite winner accuracy and Brier 0.2214. The no-vig *closing* moneyline comparator recorded Brier 0.2094 and 67.9% accuracy on the same games. Model-minus-market Brier was +0.0120 (positive means model worse). For 2024: model 0.2156 vs market 0.2010; for 2025: 0.2243 vs 0.2109; for incomplete 2026: 0.2285 vs 0.2259. Independent results need confirmation after the first connected Python importer run. These are **not** backdated live bets, UK prices, CLV, or betting profitability.

**Quick start with real verified data:**

```bash
python scripts/update.py --schedules-only      # zero extra pip dependencies, baseline and market audit
python -m http.server 8000
```

For complete tactical, QB and injury data (where nflverse archives are available):

```bash
python -m pip install 'polars>=1.0,<2'
python scripts/update.py
```

The downloaded source is required. In network-restricted environments, `python scripts/update.py --schedules-only --schedules-file /path/to/games.csv` accepts an already downloaded genuine nflverse CSV and validates it before publishing. The completed forecast dataset is written to `data/dashboard.json`. The separate `nfl_prediction_lab_v1_6_demo.html` is static, explicitly pinned, and never silently replaces production data.

**Deployment:** Commit this project to a public GitHub repository, enable **Pages → GitHub Actions**, and trigger `Refresh forecasts and deploy` with `full` or `schedules-only`. The schedule uses lightweight mode by default; a manual run can select full mode. No API keys or paid hosting are required.

**Limitations:** This release does **not** fetch UK bookmaker lines automatically and does **not** provide a live NFL feed. It does not estimate historical betting ROI from closing odds or apply unvalidated player effects. GitHub Pages is public, and browser-local bet records must be exported for backups. Source freshness depends on nflverse releases. The first production GitHub Actions run and parity check have not been performed in this environment due to blocked network access.


