# Strategy Risk Register — ETH ADX Trailing Stop

**Purpose:** Tracks every known risk for the ETH ADX trend-following strategy. Each item has an ID, severity, status, mitigation, and update log. HIGH items must be resolved before capital increases. MAJOR items must be documented and mitigated before deployment.
**Who reads it:** Greg before any capital change. Claude Code when building or modifying the ETH ADX bot. Independent reviewer before leveraged deployment.
**When updated:** Whenever a new risk is identified, or an existing item's status changes.
**Related documents:** RISK_REGISTER_ETH_RSI.md, RISK_REGISTER_BTC_SMA.md, LIVE_TRADING_CHECKLIST.md, ETH_ADX_Deployment_Card_v1.html.

---

**Strategy:** ETH ADX Trend-Following with ATR Trailing Stop
**Asset / Exchange:** ETHUSDT / Binance Spot (unleveraged → leveraged planned)
**Version:** v2.0 (trailing stop)
**Date created:** 2026-03-20
**Last updated:** 2026-06-22
**Updated by:** Greg + Claude

---

## How to Use This Register

Review before each deployment and before any capital increase.
All High priority open items must be resolved before deployment or capital increase.
Medium priority items must be resolved or formally accepted with written rationale.

| Field | Meaning |
|---|---|
| ID | Unique reference |
| Category | Strategy / Execution / Infrastructure / Data / Live Performance |
| Status | Open / In Progress / Resolved |
| Priority | High / Medium / Low |
| Target | When this item will be addressed |

---

## Open Items

---

### A003 — Slippage modelled as flat cost, not variable

**Category:** Execution

**Status:** Open

**Priority:** Medium

**Raised:** Week 4 Day 2

**Description:**
Transaction costs modelled at flat 0.15% round-trip. This covers fees and average spread but does not model variable slippage on stop-loss exits during low-liquidity periods (e.g. thin market hours on weekends). Real stop-loss fills may be 0.1–0.5% worse than the stop price in adverse conditions.

**Impact:**
Immaterial at current position sizes (~$124 per trade — extra slippage of ~$0.62 maximum). Becomes meaningful as capital scales. ATR trailing stop is less sensitive to slippage than fixed stop because it exits at a wider, more deliberate distance from peak.

**Fix:**
Monitor actual fill prices vs stop prices once live trading begins. If consistent slippage >0.3% observed, adjust cost model. Compare fixed-stop vs trailing-stop slippage in practice — trailing stop exits tend to be less market-stressed.

**Target:** Week 10 — live bot maintenance batch (alongside A010 and II-001).

**Update log:**
- 2026-06-01: Target date passed without resolution. Week 7 has concluded with no slippage monitoring data logged. Live trade history now exists (trailing stop live since Week 6) but fill prices vs stop prices have not been systematically compared. Retargeted to Week 10 alongside A010 and II-001 Telegram health check redesign — all three are live bot maintenance items that should be addressed together.
- 2026-05-01: Still open. Cost model updated from 0.175% to 0.15% (confirmed Binance fee, see A004). Slippage monitoring plan unchanged.
- 2026-03-20: Raised. Immaterial at current scale, monitor post-live.

---

### A009 — Walk-forward used fixed parameters, not true rolling re-optimisation

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 5 Day 7

**Description:**
Walk-forward validation in Stage 1c (Week 6) used the single best full-sample parameter set (ADX 19/9, trail 8% or ATR 9/2.5x) and tested its performance across rolling 1-year test windows. Parameters were not re-optimised at the end of each training window before testing. This is less rigorous than true walk-forward where parameters are independently selected per window.

**Impact:**
Stage 1c results are supporting evidence of robustness — 5/6 test years positive, consistent Calmar — but are not conclusive proof of parameter stability. The chosen parameters were selected with knowledge of the full 2018–2026 period. A true walk-forward would be a stricter test. Low signal frequency (15–20 trades/year) makes true walk-forward impractical with current data.

**Fix:**
As live trade history accumulates, use real live performance data as the primary validation source. Consider Combinatorial Purged Cross-Validation (CPCV) when 3+ years of additional live data available.

**Target:** Week 8–10 (when sufficient live data available)

**Update log:**
- 2026-05-01: Still open. Acknowledged in Stage 1c design. Live performance is primary validation path.
- 2026-04-07: Raised. Limitation acknowledged.

---

### A010 — Daily loss limit not calibrated for daily candle strategies

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 5 Extension

**Description:**
The 2% daily loss limit in RiskManager was set from intraday trading norms, not from analysis appropriate for a daily candle strategy. Backtesting showed it fires on normal ETH volatility during open positions — reducing ADX annual return from 67.4% to 8.8% when applied. It was removed from the backtest model but may remain in the live bot.

**Impact:**
If the live bot fires the daily loss limit on a valid open position, it exits unnecessarily and blocks re-entry that day. This directly reduces real returns and introduces execution drift vs backtest.

**Fix:**
Remove the daily loss limit from the live bot, or raise it to a threshold that only fires on genuinely extreme intraday losses (e.g. 8–10%). The per-trade trailing stop and max drawdown guardrail provide sufficient protection without a daily limit.

**Target:** Week 10 — live bot maintenance batch (alongside II-001).

**Update log:**
- 2026-06-01: Target date passed without resolution. Trailing stop deployed in Week 6 without resolving this item. Daily loss limit status in live bot unconfirmed. Retargeted to Week 10 alongside II-001 Telegram health check redesign — both are live bot maintenance items that should be addressed together.
- 2026-05-01: Still open. Must be resolved before deploying new trailing stop logic (A011 resolved but bot update pending).
- 2026-04-12: Raised. Daily loss limit removed from backtest after analysis.

---

### A013 — Margin leverage not yet optimised for ETH ADX

**Category:** Strategy

**Status:** Open

**Priority:** High

**Raised:** Week 5 Extension

**Description:**
Preliminary analysis showed leverage could materially improve returns for ETH ADX (annual return approximately doubles at 2x leverage with interest costs nearly zero at 12.41% Kelly sizing). Optimal leverage level not yet determined. Grid search (1.0x–5.0x, 0.1x steps) not yet run with the new trailing stop configuration.

**Key findings from preliminary (fixed-stop) analysis:**
- Interest accrues hourly on borrowed amount only during open positions
- At 12.41% own fraction, total interest over 108 trades at 2x was ~$30
- Minimum margin ratio stayed above 25% safety buffer at tested leverage levels
- Liquidation checked using daily LOW prices on every bar

**Fix:**
Week 6 Stages 3–4: run leverage grid search using the trailing stop backtest (ATR 9/2.5x or pct 8%) as the base strategy. Update Kelly sizing for new metrics. Document liquidation price and safety buffer at recommended leverage.

**Target:** Week 6 Stages 3–4

**Update log:**
- 2026-05-01: Still open. Must use trailing stop baseline (A011 now resolved) for leverage optimisation.
- 2026-04-12: Raised. Preliminary analysis had hold_days bug (now fixed).

---

### A014 — RiskManager guardrails not calibrated for daily candle strategy

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 5 Extension

**Description:**
The RiskManager guardrails (daily loss limit, max drawdown threshold, stop distance) were set from professional intraday norms, not backtested against ETH ADX specifically. The daily loss limit is known inappropriate (A010). The 15% max drawdown guardrail and the stop distance have not been jointly optimised against the trailing stop configuration.

**Impact:**
Suboptimal guardrail settings reduce strategy performance without proportionate protection. With ATR trailing stop now deployed (A011 resolved), the appropriate max drawdown guardrail may differ from the fixed-stop calibration.

**Fix:**
After trailing stop deployment and 20+ live trades, run joint optimisation of ATR multiplier vs max drawdown guardrail to find the Calmar-maximising combination.

**Target:** Week 7 — after trailing stop live deployment and initial trades

**Update log:**
- 2026-05-01: Still open. Guardrail recalibration depends on trailing stop deployment first.
- 2026-04-12: Raised.

---

### A015 — ADX parameter change (19/9) identified as superior but not yet deployed

**Category:** Strategy

**Status:** Open — decision made, monitoring in progress

**Priority:** Medium

**Raised:** Week 6 Stage 1d (2026-05-01)

**Description:**
Stage 1 optimisation (Weeks 6) found ADX threshold 19, period 9 consistently outperforms the live parameters (threshold 20, period 10) across all stop types and all grid configurations. The best overall combination (ADX 19/9, ATR 9/2.5x) produced Calmar 2.642 vs Calmar 2.013 for the retired ADX 20/10 fixed-stop baseline (live 2026-04-04 to 2026-05-13). Stage 1c stability analysis confirmed ADX 19/9 is stable across 5/6 walk-forward test years.

However, the ADX parameter change was identified through in-sample optimisation across 8.3 years of data. The improvement (+0.629 Calmar) is material but has not been validated through true out-of-sample testing. Changing both the ADX parameters AND the stop type simultaneously is two changes at once, which makes attribution harder if live performance deviates.

**Decision (Week 7, 2026-05-03) — UPDATED:**
Primary path selected: deploy ADX 19/9 + percentage trailing stop 8%.

Rationale:
- Candidate A (ADX 19/9, pct 8%) wins on annual return (80.1% vs 73.4%) and Sortino (1.780 vs 1.423).
- Candidate B (ATR) only wins on MaxDD by 3.5pp (−27.8% vs −31.3%) which is ~$52 on $1,500 capital — immaterial at this scale.
- Under the return-first framework with documented drawdown tolerance, A is the correct choice.

Note: this changes two things simultaneously (ADX parameters from 20/10 to 19/9, AND stop type from fixed 5% to pct 8% trailing). If live performance deviates from backtest, attribution of cause will require careful analysis.

Deployment deferred until all Stage 3–5 backtesting is complete. Live bot update to happen at end of Week 6.

**Next review target:** End of Week 6 (deployment). After 20 live trades, compare live metrics to Stage 1d backtest (Calmar 2.557, Sortino 1.780, Annual 80.1%).

**Update log:**
- 2026-05-03: Decision revised. Primary path: ADX 19/9 + pct 8% trailing stop. Annual 80.1% and Sortino 1.780 win vs ATR candidate. MaxDD gap 3.5pp immaterial at $1,500 capital. Deployment deferred to end of Week 6.
- 2026-05-02: Conservative path (ADX 20/10 + ATR 9/2.5x) initially selected. Revised 2026-05-03.
- 2026-05-01: Raised. Stage 1d complete. Deployment path to be chosen in Week 7.

---

### A016 — Tail liquidation risk at 1.9x leverage in extreme crash events

**Category:** Strategy

**Status:** Open — accepted with mitigations documented

**Priority:** High

**Raised:** Week 6 Stage 4 buffer analysis (2026-05-04)

**Description:**
ETH ADX at 1.9x leverage survives the worst historical single-day ETH drop
(−42.9%, 2020-03-12) from a fresh entry: margin ratio falls from 52.6% to
17.0% — below the 25% hard floor but above the 5% liquidation threshold.
However, if the position is at the worst historical backtest margin ratio
(34.4% — observed when an open position has moved against entry by ~35%), the
same −42.9% drop reduces MR to −14.9%: liquidation.

This requires two extreme conditions simultaneously: worst margin drawdown AND
worst single-day price collapse. Probability is low but non-zero. The 2020
COVID crash and 2021 May flash crash demonstrate that extreme events cluster.

**Impact:**
In a combined worst-case scenario, the full leveraged position is liquidated
before the trailing stop fires. This is structurally different from a stop-loss
loss — the account value at liquidation is close to zero (not just a trade loss).
At $1,500 capital, this would be total loss of the leveraged allocation.

**Primary mitigation:**
ATR trailing stop (9/2.5x or pct 8%) has historically exited positions before
the worst intraday lows were reached across 8+ years of backtest data. In every
historical occurrence of a large adverse move, the stop fired in the preceding
period when the peak-to-current drawdown exceeded the stop threshold. The stop
provides genuine protection but is not a mathematical guarantee in gap events.

**Secondary mitigation:**
Margin ratio Telegram alert at 40% provides early warning when MR is declining
toward the danger zone, allowing manual intervention before the extreme scenario
materialises. At 40% MR with a −42.9% drop, resulting MR = 3.5% (near
liquidation) — the 40% alert is therefore the critical early warning level.

**Residual risk:**
Gap events (large overnight price moves between candle close and next open) and
liquidity crises (stop order cannot fill at intended price) can bypass the
trailing stop. These scenarios are structurally unhedgeable at this leverage
level. They are inherent to holding leveraged positions in a 24/7 crypto market.

**Target:** Add margin ratio monitoring (40% alert) to live bot before leveraged
deployment. This is a prerequisite for leveraged ETH ADX live trading.

**Update log:**
- 2026-05-04: Raised. Buffer analysis complete. ETH ADX 1.9× confirmed SAFE
  from fresh entry but VULNERABLE at worst historical MR. Monitoring requirement
  added to LIVE_TRADING_CHECKLIST.md and STRATEGIC_FRAMEWORK.md.

---

### A021 — Exchange technical failure during stop execution

**Category:** Execution / Infrastructure

**Status:** Open

**Priority:** High

**Raised:** Week 7

**Description:**
Binance has documented history of stop order failures during extreme market stress. October 2025 crash: stop-loss orders failed to trigger, accounts frozen, Binance site went down. March 2023: Binance suspended all spot trading for 2 hours due to a bug in the trailing stop feature specifically. During peak volatility, the exchange may be unable to execute stop orders for minutes to hours. At 1.9× leverage, a 20% ETH decline during a 2-hour outage produces a 38% loss on own capital — without the stop ever firing.

**Current mitigation:**
None implemented. $150 cap on RSI, $994 on ADX spot — losses manageable at current unleveraged scale. At leveraged scale this becomes a primary risk.

**Required before leveraged deployment:**
1. Dynamic leverage framework built and backtested — leverage reduces as ADX weakens toward exit threshold
2. Exchange failure stress test — maximum tolerable outage duration quantified at each leverage level
3. Emergency manual exit protocol documented

**Blocker:** Leveraged deployment

**Target:** Before leveraged deployment

**Update log:**
- 2026-05-14: Raised. No mitigation implemented. Blocker for leveraged deployment.

---

### A022 — Monte Carlo analysis not completed for ETH ADX

**Category:** Strategy / Methodology

**Status:** In Progress — Stage 0 complete, Stage 1+ deferred (see below)

**Priority:** MAJOR

**Raised:** Week 7

**Description:**
Monte Carlo simulation has not been run for ETH ADX despite it being mandatory for all strategies under the updated Methodology Standards (Week 7). Walk-forward validation confirms the strategy works across historical regimes but does not address sequence risk or fat-tail uncertainty in the return distribution. With 159 trades and a fat-tailed momentum return distribution (power law α < 3 per Grobys et al. 2025), the true confidence intervals on backtest metrics are wider than the point estimates suggest.

**Required:**
Run Monte Carlo (minimum 10,000 simulations) on the 159-trade backtest results. Output: 5th/50th/95th percentile equity curves, P(negative year), P(50% drawdown), Monte Carlo-derived Kelly fraction. Compare MC Kelly to deployed half-Kelly (12.41%) — reduce position sizing if MC Kelly is materially lower.

**Note on priority:**
Classified MAJOR rather than HIGH because the strategy is validated through the 2022 bear market (+35.1% vs B&H −68.3%), which partially addresses the fat-tail concern. The 2022 confirmation provides direct empirical evidence of fat-tail survival that Monte Carlo alone cannot. However, this does not substitute for the simulation — sequence risk and the probability distribution of forward outcomes remain unquantified.

**Stage 0 finding — Regime Break (confirmed 2026-05-18):**
Full backtest (159 trades, Jan 2018 – May 2026) split at ETH spot ETF approval date (1 May 2024). Results confirm a material regime change in strategy character post-ETF:

| Metric | Pre-ETF (122 trades) | Post-ETF (37 trades) |
|---|---|---|
| Win rate | 44.3% | 35.1% |
| Avg win | +17.01% | +12.04% |
| Avg loss | −4.59% | −3.86% |
| Profit factor | 2.947 | 1.689 |
| Annual return | +102.78% | +23.00% |
| Max drawdown (MtM) | −36.88% | −34.68% |
| Avg hold (days) | 7.9 | 8.0 |

The strategy's risk architecture is intact (worst loss capped at −8.00% in both periods; trade duration unchanged). The edge has compressed: post-ETF win rate is 9pp lower and average wins are 5pp smaller, consistent with more institutionally-driven ETH price action producing shorter-lived or lower-magnitude trends.

**Leverage deployment decision (formal — 2026-05-18):**
Post-ETF regime break confirmed May 2026. Post-ETF profit factor 1.689 vs pre-ETF 2.947. Leverage deployment deferred until post-ETF sample reaches minimum 80 trades and profit factor confirmed above 2.0 over that sample. Revisit: approximately Week 16–18 if strategy remains live.

**Implication for Monte Carlo Stage 1:**
Running MC on the full 159-trade sample would blend two materially different regimes and overstate current forward expectation. When Stage 1 is run, it should be run on: (a) full history, and (b) post-ETF only — with the post-ETF result treated as the conservative case for leverage decision-making.

**Output:** `06_BACKTESTS/Week_8_Notebooks/stage0_regime_break.html` — equity curve split pre/post-ETF with regime statistics.

**Target:** Stage 1 (Monte Carlo) deferred to Week 16–18. Current target: accumulate post-ETF sample to 80 trades while strategy remains live.

**Update log:**
- 2026-05-18: Stage 0 regime break analysis complete. Post-ETF profit factor 1.689 vs pre-ETF 2.947. Leverage deployment formally deferred until post-ETF sample ≥ 80 trades and PF > 2.0. Revisit Week 16–18. Output: stage0_regime_break.html.
- 2026-05-14: Raised. Monte Carlo not yet run. Mandatory per updated Methodology Standards.

---

### A023 — Phase 3B exit method comparison not completed against new pipeline standard

**Category:** Strategy / Methodology

**Status:** Open

**Priority:** Medium

**Raised:** 2026-06-01 (STRATEGY_RESEARCH_PIPELINE.md v2.0 update)

**Description:**
STRATEGY_RESEARCH_PIPELINE.md Phase 3B (added 2026-06-01) requires that all five exit
methods be formally tested before selecting one. The ETH ADX strategy uses ADX signal
reversal exit (ADX drops below threshold or −DI > +DI) combined with a percentage
trailing stop (8% from peak). The following alternatives have not been formally tested
or compared:

- Exit method 3 (ATR trailing stop): ATR multipliers 1.5, 2.0, 2.5, 3.0 — not systematically compared against the current pct 8% trail
- Exit method 4 (EMA trailing stop): EMA periods 20, 30, 50 — not tested
- Exit method 5 (hybrid: ADX signal + ATR trail, whichever fires first)

Week 6 Stage 1b did compare ATR 9/2.5x vs pct 8% trailing stop, but this was a partial
test (two variants of trailing stop), not a full Phase 3B comparison across all five
exit methods with post-break PF as the ranking metric.

**Impact:**
Low at current deployment scale. The existing configuration (ADX signal + pct 8% trail)
was validated through walk-forward and regime break analysis. The gap is methodology
compliance, not imminent risk.

**Fix:**
Complete the full Phase 3B exit comparison when the leveraged bot is designed in Weeks
16–18. Post-break PF is the ranking metric. All five exit methods to be tested on the
post-ETF data period (Jan 2024 onwards) as the primary evaluation window.

**Target:** Weeks 16–18 (alongside A013 leverage design review)

**Update log:**
- 2026-06-01: Raised. New pipeline standard (Phase 3B) requires formal exit comparison.
  Partial work done in Week 6 Stage 1b. Full comparison deferred to leveraged bot design.

---

### A024 — Phase 3C SMA regime filter not tested

**Category:** Strategy / Methodology

**Status:** Open

**Priority:** Low

**Raised:** 2026-06-01 (STRATEGY_RESEARCH_PIPELINE.md v2.0 update)

**Description:**
STRATEGY_RESEARCH_PIPELINE.md Phase 3C (added 2026-06-01) requires that SMA regime
filters be tested as entry gates for all trend-following strategies. The ETH ADX strategy
uses +DI > −DI as a direction confirmation gate but does not require price to be above
a long-term SMA before entering.

The following SMA entry filters have not been formally tested:
- SMA-50 filter: only enter when ETH close > 50-day SMA
- SMA-100 filter: only enter when ETH close > 100-day SMA
- SMA-120 filter: only enter when ETH close > 120-day SMA (validated on ETH RSI)
- SMA-200 filter: only enter when ETH close > 200-day SMA
- EMA-50 filter: only enter when ETH close > 50-day EMA

Relevant context: post-ETF profit factor is 1.689 (A022 regime break analysis). A regime
filter that blocked some of the post-2024 losing trades could improve this metric.
The ETH RSI strategy demonstrates SMA-120 improving post-break PF (from 2.199 to 2.961).
A similar analysis has not been done for ETH ADX.

**Impact:**
Low at current scale. Post-break PF of 1.689 is workable but below the VIABLE threshold
(>2.0). A regime filter that improved this toward 2.0+ would strengthen the case for
leveraged deployment in Weeks 16–18.

**Fix:**
Test SMA 50/100/120/200 and EMA-50 filters on ETH ADX as a joint grid with the exit
method comparison (A023). Complete before the leveraged deployment review. Post-break PF
(Jan 2024 onwards) is the primary ranking metric.

**Target:** Weeks 16–18 alongside A023 and A013 leverage design review

**Update log:**
- 2026-06-01: Raised. New pipeline standard (Phase 3C). No SMA filter testing done to
  date on ETH ADX. Potential to improve post-ETF profit factor above 2.0 threshold.

---

## Resolved Items

| ID | Description | Resolution summary | Resolved | Week / Date |
|---|---|---|---|---|
| A001 | Win rate estimated, not measured | Backtest confirmed 34.3% win rate from 108 stop-loss trades | Week 5 Day 2 | 2026-04-07 |
| A002 | Stop-loss not included in backtest | Bar-by-bar stop-loss backtest built using daily LOW prices | Week 5 Day 1 | 2026-04-07 |
| A004 | Binance fee tier unverified | Actual fee confirmed 0.075% maker/taker (0.15% round-trip); conservative assumption confirmed | Week 4 Day 6 | 2026-04-03 |
| A005 | Kelly sizing based on pre-stop-loss metrics | Kelly recalculated at 11.77% with real inputs; difference from 12.41% immaterial | Week 5 Day 2 | 2026-04-07 |
| A006 | Parameters not re-optimised after adding stop-loss | Joint optimisation complete; live ADX 20/10 + 5% stop acceptable; best combo noted | Week 5 Day 3 | 2026-04-07 |
| A007 | Portfolio-level simulator not built | Portfolio simulator built; 5 sizing strategies compared; Kelly confirmed | Week 5 Day 2 | 2026-04-07 |
| A011 | Fixed stop-loss not trailing; trailing stop not backtested | Stage 1 complete (Week 6). ATR trailing stop (ADX 19/9, ATR 9/2.5x) outperforms fixed stop on all metrics: Calmar 2.642 vs 2.013, Max DD −27.8% vs −31.6%, 0.15% round-trip costs included. Percentage trail 8% is close second. Deployment recommendation: ATR 9/2.5x primary, pct 8% secondary. | Week 6 Stage 1d | 2026-05-01 |
| A017 | Live bot used STOP_LOSS_LIMIT since deployment 2026-04-04 | STOP_LOSS_LIMIT creates gap risk: if ETH price gaps below the limit price during a crash, the stop order does not fill and the position remains open with no protection. Fixed 2026-05-04: changed to STOP_LOSS (market execution on trigger) — guaranteed exit at best available price. Also fixed fill price read in check_stop_loss_triggered (market orders return price=0; actual fill = cummulativeQuoteQty / executedQty). Deployed to EC2 and confirmed live. | Week 6 / 2026-05-04 |
| A018 | No Telegram alert on failed order execution — silent failures unreported | Bot deployed 2026-04-04 with no Telegram alert on failed buy/sell/stop orders. Silent failure discovered 2026-05-04: 23 consecutive failed buy attempts (Apr 12 – May 4) went unreported. ADX signal was LONG from Apr 10 at ~$2,245; current price $2,355 (+4.9% missed). Root cause: Binance API key missing "Enable Spot & Margin Trading" permission. Secondary cause: no order-failure alert in bot. Fixed 2026-05-04: (1) Telegram alerts added for all failed orders and all successful trades; (2) daily health check message sent every run; (3) startup API permission check added using create_test_order; (4) API key recreated with trading permission enabled. | Week 6 / 2026-05-04 |
| A019 | Kelly position sizing implemented incorrectly since Week 4 — 20× undersizing | Kelly fraction (12.41%) was applied as position size (deploy 12.41% of capital = $124) rather than as risk fraction (maximum loss = 12.41% of capital). Correct formula: position = (Kelly% × capital) / stop%. With 5% stop this gives $2,482 — capped at $1,000 unleveraged. Actual risk per trade was 0.62% vs intended 12.41% — 20× undersizing. Discovered 2026-05-05 after first live trade deployed $124 instead of $1,000. Fixed 2026-05-05: `risk_manager.py` `calculate_position_size` corrected to `min(balance − $5, risk / stop_pct)`. Deployed to EC2. Position manually topped up via emergency buy (0.367 ETH @ $2,370.97). Blended entry $2,368.52, stop $2,250.09 (order 46346312221), 0.419 ETH total. All future bots must use correct formula. | Week 6 / 2026-05-05 | RESOLVED |
| A020 | Trade 1 stop placed at 5% from entry ($2,250.09) instead of 8% trailing ($2,179.04) — trailing logic started from wrong base | Root cause: when the automatic stop placement failed on 2026-05-05 (-2010 error), Claude Code placed a manual replacement using old TRAIL_PCT=0.05 rather than the updated 0.08. The trailing stop code itself was not broken — 4× daily checks ran correctly using live price, peak $2,399.50 was correctly recorded, and the code correctly refused to lower the stop. But the 8% trailing formula (peak × 0.92) only exceeds $2,250.09 when price reaches $2,445.75. ETH peaked at $2,408.00 and never got there, so the stop never moved. On this losing trade the tighter stop reduced the loss by ~$28-40 vs intended. On a winning trade it would have capped gains prematurely. Secondary bug: `peak_price_since_entry` was not saved to state when a new high was reached but calculated stop was below current stop — peak tracking was stale on subsequent runs. Both fixed 2026-05-13. Process fix: any manual stop replacement must use TRAIL_PCT (8%) from actual fill price. | 2026-05-13 | RESOLVED |

---

## Capital Allocation

| Strategy | Status | Capital | Position Size | Notes |
|---|---|---|---|---|
| ADX 20/10 ETH (fixed stop) | Retired | $1,000 | 12.41% Kelly | Live 2026-04-04 to 2026-05-13. Replaced by trailing stop version (ADX 19/9, 8% trail). Not additive. |
| ADX 19/9 ETH (pct 8% trailing stop) | Live | $1,000 | 12.41% Kelly (recalibrate post-deployment) | Live since 2026-05-13 (Week 6). Replaces fixed-stop version. Kelly fraction to be recalibrated after 20 post-deployment live trades. |
| ETH ADX (leveraged) | Planned | $1,500 | 100% own capital | Pending A013 (leverage optimisation) |

**Capital scaling rules:**
- Do not increase capital beyond $1,000 until A013 (leverage optimisation) resolved
- Leveraged version replaces unleveraged — not additive — to avoid correlated doubling
- Recalibrate Kelly after 20+ live trades with trailing stop (metrics will differ from fixed-stop baseline)
- Do not deploy leveraged version until A010 (daily loss limit) and A013 both resolved

---

## Review Schedule

| Milestone | Action |
|---|---|
| Before trailing stop deployment | A010 (daily loss limit) resolved; bot mechanics verified against Stage 1d backtest logic |
| Before any capital increase | All High priority items resolved |
| After 20 live trades (trailing stop) | Compare live win rate, profit factor, Calmar vs Stage 1d backtest; review A015 (ADX param change) |
| After 50 live trades | Full parameter re-evaluation; consider true walk-forward on updated data |
| Before leveraged deployment | A013 and A014 resolved; liquidation price documented; safety buffer confirmed ≥25% |
| Sharpe < 0.5 over 30 live trades | Pause live trading, full strategy review |
| Week 7 (complete) | A015 decision updated: primary path — ADX 19/9 + pct 8% trailing stop. Deployment at end of Week 6 backtesting. |
| Week 16–18 (approx) | A022: Review post-ETF sample. If ≥ 80 trades and PF > 2.0, proceed to Monte Carlo Stage 1 and leverage deployment planning. If sample still insufficient or PF still below 2.0, defer further. |
| Every 6 months | Full parameter re-evaluation on rolling window |

---

*Version 2.0 — trailing stop register baseline.*
*Version 2.1 — 2026-06-22: Capital allocation table corrected — trailing stop (ADX 19/9, 8% trail) marked Live since 2026-05-13, fixed-stop (ADX 20/10) marked Retired. A015 stale reference updated. (Week 10 audit Action 4)*
