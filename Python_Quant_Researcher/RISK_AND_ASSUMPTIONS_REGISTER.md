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

**Status:** ✅ RESOLVED

**Priority:** High

**Raised:** Week 4 Day 2

**Resolved:** Week 5 Day 2

**Description:**
Kelly Criterion calculation used an estimated 50% win rate based on industry norms for trend-following strategies. The actual win rate of ADX 20/10 on live ETHUSDT has never been measured.

**Resolution:**
Stop-loss backtest completed in Week 5 Day 1. True win rate confirmed at 34.3% from 108 trades with stop-loss logic modelled. Kelly recalculated with real inputs — new recommended Half-Kelly 11.77% vs 12.41% previously. Difference immaterial, no change to RiskManager required.

**Update log:**
- 2026-04-07: RESOLVED. Win rate confirmed 34.3% (with stop-loss). Kelly recalculated 11.77%. No RiskManager change needed.
- 2026-03-21: PARTIALLY RESOLVED. Real win rate measured at 37.5% from 96 completed trades (no stop-loss). Remains open until stop-loss backtest completes (A002).
- 2026-03-20: Raised. 50% assumption used as placeholder.

---

### A002 — Stop-loss not included in backtest

**Category:** Strategy

**Status:** ✅ RESOLVED

**Priority:** High

**Raised:** Week 4 Day 2

**Resolved:** Week 5 Day 1

**Description:**
The validated backtest (Sharpe 1.111, 57.87% annual return) used ADX exit signals only. No 5% stop-loss was modelled.

**Resolution:**
Stop-loss aware backtest built in Week 5 Day 1 using bar-by-bar simulation with daily LOW prices to detect intraday stop triggers. Results: 108 trades, win rate 34.3%, profit factor 3.197, max drawdown -30.3% (improved from -48.12%), stop exits 41.7% of trades. Trade log saved to data/trade_log_with_stoploss.csv. Note: Sharpe ratio calculation remains distorted by per-trade annualisation — needs daily equity curve approach in a future week.

**Update log:**
- 2026-04-07: RESOLVED. Stop-loss backtest complete. True metrics confirmed. Sharpe annualisation bug noted for future fix.
- 2026-03-20: Raised. Deferred to Week 5 — execution infrastructure takes priority.

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

**Status:** ✅ RESOLVED

**Priority:** High

**Raised:** Week 4 Day 2

**Resolved:** Week 5 Day 2

**Description:**
Kelly Criterion position sizing (12.41%) derived from backtest metrics that did not include stop-loss logic.

**Resolution:**
Kelly recalculated in Week 5 Day 2 using true stop-loss backtest data. Inputs: win rate 34.3%, avg win +24.04%, avg loss -3.92%, reward:risk 6.13x. New Half-Kelly: 11.77%. Difference from 12.41% is 0.64 percentage points — immaterial. No change to RiskManager required. Current 12.41% sizing remains acceptable.

**Update log:**
- 2026-04-07: RESOLVED. Kelly recalculated at 11.77%. Difference immaterial. RiskManager unchanged.
- 2026-03-21: PARTIALLY RESOLVED. Kelly re-run with real inputs: 11.84% vs 12.41% estimated. Remains open until A002 resolved.
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

### A006 — Strategy parameters not re-optimised after adding risk constraints

**Category:** Strategy

**Status:** ✅ RESOLVED

**Priority:** Medium

**Raised:** Week 4 Day 2

**Resolved:** Week 5 Day 3

**Description:**
ADX 20/10 parameters were optimised in Week 2 without stop-loss or risk management constraints.

**Resolution:**
Joint parameter optimisation completed in Week 5 Day 3. Coarse grid (64 combinations) followed by refined grid (392 combinations). Live parameters ADX 20/10 with 5% stop ranked 22nd of 392. Best combination found: ADX 18/10 with 3.5% stop (profit factor 3.397 vs 3.197 live). Difference of 0.20 in profit factor deemed within statistical noise over ~100 trades. No parameter change recommended at this stage — revisit after 20+ live trades. Full results saved to data/joint_optimisation_results_refined.csv.

**Update log:**
- 2026-04-07: RESOLVED. Joint optimisation complete. Live params acceptable. Best combo noted for future review.
- 2026-03-20: Raised. ADX 20/10 remains best available estimate pending constrained re-optimisation.

---

### A007 — Portfolio-level backtest not yet built

**Category:** Strategy

**Status:** ✅ RESOLVED

**Priority:** Medium

**Raised:** Week 4 Day 2

**Resolved:** Week 5 Day 2

**Description:**
No portfolio-level simulator existed to compare Kelly vs fixed sizing on real dollar P&L.

**Resolution:**
Portfolio simulator built in Week 5 Day 2. Five strategies compared across 108 trades: Fixed $124, Kelly 12.41%, Conservative 5%, Aggressive 25%, All-in 100%. Key finding: Kelly 12.41% produced $2,046 from $1,000 vs $1,758 fixed sizing. All-in 100% produced $70,779 in backtest but is not deployable due to sequence dependency, gap risk, and being 4x above full Kelly threshold. Chart saved to Week_5_Notebooks/results/day2_portfolio_simulator.png.

**Update log:**
- 2026-04-07: RESOLVED. Portfolio simulator built and run. Kelly confirmed as appropriate sizing methodology.
- 2026-03-20: Raised. Requires per-trade logging (A001) as prerequisite.

---

### A008 — RSI strategy deployed with small backtest sample

**Category:** Strategy

**Status:** Open

**Priority:** High

**Raised:** Week 5 Day 7

**Description:**
RSI mean reversion strategy (RSI_14_v_final) deployed live with $500 capital allocation. Backtest sample size is only 31 trades over 7.9 years — below the ideal minimum of 100 trades for statistical reliability. Walk-forward validation used fixed parameters rather than true rolling re-optimisation. Bitcoin cross-asset validation passed (profit factor 2.450 on BTC vs 5.593 on ETH).

**Impact:**
Backtest metrics may not reliably predict live performance. A 93.5% win rate from 31 trades has wide confidence intervals — true win rate could be materially lower. Position sizing capped conservatively at 10% (below Kelly recommendation of 25%) to reflect this uncertainty.

**Fix:**
Monitor live performance closely. After 20 live trades, compare actual win rate and profit factor to backtest. If materially worse, reduce capital or pause strategy. Do not increase RSI capital beyond $500 until 20+ live trades validated.

**Target:** Ongoing — review after 20 live trades

**Update log:**
- 2026-04-07: Raised at deployment. Capital capped at $500. Position size capped at 10%.

---

### A009 — Walk-forward validation used fixed parameters, not true rolling re-optimisation

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 5 Day 7

**Description:**
The walk-forward validation run for RSI and BB strategies in Week 5 Day 7 used parameters fixed at full-sample optimised values, then tested across rolling time windows. This is less rigorous than true walk-forward validation where parameters are re-optimised independently at the end of each training window before testing on the next unseen window.

**Impact:**
Results are supporting evidence of robustness but not conclusive proof. Parameters were chosen with knowledge of the full 2018-2026 period including the test windows. A true walk-forward would be a stricter test. Low signal frequency (3-4 trades/year) makes true walk-forward impractical with current data.

**Fix:**
As live trade history accumulates, use real live performance data as the primary validation source. Consider true rolling walk-forward validation when 3+ years of additional data is available. Also consider using Combinatorial Purged Cross-Validation (CPCV) — see SB006.

**Target:** Week 8-10 (when sufficient live data available)

**Update log:**
- 2026-04-07: Raised. Limitation acknowledged. Live performance monitoring is the primary validation path.

---




## Resolved Items

| ID | Description | Resolved | Week |
|----|-------------|----------|------|
| A001 | Win rate estimated, not measured | Win rate confirmed 34.3% from stop-loss backtest | Week 5 Day 2 |
| A002 | Stop-loss not in backtest | Bar-by-bar stop-loss backtest built and run | Week 5 Day 1 |
| A004 | Binance fee tier unverified | Fee confirmed 0.075% actual vs 0.175% assumed | Week 4 Day 6 |
| A005 | Kelly based on incomplete data | Kelly recalculated at 11.77% — immaterial change | Week 5 Day 2 |
| A006 | Parameters not re-optimised with stops | Joint optimisation complete — live params acceptable | Week 5 Day 3 |
| A007 | Portfolio simulator not built | Simulator built, 5 strategies compared | Week 5 Day 2 |

---

## Capital Allocation (current)

| Strategy | Status | Capital | Position Size | Notes |
|----------|--------|---------|---------------|-------|
| ADX 20/10 ETH | Live | $1,000 | 12.41% Kelly | Live since April 4, 2026 |
| RSI_14_v_final ETH | Live | $500 | 10% (conservative) | Live from Week 5 — monitor closely |
| BB_15_2_v3 ETH | Paper trading | $0 | N/A | Pending further validation |
| Total deployed | | $1,500 | | Do not exceed until A008 resolved |

---

## Review Schedule

| Milestone | Action |
|-----------|--------|
| After 20 RSI live trades | Compare live win rate vs backtest 93.5% — review A008 |
| Week 7 | Review slippage from first 10 ADX live trades (A003) |
| Week 8-10 | Consider true rolling walk-forward when more live data available (A009) |
| Every 6 months | Full parameter re-evaluation on rolling window |
| Sharpe < 0.5 over 30 live trades | Pause live trading, full strategy review |
| Before any capital increase beyond $1,500 | All High priority items must be resolved |
