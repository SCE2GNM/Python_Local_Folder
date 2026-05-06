# Strategy Research Pipeline

This document defines the standard process for moving a strategy from idea to live deployment.
Each phase must be completed in order. Do not skip phases or merge them.

---

## Phase 0 — Pre-Week Research Brief

**Timing:** Conducted 2–3 days before the week starts (in Claude chat, not Claude Code).

**Purpose:** Ensure all backtesting starts from evidence-based parameter ranges rather than arbitrary grids. Saves computational time and focuses optimisation on productive regions.

### Sources to search (in order of quality)

1. **Academic papers:** SSRN, arXiv quant-fin, Journal of Portfolio Management
   - Search: `"[indicator] cryptocurrency returns"`, `"[strategy type] momentum bitcoin"`, `"[indicator] parameter optimisation equity"`

2. **Practitioner research:** QuantConnect research library, Quantpedia strategy database, Ernest Chan blog/books, Lopez de Prado papers

3. **Crypto-specific:** Glassnode research, The Block Research

4. **Community (lower priority):** QuantConnect forums, r/algotrading — filter heavily; prioritise posts with shared code and verified results over claims alone

### Research brief must answer for each strategy

1. What parameter ranges have the strongest empirical support in the literature?
2. What entry/exit conditions are supported?
3. What regime filters improve performance?
4. What are the known failure modes?
5. Has this been tested on crypto specifically?

### Output

Save as `WEEK_[N]_RESEARCH_BRIEF.md` in project root before the week begins.

Claude Code reads the brief at week start before building any scripts. The brief informs the initial parameter grid — do not run a grid search without it.

### Critical reading standard

Treat all sources critically. Always verify that cited papers use proper out-of-sample methodology. Reject any source claiming exceptional returns without methodology disclosure. Look for: train/test split, transaction cost assumptions, and whether the strategy was published before or after the test period.

---

## Phase 1 — Strategy Design and Backtest

*(To be documented)*

---

## Phase 2 — Validation

*(To be documented)*

---

## Phase 3 — Optimisation

### Leverage Screening

**Run after top 20 strategy parameter combinations identified.**

After ranking the top 20 combinations by annual return at 1×:

1. Run a preliminary leverage grid (1.0× to 3.0×, 0.5× steps) for each of the top 20.
2. Re-rank the top 20 by leveraged annual return, subject to safety buffer ≥ 33%.
3. If the ranking shifts from the 1× ranking, run full leverage optimisation (1.0×–5.0×, 0.1× steps) on the top 3 combinations.
4. Final strategy selection is based on leveraged performance, not 1× performance.

**Rationale:** Strategies with lower raw return but lower drawdown and higher Sortino may support higher safe leverage, producing better final returns than a higher-raw-return strategy constrained to lower leverage by its drawdown profile. The 1× winner is not always the leveraged winner.

Low MaxDD and high Sortino are leverage multipliers, not just quality filters — weight them more heavily when leverage is planned. Joint optimisation of strategy parameters and leverage simultaneously is the theoretically correct approach. Sequential optimisation (strategy first, leverage second) may miss the global optimum.

---

## Phase 4 — Stability Analysis

*(To be documented)*

---

## Phase 5 — Stress Testing

*(To be documented)*

### Kelly Criterion and Leverage Interaction

**Kelly-optimal leverage:**

```
Lev_kelly = f* / stop_loss_pct
```

Example: f*=12.41%, stop=8% → Lev_kelly = 0.1241 / 0.08 = **1.55×**

This is the leverage level that maximises long-run growth according to Kelly theory — the point where the risk fraction of levered capital equals f*.

**Buffer-constrained maximum leverage:**

Determined by safety buffer analysis — the highest leverage at which the worst historical intraday move does not cause liquidation (margin ratio stays above 5% maintenance threshold, working minimum 25%). See STRATEGIC_FRAMEWORK.md for categorical liquidation check methodology.

**Deployment rule:**

| Condition | Action |
|---|---|
| Kelly leverage < buffer maximum | Use Kelly leverage — growth-optimal |
| Kelly leverage > buffer maximum | Use buffer maximum — safety-constrained |

In both cases: size the position so that maximum loss = f* × own capital, regardless of leverage level.

**Correct leveraged position sizing:**

```
Position = (f* × own_capital) / stop_pct
```

Deploy this position size from available (own + borrowed) capital. Do not automatically deploy 100% of available leveraged capital — the position size is determined by the Kelly risk formula, not by how much capital the broker will lend.

Example: f*=12.41%, own_capital=$1,000, stop=8%, Kelly leverage=1.55×
```
Position    = $124.10 / 0.08 = $1,551
Own capital = $1,000
Borrow      = $551
Leverage    = $1,551 / $1,000 = 1.55× ✓
Max loss    = $1,551 × 8% = $124.10 = 12.41% of own capital ✓
```

---

## Phase 6 — Deployment Decision

### Position Sizing — Kelly Criterion

Kelly fraction f* is the **risk fraction per trade** — the maximum possible loss as a percentage of total capital. It is not the fraction of capital to deploy as position size.

**Correct formula:**

```
Position size = (f* × Capital) / Stop loss %
```

This ensures: `Position × Stop% = f* × Capital`
i.e. maximum loss = Kelly fraction of capital, regardless of stop distance.

**Example:** f*=12.41%, Capital=$1,000, Stop=8%
```
Risk amount = 0.1241 × $1,000 = $124.10
Position    = $124.10 / 0.08  = $1,551
Cap at available capital if unleveraged.
```

**NEVER implement Kelly as:**
```
Position = f* × Capital   (= $124 — WRONG)
```
This treats Kelly as a deployment fraction, not a risk fraction. It undersizes the position by a factor of 1/stop_pct. At a 5% stop, the position is 20× too small; actual risk per trade is 0.62% of capital instead of the intended 12.41%.

**For leveraged strategies:** Kelly determines the risk per trade; leverage determines the capital efficiency. These are separate decisions — do not conflate them. Kelly optimisation assumes no borrowing costs and applies to own-capital sizing. For margin strategies, run a leverage grid search after Kelly sizing is confirmed.

**Implementation notes:**
- Always apply a small fee buffer: `min(balance − $5, position_size)`
- When stop distance changes (e.g. fixed 5% → trail 8%), recalculate position size using the new stop — the formula handles this automatically if `stop_loss_pct` in `RISK_CONFIG` is kept current
- Kelly fraction itself should be recalibrated after every 20+ live trades as win rate and reward:risk ratios accumulate from real data

---

### Confidence-Based Capital Allocation

At deployment, allocate capital proportional to confidence score — not equal allocation.

**Score each strategy (0–100) across:**

| Factor | High confidence | Low confidence |
|---|---|---|
| Backtest sample size (primary) | n > 100 trades | n < 35 trades |
| Stability result | STABLE | FRAGILE |
| Walk-forward consistency | All windows profitable | Scraping through |
| B&H relative multiple | Well above 2× threshold | Just clearing 2× |
| Live trade count | 20+ trades accumulated | Zero (deployment) |

Live trade count starts at zero for every new deployment and grows over time — initial allocation is based on backtest evidence only; subsequent rebalances incorporate live results.

**Allocation metric:** Use Sortino + annual return% (equal weight). Never use Sharpe for allocation decisions — Sharpe penalises upside volatility equally with downside.

**Performance-weighted rebalancing:** Do not implement until minimum 20 live trades per strategy accumulated. Below this threshold, performance differences are statistical noise, not evidence of edge.

---

*Pipeline version: 1.4 — updated 2026-05-06: added §Confidence-Based Capital Allocation under Phase 6*
*Pipeline version: 1.3 — updated 2026-05-05: added §Kelly Criterion and Leverage Interaction under Phase 5*
*Pipeline version: 1.2 — updated 2026-05-05: added Phase 4/5 stubs; added Phase 6 with Kelly position sizing*
*Pipeline version: 1.1 — updated 2026-05-04: added Phase 2/3 stubs; added §Leverage Screening under Phase 3*
*Pipeline version: 1.0 — created 2026-05-04*
*Update this document after any process change or post-deployment review.*
