# Research Brief — Week 9 Phase 0
## DeFi Quant Engineer Curriculum
**Prepared:** 2026-05-27
**Scope:** Altcoin generalisation, post-ETF regime, asset-specific characteristics, low-frequency sizing
**Timeframe focus:** Daily candles (consistent with current infrastructure)
**Constraints:** Long-only (UK FCA), Binance Spot, ETH primary; LINK/DOT/POL/AVAX/BNB in backtest queue
**Sources:** SSRN, Springer, Cambridge Core, Frontiers, Bitget Academy, Binance announcements,
practitioner research

---

## Executive Summary

Week 9 grid work tests whether the validated ETH ADX parameters (threshold 19, period 9)
generalise to five mid-cap altcoins. The research confirms that cross-asset momentum in
crypto is real but structurally different from the time-series momentum used in our bots —
academic evidence supports cross-sectional momentum (rank assets by recent return, go long
the top) more strongly than direct parameter transfer across assets. Each of the five
target altcoins has a distinct price-driver profile that affects how ADX signals behave:
LINK and BNB are higher-quality candidates; DOT and POL carry structural concerns that
should inform interpretation of any results. The post-2024 regime question is the most
important unresolved issue: institutional ETF adoption has increased BTC/ETH correlation
with equities, and this may reduce the independence of altcoin signals that previously
drew on crypto-specific narrative momentum. On sizing, the research is unambiguous —
20 trades/year is far below the minimum sample for reliable Kelly inputs, and crypto's
fat tails compound the problem.

---

## OVERARCHING FINDING — Parameter Transfer Risk

The single most important finding for Week 9 grid work:

**Momentum parameters do not transfer cleanly across crypto assets at the same settings.**

Liu et al. (2022, Cambridge Core) confirmed momentum effects across 1,827 cryptocurrencies,
but the mechanism is *cross-sectional* (relative performance within a period), not
time-series (does the same asset trend at the same ADX threshold?). Directly applying
ETH's ADX 19 / period 9 to LINK or AVAX assumes equivalent trend persistence and 
volatility structure — this is unlikely. Evidence from LINK's 0.75-0.85 BTC correlation
and DOT's structural underperformance suggests baseline ADX readings may be systematically
different across assets. Run the grid search but interpret passing results with this in mind:
a result that only passes at ETH parameters may be spurious on altcoins; a result that
requires materially different parameters is an honest altcoin-specific finding, not a failure.

---

## TOPIC 1 — Altcoin Trend-Following: Does Momentum Generalise?

**Evidence quality: MODERATE (academic) / LOW (asset-specific practitioner)**

### Summary

Academic research confirms cross-sectional momentum across crypto assets is robust —
a portfolio that buys recent winners and sells recent losers earns 1.08% daily return
(Liu et al., 2022) and excess weekly returns of roughly 3%. However, this is not
the same as time-series trend-following (does a single altcoin trend at a fixed ADX
threshold?), and direct parameter transfer from BTC/ETH to mid-caps lacks peer-reviewed
validation. Momentum crashes are a documented risk, particularly for equal-weighted
large-cap portfolios (Springer 2025). Volatility management — scaling position size
by recent realised volatility — is the most evidence-backed mitigation for altcoin
momentum crashes. No academic paper directly tests ADX-based entries across LINK, DOT,
AVAX, BNB at fixed parameters.

### Key Findings

- **Cross-sectional momentum confirmed** across 1,827 coins (Liu et al., 2022,
  Cambridge Core JFQA): market, size, and momentum factors explain cross-section
  of crypto returns. ~3% weekly excess returns on long/short sorted portfolios.
- **Time-series momentum less robust** than cross-sectional on altcoins: the relative
  ranking approach is more stable than asking whether a single coin trends persistently.
- **Momentum crashes are significant** for large-cap equal-weighted portfolios.
  Grobys et al. (2025, Springer Financial Markets & Portfolio Management) confirm
  cryptocurrency momentum has undefined theoretical variance (power-law exponent below 3)
  — backtest confidence intervals are materially wider than they appear.
- **Volatility scaling mitigates crashes**: risk-managed momentum (scale by inverse
  realised volatility) substantially reduces crash severity with modest return
  reduction (ScienceDirect 2025).
- **Higher beta = higher noise on ADX signals**: mid-cap altcoins have amplified
  price swings relative to BTC/ETH. ADX may fire more frequently but with less
  trend persistence, producing more false signals at the same threshold.
- **Seasonality carryover**: if the Quantpedia BTC seasonality finding (MAX strongest
  on Wednesdays/Sundays) has any analogue in altcoins, it has not been documented.
  Do not apply the Wednesday/Sunday filter to altcoin signals.

### Implications for Week 9 Grid Work

- The grid search should test a wider ADX threshold range for altcoins than for ETH
  (suggest 15-25 vs ETH-validated 19) — do not assume the same threshold will pass.
- Flag any altcoin result that only passes at exactly ETH parameters (19/9) as
  potentially spurious coincidence rather than genuine generalisation.
- Apply the survivorship bias correction already established in METHODOLOGY_STANDARDS.md:
  altcoins have higher delisting risk than BTC/ETH, making long-period backtests
  especially vulnerable to survivorship bias.
- If an altcoin shows a higher passing threshold (e.g., ADX > 23), that is consistent
  with lower trend persistence and is a legitimate result, not a failure to generalise.
- Consider adding a volatility-scaling overlay to any passing altcoin strategy:
  reduce position size when 20-day ATR is above rolling average.

### Sources

- Liu, Tsyvinski & Wu (2022). "A Trend Factor for the Cross Section of Cryptocurrency
  Returns." *Journal of Financial and Quantitative Analysis*, Cambridge Core.
- Grobys et al. (2025). "Cryptocurrency Momentum Has (Not) Its Moments." *Financial
  Markets and Portfolio Management*, Springer.
- "Cryptocurrency Market Risk-Managed Momentum Strategies." ScienceDirect, 2025.
- "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market." AUT ACFR.

---

## TOPIC 2 — RSI Mean Reversion Post-2024: Has the Regime Changed?

**Evidence quality: MODERATE (practitioner data) / INCONCLUSIVE (academic)**

### Summary

The evidence on post-ETF mean reversion is mixed and context-dependent. RSI oversold
signals on ETH have produced dramatically different outcomes in the post-ETF period:
the April 2025 oversold reading preceded a 250% rally, but the December 2024 oversold
reading produced only a brief 20% bounce before ETH collapsed to $1,385. Institutional
ETF adoption has increased BTC's correlation with equities significantly, making crypto
less of an isolated market where internal RSI dynamics are the primary price driver.
The practical implication is not that RSI mean reversion is broken — it is that macro
context now needs to be checked alongside RSI readings, and that in a downward macro
regime, RSI oversold signals should be treated with more caution than in a crypto-
isolated bull market.

### Key Findings

- **Divergent post-ETF outcomes**: April 2025 RSI oversold (ETH below 30) → 250%
  rally. December 2024 RSI oversold (ETH near $3,430) → 20% bounce then collapse
  to $1,385. Same signal, opposite outcomes depending on macro regime.
- **Institutional correlation increase**: Bitcoin ETF approval (January 2024)
  accelerated institutional flows from $15B to $75B in Q1 2024 (Ainvest). ETH ETF
  approved July 2024. BTC's correlation with S&P 500 increased substantially
  post-approval.
- **Institutional flows shifted to strategic**: advisors now control 50% of
  institutional ETF holdings; hedge funds have reduced tactical exposure. Less
  momentum chasing = less reliable RSI mean reversion in the short term.
- **SMA120 regime filter already addresses this**: the current ETH RSI bot's SMA120
  filter blocks entries in downtrends — this is precisely the right architectural
  response to macro regime risk. The filter should remain.
- **ETH specifically**: RSI mean reversion on ETH still produced measurable bounces
  in 2024-2025 but with higher variance than the pre-ETF period. The strategy's
  expected value is lower in bear-trending macro environment.
- **RSI thresholds may need tightening**: the current entry at RSI<43 is not a
  deep oversold level (traditional oversold is <30). Post-ETF, more extreme oversold
  readings (RSI<35) may filter noise better but reduce trade frequency further.

### Implications for Week 9 Grid Work

- The existing SMA120 filter is the correct mitigation — do not remove it.
- If testing RSI on altcoins, the SMA120 regime filter becomes even more important:
  altcoins have more prolonged downtrends and RSI can stay "oversold" for weeks
  during sustained sell-offs.
- Monitor whether ETH RSI bot entry RSI<43 threshold is still producing edge in
  2025 live conditions — if no entries have occurred in recent months, consider
  whether the strategy is regime-gated (waiting for right conditions) or broken.
- Post-ETF RSI results: do not conclude the strategy has failed without checking
  whether the SMA120 filter would have blocked those trades anyway.

### Sources

- FXEmpire: "ETH Market Update: Can Ethereum Rebound After RSI Hits April 2025 Lows?"
  (2025).
- Ainvest: "Bitcoin ETF Inflows and Macroeconomic Momentum" (2025).
- BeInCrypto: "Bitcoin Adoption Soars: ETF Growth & Volatility Shifts in 2025."
- Stoic.ai: "Mean Reversion Trading: How I Profit from Crypto Market Overreactions."
- MEXC Learn: "Ethereum RSI Indicator: How to Read ETH Overbought and Oversold Levels."

---

## TOPIC 3 — Chainlink (LINK): Market Characteristics

**Evidence quality: MODERATE (practitioner) / LOW (strategy-specific)**

### Summary

LINK is a high-beta ETH proxy with significant independent narrative-driven price action
tied to DeFi oracle adoption. Its 0.75-0.85 correlation with BTC/ETH means 75-85% of
its price variance is driven by broader crypto sentiment, making it a reasonable
trend-following candidate when the overall market is trending. The independent 15-30%
outperformance episodes are triggered by DeFi/oracle-specific events (L2 activity
surges, major protocol integrations) and are difficult to capture with a daily ADX
strategy. During market stress, LINK amplifies BTC/ETH drawdowns, meaning the ADX
trailing stop and entry threshold need to account for wider intraday swings. Overall,
LINK is a legitimate candidate for the Week 9 grid but should be expected to show
higher ADX entry thresholds and more frequent stop-outs than ETH.

### Key Findings

- **BTC/ETH correlation: 0.75-0.85** over rolling 90-day periods (Bitget Academy, 2026).
  High enough to inherit macro trend signals, independent enough to add noise.
- **75-85% of price variance** driven by BTC/ETH directional bias. The remaining
  15-25% is driven by DeFi oracle demand, Chainlink protocol milestones, and
  ETH gas/L2 activity.
- **Outperformance episodes**: when ETH gas fees decline and L2 transaction volumes
  surge, LINK often outperforms BTC by 15-30% over 4-8 week windows. These are
  narrative-driven and not reliably captured by ADX signals.
- **Amplified drawdowns**: during risk-off periods, LINK experiences greater percentage
  drawdowns than BTC/ETH, reflecting its mid-cap position with lower liquidity depth.
- **Trend classification**: primarily BTC-beta driven (high correlation), with
  narrative overlays. Behaves as a trend-following asset during sustained BTC/ETH
  bull trends, but less persistently than BTC itself.
- **Suitable for ADX**: the high-beta structure means ADX readings above threshold
  should correspond to real trend periods. However, expect more false starts and
  wider stop distances.

### Implications for Week 9 Grid Work

- Grid range: test ADX threshold 17-25 (may pass at lower threshold due to higher
  volatility generating stronger ADX readings during trend periods).
- Test trailing stop at 10-12% rather than 8%: LINK's amplified drawdowns may stop
  out a position that would have continued trending if given more room.
- LINK is the strongest candidate among the five altcoins for ADX generalisation,
  given its clean high-beta ETH relationship and reasonable liquidity depth.
- Do not mistake a LINK rally driven by an oracle/DeFi announcement for validated
  strategy edge — check that the ADX entry preceded the narrative event, not followed.

### Sources

- Bitget Academy: "Chainlink (LINK) Price Analysis: Trading Guide & Technical
  Indicators 2026."
- Bitget Academy: "Chainlink (LINK) Guide: Technology, Price Analysis & Trading
  in 2026."
- Coindesk.com: various LINK market structure articles.

---

## TOPIC 4 — Polkadot (DOT) and Polygon (POL): Market Characteristics

**Evidence quality: MODERATE for POL migration / LOW for strategy specifics**

### Summary

Both DOT and POL are in structural downtrends against BTC since their 2021 highs and
carry additional concerns beyond price performance. Polkadot's ecosystem has struggled
with developer and capital migration to competing layer-1s, and its 2025 price action
(below $2 at time of writing) reflects declining relative interest. Polygon completed
its MATIC→POL token migration on September 13, 2024 (1:1 conversion, Binance-supported),
which removes the migration risk — but the rebrand has not reversed the asset's
underperformance. For a trend-following grid test, both assets are lower-quality
candidates than LINK or BNB: DOT due to structural decline, POL due to rebranding
uncertainty and Ethereum L2 competitive pressure. Results should be interpreted with
significant caution.

### Key Findings

**Polkadot (DOT):**
- **2024 price action**: peaked ~$11 in Q1 2024, bled to ~$4 by mid-year, brief
  November rally to ~$7, then continued decline through 2025 (now below $2).
- **Bearish structure**: daily EMAs (20, 50, 100, 200) all above price and acting as
  resistance. Consistently lower lows. No sustained ADX trend-following periods
  visible in recent history.
- **Structural risk**: competing layer-1 and parachain ecosystems have reduced
  developer activity on Polkadot. No strong catalyst for reversal documented.
- **Backtest survivorship risk**: if running a long DOT backtest through 2021-2022
  peak, the strategy will capture the bull cycle but current structural conditions
  make those results non-representative of forward expectations.

**Polygon (POL, formerly MATIC):**
- **Migration completed**: September 13, 2024 on Binance. 1:1 conversion from MATIC
  to POL. All trading pairs updated (POL/USDT, POL/BTC, POL/ETH etc. live from
  that date). Old MATIC pairs delisted. No contract/custody issues outstanding.
- **Binance liquidity**: Spot and perpetual POL pairs fully live with normal liquidity
  depth. No delisting risk identified.
- **Market response**: POL surged 15-18% on Binance listing day (September 13, 2024),
  but this was a one-off migration event, not sustained momentum.
- **Competitive pressure**: Polygon faces significant competition from other Ethereum
  L2 solutions (Arbitrum, Optimism, Base). TVL and usage metrics have been contested.
- **Practical note for backtesting**: use POL/USDT data from September 2024 onwards;
  MATIC/USDT for prior history. Treat the migration date as a structural break
  when interpreting long-period backtest results.

### Implications for Week 9 Grid Work

- **DOT**: run the grid but set a high bar for deployment. A strategy that only
  passes on DOT's 2020-2021 bull run data is not deployable — ensure walk-forward
  window includes 2022-2024 (the structural decline period).
- **POL**: use ticker POL not MATIC in Binance API calls. Confirm data continuity
  around the September 2024 migration date before trusting full-period backtest results.
- If neither DOT nor POL passes the full validation pipeline (costs + walk-forward +
  B&H > 1.5×), that is the correct outcome — do not adjust methodology to make them pass.
- Lower deployment priority than LINK and BNB regardless of backtest result.

### Sources

- Binance.US Support: "Binance.US will support the Polygon MATIC token migration to POL."
- Coindesk: "Polygon's POL (MATIC) Token Spikes 15% on Binance Listing" (Sep 2024).
- Binance Blog: "Polygon To Upgrade MATIC Token To POL Token For Enhanced Flexibility."
- DailyCoin: "Polygon's POL (MATIC) Outshines Market with 18% Surge on Binance Migration."
- InvestingHaven, CoinCodex: Polkadot DOT price analysis 2024-2025.

---

## TOPIC 5 — BNB: Exchange Token Characteristics

**Evidence quality: MODERATE (price behaviour) / LOW (strategy-specific)**

### Summary

BNB is structurally different from LINK, DOT, and POL because its price is partially
supported by utility demand (BNB Chain gas fees, staking, Binance fee discounts) and
a programmatic deflationary mechanism (quarterly auto-burns). This creates a mild
support floor effect absent in pure narrative altcoins. In 2024, BNB reached an ATH
of $717.48 in June and closed the year near $700 — stronger performance than most
mid-cap altcoins and substantially more stable than DOT or POL. BNB shows CGARCH
volatility behaviour (different from BTC's TGARCH and ETH's EGARCH), suggesting
its volatility clustering is structurally distinct. For ADX trend-following, BNB's
more stable price behaviour and utility-driven demand make it a better candidate than
the more speculative altcoins, though it remains closely correlated with BTC/ETH.

### Key Findings

- **Strong 2024 performance**: started near $300, hit ATH $717.48 in June 2024,
  closed year ~$700. One of the stronger performing major altcoins in 2024.
- **Quarterly auto-burns** (Jan, Apr, Jul, Oct): approximately 0.5-2% supply
  burned each quarter. Q1 2024 burn: 1,944,452 BNB = ~$1.7B at prices at the time.
  Binance committed to burning 100M BNB total (50% of original supply).
- **Price impact of burns is modest**: large burn magnitudes have not produced
  proportional price spikes. Burns are predictable, and predictable supply reduction
  is priced in advance. Do not treat burn dates as signal catalysts.
- **Volatility clustering (CGARCH)**: distinct from BTC and ETH. CGARCH captures
  component-based conditional heteroskedasticity — BNB volatility has both short-term
  and long-term components, suggesting more structured volatility patterns than
  pure altcoins (Springer GARCH analysis, 2025).
- **Regulatory risk**: BNB is uniquely exposed to regulatory action against Binance.
  The 2023 Binance DOJ settlement created a sharp BNB drawdown independent of market
  conditions. This is a black-swan risk not captured in backtests.
- **Trend behaviour**: BNB shows cleaner trending periods than DOT/POL due to its
  utility base and stronger institutional recognition. Likely to show better ADX
  trend-following characteristics than the more speculative mid-caps.
- **Correlation**: high correlation with BTC/ETH (among the highest cross-coin
  correlations per TradingEconomics data), meaning BNB ADX signals will largely
  co-occur with ETH ADX signals.

### Implications for Week 9 Grid Work

- **Best altcoin candidate alongside LINK**: stronger price support, cleaner trend
  structure, better liquidity than DOT/POL.
- **Correlation overlap**: if BNB and ETH ADX signals fire simultaneously, that
  is correlated risk, not diversification. A deployed BNB strategy would increase
  single-direction exposure, not reduce it.
- **Regulatory tail risk**: add a note to any BNB strategy analysis that a
  Binance-specific regulatory event (fine, trading suspension, jurisdiction ban)
  can produce large drawdowns fully uncorrelated with ADX/market signals.
- Test trailing stop at 8-10%: BNB's more stable structure may allow tighter stops
  than the most volatile altcoins.

### Sources

- Springer Nature: "Volatility dynamics of cryptocurrencies: a comparative analysis
  using GARCH-family models" (2025).
- CryptoPotato: "Binance BNB Burn Explained: How Much is Burnt and When?"
- BNBBurn.info: BNB Real-Time Burn and Auto-Burn Schedule.
- Yahoo Finance / TheCoinRepublic: BNB quarterly burn coverage (2024).
- TradingEconomics: Crypto Correlations data.

---

## TOPIC 6 — Low-Frequency Sizing: Kelly and Fat Tails

**Evidence quality: HIGH (academic)**

### Summary

This is the area with the clearest and most concerning academic finding. The Frontiers
paper (2020) establishes that 100 trades is "too few for Kelly to work properly" and
that Kelly's theoretical properties require 10,000+ trades to manifest reliably.
At 20-30 trades per year, a strategy needs 500 years to accumulate enough trades
for full Kelly to be theoretically justified. The practical implication is not to
abandon position sizing discipline but to treat any Kelly fraction as a rough
prior with enormous uncertainty intervals, and to use at most quarter-Kelly in
all low-frequency crypto strategies — specifically because fat tails compound
the estimation error problem.

### Key Findings

- **Frontiers (2020) minimum trade requirement**: "100 trades are too few for Kelly
  to work properly." Reliable Kelly properties emerge only at 10,000+ trades.
  For practical trading: "the long run had to be really long."
- **At 20 trades/year**: 50-100 trades (2.5-5 years of data) to get even marginally
  meaningful win rate and payoff ratio estimates. Full Kelly requires ~500 years
  at 20 trades/year.
- **Estimation instability**: with only 20 trades, a single large winner or loser
  significantly distorts the estimated win rate. Kelly amplifies estimation errors —
  a win rate estimate that is 5% too high produces a materially over-sized Kelly
  fraction.
- **Fat tails compound the problem**: standard Kelly assumes a known, stable
  payoff distribution. Crypto's power-law tails mean the distribution is undefined
  or unstable. The Schulist (2016) fat-tailed Kelly framework (PIMCO) shows standard
  Kelly consistently over-bets in power-law distributed payoffs.
- **Quarter-Kelly is the practitioner consensus for crypto**: quarter-Kelly (0.25f*)
  accounts for both estimation error and fat-tail risk. Quarter-Kelly at low trade
  frequency is conservative but appropriate.
- **Half-Kelly tradeoff**: half-Kelly (0.5f*) achieves approximately 75% of full
  Kelly's growth rate while reducing maximum drawdown by roughly 50%.
  For a strategy with 25 trades/year, half-Kelly remains vulnerable to estimation
  error. Quarter-Kelly is more appropriate.
- **Non-independence risk**: crypto strategies that fire during trending regimes
  produce correlated signals. If three consecutive LINK trades all fire in a BTC
  bull run, they are effectively one bet on the regime, not three independent bets.
  Kelly's independence assumption is violated. Reduce position size accordingly.
- **The existing quarter-Kelly rule in METHODOLOGY_STANDARDS.md is correct**: the
  research here validates the decision already made, specifically for altcoins not
  validated through a full crash cycle.

### Implications for Week 9 Grid Work

- Maintain quarter-Kelly for all new altcoin strategies at deployment.
- Do not calculate Kelly from a backtest with fewer than 50 trades — the number
  is not meaningful. Report the trade count prominently in all backtest summaries.
- If a backtested strategy on AVAX or BNB shows 15 trades over the test period,
  the Kelly fraction is undefined for practical purposes. Use fixed fractional
  sizing (e.g., 1-2% of portfolio per trade) instead.
- The Kelly minimum trade count (50-100 for rough reliability) should be added
  to the validation checklist alongside the existing B&H > 1.5× gate.

### Sources

- Vince, Zhu & Zhao (2020). "Practical Implementation of the Kelly Criterion:
  Optimal Growth Rate, Number of Trades, and Rebalancing Frequency for Equity
  Portfolios." *Frontiers in Applied Mathematics and Statistics.*
- Schulist, S. (2016). "Fat Tailed Kelly." PIMCO / UCI Mathematics.
- Wikipedia: Kelly Criterion — Fractional Kelly and Extensions.
- QuantMatter: "Kelly Criterion Formula Explained: Inputs, Edge, and Fractional Kelly."
- StratBase.ai: "Kelly Criterion in Trading: The Optimal Bet Size."

---

## Asset Comparison Table

| Asset | BTC Correlation | Trend Quality | ADX Suitability | Structural Risk | Priority |
|-------|----------------|---------------|-----------------|-----------------|----------|
| LINK  | 0.75-0.85 | Good — high-beta ETH | **High** | Low | **1** |
| BNB   | High (0.80+) | Good — utility support | **High** | Regulatory tail | **2** |
| AVAX  | Moderate-high | Moderate — volatile | Medium | Moderate | 3 |
| POL   | Moderate | Poor — structural decline | Low | Migration + L2 competition | 4 |
| DOT   | Moderate | Poor — sustained downtrend | **Low** | Ecosystem decline | 5 |

---

## Week 9 Grid Work Priorities

### Priority 1 — LINK and BNB ADX Grid

Both have sufficient trend quality to be worth a full grid search.

Grid parameters:
- ADX threshold: 15-25 (wider range than ETH — parameters likely to differ)
- ADX period: 7-14
- Trailing stop: 8-12% (wider than ETH to accommodate higher volatility)
- 200MA filter: yes/no comparison
- Test period: 2020-2025, walk-forward split at 2023

Validation gates (same as METHODOLOGY_STANDARDS.md standard):
- Transaction costs applied (0.1% each way)
- B&H > 1.5× benchmark required
- Walk-forward consistency required
- Monte Carlo: 200 simulations, 95% CI positive
- Minimum 30 trades in backtest period (flag if below)

### Priority 2 — AVAX ADX Grid

- Same grid as Priority 1
- Apply survivorship bias note (AVAX had near-delisting risk in 2022-2023)
- Lower deployment threshold — only deploy if results are substantially stronger
  than LINK/BNB

### Priority 3 — DOT and POL if time permits

- These are expected to fail the full validation pipeline
- Run the grid for completeness and to document the failure reason
- POL: ensure data continuity check around September 2024 migration date
- DOT: flag that 2020-2021 bull run data likely drives any positive result

### Do NOT Build in Week 9

- Cross-sectional momentum portfolio (requires shorting — FCA blocked)
- Any altcoin RSI mean reversion strategy (regime filter research suggests
  focusing RSI work on ETH where it is already validated)
- BNB strategy with Kelly fraction above 0.25 regardless of backtest win rate

---

## Five Key Insights From This Research

**1. Cross-sectional momentum is strong; time-series parameter transfer is not.**
The academic evidence for crypto momentum is real but applies to ranking assets
relative to each other, not to applying fixed ADX thresholds across different
assets. Run wider grid ranges for altcoins; do not expect ETH parameters to pass.

**2. Post-ETF RSI signals need macro context, not a different entry threshold.**
The SMA120 filter already handles this. April 2025 RSI worked; December 2024 RSI
didn't — the difference was macro regime, and the SMA120 filter would likely have
blocked the December entry. Do not change RSI thresholds; trust the existing filter.

**3. BNB is the most structurally different altcoin in the test queue.**
Its utility-driven demand and quarterly burn mechanism create mild price floor
support not present in narrative-only altcoins. This makes it a better trend-
following candidate but also introduces a unique regulatory tail risk (Binance
itself) that is not in the backtest.

**4. DOT and POL are low-priority candidates and expected to fail.**
Both are in structural downtrends against BTC. Run the grid for completeness
but do not adjust methodology to produce passing results.

**5. 20 trades/year is below any meaningful Kelly threshold.**
The Frontiers (2020) paper is unambiguous: 100 trades is too few. At 20 trades/year
the estimated Kelly fraction is essentially an educated guess. Quarter-Kelly for all
new altcoin deployments, fixed fractional sizing if backtest shows fewer than 30 trades.

---

## Sources (Full List)

**Academic:**
- Liu, Tsyvinski & Wu (2022). "A Trend Factor for the Cross Section of Cryptocurrency
  Returns." *Journal of Financial and Quantitative Analysis*, Cambridge Core.
- Grobys et al. (2025). "Cryptocurrency Momentum Has (Not) Its Moments." *Financial
  Markets and Portfolio Management*, Springer Nature.
- "Cryptocurrency Market Risk-Managed Momentum Strategies." *Finance Research Letters*,
  ScienceDirect, 2025.
- "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market." AUT ACFR.
- Vince, Zhu & Zhao (2020). "Practical Implementation of the Kelly Criterion."
  *Frontiers in Applied Mathematics and Statistics*, DOI: 10.3389/fams.2020.577050.
- Schulist, S. (2016). "Fat Tailed Kelly." UCI Mathematics / PIMCO.
- "Volatility dynamics of cryptocurrencies: GARCH-family models." *Future Business
  Journal*, Springer Nature, 2025.
- arxiv.org (2025). "The Impact of Bitcoin ETF Approval on Bitcoin's Hedging
  Properties Against Traditional Assets."

**Practitioner:**
- Bitget Academy: "Chainlink (LINK) Guide: Technology, Price Analysis & Trading 2026."
- Binance Square / Binance Blog: Polygon MATIC→POL migration announcements (2024).
- Coindesk: "Polygon's POL (MATIC) Token Spikes 15% on Binance Listing" (Sep 2024).
- FXEmpire: "ETH Market Update: Can Ethereum Rebound After RSI Hits April 2025 Lows?"
- Ainvest: "Bitcoin ETF Inflows and Macroeconomic Momentum: A New Era for Institutional
  Adoption" (2025).
- BeInCrypto: "Bitcoin Adoption Soars: ETF Growth & Volatility Shifts in 2025."
- StratBase.ai: "Kelly Criterion in Trading: The Optimal Bet Size."
- QuantMatter: "Kelly Criterion Formula Explained."
- CryptoPotato: "Binance BNB Burn Explained: How Much is Burnt and When?"
- TradingEconomics: Crypto Correlations dashboard.

---

*Research prepared 2026-05-27.*
*Save to: 04_WEEKLY_SUMMARIES/WEEK_9_RESEARCH_BRIEF.md*
*Next: begin grid search notebooks in 06_BACKTESTS/Week_9_Notebooks/*
