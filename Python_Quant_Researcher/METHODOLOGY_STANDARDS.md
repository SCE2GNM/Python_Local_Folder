# Methodology Standards
## DeFi Quant Engineer Curriculum

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

*Version 1.0 — created 2026-05-04: initial document*
*Update this document when methodology standards change — never mid-week.*
