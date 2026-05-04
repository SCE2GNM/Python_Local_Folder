# Strategy Research Pipeline

This document defines the standard process for moving a strategy from idea to live deployment.
Each phase must be completed in order. Do not skip phases or merge them.

---

## Phase 0 — Pre-Week Research Brief

**Timing:** Conducted 2–3 days before the week starts (in Claude chat, not Claude Code).

**Purpose:** Ensure all backtesting starts from evidence-based parameter ranges rather than arbitrary grids. Saves computational time and focuses optimisation on productive regions.

### Sources to search (in order of quality)

1. **Academic papers:** SSRN, arXiv quant-fin, Journal of Portfolio Management
   - Search: `"[indicator] cryptocurrency returns"`, `"[strategy type] momentum bitcoin"`, `"[indicator] parameter optimisation equity"`

2. **Practitioner research:** QuantConnect research library, Quantpedia strategy database, Ernest Chan blog/books, Lopez de Prado papers

3. **Crypto-specific:** Glassnode research, The Block Research

4. **Community (lower priority):** QuantConnect forums, r/algotrading — filter heavily; prioritise posts with shared code and verified results over claims alone

### Research brief must answer for each strategy

1. What parameter ranges have the strongest empirical support in the literature?
2. What entry/exit conditions are supported?
3. What regime filters improve performance?
4. What are the known failure modes?
5. Has this been tested on crypto specifically?

### Output

Save as `WEEK_[N]_RESEARCH_BRIEF.md` in project root before the week begins.

Claude Code reads the brief at week start before building any scripts. The brief informs the initial parameter grid — do not run a grid search without it.

### Critical reading standard

Treat all sources critically. Always verify that cited papers use proper out-of-sample methodology. Reject any source claiming exceptional returns without methodology disclosure. Look for: train/test split, transaction cost assumptions, and whether the strategy was published before or after the test period.

---

## Phase 1 — Strategy Design and Backtest

*(To be documented)*

---

## Phase 2 — Validation

*(To be documented)*

---

## Phase 3 — Optimisation

### Leverage Screening

**Run after top 20 strategy parameter combinations identified.**

After ranking the top 20 combinations by annual return at 1×:

1. Run a preliminary leverage grid (1.0× to 3.0×, 0.5× steps) for each of the top 20.
2. Re-rank the top 20 by leveraged annual return, subject to safety buffer ≥ 33%.
3. If the ranking shifts from the 1× ranking, run full leverage optimisation (1.0×–5.0×, 0.1× steps) on the top 3 combinations.
4. Final strategy selection is based on leveraged performance, not 1× performance.

**Rationale:** Strategies with lower raw return but lower drawdown and higher Sortino may support higher safe leverage, producing better final returns than a higher-raw-return strategy constrained to lower leverage by its drawdown profile. The 1× winner is not always the leveraged winner.

Low MaxDD and high Sortino are leverage multipliers, not just quality filters — weight them more heavily when leverage is planned. Joint optimisation of strategy parameters and leverage simultaneously is the theoretically correct approach. Sequential optimisation (strategy first, leverage second) may miss the global optimum.

---

*Pipeline version: 1.1 — updated 2026-05-04: added Phase 2/3 stubs; added §Leverage Screening under Phase 3*
*Pipeline version: 1.0 — created 2026-05-04*
*Update this document after any process change or post-deployment review.*
