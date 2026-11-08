## v3.0 — 8 November 2026 — Pregame Verification Engine

- Load **same-week NFL official game-status and practice-report fields from the dated nflverse injuries mirror** on both full and lightweight refreshes. Preserve each row's actual `date_modified` timestamp; undated reports and post-kickoff/future data cannot certify absences. The mirror is explicitly labelled and linked to NFL.com for direct checking.
- Reconcile weekly QB injury designations against separately dated ESPN media observations and nflverse/ESPN projected depth-chart identities; flag disagreeing statuses, projected starters listed OUT, multiple unavailable QBs, stale/missing reports and source disagreements. An absent injury row does not establish health.
- Issue one **Pregame Verification** decision per fixture: checked, review, or hold. Confirmed starters and game-day inactives are NEVER fabricated: no direct coach-confirmation or inactive-list feed has yet been connected.
- Preserve the one-number forecast and historical archive. If the verification gate detects unreliable key QB evidence, **withhold automatic experimental QB probabilities** rather than adjusting from contradictions. Treat uncross-checked forecasts as *Unverified*, regardless of numerical confidence.
- Suppress value/EV alerts and wager-like radar picks for any unverified fixture. Allow raw manual price comparisons but visibly label their EV alerts as held until verified. Show specific blocking reasons and both teams' full QB/report evidence in a compact expandable matchup panel.
- Continue saving original predictions; add verification level, source provenance and reasons to future immutable snapshot records. Report source-coverage and gate counts in `data/full-model-audit.json`.
- Regression tests cover official report parsing, report timestamps, double QB absences, media conflicts, missing projected starters, absent weekly reports, basic cross-checked status, and blocked QB-model calculations.

## v2.9 — 7 November 2026 — Honest live NFL prediction record

- Add permanent, automatically updated `data/prediction-results.json` from existing timestamped original and revised forecasts, with one outcome per genuinely completed NFL game and explicit ungraded/pending statuses.
- New prominent **Prediction Record** in the command centre and existing performance tab: original versus latest W/L, hit rate and Brier score; per-week results, the complete list of scored games and future pending picks with predicted winners.
- Keep one pick per fixture regardless of number of refreshes; never include post-kickoff snapshots, games lacking verified final scores, or ties in performance metrics. Continue saving original predictions without rewriting them.
- Add explicit warning on sample sizes below 30 games and distinguish live forward results from reconstructed historical backtests and betting ROI.
- Scheduled workflow now commits the separate record JSON on each refresh, while using a path-ignore rule to prevent recursion.
- Targeted tests for correct-vs-incorrect original and revised selections, sample deduplication, kickoff gating, no-result outcomes, weekly cohorts and legacy archival preservation.

## v2.8 — 7 November 2026 — One number, reconciled layer contributions

- Replace the 3-column win/score headline with **one dominant predicted-winner win probability**, with the other team's chance and expected score secondary.
- Add a short, auditable **probability-contribution ladder**, starting at a 50/50 accounting reference. Elo (60% weight), scoring form (40%), any historically selected overlay, provisional QB efficiency, reported-QB replacement, and other injury effects are shown as **signed percentage-point moves toward the final predicted winner**. Every stage has its running total, and its stored home-oriented deltas reconcile to the exact final published number.
- Signals that have **no probability weighting** (situational, tactical, injuries, weather, etc.) say **Not applied**, not a misleading numerical zero. Evidence and model limitations remain accessible in compact expandable sections.
- Remove the long, repetitive **Saved pre-game predictions** table from every matchup, and remove the Prediction History navigation entry; retain the underlying immutable prediction ledger and forward-performance grading for research.
- Collapse full player, injury, QB-replacement, tactical, weather, rest, simulation and score evidence behind a single **Explore all supporting evidence** section on mobile.
- Persist actual activated layer contributions in new immutable forward revision snapshots without rewriting earlier records.
- Fix older dossier wording that incorrectly claimed QB/injury information was never part of the published percentage.

## v2.7.1 — 6 November 2026 — No overlapping QB overlay penalties

- If a fresh documented replacement qualifies for the provisional QB replacement model, **suppress** the independently researched QB-efficiency overlay for that fixture, rather than stacking two measurements of the same underlying QB downgrade. Preserve its hypothetical research delta separately, marked withheld.
- Keep the provisional statistical QB preview for games with only projected/uncertain changes and no reported replacement adjustment.
- Keep non-QB injury factors separate and the original pre-kickoff prediction immutable. Record suppression counts and two targeted regression tests.

## v2.7 — 6 November 2026 — Established QB and multiple-absence chain

- Derive a team's **established current-season starter** from previous completed nflverse schedule starting-QB records (minimum two verified starts and a unique leader), even if the latest game's starter was another QB. A tie or too few starts stays unknown; this is a historic participation inference, NOT an official QB1 designation.
- Show the hierarchy of observed current-season starters, number of verified starts, prior EPA/dropbacks and last appearance; never use the future game's actual starting QB to predict itself.
- Display in the matchup QB panel the chain **established QB → last-game starter → projected QB**, with independently dated injury designations for the two previously used QBs. A QB1 out report is not incorrectly attributed to QB2.
- If the established QB missed the previous game, reflect his existing absence as context without a fresh QB1 penalty; only a verified, separately reported absence of last game's QB can activate a **last-game QB to next projected QB** replacement scenario. Never add two full QB penalties or treat a projected starter as confirmed.
- Preserve original immutable forecast snapshots, source timestamps and the historical research-only status of QB replacement magnitudes. New tests cover established starter missing multiple games, ties, simultaneous QB absences, continued backup, and missing second-absence evidence.

## v2.6.2 — 6 November 2026 — Actual ESPN 2026 depthchart format support

- Live 2026 ESPN depth endpoint returns `depthchart` singular (confirmed via response-key inspection), while outdated public examples show `depthCharts` plural.
- Accept either nested structure through a bounded recursive search requiring BOTH an explicit QB/Quarterback position label and an explicit rank 1. No reliance on array order, no rank-2 promotion and no non-QB misclassification.
- Retain the independent injury-report and roster-identity evidence feeds, all source timestamps and contradiction safety checks.
- Regression tests for the live singular-key structure, missing rank and unrelated rank-1 players.

## v2.6.1 — 6 November 2026 — Correct live secondary-source integration

- Live GitHub refresh proved ESPN's team-specific depthchart and injury endpoints returned no documented data structures (0/28 teams). Explicitly mark that failure rather than counting these sources as successful.
- Stop querying the nonworking team-specific injury endpoint; use the already live-verified ESPN **league-wide** injury watch (269 dated entries across 32 teams at the initial check), preserving report timestamps.
- Attempt ESPN **team QB roster** endpoints instead as a secondary identity/membership check. A roster list can never become a projected or confirmed starting QB; depth-chart rank 1 is used only if a structurally valid dated rank is actually returned.
- Show roster candidates and individually dated ESPN league QB reports beside nflverse projected starters and explicit source agreement/disagreement on each full matchup.
- Include top-level response keys in source diagnostics, so future undocumented ESPN format changes are detectable without inventing results.
- Preserve previous forecasts and never label absent data as healthy or give the roster a forecast weight.

## v2.6 — 6 November 2026 — Automated independent QB evidence collection

- Fetch fresh ESPN team-specific projected QB rank-1 depth charts and dated team-specific injury reports for **teams playing within seven days**, on each scheduled full and lightweight refresh. ESPN endpoints are unofficial best-effort sources; fetch failure remains visible.
- Cross-check ESPN against the primary timestamped nflverse QB depth chart, displaying both projected identities, source observation time, agreement/conflict and missing evidence. Do not treat either as a confirmed starting quarterback.
- When nflverse's projection is missing or stale, use ESPN rank-1 only as a **source-labelled projection**, never copy ESPN player IDs into nflverse GSIS IDs or fabricate a history sample.
- On fresh, conflicting rank-1 projections, suppress both statistical QB research overlay eligibility and automatic quarterback replacement effects; preserve the conflicting names for human inspection.
- Only explicitly dated player injury entries can contribute reported statuses. An undated update has no assumed report timestamp; availability stays unknown rather than healthy.
- Light-refresh injury checks use up to 36-hour-old **previously completed QB history** without carrying forward old forecast probabilities. Each cached history has a fixed timestamp that subsequent refreshes cannot renew.
- Correct new immutable pregame log timestamps to follow the last source fetch; existing archived predictions are not modified.
- Add unit tests for source parsing, conflicting names, no fake dated injuries, history expiry, mapping and separate attribution; add mobile matchup evidence inspector.

## v2.5.1 — 6 November 2026 — Explain missing QB replacement evidence

- Replaced the oversized blanket “Conditional / Monitor Only” mobile card with a compact, accurate status for no change, missing data, reported QB OUT with unconfirmed replacement, or a supported conditional scenario.
- Added side-by-side per-team evidence diagnostics: previous QB, projected QB, depth-chart timestamp, reported QB injury status, previous dropbacks and exactly which eligibility checks failed.
- The dashboard no longer presents an unactivated “0.0 percentage points” as if the QB replacement module calculated a player value.
- Missing replacement projections are distinguished from evidence of no change; a real outgoing QB OUT report with an unknown replacement is flagged explicitly instead of buried as “no eligible QB”.
- Original published probabilities remain unchanged; full source verification and uncertainty safeguards are preserved.
- Added Python gate tests and JavaScript render regressions for the missing-projection and no-applied-effect states.

## v2.5 — 6 November 2026 — NFL QB Replacement Value Lab

- Replace the fixed-points-only QB absence estimate with a separate bounded, roster-specific replacement model that uses the outgoing starter's **completed prior-game EPA**, a dated QB replacement projection and the empirically observed EPA of quarterbacks making their first prior-data-light starts.
- Build the historical first-start prior as a rolling point-in-time sample of *other completed games* (at least 20 observations); future starter identity and same-game EPA are never pregame model inputs.
- Convert a shrunken QB efficiency gap into expected net points via recent dropback volume and a capped ±13-point scenario, with an explicitly unvalidated probability mapping.
- A full adjustment activates **only** with a matching recent QB OUT/DOUBTFUL media report and fresh dated replacement projection; a projected-only or questionable QB yields a conditional scenario but does **not** change published probability.
- Do not double-count the older fixed QB-out penalty. Keep separately archived statistical-QB, replacement-QB, and other-injury components with original predictions untouched.
- Research study scores only earlier-year pregame projection-change scenarios; never calls them confirmed injuries, and never changes a published forecast retrospectively.
- New full-matchup QB Replacement Value panel, source coverage audit and tests for rookie replacement, improving replacements, uncertainty, timestamp leakage and scenario gating.

## v2.4 — 6 November 2026 — Prospective forecast accountability

- Recover **only genuinely timestamped original picks** from the pre-existing immutable forecast log into Prediction History, including games that have already finished. Every recovered record includes an import time distinct from its original forecast time; no postgame prediction is generated.
- Score original and latest genuinely archived pre-kickoff probability on identical confirmed results: Brier, log loss, accuracy, improvements/worsenings, and per-fixture final scores.
- Record exactly how many later prediction revisions existed and how old the most recent pre-kickoff update was for each completed game. An original-only match is never presented as an updated or injury-aware forecast.
- Add a **strict final-24-hour** comparison restricted to games that actually have a saved forecast inside that final window; never guess last-minute results or availability.
- Display a completed-games prediction-by-prediction scorecard and update the public machine-readable model audit.
- Add regression tests for immutable original recovery, Jaguars–Ravens historical pick, timestamp cutoffs, legacy integrity protection, and strict 24-hour cohort.

## v2.3 — 6 November 2026 — Provisional QB statistical forecast

- Exposes the previously hidden prior-season-fitted QB EPA / sack-rate / starter-change model as an explicitly **provisional** numerical forecast when a genuine pregame QB feature snapshot is eligible.
- Historical research sample (2019–2025) and 2020–2025 season-forward evaluation determines a conservative exploratory gate, without removing the original strict QB approval gate.
- Bound QB statistical impact to ±0.20 log-odds (roughly ±5 percentage points near 50/50), retaining baseline and separately logging the QB and injury contributions.
- A QB-out injury assumption is evaluated *after* the statistical QB scenario; both components are recorded in the immutable pre-kickoff forecast revision.
- This model is NOT blind or independently prospectively calibrated; no claim of a profitable betting edge.

## v2.2.1 — 6 November 2026 — Corrected QB change direction and stale future-week estimates

- A changed projected quarterback no longer automatically penalises a team. Returning starters can improve the estimate.
- Without a dated prior-starter OUT/DOUBTFUL report, require >=80 previous dropbacks for both quarterbacks, use a bounded signed prior EPA difference, or do NOT move the forecast.
- QB and injury adjustment is disabled until within seven days of kickoff; future-week depth charts are not proof of upcoming starters.
- Regression tests cover unknown QB quality, a better returning starter and distant fixtures.
- Corrected UI cache busting so the new Prediction History navigation is visible.

## v2.2 — 6 November 2026 — Immutable forecast revisions and QB/injury-aware estimates

- All predictions are now snapshotted before kickoff in data/forecast-revisions.json, retaining the first original from the existing immutable forecast log.
- A fresh dated ESPN media OUT/DOUBTFUL report affecting a recent prior starting QB, dated QB projection changes and known ≥70% prior-snap player absences can change a separate, explicitly **provisional** published win probability.
- Both the original and baseline probabilities remain visible, with assumptions, uncertainty, model-source timestamps and detailed changes.
- New Prediction History page grades original and last recorded pre-kickoff forecasts independently, never retrospectively rewriting old scores.
- Lightweight refreshes carry existing adjustments only for up to 24h and always label them cached.
- New rules are an explicitly experimental point-based scenario, not proven injury replacement values or confirmed starting lineups.

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
