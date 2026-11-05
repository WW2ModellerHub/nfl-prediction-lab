## v2.1 — 5 November 2026 — Multi-season play-by-play accuracy research

- Expand full-refresh NFL play-by-play source coverage to eight seasons (2019–2026 for the current season).
- Add a simulated historical feature-selection lock: select a tactical variable using only seasons through 2023, then check the selected method against separate 2024+ historical outcomes.
- Show full matched Brier scores, season splits, paired week-block uncertainty ranges and precise year coverage; missing data stays missing.
- The additional historical data cannot automatically activate a tactical probability overlay. All new research remains informational until genuinely prospective testing supports adoption.
- Extend regression tests for retrospective selection integrity and source-window boundaries.

## v2.0 — 5 November 2026

- Added research-only five-way historical matchup signal ablation, with season-forward training and matched Brier comparisons.
- Added independent season-week block intervals, log-loss, accuracy and probability calibration bins.
- All results research-only; new signals have zero live forecasting weight.
- Schedule-only refreshes retain previous accuracy audit with explicit cached label; full refresh recalculates.
- Added dashboard tab, model-registry entry, provenance and leakage regression tests.

## v1.9 — 5 November 2026 — Matchup Intelligence & Upset Routes

- Added `assets/matchup-intelligence.js`, a reusable pure explainability engine that never modifies published win percentages.
- Added side-by-side cases for the model favourite and underdog, including evidence-backed tactical, pregame situational and unverified injury-watch considerations.
- Added scoring form vs points conceded, pass EPA vs pass EPA allowed, rush EPA vs rush allowed, explosive-pass rate and hit/sack proxies; original values and sample provenance are shown without asserting head-to-head play-calling or player-v-player coverage.
- New player availability comparison shows dated OUT/DOUBTFUL/IR and QUESTIONABLE reports, projected depth-chart-starter flags, data source and cached status; no fabricated player points or confirmed inactive claims.
- Improved Upset Radar with actual observed underdog matchup reasons (and explicit no-evidence fallbacks), distinct from model win chance and betting value.
- Added dedicated fail-open tests for missing data, misleading injury statuses, and no forecast mutation.
- Preserved model selection gates, Elo inputs and immutable forecast history.

## v1.8 — 5 November 2026 — Full Matchup navigation

- Fixture rows now open a dedicated, mobile-friendly full matchup page rather than relying on a modal.
- Bookmarkable direct links use `#game=<fixture-id>`; browser Back/Forward and tab links return to the correct dashboard view.
- Matchup pages include win probabilities, simulated margin assumptions, QB and injury evidence, tactical and situational details, source coverage, model gates, scenarios, and manual odds comparison.
- Added adjacent-fixture navigation, a copy-link control and an optional legacy modal.
- Missing or expired fixture IDs return a clear explanation rather than a blank page.
- Existing historical model gating and prediction values remain unchanged; no unsupported player or injury adjustments are introduced.

## v1.7 — 4 November 2026

- Added independent NFL historical situational signal audit against a pinned genuine nflverse schedule archive.
- Added separate dashboard page displaying 2024–26 Brier scores and research decision.
- Calculated six individual ATS signal rates with sample-size warnings.
- Kept research-only adjustment disabled: worse Brier in each of 2024 and 2025.
- No tactical or QB/injury validation claimed; historical PBP and timestamped reports are missing locally.
- Not deployed: connected GitHub account has no accessible writable repository.

## v1.6 — Real-Data Audit & Market Reality Check (2026-11-03)

- Added `scripts/audit.py`, a separate historical Elo/form baseline versus no-vig closing-market audit with winner accuracy, Brier, log loss, paired-game coverage and season-week block-bootstrap confidence intervals.
- Archived a **frozen, independently reconstructed** nflverse historical audit in `data/audit-reference.json`, with pinned source blob and explicit provisional status. Real Python pipeline output overrides it upon refresh.
- Added **Market Reality Check** dashboard navigation, model/market score display, season-by-season comparisons, attribution and audit export. No historical bet returns or CLV are claimed.
- Added an interactive offline research preview of actual Week 9 fixture matchups and independently reconstructed baseline probabilities, all time-stamped and labelled not live.
- Updated the GitHub Action to default to lightweight schedules-only refreshes; optional full refresh is available on manual trigger for heavier PBP/QB/injury research.
- Expanded audit, reference-integrity, and safety tests: **68 tests passing** across the entire project.
- The production dashboard still requires a verified source refresh; the preview is not the deployed service.

### Additional v1.6 safeguards

- Added Market Reality Check: independently audited season-level model probabilities against no-vig historical closing market prices. Pinned preliminary 2024–2026 snapshot labelled non-live.
- Added paired Brier, win accuracy, log loss, market coverage, and source integrity fields; live pipeline computes 95% week-block bootstrap uncertainty where enough games exist.
- Added free alternative schedules source, SHA-256/source timestamp provenance and a lightweight `--schedules-only` import mode.
- Added real scheduled November 2026 research-snapshot fixtures to self-contained demo (no fabricated player feeds or live prices).
- Excluded kicked-off, unscored fixtures from pregame forecast listings and avoided creating after-kickoff first-pick entries.
- Kept original forward forecasts immutable; closing moneyline data is never used to fit the model.
- Added automated regression tests for real-data provenance, betting leakage, odds conversion and snapshot integrity.
- Current limitations: advanced PBP ingestion and production GitHub deployment not independently verified in this network-restricted environment; no profitable edge claimed.

---

# Changelog

## v1.4 — Quarterback & Injury Intelligence

- Added `scripts/qb_injuries.py`: last-game leading passer and projected depth-chart QB (both explicitly unconfirmed); rolling player QB history via PBP; point-in-time injury/practice status filtering and chart snapshot retrieval.
- Reused existing PBP downloads to aggregate individual passer stats, avoiding additional season downloads.
- Added QB & Injury Radar tab, individual game breakdown, source-health panel and player watch alerts.
- Injury, questionable and depth-chart flags have **zero influence** on probability/score predictions until independent validation.
- Stored available QB identifiers and injury report timestamp within new immutable prediction entries; previous records remain unchanged.
- Added 10 QB/injury-specific tests to previous 32; 42 passing in total. Chromium injected-page interaction smoke test passed.
- Limitations: no verified production feed test in this environment, no confirmed gameday inactives, no complete retrospective injury snapshots, no automated player props or live alerts.

# Changelog

## v1.2 — Situational Research Gate (2 November 2026)

- Added `scripts/situational_validation.py`: regularised logistic adjustment on top of the pregame baseline.
- Season-forward evaluations are trained strictly on earlier seasons; the current season is excluded from overlay training.
- Adjustment remains OFF unless evaluation passes predeclared thresholds: at least 350 selection games, >=0.001 average Brier improvement, and 2+ positive evaluation seasons.
- Archived forward predictions now record baseline probability, adjustment status, and final published probability. Original archived predictions are never silently rewritten.
- The Model Laboratory shows season-by-season baseline/adjusted Brier scores, selection-gate status, sample sizes and penalised learned signal effects.
- Individual game details show baseline win probability vs adjusted probability, including zero when the gate fails.
- Added six model-specific regression tests, including current-season leakage and a no-signal control.
- GitHub Action now runs tests before updating predictions and deploying.

### Research limitations

The years used for gating are a model-selection dataset, **not** untouched blind validation. Historical ATS strategy counts are exploratory; neither positive Brier scores nor ATS hit rates prove a profitable bookmaker edge. No real historical schedule data is bundled; run the importer in an internet-enabled environment. The demo is invented and clearly labelled.

## v1.3 — Advanced Tactical Matchups

- New Tactical Radar navigation with team-by-team EPA, hit/sack proxies and explosive pass statistics.
- New per-game historical play-by-play aggregation from free nflverse yearly parquet releases.
- Optional strength-of-schedule passing correction based exclusively on opponents' earlier pregame performance.
- Chronological game-batch feature extraction; nothing from the current game enters its prediction.
- Penalised logistic tactical validation with sequential year testing and a separate research gate.
- Mutual exclusivity of tactical and situational probability overlays, preventing unvalidated double-counting.
- Extra forward-log metadata recording which overlay was selected, feature vector and probability delta.
- Clear unavailable/insufficient states for missing raw inputs, injuries and coverage assignments.
- Added tactical aggregation, gating, strength-of-schedule and anti-leakage regression tests.

## v1.5 — Player Impact Validation (2026-11-03)

- New **Player Impact Lab** tab and matchup modal breakdown: pregame QB evidence, fresh depth-chart timestamps, reported projected-starter absences, and eligibility for a player-adjusted probability.
- New `scripts/player_validation.py` with pregame player feature construction, regularised residual-logistic fit, season-forward Brier-score comparisons, and a strict OFF state when insufficient evidence exists.
- Historical injury and depth-chart importer now attempts timestamped 2025+ archives (older weekly depth chart formats are **not** treated as point-in-time starter forecasts).
- Optimised historical depth-chart lookups and injury report indexing to keep scheduled refresh jobs practical.
- Selection compares situational, tactical and player gates; **at most one overlay** modifies a fixture's baseline win probability. No automatic penalty for a merely questionable player.
- Preserves immutable pregame model versions, the applied overlay type, and the underlying player feature status in prediction logs.
- Historical injury reports are not official inactive confirmations; stale or missing data always blocks player-model eligibility.
- Added 11 new defensive tests (53 total); all are runnable offline using `python -m unittest discover -s tests -v`.

**Validation note:** For 2026, modern as-of depth-chart data only begins in 2025, leaving at most one complete prior season. The player gate is expected to remain **OFF**. The code implements an evidence test; it does not assert a statistically validated player injury edge or profitable strategy.
