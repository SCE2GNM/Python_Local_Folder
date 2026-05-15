# Methodology Standards
## DeFi Quant Engineer Curriculum

**Purpose:** Defines non-negotiable methodology rules that apply to all strategy development, backtesting, and deployment decisions in this curriculum. Every Claude Code session must read this before writing any backtest script.
**Who reads it:** Claude Code at the start of every session. Greg when making strategy decisions.
**When updated:** When a new methodology insight is discovered that should apply to all future work. Never updated mid-backtest.
**Related documents:** STRATEGY_RESEARCH_PIPELINE.md (pipeline phases), STRATEGY_TESTING_CHECKLIST.md (pre-deployment gates), LIVE_TRADING_CHECKLIST.md (deployment sign-off).

---

**Student:** Greg (Gmac)
**Created:** 2026-05-04
**Purpose:** Binding technical standards for backtesting, live execution,
and document production. These standards apply to every strategy.
Where a standard conflicts with a strategy-specific choice, the standard
takes precedence unless an explicit written exception is recorded.

---

## Backtesting Standards

See CURRICULUM_OPERATING_MANUAL.md — Backtesting Requirements for the full
list. Key points reproduced here for cross-reference:

- Daily equity curve method for Sortino and Sharpe (not per-trade annualisation)
- Bar-by-bar stop simulation using daily LOW prices
- 0.15% round-trip transaction costs per trade
- Both per-trade MaxDD and daily MtM MaxDD reported
- Grid boundary check and cliff-edge check required on every optimisation

---

## Live Bot Requirements

### Trailing Stop Implementation

**Standard:** Bot-managed trailing stop using `STOP_LOSS` (market) orders updated 4× per day.

Binance Spot does not support native trailing stops (`TRAILING_STOP_MARKET` is a Futures-only order type, not available to UK retail traders under FCA rules). Use bot-managed trailing stop with 4 daily `STOP_LOSS` order updates at 00:05, 06:05, 12:05, 18:05 UTC:

- **00:05** — signal run: full ADX logic + trailing stop update
- **06:05, 12:05, 18:05** — stop_update runs: trailing stop check only, no entry/exit decisions

On each run when position is LONG:
1. Get current ETH price from Binance ticker (fast, no candle download)
2. If `current_price > peak_price_since_entry`: raise stop to `current_price × (1 − trail_pct)`, cancel old STOP_LOSS order, place new one, update state file, send Telegram
3. If `current_price ≤ peak`: log no-change, no Telegram (avoids noise on quiet runs)

**Implementation:** `callbackRate` parameter is Futures-only. For Spot, compute stop price in bot and place `STOP_LOSS` order at that price. Re-place whenever peak is updated.

**Known deviation from backtest:** The backtest trailing stop updated once per day at close. Bot-managed updates at 4× daily may trigger stop raises from intraday highs that the daily backtest would have missed. This is a **positive deviation** — it locks in more gains on intraday spikes. Expect slightly more frequent stop updates than backtest suggested; trailing stop triggers may also differ marginally.

**State file:** Track `peak_price_since_entry` (high-water mark, never decreases). On entry: `peak = entry_price`. Update whenever stop moves up.

---

### Stop Order Type

**Standard:** `type="STOP_LOSS"` (market execution on trigger)

**Not permitted:** `type="STOP_LOSS_LIMIT"` for any strategy in this curriculum.

**Rationale:** A stop-limit order places a limit order when the stop price is
triggered. If the market price gaps below the limit price (overnight gap, flash
crash, thin liquidity), the limit order sits unfilled and the position remains
open at full exposure. For the strategies in this curriculum — which rely on
the stop as the primary risk control — an unfilled stop is equivalent to having
no stop at all during the most dangerous market conditions.

`STOP_LOSS` on Binance executes as a market order the moment the stop price is
triggered, guaranteeing exit at the best available price. Slippage on ETHUSDT
and BTCUSDT for positions under $500 is negligible in normal conditions.

**Residual risk:** In systemic exchange outages, neither order type guarantees
execution. This is exchange infrastructure risk, not an order type problem, and
is inherent to centralised exchange trading. It is not a reason to prefer
stop-limit orders.

---

### Order Side Effect Types (Margin Accounts)

- Entry orders must use `sideEffectType="MARGIN_BUY"` to borrow at entry.
  Without this, orders execute as unleveraged even on a margin account.
- Exit orders must use `sideEffectType="AUTO_REPAY"` to repay loan and
  accrued interest simultaneously at close.

---

### Performance Logging

After every trade closes, the bot must write to
`data/[strategy]_live_performance_log.csv`:
- date, return%, running annual return%, running Sortino, running MaxDD%,
  consecutive loss count

Telegram alerts mandatory when any of the following are breached:
- Running annual return < 50% of backtest expectation
- Running per-trade MaxDD exceeds backtest MaxDD
- 3 consecutive losing trades
- Running Sortino drops below 0.6
- Quarterly summary (cron every 90 days) regardless of alerts

---

## Leveraged Strategy Standards

### Dynamic Leverage Requirement

**Standard:** For all leveraged strategies, leverage must scale with trend strength indicator — not be fixed at entry. Maximum leverage is deployed only at peak trend confidence. Leverage is reduced as the exit signal approaches. Static maximum leverage at entry is not permitted for any new leveraged strategy from Week 8 onwards.

**Rationale:** Established in Week 7 based on exchange failure risk analysis (A021). Binance has documented stop order failures during extreme market stress (October 2025 crash, March 2023 trailing stop bug). At fixed 1.9× leverage, a 20% ETH decline during a 2-hour exchange outage produces a 38% loss on own capital with no stop ever firing. Dynamic leverage reduces maximum exposure to periods of genuine trend strength — the exact conditions where stop execution is most reliable. At ADX levels near the exit threshold, leverage is already reducing toward 1×, limiting outage exposure to the phase where trend confidence is lowest.

**Implementation requirement:** Any leveraged strategy submitted for deployment review must include a backtested dynamic leverage function mapping the trend indicator value to a leverage multiplier. The function must be monotone (higher indicator → higher leverage) and bounded at the safety buffer minimum. Flat leverage is not acceptable.

---

## Momentum Strategy Validation Standards

### Kelly Sizing for Momentum Strategies

**Standard:** Quarter-Kelly is the default position sizing for any momentum strategy not yet confirmed through a full crash cycle (2022 or equivalent bear market). Half-Kelly is permitted only after out-of-sample confirmation through a bear market period.

**Rationale:** Established in Week 7 based on power law distribution research findings (Grobys et al. 2025, Huang et al. 2024). Cryptocurrency momentum strategy returns have a tail index α < 3, placing them in the unstable variance zone where standard statistical confidence intervals are unreliable. A 5-year backtest with excellent metrics is statistically consistent with the strategy having negative long-run performance if the defining extreme event has not yet occurred in the sample. Quarter-Kelly builds in the additional margin of safety warranted by this structural uncertainty.

**Application:**
- ETH ADX trend-following: half-Kelly permitted — confirmed through 2022 (+35.1% when B&H −68.3%)
- Any new momentum strategy (Donchian, MAX, MACD-based) without 2022 confirmation: quarter-Kelly at deployment
- Promotion from quarter-Kelly to half-Kelly: requires at least one bear market validation period in live or out-of-sample data

**Scope:** Momentum strategies only. Mean reversion strategies (Bollinger, MIN, RSI-based) are less affected by power law variance instability because they cap individual trade size by design. Half-Kelly remains the default for mean reversion strategies subject to normal Monte Carlo confirmation.

---

## Chart Production Standards

All strategy deployment documents must include:
1. Interactive equity curve (Plotly HTML): leveraged vs unleveraged vs B&H,
   log scale, daily MtM, entry/exit markers, drawdown panel as lines
2. Year-by-year equity panels (one per year, normalised to 1.0 at year start)
3. Parameter sensitivity plateau charts
4. Walk-forward results bar chart

Static PNG acceptable for quick reference only. Interactive HTML is the
deployment standard.

---

## Document Versioning Protocol

Each living document has exactly one file. No versioned copies (vN) are maintained. At the end of each week, upload the current versions of all modified living documents to the Claude Project to keep project knowledge current. Documents modified during a given week are identified in the Week N summary document.

---

---

## Fat-Tail Warning — Metrics That Assume Normality

All of the following metrics assume either normally distributed returns or finite/stable variance. Both assumptions are violated for crypto momentum strategies (power law exponent α < 3, confirmed Grobys et al. 2025, Huang et al. 2024). These metrics remain useful as relative comparators and directional indicators but must NOT be treated as precise absolute measures or used as hard decision gates in isolation:

**Sharpe ratio:** uses standard deviation in denominator. Unstable when variance is fat-tailed. Use as relative comparator only — never as an absolute quality threshold.

**Sortino ratio:** uses downside standard deviation. Same instability. Retained as primary ratio metric per Week 5 decision but interpreted with caution for momentum strategies.

**Kelly fraction:** assumes stationary win rate and R:R ratio. Fat-tailed returns mean these parameters shift with extreme events. Always use Half-Kelly minimum; use Quarter-Kelly for unvalidated momentum strategies.

**Confidence intervals on backtest metrics:** standard intervals assume normality. True intervals are materially wider. Monte Carlo simulation is the correct substitute — it uses the actual observed trade distribution rather than assuming a parametric form.

**Value at Risk (VaR):** not currently used but flag for future reference — entirely inappropriate for fat-tailed distributions.

**Mitigation for all affected metrics:**

- Never use a single metric as a hard GO/NO-GO gate — require convergence across multiple metrics
- Always run Monte Carlo — it is the only method that does not assume normality
- Weight out-of-sample and walk-forward results more heavily than full-period backtest metrics
- Apply additional conservatism to Kelly sizing for momentum strategies (Quarter-Kelly standard)
- When metrics conflict, favour the more conservative interpretation

This warning applies to ALL momentum strategies. Mean reversion strategies are relatively less affected due to narrower trade return distributions but the warning still applies.

Added: Week 7. Source: STRATEGY_RESEARCH_PIPELINE.md Phase 3 requirements, Grobys et al. (2025), Huang et al. (2024), LEARNING_LOG.md power law distributions entry.

---

*Version 1.0 — created 2026-05-04: initial document*
*Version 1.1 — updated 2026-05-15: added Fat-Tail Warning section (normality assumptions)*
*Update this document when methodology standards change — never mid-week.*
