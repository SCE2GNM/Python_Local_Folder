# DeFi Quantitative Trading Engineer

**REVISED ACTUAL Curriculum (Reflecting Real Progress)**

Build-First Approach | Quality Over Schedule

---

*REVISION NOTE: This curriculum reflects ACTUAL progress rather than original planned roadmap. Week 5-6 deviated from original schedule to resolve critical infrastructure gaps before adding new strategies. This is the professional quant approach: optimize existing systems before building new ones.*

**Duration:** 24 Weeks Core + 4 Weeks Elite Extensions
**Approach:** Quality-first, gap resolution prioritized
**Time Commitment:** Full-time (6-8 hours/day)
**Philosophy:** Validate and optimize before scaling
**Current Progress:** Week 7 complete, Week 8 in progress
**Outcome:** Job-ready with production-grade live trading system

---

## Actual Progress vs Original Roadmap

| Week | Original Roadmap | Actual Completed | Status |
|---|---|---|---|
| 1 | Foundation & DevOps | Foundation & DevOps | MATCH |
| 2 | Optimization & Web3 | Optimization & Web3 | MATCH |
| 3 | Live Infrastructure | Live Infrastructure | MATCH |
| 4 | Paper Trading | Live Trading ($1k) | EXCEED |
| 5 | Mean Reversion Suite | ADX Refinement + BB/RSI | HYBRID |
| 6 | Momentum (MACD/ROC/CMO) | Strategy Refinement + Leverage | DEFER |
| 7 | Volatility Trading | BTC ADX NO-GO + BTC SMA CONDITIONAL GO + Methodology standards + Leveraged bot paused | HYBRID |
| 8 | Multi-Strategy Portfolio | Volatility Trading | SHIFTED |

**Impact:** All subsequent weeks shifted by +1. No change to Week 24 completion date if working full-time. Curriculum remains 24 weeks core + 4 weeks elite extensions.

---

## Revised Course Structure (Actual)

**Phase 1: Foundation & Live Trading (Weeks 1-4)**
Infrastructure deployed, LIVE $1,000 by Week 4

**Phase 2: Strategy Optimization (Weeks 5-9)**
Refine existing + add mean reversion, momentum, volatility

**Phase 3: Advanced Quant & DeFi (Weeks 10-17)**
ML, portfolio theory, blockchain, AMMs, MEV

**Phase 4: Production & Career (Weeks 18-24)**
Infrastructure, databases, portfolio project, job search

**Phase 5: Elite Extensions (Weeks 25-28)**
Rust/C++, CEX/DEX hedging, HFT infrastructure

---

## Weekly Breakdown — ACTUAL Curriculum (Weeks 1-24)

### Week 1: Foundation & DevOps ✓

- AWS EC2, systemd, SSH, CI/CD pipelines
- Python async, backtesting framework
- Sharpe, Sortino, Calmar, drawdown metrics
- **Deliverable:** Working CI/CD + baseline ADX strategy

### Week 2: Optimization & Web3 Intro ✓

- Grid search (28 combinations — efficient vs 240 planned)
- Expanding window walk-forward validation
- Web3.py, Ethereum connection, Uniswap V3 price reading
- **Deliverable:** ADX 20/10 optimized + live DeFi data pipeline

### Week 3: Live Trading Infrastructure ✓

- Binance API integration (REST + WebSocket)
- Real-time 1-min candle streaming (infrastructure test)
- Automated ADX signal generation
- Position tracking (FLAT/LONG state machine)
- Comprehensive logging (JSON signals, CSV trades)
- Streamlit dashboard + Telegram alerts
- **Deliverable:** Complete live trading infrastructure

### Week 4: Live Deployment (Paper → Live) ✓

- Skipped extended paper trading — went LIVE April 4, 2026
- Position sizing: 12.41% Kelly criterion
- Stop-loss: 5% fixed (Binance STOP_LOSS_LIMIT order)
- EC2 cron job: 00:05 UTC daily
- Capital deployed: $1,000 USDT
- Risk controls: 3-layer RiskManager class
- **Deliverable:** Live $1,000 ADX 20/10 bot on production

### Week 5: ADX Refinement + Mean Reversion ✓

**Part A (Days 1-3): Critical Gap Resolution**
- Stop-loss aware backtest (A002) — 108 trades, 34.3% WR, PF 3.197
- Kelly recalculation (A005) — 11.77% vs 12.41%, immaterial
- Joint parameter optimization (A006) — 392 combinations tested
- Portfolio simulator (A007) — Calmar constant across leverage
- Resolved: A001, A002, A005, A006, A007

**Part B (Days 4-7): Mean Reversion Strategies**
- Bollinger Bands v3: PF 3.497, 150MA filter, 26 trades
- RSI final: PF 5.593, WR 93.5%, 120MA filter, 31 trades
- Walk-forward: 3/3 windows profitable for both
- BTC cross-asset: All strategies generalize to BTC

**Extension Work:**
- Sharpe bug fixed (daily equity curve method)
- BTC SMA 125 discovered (Calmar 4.464 — best strategy)
- BTC ADX optimized independently (19/14, 3% stop)
- Benchmark comparison (ADX 67.4% vs buy-hold 12.9%)
- Margin analysis preliminary (interest ~$30 over 108 trades)

**Deferred:** Z-score mean reversion, pairs trading

**Deliverable:** 2 validated mean reversion strategies + ADX refinement

### Week 6: Strategy Refinement & Leverage Optimization ✓

**ACTUAL FOCUS (differs from original roadmap):**
- Deploy RSI bot to EC2 ($150 validation capital)
- Add trailing stops to ADX (16-stage optimization)
- Validate BTC SMA — full pipeline, CONDITIONAL GO (walk-forward, stops, Phase 1-4)
- Optimize leverage levels (1.0x-5.0x grid search)
- Capital deployed: ~$1,985 (ETH ADX $1,000 + ETH RSI $150 + reserves)
- Leveraged bot deliberately paused — pending dynamic leverage framework and exchange failure risk analysis
- Resolve: A011 (trailing stops), A012 (BTC validation), A013 (leverage)
- A021 exchange failure risk identified — stop orders failed on Binance during October 2025 crash and March 2023 trailing stop bug

**DEFERRED FROM ORIGINAL ROADMAP:**
- MACD implementation → Week 8
- ROC (Rate of Change) momentum → Week 8
- CMO (Chande Momentum Oscillator) → Week 8
- Breakout detection → Week 8

**Deliverable:** 2 live strategies (ETH ADX trailing stop $1,000 + ETH RSI $150 validation), BTC SMA CONDITIONAL GO, leveraged bot paused pending framework

### Week 7: Strategy Validation + Methodology (ACTUAL) ✓

- **BTC ADX 19/14** — full validation pipeline, formal NO-GO
  (post-2022 +6.2%/yr, FRAGILE stability, win rate collapsed 37%→18%)
- **BTC SMA 110/T30%** — full validation Phases 1-4, CONDITIONAL GO
  (post-2022 +32.7%/yr, MARGINAL stability, Monte Carlo viable to 20% magnitude)
- **Leveraged bot paused** — dynamic leverage framework required first
  (A021: exchange stop order failure documented, October 2025 and March 2023)
- **Methodology standards expanded:**
  - Fat-tail warning: Sharpe/Sortino/Kelly assume normality — flagged for all momentum strategies
  - Power law distributions: crypto momentum returns have α < 3
  - Monte Carlo: mandatory for all strategies (not just low sample size)
  - Regime detection methods: Hurst exponent, ADX threshold, volume filter documented
  - Regime-based cycle review: replaces trade-count gate for low-frequency strategies
  - Quarter-Kelly standard: mandatory for unvalidated momentum strategies
- Deployment card template standardised (13-section format)
- File system reorganisation designed (implementation Week 8)
- **Deliverable:** 2 strategy validation decisions + expanded methodology framework

### Week 8: Infrastructure + Momentum Strategies (REVISED)

**Carry-over from Week 7 (do first):**
- File system reorganisation (numbered folder structure)
- BTC SMA Phase 5 leverage analysis + deployment card
- Leveraged bot build (day6_leveraged_bot.py) — dynamic leverage framework first
- ETH ADX Monte Carlo (A022 — MAJOR priority)
- Telegram message redesign (II-001)
- Project reference document (PROJECT_REFERENCE.html)

**New work:**
- Donchian Channel Breakout — full validation pipeline (Priority 1 momentum)
- RSI 50-100 trend strategy — backtest vs deployed mean-reversion RSI
- MACD with regime filter (Priority 2)
- Regime detection backtesting (ADX threshold vs Hurst exponent vs volume filter)
- Dynamic leverage framework design and backtest

**Deferred from original Week 8:**
- Volatility Trading → Week 9

**Deliverable:** Leveraged bot live + 1-2 momentum strategies validated

### Week 9: Volatility Trading + Regime-Switching (REVISED)

- ATR strategies
- Keltner Channels
- Volatility breakouts
- VIX correlation analysis
- Dynamic position sizing based on volatility
- Regime-switching portfolio design (ADX trend + Bollinger mean reversion on same asset)
- Portfolio-level dynamic capital allocation (SI007)
- **Deliverable:** Volatility system + regime-switching architecture

### Week 10: Multi-Strategy Portfolio (REVISED)

- Combine trend (ADX/BTC SMA) + mean reversion (RSI/BB) + momentum + volatility
- Strategy correlation analysis
- Portfolio rebalancing algorithms
- Capital allocation optimisation (performance-weighted dynamic allocation)
- Risk parity approaches
- Hurst exponent as portfolio-level regime indicator
- Elective Professional Client application planning (FCA — unlock shorting/futures)
- **Deliverable:** Diversified multi-strategy portfolio with dynamic allocation

### Week 11: Portfolio Theory

- Modern Portfolio Theory (MPT) fundamentals
- Efficient frontier calculation
- Sharpe ratio maximization
- Correlation analysis across assets
- Multi-asset allocation optimization
- **Day 7: Margin Trading Fundamentals (Educational)**
  - Isolated vs cross margin, liquidation mechanics
  - Funding rates, position sizing under leverage
  - Professional limits (1-2x max), dangers of high leverage
  - NO REAL TRADING — theory and calculations only
- **Deliverable:** Portfolio optimizer + margin knowledge

### Week 12: Risk Management Systems

- Value at Risk (VaR) calculation
- Expected Shortfall (CVaR)
- Advanced Kelly Criterion applications
- Stop-loss optimization techniques
- Drawdown controls and circuit breakers
- Risk budgeting across strategies
- **Deliverable:** Advanced risk management framework

### Week 13: Professional Backtesting

- Eliminate look-ahead bias completely
- Survivorship bias handling
- Multiple hypothesis testing corrections
- Realistic slippage modeling (market impact)
- Commission and fee modeling
- Backtest quality metrics
- **Deliverable:** Production-grade backtest engine

### Week 14: Blockchain Deep Dive

- Ethereum architecture (blocks, state, EVM)
- Smart contract mechanics and gas optimization
- Mempool analysis and transaction ordering
- Layer 2 solutions (Optimism, Arbitrum, Base)
- Node operation and RPC providers
- **Deliverable:** Blockchain data extraction tools

### Week 15: AMMs & Liquidity Provision

- Constant product formula (x\*y=k) deep dive
- Uniswap V2 vs V3 mathematics
- Concentrated liquidity mechanics
- Impermanent loss modeling and mitigation
- Fee APY calculations
- Pool selection strategies
- **Deliverable:** AMM simulator + IL calculator

### Week 16: DEX Arbitrage

- Cross-DEX price monitoring
- Arbitrage opportunity detection
- Gas optimization for profitability
- Flashbots integration for MEV protection
- Multi-hop routing optimization
- Sandwich attack detection and avoidance
- **Deliverable:** DEX arbitrage scanner

### Week 17: Yield & Lending Protocols

- Aave and Compound mechanics
- Collateralization and health factors
- Liquidation risk modeling
- Yield farming strategies
- Leveraged farming techniques
- APY vs APR understanding
- **Deliverable:** Yield optimization system

### Week 18: Docker & Containers

- Containerization best practices
- Docker Compose for multi-service deployments
- Environment variable management
- Secrets handling (never commit credentials)
- Health checks and monitoring
- Graceful shutdown patterns
- **Deliverable:** Fully Dockerized trading system

### Week 19: Databases & Monitoring

- PostgreSQL setup and optimization
- TimescaleDB for time-series data
- Structured logging frameworks
- Grafana dashboards for live monitoring
- Alerting systems (PagerDuty, Slack)
- Performance tracking and attribution
- **Deliverable:** Production data infrastructure

### Week 20: Kubernetes Basics

- Container orchestration fundamentals
- Service mesh architecture
- Zero-downtime deployments
- Horizontal and vertical scaling
- Disaster recovery planning
- Monitoring integration with Prometheus
- **Deliverable:** Kubernetes deployment of trading system

### Week 21: Cross-Chain & MEV

- Bridge mechanics and risks
- Cross-chain arbitrage opportunities
- MEV detection and analysis
- Sandwich attack mechanics
- Flashbots bundles and private transaction pools
- MEV protection strategies
- **Deliverable:** Cross-chain monitoring + MEV tools

### Week 22: Portfolio Project (Part 1)

- System architecture design
- Multi-strategy integration
- Real-time dashboard development
- Risk system integration across all strategies
- Performance attribution by strategy
- Comprehensive documentation
- **Deliverable:** Portfolio system foundation

### Week 23: Portfolio Project (Part 2)

- Unit testing and integration testing
- Code quality: linting, type hints, formatting
- API documentation generation
- Video demo recording
- Technical blog post writing
- GitHub README optimization for hiring managers
- **Deliverable:** Complete portfolio-ready project

### Week 24: Professional Branding

- GitHub profile optimization
- LinkedIn profile for DeFi quant roles
- Twitter presence in DeFi/crypto community
- Medium technical articles
- Dune Analytics dashboards
- Open source contributions to DeFi projects
- **Deliverable:** Complete professional online presence

### Week 25: Job Search & Offers

- Resume optimization for quant roles
- Cover letter templates
- Technical interview preparation
- Mock interviews and feedback
- Salary negotiation strategies
- Offer evaluation frameworks
- **Deliverable:** Job offers and employment!

---

## Post-Employment Elite Extensions (Weeks 26-29)

*Target Audience: Students targeting elite market-making firms (GSR, Wintermute, Jump Trading, Jane Street) requiring Rust/C++ and advanced hedging strategies.*

*Prerequisites: Core curriculum complete (Weeks 1-25), first job secured, 3-6 months employment experience, proven track record.*

### Week 26: Rust Fundamentals

- Ownership, borrowing, lifetimes (memory safety)
- Pattern matching, error handling, traits
- Cargo build system and testing framework
- Port simple Python strategy to Rust
- Performance benchmarking: Rust vs Python
- **Deliverable:** Rust ADX strategy (basic implementation)

### Week 27: Rust Async & Low-Latency

- Tokio runtime (async/await in Rust)
- WebSocket streaming with microsecond latency
- Lock-free data structures
- Zero-copy serialization techniques
- Binance order execution in Rust
- **Deliverable:** Production Rust trading bot

### Week 28: CEX/DEX Simultaneous Hedging

- Uniswap V3 LP position deployment ($1,000 DEX)
- Binance perpetual futures hedge ($1,000 CEX)
- **Day 3-4: Delta-Neutral Perpetual Hedging**
  - Delta calculation from concentrated liquidity position
  - Open Binance perpetual short (1x leverage ONLY)
  - Automated delta rebalancing logic
  - Funding rate monitoring and optimization
  - Professional hedging use case (not speculation)
- Fee collection vs funding rate arbitrage analysis
- Gas optimization for on-chain rebalancing
- **Deliverable:** Live CEX/DEX hedge bot ($2,000 capital total)

### Week 29: HFT Infrastructure Knowledge

- Co-location strategies (proximity to exchange servers)
- FPGA basics for ultra-low latency execution
- Order book reconstruction from market data
- Tick-to-trade latency measurement
- Market microstructure (bid-ask spreads, toxicity)
- Maker-taker fee optimization
- **Deliverable:** HFT knowledge documentation + portfolio showcase

---

## Deferred Topics Tracking

| Topic | Originally Scheduled | Reason Deferred | New Target |
|---|---|---|---|
| Z-score mean reversion | Week 5 | Prioritized ADX gap resolution | Week 9 or 22 |
| Pairs trading | Week 5 | Prioritized ADX gap resolution | Week 9 or 22 |
| MACD momentum | Week 6 | Trailing stops + leverage priority | Week 8 |
| ROC indicator | Week 6 | Trailing stops + leverage priority | Week 8 |
| CMO indicator | Week 6 | Trailing stops + leverage priority | Week 8–9 |
| Breakout / Donchian | Week 6 | Trailing stops + leverage priority | Week 8 — Priority 1 |
| Dynamic leverage framework | Not listed — ADD | Exchange failure risk + Kelly instability | Week 8 |
| Exchange failure risk protocol | Not listed — ADD | A021 documented Oct 2025 + Mar 2023 | Week 8 |
| Regime detection (Hurst exponent) | Not listed — ADD | Methodology standards Week 7 | Week 9 |
| Regime-switching portfolio | Not listed — ADD | SI007 strategy idea, Week 7 | Week 9–10 |
| RSI 50-100 trend strategy | Not listed — ADD | Contrast vs deployed mean-reversion RSI | Week 8 |
| Bear market / short strategies | Not listed — ADD | FCA retail restriction; requires Pro Client | Week 13+ |
| Altcoin pairs — higher volatility | Not listed — ADD | SI idea logged Week 7 | Week 13+ |
| Pension investment strategies | Not listed — ADD | SI014 logged Week 7 | Week 20+ |
| Insider Buy Superstocks methodology | Not listed — ADD | SI015 logged Week 7 | Week 20+ |

**Integration Plan:** Deferred topics will be integrated into later weeks when appropriate, or included in the portfolio project (Weeks 22-23) if not critical to core curriculum.

---

## Your Actual Journey Timeline

**Week 4:** LIVE $1,000 ADX deployed (April 4, 2026)

**Week 5:** ADX refined + 2 mean reversion strategies validated

**Week 6:** 2 strategies live (ETH ADX $1,000 + ETH RSI $150), trailing stops deployed, leveraged bot paused pending dynamic framework

**Week 7:** BTC ADX rejected, BTC SMA CONDITIONAL GO, methodology framework expanded

**Week 9:** Multi-strategy diversified portfolio

**Week 13:** Professional backtesting complete + ML integration

**Week 17:** DeFi yield optimization deployed

**Week 21:** Cross-chain + MEV monitoring operational

**Week 25:** Job offers + employment!

**Week 29:** Rust proficiency + CEX/DEX hedge (elite firms ready)

---

**Expected Outcomes:** Production-grade multi-strategy trading system managing $3,000+ capital, live DeFi integration, professional portfolio showcasing 5+ validated strategies, active GitHub presence with portfolio-ready code, technical blog demonstrating expertise, and job-ready skills for $80k-300k+ remote DeFi quant roles. Elite extensions (Weeks 26-29) unlock $200k-500k+ roles at top market makers.

---

**Current Status:** Week 7 COMPLETE. Live portfolio: ETH ADX $1,000 (trailing stop active) + ETH RSI $150 (validation phase). BTC SMA CONDITIONAL GO — deployment pending Phase 5 and leveraged bot framework. All methodology standards formalised including fat-tail warning, Monte Carlo mandatory, regime-based position sizing. 17 weeks remaining in core curriculum. You are 29% complete.

---

## Methodology Standards Established (Weeks 6-7)

These standards now apply to ALL future strategy work:

- **Monte Carlo:** Mandatory for all strategies. Not optional for low sample sizes.

- **Fat-tail warning:** Sharpe, Sortino, Kelly, confidence intervals all assume normality.
  For crypto momentum strategies (power law α < 3), these are unreliable as absolute
  measures. Use as relative comparators only.

- **Quarter-Kelly:** Default for any momentum strategy not confirmed through a bear market cycle.

- **Regime-based position sizing review:** For low-frequency strategies (<10 trades/yr),
  review after one complete regime cycle (one profit exit + one loss exit) rather than
  20-trade gate.

- **Dynamic leverage:** Leverage must scale with trend strength — static maximum leverage
  at entry not permitted for new leveraged strategies from Week 8 onwards.

- **Exchange failure risk:** Stop orders can fail during extreme market stress (documented
  October 2025, March 2023). Emergency manual exit protocol required before leveraged
  deployment.

- **Deployment card standard:** All strategies require 13-section deployment card before
  capital deployment.

---

*Document version: 2.0 — converted to Markdown and updated 2026-05-16 to reflect Week 7 actual progress.*
*Source: DeFi_Quant_Roadmap_REVISED_ACTUAL.pdf (iCloud, superseded by this Markdown version).*
*PDF export: at major phase milestones only (end of Phase 1, Phase 2, etc). This Markdown file is the live document.*
