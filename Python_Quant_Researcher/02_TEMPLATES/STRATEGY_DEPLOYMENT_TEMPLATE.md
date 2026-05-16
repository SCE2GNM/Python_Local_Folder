# Strategy Deployment Document — [STRATEGY NAME]

**Purpose:** Template for creating new strategy deployment documents. Copy this file when a new strategy reaches the deployment decision phase. Fill in all sections before any live capital is deployed.
**Who reads it:** Claude Code when creating a new deployment card.
**When updated:** When the deployment card format is improved. Apply improvements to new cards — do not retroactively update existing cards unless a material error is found.
**Related documents:** ETH_ADX_Deployment_Card_v1.html, ETH_RSI_Deployment_Card_v1.html, LIVE_TRADING_CHECKLIST.md, WEEK_7_RESEARCH_BRIEF_FULL.md, LEARNING_LOG.md.

---

**Strategy:** [e.g. ETH RSI Mean Reversion]
**Asset / Exchange:** [e.g. ETHUSDT / Binance Spot]
**Version:** [e.g. v1.0]
**Date:** [YYYY-MM-DD]
**Deployer:** [Name]
**Strategy class:** [Trend-following / Mean reversion] — determines Monte Carlo methodology (Section 8)

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

### Monte Carlo Summary

*(Full Monte Carlo with equity fan is in Section 8. This table is a quick-reference summary only.)*

| Scenario | Median Annual% | P10 Annual% | P(neg year) | Quarter-Kelly |
|---|---|---|---|---|
| Backtest (___%) | | | | |
| Stress case | | | | |

Deployment position size based on: [scenario] = $____

See Section 8 for full methodology, equity fan, and all scenario rows.

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

## Section 6 — Equity Curve (Comparative, Log Scale)

**Chart type:** Interactive Plotly HTML — mandatory. Static PNG not acceptable for deployment card.
**File:** [path to .html file]

**Requirements:**
- Log scale y-axis (mandatory — linear scale masks early-period moves)
- All series normalised to $1.00 on 2018-01-01
- Daily mark-to-market construction throughout — portfolio value updated every calendar day using closing price of any open position, not only at trade exits
- Hover data minimum: date, portfolio value, drawdown from peak %, position open/flat, days in trade (if open)

**Series included:**

> **Standing rule:** Section 6 must always include all strategies in the same class (trend-following or mean reversion) overlaid on the same chart for direct comparison. Do not produce a chart that shows only the current strategy against B&H. If any same-class strategy has been validated, it must appear on this chart.

| Series | Colour | Style |
|---|---|---|
| ETH ADX trailing stop | Blue (#1f77b4) | Solid |
| BTC SMA trailing stop | Teal (#17becf) | Solid |
| ETH RSI mean reversion | Orange (#ff7f0e) | Solid |
| [This strategy — complete row] | [Colour] | Solid |
| Rejected strategies | Grey (#aaaaaa) | Dashed |
| BTC buy-and-hold benchmark | Dark grey (#333333) | Dotted |
| ETH buy-and-hold benchmark | Light grey (#999999) | Dotted |

*Add or remove rows for the strategies relevant to this deployment card. Colour coding is fixed — do not change colours between cards.*

**Drawdown sub-panel:**
Include a drawdown panel below the equity curve showing daily MtM drawdown from peak for each strategy. Same colour coding. This panel is mandatory — it makes the risk difference between strategies visible without requiring the reader to calculate from equity values.

---

## Section 7 — Pre/Post-2022 Regime Split

**Chart type:** Bar chart — mandatory for all deployment cards regardless of strategy type.
**Purpose:** Confirm the strategy performs acceptably in both bull (pre-2022) and bear/recovery (post-2022) regimes. A strategy that works only in one regime is not deployable.

**Threshold for post-2022 annual return:** ≥ +15%/yr required for GO. Document explicitly if failing.

| Metric | Pre-2022 (2018–2021) | Post-2022 (2022–present) | Full period |
|---|---|---|---|
| Annual return % | | | |
| Sortino ratio | | | |
| MtM MaxDD % | | | |
| Win rate % | | | |
| n trades | | | |
| Avg win % | | | |
| Avg loss % | | | |

**Year-by-year annual return:**

| Year | Annual return % | BTC B&H % | ETH B&H % | n trades |
|---|---|---|---|---|
| 2018 | | | | |
| 2019 | | | | |
| 2020 | | | | |
| 2021 | | | | |
| 2022 | | | | |
| 2023 | | | | |
| 2024 | | | | |
| 2025 | | | | |
| 2026 (partial) | | | | |

**Regime verdict:** [PRE-2022 PASS / POST-2022 PASS / POST-2022 FAIL — see rationale]

If post-2022 fails: document rationale for proceeding or explicit NO-GO:
> [Rationale]

---

## Section 8 — Monte Carlo Results

**Script:** [path to Monte Carlo script]
**Results file:** [path to CSV]
**n simulations:** 10,000
**Strategy class:** [Trend-following / Mean reversion] — determines methodology below

---

### Methodology

**Trend-following strategies → Option A: Return Magnitude Scaling**

Winners scaled by factor (100%, 80%, 60%, 40%, 20%); losers unchanged (structurally determined by stop distance). Standard win-rate scenario framework is inappropriate for low win rate / fat-tail payoff structures (typical win rates 20–35%, avg wins 40–150%+). The relevant stress dimension for trend-following is: *what if future trends are smaller?* Do not substitute win-rate scenarios for magnitude scaling on momentum strategies.

Fat-tail warning: Kelly fraction computed from binary formula will be unreliable (produces fractions >100%) for strategies with avg loss < 5% and avg win > 40%. Report quarter-Kelly for reference only. Use fixed capital-at-risk sizing (5–10%) for initial deployment.

**Mean-reversion strategies → Win Rate Scenario Table**

Resample trades at degraded win rates. Mean reversion strategies have win rates 50–70% and more symmetric payoffs — the Kelly formula is reliable and win-rate stress testing is the appropriate framework.

---

### Results Table

**Trend-following (magnitude scaling):**

Parameters: avg win = ___%, avg loss = ___%, n trades = ___, period = ___ years, win rate = ___%

| Win magnitude scale | Median annual % | P10 annual % | P90 annual % | P(neg year) % | Quarter-Kelly % | Break-even? |
|---|---|---|---|---|---|---|
| 100% (backtest) | | | | | | |
| 80% | | | | | | |
| 60% | | | | | | |
| 40% | | | | | | |
| 20% | | | | | | |

At what magnitude does median annual return first turn negative? ____%

**Mean-reversion (win rate scenarios):**

Parameters: avg win = ___%, avg loss = ___%, n trades = ___, period = ___ years

| Win rate scenario | Median annual % | P10 annual % | P90 annual % | P(neg year) % | Kelly f* % | Quarter-Kelly % |
|---|---|---|---|---|---|---|
| Backtest (___%) | | | | | | |
| 80% of backtest | | | | | | |
| 75% | | | | | | |
| 70% | | | | | | |
| 65% | | | | | | |

Breakeven win rate for positive Kelly: ____%
Expected live win rate range: ____% to ____%
Deployment position size based on: ____% win rate scenario = $____

---

### Equity Fan — Year-End Portfolio Values

Resampled from backtest trade distribution. Portfolio value relative to start = 1.0.

| Year | P5 | Median (P50) | P95 |
|---|---|---|---|
| 2018 | | | |
| 2019 | | | |
| 2020 | | | |
| 2021 | | | |
| 2022 | | | |
| 2023 | | | |
| 2024 | | | |
| 2025 | | | |
| 2026 (partial) | | | |

P5/P95 ratio at end of period: ____× — note this for interpreting outcome dispersion.

---

## Section 9 — Bot Architecture

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

## Section 10 — Independent Review

**Review file:** REVIEW_[STRATEGY]_[DATE].md
**Reviewer:** Fresh Claude Sonnet/Opus session (no development context)
**Date:** [YYYY-MM-DD]

CRITICAL findings resolved: [n/n]
MAJOR findings resolved or accepted: [n/n]
Minor findings documented in register: YES / NO

---

## Section 11 — Sign-Off

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

## Section 12 — Future Improvement Ideas

**Purpose:** Document research-backed improvement candidates specific to this strategy. Populated from WEEK_7_RESEARCH_BRIEF_FULL.md and LEARNING_LOG.md. These are not deployed — they are a structured list of what to test next if the strategy is scaled or reviewed.

**How to populate:** At deployment time, review LEARNING_LOG.md for ideas tagged to this strategy's asset or class. Review WEEK_7_RESEARCH_BRIEF_FULL.md for outstanding research items. Add only ideas with a specific research rationale — not generic wishlist items.

| ID | Idea | Rationale / source | Priority | Status |
|---|---|---|---|---|
| FI-001 | [e.g. Volatility-adjusted position sizing] | [e.g. LEARNING_LOG §Power law — fixed sizing ignores regime variance] | High / Med / Low | Research / Backtest / Deferred |
| FI-002 | | | | |
| FI-003 | | | | |

**Research questions outstanding:**

1. [e.g. Does regime filter (e.g. 200MA trend direction) reduce bear-year losses without materially reducing bull-year return?]
2. [e.g. Is there a parameter set that improves post-2022 performance without overfitting to the 2022-2026 window?]
3. [Add strategy-specific questions]

**Known non-starters (do not re-test without new evidence):**

| Idea | Why rejected | Evidence |
|---|---|---|
| [e.g. Shorter SMA period] | [Increases whipsaw trades in volatile regimes] | [Stage B sweep, 2026-05-XX] |

---

*Template version: 2.0 — updated 2026-05-16: added Section 6 (equity curve comparative log scale), Section 7 (pre/post-2022 regime split), Section 8 (Monte Carlo with methodology split — Option A for momentum, win rate for mean reversion); renumbered prior Sections 6/7/8 to 9/10/11; added Section 12 (future improvement ideas). Colour coding standard added to Section 6.*
*Template version: 1.0 — created 2026-05-07*
*Derived from LIVE_TRADING_CHECKLIST.md v1.9 and STRATEGY_RESEARCH_PIPELINE.md v1.5*
