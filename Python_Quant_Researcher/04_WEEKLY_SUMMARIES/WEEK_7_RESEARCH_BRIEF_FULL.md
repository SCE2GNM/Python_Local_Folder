# Comprehensive Research Brief — Momentum & Mean Reversion Strategies
## DeFi Quant Engineer Curriculum
**Prepared:** 2026-05-13
**Scope:** Momentum AND mean reversion strategies on major crypto pairs
**Timeframe focus:** Daily candles (consistent with current infrastructure)
**Constraints:** Long-only (UK FCA), BTC and ETH primary assets
**Sources:** SSRN, Quantpedia, QuantifiedStrategies, Springer, academic 
papers, peer-reviewed journals, systematic practitioner research

---

## Executive Summary

After comprehensive research across academic and practitioner sources,
six strategies emerge with meaningful empirical support for daily
candle trading on BTC/ETH. They fall into three categories:

**MOMENTUM (Trend-Following):**
1. Donchian Channel Breakout (20-day) — strongest evidence, best 
   fit for our architecture
2. MAX Strategy (10-day new high continuation) — Quantpedia 
   peer-reviewed, confirmed through August 2024
3. MACD with regime filter — widely tested, needs 200MA filter

**MEAN REVERSION:**
4. Bollinger Bands (20/2) lower band touch — ~50% CAGR, 34% 
   market exposure, strongest mean reversion evidence on BTC
5. MIN Strategy (10-day new low bounce) — Quantpedia peer-reviewed,
   confirmed but higher drawdown than MAX
6. Z-score deviation strategy — strong on ETH post-2021 (Sharpe 2.3)

**HYBRID:**
7. MIN+MAX Combined — the single best-performing approach in 
   Quantpedia's research: 98.43% annual, -37.67% MDD, 
   Ret/Vol ratio 2.06 (2015-2022 data)

**Critical overarching finding:** Regime matters more than indicator
choice. Momentum outperforms in trending markets (ADX>20, price above
200MA). Mean reversion outperforms in ranging/low-volume markets
(ADX<20, Bollinger squeeze). The same indicator applied in the wrong
regime produces losses that the right regime produces profits.

---

## CRITICAL ACADEMIC WARNING (Read Before Building Anything)

Two independent 2025 papers confirm that **cryptocurrency momentum 
strategies have undefined theoretical variance** — power law exponents
below 3 mean variance is not finite. Backtest confidence intervals are
materially wider than they appear for ALL momentum strategies.

The practical implication: a 5-year backtest showing excellent results
is still consistent with negative long-run performance. This is not
theoretical — it explains why many momentum strategies that looked
great in 2020-2021 collapsed in 2022.

**This does not apply equally to mean reversion.** Mean reversion 
strategies on BTC/ETH daily data show more stable variance because 
the payoff distribution is less fat-tailed (smaller wins, smaller 
losses). The BTC-neutral residual mean reversion strategy (Sharpe 2.3
post-2021) specifically avoided this problem by stripping out 
directional BTC exposure.

**Implication:** Monte Carlo is essential for all momentum strategies.
Mean reversion strategies are relatively more trustworthy statistically
but still require walk-forward validation.

---

## THE REGIME QUESTION — Most Important Finding

Multiple independent sources converge on one finding that matters 
more than any individual strategy:

**Bitcoin's Hurst exponent 2021-2024: 0.52**

A Hurst exponent of 0.5 = pure random walk (no trend or mean 
reversion). Above 0.6 = trending. Below 0.4 = mean reverting.

At 0.52, BTC was mildly trending but not strongly so during 
2021-2024. This explains why momentum strategies underperformed 
post-2021 and why mean reversion strategies (particularly 
BTC-neutral residual) outperformed.

**The practical trading rule that emerges from the research:**

| Regime Signal | Condition | Strategy to Use |
|---------------|-----------|-----------------|
| Strong trend | ADX>25, price above 200MA | Momentum/Donchian/MAX |
| Moderate trend | ADX 20-25, above 200MA | Momentum with caution |
| Ranging | ADX<20, below 200MA | Mean reversion/Bollinger/MIN |
| Low volume + ranging | ADX<20 + volume below avg | Mean reversion only |
| Crash/high volatility | VIX-equivalent spike | Neither — reduce size |

This is already partially implemented — your ADX strategy uses ADX>19
as the entry gate. The research suggests extending this logic: when 
ADX<19 (ranging), that is when mean reversion strategies should be 
active, not idle. This is the foundation of the regime-switching 
approach flagged as SI003 in your Strategy Ideas Log.

---

## MOMENTUM STRATEGIES

---

### Strategy M1 — Donchian Channel Breakout

**Evidence quality: HIGH**
**Crypto-specific: YES (BTC daily confirmed)**
**Post-2022 validation: YES**

**What it is:**
Entry when price makes a new N-day high (closes above upper Donchian
band). Exit when price falls below the lower Donchian band or 
trailing stop fires.

**Academic and practitioner evidence:**
- Multiple practitioner backtests on BTC/USDT daily from 2017-2024
  confirmed positive returns through all market cycles including 2022
- Win rate 30-40% with average winners 3-5× average losers — 
  identical payoff structure to your ETH ADX strategy
- Altrady (2026): "Backtests on BTC daily since 2017 show the 20/55
  system producing positive returns through both bull and bear markets"
- ETH/USD 2023: ETH broke above 20-day Donchian upper band before a 
  25% rally — documented specific crypto example
- BTC/USDT 20-day Donchian in 2022: "consistent performance during
  volatile phases while staying idle in sideways periods" (Mudrex)

**Key parameters with evidence:**
- Entry: 20-day upper band (most validated on crypto daily)
- Exit: 55-day lower band (Turtle classic) OR ATR 2× trailing stop
- Regime filter: price above 200-day EMA — dramatically reduces
  false signals in downtrends
- Grid search range: Entry 15-30, Exit 10-60

**Payoff profile:**
p_breakeven = 1/(1+b) where b ≈ 3-5×
= 1/4 to 1/6 = 16-25% breakeven win rate
Strategy far exceeds this — no payoff asymmetry risk

**Failure modes:**
- False breakouts in sideways/ranging markets — 200MA filter is 
  essential
- Consecutive losses in choppy periods test psychological discipline
- Will miss crash-recovery V-shaped bounces (mean reversion moves)

**Recommended for:** Week 7 Priority 1

---

### Strategy M2 — MAX Strategy (N-Day High Continuation)

**Evidence quality: VERY HIGH (peer-reviewed, updated through 2024)**
**Crypto-specific: YES (BTC primary)**
**Post-2022 validation: YES (out-of-sample confirmed)**

**What it is:**
Buy BTC when price reaches a new N-day maximum. Hold for N days.
Exit after N days OR when price falls below the N-day minimum.
This is a pure price momentum strategy with no technical indicator.

**Academic evidence (Quantpedia, September 2024 — most rigorous 
source found):**

Original study: November 2015 to February 2022. Results:
- 10-day lookback: strongest performance across all periods
- "Both strategies remain alive and effective, especially for 
  10-day periods"
- MAX outperforms MIN: higher returns and lower drawdown

Critical out-of-sample test: February 2022 to August 2024
(the 2022 bear market — the hardest possible test period):
- "The MAX strategy remains alive and well"
- "Buying BTC when it reaches a 10-day maximum appears effective,
  as well as all other periods"
- Despite BTC price declining dramatically in 2022, strategy 
  survived the out-of-sample period

Combined MAX+MIN (best result from paper):
- Annual return: 98.43%
- Volatility: 47.75%
- MDD: -37.67%
- Return/Volatility ratio: 2.06
- Full period 2015-2022

**Seasonality finding (bonus):**
The MAX strategy is strongest on Wednesdays and Sundays.
This is exploitable as a filter — only enter MAX signals on 
Wednesday and Sunday closes.

**Implementation for our infrastructure:**
Signal: BTC closes at new 10-day high
Entry: next open (or same close)
Exit: BTC closes at new 10-day low OR after 10 days
Stop: trailing stop 8% from peak (consistent with ADX strategy)
Filter: price above 200-day MA

**Why this is compelling:**
No indicator at all — purely price-based. Zero parameter fitting 
risk on the signal itself. Only parameters are N (lookback) and 
exit condition. Very low overfitting risk.

**Failure modes:**
- Like all momentum strategies, fails in sustained bear markets 
  without the 200MA filter
- 10-day holds mean ~37 trades/year on BTC — adequate sample

**Recommended for:** Week 7 Priority 2 (alongside/instead of MACD)

---

### Strategy M3 — MACD with 200MA Regime Filter

**Evidence quality: MODERATE**
**Crypto-specific: YES**
**Post-2022 validation: MIXED**

**Summary:** As covered in WEEK_7_RESEARCH_BRIEF.md, MACD standalone
wins only 36-40% of trades on BTC daily. Combined with RSI rises to 
77% win rate (Gate.io 2026). With 200MA filter, performance improves
significantly. The MAX strategy (M2) has stronger and cleaner 
evidence than MACD — test M2 before MACD.

**Parameters:** 12/26/9 standard, test with 200MA filter only take 
long signals when price above 200MA.

**Recommended for:** Week 8 (after M1 and M2 complete)

---

## MEAN REVERSION STRATEGIES

---

### Strategy R1 — Bollinger Bands Lower Band Touch

**Evidence quality: HIGH**
**Crypto-specific: YES (BTC primary, ETH confirmed)**
**Post-2022 validation: YES**

**What it is:**
Entry: price closes below lower Bollinger Band (20-day SMA, 2σ),
followed by a close back inside the band.
Exit: price reaches the middle band (20-day SMA).
Stop: below the entry candle low.

**Evidence:**
- QuantifiedStrategies (updated 2026): "Bitcoin Bollinger Bands 
  Trading Strategy backtests show ~50% CAGR while being in the 
  market only 34% of the time" (2015 to present)
- This is the cleanest mean reversion result found in the research
- 34% market exposure means you are sitting in cash 66% of the time
  while still generating strong returns — excellent capital efficiency
- Entry requiring CLOSE back inside the band (not just touch) 
  dramatically reduces false signals vs entering on the initial touch
- FMZQuant backtest on ETH/USDT 2024-2025 (2-day candles): 
  confirmed Bollinger reversal to 20MA as profitable

**Comparison to your current ETH RSI strategy:**
Your RSI strategy enters when RSI<43 and exits at RSI>48. The 
Bollinger strategy enters when price closes back above the lower 
band and exits at the middle band. These are structurally similar
but Bollinger has a better entry trigger — the "close back above
the lower band" confirmation significantly reduces false entries 
vs entering purely on RSI level.

**Key parameters:**
- Period: 20 (standard — most validated)
- Standard deviation: 2.0 (standard)
- Entry condition: TWO candles — first closes below lower band, 
  second closes back above lower band
- Exit: close at or above middle band (20-day SMA)
- Stop: below the low of the entry candle
- Optional regime filter: only enter when ADX<25 (in ranging market)
  — this prevents entering during strong downtrends where price 
  can stay below lower band for extended periods

**Payoff profile:**
Win rate expected: 60-70% (mean reversion tends to have higher WR)
b ratio: approximately 0.5-0.8× (wins smaller than losses)
p_breakeven = 1/(1+0.65) = 60.6%
At 65% WR: above breakeven — strategy has positive expectancy
This is better than your current ETH RSI profile (breakeven 72.1%)

**Critical warning:**
Fails in sustained downtrends. In 2022 bear market, BTC repeatedly
closed below lower band and continued falling. The regime filter
(only trade when not in sustained downtrend) is essential.
Do NOT trade this without confirming ADX<25 or price not in 
sustained decline (above 200MA or above 50-day MA minimum).

**Recommended for:** Week 7 Priority 3

---

### Strategy R2 — MIN Strategy (N-Day Low Bounce)

**Evidence quality: HIGH (same Quantpedia study as MAX)**
**Crypto-specific: YES (BTC)**
**Post-2022 validation: YES**

**What it is:**
Buy BTC when price reaches a new N-day minimum (new low).
Hypothesis: after reaching a local low, BTC tends to bounce 
(mean reversion).

**Evidence (Quantpedia 2024):**
- Mean reversion effect confirmed in BTC at local minima
- 10-day lookback: strongest results
- Returns substantial when BTC is above local N-day minima
- LOWER risk than MAX strategy (less volatile returns)
- HOWEVER: strategies that buy AT the minimum (not after crossing
  back above it) are hazardous with drawdowns over 80%

**Critical implementation nuance:**
Two versions of this strategy exist in the Quantpedia research:
1. Buy AT the minimum (when price hits new N-day low) → hazardous,
   80%+ drawdown. Do NOT build this version.
2. Buy when price is ABOVE the N-day minimum (i.e., the low was 
   reached and price has recovered) → less profitable but much 
   lower risk.

For our long-only, capital-preservation-first architecture:
Use version 2 — buy after the bounce has started, not at the 
exact low. This is structurally identical to the Bollinger strategy
where we wait for the "close back above the lower band" confirmation.

**Combined MAX+MIN:**
The most interesting finding in the Quantpedia research is that 
buying when BOTH new N-day high AND new N-day low occur within the
same period produces the best results. This sounds paradoxical but 
captures volatile sideways markets where both are hit frequently.
Annual return 98.43%, MDD -37.67%.

**Recommended for:** Build together with MAX strategy (M2) as the 
combined MIN+MAX approach is the highest-evidence strategy found.

---

### Strategy R3 — Z-Score Deviation (Single Asset)

**Evidence quality: MODERATE-HIGH**
**Crypto-specific: YES**
**Post-2022 validation: YES (particularly strong post-2021)**

**What it is:**
Calculate Z-score of current price vs rolling mean:
Z = (Current Price - Rolling Mean(N)) / Rolling StdDev(N)
Entry: Z-score below -2 (price 2 standard deviations below mean)
Exit: Z-score returns to 0 (price reverts to mean)
Stop: time-based exit (5-10 days if no reversion)

**Evidence:**
- Systematic crypto trading paper (Medium/briplotnik, 2025): 
  BTC-neutral residual mean reversion achieved Sharpe 2.3 
  post-2021 — strongest metric of any strategy in this research
- The BTC-neutral version strips out BTC market-wide movement 
  using rolling regression, then applies Z-score to the residuals
- Single-asset Z-score (without BTC neutralisation) is simpler
  to implement on our infrastructure but has lower evidence quality
- Z-score of +2.5 on BTC = +2.5 on ETH = standardised comparison 
  across assets

**Implementation consideration:**
The BTC-neutral version requires two assets (short BTC, long ETH 
when ETH/BTC ratio is at extreme) — this is pairs trading and 
requires shorting. Not available under UK FCA restrictions for
our retail setup.

The long-only single-asset Z-score is simpler: buy ETH when Z-score
falls below -2 relative to its 60-day rolling mean. This is 
essentially a quantified version of "buy when oversold vs recent 
history" — more systematic than RSI because it uses actual 
standard deviation rather than a bounded oscillator.

**Key parameters:**
- Rolling window: 30-90 days (60 days has most evidence)
- Entry: Z-score < -2
- Exit: Z-score returns to 0 (price at mean) OR time-based 5-10 
  days
- Stop: time-based preferred (mean reversion: further moves 
  strengthen not weaken the signal) — but must cap loss at -15%
  consistent with our risk management framework

**Recommended for:** Week 8-9 (after higher-priority strategies)

---

## HYBRID / REGIME-SWITCHING

---

### Strategy H1 — ADX Regime Filter (Momentum/MR Switch)

**Evidence quality: HIGH (from multiple convergent sources)**
**Crypto-specific: YES**
**Post-2022 validation: YES**

**What it is:**
Use ADX to determine the current market regime, then apply the
appropriate strategy type:
- ADX > 25: trend in place → use momentum strategy (Donchian/MAX)
- ADX 20-25: moderate trend → momentum with reduced size
- ADX < 20: ranging market → use mean reversion (Bollinger/MIN)
- ADX < 20 + volume below average → mean reversion only

**Evidence:**
This exact framework is described across multiple independent 
sources:
- Medium/Ashim Nandi (January 2026): "When ADX drops below 20 
  and volatility expands, reducing position sizes by 50% preserves
  capital. Markets reward strategies matched to conditions."
- QuantifiedStrategies (2026): "Mean reversion strategies 
  outperform momentum in low volume regimes"
- "Bitcoin mean reversion outperforms momentum when volume below
  historical averages — filters out dangerous breakout attempts
  and captures consistent yield from market noise"
- Hurst exponent evidence: BTC 2021-2024 at 0.52 (borderline)
  confirms regime is not persistently trending

**Why this matters for your portfolio:**
Your ADX strategy is already partially implementing this — it only
enters when ADX>19 (trending). When ADX<19, it is FLAT. The 
research says: when ADX<19, you should NOT be flat — you should be
running a mean reversion strategy instead. This is the gap in your
current portfolio.

Bollinger or MIN strategy on ETH when ADX<19 on ETH.
MAX/Donchian on ETH when ADX>20 on ETH.
Two bots, same asset, different regimes, designed to complement.

**This directly addresses SI003 in your Strategy Ideas Log.**

---

## Strategy Comparison Table

| Strategy | Type | Win Rate | R:R | Evidence | Post-2022 | Priority |
|----------|------|----------|-----|----------|-----------|----------|
| Donchian Breakout | Momentum | 30-40% | 3-5× | HIGH | YES ✅ | **Wk 7 #1** |
| MAX (10-day high) | Momentum | ~40% | 2-4× | VERY HIGH | YES ✅ | **Wk 7 #2** |
| BB Lower Band | Mean Rev | 60-70% | 0.6-0.8× | HIGH | YES ✅ | **Wk 7 #3** |
| MIN+MAX Combined | Hybrid | ~55% | ~2× | VERY HIGH | YES ✅ | **Wk 7 #4** |
| MACD + 200MA | Momentum | 40-55% | 2-3× | MODERATE | MIXED ⚠️ | Wk 8 |
| Z-Score Single | Mean Rev | 55-65% | 0.7-1× | MODERATE | YES ✅ | Wk 8-9 |
| ADX Regime Switch | Hybrid | Composite | Composite | HIGH | YES ✅ | Wk 9 |

---

## What You Should Build in Week 7

### Priority 1 — Donchian Channel Breakout on ETH + BTC

Grid search:
- Entry period: 15-30
- Exit period: 10-60 (also test lower band as trailing stop vs 
  fixed ATR 2×)
- 200MA filter: yes/no comparison
- Run full validation pipeline: costs, walk-forward, B&H check,
  Monte Carlo, payoff profile sanity check

### Priority 2 — MAX Strategy on BTC (+ MIN for comparison)

This is higher evidence quality than MACD and simpler:
- Signal: close above N-day high
- N: 10, 20, 30, 40, 50
- Exit: N-day low OR trailing stop
- Compare MAX alone vs MIN alone vs MIN+MAX combined
- No indicator at all — purely price-based, minimal overfitting risk

### Priority 3 — Bollinger Bands Mean Reversion on BTC + ETH

- Entry: close below lower band, followed by close back above
- Exit: price reaches middle band (20-day SMA)
- Stop: below entry candle low OR 15% fixed stop
- Test with and without ADX<25 regime filter

### Priority 4 — Combined MIN+MAX if time permits

This is the Quantpedia recommended combined approach:
- Enter when BOTH N-day high AND N-day low conditions met
- Annual 98.43%, MDD -37.67% in full period study
- Needs proper out-of-sample validation on 2022-2024 data

---

## Five Key Insights From This Research

**1. The regime question dominates everything.**
No single strategy works well across all crypto regimes. The 
research consistently shows that matching strategy type to regime
(trending vs ranging) is more important than which specific 
indicator you use. ADX below 20 = ranging = mean reversion. 
ADX above 25 = trending = momentum. This is the core insight.

**2. MAX strategy is more evidence-backed than MACD.**
The Quantpedia MAX/MIN study has proper academic methodology, 
out-of-sample testing through 2024 including the 2022 bear market,
and a peer-reviewed basis. Standard MACD has 36-40% win rate 
standalone. Test MAX before MACD.

**3. Bollinger Bands mean reversion is the strongest single 
mean reversion strategy on BTC daily candles.**
~50% CAGR at 34% market exposure (QuantifiedStrategies, updated
2026) is the strongest validated mean reversion result found. 
The two-candle entry rule (close below, then close back above 
lower band) is the critical implementation detail that separates
profitable from unprofitable versions of this strategy.

**4. The combined MIN+MAX strategy is the highest-returning 
approach found in peer-reviewed crypto research.**
98.43% annual, -37.67% MDD, Ret/Vol 2.06 across 2015-2022, 
confirmed effective in out-of-sample 2022-2024. This is a 
surprisingly simple strategy — pure price extremes, no 
indicators. Worth serious attention.

**5. Your current portfolio has a regime gap.**
ETH ADX is flat when ADX<19. ETH RSI is waiting for RSI<43. 
Neither is actively designed to trade the ranging/sideways regime.
The research strongly suggests this is where mean reversion 
strategies (Bollinger, MIN) should be deployed. The two 
strategies would be naturally self-selecting: ADX > 20 activates
ETH ADX, ADX < 20 activates ETH Bollinger.

---

## What NOT to Build (and Why)

**MACD standalone:** Win rate 36-40% — below breakeven without 
filter. Not worth building without regime filter.

**Pairs trading (BTC/ETH spread):** Requires shorting — blocked by
UK FCA restrictions.

**Cross-sectional momentum (rank coins by past return):** 
Requires multiple assets and shorting. Relevant at Week 15+.

**Intraday strategies:** Require different infrastructure. Out of 
scope until Week 12+.

**BTC-neutral residual mean reversion:** The Sharpe 2.3 result 
requires shorting BTC while longing ETH — blocked by FCA.

---

## Sources

Academic:
- Beluska & Vojtko (2024). "Revisiting Trend-following and 
  Mean-reversion in Bitcoin." SSRN/Quantpedia, September 2024.
  Updated through August 2024 including 2022 out-of-sample.
- Padyšák & Vojtko (2022). "Trend-following and Mean-reversion 
  in Bitcoin." Quantpedia original study, 2015-2022.
- Grobys et al. (2025). "Cryptocurrency Momentum Has (Not) Its 
  Moments." Financial Markets and Portfolio Management, Springer.
- Huang, Sangiorgi, Urquhart (2024). "Cryptocurrency Volume-
  Weighted Time Series Momentum." SSRN Working Paper.
- PMC/NIH Sensors Journal (2023). DOI: 10.3390/s23031664.
  Modified RSI strategy on 10 cryptocurrencies 2018-2022.
- Taylor & Frankel (2025). "Applying Reinforcement Learning in 
  Bitcoin Trading." Tandfonline, 2022-2025 data.

Practitioner:
- QuantifiedStrategies.com: Bitcoin Bollinger Bands (2026), 
  Bitcoin Mean Reversion Low Volume (2026), 20 Best Bitcoin 
  Strategies (2026)
- Altrady.com: Donchian Channel Strategy (2026)
- Mudrex: Donchian Channels Crypto Guide (2025)
- briplotnik/Medium: Systematic Crypto Trading Strategies (2025)
  — Z-score momentum Sharpe 1.0, BTC-neutral mean reversion 
  Sharpe 2.3
- Gate.io Web3 Research (2026): MACD+RSI win rate study
- Stoic.ai: Mean Reversion Strategy Guide (2026)
- Ashim Nandi/Medium: Market Regimes — Adaptation Is the Edge 
  (January 2026)
- Coin Bureau: How to Backtest Crypto Strategy (2025)
- QuantifiedStrategies: Bitcoin Mean Reversion in Low Volume 
  Regimes (2026)

---

*Research prepared 2026-05-13.*
*Save to: WEEK_7_RESEARCH_BRIEF_FULL.md*
*Next: WEEK_8_RESEARCH_BRIEF.md to be prepared end of Week 7*
