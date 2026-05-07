# Week 7 Thread Starter
## DeFi Quant Engineer Curriculum
**Student:** Greg (Gmac)
**Week:** 7 of 24
**Start date:** Monday 11 May 2026
**Calendar event:** Created in Google Calendar
**Status:** Week 6 complete (with carry-over items)

---

## How to Use This File

Read this file at the start of every Week 7
chat session before doing anything else.
All process standards are in the project
documents attached to the Claude Project.
This file contains only what is specific
to Week 7.

---

## Live Positions (as of 2026-05-07)

### ETH ADX 19/9 — LIVE ✅
- Capital: $1,000 allocated, $994.78 deployed
- Position: LONG 0.419 ETH
- Blended entry: $2,368.52 (2026-05-05)
- Current stop: $2,250.09 (fixed — trailing
  stop code deployed but stop not yet moved
  because price hasn't exceeded peak of $2,399.50)
- Stop type: STOP_LOSS market execution ✅
- Trailing stop: 8% pct, bot-managed 4× daily
  (00:05, 06:05, 12:05, 18:05 UTC)
- ADX signal: LONG (ADX=31.0 as of 2026-05-07)
- Kelly: 12.41% half-Kelly, correctly
  implemented as risk fraction
- Leverage: 1.0× unleveraged currently
- Validated leverage: 1.9× (Week 7 priority)
- Bot file: Week_4_Notebooks/day5_production_bot.py
- EC2: 3.104.101.30 (Elastic IP — permanent)
- Cron: 00:05 (signal), 06:05, 12:05, 18:05
  (stop update)

### ETH RSI 14 — VALIDATION $150 ⚠️
- Capital: $150 allocated (validation only —
  NOT $500, intentional)
- Position: FLAT — awaiting first signal
- Stop type: 15% fixed STOP_LOSS market order
- Monte Carlo result: negative Kelly at
  expected 70% live win rate
- Breakeven win rate: 72.1%
- Scale-up trigger: 20 live trades + WR ≥80%
- Stop trigger: WR <72% after 20 trades
- Bot file: Week_4_Notebooks/rsi_production_bot.py
- Cron: 00:06 UTC daily
- Status: Bot built and deployed to EC2
  (confirm running at start of Week 7)

---

## Portfolio State (as of 2026-05-07)

Total portfolio value: ~$1,985
- ETH ADX: $985 deployed (LONG), cap $1,000
- ETH RSI: $150 cash (FLAT), cap $150
- BTC SMA: $0 (shelved)
- Unallocated: $850 USDT (awaiting BTC
  strategy validation)

Portfolio manager: portfolio_manager.py ✅
Weekly rebalance: Monday 01:00 UTC cron ✅
State file: data/portfolio_state.json ✅

---

## Key Decisions Made in Week 6

These are final decisions — do not relitigate
without strong new evidence:

1. ETH ADX parameters: ADX 19/9 + 8% pct
   trailing stop (not ATR, not 20/10)
2. Stop order type: STOP_LOSS market execution
   (not STOP_LOSS_LIMIT — guaranteed fill)
3. ETH ADX leverage: 1.9× validated and
   confirmed — Week 7 deployment target
4. ETH RSI: $150 validation only — negative
   Kelly at realistic 70% live win rate
5. BTC SMA: SHELVED — 30 trades, 76%
   return from 2021, marginal stability
6. Kelly sizing: Position = (f* × capital) /
   stop_pct (risk fraction, NOT deployment
   fraction — critical fix made Week 6)
7. Trailing stop: bot-managed 4× daily
   (Binance Spot has no native trailing stop)
8. Portfolio architecture: reserved_capital
   per strategy, never reads live USDT balance
   for sizing — compounding via weekly rebalance

---

## Critical Bugs Fixed in Week 6

These were live on the bot and have been fixed.
Do not reintroduce:

1. STOP_LOSS_LIMIT → STOP_LOSS (market
   execution). Bot was failing silently for
   23 days — API permission + order type wrong.
2. Kelly sizing: was deploying f* × capital
   ($124) not (f* × capital) / stop_pct ($1,000)
3. LOT_SIZE rounding: stop quantity must be
   floored to 3dp to avoid -2010 insufficient
   balance errors
4. Stop order verification: verify_stop_order()
   now runs at start of every bot execution —
   catches silent stop cancellation by Binance
5. Entry date bug: entry_date stored at exit
   not entry (caused equity curve distortion)
6. Per-trade Sortino inflation: all Sortino
   calculations now use daily equity curve method

---

## Week 6 Carry-Over (complete before new work)

These were planned for Week 6 but not completed:

URGENT (affects live trading):
1. ✅ Trailing stop deployed (4× daily cron)
2. ⬜ ETH ADX leveraged bot (1.9×, $1,500
   capital) — leverage validated but bot
   not yet built. Requires margin account
   setup on Binance + borrow/repay logic.
   Expected return uplift: $670 → $1,909/yr.

ANALYTICAL:
3. ⬜ Stage 5 final comparison — master equity
   curves and metrics table. Charts needed
   for deployment documents.
   Run: stage5_final_comparison.py

DOCUMENTATION:
4. ⬜ Deployment document: ETH ADX (HTML
   with embedded charts, metrics, sign-off)
5. ⬜ Deployment document: ETH RSI (HTML
   with embedded charts, metrics, sign-off)
6. ⬜ GitHub close-out commit for Week 6

---

## Week 7 New Work (after carry-over complete)

### Priority 1 — ETH ADX Leveraged Bot
Build day5_leveraged_bot.py with:
- Binance Isolated Margin (not cross margin)
- Borrow logic: borrow 0.9× capital in ETH
  at entry (for 1.9× total position)
- Repay logic: full repay at exit
- Interest tracking and daily interest charge
- Same trailing stop logic as unleveraged bot
- Same stop verification, Telegram alerts,
  health checks
- Capital: $1,500 from portfolio_state.json
- Kelly position: ($186 risk) / 0.08 = $2,325,
  deploy full $1,500 own + $750 borrowed = $2,250
- Leverage: 1.9× (validated, safe buffer 34.4%)
Independent review: required before deployment.
Capital impact: move $1,000 from unleveraged
ADX allocation to $1,500 leveraged ADX.

### Priority 2 — BTC ADX 19/14 Full Validation
This is the natural Week 7 BTC strategy.
103 trades — strongest sample of all strategies.
Post-2022 concern (+5.4%/yr) must be explained.
Full pipeline required:
- Stage A: trailing stop optimisation
- Stage B: corrected Sortino, walk-forward
- Stage C: Monte Carlo (103 trades — meaningful)
- Stage D: leverage optimisation
- Stage E: independent review
- Stage F: deployment decision
If validated: deploy to BTC capital allocation
($500 initially, $1,000 if leveraged version)

### Priority 3 — Momentum Strategies
Original curriculum: MACD, ROC, CMO, breakout.
Run research brief BEFORE starting — find best
momentum indicators with empirical support for
crypto specifically (not just most famous ones).
Research brief: WEEK_7_RESEARCH_BRIEF.md
Do this at END of week (not start) per
agreement with Greg.

---

## Open Risk Register Items (HIGH priority only)

### ETH ADX (RISK_REGISTER_ETH_ADX.md)
- A016: Margin vulnerability at worst
  historical MR — trailing stop is primary
  protection. Margin alert at 40%.
  Target: margin alert in leveraged bot.

### ETH RSI (RISK_REGISTER_ETH_RSI.md)
- RR-RSI-004: Sample size 31 trades —
  insufficient for reliable inference.
  Target: monitor 20 live trades.
- RR-RSI-005: 120MA regime filter data-mining.
  Target: accept risk, monitor live.
- RR-RSI-006: Stability analysis not run.
  Target: complete during Week 7.

---

## Methodology Standards (key reminders)

These are in METHODOLOGY_STANDARDS.md in full.
Critical items:
- Sortino: ALWAYS daily equity curve method
- Kelly: ALWAYS risk fraction (f* × capital) / stop_pct
- Stop orders: ALWAYS STOP_LOSS (market),
  NEVER STOP_LOSS_LIMIT
- Stop verification: ALWAYS verify_stop_order()
  at start of every bot run while LONG
- Trailing stop: bot-managed daily (Binance
  Spot has no native trailing stop)
- Monte Carlo: mandatory for n<100 trades
- Independent review: mandatory before
  any live deployment

---

## Capital Plan (Week 7 target state)

| Strategy | Capital | Leverage | Status |
|----------|---------|----------|--------|
| ETH ADX (leveraged) | $1,500 | 1.9× | Week 7 build |
| ETH RSI (validation) | $150 | 1.0× | Live |
| BTC ADX (if validated) | $500 | 1.0× initially | Conditional |
| Unallocated | $850 | — | Awaiting BTC |
| Total | $3,000 | | |

---

## Performance-Weighted Allocation (deferred)
Deferred to Week 9. Requires ≥20 live trades
per strategy. See SI007 in Strategy Ideas Log.

---

## Week 7 Research Brief
To be created at END of Week 7 before closing.
Topic: Momentum strategies for crypto.
Focus: MACD, ROC, CMO, breakout — but research
first to find best indicators with empirical
support rather than defaulting to MACD.
File: WEEK_7_RESEARCH_BRIEF.md

---

## EC2 Infrastructure
- IP: 3.104.101.30 (Elastic IP — PERMANENT)
- SSH key: /Users/Greg/.ssh/trading-bot-key.pem
- Bot files: /home/ubuntu/Python_Local_Folder/
  Python_Quant_Researcher/Week_4_Notebooks/
- Logs: /home/ubuntu/logs/
  adx_strategy.log (ADX bot)
  rsi_strategy.log (RSI bot)
- Crons:
  00:05 UTC — ADX signal run
  06:05, 12:05, 18:05 UTC — ADX stop update
  00:06 UTC — RSI signal run
  01:00 UTC Monday — portfolio rebalance

---

*Week 7 Thread Starter v2.0*
*Prepared: 2026-05-07 (end of Week 6)*
*Replaces v1.0 prepared 2026-05-02 (outdated)*
*Next update: end of Week 7*
