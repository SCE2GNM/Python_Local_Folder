# Strategy Risk Register — BTC SMA Trailing Stop

**Strategy:** BTC-USD SMA Crossover with Percentage Trailing Stop
**Asset / Exchange:** BTCUSDT / Binance Spot (proposed)
**Version:** v1.0 — Stage 2 validation complete
**Date created:** 2026-05-02
**Last updated:** 2026-05-02
**Updated by:** Greg

---

## Validation Status

| Stage | Status | Outcome |
|---|---|---|
| Stage 2a — Grid search (SMA × trail%) | Complete | Best: SMA 120/25% (Ann 48.9%) |
| Stage 2b — ATR trail grid | Complete | ATR trail decisively weaker than pct trail |
| Stage 2c — Stability analysis | Complete | MARGINAL (50.5% composite stability) |
| Stage 2d — Walk-forward validation | Complete | 2/3 windows pass (2022 bear year fails) |
| Stage 2e — ETH cross-asset check | Complete | **FAIL — edge does not generalise to ETH** |
| Final recommendation | **NO-GO** | Proceed to BTC ADX 19/14 fallback (SI001) |

---

## Open Items

---

### BS001 — ETH cross-asset check failure

**Category:** Strategy

**Status:** Open

**Priority:** High

**Raised:** Week 6 / 2026-05-02

**Description:**
SMA 120/25% applied to ETH-USD produces poor metrics (Sortino 0.505, Calmar 0.291, MaxDD daily MtM −67.7%, annual return +16.6%) compared to BTC-USD (Sortino 1.246, Calmar 2.752, MaxDD −30.5%, annual return +48.9%). ETH lost −52.2% in 2022 (8 whipsaw trades) vs BTC −6.6% (2 trades). The edge does not generalise to ETH.

**Impact:**
Raises fundamental concern that the BTC SMA performance is specific to BTC's trend structure rather than representing a robust, transferable strategy. If deployed on BTC alone, this concern is partially mitigated but not eliminated. The strategy may be fragile to changes in BTC's own trend characteristics.

**Fix:**
Strategy currently classified NO-GO. Before reconsidering BTC-only deployment: (1) investigate whether ETH failure is due to ETH's higher volatility requiring different trail% or SMA period, or (2) accept that this strategy is BTC-specific with explicit documentation. Do not deploy without a clear explanation for the ETH divergence.

---

### BS002 — 2021 return concentration

**Category:** Strategy

**Status:** Open

**Priority:** High

**Raised:** Week 6 / 2026-05-02

**Description:**
76.2% of the full-period compounded return (2018–2026, +2664% total) came from 2021 alone — specifically one trade running Apr 2020 → Jan 2021 (+247%). Ex-2021 annual return drops from +48.9% to approximately +29% (confirmed from Stage 2c ex-2021 analysis). The strategy's headline metrics are heavily inflated by a single exceptional year.

**Impact:**
If a 2021-type parabolic bull run does not recur, realistic expectation is ~29% annual return with ~18% per-trade MaxDD. This is still a strong return but significantly below the headline figure. Investors evaluating the strategy on full-period metrics will see inflated performance.

**Fix:**
Always disclose both full-period and ex-2021 metrics in any performance presentation. Document explicitly that 76% of return came from one year. Set return expectations based on ex-2021 figures for planning purposes.

---

### BS003 — Walk-forward Window 1 (2022) failure

**Category:** Strategy

**Status:** Open — accepted with rationale

**Priority:** Medium

**Raised:** Week 6 / 2026-05-02

**Description:**
The strategy fails the "profitable in all 3 windows" walk-forward criterion. Window 1 (2022) returned −6.6% (Candidate A, 2 trades) to −11.3% (Candidate B, 3 trades). Candidate A had only 2 trades in 2022, below the 3-trade reliability threshold.

**Impact:**
Any year resembling 2022 (sustained downtrend, BTC −65%) will produce losses. The strategy cannot be described as profitable across all walk-forward windows under strict criteria.

**Rationale for proceeding:**
BTC fell 65% in 2022. The strategy spent most of the year in cash and made 2 re-entry attempts (Candidate A). The absolute losses (−6.6%) are small relative to the underlying decline. This is expected behaviour for a long-only trend-following system in a prolonged bear market — not a backtest artifact. An investor holding BTC would have lost 65%; this strategy lost 6.6%. The 2022 failure is structural to the strategy type, not to the specific parameters. Must be disclosed to any deployer.

**Fix:**
Document 2022 context in risk disclosure. Set an explicit bear-market protocol: after N consecutive losing trades (suggested: 3), reduce position size or pause the strategy until SMA is confirmed to be in an uptrend.

---

### BS004 — MARGINAL stability (Stage 2c)

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 6 / 2026-05-02

**Description:**
Stage 2c stability analysis returned MARGINAL (50.5% composite stability score for primary SMA 135/25%). SMA sweep: 6/13 values ≥ 0.7 composite (46%). Trail sweep: 3/7 values passing (43%). Performance degrades sharply above SMA 140 and below 22.5% trail.

**Impact:**
Parameters are not robustly stable across the full sweep range. Small changes to SMA period (e.g., from 135 to 145) cause significant performance deterioration. If market regime shifts and optimal parameters change, current parameters may underperform substantially.

**Fix:**
Accept MARGINAL stability as a known risk, disclosed in deployment documentation. Monitor live performance quarterly — if Calmar drops below 1.0 over a rolling 12-month period, halt and re-evaluate.

---

### BS005 — Trail stop at parameter boundary

**Category:** Strategy

**Status:** Open

**Priority:** Medium

**Raised:** Week 6 / 2026-05-02

**Description:**
At SMA 135, trail sweep performance continues improving beyond 25% (27.5%: Calmar 2.981, 30%: Calmar 3.518). The 25% trail was the initial grid boundary, extended to confirm, but the true optimum appears to be ≥27.5%. This is a mild overfitting warning — the strategy may be optimised toward the widest feasible trail rather than a genuine structural optimum.

**Impact:**
If the true optimum is 30%+, deploying at 25% means leaving return on the table. More importantly, the performance improvement continuing at the boundary raises the question of whether the test range was adequate.

**Fix:**
Extend grid to 35% trail and re-run Stage 2c stability analysis before any deployment decision. Confirm the curve peaks and flattens rather than continuing to climb. If peak is confirmed at 30–32%, update candidate parameters.

---

### BS006 — Window 3 cross-period trade dominance

**Category:** Strategy

**Status:** Open — accepted with rationale

**Priority:** Low

**Raised:** Week 6 / 2026-05-02

**Description:**
Walk-forward Window 3 (test year 2024, +87.7% for Candidate A) is dominated by one trade: entry Oct 2023 (training period) → exit Jun 2024 (test period), +128% gross. The remaining 6 trades in 2024 were all losses. Without the cross-period trade, Window 3 would show net-negative returns.

**Impact:**
Window 3 "pass" is contingent on a single trade that was already in progress when the test period began. A trader starting capital deployment on Jan 1, 2024 (not holding from Oct 2023) would not have captured this trade and would have experienced only the 6 losing trades (+net negative).

**Rationale:**
The Oct 2023 entry was generated by the strategy's rules at the time. If the strategy were live, the position would have been held through Jan 2024. The cross-period flag is a disclosure item, not a disqualifying finding. It does, however, highlight that the strategy's annual returns are highly lumpy — driven by a few long-duration winning trades per year.

**Fix:**
Note in deployment documentation. Accept as characteristic of the strategy type (low-frequency trend-following). Do not smooth or exclude cross-period trades from live performance reporting.

---

### BS007 — Low trade count per test window

**Category:** Strategy

**Status:** Open

**Priority:** Low

**Raised:** Week 6 / 2026-05-02

**Description:**
Individual walk-forward test windows contain 2–7 trades. With only 3–5 trades per year on average, annual return figures are dominated by single trades. Statistical reliability of any one year's result is very low — a single trade's timing determines whether the year is profitable.

**Impact:**
Performance metrics computed from 2–5 trades per window have very wide confidence intervals. A strategy with 3 trades per year cannot be evaluated with the same statistical confidence as a strategy with 30+ trades per year.

**Fix:**
Accept as structural to low-frequency trend-following. The full-period n=34 provides the best statistical base. Per-window results should be interpreted as directional (positive/negative regime) rather than precise performance estimates. Document explicitly.

---

## Resolved Items

*None — strategy is currently classified NO-GO. Items remain open pending re-evaluation after BTC ADX 19/14 fallback validation or further BTC SMA investigation.*

---

*Register version: 1.0 — created 2026-05-02 following completion of Stage 2 (2a–2e) validation.*
*Next review: start of Week 7, alongside BTC ADX 19/14 (SI001) validation decision.*
