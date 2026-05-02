# Strategy Risk Register — ETH ADX Trailing Stop

**Strategy:** ETH ADX Trend-Following with ATR Trailing Stop
**Asset / Exchange:** ETHUSDT / Binance Spot (unleveraged → leveraged planned)
**Version:** v2.0 (trailing stop)
**Date created:** 2026-03-20
**Last updated:** 2026-05-01
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

**Status:** Open

**Priority:** Medium

**Raised:** Week 6 Stage 1d (2026-05-01)

**Description:**
Stage 1 optimisation (Weeks 6) found ADX threshold 19, period 9 consistently outperforms the live parameters (threshold 20, period 10) across all stop types and all grid configurations. The best overall combination (ADX 19/9, ATR 9/2.5x) produced Calmar 2.642 vs Calmar 2.013 for the live ADX 20/10 fixed-stop baseline. Stage 1c stability analysis confirmed ADX 19/9 is stable across 5/6 walk-forward test years.

However, the ADX parameter change was identified through in-sample optimisation across 8.3 years of data. The improvement (+0.629 Calmar) is material but has not been validated through true out-of-sample testing. Changing both the ADX parameters AND the stop type simultaneously is two changes at once, which makes attribution harder if live performance deviates.

**Options:**
1. Deploy trailing stop with live ADX 20/10 (conservative — ATR 9/2.5x gives Calmar 2.156, +0.143 vs baseline)
2. Deploy trailing stop with ADX 19/9 (primary recommendation — Calmar 2.642, +0.629 vs baseline)

**Fix:**
Two paths depending on risk appetite:
- Conservative: deploy ADX 20/10 + ATR 9/2.5x first, accumulate 20+ live trades, then evaluate ADX parameter change
- Primary: deploy ADX 19/9 + ATR 9/2.5x, monitor for 20+ live trades, compare to backtest

**Target:** Week 7 decision point — choose deployment path

**Update log:**
- 2026-05-01: Raised. Stage 1d complete. Deployment path to be chosen in Week 7.

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

---

## Capital Allocation

| Strategy | Status | Capital | Position Size | Notes |
|---|---|---|---|---|
| ADX 20/10 ETH (fixed stop) | Live | $1,000 | 12.41% Kelly | Live since 2026-04-04; to be replaced by trailing stop version |
| ADX 19/9 ETH (ATR trailing stop) | Planned | $1,000 | 12.41% Kelly (recalibrate post-deployment) | Replaces fixed-stop version — not additive |
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
| Week 7 | Choose deployment path for A015 (ADX 20/10 conservative vs ADX 19/9 primary) |
| Every 6 months | Full parameter re-evaluation on rolling window |
