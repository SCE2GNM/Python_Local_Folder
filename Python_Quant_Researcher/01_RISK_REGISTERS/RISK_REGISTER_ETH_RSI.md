# Strategy Risk Register — ETH RSI Mean Reversion

**Purpose:** Tracks every known risk for the ETH RSI mean-reversion strategy. RR-RSI-001 (win rate sensitivity), RR-RSI-003 (Kelly sizing), RR-RSI-010 (entry without confirmed stop), and RR-RSI-011 (Sortino below threshold — accepted) are the current open items requiring attention before capital scaling.
**Who reads it:** Greg before any capital change. Claude Code when modifying the RSI bot.
**When updated:** Whenever a new risk is identified, or an existing item's status changes.
**Related documents:** RISK_REGISTER_ETH_ADX.md, LIVE_TRADING_CHECKLIST.md, ETH_RSI_Deployment_Card_v1.html.

---

**Strategy:** ETH RSI Mean Reversion (RSI-14, oversold bounce)
**Asset / Exchange:** ETHUSDT / Binance Spot
**Version:** v1.3
**Date created:** 2026-05-06
**Last updated:** 2026-06-24
**Updated by:** Greg + Claude

---

## How to Use This Register

Review before each deployment and before any capital increase.
All High priority open items must be resolved before deployment or capital increase.
Medium priority items must be resolved or formally accepted with written rationale.

| Field | Meaning |
|---|---|
| ID | Unique reference |
| Category | Strategy / Execution / Infrastructure / Data / Live Performance |
| Status | Open / In Progress / Resolved |
| Priority | High / Medium / Low |
| Target | When this item will be addressed |

---

## Open Items

---

### RR-RSI-001 — Win rate sensitivity: negative Kelly below 72.2%

**Category:** Strategy

**Status:** Open

**Priority:** High

**Raised:** 2026-05-06 (independent review)

**Description:**
The strategy has a negative Kelly expectation at win rates below 72.2% (breakeven where Kelly fraction = 0). The backtest win rate is 93.5% (29/31 trades), which is almost certainly inflated relative to live performance. Mean reversion strategies in particular are vulnerable to regime shifts — a period of sustained downtrend produces consecutive stop-losses that destroy the high win rate.

Monte Carlo win rate sensitivity (1000 simulations, 31 trades, avg win +5.79%, avg loss −15.00%, 6.49-year horizon):

| Win rate | Scenario | Median ann% | P10% | P90% | P(negative) | Kelly f* | Position |
|---|---|---|---|---|---|---|---|
| 93.5% | Backtest baseline | +22.3% | +14.3% | +30.8% | 0.0% | +76.7% | $495 (capped) |
| 80.0% | Optimistic live | +6.9% | −3.4% | +18.2% | 25.2% | +28.2% | $495 (capped) |
| 75.0% | Moderate live | −0.1% | −9.7% | +10.5% | 55.5% | +10.2% | $341 |
| 70.0% | Pessimistic live | −3.4% | −12.7% | +6.9% | 74.0% | −7.7% | $0 — DO NOT TRADE |
| 65.0% | Stress test | −9.7% | −18.4% | −0.1% | 90.8% | −25.7% | $0 — DO NOT TRADE |

Breakeven win rates:
- (a) Kelly fraction turns positive: **72.2%**
- (b) Median annual return turns positive: **~74.3%**

At 75% win rate (moderate realistic live scenario) the strategy is essentially break-even with 55.5% probability of negative annual return. The strategy only clearly profitable above ~80% win rate.

**Impact:**
If live win rate degrades to 70–75% (plausible), capital is expected to erode. At 65% win rate, 90.8% probability of negative annual return.

**Fix:**
1. Run Monte Carlo analysis before deployment — COMPLETE (2026-05-07).
2. Set initial position size conservatively based on moderate live scenario (75–80% win rate), not backtest win rate.
3. Establish win rate monitoring: after every 10 live trades, calculate running win rate. If running win rate falls below 78% over 20+ trades, pause and review.
4. Do not scale position size until 20 live trades accumulated with win rate ≥ 80%.

**Target:** Before any capital deployed.

**Update log:**
- 2026-05-06: Raised by independent review.
- 2026-05-07: Monte Carlo analysis completed. Results documented above.

---

### RR-RSI-002 — Stop order monitoring absent

**Category:** Infrastructure

**Status:** Resolved

**Priority:** High

**Raised:** 2026-05-06 (independent review)

**Description:**
Binance can silently cancel resting STOP_LOSS orders under certain conditions (account flag, maintenance, order age timeout, or low liquidity on symbol). If the stop order is cancelled without Telegram alert, the position is unprotected and the bot has no awareness of the gap. This has occurred in live ETH ADX trading (first deployment — stop order placed but position unprotected; emergency manual intervention required).

**Impact:**
Full position exposure with no stop protection. At $500 capital and 15% stop distance, unprotected downside = $75. In an extreme move (e.g. −50%), loss = $250 (50% of capital) with no automated exit.

**Fix:**
Bot must verify stop order ID is still ACTIVE on Binance on every scheduled run while in position (both signal and stop_update runs). Implementation:
```
order = client.get_order(symbol='ETHUSDT', orderId=state['stop_loss_order_id'])
if order['status'] != 'NEW':
    # Either triggered (handle as stop hit) or cancelled (re-place immediately)
    send_telegram("🚨 Stop order missing — re-placing")
    place_stop_loss(...)
```
If order is FILLED: process as stop trigger.
If order is CANCELLED or not found: re-place immediately and Telegram alert.

**Target:** Before bot deployment to live capital.

**Update log:**
- 2026-05-06: Raised by independent review.
- 2026-06-21: Resolved. verify_stop_order() confirmed present in
rsi_production_bot.py (lines 282–377), called on every run at
Step 2.5 when position is LONG. Handles all four cases: stop active,
stop filled silently, stop cancelled, exception. Code ahead of
register — closing now.

---

### RR-RSI-003 — Kelly fraction uncapped: $2,555 position on $500 capital

**Category:** Strategy

**Status:** Open

**Priority:** High

**Raised:** 2026-05-06 (independent review)

**Description:**
At the backtest win rate of 93.5%, Kelly fraction f* = 76.7%. Correct position size formula: position = (f* × capital) / stop% = (0.767 × $500) / 0.15 = **$2,555**. This requires 5.1× leverage, which is not available on Binance Spot and not appropriate for an unleveraged strategy. The unleveraged cap constrains position to $495 ($500 − $5 fee buffer).

True risk per trade at $495 position and 15% stop: $495 × 15% = **$74.25 = 14.85% of capital**. This is within acceptable range but is effectively full-Kelly risk at maximum unleveraged sizing.

At realistic live win rates (75–80%), Kelly fraction drops sharply:
- 80% win rate: Kelly 28.2% → Kelly position $940 (still capped at $495)
- 75% win rate: Kelly 10.2% → Kelly position $341 (below cap — use $341)

**Impact:**
At 75% live win rate, deploying $495 exceeds Kelly-optimal position. Over-sizing relative to Kelly accelerates capital erosion when win rate is below expectation.

**Fix:**
Set initial position size based on the **moderate live scenario (75% win rate)** rather than backtest win rate:
- Initial deployment: $341 (Kelly-optimal at 75% win rate)
- Scale to $495 only after 20 live trades with running win rate ≥ 80%
- Recalculate Kelly fraction after each block of 10 live trades

**Target:** Before any capital deployed.

**Update log:**
- 2026-05-06: Raised by independent review.
- 2026-05-07: Position sizing recommendation set. Initial deployment: $341.

---

### RR-RSI-004 — Sample size: 31 trades insufficient for reliable statistical inference

**Category:** Strategy

**Status:** Open

**Priority:** Major

**Raised:** 2026-05-06 (independent review)

**Description:**
31 backtest trades over 6.5 years. At 93.5% observed win rate, the 95% confidence interval on win rate spans approximately 79%–99% (using Wilson interval). The lower bound (79%) is already a scenario where 25% of live years are negative. With only 31 trades, the win rate estimate has high uncertainty — a single additional loss from a 32nd trade changes win rate from 93.5% to 90.6%.

**Impact:**
Backtest metrics (Sortino, Calmar, annual return%) are all conditional on the 93.5% win rate holding. Each metric has wide confidence intervals that are not disclosed by reporting point estimates alone.

**Fix:**
- Accept that backtest metrics are indicative, not precise.
- Use Monte Carlo confidence intervals (documented in RR-RSI-001) as the deployment-basis estimates.
- Do not adjust position sizing based on live results until minimum 20 live trades accumulated.
- Flag in deployment document that 95% CI on win rate spans 79%–99%.

**Target:** Accept and document before deployment. Reassess after 20 live trades.

**Update log:**
- 2026-05-06: Raised by independent review.

---

### RR-RSI-005 — 120MA regime filter: data-mining risk

**Category:** Strategy

**Status:** Resolved — accepted with written rationale

**Priority:** Major

**Raised:** 2026-05-06 (independent review)

**Description:**
The 120-day MA regime filter (only trade when price > 120MA) was selected during optimisation on 2018–2026 data. It has not been independently validated on out-of-sample data. The filter may be inadvertently selecting for the specific bull-market regimes present in the backtest period rather than identifying a structural signal that will persist. The 2018–2026 window contains two major bear markets (2018–2019, 2022) and three bull runs (2020–2021, 2023, 2025) — the filter may be calibrated to those specific bear market characteristics.

**Impact:**
If regime filter is overfitted, it may fail to exclude the next bear market period. The consequence is a series of stop-losses during a sustained downtrend, rapidly degrading win rate toward the 65–70% danger zone.

**Fix:**
- Acknowledge risk explicitly in deployment document.
- Monitor performance during any sustained price decline below 120MA — strategy should sit in cash during this period. If signals occur below 120MA (due to whipsaw), flag immediately.
- Add 120MA filter status to daily health check Telegram message.

**Target:** Document and accept before deployment. Full re-evaluation after 50 live trades.

**Update log:**
- 2026-05-06: Raised by independent review.
- 2026-05-27: Resolved. Stability grid confirmed SMA period 90–150 range does not create fragility — 120MA filter is robust across the full tested range. Formally accepted with this evidence. No code change required.

---

### RR-RSI-006 — Stability analysis not completed

**Category:** Strategy

**Status:** Resolved — STABLE classification confirmed

**Priority:** Major

**Raised:** 2026-05-06 (independent review)

**Description:**
STABLE / MARGINAL / FRAGILE classification has not been run on the RSI strategy parameters. The research pipeline requires this before deployment. Without it, there is no evidence that the chosen parameters (RSI period 14, oversold threshold, 120MA filter period) sit on a broad performance plateau rather than a narrow peak. A FRAGILE result would indicate the strategy is likely overfitted and performance is concentrated in a small parameter region.

**Impact:**
If parameters are FRAGILE, small natural variation in market structure could shift performance sharply. Would also raise confidence score penalty in confidence-based capital allocation framework.

**Fix:**
Run stability analysis before deployment: vary RSI period (10–18), oversold threshold (±2), 120MA period (90–150). Count what fraction produce composite score ≥ 0.7 (or equivalent metric). Classify STABLE/MARGINAL/FRAGILE.

**Target:** Before deployment decision. Week 7.

**Update log:**
- 2026-05-06: Raised by independent review.
- 2026-05-27: Resolved. STABLE — 314/314 full-grid parameter combinations profitable, 27/27 neighbourhood combinations (RSI period ±2, oversold threshold ±2, SMA period ±30) profitable. No fragility identified. RR-RSI-005 (120MA data-mining risk) also resolved in the same analysis.

---

### RR-RSI-008 — Phase 3D joint optimisation not completed

**Category:** Strategy / Methodology

**Status:** Open

**Priority:** Medium

**Raised:** 2026-06-01 (STRATEGY_RESEARCH_PIPELINE.md v2.0 update)

**Description:**
STRATEGY_RESEARCH_PIPELINE.md Phase 3D (added 2026-06-01) requires that entry
parameters, exit method, and regime filter be jointly optimised in a combined grid
before selecting the deployed configuration. The ETH RSI strategy parameters were
optimised sequentially:

- Entry (RSI period 14, oversold threshold 43, exit threshold 48): selected from
  full-sample grid search
- Regime filter (SMA-120): chosen by design, informed by ETH ADX precedent
- Exit (RSI exit threshold 48 + 15% fixed stop): selected from initial backtest

No joint grid was run combining top entry combinations × regime filter variants ×
stop distances. The deployed parameters may not be the jointly-optimal combination.

**Impact:**
Moderate. The strategy is deployed at $341 with conservative sizing (see RR-RSI-003).
The sequential optimisation may have missed interactions between RSI thresholds,
SMA period, and stop distance. However, the Monte Carlo (RR-RSI-001) shows the
strategy is viable at its current configuration.

**Fix:**
Complete Phase 3D joint optimisation before capital scaling beyond $341. Run a combined
grid: RSI period [12, 14, 16] × oversold threshold [40, 43, 46] × SMA period [100, 120,
150] × stop [12%, 15%, 18%]. Rank by post-break PF (post-Jan 2024), not full-period.
If current parameters (14/43/48/SMA-120/15%) are confirmed near-optimal by the joint
grid, scale capital. If a materially better combination is found, consider redeployment.

**Target:** Before first capital scaling review (when 20 live trades accumulated)

**Update log:**
- 2026-06-01: Raised. New pipeline standard (Phase 3D). Capital scaling to $495 must
  not occur until joint optimisation confirms current parameters are near-optimal.

---

### RR-RSI-009 — Phase 3C regime filter period not formally selected via sensitivity analysis

**Category:** Strategy / Methodology

**Status:** Open

**Priority:** Low

**Raised:** 2026-06-01 (STRATEGY_RESEARCH_PIPELINE.md v2.0 update)

**Description:**
STRATEGY_RESEARCH_PIPELINE.md Phase 3C (added 2026-06-01) requires testing SMA-50,
SMA-100, SMA-120, SMA-200, and EMA-50 as entry gates, with formal comparison by
post-break PF. The ETH RSI strategy uses SMA-120 as its regime filter, but this
period was chosen by design (consistency with ETH ADX precedent and general curriculum
convention) rather than selected via sensitivity analysis.

RR-RSI-006 (stability analysis not completed) partially addresses this, as the
stability grid should include SMA period variation. However, a dedicated Phase 3C
filter comparison (SMA-50/100/120/200/EMA-50 tested as isolated variable with all
other parameters held constant) has not been run. The current RR-RSI-006 is Medium
priority; this item is separate and lower priority since SMA-120 is the established
curriculum standard and likely close to optimal.

**Impact:**
Low. SMA-120 is used across ETH ADX, ETH RSI, and BNB Donchian. Its regime-filtering
effect is well-understood. The risk is that a shorter period (e.g. SMA-100 or SMA-80)
might improve signal frequency without degrading quality, or a longer period (SMA-150)
might improve bear-market protection. Neither has been quantified.

**Fix:**
Include SMA filter period as a dimension in the Phase 3D joint optimisation (RR-RSI-008).
The combined grid automatically covers this variation. No separate analysis required if
3D joint grid is run first.

**Target:** Resolved implicitly when RR-RSI-008 (Phase 3D joint optimisation) is complete

**Update log:**
- 2026-06-01: Raised. New pipeline standard (Phase 3C). Will be resolved implicitly
  via RR-RSI-008 joint grid if SMA period is included as a grid dimension.

---

### RR-RSI-010 — Stop entry proceeds even if stop placement fails

**Category:** Execution

**Status:** Open

**Priority:** Low — escalates to High before capital scaling beyond $150

**Raised:** 2026-06-21

**Description:**
If the stop order fails to place at entry, the bot records the
position as LONG with stop_loss_order_id = None and proceeds.
The verify_stop_order() function catches this on the next run via
the "no ID" branch and sends a Telegram alert. However, the entry
itself does not block or reverse if the stop cannot be confirmed.
This means there is a window between entry and the next cron run
where the position is open with no stop protection and no
automated exit.

**Impact:**
Low at $150 capital — maximum unprotected exposure approximately
$22 ($150 × 15% stop). Accepted at current scale. Becomes
material at $341+ where unprotected exposure rises to $51+.

**Fix:**
Before capital is scaled beyond $150, modify the entry logic so
that if stop placement fails, the bot immediately sells back the
ETH just purchased and sends a Telegram alert: "Trade aborted —
stop placement failed. Position closed." No open position should
exist without a confirmed stop order ID.

**Target:** Before capital scaling beyond $150 (i.e. before
RR-RSI-001 and RR-RSI-003 conditions are met)

**Update log:**
- 2026-06-21: Raised. Gap identified during Week 10 code audit.
Option A accepted at $150 — entry proceeds with alert. Option B
(abort entry) required before scale-up.

---

### RR-RSI-011 — Daily equity Sortino below deployment threshold

**Category:** Methodology

**Status:** Open — accepted at current capital level

**Priority:** Medium — review before scaling beyond $150

**Raised:** 2026-06-21

**Description:**
The correct daily equity curve Sortino for ETH RSI is 0.307,
computed in stage5_final_comparison.py. This is below the
programme's standard deployment threshold of 0.8. The strategy
was deployed at $150 validation capital without this being
formally documented.

The low Sortino is a methodological artefact: ETH RSI trades
approximately 5 times per year. The daily equity curve method
counts approximately 360 flat (cash) days per year as near-zero
daily returns, which suppresses the mean return in the Sortino
numerator without adding downside risk. The strategy's actual
trade-level metrics are strong: win rate 93.5%, profit factor
5.593, 3/3 walk-forward windows profitable.

**Acceptance rationale:**
The daily equity Sortino is an inappropriate primary quality
metric for strategies with fewer than 10 trades per year.
Supplementary quality checks all pass. Deployment at $150
accepted as validation capital. Daily equity Sortino is
retained as a reported metric but is not the primary
deployment gate for this strategy type.

**Correct alternative metrics for low-frequency strategies:**
- Profit factor > 2.0: PASS (5.593)
- Win rate > 80%: PASS (93.5%)
- Walk-forward pass rate > 60%: PASS (100%)
- Post-break profit factor > 1.5: PENDING (insufficient
  post-break trades to confirm)

**Fix required before scaling:**
Before capital is scaled beyond $150, confirm that 10+ live
trades maintain win rate >= 80% and profit factor >= 2.0.
These replace the Sortino gate for this strategy type.

**Update log:**
- 2026-06-21: Raised. Correct Sortino of 0.307 identified
  from stage5_final_comparison.py (daily equity method).
  Strategy archive S002 corrected from stale 1.205 figure.
  Accepted at $150 with supplementary metrics as quality gate.

---

### RR-RSI-012 — Multiple Testing Assessment (Deflated Sharpe Ratio)

**Category:** Statistical Validity

**Status:** Open

**Priority:** High — governs capital scaling decision

**Raised:** 2026-06-24

**Description:**
ETH RSI was selected from a grid search of 13,475 backtested combinations (5,452 ranked). The Deflated Sharpe Ratio (DSR) adjusts the observed performance for this search-space penalty.

**Inputs (all from actual data files):**
- Per-trade Sharpe: 0.7224 (mean/std of 31 trade returns)
- Number of trades: 31
- Return skewness: -1.9468 (negative — left tail, fat wins)
- Excess kurtosis: 5.2352 (fat tails)
- SE inflation factor: 1.83x (non-normal distribution penalty)
- Effective independent trials: ~78 (conservative estimate accounting for correlated grid combinations)

**DSR Results:**
- PSR with no penalty (SR0=0): 0.9847
- DSR at N=78 (realistic): 0.9240 — MARGINAL
- DSR at N=320 (includes Bollinger search): 0.9016 — MARGINAL
- DSR at N=5,452 (worst case): 0.8540 — MARGINAL
- Standard bar for credible edge: DSR > 0.95

**Conclusion:**
The edge is probably real but not conclusively proven. DSR range 0.85-0.92 across all realistic trial assumptions — consistently marginal, consistently short of the 0.95 bar.

**Two additional fragilities:**
1. The result rests on only 2 losing trades. The 95% confidence interval on the true win rate is [0.793, 0.982]. At the lower bound, PF drops to 1.48 — barely above break-even.
2. Approximately 7 post-ETF (post-May 2024) trades exist. The strategy is effectively unvalidated in the current market regime.

**Scaling conditions (hard blocks):**
- Minimum 20 live trades before any scaling decision
- Live win rate must hold >= 80% across those 20 trades
- Live profit factor must hold >= 2.0 across those 20 trades
- No consecutive loss streak of 4 or more

**Capital decision:**
Hold at $150 validation capital until all four scaling conditions are met. At ~4.8 trades/year this represents approximately 4 years of live data — correctly reflecting that low-frequency strategies cannot be validated faster.

**Reference:** ETH_RSI_DSR_Assessment.pdf (full working including all calculations and fragility checks)

**Update log:**
- 2026-06-24: Raised. DSR assessment completed using Bailey & Lopez de Prado (2014) methodology. All inputs from actual data files. PDF report produced. Conclusion: probably real edge, insufficient evidence to scale. Hold at $150.

---

*(Add further items above this line, preserving the ID sequence)*

---

## Resolved Items

| ID | Description | Resolution summary | Resolved | Week / Date |
|---|---|---|---|---|
| RR-RSI-002 | Stop order monitoring absent | verify_stop_order() implemented in bot. Handles FILLED, CANCELLED, EXPIRED, REJECTED and exception cases. Called every run while LONG. | 2026-06-21 | 2026-06-21 |
| RR-RSI-005 | 120MA regime filter: data-mining risk | Accepted — stability grid confirmed 120MA filter does not create fragility across SMA 90–150 range | 2026-05-27 | Week 9 |
| RR-RSI-006 | Stability analysis not completed | STABLE — 314/314 combinations profitable, 27/27 neighbourhood combos profitable | 2026-05-27 | Week 9 |
| RR-RSI-007 | EXIT_RSI threshold spec/live discrepancy | Documented as low-priority gap; EXIT_RSI=48 confirmed as canonical value; spec updated | 2026-05-27 | Week 9 |

---

## Capital Allocation

| Strategy | Status | Capital | Position Size Method | Notes |
|---|---|---|---|---|
| ETH RSI Mean Reversion | Planned | $500 reserved | Kelly at 75% WR → $341 initial | Scale to $495 after 20 live trades with WR ≥ 80% |

**Capital scaling rules:**
- Do not deploy any capital until RR-RSI-001, RR-RSI-002, RR-RSI-003 resolved
- Initial position size: $341 (Kelly-optimal at 75% win rate, conservative estimate)
- Scale to $495 only after 20 live trades with running win rate ≥ 80%
- Pause trading if running win rate falls below 72% over 20+ trades (approaching Kelly breakeven)
- Full review after 50 live trades: recalculate Kelly, update position sizing

---

## Review Schedule

| Milestone | Action |
|---|---|
| Before any capital deployed | All High priority items resolved |
| After 10 live trades | Calculate running win rate — flag if below 80% |
| After 20 live trades | Compare live WR vs backtest; decide position size scale-up |
| Running WR < 72% over 20+ trades | Pause — strategy at Kelly breakeven, negative expectation probable |
| After 50 live trades | Full parameter re-evaluation, recalculate Kelly fraction |
| Every 6 months | Full parameter re-evaluation on rolling window |

---

*Register version: 1.0 — created 2026-05-07*
*All items from 2026-05-06 independent review incorporated.*

*Version 1.1 — 2026-06-21: RR-RSI-002 resolved, RR-RSI-010 added (Week 10 code audit)*
*Version 1.2 — 2026-06-22: RR-RSI-011 added (Sortino below threshold — accepted at $150). S002 archive corrected from 1.205 to 0.307.*
*Version 1.3 — 2026-06-24: RR-RSI-012 added (Deflated Sharpe Ratio multiple-testing assessment — DSR range 0.85–0.92 across realistic trial counts, marginal; hold at $150 until 20 live trades meet scaling conditions). Week 10 audit Action 9.*
