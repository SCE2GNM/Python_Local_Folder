# Week 10 Thread Starter
## DeFi Quant Engineer Curriculum
**Student:** Greg (Gmac)
**Week:** 10 of 24
**Dates:** 2026-06-02 to 2026-06-08 (est.)
**Preceding summary:** 04_WEEKLY_SUMMARIES/WEEK_9_SUMMARY.md

---

## Week 9 Context — What Week 10 Needs to Know

### Strategy status coming in

- **ETH ADX (Live — $1,000 capital):** Regime break confirmed at ETH ETF approval May 2024. PF 2.947→1.689 post-ETF; win rate 44.3%→35.1%. Strategy remains live — edge compressed, not destroyed. Leverage deployment deferred to Weeks 16–18 pending post-ETF sample reaching 80 trades. Open items A023 (Phase 3B exit method comparison) and A024 (Phase 3C regime filter) — both scheduled Weeks 16–18.
- **ETH RSI (Validation — $150 capital):** RR-RSI-005 and RR-RSI-006 resolved (STABLE, both closed Week 9). Open High items: RR-RSI-001 (win rate sensitivity), RR-RSI-002 (stop order monitoring), RR-RSI-003 (Kelly sizing). Capital scaling to $341 blocked pending RR-RSI-008 (Phase 3D joint optimisation — before capital scaling).
- **BTC SMA 110/30% (CONDITIONAL GO — not deployed):** Phase 5 leverage analysis now three consecutive weeks outstanding. BS009 (Phase 3B exit comparison) and BS010 (Phase 3C regime filter) also required before deployment card can be finalised. **This must not slip to Week 11.**
- **BNB Donchian per=20/stop=5%/SMA-120 (Phase 6 — in progress):** Phases 0–5 complete. Post-break PF 2.961, STABLE grid, 9/13 walk-forward windows profitable. Deployment card written. **Two items block live capital: (1) independent red team review, (2) bot build and EC2 deployment.**
- **SOL (All strategies rejected):** SOL daily trend-following closed as a research direction.
- **LINK, DOT, MATIC, AVAX (Rejected):** All closed Week 9. No reopen conditions likely in the near term.

### Process improvements added in Week 9 — apply from Week 10 onwards

**Pipeline Phase Gate Standard (METHODOLOGY_STANDARDS.md):**
Every risk register must contain a Phase 0–6 table. Check the table at session start. Do not begin Phase N+1 work if Phase N is not signed off. If a phase is skipped, record written justification before proceeding.

**B&H Exception Rule (METHODOLOGY_STANDARDS.md):**
When an asset's buy-and-hold MDD exceeds −60%, the annual return gate and Sortino gate are both suspended. Substitute gates: Sortino > 0.8 AND MtM MDD better than −50%. The MDD gate is never suspended.

**Phase 3A–3E Mandatory Optimisation Sequence (STRATEGY_RESEARCH_PIPELINE.md v2.0):**
For every new strategy: (A) entry parameters, (B) exit method comparison, (C) regime filter test, (D) joint optimisation, (E) Monte Carlo. Mandatory order. Do not select exit method before testing entry parameters.

---

## Phase 0 — Research Opening Sequence

Before any backtest work begins this week, search the following topics and summarise findings in a Phase 0 note. Relevant findings should be incorporated into strategy design decisions where applicable.

### Search Topics for Week 10

**Topic 1 — BNB Donchian post-2024 evidence**
Search: "BNB Donchian breakout strategy parameters 2024 2025 post-institutional"
Objective: Any academic or practitioner evidence on Donchian channel parameters for BNB specifically post-2024. Does the 20-day period have theoretical support? Are there published results from the institutional adoption era?

**Topic 2 — BTC SMA leverage optimisation**
Search: "BTC SMA crossover leverage optimisation trend-following daily candles"
Objective: Academic guidance on applying leverage to low-frequency SMA crossover strategies. What leverage levels have been studied? What is the theoretical Kelly-optimal leverage for a strategy with annual return ~55% and MDD ~30%?

**Topic 3 — Dynamic leverage design for daily trend-following**
Search: "dynamic leverage trend strength ADX ATR momentum scaling daily strategy crypto"
Objective: Standard approaches for scaling leverage with trend strength. ADX-based, ATR-based, momentum-based — which has the best academic support? METHODOLOGY_STANDARDS.md requires dynamic leverage (not fixed) for all leveraged strategies from Week 8 onwards. The BTC SMA leverage design must use one of these frameworks.

**Topic 4 — Telegram bot multi-strategy health check design**
Search: "Telegram trading bot health check alert fatigue multi-strategy monitoring"
Objective: Best practices for health check message design when monitoring multiple strategies simultaneously. Alert fatigue prevention. Consolidated vs per-strategy messages. II-001 has been outstanding for four weeks — this research should directly inform the redesign.

**Topic 5 — Walk-forward optimisation vs fixed parameters**
Search: "walk-forward optimisation fixed parameters crypto daily strategy overfitting"
Objective: When does per-window re-optimisation add value vs introduce overfitting in the OOS sample? Academic evidence for daily crypto strategies with low trade frequency (4–12 trades/year). This is directly relevant to BTC SMA and BNB Donchian walk-forward interpretation.

---

## Week 10 Priority Task List — In Order

**Priority 1 — BNB Donchian pre-deployment analysis (three blockers, in order)**

Status: Phase 6 BLOCKED. Deployment card written. Three items must be resolved before bot build begins. See RISK_REGISTER_BNB_DONCHIAN.md RR-BNB-008, RR-BNB-009, RR-BNB-010.

**Step A — Separate upper/lower band optimisation (RR-BNB-008) — do first**

Run a grid of entry period × exit period combinations:
- Entry periods: 15, 20, 25, 30
- Exit periods: 5, 10, 15, 20 (exit period must always be ≤ entry period)
- Report for each combination: full-period PF, post-break PF (Jan 2024), Sortino, trade count, MtM MDD

The standard Donchian/Turtle Trading framework uses different entry and exit periods deliberately — a longer entry period filters false breakouts; a shorter exit period tightens the trailing channel. The symmetric period=20/20 assumption has never been validated against separate-period alternatives.

If the best separate-band combination materially outperforms period=20/20 on post-break PF, it becomes the new deployed configuration and the full Phase 3–5 validation pipeline must be re-run on it. If period=20/20 is confirmed optimal by the grid, document the evidence and close RR-BNB-008.

**Step B — Full trailing stop range comparison (RR-BNB-009)**

After Step A confirms the best entry/exit-period configuration, test additional trailing stop variants:
- ATR multipliers: 1.5×, 2.5×, 3.0× (2.0× was already tested in Phase 3B)
- EMA periods: 30, 50 (20 was already tested)
Compare post-break PF only. If any variant outperforms the current fixed 5% trailing stop on post-break PF with MDD better than −50%, adopt it. Otherwise confirm Exit A (channel + 5% trail) and close RR-BNB-009.

**Step C — Independent red team review (RR-BNB-010) — after Steps A and B are complete**

Conduct the mandatory independent review in a fresh Claude Sonnet session with no development context. The session must not have seen the backtest scripts or the sessions that built them.

Brief the reviewer with the final validated parameters (from Steps A and B), full backtest results, deployment card, risk register, METHODOLOGY_STANDARDS.md, and LIVE_TRADING_CHECKLIST.md.

**Critically: frame the review as an attack, not a validation.** The exact brief to include:

> *"You are reviewing this strategy as a sceptic. Your job is to find reasons not to deploy capital. Look for: overfitting, data mining bias, unrealistic assumptions, risks not captured in the register, edge cases that could cause large losses, bot implementation risks, and anything else that gives you pause. Do not be polite about problems — flag them clearly with severity (CRITICAL / MAJOR / MINOR)."*

This framing produces a materially more useful review than asking Claude to assess whether the strategy is good. Every strategy looks good to the person who built it.

All CRITICAL findings must be resolved before deployment. MAJOR findings must be resolved or formally accepted. Save output as REVIEW_BNB_DONCHIAN_[DATE].md.

**Step D — Bot build and EC2 deployment (only after Steps A–C complete)**

Build 05_BOTS/bnb_donchian_bot.py per BNB_DONCHIAN_DEPLOYMENT_CARD.md Section 9:
- Signal at 00:07 UTC daily (after ETH ADX at 00:05, ETH RSI at 00:06)
- Stop order type: STOP_LOSS (market — per METHODOLOGY_STANDARDS.md)
- Stop verification: verify_stop_order() on every run
- State file: 05_BOTS/data/bnb_donchian_state.json
- Performance log: 05_BOTS/data/bnb_donchian_live_performance_log.csv
- Telegram alerts: entry, exit (with type and return), daily health check

Test on Binance testnet before live. Confirm cron active at 00:07 UTC. Update Phase 6 status to Complete and sign off in RISK_REGISTER_BNB_DONCHIAN.md only after testnet validation passes.

---

**Priority 2 — BTC SMA Phase 5 leverage analysis (mandatory — third deferral)**

Status: CONDITIONAL GO signed. Phase 5 leverage analysis not yet complete. BS009 (Phase 3B exit method comparison) and BS010 (Phase 3C regime filter test) also required per Phase 3A–3E standard before deployment card can be finalised.

**This has been deferred for three consecutive weeks. It must not be deferred again.**

Sequence:
1. **BS009 — Phase 3B exit comparison:** Test fixed stop (current 30%), ATR trailing, and pct trailing on SMA110/T30% parameter set. Compare post-break PF. Confirm current exit is optimal or identify better alternative.
2. **BS010 — Phase 3C regime filter test:** Test SMA-50, SMA-100, no filter as alternatives to the implicit uptrend gate in the current SMA crossover signal.
3. **Phase 5 leverage grid:** 1.0×–3.0× leverage on confirmed best exit and filter. Dynamic leverage mapping from SMA strength indicator (or ATR-based) as required by METHODOLOGY_STANDARDS.md dynamic leverage standard. Rank by Calmar ratio after borrowing costs. Safety buffer: minimum margin ratio ≥ 25% at all tested leverage levels.
4. **Deployment card:** Write BTC_SMA_DEPLOYMENT_CARD.md using the same template as BNB_DONCHIAN_DEPLOYMENT_CARD.md.

---

**Priority 3 — ETH ADX A023/A024 (schedule, do not execute)**

A023 (Phase 3B exit comparison) and A024 (Phase 3C regime filter) for ETH ADX are the same Phase 3A–3E gaps identified for BTC SMA and ETH RSI. However, ETH ADX is already live and performing within acceptable parameters. These analyses should be scheduled for Weeks 16–18 alongside the leverage deployment review (when post-ETF sample reaches 80 trades). Do not begin this analysis in Week 10 — the leverage review window is the natural point to also complete the Phase 3B/3C work.

**Action this week:** Record A023 and A024 in RISK_REGISTER_ETH_ADX.md with target "Weeks 16–18 — alongside leverage deployment review" if not already present.

---

**Priority 4 — II-001 Telegram health check redesign (four weeks outstanding)**

Status: Outstanding since Week 7. Applies to both day5_production_bot.py and rsi_production_bot.py (and will apply to bnb_donchian_bot.py when built).

Design principle (from LEARNING_LOG.md Week 9 — Telegram Monitoring Design): every number in the health check message must be self-contained with its threshold visible. No cross-referencing the codebase to interpret a message received at 3am.

Required message format (for each strategy, at minimum):
- Current position state (LONG/FLAT) and reason if FLAT
- Each signal component with its current value AND threshold
- Stop order status (if LONG): current stop price, stop order ID, verification result
- Running performance: win rate, consecutive losses, portfolio value

Implement for all three bots before any of the capital scaling reviews are conducted.

---

**Priority 5 — Update revision notes PDF for Week 9**

Add Week 9 content to the PDF revision notes. Key additions:
- B&H Exception Rule (new methodology standard)
- Phase Gate Checklist standard
- Phase 3A–3E mandatory sequence
- BNB Donchian validation results
- Altcoin discovery grid results (LINK/DOT/MATIC/AVAX rejection rationale)

---

## Open Risk Register Items Coming Into Week 10

| Item | Register | Priority | Status |
|---|---|---|---|
| RR-BNB-001 | RISK_REGISTER_BNB_DONCHIAN.md | Medium | Monitoring — watch first 10 live trades |
| RR-BNB-004 | RISK_REGISTER_BNB_DONCHIAN.md | Low | Leverage deferred — reopen after 10+ live profitable trades |
| RR-RSI-001 | RISK_REGISTER_ETH_RSI.md | High | Win rate sensitivity — blocks capital deployment |
| RR-RSI-002 | RISK_REGISTER_ETH_RSI.md | High | Stop order monitoring absent — blocks capital deployment |
| RR-RSI-003 | RISK_REGISTER_ETH_RSI.md | High | Kelly fraction — blocks capital deployment |
| RR-RSI-008 | RISK_REGISTER_ETH_RSI.md | Medium | Phase 3D joint grid — required before capital scaling |
| RR-RSI-009 | RISK_REGISTER_ETH_RSI.md | Low | Resolved implicitly when RR-RSI-008 complete |
| BS009 | RISK_REGISTER_BTC_SMA.md | High | Phase 3B exit comparison — must precede Phase 5 |
| BS010 | RISK_REGISTER_BTC_SMA.md | High | Phase 3C regime filter — must precede Phase 5 |
| BTC SMA Phase 5 | RISK_REGISTER_BTC_SMA.md | High | Third deferral — Week 10 is final deadline |
| A022 | RISK_REGISTER_ETH_ADX.md | In Progress | Leverage deployment review — Weeks 16–18 |
| II-001 | Infrastructure | Medium | Telegram health check — four weeks outstanding |

---

## Capital Status Coming Into Week 10

| Strategy | Status | Capital | Notes |
|---|---|---|---|
| ETH ADX | Live | $1,000 | Trailing stop active; regime break confirmed; leverage deferred Weeks 16–18 |
| ETH RSI | Validation | $150 | Scale to $341 blocked (RR-RSI-001, RR-RSI-002, RR-RSI-003 still open) |
| BTC SMA 110/30% | Conditional GO | $500 reserved | Phase 5 leverage analysis and deployment card required before deployment |
| BNB Donchian | Phase 6 pending | $150 reserved | Independent review + bot build required before deployment |

**Total capital reserved for deployment pending approvals:** $650 ($500 BTC SMA + $150 BNB Donchian)

---

*Week 10 Thread Starter v1.0*
*Prepared: 2026-06-01 (Week 9 close-out)*
