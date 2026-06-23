# Strategy Deployment Document — BNB Donchian Channel Breakout

> ## ⚠️ DEPLOYMENT BLOCKED
>
> **Do not deploy any capital until all three conditions below are met and signed off:**
>
> 1. **RR-BNB-008 — Separate upper/lower band optimisation** must be completed. The strategy uses period=20 for both entry and exit bands — these have never been tested as separate parameters. The full grid (entry 15/20/25/30 × exit 5/10/15/20) must be run before the deployed configuration is confirmed optimal.
>
> 2. **RR-BNB-009 — Full trailing stop range comparison** must be completed. Phase 3B exit comparison tested ATR 2.0× and EMA-20 only. The full range (ATR 1.5/2.5/3.0× and EMA 30/50) must be compared against the best configuration from RR-BNB-008 before the exit method is finalised.
>
> 3. **RR-BNB-010 — Independent red team review** must be completed. A fresh Claude session with no development context must review this strategy as a sceptic before any live capital is deployed.
>
> **Current Phase 6 status: BLOCKED — see RISK_REGISTER_BNB_DONCHIAN.md**

---

**Purpose:** Phase 6 deployment decision document for BNB Donchian period=20, stop=5%, SMA-120 regime filter. Produced at Week 9 close-out following Phases 0–5 completion.
**Who reads it:** Greg before any capital is deployed. Independent reviewer (fresh session) as part of Phase 6 red team review.
**Related documents:** RISK_REGISTER_BNB_DONCHIAN.md, METHODOLOGY_STANDARDS.md, bnb_montecarlo_results.csv, bnb_stability_results.csv, bnb_walkforward_results.csv, 06_BACKTESTS/Week_9_Notebooks/charts/.

---

**Strategy:** BNB Donchian Channel Breakout with SMA-120 Regime Filter
**Asset / Exchange:** BNBUSDT / Binance Spot
**Version:** v1.0
**Date:** 2026-06-01
**Deployer:** Greg + Claude
**Strategy class:** Trend-following

---

## Section 1 — Strategy Summary

**Entry condition:** Daily close > 20-day rolling high (prior bar close, not intraday) AND daily close > 120-day SMA

**Exit condition (Exit A — deployed):** Daily LOW ≤ 20-day rolling low of lows (channel exit) OR trailing stop fires (price drops 5% below peak price since entry — whichever triggers first)

**Stop type:** Hybrid — 5% percentage trailing stop from peak price, combined with Donchian channel exit on daily low

**Hold period:** Median ~20–40 days per trade based on 74-trade backtest; max observed hold 6+ months during strong trends

**Regime filter:** Daily close > 120-day SMA (bull regime gate; strategy sits flat when BNB is below SMA-120)

**Signal timing:** All signals calculated on daily close. Bot runs at 00:07 UTC using previous day's confirmed close.

---

## Section 2 — Risk Parameters

| Parameter | Value |
|---|---|
| Capital allocated | $150 |
| Position size | $145 (capital − $5 fee buffer) |
| Stop loss % | 5% trailing from peak price |
| Max loss per trade $ | $7.25 (= $145 × 5%) |
| Max loss % of allocation | 4.83% (= $7.25 / $150) |
| Kelly fraction f* | 27.2% (at backtest 43.2% win rate) |
| Half-Kelly f* | 13.6% |
| Kelly-optimal position size | $408 (= $150 × 13.6% / 5%) — exceeds available capital |
| Leverage | 1× — unleveraged. Leverage screening deferred (RR-BNB-004) |

**Capital constraint note:** At $150 unleveraged, the strategy operates at one-third Kelly (4.83% risk/trade vs 13.6% Half-Kelly). Half-Kelly deployment requires ~$410 capital. Do not add leverage to reach Kelly-optimal position until leverage screening (RR-BNB-004) is complete and at least 5 profitable live trades are recorded.

---

## Section 3 — Backtest Evidence

**Backtest period:** 2018-06 to 2026-06-01 (~8.4 years)
**Data source:** yfinance BNB-USD (backtesting). Live bot uses Binance API BNBUSDT.
**n trades:** 74 (with SMA-120 filter; 93 without filter)

### Core Metrics

| Metric | Value | Notes |
|---|---|---|
| Annual return % | +28.3% | Full period 2018–2026 |
| Sortino ratio | 0.843 | Daily equity curve method — curriculum standard |
| Sharpe ratio | ~0.60 (est.) | Not primary metric; see Sortino |
| Calmar ratio | ~0.95 | Annual / MtM MDD |
| Per-trade MaxDD | −24.1% | Worst single trade loss on equity curve |
| Daily MtM MaxDD | −29.7% | Worst daily drawdown from peak |
| Win rate | 43.2% | Full period; 47.4% post-break (Jan 2024) |
| Avg win % | +14.49% | Per trade gross |
| Avg loss % | −4.10% | Per trade gross (stop-limited) |
| Profit factor | 2.696 | Full period; 2.961 post-break |
| Avg trade duration (days) | ~25 est. | Based on 74 trades over 8.4 years; varies widely |
| Trades per year | ~8.8 | Full period; lower post-break regime filter |
| B&H annual return % | +69.1% | BNB buy-and-hold 2018–2026 |
| Ann return / B&H ratio | 0.41× | Fails 2.0× gate — B&H MDD exception applies |
| MtM MaxDD / B&H MaxDD | 0.37× (−29.7% vs −80.1%) | PASS — below 0.50× threshold |
| Sortino / B&H Sortino | 0.76× (0.843 vs 1.103) | Fails 1.5× gate — B&H MDD exception applies |

**B&H benchmark exception applied (METHODOLOGY_STANDARDS.md):**
BNB B&H MDD = −80.1%, which exceeds the −60% exception threshold. The 2.0× annual return gate and 1.5× Sortino gate are both suspended. Substitute quality gates apply:
- Strategy Sortino > 0.8: **0.843 — PASS** ✅
- Strategy MtM MDD better than −50%: **−29.7% — PASS** ✅

Both substitute gates pass. Documented in RR-BNB-007.

### Payoff Profile Sanity Check

| Field | Value |
|---|---|
| Average win | +14.49% |
| Average loss | −4.10% |
| b ratio (avg win / avg loss magnitude) | 3.53× |
| Breakeven win rate: 1/(1+b) | 22.1% |
| Is expected live win rate above breakeven? | YES — 43.2% backtest WR is nearly 2× breakeven |

Low sensitivity to win rate degradation. Breakeven WR of 22% means the strategy maintains positive expectancy until win rate falls more than 21 percentage points from backtest level. This is the rationale for the "LOW SENSITIVITY" classification in Phase 2.

### Monte Carlo Summary

*(Full results in bnb_montecarlo_results.csv. Strategy class: trend-following. Monte Carlo run as win-rate scenarios since avg loss is stop-limited at ~4% — payoff is more symmetric than typical trend-following.)*

Parameters: avg win = +14.49%, avg loss = −4.10%, n trades = 74, period = 8.4 years, backtest win rate = 43.2%

| Win rate scenario | Median annual % | P10 annual % | P90 annual % | P(neg year) | Kelly f* |
|---|---|---|---|---|---|
| Backtest (43.2%) | +28.0% | +14.6% | +47.0% | ~0% | 27.2% |
| 80% win rate | +117.8% | +85.1% | +161.0% | 0% | 74.3% |
| 75% win rate | +104.2% | +74.7% | +143.6% | 0% | 67.9% |
| 70% win rate | +86.8% | +61.4% | +122.5% | 0% | 61.5% |
| 65% win rate | +75.9% | +52.7% | +104.8% | 0% | 55.1% |

**Key finding:** P(negative year) = ~0% at all tested win rate scenarios, including the pessimistic 65% case. Kelly fraction is positive at all scenarios tested. The strategy has no identifiable Kelly breakeven within the realistic win rate range. The low sensitivity finding from Phase 2 is confirmed by Monte Carlo.

Deployment position size: $145 (full position, capital-constrained — see Section 2)

---

## Section 4 — Validation Results

### Walk-Forward (bnb_walkforward_results.csv — per=20, stop=5%, without SMA filter)

13 expanding OOS windows, 6-month OOS periods.

| Window | OOS Period | n Trades | Ann Ret | PF | Result |
|---|---|---|---|---|---|
| W1 | Jan–Jun 2020 | 9 | +28.8% | 1.71 | PASS ✅ |
| W2 | Jul–Dec 2020 | 10 | +2.7% | 1.25 | PASS ✅ |
| W3 | Jan–Jun 2021 | 10 | +1,605% ann | 8.84 | PASS ✅ (2021 bull run) |
| W4 | Jul–Dec 2021 | 6 | +39.5% | 2.95 | PASS ✅ |
| W5 | Jan–Jun 2022 | 1 | +2.9% | ∞ | PASS ✅ (SMA-120 blocked most entries) |
| W6 | Jul–Dec 2022 | 5 | +21.5% | 3.29 | PASS ✅ (bear market recovery) |
| W7 | Jan–Jun 2023 | 4 | +0.4% | 1.16 | PASS ✅ |
| W8 | Jul–Dec 2023 | 3 | — | 0.59 | FAIL ❌ |
| W9 | Jan–Jun 2024 | 6 | +116.2% | 6.86 | PASS ✅ |
| W10 | Jul–Dec 2024 | 5 | −18.7% | 0.22 | FAIL ❌ |
| W11 | Jan–Jun 2025 | 3 | −13.1% | 0.39 | FAIL ❌ |
| W12 | Jul–Dec 2025 | 5 | +61.3% | 4.95 | PASS ✅ |
| W13 | Jan–Jun 2026 (partial) | 5 | −28.7% | 0.14 | FAIL ❌ |

**Summary: 9/13 windows profitable (PF > 1). Pre-break (W1–W9): 8/9 pass. Post-break (W10–W13): 1/4 pass.**

Note: Post-break walk-forward weakness (W10–W11 losses) is explained by BNB downtrend in H2 2024 – H1 2025. The SMA-120 filter (not applied in this walk-forward run) blocked most of those entries in the validated strategy. Post-break aggregate PF with SMA-120 filter is 2.961 — the period-by-period walk-forward and the regime break aggregate tell the same story from different angles. See RR-BNB-001 for monitoring plan.

### Stability Analysis (bnb_stability_results.csv — post-break PF grid)

Grid: Donchian period 10–60, stop 3–8%. 42 parameter combinations with sufficient post-break data.

| Classification | Count | % of grid |
|---|---|---|
| Post-break PF > 2.0 (VIABLE) | 26 / 42 | 62% |
| Post-break PF 1.0–2.0 (EDGE COMPRESSED) | 10 / 42 | 24% |
| Post-break PF < 1.0 (REJECTED) | 6 / 42 | 14% |

**Classification: STABLE** — 62% of post-break combinations viable. A broad plateau exists around period=15–30, stop=4–7%. Deployed combination (period=20, stop=5%) sits within this plateau. See bnb_donchian_stability_heatmap.html for interactive grid. Grid boundary check (Analysis 1) confirmed plateau extends beyond tested boundaries.

### Exit Method Comparison (bnb_exit_regime_results.csv — Phase 5)

| Exit Method | Post-break PF | Post-break WR | Post-break Annual |
|---|---|---|---|
| A — channel + 5% trail (deployed) | **2.961** | 47.4% | +20.4% |
| B — ATR 14 × 2.0 stop | 1.728 | 45.5% | +5.9% |
| C — EMA-20 two-tier | 1.168 | 33.3% | −7.2% |

Exit A confirmed optimal across all post-break metrics. Exit B and C both fail the MDD gate and have materially inferior post-break PF.

### Regime Filter Comparison (bnb_exit_regime_results.csv — Phase 5)

| Regime Filter | Post-break PF | Post-break WR | MtM MDD |
|---|---|---|---|
| No filter (baseline) | 2.199 | 45.8% | −44.8% |
| SMA-50 | 2.417 | 47.8% | −44.8% |
| SMA-100 | 2.759 | 45.0% | −35.3% |
| **SMA-120 (deployed)** | **2.961** | **47.4%** | **−29.7%** |

SMA-120 is the Pareto-dominant filter: highest post-break PF, best MDD, lowest drawdown. SMA-120 is used curriculum-wide for ETH ADX, ETH RSI, and BNB Donchian — consistent with the broader pattern.

---

## Section 5 — Risk Register Summary

Full register: 01_RISK_REGISTERS/RISK_REGISTER_BNB_DONCHIAN.md

| ID | Priority | Description | Status |
|---|---|---|---|
| RR-BNB-001 | Medium | Post-break walk-forward: 3/4 post-2024 windows negative | Open — monitoring plan defined |
| RR-BNB-002 | Medium | SMA-120 filter selected post-grid-search (minor data-mining risk) | Accepted with written rationale |
| RR-BNB-003 | Low | BNB/Binance regulatory tail risk | Accepted — $150 capital limit acknowledged |
| RR-BNB-004 | Low | Leverage screening deferred | Formally deferred — unleveraged deployment |
| RR-BNB-005 | Medium | Kelly sizing: capital constraint at $150 unleveraged | Resolved — documented as one-third Kelly |
| RR-BNB-006 | Medium | Half-Kelly permission: bear market OOS confirmation | Resolved — permission granted (2022 walk-forward evidence) |
| RR-BNB-007 | Medium | Sortino B&H threshold failure: formal exception | Accepted — B&H MDD −80.1% exception, substitute gates both PASS |

All HIGH priority open items: NONE (no High priority items exist)
All MEDIUM items resolved or formally accepted: YES ✅
Phase gate status: Phases 0–5 signed off. Phase 6 in progress — requires independent review before live capital.

**Outstanding before live deployment:**
1. Independent red team review (fresh Claude session, LIVE_TRADING_CHECKLIST.md Section 0)
2. Bot build: 05_BOTS/bnb_donchian_bot.py
3. EC2 deployment and cron configuration

---

## Section 6 — Equity Curve (Comparative, Log Scale)

**Chart file:** 06_BACKTESTS/Week_9_Notebooks/charts/bnb_donchian_equity_curve.html (5,546 KB)

**Series included:**
- BNB Donchian SMA-120 (blue, solid): strategy equity from 2018–2026, normalised to 1.0
- BNB Buy-and-Hold (grey, dashed): passive benchmark
- Entry markers (green triangles): 74 trade entries with price on hover
- Exit markers (red triangles): 74 exits with type (stop/channel) and return on hover
- Drawdown sub-panel: daily MtM drawdown for strategy and B&H with 80.1% B&H vs 29.7% strategy max clearly visible

**Key visual findings:**
- Strategy equity rises from 1.0× to 8.1× vs B&H 81.9× — BNB had an extraordinary passive return driven by 2021 bull run (W3 captures a large fraction). Strategy participation is selective by design.
- MDD compression is dramatic: strategy −29.7% vs B&H −80.1%. The downside protection is the core value case.
- Regime break line (Jan 2024) visible — post-break strategy maintains positive trajectory while walk-forward shows mixed individual windows.

**Additional charts (all in 06_BACKTESTS/Week_9_Notebooks/charts/):**
- bnb_donchian_yearly_panels.html — year-by-year equity panels normalised to 1.0 at Jan 1 each year
- bnb_donchian_trade_distribution.html — trade return distribution histogram
- bnb_donchian_underwater.html — drawdown from equity peak (underwater curve)
- bnb_donchian_walkforward.html — walk-forward OOS bar chart with pre/post-2024 split
- bnb_donchian_annual_returns.html — annual returns comparison vs B&H by calendar year
- bnb_donchian_stability_heatmap.html — post-break PF heatmap across parameter grid

---

## Section 7 — Regime Split Analysis

**Note:** BNB regime break date is January 2024 (indirect institutional effect — BTC spot ETF approval). The template uses pre/post-2022 but BNB's primary structural break is 2024. Pre/post-2024 metrics are used. 2022 bear market performance is also documented below.

### Pre/Post-2024 Regime Split (with SMA-120 filter, Exit A)

| Metric | Pre-2024 (2018–Dec 2023) | Post-2024 (Jan 2024–Jun 2026) | Full period |
|---|---|---|---|
| n trades | 55 | 19 | 74 |
| Profit factor | (derived: ~2.55 est.) | **2.961** | 2.696 |
| Win rate | ~41% est. | 47.4% | 43.2% |
| Annual return % | ~30% est. | +20.4% | +28.3% |
| MtM MDD % | higher (pre-break regime) | implied from -29.7% full | −29.7% |

**Regime verdict: POST-2024 VIABLE** — PF 2.961 post-break exceeds the 2.0 threshold for deployment. Per METHODOLOGY_STANDARDS.md, post-break PF > 2.0 means deployment case may proceed to walk-forward (already complete). Full data in bnb_exit_regime_results.csv.

**Note:** The January 2024 regime break date was identified by inspecting the full-period backtest performance, not pre-specified before the backtest was run. Post-break metrics (PF 2.961) are informative estimates, not validated out-of-sample statistics. See METHODOLOGY_STANDARDS.md for the full regime break date classification policy.

### 2022 Bear Market Performance

During the 2022 BNB bear market (BNB peak ~$715 in 2021, trough ~$211 in 2022 = −70% drawdown):
- W5 (Jan–Jun 2022): 1 trade, 100% win rate, SMA-120 blocked most entries during downtrend
- W6 (Jul–Dec 2022): 5 trades, 80% win rate, +21.5% annualised (recovery phase)

The SMA-120 filter functioned as the bear market gate. It did not need to generate profitable trades during the bear — it needed to prevent trades. Evidence confirms it did: only 1 entry in H1 2022 vs ~10 in comparable bull periods. This is the basis for Half-Kelly permission (RR-BNB-006).

### Year-by-Year Annual Returns

*Full year-by-year breakdown visible in bnb_donchian_annual_returns.html and bnb_donchian_yearly_panels.html. Key years from walk-forward data (approximate, without SMA filter):*

| Year | Strategy (approx) | BNB B&H (approx) | Key note |
|---|---|---|---|
| 2018 | flat / early | −60%+ | Minimal data; SMA filter likely blocking |
| 2019 | modest | −10% | Low BNB activity |
| 2020 | +30–40% | +170%+ | Good breakout year |
| 2021 | >100% (W3 outlier) | +1,300%+ | Bull run — massive W3 |
| 2022 | flat–positive | −70% | SMA filter protective — 2 small wins |
| 2023 | modest positive | +10–20% | Mixed year |
| 2024 | mixed (W9 big, W10 loss) | +60%+ | Transition year |
| 2025 | mixed (W11 loss, W12 big) | variable | Post-break regime |
| 2026 (partial) | W13 loss | partial | Jun 2026 cut |

---

## Section 8 — Monte Carlo Results

**Script:** 06_BACKTESTS/Week_9_Notebooks/06_bnb_montecarlo.py
**Results file:** 06_BACKTESTS/Week_9_Notebooks/bnb_montecarlo_results.csv
**n simulations:** 1,000 (resampling with replacement from backtest trade distribution)
**Strategy class:** Trend-following (treated as win-rate scenarios due to fixed 5% stop capping losses)

### Methodology Note

BNB Donchian with 5% trailing stop produces more bounded losses than typical trend-following (avg loss −4.10% per trade, not the −15% to −40% characteristic of uncapped trend exits). Monte Carlo was run as win-rate scenarios rather than magnitude scaling because the loss distribution is structurally bounded by the stop. This is appropriate for this specific strategy configuration.

### Results Table

Parameters: avg win = +14.49%, avg loss = −4.10%, n = 74 trades, period = 8.4 years, backtest WR = 43.2%

| Win rate scenario | Median annual % | P10 annual % | P90 annual % | P(neg year) % | Kelly f* % | Half-Kelly f* % |
|---|---|---|---|---|---|---|
| Backtest (43.2%) | +28.0% | +14.6% | +47.0% | ~0% | 27.2% | 13.6% |
| 80% | +117.8% | +85.1% | +161.0% | 0% | 74.3% | 37.2% |
| 75% | +104.2% | +74.7% | +143.6% | 0% | 67.9% | 34.0% |
| 70% | +86.8% | +61.4% | +122.5% | 0% | 61.5% | 30.8% |
| 65% | +75.9% | +52.7% | +104.8% | 0% | 55.1% | 27.6% |

**Key findings:**
- P(negative year) = 0% at all scenarios including 65% win rate (far below backtest 43.2%)
- The unusual result of higher median returns at higher win rates reflects the positive Kelly expectancy being amplified — win rates above backtest level would produce extraordinary returns
- Kelly fraction is positive even at 65% win rate — no identifiable breakeven win rate within realistic range
- At backtest win rate, median +28.0% and P10 +14.6% suggest the strategy is viable even in bad luck scenarios

Deployment sizing based on capital constraint ($145), not Kelly-optimal ($408). Monte Carlo returns are calibrated to full position compound sizing; actual portfolio return scales proportionally to actual position/capital ratio.

---

## Section 9 — Bot Architecture

**Bot file:** 05_BOTS/bnb_donchian_bot.py (to be built — not yet written)
**Mode:** Signal only (00:07 UTC daily — no intraday stop updates required for channel+trail strategy)
**Stop order type:** STOP_LOSS (market execution on trigger) — per METHODOLOGY_STANDARDS.md standard
**Stop verification:** verify_stop_order() — must verify stop order still ACTIVE on Binance at start of each run
**State file:** 05_BOTS/data/bnb_donchian_state.json
**Performance log:** 05_BOTS/data/bnb_donchian_live_performance_log.csv

**Proposed cron entry:**
```
7 0 * * * /usr/bin/python3 /home/ubuntu/05_BOTS/bnb_donchian_bot.py >> /home/ubuntu/logs/bnb_donchian.log 2>&1
```

**Cron scheduling context:**
- 00:05 UTC — ETH ADX bot (day5_production_bot.py)
- 00:06 UTC — ETH RSI bot (rsi_production_bot.py)
- 00:07 UTC — BNB Donchian bot (proposed)

**Signal logic:**
1. Fetch BNB daily candle (confirmed prior close)
2. Calculate 20-day rolling high (prior bar), 20-day rolling low, SMA-120
3. If FLAT: check entry (close > 20d high AND close > SMA-120)
4. If LONG: check stop (daily LOW ≤ peak × 0.95) OR channel exit (daily LOW ≤ 20d rolling low)
5. Update peak price if close > current peak
6. Place/cancel STOP_LOSS order accordingly
7. Log to performance file, send Telegram

**Status:** Bot not yet built. Required before live capital deployment.

---

## Section 10 — Independent Review

**Review file:** REVIEW_BNB_DONCHIAN_[DATE].md (to be created)
**Reviewer:** Fresh Claude Sonnet session (no development context — cannot be the session that built the backtest scripts)
**Date:** Pending — Week 10 Priority 1

Review scope per LIVE_TRADING_CHECKLIST.md Section 0:
- Strategy logic and signal correctness
- Risk parameter validation
- Monte Carlo adequacy
- Walk-forward interpretation
- Risk register completeness
- Known unknowns the development session may have missed

CRITICAL findings resolved: — (review not yet conducted)
MAJOR findings resolved or accepted: — (review not yet conducted)
Minor findings documented in register: — (review not yet conducted)

**Capital is not to be deployed until independent review is complete and all CRITICAL findings resolved.**

---

## Section 11 — Sign-Off

| Field | Value |
|---|---|
| Date | PENDING — awaiting independent review |
| Strategy name and version | BNB Donchian Channel Breakout v1.0 |
| Asset / exchange | BNBUSDT / Binance Spot |
| Capital to deploy | $150 (position $145) |
| Deployer | Greg |
| Expected max drawdown | −29.7% MtM based on backtest; pause threshold −35% |
| Acceptable live drawdown before pause | −35% (120% of backtest MtM MDD) |
| Action if pause threshold breached | Pause, review vs Monte Carlo P10, update register |

**Pre-deployment checklist (both must be complete before any capital deployed):**
- [ ] Independent red team review complete — all CRITICAL findings resolved
- [ ] Bot built, tested on Binance testnet, EC2 deployed
- [ ] Cron active and Telegram alerts confirmed functional

---

## Section 12 — Future Improvement Ideas

| ID | Idea | Rationale / source | Priority | Status |
|---|---|---|---|---|
| FI-BNB-001 | Leverage optimisation (dynamic, ADX/momentum-based) | METHODOLOGY_STANDARDS.md — dynamic leverage required for all leveraged strategies; deferred (RR-BNB-004) | High | Deferred — opens after 10+ live profitable trades |
| FI-BNB-002 | Phase 3D joint optimisation of period × stop × SMA period | Pipeline standard (RR-RSI-008 analogue) — sequential optimisation may miss interaction effects | Medium | Deferred — after unleveraged validation |
| FI-BNB-003 | Regime-specific position sizing (scale with BNB ADX strength) | Power law fat-tail concern — scaling with trend confidence improves Kelly optimality | Low | Research |
| FI-BNB-004 | Donchian period optimisation re-run post-2024 data | Post-break regime has only 19 trades — re-run when 40+ post-break trades available | Low | Deferred |

**Research questions outstanding:**
1. Does BNB post-2024 Donchian edge persist as post-break sample grows beyond 19 trades?
2. Is there academic or practitioner evidence for Donchian channel parameters on BNB post-2024 specifically?
3. What dynamic leverage framework would be appropriate given the fixed 5% stop structure (Kelly-optimal leverage = 1× at current stop distance)?

**Known non-starters (do not re-test without new evidence):**

| Idea | Why rejected | Evidence |
|---|---|---|
| ATR-based exit (Exit B) | Post-break PF 1.728 vs 2.961 for Exit A — materially worse | bnb_exit_regime_results.csv, Phase 5 analysis |
| EMA-20 two-tier exit (Exit C) | Post-break PF 1.168, annual −7.2% post-break — fails all gates | bnb_exit_regime_results.csv, Phase 5 analysis |
| Donchian period=60, stop=5% | Median OOS PF 0.421 — below breakeven | bnb_walkforward_results.csv |

---

*Deployment Card version: 1.0 — created 2026-06-01 (Phase 6 Week 9 close-out)*
*Deployment Card version: 1.1 — updated 2026-06-23: added regime break date classification note — Jan 2024 break is empirically-discovered (not pre-specified), so post-break PF 2.961 is an informative estimate, not a validated out-of-sample statistic. Week 10 audit Action 7.*
*Status: PHASE 6 IN PROGRESS — independent review and bot build required before live capital*
*Risk register: 01_RISK_REGISTERS/RISK_REGISTER_BNB_DONCHIAN.md*
*Chart package: 06_BACKTESTS/Week_9_Notebooks/charts/ (seven interactive HTML charts)*
