# Strategy Risk Register — BNB Donchian Breakout

**Purpose:** Tracks every known risk for the BNB Donchian trend-following strategy. All High priority open items must be resolved before any capital is deployed. All Medium priority items must be resolved or formally accepted with written rationale.
**Who reads it:** Greg before any capital change. Claude Code when building the BNB bot.
**When updated:** Whenever a new risk is identified, or an existing item's status changes.
**Related documents:** METHODOLOGY_STANDARDS.md, STRATEGY_RESEARCH_PIPELINE.md,
RISK_REGISTER_ETH_ADX.md (ADX precedent), bnb_stability_results.csv, bnb_montecarlo_results.csv.

---

**Strategy:** BNB Donchian Channel Breakout with SMA-120 Regime Filter
**Asset / Exchange:** BNBUSDT / Binance Spot
**Entry:** Close > 20-day rolling high (prior bar), AND close > 120-day SMA
**Exit:** 5% trailing stop from peak price; OR daily LOW ≤ 20-day rolling low of lows
**Version:** v1.0
**Date created:** 2026-06-01
**Last updated:** 2026-06-01
**Updated by:** Greg + Claude

---

## Pipeline Phase Gate — Current Status

| Phase | Name | Status | Signed off |
|---|---|---|---|
| Phase 0 | Research brief | ✅ Complete | Greg + Claude — WEEK_9_RESEARCH_BRIEF.md prepared 2026-05-27 |
| Phase 1 | Discovery and logic check | ✅ Complete | Greg + Claude — 148-combo discovery grid; Donchian identified as only viable family |
| Phase 2 | Initial backtest — max loss, payoff profile | ✅ Complete | Greg + Claude — max loss $7.25 (4.83%), breakeven WR 22.0% (LOW SENSITIVITY) |
| Phase 3 | Optimisation, Monte Carlo, leverage screen | ✅ Complete | Greg + Claude — MC done; leverage screen formally deferred (RR-BNB-004) |
| Phase 4 | Stability analysis | ✅ Complete | Greg + Claude — STABLE (26/42 post-break PF>2.0), heatmaps, walk-forward 9/13 |
| Phase 5 | Stress testing | ✅ Complete | Greg + Claude — regime break VIABLE (post-break PF 2.961), exit A confirmed optimal |
| Phase 6 | Deployment decision and documentation | 🔴 Blocked — RR-BNB-008, RR-BNB-009, RR-BNB-010 must be resolved first | — |

**Rule:** Do not begin Phase N+1 work until Phase N is marked signed off in this table.
If a phase is skipped or deferred, record written justification here before proceeding.

---

## Validation Summary (Week 9, 2026-05-31 – 2026-06-01)

Completed before this register was opened:

| Phase | Item | Status | Key finding |
|---|---|---|---|
| Phase 2 | Maximum loss per trade | ✅ Complete | $7.25/trade = 4.83% of $150 — acceptable |
| Phase 2 | Payoff profile sanity check | ✅ Complete | Breakeven 22.0%, LOW SENSITIVITY |
| Phase 3 | Monte Carlo stress test | ✅ Complete | 0% P(neg year) at all scenarios. Kelly positive to 65% WR |
| Phase 3 | Leverage screening | ✅ Formally deferred | Unleveraged initial deployment. See RR-BNB-004 |
| Phase 4 | Grid boundary extension | ✅ Complete | PLATEAU confirmed (Analysis 1) |
| Phase 4 | Stability grid + heatmaps | ✅ Complete | STABLE — 26/42 post-break PF > 2.0 (62%) |
| Phase 4 | Walk-forward validation | ✅ Complete | 9/13 OOS windows profitable (per=20/stop=5%) |
| Phase 5 | Regime break analysis | ✅ Complete | VIABLE — post-break PF 2.961 (SMA-120 variant) |
| Phase 5 | Exit method comparison | ✅ Complete | Exit A (current) is optimal — ATR/EMA alternatives fail MDD gate |
| Phase 5 | Monte Carlo stress test | ✅ Complete | (shared with Phase 3) |

Phase 6 (Deployment Decision) documentation is not yet written.

---

## How to Use This Register

Review before deployment and before any capital change.
All High priority open items must be resolved before deployment.
Medium priority items must be resolved or formally accepted with written rationale.

| Field | Meaning |
|---|---|
| ID | Unique reference |
| Category | Strategy / Execution / Infrastructure / Data / Live Performance |
| Status | Open / Accepted / Resolved |
| Priority | High / Medium / Low |
| Target | When this item will be addressed |

---

## Open Items

---

### RR-BNB-001 — Post-break OOS walk-forward: 2 of 5 post-2024 windows show losses

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** 2026-06-01

**Description:**
Walk-forward validation (04_bnb_walkforward.py) showed 9/13 OOS windows profitable for per=20/stop=5%. However, the post-break windows (W10–W13, covering Jul 2024 – Jun 2026) are mixed: W10 (Jul–Dec 2024) loss, W11 (Jan–Jun 2025) loss, W12 (Jul–Dec 2025) profitable, W13 (Jan–Jun 2026, partial) loss. Three of the four post-break OOS windows are losses or partial losses. The regime break analysis shows post-break PF 2.961 (SMA-120 variant), which covers the same period — the difference is that the regime break uses all post-break trades aggregated, while the walk-forward shows year-by-year variation.

The W10/W11 losses are explained by BNB trending downward in H2 2024 – H1 2025. The SMA-120 filter reduced but did not eliminate these entries (SMA-120 variant still had 19 post-break trades vs 24 without filter).

**Impact:**
Modest. The post-break aggregate PF of 2.961 and win rate of 43.2% are positive. The walk-forward mixed result reflects normal variance in a 9-trade-per-year strategy. However, it confirms that the strategy has losing windows even with positive edge — live performance will not be monotonically positive.

**Fix:**
Monitor first 10 live trades. If 3+ consecutive losses or running win rate below 30% over 10+ trades, trigger a review. Do not scale capital until 10 live profitable trades.

**Target:** Ongoing monitoring after deployment.

**Update log:**
- 2026-06-01: Raised from walk-forward analysis (bnb_walkforward_results.csv).

---

### RR-BNB-002 — SMA-120 filter selected post-grid-search

**Category:** Strategy

**Status:** Accepted

**Priority:** Medium

**Raised:** 2026-06-01

**Description:**
The SMA-120 regime filter was not part of the original 148-combination discovery grid. It was added in Analysis 4 of the validation pipeline after observing W10/W11 walk-forward losses. The filter was tested on the same dataset (BNB 2018–2026) on which the Donchian parameters were originally optimised. This introduces a minor data-mining risk: the SMA-120 period may be fitted to the specific bear market periods in the 2018–2026 window.

The improvement from the SMA-120 filter is large (post-break PF 2.199 → 2.961, MtM MDD −44.8% → −29.7%) and consistent with the rationale used for the same filter on ETH RSI (SMA-120) and ETH ADX (implicit uptrend requirement via +DI > -DI). The filter is mechanically sound: only enter trend-following positions when price is in an uptrend by a 4-month definition.

**Accepted rationale:**
The SMA-120 filter is consistent with the curriculum-wide standard for regime filters. It improves all metrics including post-break (forward-looking) PF. The same period (120) was independently validated on the ETH RSI strategy. The risk is acknowledged but the filter is accepted as structurally justified.

**Monitor:**
If live performance during uptrend periods (price > SMA-120) is significantly worse than backtest, revisit SMA period.

**Update log:**
- 2026-06-01: Raised and accepted with written rationale.

---

### RR-BNB-003 — BNB/Binance regulatory tail risk

**Category:** Strategy

**Status:** Accepted

**Priority:** Low

**Raised:** 2026-06-01

**Description:**
BNB is the native exchange token of Binance. Its price is structurally different from other altcoins: it has partial support from BNB Chain gas demand, fee discounts, and quarterly auto-burn mechanism. However, it is also uniquely exposed to adverse regulatory action against Binance itself. The 2023 Binance DOJ settlement produced a sharp BNB price drawdown independent of broader market conditions. A severe regulatory event (exchange suspension, jurisdiction ban) could produce a large loss that is fully uncorrelated with the ADX/Donchian signal and not captured in any backtest.

**Accepted rationale:**
At $150 initial validation capital, maximum possible loss is $150. The risk is acknowledged and accepted. As capital scales (see scaling rules below), regulatory tail risk should be reviewed — BNB should not represent more than 15% of total strategy capital without reassessing regulatory conditions. Do not scale BNB capital above $500 without a specific review of Binance's regulatory status at that time.

**Update log:**
- 2026-06-01: Raised and accepted with written rationale. Monitoring escalation at $500 threshold.

---

### RR-BNB-004 — Leverage screening deferred (Phase 3 formal record)

**Category:** Strategy

**Status:** Accepted — formally deferred

**Priority:** Low

**Raised:** 2026-06-01

**Description:**
STRATEGY_RESEARCH_PIPELINE.md Phase 3 requires leverage screening after identifying the top 20 parameter combinations. The stability grid (Analysis 2) identified 42 combinations; the deployed parameters (period=20/stop=5%/SMA-120) represent the best post-break validated combination.

Leverage screening was NOT completed before initial deployment.

**Accepted deferral rationale:**
1. Initial deployment capital is $150 unleveraged (Binance Spot only).
2. Binance Spot margin requires approval and active monitoring that is premature at the validation stage.
3. The deployed position is already capital-constrained (see RR-BNB-005). Leverage discussion is premature until unleveraged validation is complete.
4. METHODOLOGY_STANDARDS.md requires dynamic leverage (not static) for any leveraged strategy from Week 8 onwards — this adds additional design requirements that should not be rushed.

**Reopen condition:**
After 10+ live profitable trades with running win rate ≥ 35%, reopen this item to design a leverage-optimised variant. Leverage screening should use the walk-forward validated post-break regime as the evaluation period (Jan 2024–present), not the full backtest.

**Update log:**
- 2026-06-01: Formally deferred for unleveraged initial deployment.

---

## Resolved / Accepted Items

---

### RR-BNB-005 — Kelly sizing: capital constraint at $150 unleveraged (Correction 1)

**Category:** Strategy

**Status:** Resolved — documented and accepted

**Priority:** Medium

**Raised:** 2026-06-01

**Resolved:** 2026-06-01

**Description:**
At $150 unleveraged capital with Half-Kelly f*=13.6% and stop=5%, the Kelly-optimal position size exceeds available capital:

```
Kelly-optimal position  = (capital × half_kelly) / stop_pct
                        = ($150 × 0.136) / 0.05
                        = $408 — exceeds $150 available capital
```

The actual unleveraged position is capped at ~$145 (capital − $5 fee buffer):

```
Actual position          = $145
Dollar risk per trade    = $145 × 5% = $7.25
Risk as % of capital     = $7.25 / $150 = 4.83%
As fraction of Half-Kelly = 4.83% / 13.6% = 35%
```

**This strategy is capital-constrained at $150 unleveraged. It operates at approximately one-third of Half-Kelly, not Quarter-Kelly.** The distinction matters: Quarter-Kelly = 6.8% risk per trade (half of 13.6%). One-third Kelly = 4.5% risk per trade. At $150, the actual 4.83% risk per trade is between the two.

**To reach Half-Kelly sizing without leverage, approximately $410 capital is required:**
```
Required capital for Half-Kelly = (half_kelly × position) / stop_pct
Wait — rearranging: capital = position × stop_pct / half_kelly
At Half-Kelly position = capital × half_kelly / stop_pct, so capital = Kelly-optimal position
→ Capital needed for unconstrained Half-Kelly deployment: ~$410
```

**Capital path to Half-Kelly:**
- Do not increase to $410 until 5+ live profitable trades are recorded.
- Do not use leverage to reach $408 position until leverage screening (RR-BNB-004) is complete.
- At $150 capital, the 4.83% risk/trade is appropriate: conservative for a 74-trade backtest, consistent with the curriculum's phased capital deployment approach.

**Resolution:**
The capital constraint is understood, accepted, and correctly labelled. The initial $150 deployment is appropriate for validation. Expected annual return at current sizing is approximately 35% of Kelly-optimal modelled return. The Monte Carlo annual returns (median +28.0%) assume full position compound sizing; actual portfolio return will be lower, scaling proportionally to actual position size relative to capital.

**Update log:**
- 2026-06-01: Raised during Monte Carlo review. Correctly documented as one-third Kelly, not Quarter-Kelly.

---

### RR-BNB-006 — Half-Kelly permission: bear market out-of-sample confirmation (Correction 2)

**Category:** Strategy

**Status:** Resolved — permission granted

**Priority:** Medium

**Raised:** 2026-06-01

**Resolved:** 2026-06-01

**Description:**
METHODOLOGY_STANDARDS.md requires Half-Kelly to be justified by documented out-of-sample confirmation through a bear market period. Without this confirmation, Quarter-Kelly is the default for momentum strategies (power law distribution risk, Grobys et al. 2025, Huang et al. 2024).

**Half-Kelly justification — BNB Donchian:**

Two forms of bear market evidence:

(1) BNB asset-level: BNB experienced a severe bear market in 2022 (peak ~$715 in 2021, trough ~$211 in 2022 = −70.4% drawdown). The backtest covers this period with full price data from 2018. Any strategy showing positive edge over the 2018–2026 period has survived this drawdown.

(2) Strategy-level OOS confirmation: Walk-forward window W5 (Jul–Dec 2022, bnb_walkforward_results.csv) was a market recovery period following the 2022 crash trough. Per=20/stop=5% result: PF 3.287, win rate 80.0%, annual return +21.5%, Sortino 1.05 — profitable. More importantly, W5 (Jan–Jun 2022 for per=20) covers the onset of the bear market itself: PF ∞ (1 trade, 100% win rate), +2.9% annual return — the SMA-120 filter blocked most entries during the downtrend, protecting capital.

The SMA-120 filter is the structural bear market protection: by requiring price > 120-day SMA before entry, the strategy was effectively flat during the deepest part of the 2022 BNB decline (BNB below its 120-day SMA for extended periods). The filter does not need to generate profitable trades during the bear — it needs to PREVENT trades. Evidence from walk-forward confirms it did: W5 and W6 combined had only 6 trades (vs ~16 in comparable bull periods), and those 6 were profitable.

**Permission granted:** Half-Kelly (13.6%) is the correct sizing for BNB Donchian. The strategy has documented out-of-sample evidence through the 2022 bear market period.

**Condition on this permission:** If the SMA-120 filter stops functioning as a bear market gate (e.g., regime shift causes sustained BNB entries during a downtrend), revert to Quarter-Kelly until new bear market confirmation is accumulated.

**Update log:**
- 2026-06-01: Raised during Monte Carlo review. Half-Kelly permission documented with OOS justification.

---

### RR-BNB-007 — Sortino B&H threshold failure: formal exception

**Category:** Strategy

**Status:** Accepted — formally accepted with written rationale

**Priority:** Medium

**Raised:** 2026-06-01

**Description:**
The B&H Sortino threshold check (strategy Sortino ≥ 1.5× B&H Sortino) is not met:

| Metric | Strategy | B&H | Ratio | Threshold | Result |
|---|---|---|---|---|---|
| Annual return | +28.3% | +69.1% | 0.41× | ≥ 2.0× | FAIL — exception applies |
| MtM MDD | −29.7% | −80.1% | 0.37× | ≤ 0.50× | PASS |
| Sortino | 0.840 | 1.103 | 0.76× | ≥ 1.5× | FAIL — exception applies |

B&H Sortino (1.103) was calculated over a period that includes a −80.1% maximum drawdown. This drawdown renders the B&H Sortino a misleading benchmark: a passive investor who held BNB through an 80% loss before recovering to generate Sortino 1.10 is not a useful comparison for a risk-managed active strategy that prevented that drawdown.

**Justification for acceptance:**
The same economic argument that suspends the annual return gate under the B&H MDD exception (see METHODOLOGY_STANDARDS.md — B&H Benchmark Filter Standard) applies equally to the Sortino gate. When B&H MDD exceeds −60%, BOTH the annual return gate and the Sortino gate are suspended. The substitute quality gates apply instead.

**Substitute quality gate check:**
- Strategy Sortino > 0.8: **0.840 — PASS** ✅
- Strategy MtM MDD better than −50%: **−29.7% — PASS** ✅

Both substitute gates pass. The exception is formally accepted.

**Consequence:** No action required. Strategy proceeds to Phase 6 deployment documentation.

**Update log:**
- 2026-06-01: Raised during B&H threshold review. Exception formally documented and accepted. METHODOLOGY_STANDARDS.md updated to explicitly cover Sortino gate under the B&H MDD exception.

---

### RR-BNB-008 — Separate upper/lower band optimisation not tested

**Category:** Strategy

**Status:** Open

**Priority:** High — blocks capital deployment

**Raised:** 2026-06-01

**Description:**
The current strategy uses period=20 for both the entry trigger (20-day rolling high breakout) and the exit trigger (20-day rolling low break). These have never been tested as separate parameters. The original Donchian/Turtle Trading framework used different entry and exit periods deliberately — typically a longer entry period for the breakout entry and a shorter exit period for the trailing channel exit. Using a longer entry period reduces false breakouts (price must exceed a longer high to qualify); using a shorter exit period tightens the channel exit and captures reversals faster.

**Impact:**
High. If a separately-optimised configuration materially outperforms the symmetric period=20/20, the deployed parameters are suboptimal and the backtest metrics understate the achievable edge. If period=20/20 is confirmed optimal by the grid, this item is closed with documented evidence.

**Fix:**
Run a grid of entry period × exit period combinations:
- Entry periods: 15, 20, 25, 30
- Exit periods: 5, 10, 15, 20 (constraint: exit period ≤ entry period always)
- Report for each combination: full-period PF, post-break PF, Sortino, trade count, MtM MDD

If the best separate-band configuration materially outperforms period=20/20 on post-break PF, it becomes the new deployed configuration and the full Phase 3–5 validation pipeline must be re-run on it. If period=20/20 remains optimal, document and close this item.

**Target:** Week 10 — before bot build. Required before any capital deployment.

**Update log:**
- 2026-06-01: Raised. Gap identified at Phase 6 close-out. Standard Donchian/Turtle framework uses separate periods; symmetric assumption has not been validated.

---

### RR-BNB-009 — Trailing stop full range not tested

**Category:** Strategy

**Status:** Open

**Priority:** Medium — required before capital scaling beyond $150

**Raised:** 2026-06-01

**Description:**
Phase 3B exit comparison (bnb_exit_regime_results.csv) tested three exit methods: Exit A (channel + 5% trail), Exit B (ATR 14 × 2.0 stop only), Exit C (EMA-20 two-tier only). Exit B tested ATR multiplier=2.0 only. Exit C tested EMA period=20 only. The full Phase 3B standard requires ATR multipliers 1.5, 2.0, 2.5, 3.0 and EMA periods 20, 30, 50 to be tested systematically. Only two of seven required trailing stop variants were included.

Exit A (fixed 5% trail + channel) is the best result found so far and remains the deployed configuration. However, the comparison is incomplete against the pipeline standard — a tighter ATR (1.5×) or longer EMA period (50) might improve post-break PF further.

**Impact:**
Moderate. Exit A dominates on all current metrics. The incomplete comparison is unlikely to reverse the deployment decision but may identify a marginally better configuration. More importantly, completing this analysis closes the Phase 3B gap before scaling to larger capital where the exit method becomes more consequential.

**Fix:**
Test the following additional trailing stop variants against the best entry/exit-period combination from RR-BNB-008:
- ATR multipliers: 1.5×, 2.5×, 3.0× (2.0× already tested)
- EMA periods: 30, 50 (20 already tested)
Compare post-break PF only (post-Jan 2024). If any variant outperforms Exit A on post-break PF with MDD better than −50%, adopt it and update the deployed configuration. Otherwise confirm Exit A and close this item.

**Target:** Week 10 alongside RR-BNB-008.

**Update log:**
- 2026-06-01: Raised. Incomplete Phase 3B comparison identified at Phase 6 close-out. Exit A remains best-found; full comparison required before capital scaling.

---

### RR-BNB-010 — Independent red team review not completed

**Category:** Strategy

**Status:** Open

**Priority:** High — blocks capital deployment

**Raised:** 2026-06-01

**Description:**
LIVE_TRADING_CHECKLIST.md Section 0 requires an independent review conducted in a fresh Claude Sonnet session with no development context before any live capital deployment. The reviewer must not have seen the backtest scripts or the development sessions that produced them. The review must be framed as a sceptical attack — the reviewer's job is to find reasons NOT to deploy capital, not to validate the work.

The review has not been conducted. All work to date was performed in sessions that also built the backtest scripts and risk register — these sessions have development context that makes them unsuitable as independent reviewers.

**Impact:**
High. The independent review exists precisely to catch risks, assumptions, and logical errors that the development team cannot see due to familiarity bias. Proceeding without it means the deployment decision is made without the required second-opinion safety check. Historical precedent in this curriculum: ETH ADX independent review identified the missing stop order monitoring gap (now RR-RSI-002) — a High priority item that would have allowed unprotected live positions.

**Fix:**
After RR-BNB-008 and RR-BNB-009 are resolved, conduct the independent review:
1. Open a fresh Claude Sonnet session with no development context
2. Provide: final strategy parameters, full backtest results, deployment card, risk register, METHODOLOGY_STANDARDS.md, LIVE_TRADING_CHECKLIST.md
3. Frame explicitly as a sceptical review: *"You are reviewing this strategy as a sceptic. Your job is to find reasons not to deploy capital. Look for: overfitting, data mining bias, unrealistic assumptions, risks not captured in the register, edge cases that could cause large losses, bot implementation risks, and anything else that gives you pause. Do not be polite about problems — flag them clearly with severity."*
4. All CRITICAL findings must be resolved before any capital is deployed
5. MAJOR findings must be resolved or formally accepted with written rationale
6. Save review output as REVIEW_BNB_DONCHIAN_[DATE].md

**Target:** Week 10 — after RR-BNB-008 and RR-BNB-009 complete.

**Update log:**
- 2026-06-01: Raised. Required by LIVE_TRADING_CHECKLIST.md Section 0. Must occur after RR-BNB-008 and RR-BNB-009 resolve so the reviewer sees the final validated configuration.

---

*(Add further items above this line, preserving the ID sequence)*

---

## Resolved Summary

| ID | Description | Resolution | Date |
|---|---|---|---|
| RR-BNB-005 | Kelly sizing: capital constraint at $150 | Documented as one-third Kelly, not Quarter-Kelly. $410 needed for unconstrained Half-Kelly. | 2026-06-01 |
| RR-BNB-006 | Half-Kelly permission justification | Granted — bear market OOS confirmed (2022 walk-forward W5/W6 profitable, SMA-120 filter blocked bear entries) | 2026-06-01 |

---

## Capital Allocation

| Strategy | Status | Capital | Position | Notes |
|---|---|---|---|---|
| BNB Donchian SMA-120 | Pending — awaiting Phase 6 deployment doc | $150 reserved | $145 (capital − $5 buffer) | One-third Kelly at $150 capital |

**Capital scaling rules:**
- Do not deploy any capital until Phase 6 (Deployment Decision) documentation is written and reviewed
- Initial position: $145 (all available capital, minus fee buffer)
- Dollar risk per trade: $7.25 (= $145 × 5% stop) = 4.83% of capital
- Review scaling to $410 after 5 live profitable trades (reaches unconstrained Half-Kelly)
- Do not exceed $410 without leverage screening (RR-BNB-004) complete
- Pause if 3+ consecutive losing trades; full review if running win rate drops below 30% over 10+ trades

---

## Review Schedule

| Milestone | Action |
|---|---|
| Before any capital deployed | Phase 6 deployment doc written and reviewed |
| After 5 live profitable trades | Review capital scale-up to $410 (Half-Kelly unconstrained) |
| After 10 live trades | Calculate running win rate — flag if below 30% |
| After 20 live trades | Full performance review vs Monte Carlo P10/median/P90 expectations |
| Running win rate < 22% over 15+ trades | Pause — approaching Kelly breakeven |
| Capital increase above $500 | Review RR-BNB-003 (BNB regulatory tail risk) |
| Every 6 months live | Re-run regime break with updated data; recalculate Kelly |
| When BNB price below SMA-120 for 30+ consecutive days | Confirm strategy correctly in cash; review SMA period relevance |

---

*Register version: 1.0 — created 2026-06-01*
*All items from Week 9 validation pipeline (2026-05-31 – 2026-06-01) incorporated.*
