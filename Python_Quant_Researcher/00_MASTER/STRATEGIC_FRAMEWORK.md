# Strategic Framework
## DeFi Quant Engineer Curriculum

**Purpose:** Defines the high-level investment philosophy, portfolio objectives, risk tolerance, and decision-making principles for the 24-week curriculum. The "why" behind all strategy decisions. Read this when a decision feels unclear — it usually resolves the ambiguity.
**Who reads it:** Greg at the start of each new week. Claude at the start of any session involving capital allocation or strategy prioritisation decisions.
**When updated:** Rarely — only when a fundamental shift in approach occurs. Not updated for tactical decisions.
**Related documents:** CURRICULUM_OPERATING_MANUAL.md, RISK_REGISTER files.

---

**Student:** Greg (Gmac)
**Created:** 2026-05-04
**Purpose:** Cross-strategy decision rules and risk frameworks that apply to
every strategy in the curriculum. These rules take precedence over
strategy-specific documentation when they conflict.

---

## Safety Buffer — Evidence-Based Framework

**Buffer analysis date:** 2026-05-04
**ETH worst single-day drop:** −42.9% (2020-03-12)
**BTC worst single-day drop:** −38.6% (2020-03-12)

---

### Categorical Liquidation Threshold

At any leverage level where the worst historical single-day drop would
liquidate the position from a FRESH ENTRY, that leverage level is
categorically unsafe — do not deploy regardless of buffer percentage
shown in backtest.

**Evidence:**

| Strategy | Leverage | Entry MR | Worst drop | MR after | Verdict |
|---|---|---|---|---|---|
| BTC SMA | 2.5× | 40.0% | −38.6% | 2.3% | **CATEGORICALLY UNSAFE** — liquidated from fresh entry |
| BTC SMA | 2.0× | 50.0% | −38.6% | 18.6% | **SAFE** — survives worst historical drop from fresh entry |
| ETH ADX | 1.9× | 52.6% | −42.9% | 17.0% | **SAFE** — survives worst historical drop from fresh entry |
| ETH ADX | 1.9× | 34.4% (hist worst) | −42.9% | −14.9% | **VULNERABLE at extremes** — liquidated from worst historical MR |

---

### Revised Buffer Rules

**Hard floor (categorical):**
Leverage level must survive the worst historical single-day drop for
that asset from a FRESH ENTRY and remain above 5% maintenance margin.
If it cannot, do not deploy at that leverage. Non-negotiable.

**Working minimum:**
Leverage level must survive the 5th-worst historical single-day drop
from the worst historical backtest margin ratio and remain above 25%.
If it cannot, reduce leverage.

**33% static threshold:**
Retained as initial screening tool but superseded by the above
empirical tests when historical drop data is available. The 33%
threshold is not self-sufficient — a position exactly at 33% MR can
still be liquidated by a historically-observed extreme event.

---

### Live Bot Margin Monitoring Requirement

Margin ratio Telegram alerts are mandatory for all leveraged deployments.
These are early warning thresholds, not liquidation levels. They provide
time for manual intervention before the position enters the danger zone.

| Strategy | Alert threshold | Rationale |
|---|---|---|
| ETH ADX at 1.9× | 40% margin ratio | Below this level, an extreme event could approach the liquidation zone |
| BTC SMA at 2.0× | 35% margin ratio | Below this level, a 5th-worst BTC drop breaches the 25% hard floor |

**Primary protection:** trailing stop (historically fires before liquidation
threshold reached in 8+ years of backtest data).

**Secondary protection:** margin ratio alerts (early warning for manual
intervention).

Neither is a guarantee in genuine liquidity crises or overnight gap events.
The categorical liquidation threshold (hard floor rule above) is the
structural protection — choose a leverage level where the worst historical
event does not liquidate the position even before the stop fires.

---

## Cross-Strategy Correlation and Concurrent Drawdown Risk

**Added:** 2026-06-23 (Week 10 audit Action 6)
**Trigger:** Independent audit identified that no portfolio-level correlation analysis exists despite multiple strategies sharing the same underlying asset.

---

### Current Concurrent Exposure

As of Week 10, two live strategies hold long ETH positions simultaneously:

| Strategy | Capital | Stop Distance | Max Single-Trade Loss |
|---|---|---|---|
| ETH ADX (19/9, 8% trail) | $1,000 | 8% trailing | $80 |
| ETH RSI (14/43/48, SMA-120) | $150 | 15% fixed | $22.50 |
| **Combined worst case** | **$1,150** | **Both stops hit same day** | **$102.50 (8.9% of combined)** |

BTC SMA ($500 reserved) and BNB Donchian ($150 reserved) are on different assets and do not create direct correlation with the ETH positions. However, all crypto assets are correlated during market-wide crashes (e.g. March 2020, November 2022). In a systemic event, all four strategies could experience simultaneous losses.

**Systemic worst case (all four strategies, all stops triggered simultaneously):**
- ETH ADX: $80 loss (8% of $1,000)
- ETH RSI: $22.50 loss (15% of $150)
- BTC SMA: $150 loss (30% of $500)
- BNB Donchian: $7.50 loss (5% of $150)
- **Combined: $260 loss from $1,800 total = 14.4% portfolio drawdown in one day**

This is survivable but must be acknowledged explicitly in the capital allocation decision.

---

### Correlation Rules for New Strategy Deployment

Before deploying any new strategy with real capital, calculate the daily return correlation between the new strategy's backtest equity curve and every existing live strategy's backtest equity curve.

| Correlation | Action Required |
|---|---|
| Below 0.3 | Deploy normally — genuine diversification |
| 0.3 to 0.7 | Deploy but document the overlap in the risk register |
| Above 0.7 | Reduce the new strategy's Kelly fraction by 30% to account for correlation. Document the reduction and rationale in the deployment card |

**Hard rule:** The combined portfolio must never have more than 60% of total capital exposed to a single underlying asset. Currently ETH exposure is $1,150 out of $1,800 = 63.9%. This is above the threshold and is accepted at current scale because:
(a) BTC SMA and BNB Donchian are not yet deployed
(b) Once deployed, ETH share drops to approximately 48% ($1,150 / $2,400)

If BTC SMA and BNB Donchian are not deployed by Week 13, reassess the ETH concentration explicitly.

---

### Portfolio-Level Circuit Breaker

If combined portfolio value drops more than 15% from its all-time peak in a single calendar week:
1. Pause all strategy entries (existing positions held)
2. Send consolidated Telegram alert
3. Review all strategies before resuming entries
4. Document the event and review outcome in the weekly summary

This is a manual process until the portfolio_monitor.py is built in Week 11.

---

*Version 1.0 — created 2026-05-04: initial document, Safety Buffer evidence-based framework*
*Version 2.0 — 2026-06-23: Cross-strategy correlation and concurrent drawdown framework added (Week 10 audit Action 6). Correlation rules, concentration limits, and portfolio circuit breaker defined.*
*Update this document when cross-strategy rules change — never mid-week.*
