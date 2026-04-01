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