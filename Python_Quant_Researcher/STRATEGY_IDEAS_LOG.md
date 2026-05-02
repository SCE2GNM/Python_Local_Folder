# Strategy Ideas Log
## DeFi Quant Engineer Curriculum

Purpose: Capture trading strategy ideas for future investigation. Reviewed at start of each new week.

---

## Log Format

| Field | Description |
|---|---|
| ID | Unique reference (SI001, SI002, …) |
| Name | Short strategy name |
| Type | Category (see below) |
| Source | Where the idea originated |
| Priority | HIGH / MEDIUM / LOW |
| Target Week | Earliest week to investigate |
| Notes | Key context, dependencies, caveats |
| Date Added | YYYY-MM-DD |

---

## Categories

- Trend Following
- Mean Reversion
- Momentum
- Volatility
- DeFi/On-chain
- Arbitrage

---

## Ideas Log

### SI001 — BTC ADX 19/14 Full Validation

| Field | Value |
|---|---|
| **ID** | SI001 |
| **Name** | BTC ADX 19/14 Full Validation |
| **Type** | Trend Following |
| **Source** | Week 5 discovery |
| **Priority** | HIGH |
| **Target Week** | Week 7 |
| **Date Added** | 2026-05-01 |

**Notes:**
Partially validated in Week 5 — needs trailing stop optimisation, cost correction, Sortino correction, and walk-forward validation before deployment. Currently the BTC SMA fallback strategy. Week 5 optimum was ADX threshold 16, period 8 with fixed 5% stop, but this was computed with incorrect Sortino (per-trade method, inflates 3-4×) and without 0.15% round-trip costs applied. Re-validation required with corrected methodology before any deployment decision.
