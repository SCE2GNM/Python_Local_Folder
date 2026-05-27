# Learning Log
## DeFi Quant Engineer Curriculum
**Student:** Greg (Gmac)
**Started:** Week 1, February 2026
**Purpose:** Track concepts encountered, study priorities, and knowledge progress throughout the 24-week curriculum.

---

## How to use this log

This document has three sections:

**Concepts Encountered** — every meaningful concept introduced, with a plain English description and the week it appeared. This is your personal quant glossary.

**Study Backlog** — concepts you've been exposed to but need deeper independent study. Prioritised High / Medium / Low based on how directly they affect trading decisions.

**Concepts Mastered** — concepts you can explain clearly, apply correctly, and reason about independently. Moved here from the study backlog as you progress.

---

## Study Backlog

Items you need to study further. Tackle High priority items before increasing capital.

---

### SB001 — Kelly Criterion

**Priority:** High

**Introduced:** Week 4 Day 2

**What you've done with it:**
Used the Kelly formula to calculate optimal position sizing (12.41%) for the ADX strategy based on estimated win rate and reward:risk ratio.

**What you can explain:**
The output — that Kelly tells you what fraction of capital to bet per trade to maximise long-run growth. That Half-Kelly is safer than Full Kelly. That the formula depends on win rate and the reward:risk ratio.

**What needs deeper study:**

- The mathematical derivation of the Kelly formula from first principles (it comes from maximising the expected logarithm of wealth, not expected wealth itself — this distinction matters)
- Why log utility is the right objective for a trader (hint: it's related to the difference between arithmetic and geometric mean returns)
- The assumptions Kelly makes about bet independence — why correlated trades (e.g. two crypto positions during a market crash) violate Kelly's assumptions
- What happens mathematically when you use Full Kelly vs Half Kelly over many trades — simulate it
- How Kelly changes when win rate and avg win/loss are estimated rather than known precisely (parameter uncertainty)

**Suggested resources:**
- "Fortune's Formula" by William Poundstone (accessible, narrative-driven)
- Ed Thorp's original paper "The Kelly Criterion in Blackjack, Sports Betting and the Stock Market"
- Chapter on position sizing in "Quantitative Trading" by Ernest Chan

**Update log:**
- 2026-03-20: Added. Used in Week 4 Day 2 for position sizing calculation.

---

### SB002 — ADX Indicator (deeper mathematics)

**Priority:** Medium

**Introduced:** Week 1 (applied from Week 2 onwards)

**What you've done with it:**
Used ADX 20/10 as the primary signal for the ETH trading strategy. Optimised parameters via grid search. Validated across expanding and rolling windows. Confirmed Sharpe 0.869 and Sortino 0.816 out-of-sample.

**What you can explain:**
ADX measures trend strength on a scale of 0-100. Above 20 indicates a strong enough trend to trade. +DI > -DI indicates the trend is bullish. The strategy goes LONG when both conditions are met simultaneously.

**What needs deeper study:**

- How ADX is mathematically derived from the Directional Movement Index (DMI) — specifically how +DM, -DM, and True Range combine into +DI, -DI, and then ADX
- Why Wilder chose a 14-period default and what the theoretical basis for period selection is
- The difference between ADX as a trend strength measure vs momentum indicators (RSI, MACD) — why ADX is non-directional
- Why ADX lags price action and how this affects entry/exit timing in fast-moving markets
- How ADX behaves differently in crypto (24/7, higher volatility) vs traditional equity markets (where it was originally designed)

**Suggested resources:**
- J. Welles Wilder's original book "New Concepts in Technical Trading Systems" (1978) — the primary source
- "Technical Analysis of the Financial Markets" by John Murphy — Chapter on trend indicators
- Experiment: plot ADX alongside price for ETH 2020-2024 and manually identify where ADX signals matched and missed major trend changes

**Update log:**
- 2026-03-20: Added. Applied since Week 1, deeper mathematics not yet studied.

---

### SB003 — Sortino Ratio

**Priority:** Medium

**Introduced:** Week 4 Day 2

**What you've done with it:**
Added Sortino alongside Sharpe in the expanding vs rolling window comparison. Observed that Sortino is consistently below Sharpe for the ADX strategy (avg 0.816 vs 0.869 expanding, 0.775 vs 0.831 rolling).

**What you can explain:**
Sortino only penalises downside volatility, whereas Sharpe penalises all volatility. A strategy with large upside moves but small losses will look better on Sortino than Sharpe.

**What needs deeper study:**

- The mathematical formula in detail — specifically how the downside deviation is calculated and why the target return is typically set to zero
- Why Sortino being below Sharpe for this strategy confirms that downside volatility dominates — work through the maths manually
- When to use Sortino vs Sharpe as the primary metric — the academic debate around this
- How to set the Minimum Acceptable Return (MAR) in the Sortino formula — we used zero but this is a choice with consequences
- Calmar Ratio as an alternative — uses max drawdown instead of volatility, common in hedge fund reporting

**Suggested resources:**
- Frank Sortino's original paper "On the Use and Misuse of Downside Risk"
- Comparison of risk metrics in "Active Portfolio Management" by Grinold and Kahn

**Update log:**
- 2026-03-20: Added. Used in Week 4 Day 2 window comparison.

---

### SB004 — Walk-Forward Testing (Expanding vs Rolling Window)

**Priority:** Medium

**Introduced:** Week 2 (Expanding), Week 4 Day 2 (Rolling)

**What you've done with it:**
Run both expanding and rolling window walk-forward tests on ADX 20/10. Confirmed parameter stability — ADX 20/10 selected in 4/5 expanding windows and 3/5 rolling windows. Both methods confirmed robust.

**What you can explain:**
Walk-forward testing prevents overfitting by enforcing that parameters are always optimised on past data and tested on future data the optimiser never saw. Expanding window uses all available history. Rolling window uses a fixed recent window.

**What needs deeper study:**

- The mathematical relationship between in-sample and out-of-sample performance degradation — why 30% degradation is normal and what level would be a red flag
- Anchored walk-forward vs rolling walk-forward — when each is appropriate
- How to choose the right train/test split ratio (we used 2:1) — the theoretical basis for this
- Multiple testing bias — if you run enough parameter combinations, some will pass walk-forward by chance. How to calculate the probability of this and adjust significance thresholds accordingly
- The relationship between walk-forward results and live trading performance — why even good walk-forward results degrade further in live trading

**Suggested resources:**
- "Algorithmic Trading" by Ernest Chan — Chapter on walk-forward testing
- "Evidence-Based Technical Analysis" by David Aronson — rigorous statistical treatment

**Update log:**
- 2026-03-20: Added. Both methods applied in Week 4 Day 2.

---

### SB005 — Sharpe Ratio (deeper understanding)

**Priority:** Low

**Introduced:** Week 1

**What you've done with it:**
Used as primary performance metric throughout Weeks 1-4. Target Sharpe >= 0.85 for validation gate. Current strategy Sharpe 1.111 on full backtest, 0.869 average out-of-sample.

**What you can explain:**
Sharpe = (mean return - risk free rate) / standard deviation of returns, annualised. Higher is better. Above 1.0 is strong. Above 2.0 is exceptional.

**What needs deeper study:**

- Why we dropped the risk-free rate from our calculation (we used mean/std directly) — when this simplification is acceptable and when it matters
- The statistical significance of Sharpe ratios — a Sharpe of 0.9 over 193 trades is very different from a Sharpe of 0.9 over 10 trades. How to calculate confidence intervals around Sharpe estimates
- How Sharpe behaves with non-normal return distributions — crypto returns have fat tails and negative skew, which Sharpe was not designed for
- The difference between ex-ante Sharpe (expected) and ex-post Sharpe (realised) and why they diverge

**Suggested resources:**
- William Sharpe's original 1966 paper "Mutual Fund Performance"
- "The Statistics of Sharpe Ratios" by Andrew Lo (2002) — covers the statistical significance problem

**Update log:**
- 2026-03-20: Added. Used since Week 1, statistical foundations not yet studied.

---

---

### SB006 — Multi-parameter joint optimisation

**Priority:** Medium

**Introduced:** Week 4 Day 3

**What you understand:**
All strategy parameters are interdependent — ADX threshold, stop-loss %, position sizing, and Kelly fraction all affect each other's optimal values. Changing one requires re-evaluating all others. Identified as a gap in current curriculum approach where parameters have been optimised independently rather than jointly.

**What needs deeper study:**

- How to structure a multi-dimensional grid search across strategy, risk, and sizing parameters simultaneously
- Combinatorial Purged Cross-Validation (CPCV) — the standard technique for multi-parameter walk-forward validation
- Parameter stability analysis — identifying stable regions vs fragile single-point optima
- Out-of-sample holdout methodology — reserving final 1-2 years of data, never touched during optimisation
- Minimum description length principle — preferring simpler parameter sets when performance is similar
- How to calculate statistical significance of optimised results (probability of chance vs genuine edge)

**Curriculum target:** Weeks 6-8

**Update log:**
- 2026-03-21: Added. Identified from camera aperture/shutter/ISO analogy — all parameters interdependent.

---

### SB007 — Multi-indicator signal stacking (ADX + RSI + MACD etc.)

**Priority:** Medium

**Introduced:** Week 4 Day 3

**What you understand:**
Different indicators capture different dimensions of market behaviour. Combining independent indicators into a signal stack filters out low-confidence signals, typically reducing trade frequency but improving win rate. Each indicator must have a logical justification for inclusion — not just backtested improvement.

**What needs deeper study:**

- How to combine multiple indicators without curve-fitting — the logical vs empirical justification distinction
- Information overlap between indicators — ADX and MACD are not independent, both are trend-based. Understanding correlation between indicator signals
- How to weight multiple signals — equal weight vs confidence-weighted
- The relationship between number of indicators and overfitting risk
- Specific indicators to study: RSI (momentum), MACD (trend + momentum), Bollinger Bands (volatility), Volume (conviction)
- Academic literature on technical indicator combinations in crypto markets

**Curriculum target:** Weeks 9-12

**Update log:**
- 2026-03-21: Added. Natural extension of current single-indicator ADX strategy.

---

### SB008 — On-chain metrics and blockchain data analysis

**Priority:** Medium

**Introduced:** Week 4 Day 3 (Web3.py foundation built Week 2)

**What you understand:**
On-chain metrics measure actual blockchain activity rather than price behaviour. They provide information that doesn't exist for traditional assets. You have already connected Web3.py and read Uniswap pool prices in Week 2. The regime-switching capstone strategy (pre-curriculum) used on-chain informed allocation between HODL/LP/CASH positions.

**What needs deeper study:**

- Exchange netflow — measuring ETH moving onto/off exchanges as a buy/sell pressure indicator
- NVT ratio (Network Value to Transactions) — the crypto equivalent of a P/E ratio
- Active address growth — network adoption as a price driver
- Funding rates in perpetual futures — market sentiment and leverage positioning
- Stablecoin supply ratio — dry powder available to enter the market
- Whale wallet tracking — large holder accumulation/distribution patterns
- Data sources: Glassnode, Dune Analytics, Nansen, The Graph protocol
- How to combine on-chain regime signals with technical entry signals

**Curriculum target:** Weeks 13-16

**Update log:**
- 2026-03-21: Added. Genuine crypto-native advantage over traditional asset analysis.

---

### SB009 — Combined on-chain and technical indicator strategies

**Priority:** Low (depends on SB007 and SB008)

**Introduced:** Week 4 Day 3

**What you understand:**
Combining on-chain regime filters with technical entry signals creates a two-layer decision system. On-chain layer determines market regime (favourable/unfavourable). Technical layer determines entry/exit timing within favourable regimes. This is more sophisticated than either approach alone.

**What needs deeper study:**

- How to formally define and test regime filters using on-chain data
- Walk-forward validation methodology for combined systems
- Whether on-chain + technical outperforms either alone on a risk-adjusted basis
- Latency considerations — on-chain data has different update frequencies than price data
- The distinction between on-chain leading indicators vs lagging indicators

**Curriculum target:** Weeks 17-20

**Update log:**
- 2026-03-21: Added. Convergence of SB007 and SB008 — prerequisite for both.

---

### SB012 — Crypto asset scanning and pump/dump strategies

**Priority:** Medium

**Introduced:** Week 5 Day 7

**What you understand:**
Scanning multiple crypto assets simultaneously for momentum signals — catching the initial pump or trading the subsequent dump. Requires different infrastructure to single-asset daily strategies. Retail short-selling on Binance requires spot margin (UK) not futures.

**What needs deeper study:**
- Multi-asset scanner architecture (Binance API supports multi-symbol streaming)
- Algorithmic detection of initial pump move (volume spike + price breakout)
- Pump and dump dynamics — distinguishing genuine momentum from manipulation
- Short selling mechanics on Binance spot margin for UK retail
- DeFi alternatives: dYdX, GMX perpetuals (note: regulatory status for UK retail)
- Risk management for short positions (unlimited theoretical loss)

**Curriculum target:** Weeks 13-16

**Update log:**
- 2026-04-07: Added. Natural extension of momentum strategy work.

---

### SB013 — Adaptive and online learning strategies

**Priority:** Medium

**Introduced:** Week 5 Day 7

**What you understand:**
Strategies that periodically re-optimise their own parameters as new data arrives rather than using fixed parameters forever. Re-optimisation frequency depends on candle timeframe. Risk of over-adaptation to recent noise.

**What needs deeper study:**
- Online learning algorithms — incremental parameter updates without reprocessing full history
- Walk-forward automation — automatic rolling grid search and parameter updates
- Regime change detection as re-optimisation trigger
- Kalman filters and Bayesian updating for real-time parameter adaptation
- Reinforcement learning as alternative to grid search

**Curriculum target:** Weeks 17-20

**Update log:**
- 2026-04-07: Added. Natural evolution of fixed-parameter strategies.

---

### SB014 — Intraday timeframes for mean reversion strategies

**Priority:** Medium

**Introduced:** Week 5 Day 2

**What you understand:**
4-hour candles would generate ~6x more RSI/BB signals than daily candles, improving statistical reliability. Requires full parameter re-optimisation and different EC2 architecture (cron every 4 hours).

**What needs deeper study:**
- Full parameter re-optimisation of BB and RSI on 4-hour ETH candles
- EC2 architecture changes for sub-daily execution
- Transaction cost impact at higher frequency
- Whether the regime filter MA period needs to change timeframe

**Curriculum target:** Later intraday strategy curriculum weeks

**Update log:**
- 2026-04-07: Added. Deferred — not needed for daily candle strategy.

---

### SB015 — ATR (Average True Range)

**Priority:** Medium

**Introduced:** Week 5 Extension

**What you understand:**
ATR measures average daily price range over N periods using Wilder's exponential smoothing. Used as a volatility-adaptive trailing stop distance — the stop widens when the market is volatile and tightens when calm.

**What needs deeper study:**
- ATR formula: True Range = max(high-low, |high-prev_close|, |low-prev_close|). ATR = Wilder EMA of True Range
- ATR as position sizing tool (size position inversely to ATR for consistent risk per trade)
- ATR trailing stop vs percentage trailing stop — when does volatility adaptation help vs add noise?
- Wilder smoothing vs simple EMA for ATR calculation
- How ATR behaves differently in trending vs ranging markets
- Optimal ATR period and multiplier combinations for crypto daily candles

**Suggested resources:**
- J. Welles Wilder "New Concepts in Technical Trading Systems" (1978) — original ATR derivation
- Chapter on volatility stops in "Come Into My Trading Room" by Alexander Elder

**Curriculum target:** Week 6 Stage 1b (ATR trailing stop optimisation)

**Update log:**
- 2026-04-12: Added. Required for Week 6 ATR trailing stop grid search.

---

### SB016 — Trailing Stop Losses (percentage and ATR-based)

**Priority:** Medium

**Introduced:** Week 5 Extension

**What you understand:**
A trailing stop moves up as the trade profits, locking in gains. Percentage trailing: stop = peak_price × (1 - trail_pct). ATR trailing: stop = peak_price - (multiplier × ATR). For trend-following strategies, trailing stops outperform fixed stops by locking in profits during sustained trends.

**Week 6 Stage 1 results (ETH ADX):**
- Pct trail 8% (ADX 19/9): Calmar 2.559, Sortino 1.870, MaxDD −31.3%
- ATR 9/2.5x (ADX 19/9): Calmar 2.642, Sortino 1.385, MaxDD −27.8%
- Fixed 5% stop (corrected baseline): Calmar 2.013
- Both trailing stop types materially outperform fixed stop
- ATR recommended as primary (better Calmar, lower MaxDD); pct trail is simpler backup
- Implementation requires tracking peak_price_since_entry in bot_state.json

**What still needs deeper study:**
- Trailing stop interaction with leverage — does ATR trail provide sufficient margin protection at 2x?
- Live behaviour comparison: does ATR trail exit more or less cleanly than pct trail in real fills?
- Whether ATR period should be re-evaluated as new live data accumulates

**Curriculum target:** Partially complete — bot update and leverage analysis pending (Week 7)

**Update log:**
- 2026-05-02: Week 6 Stage 1 complete. ATR 9/2.5x confirmed best. Bot update pending (see A011 resolved, A015 open in ETH ADX risk register).
- 2026-04-12: Added. Required before leverage optimisation.

---

### SB017 — Binance Isolated Margin mechanics

**Priority:** High

**Introduced:** Week 5 Extension

**What you understand:**
Spot margin only (UK retail — FCA bans crypto derivatives). Interest charged hourly on borrowed amount only during open positions. Auto-Repay handles loan repayment automatically on close. Liquidation when equity/position < 5% maintenance margin. Intraday liquidation checked using daily low prices.

**Key confirmed facts:**
- Borrowing only occurs when a position is open — no interest when flat
- Auto-Repay enabled: loan repaid automatically from trade proceeds on close
- Own capital sits as collateral in margin wallet at all times (no interest on collateral)
- Safety buffer: minimum margin ratio should stay above 25% historically
- Preliminary analysis: ETH ADX at 2x leverage, 12.41% own fraction — total interest ~$30 over 108 trades (8.3 years) — nearly negligible

**What needs deeper study:**
- Current Binance USDT isolated margin borrow rate (check Margin Data page before deployment)
- How AUTO_BORROW_REPAY works in the Binance API — implement in production bot
- Margin call notification API — build bot logic to detect approaching 25% margin ratio
- Maximum isolated margin leverage available for ETHUSDT and BTCUSDT pairs
- How margin account equity is calculated when multiple positions are open simultaneously

**Curriculum target:** Week 6 — before any leveraged deployment

**Update log:**
- 2026-04-12: Added. Margin mechanics confirmed from Binance official documentation. Interest model in backtest confirmed correct.

---

### SB018 — Calmar Ratio as primary ranking metric

**Priority:** Medium

**Introduced:** Week 5 Extension

**What you understand:**
Calmar = Annual Return / |Max Drawdown|. Preferred over Sharpe for crypto strategies because it uses actual worst-case loss rather than statistical volatility, doesn't assume normal return distribution, and is directly relevant for leverage decisions where drawdown can trigger margin calls.

**Benchmarks:** Above 1.0 acceptable, above 2.0 strong, above 3.0 exceptional.

**Current strategy Calmar values (daily equity curve, no leverage):**
- ETH ADX 20/10: 1.645
- BTC SMA 125 (25% sizing): 4.464
- RSI Final ETH: 1.054
- BB v3 ETH: 0.768

**What needs deeper study:**
- Mathematical relationship between Calmar and Sharpe — when do they diverge and why?
- Calmar over different time windows — is a strategy's Calmar stable across sub-periods?
- Modified Calmar using average drawdown instead of maximum drawdown — more robust to outliers?
- How Calmar interacts with leverage — at what leverage does Calmar peak for each strategy?

**Curriculum target:** Ongoing — used as primary ranking metric throughout curriculum

**Update log:**
- 2026-04-12: Added. Used as primary ranking metric from Week 5 extension onwards.

---

### SB019 — Dual SMA crossover (golden cross / death cross)

**Priority:** Low

**Introduced:** Week 5 Extension

**What you understand:**
Fast/slow SMA crossover — signal fires when shorter MA crosses longer MA. Different from the price/SMA crossover used in BTC SMA 125. Golden cross = short MA crosses above long MA (bullish). Death cross = short MA crosses below long MA (bearish). Not yet tested on BTC or ETH.

**What needs deeper study:**
- Standard pairs to test: 50/200, 20/50, 10/30 on daily candles
- Compare dual SMA vs price/SMA on BTC — does adding a second MA improve or hurt performance?
- Why price/SMA might outperform dual SMA on BTC (faster signal, less lag)
- Golden cross / death cross reliability statistics on crypto vs equities

**Curriculum target:** Week 6 — optional comparison alongside BTC SMA validation

**Update log:**
- 2026-04-12: Added. Not yet tested. BTC SMA 125 (price/SMA) outperforms BTC ADX — whether dual SMA is even better remains untested.

---

### SB020 — Why SMA outperforms ADX on BTC

**Priority:** Medium

**Introduced:** Week 5 Extension

**What you understand:**
BTC has slower, longer-duration institutional trends vs ETH's faster reactive trends. A 125-day SMA filters noise below 4-month timeframe, capturing only major multi-month trends. ADX on 14-day period exits too early during BTC consolidations within larger trends. The 125-day SMA functions as both regime filter and entry signal simultaneously.

**What needs deeper study:**
- Quantify BTC vs ETH trend duration distribution — how much longer are BTC trends on average?
- Analyse ADX false exits on BTC: how many ADX exits were followed by continued trend?
- Test whether adding ADX as a secondary filter to BTC SMA improves results
- Why does a single price/SMA crossover work — what market microstructure explains it?

**Curriculum target:** Week 6 alongside BTC SMA validation

**Update log:**
- 2026-04-12: Added. Empirical finding from Week 5 extension — theoretical explanation needed.

---

### SB010 — Real-time WebSocket price feed (Binance → EC2)

**Priority:** Medium

**Introduced:** Week 5 Day 2

**What you understand:**
The current bot architecture fires once per day via cron at 00:05 UTC and is otherwise blind to price movements. A WebSocket connection would stream live price data continuously from Binance into EC2, enabling real-time position monitoring and dynamic sell triggers without waiting for the next cron cycle. Binance provides a WebSocket API designed exactly for this purpose.

**Why it was deferred:**
Not needed for a daily candle strategy. The ADX signal is calculated on daily closes — checking price every second adds infrastructure complexity without improving signal quality. The existing Binance STOP_LOSS_LIMIT order provides sufficient intraday protection for the current strategy.

**What needs deeper study:**

- Binance WebSocket API — how to maintain a persistent connection, handle reconnections, and process streaming price data in Python
- asyncio — Python's asynchronous programming library, required for WebSocket connections that run alongside other logic
- How to architect a bot that combines a daily signal engine (ADX calculation) with a real-time monitoring layer (intraday stop management)
- The infrastructure implications — a WebSocket bot runs continuously rather than as a cron job, requiring different EC2 sizing and monitoring
- When real-time monitoring adds genuine value vs when it introduces overtrading risk (e.g. reacting to noise on intraday moves)

**Curriculum target:** When moving to intraday strategies — later curriculum weeks

**Update log:**
- 2026-04-07: Added. Identified during Week 5 Day 2 discussion on gap risk and 24/7 crypto trading.

---

### SB012 — Crypto asset scanning and pump/dump strategies

**Priority:** Medium

**Introduced:** Week 5 Day 7

**What you understand:**
The idea of scanning multiple crypto assets simultaneously for momentum signals — either catching the initial pump move early, or trading the subsequent dump (short selling) if the initial move is missed. This requires a different infrastructure to the current single-asset daily strategy.

**What needs deeper study:**

- How to build a multi-asset scanner that monitors hundreds of crypto pairs simultaneously for momentum signals
- The mechanics of short selling crypto: Binance offers futures and margin trading for retail investors — research minimum capital requirements, funding rates on perpetual futures, and liquidation risk
- DeFi alternatives for shorting: dYdX, GMX, and Synthetix offer decentralised perpetual contracts — compare centralised vs decentralised short selling in terms of cost, risk, and accessibility
- How to detect the "initial move" algorithmically — volume spike + price breakout detection, order book imbalance
- Pump and dump dynamics: how to distinguish genuine momentum from coordinated manipulation — regulatory and ethical considerations
- Risk management for short positions: short selling has theoretically unlimited loss potential, requires different position sizing and stop-loss logic
- Data sources for scanning: Binance API supports multi-symbol streaming, CoinGecko and CoinMarketCap APIs for broader universe

**Curriculum target:** Weeks 13-16 (after on-chain metrics foundation built)

**Update log:**
- 2026-04-07: Added. Identified as natural extension of momentum strategy work into multi-asset and short-selling territory.

---

### SB013 — Adaptive and online learning strategies

**Priority:** Medium

**Introduced:** Week 5 Day 7

**What you understand:**
Current strategies use fixed parameters optimised once on historical data. Adaptive strategies periodically re-optimise their own parameters as new data arrives, without manual intervention. The re-optimisation frequency depends on the candle timeframe — daily strategies might re-optimise monthly, intraday strategies might re-optimise daily or even per-session.

**What needs deeper study:**

- Online learning algorithms — how to update model parameters incrementally as each new data point arrives, without reprocessing the full history
- Walk-forward automation — building a system that automatically re-runs the grid search on a rolling basis and updates deployed parameters if a better combination is found
- Regime detection as a trigger for re-optimisation — rather than re-optimising on a fixed schedule, re-optimise when a regime change is detected (e.g. market structure shift)
- The risk of over-adaptation — strategies that re-optimise too frequently will chase noise and overfit to recent data. Finding the right re-optimisation frequency is critical
- High-frequency trading (HFT) implications — at millisecond timeframes, parameter adaptation happens in real time using techniques like Kalman filters and Bayesian updating
- Reinforcement learning as an alternative to grid search — training an agent to discover optimal parameters through trial and error in a simulated environment

**Curriculum target:** Weeks 17-20 (advanced curriculum)

**Update log:**
- 2026-04-07: Added. Identified as the natural evolution of fixed-parameter strategies toward truly adaptive systems.

---

### SB014 — Intraday timeframes for mean reversion strategies

**Priority:** Medium

**Introduced:** Week 5 Day 2

**What you understand:**
Mean reversion strategies on daily candles generate very few signals — BB generates 3.3/year, RSI 3.9/year. Switching to 4-hour candles would generate approximately 6x more signals, improving statistical reliability dramatically. However this is not a simple parameter change — it requires full re-optimisation from scratch and a different bot architecture.

**Why it was deferred:**
The current bot architecture fires once daily via cron at 00:05 UTC. A 4-hour strategy requires the bot to run every 4 hours, changing the EC2 cron setup. All parameters (BB window, RSI period, MA filter, stop %) calibrated on daily candles would need complete re-optimisation on 4-hour data. Transaction costs compound 6x faster at shorter timeframes.

**What needs deeper study:**

- Full parameter re-optimisation of BB and RSI on 4-hour ETH candles — cannot transplant daily parameters
- EC2 architecture changes: cron job every 4 hours vs daily, state file management for multiple intraday runs
- Transaction cost impact at higher frequency — 0.15% round-trip at 6x frequency significantly erodes edge
- Whether the regime filter (MA) needs to change timeframe — a 120-bar MA on 4-hour candles is only 20 days, very different from the 120-day MA used on daily candles
- Liquidity and spread differences between daily and intraday candles on ETHUSDT

**Curriculum target:** When moving to intraday strategies — later curriculum weeks

**Update log:**
- 2026-04-07: Added. Identified as natural extension to improve statistical reliability of mean reversion strategies.







===

## Concepts Encountered

A complete glossary of every meaningful concept introduced during the curriculum. Plain English definitions — no jargon.

---

### Week 1

**Backtesting** — Running a trading strategy on historical data to see how it would have performed. Like replaying a football match to see if your tactics would have worked.

**Sharpe Ratio** — A measure of return per unit of risk. Calculated as average return divided by volatility of returns. Higher = better risk-adjusted performance.

**Sortino Ratio** — Like Sharpe but only penalises downside volatility (losing days). Ignores upside volatility. More appropriate for strategies with asymmetric return profiles.

**Drawdown** — The percentage decline from a portfolio's peak value to its lowest point before recovering. A 20% drawdown means you lost 20% from your best point before recovering.

**Maximum Drawdown (MDD)** — The worst drawdown over the entire backtest period. Measures the most painful loss an investor would have experienced.

**ADX (Average Directional Index)** — A technical indicator measuring trend strength on a scale of 0-100. Above 20 = strong trend. Does not indicate direction — only strength.

**+DI / -DI (Directional Indicators)** — Companion indicators to ADX. +DI measures bullish pressure, -DI measures bearish pressure. When +DI > -DI the trend is upward.

**Moving Average** — The average price over a rolling window of N days. Smooths out noise to reveal the underlying trend direction.

---

### Week 2

**Grid Search Optimisation** — Testing every combination of parameters systematically to find the best performing set. Like trying every key on a keyring to find the one that opens the lock.

**Overfitting** — When a strategy is optimised too specifically to historical data and fails on new data. Like memorising exam answers rather than understanding the subject.

**Walk-Forward Testing** — A validation method that enforces strict separation between training data (used to optimise) and test data (used to validate). Prevents overfitting.

**Expanding Window** — A walk-forward method where the training window grows each year, always starting from the same point in history.

**Rolling Window** — A walk-forward method where the training window stays a fixed size and shifts forward through time.

**Transaction Costs** — The real-world costs of executing trades — exchange fees, bid-ask spread, and slippage. Must be included in backtests for realistic results.

**Slippage** — The difference between the price you expected to trade at and the price you actually got. Caused by market impact and liquidity gaps.

**Calmar Ratio** — Annual return divided by maximum drawdown. Measures return per unit of worst-case loss. Common in hedge fund reporting.

**Web3.py** — A Python library for interacting with the Ethereum blockchain. Used to read on-chain data like Uniswap pool prices.

**Uniswap V3** — A decentralised exchange on Ethereum that uses concentrated liquidity pools. Liquidity providers earn fees but face impermanent loss risk.

---

### Week 3

**WebSocket** — A persistent two-way connection between your code and a server. Unlike a regular HTTP request (ask → answer → disconnect), a WebSocket stays open and streams data continuously.

**REST API** — A request-response interface for fetching data. You send a request, get a response, connection closes. Used for historical data and account queries.

**Candle (OHLCV)** — A single time period of price data containing: Open, High, Low, Close prices and Volume. The building block of all price charts.

**Bootstrap Pattern** — A technique for building up enough historical data before starting live calculations. We buffer candles until we have enough to calculate ADX reliably.

**State Machine** — A system that can be in one of a finite number of states (e.g. FLAT or LONG) and transitions between them based on defined rules. Our position tracker is a state machine.

**Systemd** — Linux's service manager. Runs processes in the background and automatically restarts them if they crash. Used to keep the trading bot and dashboard running 24/7 on EC2.

**Telegram Bot** — An automated messaging agent on Telegram. Used to send real-time trade alerts to your phone when signals fire.

**Streamlit** — A Python library for building interactive web dashboards. Used for the live trading dashboard deployed on EC2.

---

### Week 4

**Market Order** — An instruction to buy or sell immediately at whatever the current market price is. Guarantees execution but not price.

**Limit Order** — An instruction to buy or sell only at a specific price or better. Guarantees price but not execution.

**Stop-Loss Order** — An instruction to sell automatically if price falls below a specified level. Caps the maximum loss on a trade.

**LOT_SIZE Filter** — Binance's rule that order quantities must be in specific increments (e.g. multiples of 0.001 ETH). Orders that violate this are rejected.

**Testnet** — A sandboxed version of an exchange that uses fake money. Identical API behaviour to live trading but with no financial risk. Used for testing execution code.

**DRY_RUN Mode** — A safety flag in the trading bot. When True, all order logic runs but no orders are sent to the exchange. Like a fire drill — everything happens except the real consequence.

**Kelly Criterion** — A mathematical formula for calculating the optimal fraction of capital to bet per trade to maximise long-run account growth. Derived from maximising the expected logarithm of wealth.

**Half-Kelly** — Using 50% of the Kelly-recommended position size. Sacrifices some expected return for dramatically better protection against losing streaks. Standard practice in professional trading.

**Position Sizing** — The decision of how much capital to deploy on each trade. One of the most important and underappreciated aspects of trading system design.

**Compounding** — Reinvesting profits so that future returns are calculated on a growing base. $1,000 growing at 10%/year compounds to $2,594 after 10 years, not $2,000.

**Sortino Ratio** — A risk-adjusted return metric that only penalises downside volatility. More appropriate than Sharpe for asymmetric return distributions.

**Git** — Version control software that runs locally on your machine. Tracks every change to your code over time. Works completely offline.

**GitHub** — A cloud hosting service for git repositories. Backs up your code online and makes it accessible from anywhere.

**.gitignore** — A file that tells git which files to never track or upload. Used to prevent API keys and credentials from being pushed to GitHub.

**.env file** — A local file storing sensitive credentials (API keys, passwords). Never committed to git. Loaded into Python scripts using the dotenv library.

**Markdown (.md)** — A plain text format that renders as formatted documentation. Uses simple symbols (# for headings, ** for bold) to indicate formatting.

**Risk & Assumptions Register** — A living document tracking all known risks, assumptions, and open questions about the trading system. Should be reviewed before each capital increase.

---

### Week 5

**Stop-Loss Aware Backtest** — A backtest that explicitly checks whether the daily LOW price breached the stop level on each bar, before checking the ADX exit signal. More realistic than assuming you always hold until the ADX signal fires.

**Bar-by-Bar Simulation** — Iterating through historical data one candle at a time, maintaining position state explicitly. More accurate than vectorised backtesting because it correctly handles intraday stop triggers and trade sequencing.

**Gap Risk** — The risk that price jumps past your stop level between trading sessions (or between bot runs), causing your stop to fill at a worse price than intended. Reduced but not eliminated on 24/7 crypto exchanges when using a cron-based bot.

**Sequence Dependency** — The phenomenon where portfolio performance depends on the order trades occur, not just the distribution of outcomes. A strategy with the same trades in a different order can produce dramatically different results. Relevant when evaluating aggressive position sizing in backtests.

**Portfolio Simulator** — A tool that runs historical trades sequentially through different position sizing rules, tracking account balance after every trade. Used to compare compounding sizing strategies (Kelly %) vs fixed dollar sizing.

**Arithmetic vs Geometric Growth** — Fixed dollar sizing produces arithmetic growth (add the same amount each win). Percentage sizing produces geometric growth (each win grows the base, making future wins larger). Over many trades the difference is dramatic.

**Kelly Criterion — Week 5 Update** — Recalculated using true stop-loss data: win rate 34.3% (was 37.5%), avg loss -3.92% (was -5.37%), reward:risk ratio 6.13x (was 4.52x). New recommended Half-Kelly: 11.77%. Difference from Week 4 (12.41%) immaterial — no change to RiskManager required.

**Bollinger Bands** — A volatility-based indicator consisting of three lines: a middle band (N-day moving average), an upper band (middle + 2 standard deviations), and a lower band (middle − 2 standard deviations). The bands expand during high volatility and contract during low volatility. Mean reversion signal: buy when price closes below the lower band (statistically unusual distance from mean), exit when price recovers to the middle band. Key insight: work best in ranging markets, fail badly in trending/bear markets without a regime filter. Optimised parameters for ETH: window=15, std=2.0, stop=10%, 150MA regime filter. Profit factor 3.497, win rate 80.8%.

**RSI (Relative Strength Index)** — A momentum oscillator measuring the speed and magnitude of recent price changes on a scale of 0-100. Formula: RSI = 100 − (100 / (1 + RS)) where RS = average gain / average loss over N periods, calculated using Wilder's exponential smoothing (alpha = 1/period). RSI < 30 traditionally signals oversold; RSI > 70 signals overbought. Key difference from Bollinger Bands: BB measures WHERE price is relative to its average (location-based), RSI measures HOW FAST price moved to get there (momentum-based). They capture different dimensions of the same oversold condition. Optimised parameters for ETH: period=14, oversold<43, exit>48, stop=15%, 120MA regime filter. Profit factor 5.593, win rate 93.5%, 31 trades.

**Regime Filter (Moving Average)** — A long-term moving average used to define whether the broader market is in a bull or bear regime before taking mean reversion signals. Entry signals are only taken when price is above the MA (bull regime). This prevents buying into sustained downtrends — the "falling knife" problem. Key finding: 150MA worked better than 200MA for BB on ETH (less restrictive, more valid trades captured). 120MA worked best for RSI. The MA filter transformed BB from a losing strategy (profit factor 0.962) to a profitable one (3.497) by eliminating bear market entries.

**Parameter Stability Analysis** — A method for distinguishing genuine strategy edges from overfitting. Varies each parameter independently while holding others fixed at their best values, then measures what fraction of parameter values keep performance above a minimum threshold (profit factor > 2.0). Results interpreted as: 80-100% = stable plateau (robust edge), 50-79% = moderately stable, 0-49% = fragile spike (likely overfitting). Complemented by 2D heatmap grids showing profit factor across pairs of parameters simultaneously. Broad green regions = stable edge; isolated green cells = fragile spike.

**Signal Confluence (Indicator Stacking)** — Combining multiple independent indicators so that a trade is only taken when all indicators simultaneously agree. BB fires when price is unusually far below its average; RSI fires when it fell there unusually fast. When both agree, two independent pieces of evidence point to the same conclusion. The combined BB+RSI strategy achieved profit factor 6.353 vs 3.497 (BB alone) and 5.593 (RSI alone) — higher quality signals but fewer of them (17 trades vs 26/31 individually).

**Cross-Asset Validation** — Testing a strategy optimised on one asset using the same parameters on a completely different asset. If the strategy remains profitable, the edge is more likely genuine rather than specific to one asset's price history. Week 5 result: ADX, BB, and RSI all profitable on BTC using ETH-optimised parameters. Performance degraded (RSI: ETH 5.593 → BTC 2.450) but remained positive — the edge generalises, confirming it is not purely ETH-specific.

**Walk-Forward Validation (Mean Reversion)** — Applied to BB and RSI strategies using rolling test windows (2022-2023, 2023-2024, 2024-2026) with parameters frozen at full-sample optimised values. Both strategies profitable in all three windows. Important caveat: this is not a true walk-forward (parameters were not re-optimised per window) — it is out-of-period testing with fixed parameters. A true walk-forward requires independent re-optimisation per training window, which was impractical given only 3-4 signals per year.

**Profit Factor Calculation Bug** — When all trades in a window are winners (zero losing trades), gross_loss = 0 and profit factor = infinity. Using a near-zero denominator (1e-9) instead produces nonsensical large numbers (e.g. 68,861,154). Correct approach: return float('inf') or report "no losses" explicitly when gross_loss = 0. This bug appeared in the Week 5 Day 7 walk-forward validation and was fixed in the Bitcoin validation script.

---

### Week 5 Extension

**SMA Crossover (price vs single MA)** — Trading signal where entry fires when today's closing price crosses above the N-day simple moving average, and exit fires when price crosses back below. One moving average compared directly against price. Different from dual SMA crossover (fast/slow). BTC SMA 125 tested: entry when close > 125-day SMA, exit when close < 125-day SMA. Result: Calmar 3.506, profit factor 15.641 (25 trades — small sample), max drawdown -17.0%.

**Why SMA outperforms ADX on BTC** — BTC has slower, longer-duration institutional trends vs ETH's faster reactive trends. A 125-day SMA filters noise below 4-month timeframe — only major multi-month moves trigger signals. ADX on 14-day period is too sensitive, exiting BTC positions during normal consolidations within larger trends. The 125-day SMA functions simultaneously as regime filter and entry signal.

**Benchmark Comparison** — Comparing active strategies against passive alternatives (buy and hold, equal-weight basket) to determine if complexity is justified. Key finding: buy and hold ETH returned only 12.9%/yr over 2018-2026 despite ETH's occasional massive rallies — ADX at 67.4%/yr significantly outperforms. Equal-weight crypto basket (BTC, ETH, BNB, SOL, ADA rebalanced monthly) returned 43.4%/yr — better than single-asset hold due to diversification and rebalancing effect.

**Calmar Ratio** — Annual Return divided by absolute Max Drawdown. Primary ranking metric for leveraged strategy selection. Does not assume normal return distribution. Directly relevant when drawdown triggers margin calls. Above 1.0 acceptable, 2.0 strong, 3.0 exceptional. Stays approximately constant across leverage levels — leverage scales both return and drawdown proportionally.

**Per-trade vs Daily Equity Curve Returns** — Per-trade compounded returns chain trade returns sequentially with no idle time — overstates annual return by assuming capital is always deployed. Daily equity curve correctly models idle cash periods (ETH ADX is flat ~9 months/year) — gives honest annual return. Per-trade: ETH ADX 67.4%/yr. Daily equity curve: 9.0%/yr. Always use daily equity curve for strategy comparison and benchmarking.

**Sharpe Correction (per-trade annualisation bug)** — Previous Sharpe calculations used per-trade returns × sqrt(365), treating each trade as a 1-day return regardless of actual hold period. This massively inflated Sharpe (ADX: 4.695 wrong vs 0.817 correct). Fix: build daily equity curve, calculate daily returns, annualise with sqrt(365). Correct Sharpe values: ADX 0.817, BB 1.040, RSI 1.205.

**Trailing Stop Loss** — A stop-loss that moves in the direction of the trade as price improves, locking in profits. Percentage trailing: stop = highest_price_since_entry × (1 - trail_pct). ATR trailing: stop = highest_price_since_entry - (multiplier × ATR). For trend-following strategies, trailing stops lock in profits during strong trends and should outperform fixed stops. Two types to be tested in Week 6 on ETH ADX and BTC SMA.

**ATR (Average True Range)** — Volatility indicator measuring average daily price range. True Range = max(high-low, |high-prev_close|, |low-prev_close|). ATR = Wilder exponential moving average of True Range. Used as volatility-adaptive trailing stop distance — stop widens during volatile markets, tightens during calm. Created by J. Welles Wilder (same as ADX and RSI).

**Isolated Margin (Binance Spot)** — Each position has its own collateral pool. Borrowing occurs only when a position is open — no interest when flat. Interest charged hourly on borrowed amount. Auto-Repay handles automatic loan repayment when position closes. Liquidation when equity/position falls below 5% maintenance margin. UK retail restricted to spot margin (FCA bans crypto derivatives). Preliminary finding: ETH ADX interest costs are nearly negligible (~$30 total over 108 trades at 2x leverage) due to short average hold times.

**Leverage Grid Search** — Finding optimal leverage by testing multiple levels (1.0x-5.0x) and ranking by Calmar ratio after interest costs. Safety buffer: minimum historical margin ratio must stay above 25%. Intraday liquidation risk modelled using daily LOW prices. Stop-loss slippage 2% below intended stop, liquidation slippage 3% below liquidation price.

**Kelly Criterion and Leverage** — Kelly formula optimises fraction of own capital to deploy and assumes no borrowing costs. In a margin context, Kelly does not apply directly — the question becomes: what leverage multiplier maximises risk-adjusted return after borrowing costs? Leverage grid search replaces Kelly optimisation for margin strategies.

---

### Week 6

**Trailing Stop Confirmed Outperformance (Stage 1 result)** — Stage 1 optimisation on ETH ADX confirmed that trailing stops materially outperform the live fixed 5% stop. Best results with 0.15% round-trip costs: percentage trail 8% (ADX 19/9, Calmar 2.559, Sortino 1.870), ATR 9/2.5x (ADX 19/9, Calmar 2.642, Sortino 1.385). Both beat the corrected fixed-stop baseline (Calmar 2.013). ATR trail recommended as primary — slightly better Calmar and lower MaxDD (−27.8% vs −31.6%). Pct trail is close second and simpler to implement. The trailing stop improvement is genuine: trailing stops lock in profits during sustained trends and reduce average losing trade size by exiting later but from a higher peak.

**Composite Score (Multi-Metric Normalised Ranking)** — Method for ranking strategies across multiple competing objectives. Steps: (1) collect Calmar, Sortino, Annual%, MaxDD across grid; (2) apply min-max normalisation per metric to [0, 1]; (3) take equal-weight mean. MaxDD: all-negative, less negative = better = higher normalised value — no inversion needed if normalised correctly. Result is a single composite score [0, 1] where 1.0 = best on all metrics simultaneously. Primary use: comparing strategies within a grid search when no single metric dominates.

**Per-Trade MaxDD vs Daily Mark-to-Market MaxDD** — Two fundamentally different drawdown measures that are frequently confused. Per-trade MaxDD: peak-to-trough on the sequence of completed trade returns, using `np.cumprod(1 + rets)`. Does not see within-trade price swings — only captures drawdowns between consecutive trade exits. Daily MtM MaxDD: peak-to-trough on the full daily equity curve (portfolio marked to market every day using closing prices). Always worse than per-trade MaxDD because it captures intraday price swings while a position is open. Example: BTC SMA Candidate A — per-trade MaxDD −17.8%, daily MtM MaxDD −30.5%. For live trading, daily MtM MaxDD is what you experience watching your account. Both must be reported.

**Stability Thresholds: STABLE / MARGINAL / FRAGILE** — Classification of parameter stability from a composite score sweep. Method: vary each parameter independently, count what fraction of values produce composite ≥ 0.7. STABLE: >60% of values pass (broad plateau, robust edge). MARGINAL: 40–60% pass (some sensitivity, acceptable). FRAGILE: <40% pass (performance concentrated in a narrow range, likely overfitting). A MARGINAL result is not a disqualifier but requires explicit acknowledgement and ongoing monitoring. BTC SMA primary (SMA 135/25%): 50.5% MARGINAL.

**Parameter Boundary Overfitting** — When the best grid search result sits at the maximum or minimum edge of the tested parameter range, it signals the grid was too narrow — the true optimum likely lies outside it. Example: BTC SMA trail sweep showed Calmar continuing to improve at 25% → 27.5% → 30% (the boundary). This means the strategy may be implicitly optimised toward the widest feasible trail rather than a genuine structural peak. Fix: always extend the range until the performance curve clearly peaks and flattens before accepting a result. This check is now in the Live Trading Checklist.

**Return Concentration Risk** — When a disproportionate share of backtest returns originates from a single year or trade, the headline performance metric is misleading. BTC SMA: 76.2% of the full-period compounded return (+2664%, 2018–2026) came from 2021 alone. Ex-2021 annual return drops from 48.9% to ~29%. An investor evaluating on full-period metrics will systematically overestimate forward returns. Fix: always report both full-period and ex-outlier metrics. Set return expectations on the ex-outlier figure for planning purposes.

**Walk-Forward Identical Results with Fixed Parameters** — When running walk-forward validation with fixed (non-re-optimised) parameters, expanding and rolling window methods produce IDENTICAL test-period results. This is because the same strategy with the same parameters runs on the same test data regardless of how the training window is defined. The expanding/rolling distinction only matters when you re-optimise parameters in each training window — a more rigorous but computationally expensive approach. With fixed parameters, running "both methods" is a documentation exercise, not a genuine dual test. Low-frequency strategies (3–5 trades/year) make true walk-forward re-optimisation impractical.

**Cross-Period Trade** — A trade that enters during the training period of a walk-forward window but exits during the test period. These trades are legitimate (the strategy was live and generated the signal correctly), but they inflate test-period performance by carrying unrealised profit from before the test window began. Must be flagged explicitly in walk-forward reports. Example: Window 3 (2024) — one trade entered Oct 2023 (training), exited Jun 2024 (test), +128% gross. Without this cross-period trade, Window 3 would show net-negative results from the remaining 6 trades.

**Cross-Asset Validation Failure** — When a strategy optimised on one asset fails to generate acceptable performance on another asset using identical parameters. Failure is informative: it suggests the edge is asset-specific rather than arising from a universal market structure. BTC SMA 120/25% on ETH: Sortino 0.505 (vs 1.246 on BTC), Calmar 0.291 (vs 2.752), daily MtM MaxDD −67.7% (vs −30.5%), 8 whipsaw trades in 2022 (vs 2 on BTC). The ETH failure is explained by ETH's higher volatility generating more false crossovers — same SMA period that filters noise on BTC is insufficient on ETH. Cross-asset failure does not automatically mean the strategy is worthless on the original asset, but it raises the concern that the original asset may change its own characteristics over time.

**NO-GO Decision with Documented Rationale** — The formal end-point of a validation pipeline. A NO-GO means "do not deploy capital to this strategy at this time," not "this strategy is permanently discarded." The NO-GO must be accompanied by: (1) the specific criterion that failed, (2) the evidence, (3) the fallback plan. BTC SMA Stage 2e: ETH cross-asset failure → NO-GO → fallback to BTC ADX 19/14 (SI001). A documented NO-GO is a risk management success, not a failure — it prevented capital from being deployed to a strategy with insufficient validation.

**Per-Strategy Risk Register** — A living document tracking each known risk for a specific strategy, with ID, category, status, priority, description, impact, and fix/rationale. Separate from the master assumptions register. Required before any deployment decision. Items are HIGH (must resolve before deployment), MEDIUM (resolve or formally accept with rationale), or LOW (monitor). Open items remain open until either resolved or superseded. The register is version-controlled alongside the code.

**Leverage as a Strategy Multiplier** — When leverage is available, strategy selection should not be based solely on 1× performance. A strategy with lower raw return but lower drawdown and higher Sortino may support higher safe leverage, producing better final levered returns than a higher-raw-return strategy constrained to lower leverage by its drawdown profile. Example: Strategy A at 60% annual, −40% MaxDD, optimal leverage 1.5× = 90% effective return. Strategy B at 40% annual, −15% MaxDD, optimal leverage 3.0× = 120% effective return. Strategy B wins despite lower raw performance. Implication: Sortino and MaxDD are leverage multipliers — in a leveraged portfolio, maximising Sortino subject to a return floor is a better objective than maximising raw return. Joint optimisation of strategy parameters and leverage simultaneously is the theoretically correct approach. Sequential optimisation (strategy first, leverage second) may miss the global optimum.

**Portfolio Capital Allocation Philosophy** — Fixed percentage allocation preserves diversification but does not reward edge. Performance-weighted allocation rewards edge but introduces noise-chasing risk at low trade counts. The correct approach is tiered: base allocation (fixed, ensures diversification) plus performance pool (Sortino + annual return% weighted, 50/50 equal weight, requires 20+ live trades per strategy before influencing allocation). Confidence-based initial allocation should factor in: backtest sample size (primary — 103 trades >> 31 trades in reliability), stability result (STABLE/MARGINAL/FRAGILE), walk-forward consistency, B&H multiple, and live trade count accumulating over time. Regime self-selection partially solves the performance-weighting concern — strategies that do not signal in adverse regimes sit in cash automatically, so idle capital is naturally available for the strategy suited to the current regime. Dynamic opportunistic allocation (idle capital flows to whichever strategy has an active signal, reducing back to equal shares when multiple strategies signal simultaneously) is theoretically sound but practically complex — forced partial exits override individual strategy logic and create backtesting challenges. Deferred to Week 9+. Sortino is the correct performance metric for allocation decisions — Sharpe penalises upside volatility equally with downside. Performance pool formula: 0.5 × normalised Sortino + 0.5 × normalised annual return%.

**Monte Carlo Simulation** — A technique for understanding the range of possible outcomes from a strategy by running it thousands of times with randomly drawn results from the known probability distribution (win rate, avg win, avg loss). Rather than one single backtest path, Monte Carlo produces a full distribution of outcomes — median case, worst 10%, best 10%, probability of negative year. Especially important for low-frequency strategies (4–12 trades/year) where a single bad trade represents 8–25% of annual sample and statistical noise is high. Key outputs: median annual return%, 10th percentile return% (bad luck scenario), probability of negative year, and how these change as win rate degrades from backtest to expected live levels. In the RSI strategy case, Monte Carlo at realistic 70% win rate showed negative Kelly expectation — the strategy's asymmetric payoff (avg win 5.79% vs avg loss 15%) requires above 72.1% win rate to have positive expectancy. Monte Carlo is the correct tool for stress-testing low-sample strategies before deployment.

**Kelly Criterion — Correct Implementation** — Kelly fraction f* represents the fraction of capital to RISK per trade (maximum possible loss), not the fraction to DEPLOY as position size. Correct position sizing formula: Position size = (f* × Capital) / Stop loss %. Example: f*=12.41%, Capital=$1,000, Stop=5% → Position size = $2,482 (use leverage or cap at available capital if unleveraged) → Maximum loss = $2,482 × 5% = $124.10 = 12.41% of capital. Previous implementation deployed 12.41% of capital as position size ($124), resulting in actual risk of only 0.62% per trade — 20× undersizing of the position. Fixed Week 6 Day 5. Implication for trailing stop update: when stop distance changes (e.g. fixed 5% → trail 8%), position size must be recalculated using the new stop %. At 8% trail: size = $124.10 / 0.08 = $1,551 → capped at available capital. Kelly with leverage: Kelly-optimal leverage = f* / stop_pct. For ETH ADX: 0.1241 / 0.08 = 1.55×. Buffer-constrained maximum is 1.9×. Since Kelly-optimal (1.55×) is below the safety maximum (1.9×), operating at Kelly-optimal is both growth-optimal and safe.

---

### Week 7

**Time-Series Momentum (TSMOM)** — A strategy framework, not a traditional indicator. Signal: buy if the asset's return over the past n months is positive, hold/flat if negative. Lookback typically 1–12 months. Academic evidence is strong: SSRN December 2024 paper found volume-weighted TSMOM on crypto generates 0.94%/day with annualised Sharpe 2.17. Springer 2023 conference confirmed positive results across multiple lookback windows. Erasmus University thesis found significant positive excess returns for 85% of long-only portfolios — but long-short portfolios showed no significant positive returns. Long-only is the relevant case (UK FCA, no shorting). Why not built yet: TSMOM is a portfolio-level, cross-sectional concept — it ranks multiple assets by past return and buys top performers. For a single-asset strategy on BTC or ETH, TSMOM reduces to a simple ROC zero-line or SMA crossover, already implicitly captured by our existing SMA and ADX strategies. Not worth building as a separate strategy at this stage. Revisit: Week 15+, when the portfolio spans enough assets for cross-sectional ranking to be meaningful. Introduced: Week 7 (WEEK_7_RESEARCH_BRIEF.md Phase 0 momentum research).

**Trailing Stop — Hourly Check with Minimum Improvement Threshold** — When managing a trailing stop via cron, checking every hour (rather than every 4–6 hours) better captures intraday highs during uptrends. Key guard: only cancel and replace the Binance stop order if the new calculated stop price is at least 0.25–0.5% higher than the current stop. This prevents unnecessary order churn and minimises the window where no stop exists on the exchange (the gap between cancel and replacement). Apply to all future bots from the start. Introduced: Week 7.

**Kelly Criterion — Corrected Understanding** — Kelly output is a risk fraction — the percentage of total capital you are willing to LOSE if the stop fires. It is NOT the fraction of capital to allocate to the trade. With Half-Kelly at 12.41% and an 8% trailing stop: dollar_risk = capital × 12.41% = $124.10; position_size = $124.10 / 8% = $1,551. The position deployed is larger than the risk amount because the stop sits 8% below entry, not at zero. Half-Kelly (rather than full Kelly) is appropriate because backtest win rate and R:R are estimates, not guarantees — Half-Kelly builds in a margin of safety for the gap between backtest and live performance. This corrects the Week 4–6 implementation error where 12.41% was applied as the position fraction rather than the risk fraction, causing 20× position undersizing ($124 deployed instead of $1,551). Introduced: Week 7.

**Power Law Distributions and Undefined Variance in Crypto Momentum Strategies** — Standard backtest metrics (Sharpe, Sortino, Kelly fraction, confidence intervals) all assume that return variance is finite and stable — meaning it converges to a reliable number as you collect more data. This assumption holds for normally distributed returns but breaks down for crypto momentum strategies.

Crypto returns follow a power law distribution (fat-tailed), described by an exponent α (alpha). The critical threshold is α = 3:
- α > 3: variance is finite and stable — standard statistics are reliable
- α between 2 and 3: variance is technically finite but extremely unstable — never truly converges
- α < 2: variance is literally mathematically infinite

Two independent 2025 papers (Grobys et al., Springer; Huang et al., SSRN) found that cryptocurrency momentum strategy returns have α < 3 — sitting in the unstable zone.

The plain English consequence: a 5-year backtest showing excellent momentum results (Sharpe 2.1, Sortino 1.8, Kelly 24%) is still statistically consistent with the strategy having negative long-run performance. The extreme event that would reveal this has simply not yet occurred in the sample. Your confidence interval looks like 40%–120% but the true interval might be −20% to 300%.

The wealth analogy: measuring average wealth in a room of 999 ordinary people gives £50,000. One billionaire enters and the average jumps to £1 billion. Add 999 more ordinary people and it crashes back. The average never converges. Crypto momentum returns behave like wealth, not height.

Why this does NOT apply equally to mean reversion: mean reversion strategies deliberately cut off the fat tail — they exit at the 20-day SMA or a fixed RSI level, harvesting small oscillations rather than riding extreme trends. Smaller wins, smaller losses, more stable variance. Bollinger and MIN strategies are relatively more trustworthy statistically than Donchian or MAX strategies.

Practical implications — applied to every future momentum strategy:
1. Monte Carlo is non-negotiable for all momentum strategies — not optional
2. True confidence intervals are wider than backtest numbers suggest — build in more margin of safety than the numbers imply
3. Out-of-sample testing through a bear market (2022) is especially valuable — it is direct evidence that at least one fat-tail event did not destroy the strategy. Strategies confirmed through 2022 (Donchian, MAX) are materially more trustworthy than those that have not been tested through a crash cycle
4. Kelly sizing for momentum strategies: use quarter-Kelly (not half-Kelly) for any momentum strategy not yet validated through a full crash cycle. Half-Kelly remains appropriate for strategies with confirmed 2022 out-of-sample performance
5. Never rely on a single backtest metric in isolation for a momentum strategy
Affected metrics: Sharpe ratio, Sortino ratio, Kelly fraction, and all standard confidence intervals assume normality or stable variance and are therefore unreliable as precise absolute measures for crypto momentum strategies. Monte Carlo simulation is the correct substitute because it uses the actual observed trade distribution. See METHODOLOGY_STANDARDS.md Fat-Tail Warning section for the full mitigation framework.

What this means for our current deployed strategies: ETH ADX trend-following is a momentum strategy. Its backtest metrics (Sharpe 1.425, Sortino 1.761) should be treated as upper bounds with wider true confidence intervals than they appear. The 2022 out-of-sample period (+35.1% when B&H was −68.3%) is the single most important validation data point we have — it is direct evidence of fat-tail survival.

Introduced: Week 7. Source: WEEK_7_RESEARCH_BRIEF_FULL.md, Grobys et al. (2025) Springer, Huang et al. (2024) SSRN.

**Hurst Exponent — Measuring Trend vs Mean Reversion Tendency** — A statistical measure of whether a time series tends to trend (H > 0.5), mean revert (H < 0.5), or move randomly (H = 0.5).

- H > 0.6: persistently trending — momentum strategies favoured
- H = 0.5: pure random walk — no exploitable structure
- H < 0.4: mean reverting — mean reversion strategies favoured

BTC Hurst exponent 2021–2024: 0.52 — barely above random walk. This explains why momentum strategies underperformed post-2021 and why mean reversion strategies outperformed during this period. The regime is not persistently trending.

Trading implication: Hurst exponent calculated on a rolling basis could serve as a regime filter — more sophisticated than using ADX alone. When rolling Hurst drops toward 0.5, reduce momentum exposure and increase mean reversion exposure. Revisit at Week 9+ when the portfolio becomes multi-strategy.

Introduced: Week 7. Source: WEEK_7_RESEARCH_BRIEF_FULL.md.

**Regime Detection Methods — Comparison** — Four methods exist for detecting whether a market is currently trending or ranging. The choice of method determines which strategy type to deploy.

*Method 1 — Rolling Hurst Exponent:* Theoretically strongest. Directly measures whether recent price history is trending (H > 0.6), random (H ≈ 0.5), or mean-reverting (H < 0.4). Calculated on a rolling window of 100–200 days. BTC Hurst exponent 2021–2024 was 0.52 — barely above random walk, explaining why momentum strategies underperformed that period. Limitation: computationally intensive, requires long lookback, can lag regime changes by weeks.

*Method 2 — ADX Threshold (already implemented):* ADX > 20 = trending regime, activate momentum strategy. ADX < 20 = ranging regime, activate mean reversion strategy. Simple, fast, already computed as part of the entry signal. Multi-source empirical support confirmed in WEEK_7_RESEARCH_BRIEF_FULL.md. Limitation: measures trend strength of recent moves, not underlying market structure — can give false signals during volatile ranging markets.

*Method 3 — Volume-Based Filter:* Mean reversion outperforms when volume is below its historical average. Momentum outperforms when volume is above average. Simple to implement — compare today's volume to its N-day moving average. Confirmed by QuantifiedStrategies (2026): "Bitcoin mean reversion outperforms momentum when volume below historical averages." Limitation: volume data quality varies on crypto; reliable on BTC/ETH, less so on altcoins.

*Method 4 — Bollinger Band Width:* Narrow bands (low volatility, price coiling) → breakout/trend move more likely → momentum. Wide bands (high volatility, price ranging) → mean reversion more likely. Already embedded in the Bollinger strategy itself. Limitation: reacts to recent volatility, not underlying market structure.

Current recommendation: ADX threshold is the right practical choice for current single-asset infrastructure — already computed, multi-source support, simple to implement in regime-switching architecture (SI003). The Hurst exponent becomes more valuable at Week 9+ when the portfolio spans multiple assets and a single portfolio-level regime indicator is needed rather than per-asset ADX.

Introduced: Week 7. Regime detection research and backtesting targeted for Week 8–9.

---

### Week 8

**Keltner Channel — Construction and Breakout Strategy Logic** — A volatility envelope indicator built around an EMA centre line. Upper band = EMA + multiplier × ATR; lower band = EMA − multiplier × ATR. Unlike Bollinger Bands (which use standard deviation), Keltner uses ATR, making the bands more stable in trending markets because ATR responds smoothly to true range rather than amplifying with price volatility spikes.

Breakout strategy logic: enter long when close crosses above the upper band (price leaving the envelope signals trend initiation). Use the EMA centre line as a dynamic trailing stop — exit when the LOW of any bar touches or crosses below the prior bar's EMA (intrabar trigger), or when the CLOSE drops below the current bar's EMA (EOD trigger). This gives trades room to breathe during the trend while cutting quickly once momentum fades. The EMA-as-stop is more responsive than a fixed stop and more adaptive than a percentage trailing stop.

Key design choice: EMA period and multiplier interact. Larger EMA period = smoother centre line, fewer but larger trades. Larger multiplier = wider envelope, fewer false breakouts but more slippage on stop. Best SOL result (ema=22, mult=1.5) balanced both, but regime break rendered the edge non-existent post-ATH (PF 0.055).

Introduced: Week 8. Source: sol_grid_search.py, keltner_walkforward.py, sol_regime_break.py.

**EMA Trailing Stop with Intrabar Trigger** — A two-tier exit check designed for daily candles where the intraday price path is unknown. The logic resolves the ambiguity of whether the low or the close triggered the stop first.

Tier 1 (intrabar): check if LOW ≤ prior bar's EMA. If yes, assume the EMA was hit intraday and fill at the prior EMA value (conservative, slightly better than close fill). Tier 2 (EOD): if the low did not trigger, check if CLOSE < current bar's EMA. If yes, exit at close.

Why tier 1 must be checked first: on a strong reversal day, both conditions can be simultaneously true (low hit the EMA and close is below current EMA). Checking the low first gives the correct execution price (EMA fill rather than close fill) and avoids attributing the loss to a different bar. Implemented in sol_regime_break.py and all Week 8 Keltner scripts.

Introduced: Week 8. Source: keltner_walkforward.py run_period() function.

**Multi-Strategy Discovery Grid Methodology** — A systematic approach to altcoin backtesting that tests all major indicator families before committing to deep optimisation of any single strategy. The grid runs ADX, Supertrend, Donchian Channel, Keltner Channel, and Bollinger Bands across their parameter space (~1,478 combos for SOL) with two hard filters: minimum 30 trades and MDD > −50%.

The purpose is to identify which strategy class has exploitable edge on a specific asset before investing time in walk-forward or regime analysis. If no indicator family produces ≥5 passing combinations, the asset is considered unsuitable for daily trend-following at current market structure. For SOL, only Keltner produced passing combos (21 of ~320 Keltner combinations passed). ADX produced 1 borderline combo; Supertrend, Donchian, and Bollinger produced 0.

B&H annual return is the benchmark — a strategy that passes both filters but underperforms B&H represents a sub-optimal allocation of capital and risk. This benchmark check eliminated the single ADX combo that technically passed (27.7%/yr vs B&H). The framework (sol_grid_search.py) is reusable across any asset.

Introduced: Week 8. Source: sol_grid_search.py, Week_8_SUMMARY.md.

**Exit Gap Analysis** — A verification step that checks whether the assumed fill price at exit matches what was actually achievable at market open on the exit bar. Required for any strategy that uses an indicator value (e.g., prior bar's EMA) as the exit fill price, since intraday execution can differ from the close of the prior bar.

Method: for each trade, compare the open price on the exit day against the assumed fill (e.g., prior EMA value). Flag gaps exceeding 3% as material. Adverse gap = open is worse than assumed fill (lower open for longs). Favourable gap = better than assumed fill.

SOL Keltner exit gap analysis (ema=22/mult=1.5): zero adverse gaps >3%. The EMA-based fill was validated as realistic. This is a pre-deployment checklist item per METHODOLOGY_STANDARDS.md and was the final validation step before the regime break analysis made deployment moot.

Introduced: Week 8. Source: keltner_gap_analysis.py.

**Walk-Forward Window Design for Short-History Assets** — Walk-forward analysis using 2-year in-sample (IS) and 6-month out-of-sample (OOS) windows, in both expanding (IS anchor fixed) and rolling (IS window moves forward with OOS) variants. For assets with limited history (SOL daily candles from Jan 2020 = ~5.5 years as of 2026), this produces only 6–7 windows, yielding ~2–4 trades per OOS window at a moderate trade frequency.

With 2–4 trades per OOS window, standard statistical significance tests are meaningless. The correct interpretation is directional: are OOS windows consistently profitable, or do results deteriorate systematically? A consistent pattern of OOS profitability across most windows (e.g., 5/7) is meaningful directional evidence even without statistical significance. Random or deteriorating OOS performance is decisive negative evidence.

SOL Keltner walk-forward result: last 2 OOS windows were negative, consistent with the regime break finding. The walk-forward confirmed the regime break from a different angle.

Design note: for assets where SOLUSDT data begins 2020, the first valid 2-year IS window ends Jan 2022, leaving only ~4 years of OOS-eligible data. This is the practical minimum for walk-forward to be directionally informative.

Introduced: Week 8. Source: keltner_walkforward.py, WEEK_8_SUMMARY.md.

**Regime Break Analysis Methodology** — A structured test to determine whether a strategy's underperformance in recent data represents a temporary drawdown or a permanent structural change in market behaviour. The test splits the trade record at one or more structural break dates and compares profit factor, win rate, and annual return across periods.

Decision rule: PF < 1.0 in the most recent period = regime change (not drawdown), strategy is non-viable. PF > 1.0 but degraded = potential drawdown, reopen condition applies. PF stable across all periods = no regime break detected.

Break dates should be chosen based on market structure events, not based on where the backtest performance changes — choosing dates after seeing the data creates look-ahead bias. Valid anchors: major regulatory events (BTC spot ETF approval Jan 2024), macro inflections (BTC halving), asset-specific structural changes (SOL ATH and subsequent bear market Aug 2025).

Applied in Week 8: ETH ADX split at May 2024 ETF approval — PF declined 2.947→1.689 (degraded, leverage deferred). SOL Keltner three-period split — PF 7.793→3.932→0.055 (decisive regime change, rejected).

Introduced: Week 8. Source: stage0_regime_break.py, sol_regime_break.py, RISK_REGISTER_ETH_ADX.md.

**Institutional Adoption Effect on Trend-Following** — When a crypto asset gains institutional adoption (ETF approval, large-cap index inclusion, major exchange listing), liquidity increases structurally. Higher liquidity means more participants entering and exiting at similar price levels, which causes trends to fade faster and mean reversion to become more pronounced.

Mechanism: pre-ETF, fewer participants meant momentum could persist for days or weeks without being arbitraged away. Post-ETF, institutional arbitrageurs and market makers absorb momentum moves more quickly, reducing trend duration and magnitude. This compresses win rate (fewer trades run to full target) and average win size, which together compress profit factor even if loss behaviour is unchanged.

Observed in Week 8 data: ETH ADX win rate fell 44.3%→35.1% post-ETF approval. SOL Keltner PF collapsed from 7.793 pre-ETF to 3.932 in the ETF-to-ATH period and 0.055 post-ATH. The pattern is consistent across both assets: institutional adoption is a structural headwind for daily trend-following strategies.

Practical implication: treat spot ETF approval or equivalent adoption event as an automatic trigger for regime break analysis on any trend-following strategy applied to that asset. Do not assume pre-event parameters remain valid.

Introduced: Week 8. Source: RISK_REGISTER_ETH_ADX.md (A022), sol_regime_break.py, WEEK_8_SUMMARY.md.

**Survivorship Bias in Altcoin Backtesting** — When backtesting any altcoin on historical data, only assets that are still trading today can be tested. Assets that failed (collapsed, delisted, lost 99%+ of value) are invisible to the backtest. This means any observed backtest result is conditional on survival — it answers "how would this strategy have performed on the coins that survived?" not "how would this strategy have performed across the full universe of coins you might have picked?"

For aggressive trend-following strategies applied to altcoins, survivorship bias inflates all metrics: the surviving assets by definition had enough price movement to generate the data needed to trigger entries and exits profitably. A failed coin would have generated continuous losing trades until it delisted. The true strategy expectancy across all possible altcoin selections is lower than any single backtested survivor suggests.

Mitigation: use quarter-Kelly (not half-Kelly) for any momentum strategy on an altcoin that has not been validated through a full crash cycle. The quarter-Kelly adjustment is a practical correction for the unknown survivorship bias premium embedded in the backtest result. BNB, AVAX, LINK, DOT, MATIC — all in the Week 9 backtest queue — have survived through 2022 and represent a lower survivorship bias risk tier than newer assets.

Introduced: Week 8. Source: METHODOLOGY_STANDARDS.md, WEEK_7_RESEARCH_BRIEF_FULL.md (fat-tail section).

**SOL Market Characteristics and ADX Failure** — Solana (SOLUSDT daily) exhibits violent intraday reversals as a structural characteristic. This stems from its high retail participation, frequent network incidents that caused sharp confidence-driven selloffs in 2022–2023, and its position as a high-beta asset relative to BTC. The result is a candle pattern with frequent large bodies followed by immediate reversals, without the sustained multi-day trend continuation that ADX-based entries require.

ADX failure mechanism on SOL: ADX entry fires on the third day of a directional move (ADX rising above 20, DI alignment confirmed). On BTC and ETH, this typically precedes several more trending days. On SOL, the reversal often arrives before the ADX-triggered trade can reach profit target, because the same high-beta characteristic that created the initial ADX signal also attracts mean-reverting counterparties. The result: SOL ADX produced 1 passing combination in 1,232 tested, all below B&H.

Keltner was more effective because EMA-as-stop exits more quickly than ADX's lagging exit, capturing the initial momentum burst before reversal. Even so, post-ATH regime change eliminated the Keltner edge entirely (PF 0.055). SOL daily trend-following rejected across all indicator families.

Introduced: Week 8. Source: sol_grid_search.py results, STRATEGY_ARCHIVE.md S007–S010.

**Telegram Monitoring Design — Exposing Full Signal State** (II-001, Week 9 carry-over) — A health-check Telegram message should expose the full decision logic, not just the outcome. For an ADX strategy: showing only "ADX=24 — SIGNAL" hides whether the direction check passed. Showing "ADX=24 (threshold 19) | +DI=18 | -DI=12 | ADX ✅ | Direction ✅" makes the entry condition independently verifiable from the message alone. Similarly, when FLAT, the reason matters: "ADX below threshold" vs "-DI > +DI (wrong direction)" are different failure modes that suggest different diagnoses. For an RSI strategy: always displaying both entry (<43) and exit (>48) thresholds in every message state means the operator never has to cross-reference the codebase to understand the current position's exit criteria.

Principle: a monitoring message is read under pressure, without context. Every number should be self-contained and its threshold visible alongside it.

Documentation drift corollary: stale comments (trading_executor.py said ADX >= 20, period 10 — live bot uses 19, period 9) create genuine confusion because they are read under the same pressure as monitoring messages. Keep docstrings updated whenever parameters change in production.

Introduced: Week 9. Source: day5_production_bot.py, rsi_production_bot.py, trading_executor.py.

---

## Concepts Mastered

Concepts you can explain clearly, apply correctly, and reason about independently.

*None formally assessed yet — will populate as curriculum progresses.*

---

## Review Schedule

| Milestone | Action |
|-----------|--------|
| End of each week | Review study backlog, update priorities |
| Before capital increase | Resolve all High priority study backlog items |
| Week 12 (midpoint) | Full curriculum review — assess what has moved to Mastered |
| Week 24 (end) | Final assessment against all concepts encountered |