# Strategy Ideas Log
## DeFi Quant Engineer Curriculum

Purpose: Capture trading strategy ideas for future investigation. Reviewed at start of each new week.

---

## Log Format

| Field | Description |
|---|---|
| ID | Unique reference (SI001, SI002, …) |
| Name | Short strategy name |
| Type | Category (see below) |
| Source | Where the idea originated |
| Priority | HIGH / MEDIUM / LOW |
| Target Week | Earliest week to investigate |
| Notes | Key context, dependencies, caveats |
| Date Added | YYYY-MM-DD |

---

## Categories

- Trend Following
- Mean Reversion
- Momentum
- Volatility
- DeFi/On-chain
- Arbitrage

---

## Ideas Log

### SI001 — BTC ADX 19/14 Full Validation

| Field | Value |
|---|---|
| **ID** | SI001 |
| **Name** | BTC ADX 19/14 Full Validation |
| **Type** | Trend Following |
| **Source** | Week 5 discovery |
| **Priority** | HIGH |
| **Target Week** | Week 7 |
| **Date Added** | 2026-05-01 |

**Notes:**
Partially validated in Week 5 — needs trailing stop optimisation, cost correction, Sortino correction, and walk-forward validation before deployment. Currently the BTC SMA fallback strategy. Week 5 optimum was ADX threshold 16, period 8 with fixed 5% stop, but this was computed with incorrect Sortino (per-trade method, inflates 3-4×) and without 0.15% round-trip costs applied. Re-validation required with corrected methodology before any deployment decision.

**Week 7 update — SI001 fully validated, GO decision:**
Full 4-stage validation complete (Week 7). Corrected methodology (daily equity Sortino, 0.15% costs). Key findings:
- Fixed 3% stop outperforms all trailing stops — opposite of ETH ADX. Reason: high trade frequency (103 trades) makes fixed stop's quick-exit discipline superior to trailing stops, which add MtM drawdown without adding return.
- Best: ADX 19/14, fixed 3% stop. Ann +42.3%, MaxDD −42.0% per-trade / −45.2% MtM, Sortino 1.441, Calmar 1.007, 103 trades.
- Stage B: MARGINAL stability (54.5%). Half-split concern: 2018–2021 +95.1%/yr vs post-2022 +5.4%/yr — sharp regime deterioration.
- Stage C: 2/3 walk-forward windows pass. 2022 fail (−42.0%) vs BTC B&H −65.3%.
- Stage D: ETH cross-asset PARTIAL — Sortino 0.794 (just below 0.8 threshold), Calmar 1.069 (above 1.0).
- GO decision: Calmar 1.007 borderline. Inferior to BTC SMA on risk-adjusted basis. Deployable but second choice for BTC capital.
- Capital allocation: $1,000 BTC. Deploy BTC SMA (preferred) when conditions met; BTC ADX is fallback.

---

### SI002 — BTC ADX 19/14 (secondary BTC strategy)

| Field | Value |
|---|---|
| **ID** | SI002 |
| **Name** | BTC ADX 19/14 Fixed 3% Stop |
| **Type** | Trend Following |
| **Source** | Week 7 SI001 validation outcome |
| **Priority** | MEDIUM |
| **Target Week** | Week 9+ (only if BTC SMA deployment delayed or fails live) |
| **Date Added** | 2026-05-02 |

**Notes:**
BTC ADX 19/14 fully validated in Week 7. GO decision, but ranked below BTC SMA 120/25% on all risk-adjusted metrics. Should be treated as a fallback for BTC capital, not a co-deployment.

Key finding: fixed 3% stop is optimal — trailing stops underperform on this strategy. This is structurally different from ETH ADX where ATR trailing stop gave Calmar 2.642 vs 2.013 fixed. Reason: BTC ADX 19/14 generates 103 trades/8yr; quick exits and frequent re-entries work better than wider trailing stops that increase MtM drawdown without adding return.

Regime concern: post-2022 annual return only +5.4%/yr (vs +95.1%/yr pre-2022). Strong regime deterioration. Monitor closely — if first 20 live trades show <5% annual rate, re-evaluate deployment.

Full metrics (corrected): Ann +42.3%, MaxDD −42.0% per-trade / −45.2% MtM, Sortino 1.441, Calmar 1.007, 103 trades, 27.2% win rate, 2022 return −42.0%.

B&H comparison: Ann 2.10× B&H (BTC SMA); MaxDD 0.37× B&H. Note BTC ADX fares worse in 2022 (−42.0% vs B&H −65.3%) but SMA is much better (−6.6%).

Deployment path: Only deploy if BTC SMA (CONDITIONAL GO) is not yet ready due to capital constraints or additional validation requirements.

---

### SI003 — BTC Regime-Switching: SMA vs ADX Rotation

| Field | Value |
|---|---|
| **ID** | SI003 |
| **Name** | BTC Regime-Switching: SMA vs ADX Rotation |
| **Type** | Trend Following / Portfolio |
| **Source** | Week 6 observation |
| **Priority** | HIGH |
| **Target Week** | Week 9 |
| **Date Added** | 2026-05-03 |

**⚠ Do NOT overlook at start of Week 9 — review this entry explicitly before beginning Week 9 work.**

**Notes:**
BTC SMA and BTC ADX perform differently by regime, with clear year-by-year evidence:
- 2021 (volatile multi-wave bull): ADX +467% vs SMA +236% — ADX wins decisively
- 2022 (sustained bear): SMA −7% vs ADX −42% — SMA wins decisively
- 2020 (V-shaped recovery): ADX +28% vs SMA +6% — ADX captures more of the initial bounce

Running both simultaneously allocates capital to the weaker strategy in any given regime. A classifier that correctly identifies regime type in advance could significantly improve overall BTC returns.

Research question: can a regime classifier identify in advance which strategy to deploy, or how to weight between them?

Candidate classifiers to investigate:
- Volatility-based: realised vol or ATR regime (low vol → SMA, high vol → ADX)
- Indicator-based: trending vs ranging regime (ADX level itself as meta-signal)
- ML-based: classify regime using lagged volatility, return autocorrelation, drawdown depth

Directly relevant to Week 9 multi-strategy portfolio work. If a classifier can correctly assign regime even 60% of the time, the combined strategy should outperform either standalone on risk-adjusted metrics. Potential to capture both the SMA's bear-market capital preservation and the ADX's volatile-regime responsiveness.

Dependency: both BTC SMA and BTC ADX must be live and generating trade logs before regime-switching research is meaningful.

---

### SI004 — V-Shaped Recovery Strategies

| Field | Value |
|---|---|
| **ID** | SI004 |
| **Name** | V-Shaped Recovery Strategies |
| **Type** | Mean Reversion / Volatility |
| **Source** | Week 6 observation |
| **Priority** | MEDIUM |
| **Target Week** | Week 8–9 |
| **Date Added** | 2026-05-03 |

**Review at start of Week 8 and Week 9.**

**Notes:**
Trend-following strategies miss V-shaped recoveries because confirmation signals arrive after the initial bounce. Year-by-year evidence: 2020 V-shaped recovery — SMA +6%, ADX +28% vs B&H +303%. The entire B&H gain was in the crash-recovery move before any trend signal fired.

Three research directions:

(1) Mean reversion entries during crash — RSI and Bollinger Bands already validated and partially address this (ETH RSI 14/43/48 deployed). Investigate whether a similar oversold-entry strategy on BTC captures crash-recovery returns that trend strategies miss.

(2) Volatility breakout strategies — covered in Week 8 curriculum. Volatility expansion after compression often precedes V-shaped recoveries. Research whether breakout entries on ATR expansion or volatility regime signal captures early recovery moves.

(3) Combined portfolio of trend + mean reversion — running trend alongside mean reversion should smooth cross-regime performance. In bear/recovery regimes the mean reversion strategy earns while trend is flat/negative; in sustained bull runs the trend strategy earns while mean reversion chops. Test formally in Week 9 using correlation of returns between ETH ADX and ETH RSI strategies already live.

Priority below SI003 because the mean reversion component (ETH RSI) is already deployed — the incremental value is in the BTC application and the Week 9 portfolio combination analysis.

---

### SI005 — Cloud Compute Review Schedule

| Field | Value |
|---|---|
| **ID** | SI005 |
| **Name** | Cloud Compute Review Schedule |
| **Type** | Infrastructure |
| **Source** | Week 6 planning |
| **Priority** | HIGH |
| **Target Week** | Weeks 10, 13, 20 |
| **Date Added** | 2026-05-04 |

**Notes:**
Review compute requirements at scheduled milestones. MacBook M3 8GB is sufficient for daily candle backtesting through at least Week 12. Do not upgrade hardware — use cloud services instead.

- **Week 10 (ML training):** Consider Google Colab (free) if local Random Forest / XGBoost training takes >30 minutes per model.
- **Week 13 (large backtests):** Consider EC2 overnight runs for grids >50,000 combinations or minute-level intraday data. EC2 already available at 3.104.101.30 (Elastic IP, ap-southeast-2).
- **Week 20+ (HFT):** Dedicated cloud infrastructure required. Local MacBook not suitable for latency-sensitive execution. Review co-location and cloud exchange connectivity at that point.

General rule: any computation expected to take >2 hours on local Mac should run on EC2 instead. EC2 c5.2xlarge (8 vCPUs, 16GB RAM) costs ~$0.34/hour — a 6-hour run costs ~$2. Google Colab free for ML workloads.

---

### SI006 — Multi-Exchange Execution for Large Positions

| Field | Value |
|---|---|
| **ID** | SI006 |
| **Name** | Multi-Exchange Execution for Large Positions |
| **Type** | Infrastructure |
| **Source** | Week 6 observation |
| **Priority** | LOW |
| **Target Week** | Week 18–20 |
| **Date Added** | 2026-05-04 |

**Notes:**
When single position size exceeds $5,000–$10,000, consider splitting execution across Binance (primary) and Coinbase/Kraken (secondary) to reduce exchange outage risk. Binance documented infrastructure failures during the October 2025 crash ($683M total compensation paid to affected users). At current position sizes (<$1,500 per strategy), the operational complexity of multi-exchange execution is not justified — a single exchange outage would cost less than the overhead of maintaining dual exchange connectivity.

Not worth implementing until position sizes grow to the $5,000–$10,000 range where exchange outage risk becomes material relative to the engineering cost.

Review at Week 18–20 (Docker/infrastructure professionalisation phase) when bot architecture is being rebuilt for production. At that point, assess: whether position sizes have grown to the threshold, whether Binance outage history since Week 6 warrants earlier action, and whether Coinbase or Kraken APIs are sufficiently compatible with existing bot logic to justify dual-exchange support.

---

### SI007 — Performance-Weighted Capital Allocation

| Field | Value |
|---|---|
| **ID** | SI007 |
| **Name** | Performance-Weighted Capital Allocation |
| **Type** | Portfolio Management |
| **Source** | Week 6 observation |
| **Priority** | HIGH |
| **Target Week** | Week 9 |
| **Date Added** | 2026-05-06 |

**Notes:**
Fixed percentage allocation holds back best-performing strategies. Solution: tiered approach — base allocation (fixed percentage, ensures diversification is preserved) plus performance pool (Sortino + annual return% weighted, 50/50 equal weight). Rebalance quarterly minimum — monthly rebalancing on 4–12 trades/year is pure noise. Requires minimum 20 live trades per strategy before allocation shifts.

Confidence-based initial allocation at deployment: score each strategy on sample size, stability result, walk-forward consistency, B&H relative multiple, and live trade count. Do not allocate equal capital to a 31-trade strategy and a 103-trade strategy without justification.

Dynamic opportunistic allocation (idle capital flows to active signal) deferred — forced partial exits override strategy logic and backtesting interaction effects are complex.

Data collection starts now via `record_trade_result()` in portfolio_manager. Implement full framework in Week 9 multi-strategy portfolio work.

---

### SI008 — Monte Carlo Simulation for Strategy Validation

| Field | Value |
|---|---|
| **ID** | SI008 |
| **Name** | Monte Carlo Simulation for Strategy Validation |
| **Type** | Methodology |
| **Source** | Week 6 observation |
| **Priority** | HIGH |
| **Target Week** | All future strategies |
| **Date Added** | 2026-05-06 |

**Notes:**
Monte Carlo stress testing should be run on every strategy before deployment, especially low-frequency strategies with fewer than 50 backtest trades. Run 1,000 simulations at multiple win rate scenarios (backtest rate, 80%, 75%, 70%, 65%) to understand the full distribution of outcomes. Key outputs: median annual return, 10th percentile, probability of negative year, Kelly fraction at each win rate. Identifies strategies with fragile win-rate dependency before live capital is committed.

RSI case study: backtest win rate 93.5% produced median +22.3% annual return. At 70% realistic live win rate, Kelly turns negative — strategy has no positive expectancy at that win rate. This would not have been visible from backtest metrics alone. Monte Carlo revealed the deployment position size should be based on the moderate live scenario ($341), not the backtest scenario ($495).

Now incorporated into STRATEGY_RESEARCH_PIPELINE.md Phase 3 as a required step for n < 100 backtest trades.

---

### SI009 — Bear Market / Short Strategies

| Field | Value |
|---|---|
| **ID** | SI009 |
| **Name** | Bear Market / Short Strategies |
| **Type** | Trend Following / Momentum |
| **Source** | Week 7 |
| **Priority** | MEDIUM |
| **Target Week** | Weeks 13–18 |
| **Date Added** | 2026-05-13 |

**Notes:**
Strategies that profit during sustained crypto downtrends. Requires either shorting (borrowing asset to sell, repurchase cheaper) or derivatives (futures, perpetual swaps).

**Why deferred:** UK FCA retail classification blocks access to Binance futures and perpetuals. Long-only constraint is a fundamental restriction until Professional Client status is obtained or DeFi alternatives are used.

**Two paths to unlock:**

1. **Elective Professional Client application** to FCA/Binance (requires 2 of 3: 10+ trades/quarter for 4 quarters, €500k+ portfolio, or 1+ year professional finance experience). Realistic target: Weeks 18–24 as live trading track record builds.

2. **DeFi perpetuals** (dYdX, GMX, Synthetix) — decentralised, no FCA jurisdiction, no KYC restriction. Proper study required before use (smart contract risk, liquidation mechanics, funding rates).

Curriculum target: Weeks 13–18 (DeFi deep-dive already scheduled).

---

### SI010 — Retrospective Research: Trend-Following Indicator Selection

| Field | Value |
|---|---|
| **ID** | SI010 |
| **Name** | Retrospective Research: Trend-Following Indicator Selection |
| **Type** | Methodology / Research |
| **Source** | Week 7 |
| **Priority** | HIGH |
| **Target Week** | Week 8 (or when next trend-following strategy is built) |
| **Date Added** | 2026-05-13 |

**⚠ Review at Week 8 start before building any new trend-following strategy.**

**Notes:**
A structured Phase 0 research exercise to validate that ADX is the optimal trend-following indicator for ETH and BTC daily candles, or to identify a superior alternative that should be tested alongside or instead of ADX.

**Background:** ADX was selected from the curriculum list without prior literature research. The validation pipeline (728-combination grid search, walk-forward, Monte Carlo) compensated for the missing research phase and produced a robust deployed strategy. However, we have never formally asked: is ADX the best trend-following indicator for this asset and timeframe, or did we happen to start with a reasonable choice?

**Research must cover:**
- Academic literature on trend-following indicators for crypto daily candles (ADX, Donchian, moving average crossovers, Ichimoku, Supertrend, Keltner Channel)
- Which indicators have the strongest empirical support specifically on BTC and ETH daily data
- Whether any indicator class consistently outperforms ADX on crypto in peer-reviewed backtests
- Parameter sensitivity comparison across indicator families
- Regime filter effectiveness across indicator types

**Hypothesis to test:** Donchian Channel Breakout may be a natural complement or partial substitute for ADX — both have similar payoff profiles (30–40% WR, 3–5× R:R) but detect trends differently. ADX measures trend strength; Donchian detects trend start via price breakout. Running both may improve signal frequency without adding correlation.

**Action:** Run full Phase 0 research brief before building any new trend-following strategy. Compare findings directly against ADX 19/9 backtest metrics (Annual +79.7%, Sharpe 1.425, Sortino 1.761, Calmar 2.160).

---

### SI011 — Altcoin Pairs: Higher Volatility, Less Efficient Markets

| Field | Value |
|---|---|
| **ID** | SI011 |
| **Name** | Altcoin Pairs: Higher Volatility, Less Efficient Markets |
| **Type** | Trend Following / Mean Reversion |
| **Source** | Week 7 |
| **Priority** | MEDIUM |
| **Target Week** | Week 13+ |
| **Date Added** | 2026-05-14 |

**Notes:**
Trade less common currency pairs on Binance — assets with greater price swings than BTC/ETH. Examples: SOL, AVAX, MATIC, LINK daily candles. Less institutional coverage = less efficient pricing = potentially larger exploitable edges.

**Hypothesis:** The ADX trend-following and mean reversion strategies may produce stronger signals on higher-volatility altcoins where trends are more pronounced and oversold bounces are more reliable. The same parameter sets optimised for ETH may transfer or may need asset-specific optimisation.

**Pump and dump identification:** Research whether systematic indicators can identify early-stage pump patterns before they become obvious — unusual volume spikes on low-cap pairs, RSI divergence from price, order book imbalance signals.

**Legal caveat:** Pump and dump schemes are potentially illegal to participate in knowingly in many jurisdictions. Requires legal research before any implementation. Do not pursue this sub-direction until legal position is confirmed.

**Risks:**
- Much lower liquidity on altcoin pairs — position sizing must be adjusted
- Spreads are wider; stop slippage is more severe
- Exchange listing/delisting risk (asset may disappear)
- Manipulation risk is higher on small caps

**Dependency:** Core BTC/ETH strategies must be validated and deployed before expanding to altcoin pairs. Do not begin until Week 13+.

---

### SI012 — Regime-Switching Portfolio: ADX Trend + Bollinger Mean Reversion on Same Asset

| Field | Value |
|---|---|
| **ID** | SI012 |
| **Name** | Regime-Switching Portfolio: ADX Trend + Bollinger Mean Reversion |
| **Type** | Trend Following / Mean Reversion / Portfolio |
| **Source** | Week 7 |
| **Priority** | HIGH |
| **Target Week** | Week 9–10 |
| **Date Added** | 2026-05-14 |

**Notes:**
Run two complementary bots on the same asset (ETH or BTC): momentum bot active when ADX > 20 (trending), mean reversion bot active when ADX < 20 (ranging). Bots are self-selecting — never both active simultaneously. Fills the current portfolio regime gap where both deployed strategies are flat during sideways markets.

**Evidence:** WEEK_7_RESEARCH_BRIEF_FULL.md identifies this as the most actionable gap in the current portfolio. Bollinger Bands mean reversion on BTC daily: ~50% CAGR at 34% market exposure (QuantifiedStrategies 2026). ADX as regime filter has strong multi-source support. Combined approach addresses the finding that BTC Hurst exponent 2021–2024 = 0.52 (borderline trending/random) — neither pure momentum nor pure mean reversion dominates.

**Implementation:**
- ETH ADX bot (existing) handles trending regime (ADX > 20)
- New Bollinger bot handles ranging regime (ADX < 20)
- Shared capital pool with allocation rules: if ADX > 20, allocate to ADX bot; if ADX < 20, allocate to Bollinger bot; if transitioning, no allocation

**References:** SI003 (BTC regime-switching: SMA vs ADX rotation). SI012 is broader — applies to any asset and pairs two different strategy types rather than two variants of the same strategy type.

**Dependency:** Bollinger and MAX strategies must be backtested and validated before implementation.

---

### SI013 — Quarter-Kelly Sizing for Unvalidated Momentum Strategies

| Field | Value |
|---|---|
| **ID** | SI013 |
| **Name** | Quarter-Kelly Sizing for Unvalidated Momentum Strategies |
| **Type** | Methodology / Risk Management |
| **Source** | Week 7 |
| **Priority** | HIGH |
| **Target Week** | Immediate — applies to all new momentum strategies from Week 8 onwards |
| **Date Added** | 2026-05-14 |

**Notes:**
A sizing rule, not a strategy. Any new momentum strategy (Donchian, MAX, MACD) that has not been confirmed through a full bear market cycle should use quarter-Kelly position sizing, not half-Kelly. This reflects the power law distribution finding that momentum strategy confidence intervals are materially wider than backtest numbers suggest.

**Current application:**
- ETH ADX uses half-Kelly (12.41%) — justified because it has 2022 out-of-sample confirmation (+35.1% vs B&H −68.3%)
- New momentum strategies in Weeks 8–12 should start at quarter-Kelly (~6%) until their first bear market validation period is complete
- Promotion to half-Kelly requires documented out-of-sample evidence through a bear market period

**Not applicable to:** Mean reversion strategies (Bollinger, RSI, MIN). Power law instability primarily affects momentum strategies that ride fat-tail returns. Mean reversion strategies cap individual trade size by design and are less affected.

This rule is now codified in METHODOLOGY_STANDARDS.md under "Momentum Strategy Validation Standards."

---

### SI014 — Pension Investment Strategy Research

| Field | Value |
|---|---|
| **ID** | SI014 |
| **Name** | Pension Investment Strategy Research |
| **Type** | Multi-asset / Long-term |
| **Source** | Week 7 |
| **Priority** | LOW |
| **Target Week** | Week 20+ — after core crypto infrastructure is built and stable |
| **Date Added** | 2026-05-15 |

**What it is:** Research and develop systematic strategies suitable for pension investment — long-term, lower frequency, capital preservation focus. Not crypto — traditional assets (equities, bonds, ETFs, index funds).

**Context:** Greg wants to apply quant principles learned in this curriculum to personal pension portfolio management. Different risk profile from crypto trading — lower volatility tolerance, longer time horizon, tax-efficient wrappers (ISA, SIPP in UK context).

**What to research:** Systematic rebalancing strategies, factor investing (value, momentum, quality), passive vs active allocation, lifecycle investing principles, drawdown management for retirement portfolios.

**Introduced:** Week 7

---

### SI015 — Stock Selection: Insider Buy Superstocks Methodology

| Field | Value |
|---|---|
| **ID** | SI015 |
| **Name** | Stock Selection: Insider Buy Superstocks Methodology |
| **Type** | Equity / Semi-systematic |
| **Source** | Week 7 |
| **Priority** | LOW |
| **Target Week** | Week 20+ — after core crypto work complete |
| **Date Added** | 2026-05-15 |

**What it is:** Research and backtest the stock selection methodology from the book "Insider Buy Superstocks" — identifies stocks with significant insider buying as a signal for outperformance.

**Context:** Greg wants to apply this methodology to UK/US stock markets. Insider buying is a legally disclosed signal (Form 4 filings in US, PDMR disclosures in UK) where company executives and directors buy shares in their own company with personal money — historically a strong positive signal.

**What to research:** How to access insider buying data (SEC EDGAR for US, FCA/Companies House for UK), screening criteria from the book, backtesting methodology on stock universe, position sizing for concentrated stock portfolios.

**Note:** This is a discretionary/semi-systematic equity strategy, not crypto. Requires different data infrastructure and regulatory knowledge. Legal in all jurisdictions — insider buying (not selling) is a public signal.

**Introduced:** Week 7

---

### SI016 — Pump Detection / Momentum Surfing on Intraday Candles

| Field | Value |
|---|---|
| **ID** | SI016 |
| **Name** | Pump Detection / Momentum Surfing (15-min / 1-hour) |
| **Type** | Momentum / Intraday |
| **Asset** | Mid-cap altcoins — small cap, high volatility, no significant institutional interest |
| **Source** | Week 8 |
| **Priority** | LOW |
| **Target Week** | Week 16–18 — alongside DeFi deep-dive |
| **Date Added** | 2026-05-20 |

**What it is:** Detect the early phase of organic price pumps on 15-minute (minimum) or 1-hour candles and enter momentum positions before the move is fully priced. Exit on a fixed time basis (2–4 hours) OR on a volume collapse signal, whichever fires first.

**Signals:**
- Volume spike: 3–10× rolling average (primary — distinguishes pump from random move)
- Price velocity: rate of change over a short window (confirms directional momentum)
- Social sentiment (optional but significantly improves signal quality): LunarCrush or Santiment API — rising mention count or sentiment score correlated with volume spike

**Entry / exit rules:**
- Entry: confirmed volume spike + price velocity above threshold on same bar
- Exit A: fixed time exit at 2–4 hours from entry (hard cap on trade duration)
- Exit B: volume collapse — current bar volume falls below rolling average (momentum exhaustion)
- Stop: hard stop at entry candle low (intraday, so tight)
- Position sizing: very small — high risk / high reward profile; quarter-Kelly or fixed fractional (not Kelly-derived until live win rate established)

**Infrastructure prerequisites (all required before this is viable):**
- Intraday data pipeline — 15-min candle feed; not available in current daily-candle infrastructure
- Event-driven execution — cron-based daily bot is insufficient; requires asyncio or message-queue architecture with sub-minute latency
- Social data API — LunarCrush or Santiment (optional but materially improves signal quality)

**Why deferred to Week 16–18:**
All current infrastructure is daily candles and cron-based. Intraday requires a fundamentally different execution layer. Complete the daily strategy framework (Weeks 9–15) before introducing intraday complexity. Week 16–18 DeFi deep-dive is the natural entry point for on-chain and social data integration.

**Legal distinction (important):**
Detecting and riding an organic pump is legal. Participating in, coordinating, or promoting a pump-and-dump scheme is not — it constitutes market manipulation and is a criminal offence in most jurisdictions. Any implementation must target organic volume events only. No coordination with any third party about upcoming moves. This distinction must be maintained clearly in any future implementation research.

**What to research when the time comes:**
- Intraday data sources: WebSocket feeds vs REST polling; Binance WS API for real-time candles
- Event-driven bot architecture: asyncio, Redis pub/sub, or Kafka for message queuing
- Volume anomaly detection: rolling z-score vs static multiple — z-score adapts to regime changes
- False positive rate analysis: what fraction of 3–10× volume spikes produce sustained moves vs immediate reversals
- Social sentiment API integration: LunarCrush v3 or Santiment GraphQL
- Backtesting methodology for intraday strategies (no daily close assumption; slippage modelling differs)

**Introduced:** Week 8

---

### SI017 — Week 8 SOL Discovery Results + Altcoin Backtest Queue

| Field | Value |
|---|---|
| **ID** | SI017 |
| **Name** | SOL Discovery Results (Week 8) + Altcoin Backtest Queue |
| **Type** | Research Log / Multi-asset |
| **Source** | Week 8 |
| **Priority** | HIGH |
| **Target Week** | Week 9 — data quality checks first, then backtest queue |
| **Date Added** | 2026-05-20 |

**Purpose of this entry:** Record Week 8 SOL discovery outcomes for reference and define the Week 9 altcoin backtest queue.

---

**Week 8 SOL multi-strategy discovery results (sol_grid_search.py, ~1,478 combinations):**

| Strategy | Combos tested | Combos passing filters | Best annual | Best MDD | Outcome |
|---|---|---|---|---|---|
| Keltner Channel | 44 | 21 | +121.9% (ema=22/mult=1.5) | −45.6% | **REJECTED** — regime break post-Aug 2025 (PF 0.055) |
| ADX | 1,232 | 1 | +27.7% (p=14/thr=21/stop=6%) | −49.9% | **REJECTED** — 1 viable combo, below B&H, Sortino 0.668 |
| Supertrend | 70 | 0 | N/A | N/A | **REJECTED** — 0 combos pass ≥30 trades / MDD > −50% filter |
| Donchian | 77 | 0 | N/A | N/A | **REJECTED** — 0 combos pass filter |
| Bollinger | 55 | 0 | N/A | N/A | **REJECTED** — 0 combos pass filter |

Filter criteria: ≥30 trades AND MDD > −50%. All results documented in STRATEGY_ARCHIVE.md (S006–S010).

**Key SOL finding:** Keltner Channel was the only viable indicator family on SOLUSDT, but regime break analysis (sol_regime_break.py) showed complete edge collapse post-ATH (PF 7.793 pre-ETF → 3.932 ETF-to-ATH → 0.055 post-ATH). SOL daily candles are not a productive research direction at current market structure.

---

**Week 9 altcoin backtest queue:**

The following assets are added to the research queue for multi-strategy discovery grids in Week 9. Data quality checks must be completed before running any backtest (confirm data start date, identify any gaps or delistings, verify symbol availability on Binance).

| Asset | Symbol | Notes |
|---|---|---|
| BNB | BNBUSDT | Binance native token — data available from 2017; well-established liquidity |
| AVAX | AVAXUSDT | Data from ~2020; institutional interest growing |
| LINK | LINKUSDT | Data from 2017 on Binance; strong liquidity |
| DOT | DOTUSDT | Data from ~2020; lower liquidity than BNB/LINK |
| MATIC | MATICUSDT | Renamed POLYGONUSDT in some feeds — verify symbol before data pull |

**Methodology note:** Run the same multi-strategy discovery grid used for SOL (sol_grid_search.py framework — ADX, Supertrend, Donchian, Keltner, Bollinger, ~1,478 combos) on each asset. Only proceed to walk-forward validation for assets where ≥1 strategy type shows ≥5 passing combinations with Sortino > 0.8.

**Introduced:** Week 8

---

## Infrastructure Improvements

### II-001 — Telegram Health Check Message Redesign

| Field | Value |
|---|---|
| **ID** | II-001 |
| **Name** | Telegram Health Check Message Redesign |
| **Type** | Infrastructure |
| **Source** | Week 7 |
| **Priority** | MEDIUM |
| **Target Week** | Week 8 — implement before leveraged bot deployment |
| **Date Added** | 2026-05-15 |

**What it is:** Redesign the Telegram health check messages sent by all bots to improve readability and reduce noise.

**Current problems:** Status buried after timestamp, portfolio block repeated identically across both bot messages, no visual hierarchy, redundant cash balance shown twice.

**Required changes:**
- Lead with status as the first word — FLAT / LONG / EXIT
- When FLAT: short 3-line format. Bot name, signal proximity (e.g. ADX 18.9 vs threshold 19), capital allocated. No portfolio block.
- When LONG: richer format showing entry price, current stop, peak price, current price, unrealised P&L, capital at risk
- Remove shared cash balance from individual bot messages — show only in a separate daily portfolio summary if needed
- Apply to all bots: day5_production_bot.py, rsi_production_bot.py, and any future bots including the leveraged bot

**Introduced:** Week 7
