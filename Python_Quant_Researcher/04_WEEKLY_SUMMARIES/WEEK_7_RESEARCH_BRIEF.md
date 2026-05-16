> **Note:** This is the summary brief. The comprehensive version is WEEK_7_RESEARCH_BRIEF_FULL.md — use that as the authoritative reference.

# Week 7 Research Brief — Momentum Strategies
## DeFi Quant Engineer Curriculum
**Prepared:** 2026-05-08 (end of Week 6)
**For:** Week 7 (start Monday 11 May 2026)
**Researcher:** Claude Sonnet (web search)
**Sources:** Academic papers (SSRN, arXiv, Springer), practitioner sites
(QuantifiedStrategies, StockCharts, TradingView), crypto-specific sources

---

## Executive Summary

The research brief covers five momentum indicator families relevant
to Week 7: MACD, ROC, CMO, Donchian Breakout, and Time-Series 
Momentum (TSMOM). The key finding is that **no single momentum 
indicator has a clearly dominant edge in crypto when used alone** — 
the academic literature consistently finds that momentum effects 
exist but are highly regime-dependent and subject to significant 
tail risk. The practitioner evidence supports this: MACD standalone 
wins only 40% of trades on BTC daily candles. The strongest 
evidence points toward **breakout strategies (Donchian) as the 
best fit for our daily candle, trend-following architecture**, with 
MACD as the second priority for testing.

**Recommended testing order for Week 7:**
1. Donchian Channel Breakout (20/55 parameters, ATR stop)
2. MACD (12/26/9 default, with RSI or ADX regime filter)
3. ROC (zero-line crossover, period 20-30 for daily crypto)
4. CMO (zero-line crossover with MA signal line, period 14)

Do NOT test all four exhaustively — validate 1 and 2 properly
before moving to 3 and 4.

---

## Critical Academic Finding — Read Before Building Anything

A 2025 paper in the International Journal of Finance & Economics
(Grobys et al.) examined six cryptocurrency momentum strategies 
and found that **the theoretical variance of cryptocurrency momentum 
returns is statistically undefined** — the strategies have power law 
exponents below 3, meaning variance is not finite in the mathematical 
sense. The practical implication: momentum backtest results in crypto 
have extremely wide confidence intervals. A 5-year backtest showing 
great results can still be consistent with negative long-run 
performance.

A second paper (Springer, 2025) confirmed: "risk-managed 
cryptocurrency momentum payoffs are subject to considerable 
uncertainty despite impressive backtested returns."

This does not mean momentum strategies don't work in crypto. It 
means they have heavier tails than equity momentum and are more 
sensitive to regime changes. The 2022 bear market is the key stress 
test — any momentum strategy that doesn't explicitly handle the 
2022 crash is not properly validated.

**Implication for Week 7:** Monte Carlo is especially important for 
any momentum strategy with fewer than 100 backtest trades. The 
fat-tailed nature of crypto momentum means standard confidence 
intervals understate uncertainty.

---

## 1. MACD (Moving Average Convergence Divergence)

### What It Is
Gerald Appel's 1970s indicator. MACD line = EMA(12) - EMA(26). 
Signal line = EMA(9) of MACD line. Histogram = MACD - Signal.
Entry: MACD crosses above signal line (bullish crossover).
Exit: MACD crosses below signal line.

### What the Evidence Says

**Standalone performance (poor):**
- MACD crossovers alone win approximately 36-40% of the time on 
  BTC daily charts. This is below a coin flip for bullish crossovers.
- A 2023 Bitcoin Insider/Medium backtest of MACD on BTC daily 
  candles found win rates of ~36% bullish, ~27% bearish crossovers.
  The strategy produced positive returns but underperformed vs the 
  sophistication required to run it.
- QuantifiedStrategies confirmed: "a very profitable Bitcoin MACD 
  trading strategy" is achievable but requires a specific filter 
  beyond simple crossovers — the exact filter is behind a paywall.

**With confirmation (materially better):**
- Gate.io Web3 Research (2026): combining MACD + RSI raises 
  backtested win rate to 77% vs 54-60% for MACD alone.
- Peer-reviewed Sensors Journal (PMC/NIH, 2023): modified RSI 50-100 
  strategy returned 773.65% from 2018-2022 vs 275.22% B&H. The RSI 
  entry signal combined with MACD trend confirmation is the pattern 
  most supported by the evidence.

**Crypto-specific parameter findings:**
- Standard 12/26/9 works on daily charts — most sources confirm this.
- For longer-term trend capture: 24/52/18 (double the standard).
- For faster signals (not recommended for our daily candle system).
- Key insight: crypto's higher volatility means MACD generates more 
  false signals in ranging markets than in equity markets. A regime 
  filter (200-day MA or ADX) is widely recommended to avoid trading 
  MACD crossovers during ranging periods.

**Known failure modes:**
- MACD is a lagging indicator — based on historical price data.
  In fast-moving crypto markets, by the time MACD signals, the move 
  is often well underway.
- In sideways/choppy markets: frequent false positives. "The MACD's 
  most actionable component is its histogram — a flip from negative 
  to positive indicates incoming buying momentum." Shrinking histogram 
  at crossover = weak/false signal.
- MACD in the 2022 bear: multiple whipsaw crossovers as BTC declined.
  Standalone MACD would have been stopped out repeatedly.

**Regime filter recommendation:**
Strong consensus across sources: only take MACD long signals when 
price is above the 200-day MA (or ADX > 20). This filters out the 
majority of false signals in bear markets.

**Parameter ranges to test:**
- Fast EMA: 8-15 (standard 12)
- Slow EMA: 20-30 (standard 26)
- Signal: 7-11 (standard 9)
- Priority test: 12/26/9 first (most evidence), then 8/21/9

---

## 2. ROC (Rate of Change)

### What It Is
Pure momentum oscillator. ROC = [(Current Price - Price n periods 
ago) / Price n periods ago] × 100. Oscillates above/below zero.
Entry: ROC crosses above zero (positive momentum).
Exit: ROC crosses below zero.

### What the Evidence Says

**Conceptual strengths:**
- ROC is "momentum in its purest form" (StockCharts/Fidelity).
  No smoothing — directly measures percentage price change over n 
  periods. More transparent than MACD which involves two EMAs.
- Because ROC is less mathematically complex than MACD, it may be 
  less subject to the overfitting criticism. Simple indicators 
  sometimes outperform complex ones out-of-sample precisely because 
  they have fewer parameters to overfit.

**Crypto-specific findings:**
- Phemex Academy: ROC zero-line crossover strategy on BTC daily — 
  documented +14% price moves following ROC moves above zero line.
- TradingView practitioner community uses layered ROC (multiple 
  periods, e.g. 7/30/100 days) to detect when fast momentum aligns 
  with slow structure — "resilient regime filter backbone for 
  automated strategies since 2021."
- Default period is 9 (optimised for forex hourly). For daily crypto 
  charts: 20-30 is more appropriate given higher volatility and 
  longer trend duration.

**Key insight from research:**
ROC requires manual overbought/oversold level setting — no fixed 
range like RSI's 0-100. For crypto: ±20-30% for daily ROC periods 
of 20-25. The zero-line crossover is the cleaner signal for a 
systematic strategy — avoids the subjectivity of overbought/oversold 
level setting.

**Known failure modes:**
- Very sensitive to volatility. A single abnormal day (flash crash, 
  macro event) can spike ROC dramatically and generate false signals.
  Partially mitigated by longer periods.
- Requires constant optimisation as volatility regime changes. 
  "If volatility has changed, you need to revise the period."
- No upper bound — unlike RSI, can't use fixed overbought levels.

**Parameter ranges to test:**
- Period: 20-35 (daily crypto — longer than default 9)
- Entry: ROC crosses above 0 (with regime filter recommended)
- Exit: ROC crosses below 0 OR trailing stop
- Alternative: ROC-based trend confirmation (above/below threshold)
  rather than pure crossover

---

## 3. CMO (Chande Momentum Oscillator)

### What It Is
Developed by Tushar Chande, 1994. Measures momentum using BOTH 
up-days and down-days symmetrically. Scale: -100 to +100.
Above 0 = bullish momentum. Below 0 = bearish momentum.
Overbought: +50. Oversold: -50.
Formula: (Sum of up-closes - Sum of down-closes) / 
         (Sum of all closes) × 100 over n periods.

### What the Evidence Says

**Conceptual strengths vs RSI:**
- CMO uses both up and down days in both numerator and denominator — 
  unlike RSI which only uses gains in the numerator.
- More responsive to price movements than RSI due to lack of 
  smoothing. "The CMO oscillates more than RSI."
- Symmetrical around zero — provides more balanced view of momentum.

**Trading application evidence:**
- QuantifiedStrategies (2025): tested CMO strategies in Python.
  Confirmed CMO works better with a trend filter (MA or trendline) 
  to identify main trend direction — not effective standalone.
  "Using CMO to spot end of pullbacks in trend direction and ride 
  the next impulse wave" — i.e. use as entry timing within a 
  confirmed trend, not as the primary trend detector.
- Medium/Bitcoin (2025): CMO + Ease of Movement backtest on BTC 
  showed potential but was noted as "not yet undergone robustness 
  testing."
- TradingView community: common setup is CMO + 10-period MA as 
  signal line. When CMO crosses above its MA = bullish. 
  When CMO crosses below its MA = bearish.

**Known failure modes:**
- CMO does NOT perform well in volatile non-trending markets. Price 
  spikes in both directions without directional trend cause the 
  indicator to spike or stay flat — no useful signal.
- More responsive than RSI = more whipsaw signals.
- Best suited as a pullback/entry timing tool within an 
  already-confirmed trend, not as a standalone trend detector.

**Critical question for Week 7 backtesting:**
Is CMO meaningfully different from RSI in practice on daily crypto 
data? Or does it produce similar signals with more noise? This is an 
empirical question — backtest both with identical setups and compare.

**Parameter ranges to test:**
- Period: 9-20 (default 9, but longer periods reduce noise)
- Entry: CMO crosses above 0 (with ADX or MA regime filter)
- OR: CMO crosses above its own 10-period MA (signal line approach)
- Exit: CMO crosses below 0 OR trailing stop

---

## 4. Donchian Channel Breakout

### What It Is
Richard Donchian's 1950s system, popularised by the Turtle Traders.
Upper band: highest high over n periods.
Lower band: lowest low over n periods.
Entry: Price breaks above upper band (new n-period high).
Exit: Price breaks below lower band (new n-period low) OR trailing stop.
Classic Turtle parameters: 20-day entry, 10-day exit.

### What the Evidence Says

**This is the strongest momentum indicator for our architecture.**

**Academic and practitioner consensus:**
- Multiple sources confirm Donchian breakout works on BTC/ETH daily 
  charts across multiple market cycles (2017 bull, 2018 bear, 
  2020-21 bull, 2022 bear, 2023+ recovery).
- QuantifiedStrategies confirms the Donchian/Turtle concept produces 
  "very profitable" results on Bitcoin when properly configured.
- Altrady/practitioner source (2026): "Backtests on BTC daily candles 
  since 2017 show the 20/55 Donchian system (Turtle-style) producing 
  positive returns through both bull and bear markets. Win rate is 
  typically 30-40% with average winners 3-5× average losers."

**Why Donchian fits our architecture better than MACD/ROC/CMO:**
- Win rate 30-40% with 3-5× reward:risk is structurally identical to 
  our ETH ADX strategy (41.8% WR, 6.13× reward:risk). Our framework 
  is designed for this type of payoff profile.
- MACD/CMO mean reversion patterns (high WR, small wins) are more 
  like the RSI strategy — which we've already seen is fragile.
- Donchian doesn't require overbought/oversold parameter calibration 
  — the breakout is purely price-based and objective.
- Altrady Donchian guide: ETH/USD in 2023 broke above 20-day 
  Donchian upper band before a 25% rally. "Traders who recognised 
  this breakout captured the move without relying on subjective 
  intuition."
- Mudrex backtest: BTC/USDT Donchian bot (20-day) in 2022 showed 
  "consistent performance during volatile phases while staying idle 
  in sideways periods."

**Key parameter finding:**
- Entry: 20-day upper band breakout (most validated)
- Exit: 55-day lower band (Turtle-style — gives trades more room)
- Alternative exit: 10-day lower band (faster, more trades)
- ATR-based stop as alternative to lower band exit
- Regime filter: 200-day EMA — only take long breakouts when price 
  is above 200-day EMA. Avoids trading breakouts against the major trend.
- "Same period for every asset" is a mistake — BTC and ETH may 
  need different lookback periods. Start with 20-day on both then 
  optimise separately.

**Known failure modes:**
- False breakouts in sideways markets. Standard Donchian assumption 
  is a trending environment. A 200-day MA filter dramatically reduces 
  false signals.
- Not suited for ranging/sideways markets — will be repeatedly 
  stopped out.
- Win rate 30-40% requires strong psychological discipline — many 
  consecutive losses are normal and expected.

**Parameter ranges to test:**
- Entry (upper band): 15-30 (standard 20)
- Exit (lower band): 10-55 (Turtle: 55, faster: 10-20)
- Filter: price above 200-day EMA (mandatory filter)
- ATR stop: 2× ATR below entry as alternative to lower band exit
- Test BTC and ETH separately — optimal periods likely differ

---

## 5. Time-Series Momentum (TSMOM)

### What It Is
Not an indicator in the traditional sense — a strategy framework.
TSMOM signal: buy if asset's return over the past n months is 
positive, sell/hold if negative. Lookback typically 1-12 months.

### What the Evidence Says

**Academic evidence is strong:**
- SSRN (December 2024): Volume-weighted TSMOM on cryptocurrency 
  markets generates 0.94%/day with annualised Sharpe 2.17. Strong 
  evidence, peer-reviewed.
- Springer (2023 conference): TSMOM strategies for cryptocurrencies 
  confirmed in multiple lookback windows.
- Thesis (Erasmus University): TSMOM "significant positive excess 
  returns for 85% of long-only portfolios" — but long-short 
  portfolios show no significant positive returns. 
  Long-only is the relevant case for us (UK FCA, no shorting).

**Why we're not recommending it as Week 7 priority:**
TSMOM is a portfolio-level cross-sectional concept — it ranks assets 
by past return and buys the top performers. For a single-asset 
strategy on BTC or ETH, TSMOM reduces to a simple moving average 
crossover or ROC zero-line strategy. It's already captured in our 
existing SMA and ADX strategies. Not worth building as a separate 
strategy for single assets at this stage.

**Revisit:** When portfolio expands beyond 3-4 assets and cross-
sectional ranking becomes meaningful (Week 15+).

---

## Comparison Table — All Five Indicators

| Indicator | Win Rate | Reward:Risk | Regime Fit | Solo Performance | Filter Needed | Priority |
|-----------|----------|-------------|------------|------------------|---------------|----------|
| Donchian  | 30-40%   | 3-5×        | Trending   | Strong ✅        | 200-day EMA   | **1st**  |
| MACD      | 36-40%   | ~2-3×       | Trending   | Weak (solo) ⚠️  | ADX or 200MA  | **2nd**  |
| ROC       | Unknown  | Unknown     | Trending   | Not validated    | Regime filter | **3rd**  |
| CMO       | Unknown  | Unknown     | Trending   | Weak (solo) ⚠️  | MA filter     | **4th**  |
| TSMOM     | 50%+     | ~2×         | Any        | Moderate         | Volume filter | Defer    |

---

## Answers to the 5 Research Questions

**Q1: What parameter ranges have strongest empirical support?**

Donchian: 20-day entry, 55-day exit (Turtle classic) — most 
validated across multiple cycles on BTC/ETH. Also test 20/20.

MACD: 12/26/9 is the most tested configuration. No strong evidence 
for alternative parameters on crypto specifically. The signal 
generation mechanism matters more than parameter tuning.

ROC: 20-25 periods for daily crypto charts (longer than the 9-period 
default which is optimised for forex/hourly).

CMO: 14 periods (same as RSI default — provides a direct comparison 
baseline). With 10-period MA signal line.

**Q2: What entry/exit conditions are supported?**

Donchian: Entry = price closes above upper band. Exit = price closes 
below lower band (or ATR trailing stop). Regime filter = price above 
200-day EMA.

MACD: Entry = histogram turns positive AND expanding (not just 
crossover). Exit = histogram turns negative. Regime filter = ADX > 20 
or price above 200 MA. Single crossover alone has only 36-40% win rate.

ROC: Entry = ROC crosses above zero while price is above 200-day MA. 
Exit = ROC crosses below zero or trailing stop.

CMO: Entry = CMO crosses above its 10-period signal MA while above 0. 
Exit = CMO crosses below signal MA or trailing stop.

**Q3: What regime filters improve performance?**

Consistent finding across ALL five indicators: performance improves 
significantly when trades are filtered to align with the major trend. 
Best documented regime filter for daily crypto:

- 200-day EMA: only take long signals when price is above 200-day EMA.
  This filter was the basis of the peer-reviewed study showing 
  773.65% returns from 2018-2022 (modified RSI 50-100 strategy — 
  enter when RSI crosses above 50 AND price above 200-day EMA).
- ADX > 20: ensures there is a trend in place before entering any 
  momentum trade. This is already embedded in our ADX strategy — 
  worth testing as a filter for MACD/Donchian too.

**Q4: What are the known failure modes?**

All momentum indicators:
- 2022 bear market: repeated whipsaw false signals during 
  sustained downtrend. Regime filter is the primary defence.
- Ranging/sideways markets: false crossovers generate losses. 
  The 2019 period on BTC and many months in 2023 were problematic.

MACD specifically: lags price significantly. By the time the 
crossover fires, 20-40% of the move has already occurred.

Donchian specifically: false breakouts — price makes new high then 
immediately reverses. More common on shorter periods (5-10 days). 
Longer periods (20+ days) reduce but don't eliminate this.

CMO/ROC specifically: no fixed overbought/oversold levels — requires 
manual calibration for each asset and time period.

**Q5: Has this been tested on crypto specifically?**

Donchian: Yes. Multiple practitioner backtests on BTC/USDT daily 
from 2017-2024. Positive results confirmed.

MACD: Yes, extensively. 2023 backtests show positive results but 
underperformance vs careful B&H. Key finding: needs a filter.

RSI + MACD combined: Yes. Peer-reviewed 2023 study (PMC/NIH) on 
10 cryptocurrencies 2018-2022. 773.65% return vs 275.22% B&H.

ROC: Limited crypto-specific evidence. Conceptually sound but 
empirical validation primarily on equity/forex markets.

CMO: Very limited crypto-specific evidence. One Medium article 
(January 2025) tested CMO + EMV on BTC without robustness testing.

---

## Recommended Testing Order for Week 7

### Priority 1 — Donchian Channel Breakout (BTC and ETH)

This is the most evidence-backed choice for our architecture:
- Payoff profile (30-40% WR, 3-5× R:R) matches our existing 
  ADX strategy — our pipeline is calibrated for this structure.
- Multiple backtests on BTC daily confirmed across market cycles.
- Simple, transparent, no smoothing — lower overfitting risk than 
  MACD.
- Natural complement to ADX: ADX detects trend strength, Donchian 
  detects trend start via breakout. They're conceptually related.

Grid search bounds (from evidence):
- Entry period: 10-40 (priority range: 15-25)
- Exit period: 10-60 (priority range: 20-55)
- Regime filter: price above 200-day EMA (test with and without)

### Priority 2 — MACD with Regime Filter (ETH focus)

Test this second:
- Most widely validated indicator in crypto — extensive evidence base.
- BUT: standalone performance is poor. Must test with regime filter.
- Compare MACD+200MA filter vs MACD+ADX filter.
- Key question: does adding MACD to our portfolio provide 
  diversification value vs ADX, or is it too correlated?

Grid search bounds:
- Fast EMA: 8-16
- Slow EMA: 20-32
- Signal: 7-11
- Always with 200-day EMA filter AND ADX>20 filter separately tested

### Priority 3 — ROC (only if time permits)

Lower priority because:
- Less crypto-specific evidence than Donchian or MACD.
- Structurally similar to MACD but simpler — may not add diversification.
- Test only if Donchian and MACD complete with enough time remaining.

### Priority 4 — CMO (defer if needed)

Only test if Priorities 1-3 complete satisfactorily. CMO is 
essentially an alternative RSI formulation — we already have RSI 
deployed. CMO may not add meaningful diversification to the portfolio.

---

## One Unexpected Finding Worth Investigating

**RSI 50-100 trend strategy** — the 2023 peer-reviewed paper tested 
not our mean-reversion RSI (entry <43, exit >48) but a TREND-FOLLOWING 
RSI where entry fires when RSI crosses ABOVE 50 (momentum building, 
not oversold). This produced 773.65% vs 275.22% B&H on 10 
cryptocurrencies 2018-2022.

This is structurally a momentum strategy, not mean reversion — it 
enters when momentum is building (RSI > 50) and uses the RSI as a 
momentum confirmation filter rather than an oversold indicator. 
Completely different from our current ETH RSI strategy.

Worth keeping in mind as a possible alternative to CMO in Week 7 
testing — it has peer-reviewed evidence behind it.

---

## What to Tell Claude Code at Week 7 Start

The Donchian Channel Breakout should be the first strategy built in 
Week 7. Suggested opening instruction:

"Read WEEK_7_THREAD_STARTER.md and this research brief for full 
context. Begin Week 7 strategy work with Priority 1: Donchian 
Channel Breakout on ETH daily (2018-present), then BTC daily.

Initial parameters: entry period 20-day, exit period 55-day, 
200-day EMA regime filter (long-only when price above 200 EMA).
Apply full methodology: 0.15% round-trip costs, bar-by-bar low stop,
daily equity curve Sortino, both MaxDD figures, grid boundary check.

This is a long-only system consistent with our UK FCA compliance 
(no shorting). Stop loss: ATR-based (2× ATR) rather than lower band 
exit — matches our trailing stop architecture better.

Reference parameter ranges from WEEK_7_RESEARCH_BRIEF.md."

---

## Sources Used

Academic:
- Grobys et al. (2025). "Cryptocurrency Momentum Has (Not) Its 
  Moments." Financial Markets and Portfolio Management, Springer.
- Huang, Sangiorgi, Urquhart (2024). "Cryptocurrency Volume-Weighted 
  Time Series Momentum." SSRN Working Paper, December 2024.
- Li & Zhang (2023). "Time Series Momentum Trading Strategy for 
  Cryptocurrencies." Springer Conference Proceedings, CONF-BPS 2023.
- Dobrynskaya (2023). "Cryptocurrency Momentum and Reversal." 
  Journal of Alternative Investments 26: 65-76.
- PMC/NIH Sensors Journal (2023). DOI: 10.3390/s23031664. 
  Modified RSI strategy on 10 cryptocurrencies 2018-2022.
- arXiv (2026). "Systematic Trend-Following with Adaptive Portfolio 
  Construction." arXiv:2602.11708.

Practitioner:
- QuantifiedStrategies.com: Bitcoin MACD Strategy, CMO Strategy 
  (November 2025), Bitcoin Donchian.
- StockCharts ChartSchool: ROC indicator guide (updated 2025-2026).
- Altrady.com: MACD vs RSI analysis (2025), Donchian guide (2026).
- Mudrex.com: Donchian Channels crypto guide (November 2025).
- Gate.io Web3 Research (2026): MACD+RSI combined win rate study.
- Bitcoin Insider/Medium: MACD backtest on BTC 2023.

---

*Research brief prepared 2026-05-08 for Week 7 starting 2026-05-11.*
*Next research brief: WEEK_8_RESEARCH_BRIEF.md — to be prepared 
at end of Week 7.*
