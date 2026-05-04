# Curriculum Operating Manual
## DeFi Quant Engineer Curriculum
**Student:** Greg (Gmac)
**Version:** 1.0
**Created:** Week 6, 2026-05-04
**Purpose:** Standard operating procedure for 
every week of the curriculum. Read this before 
starting any new chat thread or Claude Code session.

---

## What This Document Is

This is the meta-document that explains how the 
curriculum works in practice. It does not change 
week to week. It describes the tools, documents, 
workflows, and decision frameworks that apply to 
every week from Week 6 onwards.

Week-specific context (current live strategies, 
open risk items, weekly goals) lives in the 
week's thread starter file, not here.

---

## The Two Tools and When to Use Each

**Claude Chat (this interface)**
Use for: strategy decisions, research, concept 
explanations, interpreting results, go/no-go 
decisions, drafting document content.
Do NOT use for: writing code, running backtests, 
creating files, updating documents.

**Claude Code (terminal)**
Use for: writing and running Python scripts, 
creating and updating all project files, running 
backtests, committing to GitHub.
Do NOT use for: strategy decisions, research, 
or anything requiring judgment.

The workflow is always: decide in chat, execute 
in Code. Never let Claude Code make strategic 
decisions autonomously.

---

## How to Start a New Week

**Step 1 — Two to three days before the week:**
Conduct the research phase in Claude Chat.
Ask Claude to search for academic papers, 
practitioner research, and crypto-specific 
sources covering the week's planned strategies.
Produce WEEK_[N]_RESEARCH_BRIEF.md.
Save to project root via Claude Code.

**Step 2 — Start of week, Claude Chat:**
Open new chat thread.
Paste in this order:
1. Opening: "Read these documents for context"
2. The current week's thread starter file content
3. The research brief content
4. Your specific opening question or instruction

**Step 3 — Start of week, Claude Code:**
```bash
cd /Users/Greg/Documents/Python_Local_Folder/
Python_Quant_Researcher
source venv/bin/activate
claude
```
First message to Claude Code:
"Read WEEK_[N]_THREAD_STARTER.md and 
WEEK_[N]_RESEARCH_BRIEF.md for full context. 
We are starting Week [N]. Begin with [first task]."

---

## The Standard Strategy Research Pipeline

Every strategy follows these six phases in order.
Never skip phases or change their order.
Full detail in STRATEGY_RESEARCH_PIPELINE.md.

**Phase 0:** Pre-week research brief
**Phase 1:** Discovery and logic check
**Phase 2:** Initial backtest with realistic figures
**Phase 3:** Optimisation, validation, and 
preliminary leverage screen
**Phase 4:** Strategy comparison and selection
**Phase 5:** Stress testing (three layers)
**Phase 6:** Deployment decision and documentation

Key principle: Phases 2-4 use realistic figures 
throughout. Phase 5 applies conservative stress 
assumptions. Never mix them.

---

## Realistic vs Conservative Figures

**Realistic figures (Phases 2-4):**
Stop slippage: 0.1%
Liquidation slippage: 0.25%
Transaction costs: 0.15% round-trip
Interest rate: current confirmed Binance rate

**Conservative stress figures (Phase 5 only):**
Stop slippage: 0.25%
Liquidation slippage: 0.5%
Transaction costs: 0.30% round-trip (doubled)

**Hard constraints (always apply):**
Safety buffer ≥ 33% (working minimum)
Safety buffer ≥ 25% (hard floor veto)
Zero liquidation events at recommended leverage

---

## Leverage Optimisation — Joint Approach

From Week 7 onwards, leverage screening is 
integrated into Phase 3, not a separate phase.

After identifying top 20 strategy combinations 
by 1x annual return:
1. Run coarse leverage screen (1.0x to 3.0x, 
   0.5x steps) for all top 20
2. Re-rank by best achievable leveraged return
3. If ranking unchanged: sequential approach 
   was correct, proceed
4. If ranking shifts: run full leverage grid 
   (1.0x to 5.0x, 0.1x steps) for top 3 only

Rationale: low MaxDD and high Sortino are 
leverage multipliers. The 1x winner is not 
always the leveraged winner.

---

## Metric Priority

**Primary:** Annual return % (after all costs)
**Quality filters:** Sortino > 0.8, 
  MaxDD disclosed and accepted
**Hard constraints:** Safety buffer, 
  zero liquidations
**Not primary:** Calmar ratio

Calmar is useful context but should never 
drive the deployment decision. Annual return 
is the objective; drawdown is a disclosed risk 
that the deployer accepts.

---

## Backtesting Requirements

Every backtest must include:
- 0.15% round-trip transaction costs per trade
- Bar-by-bar stop simulation using daily LOW prices
- Sortino from daily equity curve 
  (not per-trade method)
- Sharpe from daily equity curve
- Entry date captured at entry (not at exit)
- Both per-trade MaxDD AND daily MtM MaxDD reported
- Sample size (n trades) alongside every metric
- B&H relative check: annual ≥2x, MaxDD ≤50%, 
  Sortino ≥1.5x

Grid boundary check required on every optimisation:
Best result must not sit at the edge of the 
tested parameter range.

Cliff-edge check required on every sensitivity:
Chosen parameters must sit at the peak of the 
annual return curve, not on a declining slope.

---

## Charts — Standard Requirements

Every strategy must produce:
1. Interactive equity curve (Plotly HTML):
   Leveraged vs unleveraged vs B&H benchmark
   Log scale, daily MtM, entry/exit markers
   Drawdown panel as lines (not filled areas)
2. Year-by-year equity panels (one per year)
3. Parameter sensitivity plateau charts
4. Walk-forward results bar chart
5. Parallel coordinates (top 50 by annual return)
6. Trade return distribution histogram
7. Drawdown profile (underwater curve)

All charts interactive HTML. Static PNG 
acceptable for quick reference only.
Deployment document must embed all charts.

---

## Document Maintenance

**Updated continuously by Claude Code:**
- All strategy Risk Registers
- Learning Log
- Strategy Ideas Log
- Live Trading Checklist
- Strategy Research Pipeline

**Updated weekly (end of week):**
- Week [N] thread starter (created fresh)
- GitHub commit (all changes)

**Updated in Claude Project manually (weekly):**
- This operating manual (if changed)
- Live Trading Checklist (if changed)
- Strategy Research Pipeline (if changed)
- Current week's thread starter

**Never edited manually:**
Let Claude Code make all file changes. 
Only exception: Claude Project uploads.

---

## End of Week Checklist

Before closing any week:

1. All planned backtests complete
2. All Risk Register items reviewed and updated
3. Learning Log updated with week's concepts
4. Strategy Ideas Log reviewed for next week
5. All scripts committed to GitHub
6. Week [N+1] thread starter created
7. Week [N+1] research brief created
8. Claude Project documents updated
9. Any live deployments made with completed 
   deployment documents
10. Live Trading Checklist archived for 
    any new deployments

---

## Working Preferences

- Explain concepts before writing code
- One stage at a time — pause and report 
  between stages
- Flag risks explicitly rather than deferring
- Correct wrong assumptions directly
- Track all analysis for bulk log updates
- Return is the primary objective; drawdown 
  is a disclosed risk not a veto
- Conservative on leverage: 33% buffer minimum
- All decisions made in chat, executed in Code

---

## Key File Locations

**Project root:**
/Users/Greg/Documents/Python_Local_Folder/
Python_Quant_Researcher/

**EC2:**
15.134.135.221, ap-southeast-2 (Sydney)
Live bot: day5_production_bot.py
Cron: 00:05 UTC daily

**GitHub:**
SCE2GNM/execution-engine

**Key data files:**
data/trade_log_with_stoploss.csv (108 ETH ADX)
data/trade_log_rsi_final.csv (31 RSI trades)
data/stage1a_results.csv through stage4
WEEK_[N]_THREAD_STARTER.md (current week)
WEEK_[N]_RESEARCH_BRIEF.md (current week)

---

*Version 1.0 — created Week 6, 2026-05-04*
*Update this document when processes change.*
*Never update mid-week — only at week boundaries.*
