# Risk & Assumptions Register
## ADX 20/10 ETH Trading Strategy

**Last updated:** 2026-03-20

**Updated by:** Greg (Gmac) + Claude

**Purpose:** Track all known assumptions, risks, and open questions as the strategy develops. Review before each live capital increase.

---

## How to read this register

| Field | Meaning |
|-------|---------|
| ID | Unique reference number |
| Category | Strategy / Execution / Infrastructure / Data |
| Status | Open / In Progress / Resolved |
| Priority | High / Medium / Low |
| Target | When we plan to address it |

---

## Open Items

---

### A001 — Win rate estimated, not measured

**Category:** Strategy

**Status:** In Progress

**Priority:** High

**Raised:** Week 4 Day 2

**Description:**
Kelly Criterion calculation used an estimated 50% win rate based on industry norms for trend-following strategies. The actual win rate of ADX 20/10 on live ETHUSDT has never been measured.

**Impact:**
If real win rate is materially below 50%, Kelly sizing of 12.41% may be too aggressive. If above 50%, we may be undersizing positions and leaving returns on the table.

**Fix:**
Add per-trade logging to backtest (entry price, exit price, P&L per trade) to derive a real win rate from 193 historical trades. Re-run Kelly with measured inputs.

**Target:** Week 4 Day 3 (add per-trade backtest logging)

**Update log:**
- 2026-03-21: PARTIALLY RESOLVED. Real win rate measured at 37.5% from 96 completed trades (no stop-loss). Significantly lower than 50% estimate but compensated by larger avg win (24.30% vs 9.93%). Kelly impact immaterial (-0.57%). Remains open until stop-loss backtest completes (A002).
- 2026-03-20: Raised. 50% assumption used as placeholder.

---

### A002 — Stop-loss not included in backtest

**Category:** Strategy

**Status:** Open

**Priority:** High

**Raised:** Week 4 Day 2

**Description:**
The validated backtest (Sharpe 1.111, 57.87% annual return) used ADX exit signals only. No 5% stop-loss was modelled. Real trading will include stop-loss exits that fire before the ADX exit signal, which the backtest never captured.

**Impact:**
Real performance metrics will differ from backtest figures. Direction is uncertain — stop-losses sometimes prevent larger losses, sometimes cut winning trades early. Sharpe and annual return figures should be treated as upper bounds until stop-loss backtesting is complete.

**Fix:**
Re-build backtest with intraday stop-loss logic using daily low prices to detect stop triggers within each candle.

**Target:** Week 5

**Update log:**
- 2026-03-20: Raised. Deferred to Week 5 — execution infrastructure takes priority.
- 2026-03-20: Sortino consistently below Sharpe across both validation methods (Expanding avg 0.816 vs Sharpe 0.869, Rolling avg 0.775 vs Sharpe 0.831). This confirms downside volatility is the dominant risk characteristic of this strategy. Stop-loss behaviour directly affects this profile — resolving A002 is important before scaling capital beyond initial $1,000.

### A003 — Slippage modelled as flat cost, not variable

**Category:** Execution

**Status:** Open

**Priority:** Medium

**Raised:** Week 4 Day 2

**Description:**
Transaction costs modelled at flat 0.175% per trade. This covers fees and average spread but does not model variable slippage on stop-loss exits during low-liquidity periods (e.g. thin market hours on weekends). Real stop-loss fills may be 0.1-0.5% worse than the stop price in adverse conditions.

**Impact:**
Small at current position sizes ($124 per trade — extra slippage of ~$0.62 maximum). Becomes meaningful as capital scales.

**Fix:**
Monitor actual fill prices vs stop prices once live trading begins. If consistent slippage > 0.3% observed, adjust cost model.

**Target:** Week 7 (after 10+ live trades)

**Update log:**
- 2026-03-20: Raised. Immaterial at current scale, monitor post-live.

---

### A004 — Binance fee tier unverified

**Category:** Execution

**Status:** Resolved

**Priority:** Low

**Raised:** Week 4 Day 2

**Description:**
Transaction costs assumed at 0.175% (medium scenario from Week 2). Actual Binance fee depends on 30-day trading volume tier and whether BNB is held for fee discounts.

**Impact:**
Minor at current position sizes. At $124 × 23.5 trades/year = $2,914 annual volume — this is Binance's lowest tier (0.1% maker / 0.1% taker). Our 0.175% assumption is actually conservative, meaning real costs may be slightly lower.

**Fix:**
Verify fee tier in Binance account settings before Day 7 live deployment.

**Target:** Week 4 Day 6 (pre-flight checklist)

**Update log:**
- 2026-03-20: Raised. Likely conservative assumption — may work in our favour.
- 2026-04-03: RESOLVED. Actual fee rate confirmed 0.075% maker/taker (with BNB discount). 
  Significantly better than 0.175% assumed. Backtest results are conservative — 
  real performance will be marginally better. Round-trip cost 0.15% vs 0.175% assumed.
---

### A005 — Kelly sizing based on pre-stop-loss backtest metrics

**Category:** Strategy

**Status:** In Progress

**Priority:** High

**Raised:** Week 4 Day 2

**Description:**
Kelly Criterion position sizing (12.41%) derived from backtest metrics that do not include stop-loss logic (see A002). Once stop-loss backtesting is complete and per-trade win rate is measured (see A001), Kelly should be re-calculated with updated inputs.

**Impact:**
Current 12.41% sizing is an estimate with two unresolved upstream assumptions. It is conservative enough (Half-Kelly with 25% cap) to be safe for initial deployment but should be refined.

**Fix:**
Re-run Kelly after A001 and A002 are resolved.

**Target:** Week 5 (after stop-loss backtest complete)

**Update log:**
- 2026-03-21: PARTIALLY RESOLVED. Kelly re-run with real inputs: 11.84% vs 12.41% estimated. Difference immaterial — no change to RiskManager. Remains open until A002 resolved and Kelly re-run with stop-loss backtest data.
- 2026-03-20: Raised. Proceeding with 12.41% as conservative initial estimate.

---

### A006 — Strategy parameters not re-optimised after adding risk constraints

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 4 Day 2

**Description:**
ADX 20/10 parameters were optimised in Week 2 without stop-loss or risk management constraints. Adding a 5% stop-loss changes the effective return profile of each parameter combination. The optimal parameters under constrained trading may differ from unconstrained optimisation results.

**Impact:**
ADX 20/10 may not be the optimal parameters once stop-losses are included. Could be higher or lower threshold depending on how stop-losses interact with trend strength signals.

**Fix:**
Re-run grid search optimisation with stop-loss logic included after A002 is resolved.

**Target:** Week 5

**Update log:**
- 2026-03-20: Raised. ADX 20/10 remains best available estimate pending constrained re-optimisation.

---

### A007 — Portfolio-level backtest not yet built

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 4 Day 2

**Description:**
Current backtest measures percentage returns per dollar invested. It does not model actual dollar portfolio growth with compounding position sizing applied trade by trade. A portfolio-level backtest is needed to properly compare 95% fixed sizing vs 12.41% Kelly sizing and to measure real dollar drawdowns, compounding effects, and probability of ruin at different position sizes.

**Impact:**
Cannot yet quantitatively confirm that Kelly sizing (12.41%) produces better risk-adjusted dollar returns than fixed sizing (95%) over the full backtest period. The theoretical case is strong but unverified empirically on this specific strategy.

**Fix:**
Build portfolio simulator that replays all 193 historical trades with actual dollar position sizing, tracking balance trade by trade. Compare 95% vs 12.41% vs Full Kelly on final portfolio value, max drawdown, and Sharpe.

**Target:** Week 5 (after per-trade logging from A001 is complete)

**Update log:**
- 2026-03-20: Raised. Requires per-trade logging (A001) as prerequisite.

---




## Resolved Items

*None yet — register opened Week 4 Day 2*

---

## Review Schedule

| Milestone | Action |
|-----------|--------|
| Week 4 Day 3 | Add per-trade logging to backtest (A001) |
| Week 4 Day 6 | Verify Binance fee tier (A004) |
| Week 5 | Stop-loss backtest (A002), re-run Kelly (A005), re-run grid search (A006) |
| Week 7 | Review slippage from first 10 live trades (A003) |
| Every 6 months | Full parameter re-evaluation on rolling window |
| Sharpe < 0.5 over 30 live trades | Pause live trading, full strategy review |
