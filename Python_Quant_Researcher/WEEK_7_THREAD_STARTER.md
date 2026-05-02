# Week 7 Thread Starter
## DeFi Quant Engineer Curriculum
**Student:** Greg (Gmac)
**Week:** 7 of 24
**Dates:** TBD
**Status:** Planning — continuation from Week 6 (Stage 1 + Stage 2 complete)

---

## Context for Claude Code

This file provides full context for Week 7. Read this before doing anything else.

You are acting as Greg's quant curriculum tutor and technical collaborator. The teaching style is: explain concepts before writing code, one step at a time, honest assessment of weaknesses, all risks tracked in the Risk Register.

The project lives at:
`/Users/Greg/Documents/Python_Local_Folder/Python_Quant_Researcher/`

Python 3.12, virtual environment at `venv/`, VS Code, GitHub (SCE2GNM/execution-engine), AWS EC2 (15.134.135.221, ap-southeast-2).

---

## What is live and running

| Strategy | Asset | Capital | Status | Notes |
|----------|-------|---------|--------|-------|
| ADX 20/10 (fixed stop) | ETH | $1,000 | LIVE on EC2 | To be replaced by trailing stop version |
| RSI 14/43/48 | ETH | $500 | PENDING EC2 deployment | Deferred from Week 6 |

EC2 bot: `day5_production_bot.py` running via cron (00:05 UTC daily).
State file: `data/bot_state.json`
Log file: `/home/ubuntu/logs/adx_strategy.log`

---

## Week 6 Summary — What Was Accomplished

### Stage 1 — ETH ADX Trailing Stop Optimisation (complete)

**Stage 1a — Percentage trailing stop grid search**
- Grid: ADX threshold 15–22, ADX period 8–14, trail_pct 3–15%
- Best: ADX 19/9, trail 8% → Calmar 2.559, Sortino 1.870, Ann +80.2%, MaxDD −31.3%, 158 trades
- Results saved: `Week_6_Notebooks/results/stage1a_results.csv`

**Stage 1b — ATR trailing stop grid search**
- Grid: ADX threshold 15–22, ADX period 8–14, ATR period 7–21, multiplier 1.5–4.0
- Best: ADX 19/9, ATR 9, multiplier 2.5x → Calmar 2.642, Sortino 1.385, Ann +73.5%, MaxDD −27.8%, 123 trades
- Results saved: `data/stage1b_results.csv`

**Stage 1c — Stability analysis**
- Both candidates tested across year-by-year, half-split, and rolling windows
- Live baseline (ADX 20/10, fixed 5%): Calmar 1.645 (Week 5, pre-correction) → ~2.013 (corrected with 0.15% costs)
- ATR candidate 5/6 test years profitable; pct trail candidate similar
- Both trailing stop types robustly outperform fixed stop

**Stage 1d — Final comparison**
- Five strategies: LIVE (ADX 20/10 fixed), CAND_A (ADX 19/9 pct 8%), CAND_B (ADX 19/9 ATR 9/2.5x), LIVE-AT (ADX 20/10 ATR 9/2.5x), LIVE-PT (ADX 20/10 pct 8%)
- **Recommendation: Deploy ADX 19/9 + ATR 9/2.5x (CAND_B)** — Calmar 2.642, best MaxDD
- Conservative option: LIVE-AT (ADX 20/10 + ATR 9/2.5x) — Calmar 2.156, parameter change deferred
- A011 RESOLVED in RISK_REGISTER_ETH_ADX.md

### Stage 2 — BTC SMA Full Validation (complete → NO-GO)

| Stage | Status | Outcome |
|---|---|---|
| 2a — Grid search (SMA × trail%) | Complete | Best: SMA 120/25% (Ann 48.9%, Calmar 2.752) |
| 2b — ATR trail grid | Complete | ATR trail decisively weaker than pct trail on BTC |
| 2c — Stability analysis | Complete | MARGINAL (50.5% composite stability) |
| 2d — Walk-forward validation | Complete | 2/3 windows pass (2022 bear year fails) |
| 2e — ETH cross-asset check | Complete | **FAIL** — Sortino 0.505, MaxDD −67.7% on ETH |
| Final recommendation | **NO-GO** | Fallback: BTC ADX 19/14 (SI001) in Week 7 |

Key metrics — BTC SMA 120/25% (primary candidate):
- Ann +48.9%, Daily MtM MaxDD −30.5%, Per-trade MaxDD −17.8%
- Calmar 2.752, Sortino 1.246, 34 trades (2018–2026)
- 76.2% of total return from 2021 alone. Ex-2021: ~29%/yr
- Risk register: `RISK_REGISTER_BTC_SMA.md` (7 open items, all remain open pending NO-GO)

### Other Week 6 deliverables
- `LIVE_TRADING_CHECKLIST.md` updated with 8 new items (Sortino/Sharpe formula, exit mechanisms, grid boundary check, MaxDD labelling, cliff-edge check, walk-forward both methods, daily loss limit)
- `STRATEGY_IDEAS_LOG.md` created with SI001 (BTC ADX 19/14)
- `RISK_REGISTER_BTC_SMA.md` created (BS001–BS007)
- Interactive Plotly parallel coordinates chart: `Week_6_Notebooks/results/stage2_parallel_coordinates_interactive.html`
- `LEARNING_LOG.md` updated with Week 6 concepts

---

## Week 7 Priority Tasks

### PRIORITY 1 — Deploy ETH ADX trailing stop to live bot

**What needs doing:**
Update `day5_production_bot.py` on EC2 to replace fixed 5% stop with ATR 9/2.5x trailing stop. Update `bot_state.json` schema to track `peak_price_since_entry`. This is the deployment of the A011 resolution.

**Pre-deployment requirements (from RISK_REGISTER_ETH_ADX.md):**
1. Resolve A010 — remove daily loss limit or raise to 8–10% before trailing stop goes live
2. Decision on A015 — choose conservative (ADX 20/10 + ATR 9/2.5x) or primary (ADX 19/9 + ATR 9/2.5x)
3. Verify bot mechanics match stage1d backtest logic exactly
4. Test full trade cycle on Binance testnet with new trailing stop logic
5. Ensure Telegram alerts include trail stop trigger event
6. Confirm cron remains 00:05 UTC, check bot is healthy post-update

**Recommended path for A015:** Deploy ADX 19/9 + ATR 9/2.5x (primary recommendation). Rationale: the improvement is material (+0.629 Calmar), stage1c confirmed stability. Accept monitoring risk for first 20 live trades.

**Also deploy RSI bot (PENDING since Week 6):**
Build `rsi_production_bot.py` — separate script, own state file, own cron job (00:06 UTC), same Telegram bot. Params: period=14, oversold<43, exit>48, stop=15%, 120MA regime filter. Capital $500, position size 15%.

---

### PRIORITY 2 — BTC ADX 19/14 Full Validation (SI001)

This is the BTC SMA fallback strategy. ADX 19/14 was identified in Week 5 extension as the best BTC ADX configuration but was computed with two known errors:
1. **Wrong Sortino** — per-trade annualisation method (inflates 3–4×); must recalculate using daily equity curve
2. **No costs** — 0.15% round-trip was not applied; must be corrected

Week 5 extension results (uncorrected): ADX threshold 19, period 14, fixed 3% stop. Calmar 1.121. 100% stability. The corrected Calmar will be lower.

**Full validation plan (mirrors BTC SMA Stage 2 structure):**

**Stage A — Joint optimisation with trailing stop**
- Grid: ADX threshold 14–25, ADX period 8–18, trail_pct 3–20% (pct) AND ATR period 7–21, multiplier 1.5–4.0 (ATR)
- Apply 0.15% round-trip costs throughout
- Metrics: Calmar, Sortino (daily equity), Annual%, Daily MtM MaxDD, Per-trade MaxDD, Trades
- Minimum: 30 trades across full period
- Report best by composite score AND by annual return. Grid boundary check required.

**Stage B — Stability analysis**
- Vary each parameter independently ±3 steps from best
- Composite score ≥ 0.7 threshold
- Report STABLE / MARGINAL / FRAGILE

**Stage C — Walk-forward validation**
- Both expanding and rolling windows (3-year train, 1-year test: 2022, 2023, 2024)
- Fixed parameters (same note as BTC SMA: identical results for expanding/rolling with fixed params)
- Flag all cross-period trades explicitly
- Pass criterion: profitable in all 3 windows (or justify exceptions with 2022 bear-market rationale if applicable)

**Stage D — ETH cross-asset check**
- Apply BTC-optimised ADX params + trailing stop to ETH-USD
- Same metrics. Note ETH already has its own validated ETH ADX strategy — this is checking if the BTC-specific params transfer
- Pass criterion: Sortino ≥ 0.8, Calmar ≥ 1.0

**Final decision:** GO / NO-GO based on all four stages. If NO-GO, document reason and update SI001. If GO, create `RISK_REGISTER_BTC_ADX.md` and complete `LIVE_TRADING_CHECKLIST.md`.

---

### PRIORITY 3 — ETH ADX Leverage Optimisation (A013)

**Deferred from Week 6.** Now unblocked since A011 (trailing stop) is resolved.

Base strategy for leverage analysis: ADX 19/9 + ATR 9/2.5x (Stage 1d primary recommendation).

**Scope:**
- Leverage grid 1.0x–5.0x in 0.1x steps (41 levels)
- Interest: 0.015%/day on borrowed amount during position only
- Safety buffer: minimum historical margin ratio ≥25% (checked against daily LOW prices)
- Stop slippage: 2% below stop price; liquidation slippage: 3% below liquidation price
- Metrics: Calmar, Sortino, Annual%, MaxDD (daily MtM), minimum margin ratio, total interest cost

**Target outcome:** Recommended leverage level with Calmar maximised after interest, safety buffer confirmed, liquidation price documented.

Deferred to later in Week 7 (after trailing stop deployment and BTC ADX validation).

---

## Key Strategy Metrics (end of Week 6)

| Strategy | Annual | Max DD (MtM) | Calmar | Sortino | Trades | Status |
|----------|--------|--------------|--------|---------|--------|--------|
| ETH ADX 20/10 (fixed 5%) | ~67%* | −40.9% | 1.645* | 1.070* | 108 | Live (to be replaced) |
| ETH ADX 19/9 (pct 8%) | +80.2% | −31.3% | 2.559 | 1.870 | 158 | Validated, deploy |
| ETH ADX 19/9 (ATR 9/2.5x) | +73.5% | −27.8% | 2.642 | 1.385 | 123 | **Recommended** |
| BTC SMA 120/25% | +48.9% | −30.5% | 2.752 | 1.246 | 34 | NO-GO |
| BTC ADX 19/14 (uncorrected) | ~TBD | ~TBD | 1.121* | inflated* | TBD | SI001 — to validate |
| ETH RSI 14/43/48 | +16.9% | −16.0% | 1.054 | 0.265 | 31 | Pending EC2 deploy |

*Pre-correction figures. BTC ADX corrected metrics will be lower.

---

## Open Risk Register Items

### ETH ADX (`RISK_REGISTER_ETH_ADX.md`)

| ID | Description | Priority | Target |
|----|-------------|----------|--------|
| A003 | Slippage modelled as flat cost | Medium | After 10+ live trades |
| A009 | Walk-forward used fixed params (not true re-opt) | Medium | Week 8–10 |
| A010 | Daily loss limit not calibrated — must resolve before trailing stop deploy | Medium | **Week 7 (pre-deploy)** |
| A013 | ETH ADX leverage not optimised | High | Week 7 Stage 3 |
| A014 | RiskManager guardrails not calibrated | Medium | After trailing stop live |
| A015 | ADX 19/9 parameter change — deploy or defer? | Medium | **Week 7 decision** |

### BTC SMA (`RISK_REGISTER_BTC_SMA.md`)

All items (BS001–BS007) remain open. Strategy is NO-GO. No action required unless reconsidering BTC SMA in future.

---

## Important Technical Context

### File locations (Week 6 additions)

```
Week_6_Notebooks/
  stage1a_percentage_trailing.py      # ETH ADX pct trail grid search
  stage1b_atr_trailing.py             # ETH ADX ATR trail grid search
  stage1c_stability.py                # Trailing stop stability analysis
  stage1d_final_comparison.py         # Fixed vs pct vs ATR comparison
  stage2_btc_sma_validation.py        # BTC SMA Stage 2a main backtest
  stage2a_composite_analysis.py       # Stage 2a composite score analysis
  stage2a_extended_analysis.py        # Extended grid (wider SMA/trail range)
  stage2b_run.py                      # Stage 2b ATR trail on BTC SMA
  stage2c_stability.py                # Stage 2c stability (MARGINAL result)
  stage2d_walkforward_v2.py           # Stage 2d walk-forward (3 candidates)
  stage2e_eth_crossasset.py           # Stage 2e ETH cross-asset check (FAIL)
  stage2_analysis_suite.py            # Static charts from stage2a results
  stage2_parallel_interactive.py      # Plotly interactive HTML

Week_6_Notebooks/results/
  stage1a_results.csv                 # Stage 1a full grid results
  stage1a_heatmap.png
  stage1b_heatmap.png
  stage1d_equity_curves.png
  stage2_parallel_coordinates_interactive.html  # 171-strategy interactive chart
  stage2a_heatmap.png, stage2c_stability_heatmap.png, etc.

data/
  stage1b_results.csv                 # Stage 1b full ATR grid results
  stage2a_results.csv                 # BTC SMA Stage 2a results (3 metrics)
  stage2a_results_extended.csv        # Extended results (171 combos, 7 metrics)
  stage2b_results.csv                 # BTC SMA Stage 2b ATR results

RISK_REGISTER_BTC_SMA.md             # BTC SMA strategy risk register (7 open items)
STRATEGY_IDEAS_LOG.md                 # SI001: BTC ADX 19/14 pending validation
LIVE_TRADING_CHECKLIST.md             # Updated with 8 new items
```

### Key confirmed parameters

**ETH ADX (recommended deployment):**
- ADX threshold: 19, period: 9
- Stop: ATR period 9, multiplier 2.5x (percentage 8% as backup)
- Costs: 0.15% round-trip (0.075% each side)
- Signal: ADX > 19 AND +DI > −DI AND fresh crossover (not consecutive)
- Entry: next close after signal day
- Exit: signal reversal OR ATR stop (whichever fires first)

**BTC ADX (to be validated in Week 7, pre-correction):**
- ADX threshold: 19, period: 14 — needs trailing stop re-optimisation
- Previous uncorrected Calmar: 1.121. Corrected figure unknown until Stage A.

**ETH RSI (pending deployment):**
- period=14, oversold<43, exit>48, stop=15%, 120MA regime filter
- Capital: $500, position size: 15%

### Methodology reminders
- Daily equity curve for Sortino/Sharpe: `mean(daily_rets) / std(daily_rets[daily_rets < 0]) * sqrt(365)`
- Costs: `COST_PER_TRADE = 0.00075 * 2 = 0.0015` applied at each trade exit
- Stop checked against daily LOW (bar-by-bar simulation)
- Percentage trailing: `stop = peak_price × (1 − trail_pct)`, ratchets upward only
- ATR trailing: `stop = peak_price − (mult × ATR)`, ratchets upward only
- Grid boundary check: confirm best result does not sit at range edge
- Cliff-edge check: confirm annual return % peaks and plateaus before accepting params

---

## Capital Plan (post Week 7)

| Strategy | Capital | Leverage | Notes |
|----------|---------|----------|-------|
| ETH ADX 19/9 (ATR trail) | $1,000 | 1.0x → TBD | Replaces fixed-stop version |
| ETH RSI | $500 | 1.0x | Unchanged |
| BTC ADX (if validated) | $1,000 | 1.0x initially | Only if Stage A–D pass |
| ETH ADX (leveraged) | $1,500 | TBD | Pending A013 |
| Total | $3,500 | | |

Do not increase capital until A013 resolved. Leveraged version replaces unleveraged — not additive.

---

*End of Week 7 Thread Starter*
*Prepared: Week 6 final session (2026-05-02)*
*Next session: Use Claude Code to execute Week 7 priorities above*
