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
