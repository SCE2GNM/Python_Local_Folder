# Strategy Risk Register — [STRATEGY NAME]

**Purpose:** Template for creating per-strategy risk registers. Copy this file when a new strategy enters Phase 1 of the validation pipeline. Every deployed strategy must have its own risk register created from this template.
**Who reads it:** Claude Code when creating a new risk register.
**When updated:** When the risk register format is improved. Apply to new registers only.
**Related documents:** RISK_REGISTER_ETH_ADX.md, RISK_REGISTER_ETH_RSI.md, RISK_REGISTER_BTC_SMA.md.

---

**Strategy:** [e.g. ETH ADX Trailing Stop]
**Asset / Exchange:** [e.g. ETHUSDT / Binance Spot]
**Version:** [e.g. v1.0]
**Date created:** [YYYY-MM-DD]
**Last updated:** [YYYY-MM-DD]
**Updated by:** [Name]

---

## How to Use This Register

Create one copy of this file per strategy, named `RISK_REGISTER_[ASSET]_[STRATEGY].md`
(e.g. `RISK_REGISTER_ETH_ADX.md`, `RISK_REGISTER_ETH_RSI.md`).

Review the register before each deployment and before any capital increase.
All High priority open items must be resolved before deployment.
Medium priority items must be resolved or formally accepted with written rationale.

| Field | Meaning |
|---|---|
| ID | Unique reference (e.g. A001, A002) |
| Category | Strategy / Execution / Infrastructure / Data / Live Performance |
| Status | Open / In Progress / Resolved |
| Priority | High / Medium / Low |
| Target | When this item will be addressed |

**Categories:**
- **Strategy** — backtest assumptions, parameter choices, signal logic, risk model
- **Execution** — fills, fees, slippage, order types, exchange behaviour
- **Infrastructure** — EC2, cron, bot code, alerting, connectivity
- **Data** — data quality, look-ahead, survivorship, feed reliability
- **Live Performance** — observed deviation from backtest expectations

---

## Open Items

---

### [ID] — [Short title]

**Category:** [Strategy / Execution / Infrastructure / Data / Live Performance]

**Status:** Open

**Priority:** [High / Medium / Low]

**Raised:** [Week X / YYYY-MM-DD]

**Description:**
[What is the risk or assumption? Be specific about what is unknown or unvalidated.]

**Impact:**
[What happens if this materialises? Quantify where possible.]

**Fix:**
[What action resolves this? Who is responsible?]

**Target:** [Week X / after N live trades / YYYY-MM-DD]

**Update log:**
- [YYYY-MM-DD]: Raised.

---

*(Add further items above this line, preserving the ID sequence)*

---

## Resolved Items

| ID | Description | Resolution summary | Resolved | Week / Date |
|---|---|---|---|---|
| | | | | |

---

## Capital Allocation

| Strategy | Status | Capital | Position Size Method | Notes |
|---|---|---|---|---|
| [Strategy name] | [Live / Paper / Planned] | $ | [Kelly X% / Fixed $Y] | |

**Capital scaling rules:**
- [Rule 1 — e.g. Do not increase capital until all High priority items resolved]
- [Rule 2 — e.g. Review after 20 live trades]

---

## Review Schedule

| Milestone | Action |
|---|---|
| Before any capital increase | All High priority items must be resolved |
| After 20 live trades | Compare live metrics vs backtest: win rate, profit factor, avg win/loss |
| After 50 live trades | Full parameter re-evaluation on updated data |
| Sharpe < 0.5 over 30 live trades | Pause live trading, full strategy review |
| [Strategy-specific milestone] | [Action] |
| Every 6 months | Full parameter re-evaluation on rolling window |

---

*Template version: 1.0 — created 2026-05-01*
