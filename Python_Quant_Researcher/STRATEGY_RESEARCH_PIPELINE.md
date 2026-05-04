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

*Pipeline version: 1.0 — created 2026-05-04*
*Update this document after any process change or post-deployment review.*
