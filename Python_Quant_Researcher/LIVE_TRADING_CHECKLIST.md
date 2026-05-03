# Live Trading Pre-Deployment Checklist

**This checklist must be completed in full before deploying any strategy to live capital.**

Partially completed checklists are not acceptable. If any item cannot be checked, document
the reason and obtain explicit written sign-off before proceeding. Archive a completed copy
of this checklist alongside each deployment (e.g. `checklists/CHECKLIST_ETH_ADX_v2_2026-05-01.md`).

---

## Instructions

- Check each item as `[x]` when confirmed PASS
- Leave as `[ ]` if not yet confirmed — do not proceed with incomplete items
- For leveraged strategies, all leveraged-specific items are mandatory
- For unleveraged strategies, leveraged items may be marked `[N/A]` with a note

---

## 1. Backtest Quality

- [ ] Daily equity curve method used for Sharpe and Sortino (not per-trade annualisation)
- [ ] Sharpe ratio confirmed calculated from daily equity curve (not per-trade returns). Per-trade method inflates Sharpe by 3-5x. Week 5 confirmed correct method: `mean(daily_returns) / std(daily_returns) * sqrt(365)`
- [ ] Sortino ratio confirmed calculated from daily equity curve (not per-trade returns). Per-trade method inflates Sortino by 3-4x. Correct method: `mean(daily_returns) / std(downside_daily_returns) * sqrt(365)` where downside = only days with negative returns
- [ ] Transaction costs applied per trade at confirmed rate (confirm actual Binance fee tier before marking)
- [ ] Stop-loss modelled bar-by-bar using daily LOW prices (not close prices)
- [ ] All exit mechanisms explicitly documented: which are modelled in backtest (per-trade stop, strategy exit signal) and which are excluded (portfolio guardrail, daily loss limit) with written rationale for any exclusions
- [ ] Grid search boundary check completed — confirm best result does not sit at the maximum or minimum edge of the tested parameter range. If it does, extend the range before accepting the result as a genuine optimum.
- [ ] Parameter sensitivity cliff-edge check completed — confirm chosen parameters sit at or near the PEAK of the annual return % sensitivity curve, not on a declining slope toward a performance cliff. This applies to the primary objective metric (annual return %) not to Calmar or composite score.
- [ ] Walk-forward validation completed using BOTH methods:
  (1) Expanding window (anchored) — training period always starts at inception, grows with each window. Tests whether strategy works as more history accumulates.
  (2) Rolling window (sliding) — fixed-length training period slides forward, old data drops off. Tests whether strategy works across different market regimes including periods where exceptional years are excluded from training data.
  Both methods must pass (profitable in all windows) before deployment. If rolling window fails due to very small sample size per window (fewer than 5 trades), document explicitly with written rationale for proceeding or not.
  **Fixed-parameter note:** When using fixed parameters without per-window re-optimisation, expanding and rolling window results are mathematically identical. If this is the case, document it explicitly — do not present two identical result sets as independent validation. True walk-forward with per-window re-optimisation is the stronger test and is the standard to target.
- [ ] Buy-and-hold relative threshold check — confirm the strategy clears all three bars vs passive B&H for the same asset over the same period: (1) Annual return ≥ 2.0× B&H annual return; (2) Daily MtM MaxDD ≤ 0.50× B&H MaxDD; (3) Sortino ≥ 1.5× B&H Sortino. Report all three ratios explicitly. A strategy that beats B&H on one metric but not all three does not have a clear edge over passive holding.
- [ ] Stability analysis passed — key parameters stable across ≥50% of sub-periods
- [ ] Minimum 30 trades in full-period backtest (fewer than 30 = do not deploy)
- [ ] MaxDD figure confirmed and labelled correctly — per-trade MaxDD (peak-to-trough on completed trade returns) and daily mark-to-market MaxDD (worst intraday portfolio value vs peak) are different measures. Both must be reported. Daily mark-to-market is what you experience watching a live account.
- [ ] Equity curve construction verified — when comparing multiple strategies, all use identical daily mark-to-market construction. Portfolio value updated every calendar day based on the closing price of any open position. Not updated only at trade exits. Inconsistent construction between strategies creates misleading visual comparisons (e.g., one strategy shows smooth intraday tracking, another shows flat periods with spikes at exits — the difference is a bug, not a strategy characteristic).
- [ ] Interactive HTML chart produced for all multi-metric comparisons — static PNG acceptable for quick reference only. The deployment document must include an interactive Plotly HTML chart for the equity curve and drawdown profile, allowing hover inspection of exact values at any date. Minimum hover data: date, portfolio value, drawdown from peak %, position open/flat, days in trade if open.
- [ ] Backtest data range documented (start date, end date, source)
- [ ] No look-ahead bias confirmed (signals computed from data available at bar close only)

---

## 2. Risk Register

- [ ] Per-strategy Risk Register reviewed in full (current date)
- [ ] All High priority items: status is RESOLVED
- [ ] All Medium priority items: status is RESOLVED, or formally accepted with written rationale in register
- [ ] No new risks identified since last register review
- [ ] Risk Register last-updated date is within 7 days of deployment date

---

## 3. Bot Mechanics

- [ ] Bot entry logic matches backtest exactly (ADX threshold, period, DI+ > DI- condition)
- [ ] Bot exit logic matches backtest exactly (signal reversal exit and stop-loss exit)
- [ ] Stop type correctly implemented and matches backtest:
  - [ ] Fixed stop: stop price set at entry, never updated
  - [ ] Percentage trailing stop: stop updated upward with each new close high
  - [ ] ATR trailing stop: stop = peak − (multiplier × ATR), ratchets upward only
- [ ] Stop checked against live price (not just at candle close) where required
- [ ] Position sizing reads live account balance correctly (not hardcoded)
- [ ] Telegram alerts tested end-to-end: entry signal, exit signal, stop trigger, error
- [ ] Full trade cycle tested on Binance testnet (entry → hold → exit via stop or signal)
- [ ] Daily loss limit explicitly reviewed — default 2% is inappropriate for daily candle strategies. Must be set to a strategy-appropriate level or removed, with written rationale documented
- [ ] Bot handles edge cases: no signal, consecutive signals, gap opens
- [ ] Automated performance monitoring configured.
  Do NOT use manual trade-count review triggers
  for low-frequency strategies (<5 trades/year).
  Bot must automatically:
  (1) Log metrics after every trade closes to
      data/[strategy]_live_performance_log.csv:
      date, return%, running annual return%,
      running Sortino, running MaxDD%,
      consecutive loss count
  (2) Send Telegram alert when any threshold breached:
      running annual return < 50% of backtest expectation,
      running per-trade MaxDD exceeds backtest MaxDD,
      3 consecutive losing trades,
      running Sortino drops below 0.6
  (3) Send quarterly Telegram performance summary
      (cron every 90 days) regardless of alerts
- [ ] Review triggers are time-based not trade-count-based
  for low-frequency strategies.
  Quarterly automated review mandatory minimum.
  Annual full parameter re-evaluation mandatory.

---

## 4. Capital and Margin

- [ ] Capital allocated and funded in correct exchange wallet
- [ ] Position size formula verified against current balance
- [ ] For leveraged strategies: isolated margin wallet funded (not cross-margin)
- [ ] For leveraged strategies: AUTO_REPAY enabled on Binance margin account
- [ ] For leveraged strategies: leverage level set correctly on the trading pair in Binance UI
- [ ] For leveraged strategies: liquidation price calculated and documented below
- [ ] For leveraged strategies: safety buffer confirmed ≥25% above liquidation at entry
- [ ] For leveraged strategies: current borrow interest rate confirmed on Binance Margin Data page

**Leverage documentation (complete if applicable):**

| Field | Value |
|---|---|
| Leverage level | |
| Own capital | |
| Borrowed capital | |
| Entry price (example) | |
| Liquidation price | |
| Safety buffer % | |
| Interest rate (annual) | |
| Interest cost per trade (estimated) | |

---

## 5. Operational

- [ ] Cron job scheduled and confirmed active (`crontab -l` output verified)
- [ ] EC2 instance running, accessible via SSH, and confirmed healthy
- [ ] All dependencies installed on EC2 (Python packages, ta-lib if required)
- [ ] Code committed to GitHub — no uncommitted changes on EC2
- [ ] Environment variables set on EC2 (API keys, Telegram token, bot config)
- [ ] Daily loss limit reviewed and set appropriately for this strategy's volatility profile
- [ ] Log file path confirmed writeable and monitored
- [ ] First scheduled run time noted and confirmed (next candle close after deployment)

---

## 6. Sign-off

- [ ] All above items checked PASS (or formally accepted with documented rationale)
- [ ] Expected drawdown profile reviewed and accepted:
  - Expected max drawdown: _____%
  - Worst historical drawdown in backtest: _____%
  - Acceptable live drawdown before pause: _____%
- [ ] If drawdown exceeds the pause threshold, action is: _______________________

| Field | Value |
|---|---|
| Date | |
| Strategy name and version | |
| Asset / exchange | |
| Capital deployed | |
| Deployer | |

---

*Template version: 1.3 — updated 2026-05-03: added equity curve construction verification item; added interactive HTML chart requirement; updated automated monitoring wording*
*Template version: 1.1 — updated 2026-05-02: added B&H relative threshold check; added fixed-parameter walk-forward note*
*Template version: 1.0 — created 2026-05-01*
*Review and update this template after any deployment incident or process change.*
