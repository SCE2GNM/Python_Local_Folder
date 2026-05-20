# Week 9 Thread Starter
## DeFi Quant Engineer Curriculum
**Student:** Greg (Gmac)
**Week:** 9 of 24
**Dates:** 21–27 May 2026
**Preceding summary:** 04_WEEKLY_SUMMARIES/WEEK_8_SUMMARY.md

---

## Week 8 Context — What Week 9 Needs to Know

### Strategy status coming in
- **ETH ADX (Live — $1,000 capital):** Regime break confirmed at ETH ETF approval May 2024. PF declined 2.947 → 1.689 post-ETF; win rate 44.3% → 35.1%. Risk architecture intact (worst loss still capped −8%). Strategy remains live — edge compressed but not destroyed. Leverage deployment formally deferred to Week 16–18 pending post-ETF sample reaching 80 trades with PF > 2.0. See RISK_REGISTER_ETH_ADX.md item A022.
- **ETH RSI (Validation — $150 capital):** No changes in Week 8. RR-RSI-006 stability analysis still open and six weeks outstanding. This is the blocker to any capital scaling decision.
- **BTC SMA 110/30% (CONDITIONAL GO — not deployed):** Phase 5 leverage analysis incomplete for the second consecutive week. CONDITIONAL GO is signed but deployment is blocked pending the leverage grid.
- **SOL Keltner (Rejected):** Decisive regime break — PF 7.793 pre-ETF → 3.932 ETF-to-ATH → 0.055 post-ATH. Closed 2026-05-20. Reopen condition: PF > 2.0 over ≥ 20 trades in post-Aug 2025 data.
- **SOL ADX, Supertrend, Donchian, Bollinger (Rejected):** All four indicator families produced 0 viable combinations on SOLUSDT daily. SOL daily trend-following closed as a research direction.

### Frameworks created in Week 8
- **STRATEGY_ARCHIVE.md** — permanent record of all 10 strategies researched through Week 8 (S001–S010). Located at 00_MASTER/STRATEGY_ARCHIVE.md.
- **sol_grid_search.py** — multi-asset discovery grid (ADX/Supertrend/Donchian/Keltner/Bollinger, ~1,478 combos, 30-trade / −50% MDD filters). Reusable for Week 9 altcoin queue.

### Standing rule added in Week 8 — applies to all future work
**Regime break analysis is mandatory before walk-forward on any asset.** Full-period backtest metrics are dominated by the pre-institutional regime and overstate current expected performance for BTC and ETH. The post-break profit factor and win rate are the correct forward-looking inputs for deployment decisions. See METHODOLOGY_STANDARDS.md — Regime Break Analysis section.

Split dates:
- BTC/ETH: January 2024 (BTC ETF) and May 2024 (ETH ETF)
- SOL: August 2025 (ATH and regime shift)
- BNB/AVAX/LINK/DOT/MATIC: January 2024 as default (indirect institutional effect)

---

## Week 9 Priority Task List — In Order

**Priority 1 — LEARNING_LOG.md update**
Status: ✅ Complete — committed `a2278fc` during Week 8 close-out.
9 concepts added: Keltner Channel, EMA trailing stop with intrabar trigger, multi-strategy discovery grid, exit gap analysis, walk-forward for short-history assets, regime break analysis methodology, institutional adoption effect, survivorship bias in altcoin backtesting, SOL market characteristics.

**Priority 2 — ETH RSI stability analysis (RR-RSI-006)**
Six weeks outstanding (open since Week 3). Required before any discussion of scaling ETH RSI beyond $150.
Action: Complete the rolling parameter stability analysis specified in RR-RSI-006. Report parameter robustness across three time windows. Update RISK_REGISTER_ETH_RSI.md with outcome and close out RR-RSI-005 and RR-RSI-006.

**Priority 3 — Data quality checks: LINK, DOT, MATIC**
Before running the discovery grid on any new asset, confirm:
1. Sufficient history (≥ 3 years preferred, 2 years minimum)
2. No suspicious gaps or price anomalies
3. Adequate daily volume for realistic execution
If an asset fails the data check, remove from the queue and note in STRATEGY_IDEAS_LOG.md (SI017).

**Priority 4 — Multi-asset discovery grid: LINK, DOT, MATIC, BNB, AVAX**
Run sol_grid_search.py framework on each passing asset. Only proceed to walk-forward where ≥ 5 combos pass with Sortino > 0.8. If no asset passes, document and close the altcoin research direction for the current market cycle.
Note: Regime break analysis (Priority 1 standing rule above) is mandatory before walk-forward on any asset that produces passing combos.

**Priority 5 — BTC SMA Phase 5 leverage analysis**
Two weeks outstanding. Complete the remaining CONDITIONAL GO condition: run leverage grid (1.0×–3.0×, coarse then fine) on SMA110/T30%. Write deployment card. Capital: $500 initial.
Prerequisite per METHODOLOGY_STANDARDS.md: dynamic leverage framework must be backtested before deployment — not a fixed multiplier.

---

## Assets Confirmed for Week 9 Backtests — Kelly Permissions

| Asset | Kelly Permission | Notes |
|---|---|---|
| BNB (BNBUSDT) | Half-Kelly | Survived 2022 bear — half-Kelly permitted |
| AVAX (AVAXUSDT) | Quarter-Kelly | No 2022 OOS confirmation in this curriculum |
| LINK (LINKUSDT) | TBD | Data quality check required first |
| DOT (DOTUSDT) | TBD | Data quality check required first |
| MATIC (MATICUSDT) | TBD | Data quality check required first |
| SOL (SOLUSDT) | Quarter-Kelly — deferred | Not in active backtest queue; reopen pending regime break resolution (PF > 2.0 over ≥ 20 trades post-Aug 2025) |

---

## Per-Trade MaxDD — Week 9 Compliance Requirement

Week 8 scripts (sol_grid_search.py, keltner_walkforward.py, sol_regime_break.py) report MtM MaxDD only. This is a known gap against METHODOLOGY_STANDARDS.md which requires both per-trade MaxDD and daily MtM MaxDD.

**Add per-trade MaxDD to every new backtest script in Week 9.** Report both:
- `per_trade_mdd`: maximum single trade loss as % of capital
- `mtm_mdd`: maximum drawdown on daily equity curve (MtM)

---

## Open Risk Register Items Coming Into Week 9

| Item | Register | Status |
|---|---|---|
| RR-RSI-005 | RISK_REGISTER_ETH_RSI.md | Update required |
| RR-RSI-006 | RISK_REGISTER_ETH_RSI.md | Six weeks outstanding — Week 9 Task 2 |
| RISK_REGISTER_BTC_SMA.md | BTC SMA | Phase 5 status update required |
| A022 | RISK_REGISTER_ETH_ADX.md | In Progress — next review Week 16–18 |
| II-001 | Infrastructure | Telegram health check redesign — three weeks outstanding |

---

*Week 9 Thread Starter v1.0*
*Prepared: 2026-05-20 (Week 8 close-out)*
