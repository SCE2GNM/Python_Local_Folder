# Strategy Risk Register — ETH ADX Trailing Stop

**Strategy:** ETH ADX Trend-Following with ATR Trailing Stop
**Asset / Exchange:** ETHUSDT / Binance Spot (unleveraged → leveraged planned)
**Version:** v2.0 (trailing stop)
**Date created:** 2026-03-20
**Last updated:** 2026-05-04
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

### A003 — Slippage modelled as flat cost, not variable

**Category:** Execution

**Status:** Open

**Priority:** Medium

**Raised:** Week 4 Day 2

**Description:**
Transaction costs modelled at flat 0.15% round-trip. This covers fees and average spread but does not model variable slippage on stop-loss exits during low-liquidity periods (e.g. thin market hours on weekends). Real stop-loss fills may be 0.1–0.5% worse than the stop price in adverse conditions.

**Impact:**
Immaterial at current position sizes (~$124 per trade — extra slippage of ~$0.62 maximum). Becomes meaningful as capital scales. ATR trailing stop is less sensitive to slippage than fixed stop because it exits at a wider, more deliberate distance from peak.

**Fix:**
Monitor actual fill prices vs stop prices once live trading begins. If consistent slippage >0.3% observed, adjust cost model. Compare fixed-stop vs trailing-stop slippage in practice — trailing stop exits tend to be less market-stressed.

**Target:** Week 7 (after 10+ live trades)

**Update log:**
- 2026-05-01: Still open. Cost model updated from 0.175% to 0.15% (confirmed Binance fee, see A004). Slippage monitoring plan unchanged.
- 2026-03-20: Raised. Immaterial at current scale, monitor post-live.

---

### A009 — Walk-forward used fixed parameters, not true rolling re-optimisation

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 5 Day 7

**Description:**
Walk-forward validation in Stage 1c (Week 6) used the single best full-sample parameter set (ADX 19/9, trail 8% or ATR 9/2.5x) and tested its performance across rolling 1-year test windows. Parameters were not re-optimised at the end of each training window before testing. This is less rigorous than true walk-forward where parameters are independently selected per window.

**Impact:**
Stage 1c results are supporting evidence of robustness — 5/6 test years positive, consistent Calmar — but are not conclusive proof of parameter stability. The chosen parameters were selected with knowledge of the full 2018–2026 period. A true walk-forward would be a stricter test. Low signal frequency (15–20 trades/year) makes true walk-forward impractical with current data.

**Fix:**
As live trade history accumulates, use real live performance data as the primary validation source. Consider Combinatorial Purged Cross-Validation (CPCV) when 3+ years of additional live data available.

**Target:** Week 8–10 (when sufficient live data available)

**Update log:**
- 2026-05-01: Still open. Acknowledged in Stage 1c design. Live performance is primary validation path.
- 2026-04-07: Raised. Limitation acknowledged.

---

### A010 — Daily loss limit not calibrated for daily candle strategies

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 5 Extension

**Description:**
The 2% daily loss limit in RiskManager was set from intraday trading norms, not from analysis appropriate for a daily candle strategy. Backtesting showed it fires on normal ETH volatility during open positions — reducing ADX annual return from 67.4% to 8.8% when applied. It was removed from the backtest model but may remain in the live bot.

**Impact:**
If the live bot fires the daily loss limit on a valid open position, it exits unnecessarily and blocks re-entry that day. This directly reduces real returns and introduces execution drift vs backtest.

**Fix:**
Remove the daily loss limit from the live bot, or raise it to a threshold that only fires on genuinely extreme intraday losses (e.g. 8–10%). The per-trade trailing stop and max drawdown guardrail provide sufficient protection without a daily limit.

**Target:** Before trailing stop deployment

**Update log:**
- 2026-05-01: Still open. Must be resolved before deploying new trailing stop logic (A011 resolved but bot update pending).
- 2026-04-12: Raised. Daily loss limit removed from backtest after analysis.

---

### A013 — Margin leverage not yet optimised for ETH ADX

**Category:** Strategy

**Status:** Open

**Priority:** High

**Raised:** Week 5 Extension

**Description:**
Preliminary analysis showed leverage could materially improve returns for ETH ADX (annual return approximately doubles at 2x leverage with interest costs nearly zero at 12.41% Kelly sizing). Optimal leverage level not yet determined. Grid search (1.0x–5.0x, 0.1x steps) not yet run with the new trailing stop configuration.

**Key findings from preliminary (fixed-stop) analysis:**
- Interest accrues hourly on borrowed amount only during open positions
- At 12.41% own fraction, total interest over 108 trades at 2x was ~$30
- Minimum margin ratio stayed above 25% safety buffer at tested leverage levels
- Liquidation checked using daily LOW prices on every bar

**Fix:**
Week 6 Stages 3–4: run leverage grid search using the trailing stop backtest (ATR 9/2.5x or pct 8%) as the base strategy. Update Kelly sizing for new metrics. Document liquidation price and safety buffer at recommended leverage.

**Target:** Week 6 Stages 3–4

**Update log:**
- 2026-05-01: Still open. Must use trailing stop baseline (A011 now resolved) for leverage optimisation.
- 2026-04-12: Raised. Preliminary analysis had hold_days bug (now fixed).

---

### A014 — RiskManager guardrails not calibrated for daily candle strategy

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 5 Extension

**Description:**
The RiskManager guardrails (daily loss limit, max drawdown threshold, stop distance) were set from professional intraday norms, not backtested against ETH ADX specifically. The daily loss limit is known inappropriate (A010). The 15% max drawdown guardrail and the stop distance have not been jointly optimised against the trailing stop configuration.

**Impact:**
Suboptimal guardrail settings reduce strategy performance without proportionate protection. With ATR trailing stop now deployed (A011 resolved), the appropriate max drawdown guardrail may differ from the fixed-stop calibration.

**Fix:**
After trailing stop deployment and 20+ live trades, run joint optimisation of ATR multiplier vs max drawdown guardrail to find the Calmar-maximising combination.

**Target:** Week 7 — after trailing stop live deployment and initial trades

**Update log:**
- 2026-05-01: Still open. Guardrail recalibration depends on trailing stop deployment first.
- 2026-04-12: Raised.

---

### A015 — ADX parameter change (19/9) identified as superior but not yet deployed

**Category:** Strategy

**Status:** Open — decision made, monitoring in progress

**Priority:** Medium

**Raised:** Week 6 Stage 1d (2026-05-01)

**Description:**
Stage 1 optimisation (Weeks 6) found ADX threshold 19, period 9 consistently outperforms the live parameters (threshold 20, period 10) across all stop types and all grid configurations. The best overall combination (ADX 19/9, ATR 9/2.5x) produced Calmar 2.642 vs Calmar 2.013 for the live ADX 20/10 fixed-stop baseline. Stage 1c stability analysis confirmed ADX 19/9 is stable across 5/6 walk-forward test years.

However, the ADX parameter change was identified through in-sample optimisation across 8.3 years of data. The improvement (+0.629 Calmar) is material but has not been validated through true out-of-sample testing. Changing both the ADX parameters AND the stop type simultaneously is two changes at once, which makes attribution harder if live performance deviates.

**Decision (Week 7, 2026-05-03) — UPDATED:**
Primary path selected: deploy ADX 19/9 + percentage trailing stop 8%.

Rationale:
- Candidate A (ADX 19/9, pct 8%) wins on annual return (80.1% vs 73.4%) and Sortino (1.780 vs 1.423).
- Candidate B (ATR) only wins on MaxDD by 3.5pp (−27.8% vs −31.3%) which is ~$52 on $1,500 capital — immaterial at this scale.
- Under the return-first framework with documented drawdown tolerance, A is the correct choice.

Note: this changes two things simultaneously (ADX parameters from 20/10 to 19/9, AND stop type from fixed 5% to pct 8% trailing). If live performance deviates from backtest, attribution of cause will require careful analysis.

Deployment deferred until all Stage 3–5 backtesting is complete. Live bot update to happen at end of Week 6.

**Next review target:** End of Week 6 (deployment). After 20 live trades, compare live metrics to Stage 1d backtest (Calmar 2.557, Sortino 1.780, Annual 80.1%).

**Update log:**
- 2026-05-03: Decision revised. Primary path: ADX 19/9 + pct 8% trailing stop. Annual 80.1% and Sortino 1.780 win vs ATR candidate. MaxDD gap 3.5pp immaterial at $1,500 capital. Deployment deferred to end of Week 6.
- 2026-05-02: Conservative path (ADX 20/10 + ATR 9/2.5x) initially selected. Revised 2026-05-03.
- 2026-05-01: Raised. Stage 1d complete. Deployment path to be chosen in Week 7.

---

### A016 — Tail liquidation risk at 1.9x leverage in extreme crash events

**Category:** Strategy

**Status:** Open — accepted with mitigations documented

**Priority:** High

**Raised:** Week 6 Stage 4 buffer analysis (2026-05-04)

**Description:**
ETH ADX at 1.9x leverage survives the worst historical single-day ETH drop
(−42.9%, 2020-03-12) from a fresh entry: margin ratio falls from 52.6% to
17.0% — below the 25% hard floor but above the 5% liquidation threshold.
However, if the position is at the worst historical backtest margin ratio
(34.4% — observed when an open position has moved against entry by ~35%), the
same −42.9% drop reduces MR to −14.9%: liquidation.

This requires two extreme conditions simultaneously: worst margin drawdown AND
worst single-day price collapse. Probability is low but non-zero. The 2020
COVID crash and 2021 May flash crash demonstrate that extreme events cluster.

**Impact:**
In a combined worst-case scenario, the full leveraged position is liquidated
before the trailing stop fires. This is structurally different from a stop-loss
loss — the account value at liquidation is close to zero (not just a trade loss).
At $1,500 capital, this would be total loss of the leveraged allocation.

**Primary mitigation:**
ATR trailing stop (9/2.5x or pct 8%) has historically exited positions before
the worst intraday lows were reached across 8+ years of backtest data. In every
historical occurrence of a large adverse move, the stop fired in the preceding
period when the peak-to-current drawdown exceeded the stop threshold. The stop
provides genuine protection but is not a mathematical guarantee in gap events.

**Secondary mitigation:**
Margin ratio Telegram alert at 40% provides early warning when MR is declining
toward the danger zone, allowing manual intervention before the extreme scenario
materialises. At 40% MR with a −42.9% drop, resulting MR = 3.5% (near
liquidation) — the 40% alert is therefore the critical early warning level.

**Residual risk:**
Gap events (large overnight price moves between candle close and next open) and
liquidity crises (stop order cannot fill at intended price) can bypass the
trailing stop. These scenarios are structurally unhedgeable at this leverage
level. They are inherent to holding leveraged positions in a 24/7 crypto market.

**Target:** Add margin ratio monitoring (40% alert) to live bot before leveraged
deployment. This is a prerequisite for leveraged ETH ADX live trading.

**Update log:**
- 2026-05-04: Raised. Buffer analysis complete. ETH ADX 1.9× confirmed SAFE
  from fresh entry but VULNERABLE at worst historical MR. Monitoring requirement
  added to LIVE_TRADING_CHECKLIST.md and STRATEGIC_FRAMEWORK.md.

---

## Resolved Items

| ID | Description | Resolution summary | Resolved | Week / Date |
|---|---|---|---|---|
| A001 | Win rate estimated, not measured | Backtest confirmed 34.3% win rate from 108 stop-loss trades | Week 5 Day 2 | 2026-04-07 |
| A002 | Stop-loss not included in backtest | Bar-by-bar stop-loss backtest built using daily LOW prices | Week 5 Day 1 | 2026-04-07 |
| A004 | Binance fee tier unverified | Actual fee confirmed 0.075% maker/taker (0.15% round-trip); conservative assumption confirmed | Week 4 Day 6 | 2026-04-03 |
| A005 | Kelly sizing based on pre-stop-loss metrics | Kelly recalculated at 11.77% with real inputs; difference from 12.41% immaterial | Week 5 Day 2 | 2026-04-07 |
| A006 | Parameters not re-optimised after adding stop-loss | Joint optimisation complete; live ADX 20/10 + 5% stop acceptable; best combo noted | Week 5 Day 3 | 2026-04-07 |
| A007 | Portfolio-level simulator not built | Portfolio simulator built; 5 sizing strategies compared; Kelly confirmed | Week 5 Day 2 | 2026-04-07 |
| A011 | Fixed stop-loss not trailing; trailing stop not backtested | Stage 1 complete (Week 6). ATR trailing stop (ADX 19/9, ATR 9/2.5x) outperforms fixed stop on all metrics: Calmar 2.642 vs 2.013, Max DD −27.8% vs −31.6%, 0.15% round-trip costs included. Percentage trail 8% is close second. Deployment recommendation: ATR 9/2.5x primary, pct 8% secondary. | Week 6 Stage 1d | 2026-05-01 |
| A017 | Live bot used STOP_LOSS_LIMIT since deployment 2026-04-04 | STOP_LOSS_LIMIT creates gap risk: if ETH price gaps below the limit price during a crash, the stop order does not fill and the position remains open with no protection. Fixed 2026-05-04: changed to STOP_LOSS (market execution on trigger) — guaranteed exit at best available price. Also fixed fill price read in check_stop_loss_triggered (market orders return price=0; actual fill = cummulativeQuoteQty / executedQty). Deployed to EC2 and confirmed live. | Week 6 / 2026-05-04 |
| A018 | No Telegram alert on failed order execution — silent failures unreported | Bot deployed 2026-04-04 with no Telegram alert on failed buy/sell/stop orders. Silent failure discovered 2026-05-04: 23 consecutive failed buy attempts (Apr 12 – May 4) went unreported. ADX signal was LONG from Apr 10 at ~$2,245; current price $2,355 (+4.9% missed). Root cause: Binance API key missing "Enable Spot & Margin Trading" permission. Secondary cause: no order-failure alert in bot. Fixed 2026-05-04: (1) Telegram alerts added for all failed orders and all successful trades; (2) daily health check message sent every run; (3) startup API permission check added using create_test_order; (4) API key recreated with trading permission enabled. | Week 6 / 2026-05-04 |

---

## Capital Allocation

| Strategy | Status | Capital | Position Size | Notes |
|---|---|---|---|---|
| ADX 20/10 ETH (fixed stop) | Live | $1,000 | 12.41% Kelly | Live since 2026-04-04; to be replaced by trailing stop version |
| ADX 19/9 ETH (pct 8% trailing stop) | Planned | $1,000 | 12.41% Kelly (recalibrate post-deployment) | Replaces fixed-stop version — not additive |
| ETH ADX (leveraged) | Planned | $1,500 | 100% own capital | Pending A013 (leverage optimisation) |

**Capital scaling rules:**
- Do not increase capital beyond $1,000 until A013 (leverage optimisation) resolved
- Leveraged version replaces unleveraged — not additive — to avoid correlated doubling
- Recalibrate Kelly after 20+ live trades with trailing stop (metrics will differ from fixed-stop baseline)
- Do not deploy leveraged version until A010 (daily loss limit) and A013 both resolved

---

## Review Schedule

| Milestone | Action |
|---|---|
| Before trailing stop deployment | A010 (daily loss limit) resolved; bot mechanics verified against Stage 1d backtest logic |
| Before any capital increase | All High priority items resolved |
| After 20 live trades (trailing stop) | Compare live win rate, profit factor, Calmar vs Stage 1d backtest; review A015 (ADX param change) |
| After 50 live trades | Full parameter re-evaluation; consider true walk-forward on updated data |
| Before leveraged deployment | A013 and A014 resolved; liquidation price documented; safety buffer confirmed ≥25% |
| Sharpe < 0.5 over 30 live trades | Pause live trading, full strategy review |
| Week 7 (complete) | A015 decision updated: primary path — ADX 19/9 + pct 8% trailing stop. Deployment at end of Week 6 backtesting. |
| Every 6 months | Full parameter re-evaluation on rolling window |
