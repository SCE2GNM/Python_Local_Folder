# Strategy Research Archive
## DeFi Quant Engineer Curriculum

**Purpose:** Permanent record of every strategy researched during this curriculum, including all strategies rejected at any pipeline stage. A rejected strategy is a documented decision, not a failure.
**Who reads it:** Greg when reviewing what has been tried and why. Claude Code when evaluating whether a strategy has been previously tested. Independent reviewers auditing research quality.
**When updated:** After every GO/NO-GO decision, whether positive or negative. Updated at end of each week.
**Sources:** RISK_REGISTER files, weekly summaries, backtest result CSVs, Strategy Ideas Log.

---

## Status Legend

| Status | Meaning |
|---|---|
| **Live** | Deployed to EC2 with real capital |
| **Validation** | Deployed at minimal capital to accumulate live trade data before scale-up |
| **Not Deployed** | Backtested and assessed, never deployed — see notes |
| **Deferred** | CONDITIONAL GO or better — deployment blocked by an explicit condition |
| **Rejected** | Formal NO-GO at a named pipeline stage |

---

## Strategies

---

## S001 — ETH ADX Trend-Following (Live)

**Status:** Live
**Rejection stage:** N/A — passed all stages
**Date approved:** 2026-05-05 (initial deployment); 2026-05-13 (trailing stop parameters confirmed)
**Tested in:** Weeks 4–6

### Parameters tested

| Stage | Parameters |
|---|---|
| Initial deployment | ADX period 20, DI period 10, fixed 5% stop |
| Week 5 re-optimisation | ADX threshold 16–25, DI period 7–15, fixed stops 3–10% (728-combination grid) |
| Week 6 trailing stop grid | ADX 19/9, ATR 9/2.5× and pct trail 8% (36 combinations) |
| **Deployed (current)** | **ADX period 19, DI period 9, pct trailing stop 8%** |

### Best backtest metrics (full period 2018–2026, 8.4 years)

| Metric | Value |
|---|---|
| Annual return | +80.1% |
| Max drawdown (per-trade) | −31.3% |
| Max drawdown (MtM) | −31.3% |
| Sortino | 1.780 |
| Calmar | 2.557 |
| Win rate | ~42% (Pre-ETF 44.3%, Post-ETF 35.1% — regime split confirmed May 2026) |
| Trades | 159 (full backtest period) |

**Post-ETF regime note (A022, 2026-05-18):** Strategy remains live but edge has compressed post-ETH spot ETF approval (May 2024). Pre-ETF: PF 2.947, annual +102.8%, WR 44.3%. Post-ETF (37 trades): PF 1.689, annual +23.0%, WR 35.1%. Risk architecture intact (worst loss capped −8.0% in both periods). Leverage deployment deferred until post-ETF sample reaches 80 trades and PF confirmed above 2.0.

### Why approved

Full 4-stage validation complete. 2022 bear market confirmation (+35.1% when ETH B&H −68.3%) is the single most important validation data point. Calmar 2.557 confirms satisfactory return-to-drawdown profile at 1× leverage. Kelly correct implementation corrected Week 6 (20× undersizing bug resolved).

### Reopen conditions

Strategy is live. Next scheduled review: after 80 post-ETF live trades — leverage deployment decision at that point (A022).

### Links

- `01_RISK_REGISTERS/RISK_REGISTER_ETH_ADX.md`
- `06_BACKTESTS/Week_6_Notebooks/` — trailing stop grid scripts
- `05_BOTS/day5_production_bot.py` — live bot (EC2, 4× daily cron)
- Risk register items: A003, A009, A010, A013–A016, A021, A022 (open)

---

## S002 — ETH RSI Mean Reversion (Validation)

**Status:** Validation — deployed at $150 capital cap; scale-up conditions not yet met
**Rejection stage:** Not rejected — conditional deployment
**Date approved:** 2026-05-07 (deployed at $150)
**Tested in:** Weeks 5–6

### Parameters tested

| Stage | Parameters |
|---|---|
| Discovery | RSI period 10–20, oversold threshold 30–50, exit threshold 45–60, stops 5–20%, MA filter 50–200 |
| Optimised | RSI 14, entry <43, exit >48, 15% fixed stop, 120MA regime filter |

### Best backtest metrics (ETH-USD, 2018–2026, 6.5 years)

| Metric | Value |
|---|---|
| Annual return (Monte Carlo median at 93.5% WR) | +22.3% |
| Max drawdown | ~−21% (implied from Calmar 1.054 and annual ~22.3%) |
| Sortino | 0.307 (daily equity curve method — authoritative figure from stage5_final_comparison.py. Below 0.8 deployment threshold. Accepted at $150 validation capital — see RR-RSI-011 for rationale.) |
| Calmar | 1.054 |
| Profit factor | 5.593 |
| Win rate | 93.5% (29/31 trades) |
| Trades | 31 (6.5 years, ~4.8 trades/year) |

**Monte Carlo findings (RR-RSI-001):** At 70% live win rate (pessimistic scenario), Kelly fraction is negative — strategy has no positive expectancy. Breakeven win rate = 72.2%. At 75% live win rate, median annual return is −0.1% with 55.5% probability of negative year. Strategy only clearly profitable above ~80% live win rate.

### Why capped at $150

Backtest win rate of 93.5% is almost certainly overstated — it is based on 31 trades, giving a 95% confidence interval of 79%–99%. Monte Carlo at realistic live win rates (70–75%) shows negative or near-zero Kelly expectation. $150 limits capital at risk to an acceptable learning cost while accumulating 20 live trades. Scale-up requires: 20 live trades completed AND running win rate ≥80%.

Stability analysis (RR-RSI-006) also outstanding — no STABLE/MARGINAL/FRAGILE classification has been run on this strategy.

### Reopen conditions (scale-up)

Scale to $341–$495 only after: (1) 20 live trades completed, (2) running win rate ≥80%, (3) RR-RSI-006 stability analysis completed.

### Links

- `01_RISK_REGISTERS/RISK_REGISTER_ETH_RSI.md`
- `06_BACKTESTS/Week_5_Notebooks/day5_rsi_final.py`
- `06_BACKTESTS/Week_5_Notebooks/day5_rsi_stability.py`
- `05_BOTS/rsi_production_bot.py` — live bot (EC2, 00:06 UTC daily)
- Risk register items: RR-RSI-001 through RR-RSI-006 (all open)

---

## S003 — ETH Bollinger Bands Mean Reversion (Not Deployed)

**Status:** Not Deployed — backtest passed initial assessment; walk-forward borderline; never committed to live capital
**Rejection stage:** Walk-forward validation (Week 5 Day 7) — borderline result, not a hard NO-GO
**Date closed:** 2026-05-07 (Week 6 start — superseded by ETH RSI deployment)
**Tested in:** Week 5

### Parameters tested

| Version | Parameters | PF | Outcome |
|---|---|---|---|
| v1 | BB window 20, std 2.0, stop 5%, no filter | 0.962 | Loss — rejected |
| v2 | BB window 20, std 2.0, stop 10%, 200MA filter | 1.615 | Improved — continued |
| v3 (final) | BB window 15, std 2.0, stop 10%, 150MA filter | 3.497 | Best result |

### Best backtest metrics (ETH-USD, 2018–2024, ~6.5 years — BB_15_2_v3)

| Metric | Value |
|---|---|
| Annual return | +14.8% |
| Max drawdown | −19.2% |
| Calmar | 0.768 |
| Sortino | 0.220 (per-trade method — pre-Week 6 correction; daily equity Sortino not computed) |
| Profit factor | 3.497 |
| Win rate | 80.8% |
| Trades | 26 (~4 trades/year) |

**Methodology note:** These metrics were computed before the Week 6 Sortino correction (per-trade method, not daily equity curve). The Sortino of 0.220 is likely understated relative to what daily equity method would produce for a mean reversion strategy. Annual return of 14.8% reflects conservative trading frequency (4 trades/year) under the 150MA regime filter.

### Why not deployed

Three reasons: (1) 26 trades is thin — below the 30-trade minimum established in later Methodology Standards; (2) walk-forward validation showed borderline results (2/3 test windows profitable — sufficient to pass but not a clean DEPLOY verdict); (3) ETH RSI was deployed instead as the primary ETH mean reversion strategy, using the available $150–$500 validation capital. No analytical case for running both simultaneously at this stage.

### Reopen conditions

Reopen if ETH RSI is permanently abandoned or if a mean reversion regime-switching portfolio (SI012) is built in Week 9+. Before reopening, re-run full backtest with corrected daily equity Sortino method and complete stability analysis. Run Monte Carlo at conservative win rates (60–70%) to check positive expectancy. Minimum 30 trades required.

### Links

- `06_BACKTESTS/Week_5_Notebooks/day4_bollinger_final.py`
- `06_BACKTESTS/Week_5_Notebooks/day4_bollinger_optimisation.py`
- `06_BACKTESTS/Week_5_Notebooks/day7_walk_forward.py`
- Strategy Ideas Log: SI012 (regime-switching portfolio — ADX + Bollinger)

---

## S004 — BTC SMA Crossover (Deferred)

**Status:** Deferred — CONDITIONAL GO (Week 7); Phase 5 leverage analysis and deployment card pending (Week 8)
**Rejection stage:** Initial pipeline ran NO-GO (Week 6); revised pipeline CONDITIONAL GO (Week 7)
**Date deferred:** 2026-05-15 (CONDITIONAL GO signed off)
**Tested in:** Weeks 5–7

### Parameters tested

| Stage | Parameters | Outcome |
|---|---|---|
| Original pipeline (Week 6) | SMA period 80–200, pct trail 8–30%, grid 5-stage | Primary: SMA 120/25% — NO-GO |
| Stage B re-run T8% sweep (Week 7) | SMA 80–160, pct trail 8% | NO-GO — T8% too tight (12 whipsaw entries Jan 2021 alone) |
| Stage B wider trail sweep (Week 7) | SMA 100–150, pct trail 15–35% (55 combinations) | 33/55 pass; **SMA 110/30% selected** |
| **Current primary candidate** | **SMA period 110, pct trail 30%** | CONDITIONAL GO |

### Best backtest metrics (BTCUSDT, 2018–2026)

**SMA 110/30% (current primary):**

| Metric | Value |
|---|---|
| Sortino | 1.379 |
| Max drawdown (MtM) | −31.4% |
| Post-2022 annual return | +32.7% |
| Win rate | 23% |
| Avg win | +88.0% |
| Avg loss | −2.7% |
| Trades | 39 |
| MC median annual (100% magnitude) | +55.3% |
| MC P10 annual (100% magnitude) | +27.5% |
| P(negative year) at 100% magnitude | 39.7% |

**Phase 4 ETH cross-asset:** PARTIAL PASS — ETH annual +26.8% positive, but Sortino 0.701 (below 0.8 threshold), post-2022 ETH return −0.5%. BTC-only deployment restriction confirmed.

**For comparison — original candidate SMA 120/25% (shelved Week 6):** Annual +48.9%, MtM MaxDD −30.5%, Sortino 1.246, Calmar 2.752, n=34 trades. Shelved due to MARGINAL stability (50.5%), 76% of return concentrated in 2021 (ex-2021 annual ~29%), and ETH cross-asset failure.

### Why deferred

CONDITIONAL GO — not rejected. Conditions blocking deployment: (1) Phase 5 leverage analysis not completed (Week 8 carry-over); (2) deployment card not written; (3) position sizing fixed at 5–10% capital-at-risk (Kelly-derived sizing unreliable for fat-tail distributions with 39 trades). Initial capital target: $500 BTC (MARGINAL stability warrants conservative start). Two open risk items flagged: BS001 (ETH cross-asset failure accepted as asset-specificity), BS002 (76% 2021 return concentration — disclosed, not a veto).

### Reopen conditions

Already CONDITIONAL GO. Deploy after: Phase 5 leverage analysis complete, deployment card written, A021 emergency exit protocol documented.

### Links

- `01_RISK_REGISTERS/RISK_REGISTER_BTC_SMA.md`
- `06_BACKTESTS/Week_7_Notebooks/btc_sma_stage_b_results.csv` — Stage B wider trail sweep (partially; file captures T8% version — wider sweep results in risk register)
- `06_BACKTESTS/Week_6_Notebooks/btc_sma_stage_c_magnitude.py` — Phase 3 Monte Carlo
- `06_BACKTESTS/Week_7_Notebooks/results/btc_sma_stage_c_results.csv` — MC results
- Risk register items: BS001–BS008 (BS005 resolved, remainder open)

---

## S005 — BTC ADX Trend-Following (Rejected)

**Status:** Rejected
**Rejection stage:** Stage B (half-split / stability) — decisive NO-GO, Monte Carlo not required
**Date closed:** 2026-05-14
**Tested in:** Week 7

### Parameters tested

| Stage | Parameters |
|---|---|
| Stage A — stop sweep | Fixed stops 3–8%, ATR and pct trail variants (14 combinations) |
| **Stage B candidate** | **ADX threshold 19, period 14, fixed 3% stop** |
| Stage B — stop stability sweep | Fixed stop 2.0–8.0% (11 values) |

Best stop from Stage A: fixed 3% (Annual +42.1%, Sortino 1.139, Calmar 1.003, 103 trades).

### Best backtest metrics (BTCUSDT, 2018–2026, 8.4 years)

| Metric | Full period | Pre-2022 | Post-2022 |
|---|---|---|---|
| Annual return | +42.1% | +95.1% | +6.2% |
| Max drawdown (MtM) | −48.4% | — | — |
| Max drawdown (per-trade) | −42.0% | — | — |
| Sortino | 1.139 | 1.800 | 0.349 |
| Calmar | 1.003 | 4.738 | 0.156 |
| Win rate | 27% | 38% | 18% |
| Trades | 103 | 48 | 55 |

### Why rejected

**Two hard failures — both required for Stage B GO:**

1. **FRAGILE stability:** Only 3 of 11 stop values pass the composite stability threshold (27% vs 40% minimum). The 3% stop sits near the peak of a narrow spike; 6.0–8.0% stops have half the Sortino and twice the MDD. A strategy that only works at one specific stop value is almost certainly data-fitted to the backtest.

2. **Post-2022 annual return +6.2%/yr against a 15%/yr minimum threshold:** Structural regime deterioration confirmed. Win rate collapsed from 38% pre-2022 to 18% post-2022. Average ADX level when on-signal declined from 34.0 to 30.5 — BTC spending less time in strong trends post-ETF-era institutionalisation. At 6.2%/yr, the strategy barely exceeds cash returns and is not worth the drawdown risk (−48.4% MtM).

Note: BTC SMA 110/30% is decisively superior to BTC ADX on every risk-adjusted metric (Calmar 2.752 vs 1.003, 2022 loss −6.6% vs −42.0%). BTC ADX is not a fallback option.

### Reopen conditions

Would require evidence of regime recovery: post-2022 annual return exceeding 20%/yr over a 30+ trade live or out-of-sample sample. Not worth pursuing while BTC SMA CONDITIONAL GO is pending deployment.

### Links

- `01_RISK_REGISTERS/RISK_REGISTER_BTC_SMA.md` (rejection noted in header block)
- `06_BACKTESTS/Week_7_Notebooks/btc_adx_stageA.py`
- `06_BACKTESTS/Week_7_Notebooks/results/btc_adx_stageA_results.csv`
- `06_BACKTESTS/Week_7_Notebooks/results/btc_adx_stage_b_results.csv`
- Strategy Ideas Log: SI001 (originally high priority — revised to NO-GO after Stage B)

---

## S006 — SOL Keltner Channel Breakout (Rejected)

**Status:** Rejected
**Rejection stage:** Regime break analysis (Week 8) — decisive NO-GO
**Date closed:** 2026-05-20
**Tested in:** Week 8

### Parameters tested

Multi-strategy discovery grid (sol_grid_search.py): Keltner Channel, 44 combinations — EMA period 15–25, multiplier 1.5–3.0 (step 0.5). Filter: ≥30 trades AND MDD > −50%.

Walk-forward candidates (keltner_walkforward.py): top 3 from grid — ema=22/mult=1.5 (rank 1), ema=22/mult=2.0, ema=19/mult=1.5.

### Best backtest metrics (SOLUSDT, 2020–2026, 6.3 years — ema=22, mult=1.5)

| Metric | Value |
|---|---|
| Annual return | +121.9% |
| Max drawdown (MtM) | −45.6% |
| Sortino | 1.933 |
| Profit factor | 5.966 |
| Win rate | 39.1% |
| Trades | 46 |

21 of 44 Keltner combinations passed the ≥30 trades / MDD > −50% filter. Keltner dominated the top 20 by a wide margin over all other tested strategy types on SOLUSDT.

### Why rejected

Walk-forward validation (7 expanding + 7 rolling windows, 2-year IS / 6-month OOS) showed the last 2 OOS windows unprofitable. Regime break analysis (sol_regime_break.py, split at Jan 2024 BTC ETF approval and Aug 2025 SOL ATH) confirmed the edge is structurally absent in the most recent period:

| Period | Profit Factor |
|---|---|
| Pre-ETF (2020 – Jan 2024) | 7.793 |
| ETF to ATH (Jan 2024 – Aug 2025) | 3.932 |
| Post-ATH (Aug 2025 – May 2026) | 0.055 |

A profit factor of 0.055 post-ATH means the strategy lost approximately $0.95 for every $1 of gross profit — near-total edge destruction. This is the same structural deterioration pattern as BTC ADX 19/14 (post-2022 collapse) but more extreme and more recent. The Keltner breakout edge existed when SOL was a high-momentum emerging asset; it has evaporated as the post-ATH regime established itself. Full backtest metrics are inflated by the pre-2024 period and do not reflect the current tradeable edge.

### Reopen conditions

PF > 2.0 confirmed over ≥ 20 trades in post-Aug 2025 live or OOS data. Do not revisit on the basis of a single favourable quarter — sustained evidence required.

### Links

- `06_BACKTESTS/Week_8_Notebooks/sol_grid_search.py`
- `06_BACKTESTS/Week_8_Notebooks/sol_grid_results.csv`
- `06_BACKTESTS/Week_8_Notebooks/keltner_walkforward.py`
- `06_BACKTESTS/Week_8_Notebooks/keltner_gap_analysis.py` — exit slippage analysis for ema=22/mult=1.5
- `06_BACKTESTS/Week_8_Notebooks/sol_regime_break.py` — regime break script (pending run)

---

## S007 — SOL ADX Trend-Following (Rejected)

**Status:** Rejected
**Rejection stage:** Discovery grid (Stage A equivalent — Week 8)
**Date closed:** 2026-05-19
**Tested in:** Week 8

### Parameters tested

1,232 combinations: ADX period 7–20, threshold 15–25, fixed stop 5–12%. Filter: ≥30 trades AND MDD > −50%.

### Best backtest metrics (SOLUSDT, 2020–2026 — only passing combination)

| Metric | Value |
|---|---|
| Annual return | +27.7% |
| Max drawdown (MtM) | −49.9% |
| Sortino | 0.668 |
| Profit factor | 1.546 |
| Win rate | 37.2% |
| Trades | 172 |

### Why rejected

Only 1 of 1,232 ADX combinations survived the ≥30 trades / MDD > −50% filters. A strategy with only one viable parameter set is fragile by definition — no stable plateau exists. Additionally: (1) annual return +27.7% is well below SOL buy-and-hold (≈+125%/yr from Jan 2020); (2) Sortino 0.668 is below the 0.8 quality threshold; (3) MDD of −49.9% at the boundary of the −50% filter indicates the strategy barely survives the minimum acceptability criterion.

### Reopen conditions

None — permanently closed for SOL. ADX trend-following on SOL does not produce a viable edge. If ADX is revisited on SOL at any point, it should be with a materially different signal construction, not a parameter re-sweep of the same framework.

### Links

- `06_BACKTESTS/Week_8_Notebooks/sol_grid_search.py`
- `06_BACKTESTS/Week_8_Notebooks/sol_grid_results.csv`

---

## S008 — SOL Supertrend (Rejected)

**Status:** Rejected
**Rejection stage:** Discovery grid (Week 8)
**Date closed:** 2026-05-19
**Tested in:** Week 8

### Parameters tested

70 combinations: ATR period 7–20, multiplier 2.0–4.0 (step 0.5). Filter: ≥30 trades AND MDD > −50%.

### Best backtest metrics

No combinations passed both filters. 0 of 70 combinations appear in sol_grid_results.csv.

The two likely failure modes: (1) wide ATR multipliers produce insufficient trade count (<30 trades in 6.3 years); (2) tight ATR multipliers produce trades with MDD exceeding −50% on SOL's high-volatility daily candles. SOL's price history (2020–2026) includes moves of −95% (2022 bear market) that stress-break any Supertrend configuration at reasonable multipliers.

### Why rejected

Zero viable parameter combinations on SOL in a 70-combination grid is a decisive negative result. Supertrend on SOLUSDT daily candles does not produce a viable trading edge under the minimum standards of this curriculum.

### Reopen conditions

None for SOL daily candles. Supertrend has not been tested on ETH or BTC — could be investigated there in a future week as part of indicator comparison research (SI010).

### Links

- `06_BACKTESTS/Week_8_Notebooks/sol_grid_search.py`

---

## S009 — SOL Donchian Channel Breakout (Rejected)

**Status:** Rejected
**Rejection stage:** Discovery grid (Week 8)
**Date closed:** 2026-05-19
**Tested in:** Week 8

### Parameters tested

77 combinations: entry period 10–40 (step 5), exit period 10–60 (step 5). Filter: ≥30 trades AND MDD > −50%.

### Best backtest metrics

No combinations passed both filters. 0 of 77 combinations appear in sol_grid_results.csv.

### Why rejected

Donchian breakout on SOL generated either too few trades (wide channels on a volatile asset produce infrequent breakouts) or excessive drawdown in bear market periods. SOL's 2022 decline (approximately −95%) is likely the primary driver of MDD filter failures for most configurations. Unlike Keltner which uses ATR-based adaptive bands, fixed-period Donchian channels cannot adapt to volatility expansion during a sustained crash.

Note: Donchian breakout on ETH and BTC daily has not been tested. The WEEK_7_RESEARCH_BRIEF_FULL.md identified Donchian as Priority 1 for Week 7 — this work was not completed. The SOL rejection does not imply the same result on ETH/BTC.

### Reopen conditions

Test Donchian on ETH and BTC (Week 9+ backlog — see SI010). SOL Donchian on daily candles: permanently closed.

### Links

- `06_BACKTESTS/Week_8_Notebooks/sol_grid_search.py`

---

## S010 — SOL Bollinger Bands Mean Reversion (Rejected)

**Status:** Rejected
**Rejection stage:** Discovery grid (Week 8)
**Date closed:** 2026-05-19
**Tested in:** Week 8

### Parameters tested

55 combinations: BB period 15–25, std 1.5–2.5 (step 0.25), fixed 15% stop. Filter: ≥30 trades AND MDD > −50%.

### Best backtest metrics

No combinations passed both filters. 0 of 55 combinations appear in sol_grid_results.csv.

### Why rejected

Mean reversion on SOL daily candles does not survive the minimum viability filters. SOL's higher volatility relative to ETH and BTC means price can move far below the lower Bollinger band and stay there during bear markets — a structure that destroys mean reversion strategies. The 2022 SOL decline (−95%) would produce a cascade of stop-outs that drives MDD well below −50% for any reasonable parameter set. Additionally, SOL's shorter history (data from 2020 only — vs 2018 for ETH/BTC) means there is less data for parameter fitting.

The ETH Bollinger strategy (S003) was tested on a longer and less volatile base asset — that context does not transfer to SOL.

### Reopen conditions

None for SOL. Bollinger mean reversion remains a valid research direction for ETH (S003) and possibly BTC if combined with a regime filter (ADX<20).

### Links

- `06_BACKTESTS/Week_8_Notebooks/sol_grid_search.py`

---

---

## S011 — BNB Donchian Channel Breakout SMA-120 (Deferred — CONDITIONAL GO)

**Status:** Deferred — CONDITIONAL GO, Phase 6 in progress
**Rejection stage:** Not rejected — deployment pending independent review and bot build
**Date approved:** 2026-06-01 (Phases 0–5 signed off; Phase 6 in progress)
**Tested in:** Week 9

### Parameters tested

| Stage | Parameters |
|---|---|
| Discovery grid | 148-combination grid: 5 indicator families (ADX, Supertrend, Donchian, Keltner, Bollinger) on BNB-USD 2018–2026 |
| Donchian hard-filter scan | 23 Donchian combinations passed B&H-exception-adjusted filters |
| Top candidates | per=20/stop=5% and per=60/stop=5% proceeded to walk-forward |
| **Deployed (per=20)** | **period=20, stop=5% trailing, SMA-120 regime filter (Exit A)** |

### Best backtest metrics (BNB-USD, 2018–2026, ~8.4 years, SMA-120 filter)

| Metric | Value |
|---|---|
| Annual return | +28.3% |
| Max drawdown (per-trade) | −24.1% |
| Max drawdown (MtM) | −29.7% |
| Sortino | 0.843 |
| Profit factor (full) | 2.696 |
| Profit factor (post-break Jan 2024) | 2.961 |
| Win rate | 43.2% (full); 47.4% post-break |
| Trades | 74 |
| B&H MDD | −80.1% (B&H exception applies — see METHODOLOGY_STANDARDS.md) |
| Substitute gates | Sortino > 0.8 ✅ + MDD < 50% ✅ — PASS |

Walk-forward: 9/13 OOS windows profitable (PF > 1). Stability: STABLE — 26/42 post-break combinations with PF > 2.0 (62%).

### Why conditional GO (not rejected)

Full 5-phase validation complete. Post-break PF 2.961 exceeds 2.0 threshold. B&H MDD exception formally applied and documented (RR-BNB-007). Half-Kelly permission granted with 2022 bear market evidence (RR-BNB-006). Two process items remain before live capital: independent red team review and bot build.

### Outstanding deployment conditions

1. Independent red team review (fresh Claude session) — LIVE_TRADING_CHECKLIST.md Section 0
2. Bot build and EC2 deployment
3. Phase 6 sign-off

### Links

- `01_RISK_REGISTERS/RISK_REGISTER_BNB_DONCHIAN.md`
- `03_DEPLOYMENT_CARDS/BNB_DONCHIAN_DEPLOYMENT_CARD.md`
- `06_BACKTESTS/Week_9_Notebooks/` — all backtest scripts and result CSVs
- `06_BACKTESTS/Week_9_Notebooks/charts/` — seven interactive HTML charts
- Risk register items: RR-BNB-001 through RR-BNB-007

---

## S012 — BNB Donchian per=60/stop=5% (Rejected — Insufficient Evidence)

**Status:** Rejected
**Rejection stage:** Walk-forward validation (Week 9) — OOS median PF below 1.0
**Date closed:** 2026-06-01
**Tested in:** Week 9

### Parameters tested

Donchian period=60, stop=5% trailing — second-ranked combination from BNB hard-filter scan.

### Why rejected

Walk-forward OOS median PF = 0.421 (below 1.0 breakeven). In 13 walk-forward windows, the strategy showed inconsistent OOS performance without the clear profitable pattern of the per=20 variant. Regime break post-break PF was 2.659 (viable on full post-break aggregate) but window-by-window consistency was insufficient. The per=20 combination dominates on all deployment metrics.

### Reopen conditions

Not worth reopening while per=20 is deployed. If per=20 live performance is disappointing, revisit wider Donchian period grid. Would require at least 5 post-break OOS windows with PF > 1.0 to re-qualify.

### Links

- `06_BACKTESTS/Week_9_Notebooks/bnb_walkforward_results.csv`

---

## S013 — AVAX Keltner Channel EMA=15/mult=2.0 (Rejected)

**Status:** Rejected
**Rejection stage:** Regime break analysis (Week 9) — post-break PF 1.413, insufficient edge
**Date closed:** 2026-06-01
**Tested in:** Week 9

### Parameters tested

Multi-asset discovery grid (01_altcoin_discovery_grid.py): Keltner Channel, multiple EMA/multiplier combinations on AVAX-USD. Best result: EMA=15, multiplier=2.0.

### Best backtest metrics (full period)

Single combination passed hard-filter scan with B&H-exception-adjusted gates.

### Why rejected

Post-break regime break analysis: PF 1.413 (post-Jan 2024). This falls in the "edge compressed" range (1.0–2.0) where METHODOLOGY_STANDARDS.md requires caution and reduced sizing — it does not clear the 2.0 threshold required for a full deployment case. Win rate declined from 53% pre-break to 33% post-break — a meaningful structural deterioration. With only 1 qualifying combination in the discovery grid, the strategy also lacks the parameter stability needed for a CONDITIONAL GO.

### Reopen conditions

Wider parameter grid producing 3+ combinations with post-break PF > 2.0. Do not reopen on the basis of single-combination results. Post-break sample must reach ≥ 30 trades before the PF estimate is reliable.

### Links

- `06_BACKTESTS/Week_9_Notebooks/01_altcoin_discovery_grid.py`
- `06_BACKTESTS/Week_9_Notebooks/altcoin_discovery_results.csv`
- `00_MASTER/STRATEGY_IDEAS_LOG.md` (individual failure notes)

---

## S014 — LINK Trend-Following (Rejected)

**Status:** Rejected
**Rejection stage:** Discovery grid (Week 9) — zero hard-filter passes
**Date closed:** 2026-06-01
**Tested in:** Week 9

### Why rejected

LINK (LINKUSDT) produced zero passing combinations across all indicator families in the multi-asset discovery grid. Primary failure mode: LINK's high volatility generates wide ATR and large intraday candles that blow through 5–12% fixed stops before the trend can develop. No indicator family found a stop distance that simultaneously controls MDD and generates enough trades to pass the 30-trade minimum.

### Reopen conditions

Evidence of structural volatility reduction in LINK (e.g., post-futures-ETF stabilisation, higher market cap diluting volatility). Would need at least 5 combinations clearing hard filters. See STRATEGY_IDEAS_LOG.md for detailed failure notes.

### Links

- `06_BACKTESTS/Week_9_Notebooks/01_altcoin_discovery_grid.py`
- `00_MASTER/STRATEGY_IDEAS_LOG.md`

---

## S015 — DOT Trend-Following (Rejected)

**Status:** Rejected
**Rejection stage:** Discovery grid (Week 9) — best result below quality threshold
**Date closed:** 2026-06-01
**Tested in:** Week 9

### Why rejected

DOT (DOTUSDT) is in a structural downtrend from its 2021 ATH. The best discovery grid result achieved Sortino 0.49 — below the 0.8 quality threshold. Trend-following cannot sustainably generate edge when the asset has no sustained uptrends to follow. The SMA-120 regime filter would block most entry signals during DOT's prolonged decline, resulting in very few trades and near-zero returns. No meaningful optimisation target exists in the current market structure.

### Reopen conditions

DOT price recovery above a multi-year SMA (e.g., 200-day SMA) sustained for 6+ months, combined with post-recovery discovery grid showing ≥ 5 combinations with Sortino > 0.8. See STRATEGY_IDEAS_LOG.md for details.

### Links

- `06_BACKTESTS/Week_9_Notebooks/01_altcoin_discovery_grid.py`
- `00_MASTER/STRATEGY_IDEAS_LOG.md`

---

## S016 — MATIC Trend-Following (Rejected)

**Status:** Rejected
**Rejection stage:** Discovery grid (Week 9) — B&H floor eliminates all candidates
**Date closed:** 2026-06-01
**Tested in:** Week 9

### Why rejected

MATIC (now POL) produced discovery grid combinations that technically passed internal filters but could not clear the B&H benchmark gate. MATIC's 2020–2021 bull run was so extreme (from fractions of a cent to ~$2.50+) that its buy-and-hold annual return sets a gate that no actively managed strategy can match — even using the B&H MDD exception framework. The B&H MDD for MATIC exceeds −60%, but the 1.5× annual return gate (even suspended) is replaced by Sortino > 0.8 + MDD < 50%, and no discovered combination clears both substitute gates reliably post-break. Additionally, the MATIC → POL rebrand introduces structural uncertainty in the asset itself.

### Reopen conditions

POL (former MATIC) price history normalisation — after several years where the 2020–2021 outlier is sufficiently diluted by subsequent price action. Would require fresh discovery grid with at least 3 post-break combinations clearing substitute gates. See STRATEGY_IDEAS_LOG.md for details.

### Links

- `06_BACKTESTS/Week_9_Notebooks/01_altcoin_discovery_grid.py`
- `00_MASTER/STRATEGY_IDEAS_LOG.md`

---

## Strategies Planned But Not Yet Backtested

The following strategies have been formally proposed and prioritised but do not yet have documented backtest results. They are listed here to prevent duplication and to record when they were proposed.

| Strategy | Asset | Proposed in | Priority | Notes |
|---|---|---|---|---|
| Donchian Channel Breakout | ETH, BTC | Week 7 Research Brief | Week 9+ | Priority 1 in Week 7 brief — not executed on ETH/BTC. SOL rejected (S009). BNB executed (S011). |
| MAX Strategy (N-day high continuation) | BTC | Week 7 Research Brief | Week 9+ | Peer-reviewed evidence (Quantpedia 2024), out-of-sample through 2024. Combine with MIN for best results. |
| MIN Strategy (N-day low bounce) | BTC | Week 7 Research Brief | Week 9+ | Run together with MAX. Avoid buy-at-minimum version (>80% MDD). |
| Bollinger Bands | BTC | Week 7 Research Brief | Week 9+ | Untested on BTC. QuantifiedStrategies ~50% CAGR at 34% market exposure. |
| MACD + 200MA filter | BTC, ETH | Week 7 Research Brief | Week 8+ | Weaker evidence than Donchian/MAX. Test after higher-priority strategies. |
| Z-Score deviation | ETH | Week 7 Research Brief | Week 8–9 | Long-only single-asset version only (BTC-neutral requires shorting). |
| Supertrend | ETH, BTC | Week 7 Research Brief | Week 9+ | Not tested on ETH/BTC. SOL result (S008) is not transferable. |
| ADX regime-switching portfolio | ETH | SI012 | Week 9–10 | Pair ADX trend bot (ADX>20) with Bollinger mean reversion bot (ADX<20) on same asset. |
| BTC regime-switching: SMA vs ADX | BTC | SI003 | Week 9+ | Classifier to weight between BTC SMA and BTC ADX by regime. Requires both live first. |

---

*Archive version 1.0 — created 2026-05-20*
*Archive version 1.1 — updated 2026-06-01: S011–S016 added (Week 9 BNB and altcoin results)*
*Archive version 1.2 — updated 2026-06-22: S002 Sortino corrected from stale 1.205 to authoritative 0.307 (daily equity curve method, stage5_final_comparison.py). See RR-RSI-011.*
*Update at each GO/NO-GO decision and at end of each week.*
