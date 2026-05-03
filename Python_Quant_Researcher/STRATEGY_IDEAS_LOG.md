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

**Notes:**
BTC SMA and BTC ADX perform differently by regime: SMA is better in slow sustained trends (2020–2021 bull run, −6.6% in 2022 bear market) while ADX is better in volatile multi-wave bull markets and V-shaped recoveries (Ann +42.3%, more responsive to re-entries). Running both simultaneously allocates capital to the weaker strategy in any given regime.

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

**Notes:**
Trend-following strategies miss V-shaped recoveries because confirmation signals (SMA crossover, ADX threshold) arrive after the initial bounce. Key observation: BTC SMA in 2020 returned only +6% vs B&H +303% — the entire gain was in the V-shaped recovery before any SMA signal fired.

Three research directions:

(1) Mean reversion entries during crashes — RSI/Bollinger Band already validated for ETH (ETH RSI 14/43/48). Investigate whether a similar oversold-entry strategy on BTC captures crash-recovery returns that trend strategies miss.

(2) Volatility breakout strategies — on the Week 8 curriculum. Volatility expansion after compression often precedes V-shaped recoveries. Research whether breakout entries on VIX-equivalent (crypto fear index) or ATR expansion signal captures early recovery moves.

(3) Combined portfolio: trend + mean reversion — running a trend-following strategy alongside a mean reversion strategy should smooth cross-regime performance. In bear/recovery regimes the mean reversion strategy earns while trend is flat/negative; in sustained bull runs the trend strategy earns while mean reversion chops. Investigate correlation of returns between ETH ADX and ETH RSI strategies already live.

Priority below SI003 because the mean reversion component (ETH RSI) is already deployed — the incremental value is in the BTC application and portfolio combination analysis.
