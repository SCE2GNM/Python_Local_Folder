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
