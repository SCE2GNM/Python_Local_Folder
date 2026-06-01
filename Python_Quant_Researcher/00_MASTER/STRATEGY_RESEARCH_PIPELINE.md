# Strategy Research Pipeline

This document defines the standard process for moving a strategy from idea to live deployment.
Each phase must be completed in order. Do not skip phases or merge them.

---

## Phase 0 — Pre-Week Research Brief

**Timing (Week 8 onwards):** Conducted at the start of the new week's chat thread, before any backtesting begins. Running research in the same chat as the work it informs means full context is available for follow-up questions. Always done in Claude Chat (web search enabled), never in Claude Code.

**Timing (Week 7):** Research brief was prepared at end of Week 6 and saved as WEEK_7_RESEARCH_BRIEF.md. This was the original approach — superseded from Week 8 onwards.

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

**Standing note:** Phase 0 research is always conducted in Claude Chat (web search enabled), never in Claude Code. Claude Code cannot search the web.

---

## Phase 1 — Strategy Design and Backtest

*(To be documented)*

---

## Phase 2 — Initial Backtest

### Maximum Loss Per Trade Check

Before any optimisation, calculate and explicitly state:
- Maximum loss per trade in dollars = `position_size × stop_loss_pct`
- Maximum loss as % of total strategy allocation
- Maximum loss as % of total portfolio

Ask explicitly: *"Is this maximum loss per trade acceptable given the strategy's win rate, average win, and sample size?"*

Flag for review if maximum loss % of allocation exceeds 20% AND win rate is below 80%. This combination means a short losing streak can significantly impair the allocation before recovery is possible.

**Example flag:** RSI strategy — 15% stop × $500 full deployment = $75 max loss = 15% of allocation. Backtest win rate 93.5% but expected 60–70% live. At 70% win rate and negative Kelly, this warrants reduced position size, not full allocation deployment.

---

### Payoff Profile Sanity Check

Calculate the breakeven win rate for positive Kelly expectation:

```
p_breakeven = 1 / (1 + b)
where b = avg_win / avg_loss_magnitude
```

If `p_breakeven > 65%`: flag as **HIGH SENSITIVITY** strategy. Win rate must be reliably above this threshold for the strategy to have positive expectancy. Document expected live win rate degradation and confirm `p_live_expected > p_breakeven` before proceeding to optimisation.

**Example:** RSI strategy
```
b = 5.79% / 15.00% = 0.386
p_breakeven = 1 / (1 + 0.386) = 72.1%
Expected live win rate: 60–70%
Result: HIGH SENSITIVITY FLAG — live win rate likely below breakeven.
Requires Monte Carlo stress test before deployment decision.
```

---

## Phase 3 — Optimisation

Every sub-phase is required for every strategy. If a sub-phase is deferred, written
justification must be recorded in the strategy risk register before Phase 4 begins.
The sequence 3A → 3B → 3C → 3D → 3E is mandatory and cannot be reordered.

---

### 3A — Entry Optimisation

Test all relevant entry parameter combinations within the research-brief-informed range.
Apply the minimum 30-trade filter throughout. Metric for ranking: **post-break profit
factor** (not full-period). Record the top 3 entry parameter combinations for use in 3D.

**Grid boundary check:** the best result must not sit at the edge of the tested range.
If it does, extend the range until performance clearly peaks and plateaus before accepting.

---

### 3B — Exit Optimisation

Test all five exit methods for every strategy before selecting one. Report for each:
full-period PF, post-break PF, win rate, trade count, annual return, Sortino, MtM MDD,
per-trade MDD. **Select based on post-break PF, not full-period metrics.**
Document selection with an explicit comparison table showing all five methods tested.

**Exit method 1 — Signal-based:**
Indicator reversal (e.g. ADX drops below threshold, RSI crosses exit level,
price breaks below Donchian lower channel). The "default" exit for the strategy type.

**Exit method 2 — Fixed percentage stop only:**
Pure stop management, no signal exit. Stop set at entry and fixed (does not trail).
Test stops at: 2%, 3%, 4%, 5%, 6%, 7%, 8%, 10%, 12%, 15%.

**Exit method 3 — ATR trailing stop:**
Stop = peak price − (multiplier × ATR). Ratchets upward only, never down.
Exit when daily LOW touches the trailing stop level.
Test ATR multipliers: 1.5, 2.0, 2.5, 3.0. Default ATR period: 14.

**Exit method 4 — EMA trailing stop:**
Two-tier check. Tier 1: exit when daily LOW ≤ prior bar's EMA (intrabar, fill at prior EMA).
Tier 2: exit when close < current EMA (EOD trigger, fill at close). Always check LOW first.
Test EMA periods: 20, 30, 50.

**Exit method 5 — Hybrid (signal + ATR trailing stop):**
Signal-based exit combined with ATR trailing stop; whichever fires first exits the position.
Use the best ATR multiplier from method 3.

**Stop range optimisation (mandatory):**
Test stop values at: 2%, 3%, 4%, 5%, 6%, 7%, 8%, 10%, 12%, 15%.
For each, report: annual return, Sortino, profit factor, trade count, MtM MDD.
Confirm the chosen stop sits on a plateau — not a cliff edge or a grid boundary.
If a stop value fails hard filters (trade count or MDD gate), report the failure reason
explicitly (MDD failure vs trade count failure — these are different diagnostics).

---

### 3C — Regime Filter Optimisation

**Required for all trend-following strategies** (ADX, Donchian, Supertrend, Keltner,
any MACD-based trend strategy).

For each filter, report: full-period PF, post-break PF, MtM MDD, annual return, trade count.
**Select based on post-break PF improvement vs trade count cost.**
Always include no-filter baseline in the comparison.

| Filter | Entry condition |
|---|---|
| No filter (baseline) | Always enter on signal |
| SMA-50 | Enter only when close > 50-day SMA |
| SMA-100 | Enter only when close > 100-day SMA |
| SMA-120 | Enter only when close > 120-day SMA |
| SMA-200 | Enter only when close > 200-day SMA |
| EMA-50 | Enter only when close > 50-day EMA |

**For mean reversion strategies** (RSI, Bollinger Bands): the SMA-120 regime filter is
validated on ETH RSI. For any new asset or parameter set, run the same sensitivity
analysis above to confirm the existing period is optimal.

---

### 3D — Joint Optimisation

After 3A, 3B, and 3C are individually complete, run a joint grid:
- Top 3 entry parameter combinations from 3A
- Best exit method from 3B with top 2 stop distances
- Best 2 regime filters from 3C (always include no-filter as baseline)

**The deployed configuration must come from this joint grid** — not from individually
optimised phases. Sequential optimisation (entry → exit → regime → combine) misses
interactions between parameters. 3D is the correct final parameter selection step.

---

### 3E — Monte Carlo Stress Test

**Required for all strategies with fewer than 100 backtest trades. Recommended for all.**

Bootstrap method: resample wins and losses separately in the required win-rate proportion
to adjust win rate while preserving actual win/loss size distributions. Apply 0.15%
transaction costs to each simulated trade return before compounding.

Run 1,000 simulations at five win-rate scenarios: backtest rate, 80%, 75%, 70%, 65%.
For each scenario report:

- Median annual return %
- 10th percentile annual return % (bad luck)
- 90th percentile annual return %
- Probability of negative annual return
- Kelly fraction at this win rate: f* = p − (1−p)/b
- Recommended Half-Kelly position size at deployed capital
- Kelly breakeven win rate: p_breakeven = 1/(1+b)

**Mandatory flags — no exceptions:**
- Kelly turns negative at any scenario → **DO NOT DEPLOY at this win rate**
- Probability of negative year > 30% at any scenario → flag for explicit acceptance

Use conservative sizing scenario (worst viable Kelly-positive scenario) as deployment
reference — not the backtest scenario. If live win rate is expected lower than backtest
(common for mean-reversion strategies), size for the expected live win rate.

---

### Leverage Screening

**Run after Phase 3D joint optimisation identifies top 20 combinations.**

1. Run preliminary leverage grid (1.0× to 3.0×, 0.5× steps) for each of the top 20.
2. Re-rank top 20 by leveraged annual return, subject to safety buffer ≥ 33%.
3. If ranking shifts from the 1× ranking, run full leverage grid (1.0×–5.0×, 0.1× steps)
   on the top 3 combinations.
4. Final selection is based on leveraged performance, not 1× performance.

Low MaxDD and high Sortino are leverage multipliers — a strategy with lower raw return
but lower drawdown may support higher safe leverage than the raw-return winner.

**Deferral:** Leverage screening may be formally deferred for unleveraged initial deployments.
The deferral and its justification must be recorded in the strategy risk register before
Phase 4 begins. Reopen condition must also be stated.

---

### Phase 3 Visualisation Deliverables

The following must be produced after Phase 3D is complete.
**Phase 3 is not complete until all six deliverables exist as saved files.**

| ID | Chart | Format | Required content |
|---|---|---|---|
| 3V1 | Post-break PF heatmap | PNG | PF across entry parameter grid (period × threshold or equivalent). Diverging colourmap centred at PF=2.0. Deployed combination marked with ★. |
| 3V2 | Full-period Sortino heatmap | PNG | Sortino across the same grid. Diverging colourmap centred at Sortino=0.8. Deployed combination marked. |
| 3V3 | Annual return heatmap | PNG | Annual return across the same grid. Diverging colourmap centred at B&H annual return for that asset. Deployed combination marked. |
| 3V4 | Stop sensitivity chart | PNG | Annual return and MtM MDD vs stop % (line chart, two y-axes). Mark chosen stop value with vertical dashed line. |
| 3V5 | Regime filter comparison chart | PNG | Grouped bar chart showing post-break PF for each filter option tested. Baseline (no filter) as reference bar. |
| 3V6 | Exit method comparison table | Console + CSV | All five exit methods with full metrics: full-period PF, post-break PF, WR, trades, annual return, Sortino, MtM MDD, per-trade MDD. |

Save all charts to `06_BACKTESTS/Week_[N]_Notebooks/charts/` (or equivalent week folder).

---

## Phase 4 — Stability Analysis

*(Full methodology to be documented)*

Complete the following before marking Phase 4 signed off:
- Grid boundary extension on chosen stop value
- Stability grid classification: STABLE / MARGINAL / FRAGILE (post-break PF > 2.0 threshold)
- Walk-forward validation (expanding IS window, 6-month OOS, step 6 months)
- Regime break analysis (mandatory per METHODOLOGY_STANDARDS.md)

---

### Phase 4 Visualisation Deliverables

**Phase 4 is not complete until all three deliverables exist as saved files.**

| ID | Chart | Format | Required content |
|---|---|---|---|
| 4V1 | Walk-forward OOS bar chart | PNG | OOS profit factor by window. Green bars = profitable (PF ≥ 1.0), red = loss. Mark January 2024 regime break date with vertical dashed line. |
| 4V2 | Annual returns vs B&H | PNG | Strategy annual return vs B&H annual return, grouped bars by calendar year. B&H as grey reference bars. |
| 4V3 | Drawdown comparison | PNG | Strategy MtM MDD vs B&H MDD by year, line chart. Show both on same axes to illustrate drawdown reduction from active management. |

---

## Phase 5 — Stress Testing

*(Full methodology to be documented)*

Phase 5 stress testing builds on Phase 3E Monte Carlo with additional layers:
- Conservative cost assumptions (0.30% round-trip, doubled from realistic)
- Worst-case stop slippage scenarios (0.25% vs 0.10% realistic)
- Leverage interaction analysis (if leveraged deployment is planned)

---

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

### Phase 6 Visualisation Deliverables

The following must be produced as part of the deployment documentation.
**Phase 6 is not complete until all five deliverables exist as saved files.**

| ID | Chart | Format | Required content |
|---|---|---|---|
| 6V1 | Interactive equity curve | Plotly HTML | Strategy vs B&H, log scale, daily MtM. Entry markers (▲), exit markers (▼), trailing stop line (dashed). Drawdown panel as lines below main chart. |
| 6V2 | Year-by-year equity panels | PNG | One panel per year, normalised to 1.0 at year start. Show strategy vs B&H per year. |
| 6V3 | Trade return distribution | PNG | Histogram of individual trade returns. Wins in green, losses in red. Mark mean win and mean loss with vertical dashed lines. |
| 6V4 | Underwater curve | PNG | Drawdown from equity peak (MtM), time series. Shade depth of drawdown. Mark regime break date. |
| 6V5 | Parallel coordinates chart | Plotly HTML | Top 50 combinations from Phase 3D joint grid by annual return. Axes: entry param, stop, regime filter, annual return, Sortino, post-break PF. |

Interactive HTML charts saved to `06_BACKTESTS/Week_[N]_Notebooks/charts/interactive/`.
PNG charts saved to `06_BACKTESTS/Week_[N]_Notebooks/charts/`.
Deployment document must embed or link all charts.

---

*Pipeline version: 2.0 — updated 2026-06-01: comprehensive Phase 3 rewrite (3A–3E mandatory sequence); visualisation deliverables added to Phases 3, 4, 6; Phase 4 and Phase 5 stubs expanded — updated 2026-05-07: added Phase 2 (Maximum Loss Per Trade Check, Payoff Profile Sanity Check); added Monte Carlo Stress Test to Phase 3*
*Pipeline version: 1.4 — updated 2026-05-06: added §Confidence-Based Capital Allocation under Phase 6*
*Pipeline version: 1.3 — updated 2026-05-05: added §Kelly Criterion and Leverage Interaction under Phase 5*
*Pipeline version: 1.2 — updated 2026-05-05: added Phase 4/5 stubs; added Phase 6 with Kelly position sizing*
*Pipeline version: 1.1 — updated 2026-05-04: added Phase 2/3 stubs; added §Leverage Screening under Phase 3*
*Pipeline version: 1.0 — created 2026-05-04*
*Update this document after any process change or post-deployment review.*
