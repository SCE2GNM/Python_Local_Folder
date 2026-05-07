# Strategy Deployment Document — [STRATEGY NAME]

**Strategy:** [e.g. ETH RSI Mean Reversion]
**Asset / Exchange:** [e.g. ETHUSDT / Binance Spot]
**Version:** [e.g. v1.0]
**Date:** [YYYY-MM-DD]
**Deployer:** [Name]

---

## Section 1 — Strategy Summary

**Entry condition:** [e.g. RSI-14 < 30, price > 120MA]
**Exit condition:** [e.g. RSI-14 > 70]
**Stop type:** [e.g. Fixed 15% / Percentage trailing 8% / ATR trailing]
**Hold period:** [e.g. 1–3 days typical, max 7 days]
**Regime filter:** [e.g. Price > 120-day MA]

---

## Section 2 — Risk Parameters

| Parameter | Value |
|---|---|
| Capital allocated | $ |
| Position size | $ |
| Stop loss % | % |
| Max loss per trade $ | $ |
| Max loss % of allocation | % |
| Kelly fraction f* | % |
| Kelly-optimal position size | $ |
| Leverage | × (if applicable) |

---

## Section 3 — Backtest Evidence

**Backtest period:** [Start date] to [End date]
**Data source:** [Binance / yfinance]
**n trades:** [Number]

### Core Metrics

| Metric | Value |
|---|---|
| Annual return % | |
| Sortino ratio | |
| Sharpe ratio | |
| Calmar ratio | |
| Per-trade MaxDD | |
| Daily MtM MaxDD | |
| Win rate | |
| Avg win % | |
| Avg loss % | |
| Profit factor | |
| Avg trade duration (days) | |
| Trades per year | |
| B&H annual return % | |
| Ann return / B&H ratio (≥2×) | |
| MtM MaxDD / B&H MaxDD (≤0.5×) | |
| Sortino / B&H Sortino (≥1.5×) | |

### Payoff Profile Sanity Check

| Field | Value |
|---|---|
| Average win | % |
| Average loss | % |
| b ratio (avg win / avg loss magnitude) | |
| Breakeven win rate: 1/(1+b) | % |
| Is expected live win rate above breakeven? | YES / NO |

If NO: document justification for deployment:
> [Justification]

### Monte Carlo Stress Test Results

*(Required if backtest trades < 100)*

Parameters: avg win = ___%, avg loss = ___%, n trades = ___, period = ___ years

| Win Rate Scenario | Median Annual% | 10th Pct% | 90th Pct% | P(neg year) | Kelly f* | Position Size |
|---|---|---|---|---|---|---|
| Backtest (___%) | | | | | | |
| 80% | | | | | | |
| 75% | | | | | | |
| 70% | | | | | | |
| 65% | | | | | | |

Breakeven win rate for positive Kelly: ____%
Expected live win rate range: ____% to ____%
Deployment position size based on: ____% win rate scenario = $____

---

## Section 4 — Validation Results

### Walk-Forward

| Window | Period | n Trades | Annual Return | Result |
|---|---|---|---|---|
| 1 | | | | PASS / FAIL |
| 2 | | | | PASS / FAIL |
| 3 | | | | PASS / FAIL |

### Stability Analysis

| Parameter | STABLE / MARGINAL / FRAGILE | Notes |
|---|---|---|
| [Primary parameter] | | |
| [Secondary parameter] | | |

### Factor of Safety Stress Test

| Scenario | Annual Return | Pass (>15%)? |
|---|---|---|
| Win rate −20% | | |
| Avg loss +20% | | |
| Costs doubled | | |
| Stop slippage doubled | | |

---

## Section 5 — Risk Register Summary

| ID | Priority | Description | Status |
|---|---|---|---|
| | HIGH | | Open / Resolved |
| | MAJOR | | Open / Resolved |

All HIGH items resolved: YES / NO
All MAJOR items resolved or formally accepted: YES / NO

---

## Section 6 — Bot Architecture

**Bot file:** [path]
**Mode(s):** [e.g. --mode=signal (00:05 UTC), --mode=stop_update (06:05, 12:05, 18:05 UTC)]
**Stop order type:** STOP_LOSS (market, guaranteed execution)
**Stop verification:** verify_stop_order() runs at start of every execution
**State file:** [path]
**Performance log:** [path]

**Cron entries:**
```
[paste crontab -l output]
```

---

## Section 7 — Independent Review

**Review file:** REVIEW_[STRATEGY]_[DATE].md
**Reviewer:** Fresh Claude Sonnet/Opus session (no development context)
**Date:** [YYYY-MM-DD]

CRITICAL findings resolved: [n/n]
MAJOR findings resolved or accepted: [n/n]
Minor findings documented in register: YES / NO

---

## Section 8 — Sign-Off

| Field | Value |
|---|---|
| Date | |
| Strategy name and version | |
| Asset / exchange | |
| Capital deployed | |
| Deployer | |
| Expected max drawdown | % |
| Acceptable live drawdown before pause | % |
| Action if pause threshold breached | |

---

*Template version: 1.0 — created 2026-05-07*
*Derived from LIVE_TRADING_CHECKLIST.md v1.9 and STRATEGY_RESEARCH_PIPELINE.md v1.5*
