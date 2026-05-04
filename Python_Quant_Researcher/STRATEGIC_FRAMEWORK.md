# Strategic Framework
## DeFi Quant Engineer Curriculum

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

*Version 1.0 — created 2026-05-04: initial document, Safety Buffer evidence-based framework*
*Update this document when cross-strategy rules change — never mid-week.*
