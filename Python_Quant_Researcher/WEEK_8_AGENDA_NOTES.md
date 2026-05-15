# Week 8 Agenda Notes
## DeFi Quant Engineer Curriculum

**Student:** Greg (Gmac)
**Week:** 8 of 24
**Prepared:** End of Week 7 (2026-05-15)
**Purpose:** Carry-over items and priorities for Week 8 session start

---

## Week 8 Carry-Over Items (from Week 7)

1. **II-001: Telegram message redesign** — implement before leveraged bot deployment. See STRATEGY_IDEAS_LOG.md for full spec. Apply to day5_production_bot.py, rsi_production_bot.py, and any future bots.

2. **Leveraged bot build (day6_leveraged_bot.py)** — Priority 1, deferred from Week 7 pending dynamic leverage framework. Do not build until dynamic leverage framework is designed and backtested.

3. **Dynamic leverage framework** — design and backtest before leveraged bot deployment. Methodology: Kelly-based or volatility-targeted leverage that adjusts position size based on market conditions rather than fixed 1.9×.

4. **BTC SMA Stage C Monte Carlo** — in progress. Win-rate scenario framework is inappropriate for the 23–33% win rate / fat-tail payoff structure of T30% strategies. Resolve scenario design before running Stage C. See session notes for proposed alternatives (return magnitude scaling or bootstrap resampling).

5. **A022: ETH ADX Monte Carlo** — MAJOR priority, Week 8. Risk register item A022 for ETH ADX strategy requires Monte Carlo validation before any leveraged deployment.

6. **ETH RSI stability analysis RR-RSI-006** — outstanding from Week 7 risk register. Required before ETH RSI strategy can be considered for scaling.

7. **Project reference document (PROJECT_REFERENCE.html)** — outstanding from Week 7. Untracked file in repo root. Review whether to commit or archive.

---

*Created: 2026-05-15 — end of Week 7*
