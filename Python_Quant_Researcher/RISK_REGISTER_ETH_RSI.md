# Strategy Risk Register — ETH RSI Mean Reversion

**Strategy:** ETH RSI Mean Reversion (RSI-14, oversold bounce)
**Asset / Exchange:** ETHUSDT / Binance Spot
**Version:** v1.0
**Date created:** 2026-05-06
**Last updated:** 2026-05-07
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

**Status:** Open

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

**Status:** Open

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

---

### RR-RSI-006 — Stability analysis not completed

**Category:** Strategy

**Status:** Open

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

---

*(Add further items above this line, preserving the ID sequence)*

---

## Resolved Items

| ID | Description | Resolution summary | Resolved | Week / Date |
|---|---|---|---|---|
| — | — | No resolved items yet | — | — |

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
