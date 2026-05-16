# Week 6 Thread Starter
## DeFi Quant Engineer Curriculum
**Student:** Greg (Gmac)
**Week:** 6 of 24
**Dates:** TBD
**Status:** Planning — continuation from Week 5 extension work

---

## Context for Claude Code

This file provides full context for Week 6. Read this before doing anything else.

You are acting as Greg's quant curriculum tutor and technical collaborator. The teaching style is: explain concepts before writing code, one step at a time, honest assessment of weaknesses, all risks tracked in the Risk Register.

The project lives at:
`/Users/Greg/Documents/Python_Local_Folder/Python_Quant_Researcher/`

Python 3.12, virtual environment at `venv/`, VS Code, GitHub (SCE2GNM/execution-engine), AWS EC2 (3.104.101.30, ap-southeast-2, Elastic IP).

---

## What is live and running

| Strategy | Asset | Capital | Status | Notes |
|----------|-------|---------|--------|-------|
| ADX 20/10 | ETH | $1,000 | LIVE on EC2 | Cron 00:05 UTC daily |
| RSI 14/43/48 | ETH | $500 | PENDING | EC2 deployment deferred to Week 6 |
| BB 15/2.0 | ETH | $0 | Paper trading | Pending further validation |

EC2 bot: `day5_production_bot.py` running via cron and systemd.
State file: `data/bot_state.json`
Log file: `/home/ubuntu/logs/adx_strategy.log`

---

## Week 5 Summary — What Was Accomplished

### Part A — ADX Strategy Refinement (Days 1-3)
- **Day 1:** Stop-loss aware backtest built (bar-by-bar, daily LOW prices). Results: 108 trades, win rate 34.3%, profit factor 3.197, max drawdown -30.3%.
- **Day 2:** Kelly recalculated (11.77%, immaterial change). Portfolio simulator built — 5 sizing strategies compared. Resolved A001, A005, A007.
- **Day 3:** Joint parameter optimisation — 392 combinations. Live params (ADX 20/10, 5% stop) ranked 22nd. 100% stability on all parameters. Resolved A006.

### Part B — Mean Reversion Strategies (Days 4-7)
- **BB v3:** window=15, std=2.0, stop=10%, 150MA. PF 3.497, win rate 80.8%, 26 trades. Paper trading.
- **RSI final:** period=14, oversold<43, exit>48, stop=15%, 120MA. PF 5.593, win rate 93.5%, 31 trades. Stability 80-100% all params. Validated on BTC (PF 2.450). Approved for deployment at $500, 15% sizing.
- **Combined BB+RSI:** PF 6.353 but only 17 trades — not deployed.
- **Walk-forward:** Both strategies profitable in all 3 test windows.

### Week 5 Extension Work
- **BTC ADX:** Independently optimised (ADX 19/14, 3% stop). Calmar 1.121. 100% stability.
- **BTC SMA 125:** Price crosses 125-day SMA. Calmar 3.506 (no leverage), profit factor 15.641 (25 trades — small sample). Stability: Calmar 56%, Sharpe 100%, PF 92%.
- **Sharpe correction:** Fixed per-trade annualisation bug. Correct values: ADX Sharpe 0.817, Sortino 1.070.
- **Benchmark comparison:** ADX outperforms buy-and-hold ETH (67.4% vs 12.9%/yr). Equal-weight basket 43.4%/yr.
- **Kelly sizing comparison:** All-in ($70,779) vs Kelly ($2,046) from $1,000. Calmar stays constant across sizing levels — leverage scales proportionally.
- **Margin backtest v1:** Hold days bug identified and fixed. Interest costs negligible for ADX (~$30 over 108 trades at 2x). Preliminary results suggest 2x leverage optimal for ETH ADX at 12.41% sizing.
- **SMA crossover:** ETH SMA 35 (Calmar 1.411), BTC SMA 125 (Calmar 3.506). BTC SMA dramatically outperforms BTC ADX on Calmar.

### Key Metrics — All Strategies (Daily Equity Curve Method)

| Strategy | Annual | Max DD | Calmar | Sharpe | Sortino | PF | Trades |
|----------|--------|--------|--------|--------|---------|-----|--------|
| ADX ETH 20/10 | 67.4% | -40.9% | 1.645 | 0.817 | 1.070 | 3.197 | 108 |
| RSI ETH final | 16.9% | -16.0% | 1.054 | 1.205 | 0.265 | 5.593 | 31 |
| BB v3 ETH | 14.8% | -19.2% | 0.768 | 1.040 | 0.220 | 3.497 | 26 |
| BTC SMA 125 | 19.8% | -4.4% | 4.464 | 0.521 | 1.807 | 15.641* | 25 |
| SMA 35 ETH | 63.0% | -44.6% | 1.411 | 0.638 | 1.290 | 3.511 | 97 |
| Buy&Hold ETH | 12.9% | -94.0% | 0.137 | 0.572 | 0.786 | — | — |
| EW Basket | 43.4% | -89.2% | 0.486 | 0.859 | 1.147 | — | — |

*BTC SMA profit factor unreliable — only 25 trades

---

## Week 6 Priority Tasks

### PRIORITY 1: Deploy RSI bot to EC2
Build `rsi_production_bot.py` — separate script from ADX bot, own state file, own cron job (00:06 UTC), same Telegram bot. Capital $500, position size 15%, 15% stop-loss, 120MA regime filter.

### PRIORITY 2: Complete the 16-stage optimisation plan

**Stage 1 — ETH ADX trailing stop optimisation:**
- 1a: Percentage trailing stop grid search (trail_pct 3-15%, step 1%, combined with ADX threshold 15-22 and period 8-14)
- 1b: ATR trailing stop grid search (ATR period 7-21, multiplier 1.5-4.0, combined with ADX params)
- 1c: Stability analysis — best trailing stop type from 1a vs 1b
- 1d: Compare: trailing stop vs fixed stop on all metrics (Calmar, Sharpe, Sortino, PF, win rate)

**Stage 2 — BTC SMA 125 complete validation:**
- 2a: Add percentage trailing stop — joint optimisation with SMA period (80-170, step 5) × stop (5-20%, step 2.5%)
- 2b: Add ATR trailing stop — same joint optimisation
- 2c: Stability analysis — best BTC SMA + trailing stop combination
- 2d: Walk-forward validation — 3 rolling windows (same methodology as ETH RSI)
- 2e: Cross-asset check — BTC-optimised params on ETH

**Stage 3 — ETH ADX leverage optimisation:**
- 3a: Leverage grid 1.0x-5.0x, 0.1x steps (41 levels). 100% own capital. Trailing stop from Stage 1. All metrics including Sortino. Safety buffer: min margin ratio ≥25%.
- 3b: Leverage stability analysis
- 3c: Interest rate sensitivity (0.010%, 0.015%, 0.020%/day)

**Stage 4 — BTC SMA leverage optimisation:**
- 4a: Same as 3a but for BTC SMA with trailing stop from Stage 2
- 4b: Leverage stability
- 4c: Interest rate sensitivity — note BTC SMA holds much longer, interest will be more material

**Stage 5 — Final consolidated comparison:**
One table showing all metrics for all strategies at recommended leverage. Full visualisation: price charts with entry/exit markers colour-coded by exit type, equity curves, drawdown comparison.

### PRIORITY 3: Update live bot with validated trailing stop
Once Stage 1 confirms trailing stop improves performance, update `day5_production_bot.py` to use trailing stop instead of fixed stop. Update bot_state.json schema to track peak_price_since_entry.

---

## Important Technical Context

### File locations
```
data/trade_log_with_stoploss.csv          # ETH ADX 108 trades — use for Stage 1 analysis
data/trade_log_rsi_final.csv              # RSI 31 trades
data/trade_log_bollinger_final.csv        # BB 26 trades
data/btc_adx_optimisation_results.csv    # BTC ADX grid search results
data/rsi_optimisation_results.csv        # RSI grid search results
data/bollinger_optimisation_results.csv  # BB grid search results
data/joint_optimisation_results_refined.csv  # ETH ADX joint optimisation
Week_5_Notebooks/                         # All Week 5 scripts
```

### Key confirmed parameters
- **ETH ADX live:** ADX threshold=20, period=10, stop=5% (fixed, to be replaced with trailing)
- **ETH RSI pending:** period=14, oversold<43, exit>48, stop=15%, 120MA
- **BTC SMA pending validation:** SMA period=125, no hard stop yet
- **BTC ADX independently optimised:** threshold=19, period=14, stop=3%

### Margin trading confirmed facts
- UK retail: spot margin only (FCA bans crypto derivatives since Jan 2021)
- Interest: ~0.015%/day on borrowed amount during position only
- Auto-Repay: loan repaid automatically from trade proceeds on close
- Liquidation: equity/position < 5% maintenance margin (check daily LOW prices)
- Safety buffer: minimum margin ratio must stay above 25% historically
- Stop slippage in backtest: 2% below intended stop price
- Liquidation slippage: 3% below liquidation price

### Capital plan (post Week 6)
| Strategy | Capital | Leverage | Notes |
|----------|---------|----------|-------|
| ETH ADX (leveraged) | $1,500 | TBD Week 6 | Replaces $1,000 unleveraged |
| ETH RSI | $500 | 1.0x | Unleveraged until validated |
| BTC SMA (leveraged) | $1,000 | TBD Week 6 | After full Stage 2 validation |
| Total | $3,000 | | |

---

## Open Risk Register Items (High Priority)

| ID | Description | Target |
|----|-------------|--------|
| A008 | RSI deployed with only 31 backtest trades | Review after 20 live trades |
| A010 | Daily loss limit not calibrated — may hurt live returns | Week 6 |
| A011 | ETH ADX uses fixed stop, not trailing stop | Week 6 Stage 1 |
| A012 | BTC SMA 125 not fully validated | Week 6 Stage 2 |
| A013 | Margin leverage not yet optimised | Week 6 Stages 3-4 |
| A014 | RiskManager guardrails not calibrated | Week 6 after Stage 1 |

---

## Pre-deployment Checklist (updated for leveraged strategies)

Before deploying any leveraged position, ALL of the following must be confirmed:

1. Daily backtest validated (Calmar >= 1.5, Sortino >= 0.8)
2. Walk-forward validation passed (profitable in all windows)
3. Stability analysis passed (all parameters >= 50% stability)
4. Trailing stop validated (outperforms fixed stop)
5. Leverage level confirmed (safety buffer maintained, optimal Calmar)
6. Production bot running on EC2 with correct parameters
7. Cron job confirmed
8. Trailing stop logic tested on testnet
9. Isolated margin wallet funded
10. AUTO_REPAY enabled on Binance margin account
11. Leverage level set correctly on trading pair in Binance
12. Liquidation price calculated and documented
13. Margin ratio monitoring added to bot
14. Current interest rate confirmed on Binance Margin Data page
15. Daily loss limit reviewed and removed/calibrated
16. Capital allocation confirmed — no unintended correlated overlap
17. Telegram alerts working
18. High priority Risk Register items resolved
19. Mentally prepared for leveraged drawdowns

---

## Study Backlog Items for Week 6

High priority items to read before/during Week 6:
- **SB015:** ATR — required for Stage 1b (ATR trailing stop)
- **SB016:** Trailing stops — required for all of Stage 1 and 2
- **SB017:** Binance Isolated Margin — required before any leveraged deployment
- **SB018:** Calmar Ratio — primary metric throughout Week 6

---

*End of Week 6 Thread Starter*
*Prepared: Week 5 final session*
*Next session: Use Claude Code for all 16 optimisation stages*
