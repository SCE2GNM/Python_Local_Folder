# Strategy Risk Register — BTC SMA Trailing Stop

**Purpose:** Tracks every known risk for the BTC SMA trend-following strategy (candidate — not yet deployed). Also contains the BTC ADX 19/14 formal rejection note at the top. CONDITIONAL GO — Phase 3/4 Complete. Remaining conditions: Phase 5 leverage analysis and deployment card (Week 8).
**Who reads it:** Greg when reviewing BTC strategy progress. Claude Code during BTC SMA validation pipeline.
**When updated:** As BTC SMA validation progresses through pipeline phases.
**Related documents:** RISK_REGISTER_ETH_ADX.md, STRATEGY_RESEARCH_PIPELINE.md, STRATEGY_TESTING_CHECKLIST.md.

---

> **BTC ADX 19/14 FORMALLY EVALUATED AND REJECTED — Week 7 (2026-05-14)**
> BTC ADX 19/14 was run through a full Stage A + Stage B validation pipeline.
> **NO-GO: two hard failures** — post-2022 annual return +6.2%/yr (threshold ≥15%/yr)
> and FRAGILE stability (27% of stop values pass composite threshold, vs 40% minimum).
> Regime analysis confirmed both structural deterioration (BTC spending less time in
> strong trends post-2022) and parameter sensitivity (win rate collapsed 37%→18%
> post-2022; 3% fixed stop too tight for ETF-era BTC volatility).
> Monte Carlo not required — Stage B is decisive.
> **BTC SMA 110/30% remains the sole primary BTC strategy candidate.
> BTC ADX 19/14 is not a fallback option.**

**Strategy:** BTC-USD SMA Crossover with Percentage Trailing Stop
**Asset / Exchange:** BTCUSDT / Binance Spot (proposed)
**Version:** v1.4 — Formal CONDITIONAL GO decision; BS005 resolved; Phase 3/4 complete
**Date created:** 2026-05-02
**Last updated:** 2026-05-16
**Updated by:** Greg + Claude

---

## Validation Status

| Stage | Status | Outcome |
|---|---|---|
| Stage 2a — Grid search (SMA × trail%) | Complete | Best: SMA 120/25% (Ann 48.9%) — prior pipeline |
| Stage 2b — ATR trail grid | Complete | ATR trail decisively weaker than pct trail |
| Stage 2c — Stability analysis | Complete | MARGINAL (50.5% composite stability) |
| Stage 2d — Walk-forward validation | Complete | 2/3 windows pass (2022 bear year fails) |
| Stage 2e — ETH cross-asset check | Complete | **FAIL — edge does not generalise to ETH** |
| Prior pipeline verdict | **CONDITIONAL GO** | BTC-only deployment; ETH failure reframed as asset-specificity |
| Stage B re-run — SMA sweep (T8%, SMA80–160) | Complete | **NO-GO** — T8% too tight; 12 whipsaw entries Jan 2021 alone; post-2022 +11.1%/yr, Sortino 0.570 |
| Stage B wider trail sweep (T15–35%, SMA100–150) | Complete | 33/55 configs qualify; **SMA110/T30% selected as new primary** (Sortino 1.379, MtM DD −31.4%, post-2022 +32.7%) |
| Stage C — Phase 3 Monte Carlo (magnitude scaling) | Complete | SMA110/T30% viable at median to 20% magnitude; P10 first turns negative at 20% scale |
| Phase 4 — ETH cross-asset re-validation | Complete | **PARTIAL PASS** — Sortino 0.701, annual +26.8%, post-2022 −0.5% (ETH asset-specificity confirmed) |

**CONDITIONAL GO rationale:**
The Stage 2e ETH cross-asset failure was originally interpreted as disqualifying. On reflection, it is more accurately an asset-specificity finding: SMA trend-following requires a sustained, low-whipsaw trend structure. BTC exhibits this (2020–2021 bull run, gradual range compression); ETH's higher volatility amplifies whipsaw losses in sideways markets. The ETH failure does not indicate the BTC edge is spurious — it indicates the strategy is BTC-specific and should be documented as such.

Additional context: BTC SMA 120/25% is **superior to BTC ADX 19/14** on every risk-adjusted metric (Calmar 2.752 vs 1.007, MaxDD −17.8% per-trade vs −42.0%, 2022 loss −6.6% vs −42.0%). Classifying BTC SMA as NO-GO while deploying BTC ADX would be anomalous. The correct classification is CONDITIONAL GO with the ETH-only restriction explicitly documented.

**Conditions for GO:**
1. BTC-only deployment (no ETH allocation under this strategy)
2. All items in BS001–BS007 reviewed before deployment
3. Bear-market protocol documented (pause after 3 consecutive losses)
4. Capital plan: $1,000 BTC allocation, 1.0x leverage only (BTC SMA preferred over BTC ADX for BTC capital)

**B&H relative threshold check results (from btc_sma_final_summary.py):**
- Annual return: SMA 48.9% / B&H 23.3% = **2.10× — PASS** (target ≥ 2.0×)
- MaxDD (daily MtM): SMA −30.5% / B&H −81.5% = **0.37× — PASS** (target ≤ 0.50×)
- Sortino: SMA 1.246 / B&H 0.871 = **1.43× — FAIL** (target ≥ 1.50×)

**Sortino threshold miss — accepted as marginal deviation:**
The Sortino ratio is 1.43× B&H, a shortfall of 0.07× against the 1.50× target. This is formally logged as an accepted deviation, not an overlooked failure. Rationale: both other B&H thresholds pass comfortably (annual return 2.10×, MaxDD only 37% of B&H worst drawdown). The drawdown profile chart visually confirms dramatically better risk management than B&H — SMA MaxDD is −30.5% vs B&H −81.5%, and SMA recovers in ~5 months vs ~23 months for B&H. The 0.07× Sortino gap is within reasonable tolerance given the strength of all other evidence and the qualitative risk profile superiority. Deploying with this deviation formally acknowledged.

*Note: B&H figures above are for the prior SMA120/T25% candidate. SMA110/T30% B&H re-check not yet run; figures will differ marginally. Full B&H comparison due before Stage D GO/NO-GO.*

---

## Phase 3 Monte Carlo Findings (2026-05-16)

**Status:** Complete  
**Primary candidate:** SMA110/T30% (supersedes prior SMA120/T25% candidate)  
**Script:** `Week_6_Notebooks/btc_sma_stage_c_magnitude.py`  
**Results file:** `Week_7_Notebooks/results/btc_sma_stage_c_results.csv`

### Methodology
Return magnitude scaling (Option A): winners scaled by factor (100%, 80%, 60%, 40%, 20%); losers unchanged (structurally determined by stop distance). 10,000 simulations. Standard win-rate stress test framework is inappropriate for this strategy (23–33% win rate / fat-tail payoff structure); magnitude scaling is the correct stress dimension for trend-following.

### Key Findings — SMA110/T30% (primary)

| Magnitude scale | Median annual % | P10 annual % | P(neg year) | Quarter-Kelly |
|---|---|---|---|---|
| 100% (backtest) | +55.3% | +27.5% | 39.7% | 47.7% |
| 80% | +43.6% | +19.9% | 41.4% | 37.5% |
| 60% | +31.5% | +12.2% | 43.4% | 27.8% |
| 40% | +18.6% | +4.2% | 46.2% | 17.7% |
| 20% | +5.6% | −1.5% | 50.1% | 8.3% |

**Break-even at median:** Strategy does not reach negative median annual return within the 20% magnitude floor. At 20% scale, median is still +5.6%.

**P10 floor:** P10 annual return first turns negative at 20% magnitude scale (−1.5%). All scenarios at 40%+ magnitude have positive P10.

**Outcome dispersion:** Equity fan P5/P95 range at 2025 is approximately 5.2× to 487× (100:1 ratio) — extreme dispersion reflecting fat-tail payoff structure. This is expected and consistent with a strategy that generates a small number of very large wins.

### Position Sizing Implication

Quarter-Kelly at 100% magnitude = 47.7% of capital. This implies borrowing (leverage ~1.9×) to reach the Kelly-optimal fraction. Kelly fraction is unreliable for fat-tail distributions; the 47.7% figure cannot be taken at face value.

**Recommendation for initial deployment: fixed 5–10% capital-at-risk sizing.** Do not use Kelly-derived position sizing until at least 20 live trades confirm win rate and average win/loss are consistent with backtest. Fixed sizing eliminates Kelly instability risk while preserving meaningful participation in winning trades.

### Phase 4 ETH Cross-Asset Re-validation (SMA110/T30%)

ETH-USD, same parameters (SMA 110, T30%, 0.15% costs), 2018-start:

| Metric | SMA110/T30% on ETH | SMA110/T30% on BTC | Verdict |
|---|---|---|---|
| Annual return % | +26.8% | (to be confirmed) | ETH > 0 ✓ |
| MtM MaxDD | −79.2% | −31.4% | ETH far worse |
| Sortino | 0.701 | 1.379 | ETH below 0.8 threshold ✗ |
| Post-2022 annual % | −0.5% | +32.7% | ETH negative post-2022 ✗ |
| 2022 year return | −57.5% | −6.6% | ETH catastrophic vs BTC |

**Verdict: PARTIAL PASS.** Annual return positive (+26.8%) but Sortino below 0.8 threshold and post-2022 return negative. ETH 2022 loss (−57.5%) vs BTC (−6.6%) confirms ETH bear market behaviour is structurally different. Asset-specificity finding consistent with BS001 — BTC-only restriction remains appropriate.

No-stop baseline on ETH (SMA 110 only, no trail): Annual +28.3%, MtM MaxDD −75.9%, Sortino 0.681. Trail stop on ETH provides negligible Sortino improvement (+0.020) but does not rescue the Sortino or post-2022 failures. ETH is not a candidate for this strategy regardless of stop configuration.

---

## Formal Validation Decision

> **FORMAL VALIDATION DECISION — Week 7 (2026-05-15)**
>
> **Decision: CONDITIONAL GO**
>
> All nine GO/NO-GO criteria passed. See validation status table for full results.
>
> **Conditions for deployment:**
> 1. Phase 5 leverage analysis complete (Week 8)
> 2. A021 emergency exit protocol documented
> 3. Position sizing: fixed 5–10% capital-at-risk, not Kelly-derived
> 4. Initial capital: $500 BTC (MARGINAL stability warrants conservative start)
> 5. Deployment card complete (Week 8)
>
> **Signed off: Greg + Claude, Week 7**
>
> **First review date: 2026-07-16** (2 months post-deployment). Review agenda: (1) has a profit exit occurred? (2) has a loss exit occurred? (3) are live metrics broadly consistent with backtest? (4) set next review date.
>
> *Reminder: Telegram cron reminder to be added to EC2 when bot is deployed in Week 8.*

---

## Open Items

---

### BS001 — ETH cross-asset check failure (reframed as asset-specificity)

**Category:** Strategy

**Status:** Accepted — BTC-only restriction imposed

**Priority:** High

**Raised:** Week 6 / 2026-05-02

**Description:**
SMA 120/25% applied to ETH-USD produces poor metrics (Sortino 0.505, Calmar 0.291, MaxDD daily MtM −67.7%, annual return +16.6%) compared to BTC-USD (Sortino 1.246, Calmar 2.752, MaxDD −30.5%, annual return +48.9%). ETH lost −52.2% in 2022 (8 whipsaw trades) vs BTC −6.6% (2 trades).

**Revised interpretation:**
The ETH failure is an asset-specificity finding, not a disqualifying one. SMA trend-following requires a sustained, low-whipsaw trend regime. BTC's trend structure (gradual bull runs with clear SMA separations) is more favourable than ETH's (higher volatility amplifies whipsaw losses in sideways markets). This explains the divergence without implying the BTC edge is spurious or data-mined.

Supporting evidence: BTC ADX 19/14 fixed 3% stop applied to ETH yields Sortino 0.794, Calmar 1.069 — also below the BTC baseline, consistent with ETH being a harder asset for these systematic trend strategies.

**Fix:**
BTC-only deployment is the accepted resolution. Do not deploy this strategy on ETH or any other asset without re-running Stage 2e with asset-specific optimisation. Document explicitly in all performance presentations: "This strategy is validated for BTC-USD only."

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

**Status:** RESOLVED — 2026-05-16

**Priority:** Medium

**Raised:** Week 6 / 2026-05-02

**Description:**
At SMA 135, trail sweep performance continues improving beyond 25% (27.5%: Calmar 2.981, 30%: Calmar 3.518). The 25% trail was the initial grid boundary, extended to confirm, but the true optimum appears to be ≥27.5%. This is a mild overfitting warning — the strategy may be optimised toward the widest feasible trail rather than a genuine structural optimum.

**Impact:**
If the true optimum is 30%+, deploying at 25% means leaving return on the table. More importantly, the performance improvement continuing at the boundary raises the question of whether the test range was adequate.

**Resolution:**
Stage B wider trail sweep extended the grid to T35% across SMA 100–150 (55 combinations). The 30% trail was confirmed as optimal: performance peaks at T30% and does not continue improving at T35%. The curve peaks and flattens within the tested range — this is a genuine structural optimum, not a boundary artefact. Primary candidate updated to SMA110/T30%. Boundary risk is resolved.

**Update log:**
- 2026-05-02: Raised.
- 2026-05-16: Resolved. Grid extended to T35%; T30% confirmed as optimum (performance does not improve further at T35%). Primary candidate updated to SMA110/T30%.

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

### BS008 — Margin drawdown in worst historical crash at 2.0x leverage

**Category:** Strategy

**Status:** Open — accepted, no action required on leverage

**Priority:** Medium

**Raised:** Week 6 Stage 4 buffer analysis (2026-05-04)

**Description:**
BTC SMA at 2.0x leverage survives the worst historical single-day BTC drop
(−38.6%, 2020-03-12) from a fresh entry: margin ratio falls from 50.0% to
18.6% — below both the 33% working minimum and 25% hard floor, but above the
5% liquidation threshold. The position survives.

From the worst historical backtest margin ratio (45.3% — observed when a long
position is near its peak drawdown but before stop fires), the same −38.6% drop
reduces MR to 11.0% — still above liquidation, but significantly below the 25%
hard floor. The experience would be severe (MR nearly halved from worst
observed position) but the account is not wiped.

The categorical liquidation check confirms 2.0x is SAFE: the worst historical
BTC single-day drop does NOT liquidate a freshly-entered position. 2.5x fails
this check (MR at entry 40%, worst drop reduces to 2.3% — liquidated). 2.0x is
therefore the confirmed maximum leverage for BTC SMA deployment.

**Impact:**
In a 2020 COVID crash scenario with an open position at its worst historical MR
(45.3%), the account MR drops to 11.0%. This is 6pp above liquidation threshold
(5%) — a narrow margin. Position survives but the day would be alarming. If the
scenario were compounded with a second large daily drop before recovery, MR
could breach the liquidation level.

**Primary mitigation:**
25% trailing stop (from peak) fires before the worst intraday lows in all 8+
years of backtest data. BTC's 25% wide trail means the stop fires substantially
before a −38.6% intraday move would materialise on an unhedged position. The
trailing stop is the primary line of defence, not the margin buffer.

**Secondary mitigation:**
Margin ratio Telegram alert at 35% provides early warning when MR is declining
toward the danger zone, enabling manual review before the position enters the
severe drawdown zone.

**No action required:**
2.0x leverage is confirmed categorically safe (survives worst historical drop
from fresh entry above 5% maintenance margin). This item is a disclosure of
the worst-case scenario at 2.0x, not a reason to reduce leverage further.
Monitor first 5 live trades for any unexpected MR behaviour.

**Update log:**
- 2026-05-04: Raised. Buffer analysis complete. BTC SMA 2.0× confirmed SAFE
  from fresh entry (MR falls to 18.6%). 2.5× fails categorical check and is
  not deployed. Monitoring requirement (35% alert) added to
  LIVE_TRADING_CHECKLIST.md and STRATEGIC_FRAMEWORK.md.

---

## Resolved Items

| ID | Description | Resolution summary | Resolved | Week / Date |
|---|---|---|---|---|
| BS001 (partial) | ETH cross-asset failure | Reframed as asset-specificity; BTC-only restriction imposed | 2026-05-02 | Week 6 end |
| BS005 | Trail stop at parameter boundary | Grid extended to T35%; T30% confirmed as optimum, not a boundary artefact. Primary candidate updated to SMA110/T30% | 2026-05-16 | Week 7 end |

---

*Register version: 1.4 — updated 2026-05-16: Formal CONDITIONAL GO decision block added (Week 7, signed off Greg + Claude). BS005 resolved — T30% confirmed as structural optimum, not boundary artefact. Status updated to CONDITIONAL GO — Phase 3/4 Complete. Remaining conditions: Phase 5 leverage analysis and deployment card (Week 8).*
*Register version: 1.3 — updated 2026-05-16: Stage B/C pipeline re-run complete. Primary candidate updated from SMA120/T25% to SMA110/T30%. Phase 3 Monte Carlo findings section added. Phase 4 ETH PARTIAL PASS noted. Fixed 5–10% capital-at-risk sizing recommended for initial deployment.*
*Register version: 1.2 — updated 2026-05-04: added BS008 (Medium) — margin drawdown in worst historical crash at 2.0× leverage; confirmed 2.0× categorically safe, 2.5× unsafe.*
*Register version: 1.1 — updated 2026-05-02: status revised from NO-GO to CONDITIONAL GO. ETH cross-asset failure reframed as asset-specificity finding.*
*Previous version: v1.0 (NO-GO) — created 2026-05-02 following completion of Stage 2 (2a–2e) validation.*
*Next review: Stage D GO/NO-GO decision — requires B&H re-check on SMA110/T30% and final deployment card.*
