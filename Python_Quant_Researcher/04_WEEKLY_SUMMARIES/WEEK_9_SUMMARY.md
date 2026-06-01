# Week 9 Summary — Permanent Historical Record
## DeFi Quant Engineer Curriculum
**Student:** Greg (Gmac)
**Week:** 9 of 24
**Dates:** 2026-05-21 to 2026-06-01

---

## 1. Planned vs Actual

| Planned (from WEEK_9_THREAD_STARTER.md) | Outcome |
|---|---|
| LEARNING_LOG.md update — Week 9 Task 1 | ✅ Complete — committed a2278fc during Week 8 close-out (Week 8 concepts added before Week 9 started) |
| ETH RSI stability analysis (RR-RSI-006) — six weeks outstanding | ✅ Complete — STABLE (314/314 profitable, 27/27 neighbourhood). RR-RSI-005 and RR-RSI-006 resolved. |
| Data quality checks: LINK, DOT, MATIC | ✅ Complete — all three cleared data quality; proceeded to grid |
| Multi-asset discovery grid: LINK, DOT, MATIC, BNB, AVAX | ✅ Complete — all five assets run; one viable candidate (BNB Donchian) |
| BTC SMA Phase 5 leverage analysis | ⬜ NOT DONE — carry-over to Week 10 (third consecutive deferral) |
| II-001 Telegram health check redesign | ⬜ NOT DONE — carry-over to Week 10 (four weeks outstanding) |

**Additional work completed (not in original plan):**

| Item | Outcome |
|---|---|
| BNB Donchian Phase 0–2: discovery, logic check, max loss | ✅ Complete — breakeven WR 22%, LOW SENSITIVITY |
| BNB Donchian Phase 3: Monte Carlo | ✅ Complete — 0% P(neg year), Kelly positive to 65% WR |
| BNB Donchian Phase 4: stability grid, walk-forward | ✅ Complete — STABLE (26/42 post-break PF>2.0), 9/13 WF windows profitable |
| BNB Donchian Phase 5: regime break, exit comparison | ✅ Complete — post-break PF 2.961 (SMA-120), Exit A confirmed optimal |
| Phase Gate standard added to METHODOLOGY_STANDARDS.md | ✅ Complete — pipeline phase table required in all risk registers |
| B&H Exception Rule added to METHODOLOGY_STANDARDS.md | ✅ Complete — when B&H MDD > −60%, return/Sortino gates suspended |
| Phase 3A–3E optimisation sequence added to STRATEGY_RESEARCH_PIPELINE.md | ✅ Complete — mandatory order for all future strategies |
| RISK_REGISTER_BNB_DONCHIAN.md created | ✅ Complete — 7 items (RR-BNB-001 through RR-BNB-007) |
| BNB Phase 6 chart package (07_bnb_charts.py) | ✅ Complete — seven interactive HTML charts, all confirmed saved |
| BNB Phase 6 deployment card | ✅ Complete — BNB_DONCHIAN_DEPLOYMENT_CARD.md written |
| ETH RSI register cleanup (RR-RSI-007, -008, -009; RSI-005/-006 resolved) | ✅ Complete — this close-out session |
| STRATEGY_ARCHIVE.md updated (S011–S016 added) | ✅ Complete — this close-out session |
| LEARNING_LOG.md Week 9 concepts added | ✅ Complete — this close-out session |

**Summary:** The multi-asset discovery grid produced one viable candidate (BNB Donchian) which then consumed the majority of the week with a full Phases 0–5 validation. BTC SMA Phase 5 and II-001 were deferred for the third and fourth time respectively. Both are now Week 10 Priority 2 and Priority 4.

---

## 2. Key Findings

### Multi-Asset Discovery Grid Results

| Asset | Result | Detail |
|---|---|---|
| LINK | Rejected — zero passes | High volatility blows all stop distances; no viable combinations |
| DOT | Rejected — no viable edge | Structural multi-year downtrend; best Sortino 0.49 (below 0.8 threshold) |
| MATIC | Rejected — B&H floor | B&H MDD > −60% exception applied but no combinations clear substitute gates post-break |
| AVAX | Rejected — edge compressed | Keltner EMA=15/mult=2.0 sole pass, post-break PF 1.413 (1.0–2.0 range: insufficient) |
| BNB | VIABLE — Donchian | 23+ combinations passed B&H-exception-adjusted gates; 2 proceeded to validation |

Only BNB produced a deployable candidate from the five-asset sweep. The altcoin research direction (LINK, DOT, MATIC, AVAX) is closed for the current market cycle. Documented in STRATEGY_ARCHIVE.md S012–S016.

### BNB Donchian Validation (Phases 0–5 — all complete)

- **Phase 2 (Max loss):** $7.25 per trade = 4.83% of $150 capital. Breakeven WR 22.0% — LOW SENSITIVITY. The strategy maintains positive expectancy unless win rate falls 21+ percentage points from backtest level.
- **Phase 3 (Monte Carlo):** 0% P(negative year) at all tested win rate scenarios (43.2% down to 65%). Kelly positive throughout. Deployment at one-third Kelly due to capital constraint at $150 unleveraged (RR-BNB-005). Half-Kelly permission formally documented (RR-BNB-006).
- **Phase 4 (Stability + Walk-Forward):** STABLE — 26/42 post-break parameter combinations with PF > 2.0 (62%). Walk-forward: 9/13 OOS windows profitable. Grid boundary extension confirmed plateau extends beyond tested range (Analysis 1).
- **Phase 5 (Regime Break + Exit Comparison):** Post-break PF 2.961 with SMA-120 filter (Jan 2024 break date). VIABLE. Exit A (channel + 5% trail) dominates Exit B (ATR) and Exit C (EMA two-tier) on all post-break metrics. SMA-120 is the Pareto-dominant regime filter across SMA-50/100/120/200 tested.

### Process Improvements Added This Week

**Pipeline Phase Gate Standard** — Mandatory Phase 0–6 table in every risk register. Claude Code checks the table at the start of every session. Phase N+1 work may not begin until Phase N is signed off. Written deferral justification required for any skipped phase. Added to METHODOLOGY_STANDARDS.md.

**B&H Benchmark Exception Rule** — When B&H MDD > −60%, the 2.0× annual return gate and 1.5× Sortino gate are suspended. Substitute gates: Strategy Sortino > 0.8 AND Strategy MtM MDD better than −50%. The MDD gate is never suspended. First applied to BNB (B&H MDD −80.1%). Added to METHODOLOGY_STANDARDS.md.

**Phase 3A–3E Optimisation Sequence** — Entry parameters → exit comparison → regime filter test → joint optimisation → Monte Carlo. Mandatory order for all future strategies. Retroactively opened as gap items for ETH RSI (RR-RSI-008 Phase 3D, RR-RSI-009 Phase 3C). Added to STRATEGY_RESEARCH_PIPELINE.md v2.0.

**Visualisation as Phase Deliverable** — Chart package formally required as a named Phase 4/6 deliverable, not optional documentation. Seven interactive HTML charts for BNB Donchian confirm Phase 6 production-ready status.

### B&H Exception Rule — First Application (BNB)

| B&H Check | Threshold | BNB B&H Value | Gate | Strategy Result | Status |
|---|---|---|---|---|---|
| Annual return | ≥ 2.0× B&H | +69.1% → gate: 138.2% | Suspended (B&H MDD −80.1%) | +28.3% | EXCEPTION APPLIED |
| MtM MDD | ≤ 0.50× B&H MDD | −80.1% → gate: −40.0% | Never suspended | −29.7% | PASS ✅ |
| Sortino | ≥ 1.5× B&H Sortino | 1.103 → gate: 1.655 | Suspended | 0.843 | EXCEPTION APPLIED |
| Substitute: Sortino > 0.8 | — | — | Applies | 0.843 | PASS ✅ |
| Substitute: MDD < −50% | — | — | Applies | −29.7% | PASS ✅ |

---

## 3. Risk Register Items — Opened, Updated, and Closed This Week

### RISK_REGISTER_BNB_DONCHIAN.md (new — created 2026-06-01)

| ID | Description | Action | Status |
|---|---|---|---|
| RR-BNB-001 | Post-break walk-forward mixed (3/4 post-2024 windows losses) | Opened | Open — monitoring |
| RR-BNB-002 | SMA-120 filter selected post-grid (data-mining risk) | Opened | Accepted with rationale |
| RR-BNB-003 | BNB/Binance regulatory tail risk | Opened | Accepted — $150 limit |
| RR-BNB-004 | Leverage screening deferred | Formally deferred | Low — reopen after 10 live trades |
| RR-BNB-005 | Kelly sizing: capital constraint at $150 | Raised and resolved | Documented as one-third Kelly |
| RR-BNB-006 | Half-Kelly permission | Raised and resolved | Granted — 2022 bear market evidence |
| RR-BNB-007 | Sortino B&H threshold failure: exception | Raised and accepted | B&H MDD exception formally documented |

### RISK_REGISTER_ETH_RSI.md (updated this week — close-out session)

| ID | Description | Action | Status |
|---|---|---|---|
| RR-RSI-005 | 120MA regime filter: data-mining risk | Resolved | Stability grid confirms robustness across SMA 90–150 |
| RR-RSI-006 | Stability analysis not completed | Resolved | STABLE — 314/314 profitable, 27/27 neighbourhood |
| RR-RSI-007 | EXIT_RSI threshold discrepancy | Moved to Resolved table | Documented; EXIT_RSI=48 canonical |
| RR-RSI-008 | Phase 3D joint optimisation not completed | Opened | Open — Medium priority |
| RR-RSI-009 | Phase 3C regime filter period not via sensitivity analysis | Opened | Open — Low priority |
| RR-RSI-009 cross-reference bug | Fix line referenced RR-RSI-007 instead of RR-RSI-008 | Fixed | Corrected |

---

## 4. Key Decisions Made

| Decision | Rationale |
|---|---|
| Deploy BNB Donchian per=20/stop=5%/SMA-120 at $150 | Phases 0–5 complete, all quality gates passed (with B&H MDD exception), post-break PF 2.961 |
| Reject per=60/stop=5% | Walk-forward median OOS PF 0.421; per=20 dominates on all metrics |
| Close LINK, DOT, MATIC, AVAX as research directions | No viable combinations in discovery grid; failure modes are structural (not parameter-solvable) |
| Half-Kelly permission for BNB | 2022 bear market OOS evidence confirms SMA-120 filter protected capital; 2 walk-forward windows confirm |
| Capital constraint at one-third Kelly | $150 unleveraged — Kelly-optimal position $408 exceeds available capital; correct treatment is one-third Kelly, not Quarter-Kelly |
| B&H exception formally adopted into Methodology Standards | BNB case revealed a structural gap in the benchmark framework; now a standing rule for all future strategies with B&H MDD > −60% |
| BTC SMA Phase 5 deferred to Week 10 (mandatory) | Three consecutive deferrals; must complete in Week 10 without further deferral |

---

## 5. Open Items Carrying Into Week 10

| # | Item | Register | Urgency |
|---|---|---|---|
| 1 | BNB Donchian independent review + bot build | RISK_REGISTER_BNB_DONCHIAN.md | Week 10 Priority 1 |
| 2 | BTC SMA Phase 5 leverage analysis | RISK_REGISTER_BTC_SMA.md | Week 10 Priority 2 — third deferral; must not slip again |
| 3 | BTC SMA BS009/BS010 (Phase 3B exit, Phase 3C filter) | RISK_REGISTER_BTC_SMA.md | Required before deployment card |
| 4 | II-001 Telegram health check redesign | Infrastructure | Week 10 Priority 4 — four weeks outstanding |
| 5 | ETH ADX A023/A024 (exit method, regime filter — Phase 3B/3C) | RISK_REGISTER_ETH_ADX.md | Schedule within Weeks 16–18 |
| 6 | ETH RSI RR-RSI-008 (Phase 3D joint grid) | RISK_REGISTER_ETH_RSI.md | Before ETH RSI capital scaling to $341 |
| 7 | ETH RSI RR-RSI-009 (Phase 3C filter — resolved by RR-RSI-008) | RISK_REGISTER_ETH_RSI.md | Implicit — resolved when RR-RSI-008 complete |
| 8 | Update revision notes PDF for Week 9 | Admin | Week 10 |

---

## 6. Documents Modified This Week

| Document | Path | Change type |
|---|---|---|
| METHODOLOGY_STANDARDS.md | 00_MASTER/ | Updated — Pipeline Phase Gate standard, B&H Exception Rule (both new sections) |
| STRATEGY_RESEARCH_PIPELINE.md | 00_MASTER/ | Updated — Phase 3A–3E mandatory sequence, Phase Gate table requirement |
| STRATEGY_ARCHIVE.md | 00_MASTER/ | Updated — S011–S016 added (BNB, AVAX, LINK, DOT, MATIC) |
| LEARNING_LOG.md | 00_MASTER/ | Updated — Week 9 section (9 new concepts) |
| RISK_REGISTER_BNB_DONCHIAN.md | 01_RISK_REGISTERS/ | Created — RR-BNB-001 through RR-BNB-007 |
| RISK_REGISTER_ETH_RSI.md | 01_RISK_REGISTERS/ | Updated — RR-RSI-005/-006 resolved, RR-RSI-007 moved, RR-RSI-008/-009 opened, cross-reference fixed |
| BNB_DONCHIAN_DEPLOYMENT_CARD.md | 03_DEPLOYMENT_CARDS/ | Created — Phase 6 deployment card |
| 01_altcoin_discovery_grid.py | 06_BACKTESTS/Week_9_Notebooks/ | Created — multi-asset discovery grid |
| 02_bnb_hardfilter_scan.py | 06_BACKTESTS/Week_9_Notebooks/ | Created — BNB hard filter scan |
| 03_regime_break_analysis.py | 06_BACKTESTS/Week_9_Notebooks/ | Created — regime break + exit comparison |
| 04_bnb_walkforward.py | 06_BACKTESTS/Week_9_Notebooks/ | Created — walk-forward validation |
| 05_bnb_validation_pipeline.py | 06_BACKTESTS/Week_9_Notebooks/ | Created — stability grid |
| 06_bnb_montecarlo.py | 06_BACKTESTS/Week_9_Notebooks/ | Created — Monte Carlo |
| 07_bnb_charts.py | 06_BACKTESTS/Week_9_Notebooks/ | Created — Phase 6 chart package |
| charts/*.html (7 files) | 06_BACKTESTS/Week_9_Notebooks/charts/ | Created — all seven interactive charts |
| bnb_*.csv (5 files) | 06_BACKTESTS/Week_9_Notebooks/ | Created — result CSVs from all analyses |
| altcoin_discovery_results.csv | 06_BACKTESTS/Week_9_Notebooks/ | Created — multi-asset grid results |
| WEEK_9_SUMMARY.md | 04_WEEKLY_SUMMARIES/ | Created — this document |
| WEEK_10_THREAD_STARTER.md | 04_WEEKLY_SUMMARIES/ | Created — Week 10 session starter |

---

*Week 9 Summary v1.0*
*Prepared: 2026-06-01 (close-out session)*
*This is a permanent historical record — do not edit after creation*
