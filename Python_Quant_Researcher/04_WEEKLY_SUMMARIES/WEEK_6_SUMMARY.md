# Week 6 Summary — Permanent Historical Record
## DeFi Quant Engineer Curriculum
**Student:** Greg (Gmac)
**Week:** 6 of 24
**Dates:** 28 April – 7 May 2026

---

## 1. Planned vs Actual

| Planned | Outcome |
|---|---|
| Stage 1: Trailing stop optimisation (ATR vs pct) | ✅ Complete — pct 8% and ATR 9/2.5x both validated |
| Stage 2: Corrected Sortino, walk-forward (ETH ADX) | ✅ Complete |
| Stage 3: Monte Carlo, stress test (ETH ADX) | ✅ Complete |
| Stage 4: Leverage optimisation (ETH ADX) | ✅ Complete — 1.9× validated |
| Stage 5: Final comparison — master equity curves | ⬜ NOT DONE — script not run, HTML not generated |
| Deployment documents — ETH ADX and ETH RSI (HTML) | ⬜ NOT DONE — carry-over to Week 7 |
| BTC SMA validation pipeline | ✅ Complete — 5 stages, NO-GO decision documented |
| ETH RSI validation and Monte Carlo | ✅ Complete |
| Portfolio manager and position tracking | ✅ Complete — portfolio_manager.py built and deployed |
| ETH ADX production bot — fix stop order type | ✅ Fixed — STOP_LOSS_LIMIT → STOP_LOSS |
| ETH ADX production bot — trailing stop (bot-managed) | ✅ Deployed — 4× daily cron |
| ETH ADX production bot — Kelly sizing correction | ✅ Fixed — position sizing was 20× too small |
| ETH ADX production bot — stop order verification | ✅ Deployed — verify_stop_order() |
| ETH RSI production bot — build and deploy | ✅ Complete — deployed to EC2 |
| Weekly portfolio rebalance cron | ✅ Complete — Monday 01:00 UTC |
| ETH ADX leveraged bot (1.9×) | ⬜ NOT DONE — carry-over to Week 7 |
| GitHub close-out commit | ⬜ Partial — most work committed, final commit pending |

**Summary:** Core analytical work complete. Infrastructure work complete. Stage 5 comparison, deployment documents, and leveraged bot deferred.

---

## 2. Key Decisions Made

### Decision 1: ETH ADX parameters — ADX 19/9 + 8% percentage trailing stop
**Rationale:** Stage 1 grid search across 36 combinations confirmed ADX 19/9 + 8% pct trail as best by composite score (Calmar + Sortino + Annual% + MaxDD). ATR 9/2.5× was marginally better on Calmar (2.642 vs 2.559) but the pct trail is simpler to implement and verify in live code, and the difference was within noise. Final choice: pct trail 8% as live parameter. ATR noted as close second.

### Decision 2: Stop order type — STOP_LOSS (market execution)
**Rationale:** Bot had been using STOP_LOSS_LIMIT for 23 days without placing a single stop. API permission error + wrong order type. STOP_LOSS (market) guarantees fill regardless of price gap. STOP_LOSS_LIMIT does not — if price gaps past the limit, the order remains open and position is fully exposed. For a daily candle strategy on 24/7 crypto, guaranteed execution is non-negotiable.

### Decision 3: ETH ADX leverage — 1.9× validated
**Rationale:** Stage 4 leverage grid search. Kelly-optimal leverage = f*/stop_pct = 0.1241/0.08 = 1.55×. Safety constraint: worst historical daily low drop must not liquidate. At 1.9×, safety buffer = 34.4% above worst historical drawdown scenario. 1.9× sits between Kelly-optimal (1.55×) and safety maximum (2.0×) — grows faster than Kelly-optimal while maintaining a meaningful buffer. Interest cost nearly negligible (~$30 over 108 trades at 8.3 years). Decision: deploy at 1.9×.

### Decision 4: ETH RSI — $150 validation only
**Rationale:** Monte Carlo at realistic 70% live win rate (vs 93.5% backtest) showed negative Kelly expectation. Breakeven win rate = 72.1%. 31-trade backtest sample is insufficient to confidently project 70%+ live performance. $150 limits loss to an affordable learning cost while accumulating 20 live trades for decision. Scale-up only after WR ≥ 80% over 20 live trades.

### Decision 5: BTC SMA — SHELVED
**Rationale:** 5-stage pipeline complete. Hard failure: MARGINAL stability (50.5%), 76% of total return from 2021 alone (ex-2021 annual return ~29%), cross-asset validation failed on ETH (Calmar 0.291), parameter boundary issue at 25% trail. Not permanently discarded — the edge may be real, but evidence quality insufficient for capital deployment. BTC ADX 19/14 identified as the stronger BTC candidate for Week 7.

### Decision 6: Kelly sizing — risk fraction (not deployment fraction)
**Rationale:** Previous implementation used Kelly as deployment fraction (deployed f* × capital = $124). Correct: Kelly is the fraction of capital you can afford to RISK (lose) per trade. Correct position size = (f* × capital) / stop_pct. At 8% trail: ($124.10) / 0.08 = $1,551, capped at $994.78. Previous implementation was 20× too small — a major systematic undersizing bug present since Week 4.

### Decision 7: Portfolio architecture — reserved_capital per strategy
**Rationale:** Live USDT balance fluctuates as strategies open/close positions. Using live balance for sizing would cause one strategy's entry to shrink another strategy's sizing. Solution: each strategy has a reserved_capital allocation, stable between weekly rebalances, used as the stable capital base for Kelly sizing. Weekly rebalance (Monday 01:00 UTC) recalculates reserved_capital based on total portfolio value.

### Decision 8: Trailing stop — bot-managed 4× daily
**Rationale:** Binance Spot has no native trailing stop API. The alternative (STOP_LOSS_LIMIT updated frequently) risks gaps between cancellation and replacement. Bot-managed approach: cron runs at 00:05, 06:05, 12:05, 18:05 UTC. Each run cancels the existing stop and places a new one at max(current_stop, peak × (1 - TRAIL_PCT)). 4× daily ensures the stop is updated within 6 hours of any new price peak.

---

## 3. Critical Bugs Discovered and Fixed

### Bug 1: STOP_LOSS_LIMIT → STOP_LOSS
**Severity:** Critical — live position had no stop protection  
**Duration:** 23 days undetected (Week 5 deployment → Week 6 discovery)  
**Root cause:** Binance Spot requires separate permission for STOP_LOSS_LIMIT orders. Bot was calling the API correctly but the wrong order type meant the permission check failed silently. `create_test_order()` passed (tests market orders) but real stop order calls returned -2010.  
**Fix:** Changed `type="STOP_LOSS_LIMIT"` → `type="STOP_LOSS"` throughout bot. STOP_LOSS executes as a market order on trigger — guaranteed fill. STOP_LOSS_LIMIT banned from all future bots.  
**Process change:** Added stop order type requirement to LIVE_TRADING_CHECKLIST.md §3.

### Bug 2: Kelly sizing — 20× undersizing
**Severity:** Critical — systematic underexposure since Week 4  
**Duration:** Full Week 4 and Week 5 deployment period  
**Root cause:** Kelly fraction interpreted as deployment fraction (deploy 12.41% of capital = $124). Kelly is actually a risk fraction: how much of capital you can afford to lose. Position size = risk_amount / stop_pct, not risk_amount directly.  
**Fix:** Updated RiskManager.calculate_position_size() to use (f* × capital) / stop_pct. At 8% trail with $1,000 capital: position = $1,551, capped at $994.78. Actual risk preserved at 12.41% of capital.  
**Process change:** Added Kelly correct implementation to Learning Log and Methodology Standards.

### Bug 3: Silent stop cancellation — no verification
**Severity:** Critical — live position could silently lose stop protection  
**Duration:** Unknown — Binance can cancel STOP_LOSS orders without notification  
**Root cause:** Bot placed stop at entry, assumed it remained active. Binance has documented cases of stop orders being cancelled (maintenance events, API issues). No code checked the stop was still active on subsequent runs.  
**Fix:** Added `verify_stop_order()` to day5_production_bot.py. Runs at start of every bot execution while LONG. Queries Binance for the stop order ID in state file. Cases: NEW (pass), FILLED (update state to FLAT, send Telegram — stop was hit while bot was idle), CANCELLED/other (re-place stop immediately, alert).  
**Process change:** Added stop order verification requirement to LIVE_TRADING_CHECKLIST.md §3.

### Bug 4: LOT_SIZE rounding on stop orders
**Severity:** Major — stop orders rejected with -2010 insufficient balance  
**Root cause:** Stop order quantity not floored to 3 decimal places. Binance LOT_SIZE filter for ETHUSDT requires qty in 0.001 ETH increments. A stop placed for 0.4199 ETH was rejected; 0.419 ETH was accepted.  
**Fix:** `math.floor(qty * 1000) / 1000` applied to all stop order quantities.

### Bug 5: Entry date stored at exit, not entry
**Severity:** Medium — equity curve distortion in performance analysis  
**Root cause:** `entry_date` was being written to state file at exit (when other trade data was being cleared) rather than at the point of trade entry.  
**Fix:** `entry_date = datetime.now().strftime('%Y-%m-%d')` moved to the entry block in the bot.

### Bug 6: Per-trade Sortino inflation
**Severity:** Major — Sortino inflated 3-4× in all analysis before Week 6  
**Root cause:** Sortino calculated on per-trade returns, treating each trade as 1-day. Correct method: build daily equity curve, calculate daily returns, compute downside deviation from days with negative returns only, annualise with sqrt(365).  
**Fix:** All Sortino calculations updated to daily equity curve method. ADX Sortino dropped from ~3.5 to 1.870 (correct value).  
**Process change:** Methodology Standards updated. LIVE_TRADING_CHECKLIST.md §1 updated.

---

## 4. Strategies Validated, Deployed, or Shelved

### ETH ADX 19/9 — DEPLOYED (LIVE) ✅
- Parameters: ADX period 19, DI period 9, 8% percentage trailing stop
- Performance: Calmar 2.559, Sortino 1.870, MaxDD −31.3%, Annual 24.4%
- Kelly: 12.41% half-Kelly → $1,551 position (capped at $994.78 unleveraged)
- Leverage validated: 1.9× (Kelly-optimal 1.55×, safety maximum 2.0×)
- Status: LIVE, $994.78 deployed, trailing stop bot-managed 4× daily
- Outstanding: leveraged bot (1.9×) not yet built — Week 7 priority

### ETH RSI 14 — DEPLOYED (VALIDATION) ⚠️
- Parameters: RSI 14, entry <43, exit >48, stop 15% fixed, 120-day SMA regime filter
- Performance (backtest): Calmar 1.054, Sortino 1.205, win rate 93.5% (31 trades)
- Monte Carlo at 70% live win rate: negative Kelly expectation
- Breakeven win rate: 72.1%
- Status: LIVE at $150 validation capital. FLAT (no signal yet). Scale-up after 20 trades + WR ≥ 80%
- Bot: deployed to EC2, cron 00:06 UTC daily

### BTC SMA 125 — SHELVED ❌
- 5-stage validation completed
- Hard failures: MARGINAL stability, 76% return concentration in 2021, cross-asset failure on ETH
- Annual return ex-2021: ~29% (not +5.4%/yr as initially feared — still positive but marginal evidence)
- Decision: NO-GO. Capital ($850) held in unallocated until BTC ADX 19/14 validated
- Not permanently discarded — may revisit with more live data

### BTC ADX 19/14 — IDENTIFIED (not yet started)
- 103 trades — strongest sample of all strategies tested
- Week 7 full pipeline: trailing stop → corrected Sortino + WFV → Monte Carlo → leverage → review → decision
- Post-2022 performance concern (+5.4%/yr) must be explained before deployment

---

## 5. Documents Created or Significantly Updated

### Created (new files)
| File | Purpose |
|---|---|
| `portfolio_manager.py` | Shared portfolio state management across all bots |
| `data/portfolio_state.json` | Live portfolio state (reserved_capital, positions) |
| `portfolio_rebalance.py` | Standalone weekly rebalance script (Monday 01:00 UTC cron) |
| `Week_4_Notebooks/rsi_production_bot.py` | ETH RSI production bot — full deployment |
| `RISK_REGISTER_ETH_RSI.md` | RSI strategy risk register (6 items: RR-RSI-001 to 006) |
| `STRATEGY_DEPLOYMENT_TEMPLATE.md` | Reusable 8-section template for all future deployment decisions |
| `WEEK_7_THREAD_STARTER.md` (v2.0) | Complete rewrite with current live positions and Week 7 priorities |
| `WEEK_6_SUMMARY.md` | This file |
| `Deployment_Documents/Week_6/` | Folder containing 10 HTML analytical output files |

### Significantly Updated
| File | Changes |
|---|---|
| `Week_4_Notebooks/day5_production_bot.py` | Portfolio manager integration, verify_stop_order(), STOP_LOSS fix, trailing stop 4× daily, Kelly sizing fix |
| `LIVE_TRADING_CHECKLIST.md` | v1.0 → v2.0: §0 Pre-Deployment Review, stop order type, stop verification, capital confidence score |
| `STRATEGY_RESEARCH_PIPELINE.md` | v1.0 → v1.5: Phase 2 max loss + payoff profile checks, Phase 3 Monte Carlo, Phase 6 confidence scoring |
| `LEARNING_LOG.md` | Week 6 concepts: trailing stop confirmed, composite score, per-trade vs daily MtM, stability thresholds, boundary overfitting, return concentration, portfolio allocation philosophy, Monte Carlo, Kelly correct implementation |
| `STRATEGY_IDEAS_LOG.md` | SI007 (performance-weighted allocation, Week 9+), SI008 (stop order verification pattern) |
| `RISK_REGISTER_ETH_ADX.md` | A016 added: margin vulnerability at worst historical MR |
| `data/portfolio_state.json` | Updated: eth_rsi $150, btc_sma $0 |
| `METHODOLOGY_STANDARDS.md` | Kelly correct implementation, Sortino daily equity curve method confirmed |

---

## 6. Live Trading Status at Week End (2026-05-07)

### ETH ADX — LONG
- Entry: 0.419 ETH @ $2,368.52 (2026-05-05)
- Capital: $994.78 deployed from $1,000 reserved
- Stop: $2,250.09 (8% trailing, bot-managed)
- Peak price since entry: $2,399.50 (trailing stop not yet moved above initial)
- ADX signal: LONG (ADX=31.0)
- Cron: 00:05 (signal), 06:05, 12:05, 18:05 UTC (stop update)
- Bot verified healthy (Telegram health checks running)

### ETH RSI — FLAT
- Capital: $150 reserved, $150 cash
- No entry signal since deployment
- Cron: 00:06 UTC daily
- Bot deployed and verified

### BTC SMA — SHELVED
- Capital: $0 reserved
- No bot deployed

### Portfolio totals
| | |
|---|---|
| ETH ADX deployed | $985 (~current value) |
| ETH RSI cash | $150 |
| Unallocated | $850 USDT |
| Total | ~$1,985 |

---

## 7. Lessons Learned — Top 10

These are the highest-signal lessons from Week 6. Ordered by significance to live trading safety and analytical quality.

**Lesson 1 — Silent failures are the most dangerous failures**  
The stop order was broken for 23 days without any alert, log entry, or visible error. The bot was running normally, health checks were passing, and nothing indicated a problem — yet the position had zero downside protection. Conclusion: every critical safety system (stop placement, stop verification, API permissions) must produce a positive confirmation that it worked, not just absence of error.

**Lesson 2 — Kelly is a risk fraction, not a deployment fraction**  
This was the largest practical error of the curriculum: deploying 12.41% of capital as position size instead of deploying (12.41% × capital) / stop_pct as position size. The difference: $124 deployed vs $1,551 deployed (20× undersizing). The correct mental model: Kelly tells you the maximum you can AFFORD TO LOSE per trade. Position size = risk_budget / stop_distance.

**Lesson 3 — Per-trade returns inflate every metric by 3-5×**  
Sharpe, Sortino, and annual return calculated on per-trade returns are all systematically wrong for strategies with idle periods. A strategy flat for 9 months/year and calculating Sortino on 6 trades per year is not comparable to a strategy calculated on 252 daily returns. Always use daily equity curve. The correction reduced apparent Sortino from ~3.5 to 1.870.

**Lesson 4 — Backtest returns can be dominated by one year**  
BTC SMA reported 48.9%/yr over 2018-2026 but 76% of that came from 2021 alone. Ex-2021 annual return: ~29%. An investor evaluating the headline figure will systematically overestimate future returns. Always report both full-period and ex-outlier metrics. Set forward expectations on the ex-outlier figure.

**Lesson 5 — Stability analysis is a better measure of edge quality than peak performance**  
A strategy that achieves best-on-grid performance at a single narrow parameter value (FRAGILE) is almost certainly overfit. A strategy that achieves good-but-not-best performance across a wide plateau (STABLE) is far more likely to work in live trading. STABLE/MARGINAL/FRAGILE classification must be completed before any deployment decision.

**Lesson 6 — Walk-forward with fixed parameters is not a dual test**  
When parameters are not re-optimised per training window, expanding and rolling walk-forward produce identical test-period results. Presenting both as independent validation is a documentation error, not a genuine test of robustness. True walk-forward re-optimisation is the correct standard but impractical for low-frequency strategies. Document this limitation explicitly.

**Lesson 7 — Monte Carlo is mandatory for low-sample strategies**  
RSI had a 93.5% win rate on 31 trades. Monte Carlo at 70% expected live win rate showed negative Kelly expectation. The 31-trade backtest win rate is almost certainly overstated due to regime selection and small sample noise. Monte Carlo correctly quantifies the distribution of outcomes at reduced win rates and reveals strategies that look strong on headline but are fragile at realistic live performance.

**Lesson 8 — Portfolio architecture must isolate strategy capital**  
Using a shared live USDT balance for position sizing causes inter-strategy interference: one bot's entry reduces another bot's available capital. The solution (reserved_capital per strategy, weekly rebalance) means each strategy sizes from a stable, pre-allocated capital base that is immune to other strategies' positions. This is the correct architecture for any multi-strategy portfolio.

**Lesson 9 — Parameter grid boundaries must be checked before accepting a result**  
The BTC SMA trailing stop search showed continuously improving performance up to the boundary (27.5%) of the tested range. This means the true optimum likely lies outside the grid — the "best" result is an artefact of grid extent, not a genuine structural peak. Fix: always extend the range until performance clearly peaks and plateaus before accepting any grid result.

**Lesson 10 — NO-GO decisions are risk management successes, not failures**  
BTC SMA passed enough tests to be tempting but failed enough to justify rejection. Documenting a clear NO-GO with specific failure criteria and fallback plan (BTC ADX 19/14) is the correct outcome of a disciplined validation pipeline. The alternative — deploying capital to a MARGINAL strategy because it "mostly worked" — is exactly the failure mode the pipeline is designed to prevent.

---

## 8. What Was Deferred and Why

### Deferred 1: ETH ADX leveraged bot (1.9×)
**What:** Build day5_leveraged_bot.py using Binance Isolated Margin  
**Why deferred:** Leverage validated analytically (Stage 4). But building the margin bot requires Binance Isolated Margin account setup, borrow/repay API logic (MARGIN_BUY/AUTO_REPAY side effects), margin ratio monitoring, and full independent review before deployment. This is a substantial build. Week 6 ran out of time after prioritising RSI bot deployment and bug fixes.  
**Week 7 priority:** #1 — do before new strategy work

### Deferred 2: Stage 5 final comparison
**What:** Run stage5_final_comparison.py to generate master equity curves and metrics table across all strategies  
**Why deferred:** stage5_final_comparison.py was never written. Analytical work was prioritised over visualisation once the deployment decisions were made.  
**Week 7 priority:** #2 (analytical carry-over) — needed for deployment documents

### Deferred 3: Deployment documents — ETH ADX and ETH RSI
**What:** HTML deployment documents with embedded interactive charts, full metrics tables, risk register summary, and sign-off for both deployed strategies  
**Why deferred:** Stage 5 comparison not complete (dependency). Also deprioritised in favour of live infrastructure work.  
**Week 7 priority:** #3 (documentation carry-over)

### Deferred 4: RR-RSI-006 — Stability analysis for ETH RSI
**What:** STABLE/MARGINAL/FRAGILE classification for RSI parameters (14, 43, 48, 15%, 120MA)  
**Why deferred:** RSI validation focused on Monte Carlo (the more urgent risk given small sample size). Stability analysis was not run.  
**Week 7 priority:** Complete during Week 7 when building RSI deployment document

### Deferred 5: Performance-weighted portfolio allocation
**What:** Sortino-weighted capital allocation formula across live strategies  
**Why deferred:** Requires minimum 20 live trades per strategy. ETH ADX has 0 live completed trades (position still open). ETH RSI has 0 live trades.  
**Timeline:** Week 9 earliest. Logged as SI007 in Strategy Ideas Log.

---

*Week 6 Summary v1.0*  
*Prepared: 2026-05-07 (end of Week 6)*  
*This is a permanent historical record — do not edit after creation*
