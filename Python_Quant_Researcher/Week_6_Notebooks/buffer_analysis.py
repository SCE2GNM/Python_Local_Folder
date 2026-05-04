#!/usr/bin/env python3
"""
Empirical Buffer Analysis — Minimum margin ratio requirements
Determines whether 25% / 33% thresholds are empirically justified.

Margin ratio definition (matches backtest):
  MR = 1 − (lev − 1) × entry_price / (lev × current_price)
  At entry: MR = 1/lev
  Liquidation at MR = 5% (maintenance margin)

Key formula — MR after a price drop of fraction d from current level:
  MR_new = 1 − (1 − MR_current) / (1 − d)

Minimum starting MR to remain above threshold T after drop d:
  MR_min = 1 − (1 − T) × (1 − d)
"""

import warnings
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

MAINT_MARGIN = 0.05   # 5% — Binance maintenance margin for isolated spot margin
HARD_FLOOR   = 0.25   # 25% — hard floor veto
WORK_MIN     = 0.33   # 33% — working minimum
TOP_N        = 10     # worst N drops to report

# Leverage scenarios with their worst historical MR from backtests
SCENARIOS = [
    {'name': 'ETH ADX 1.9×', 'asset': 'ETH-USD', 'lev': 1.9, 'worst_hist_mr': 0.344},
    {'name': 'BTC SMA 2.0×', 'asset': 'BTC-USD', 'lev': 2.0, 'worst_hist_mr': 0.453},
    {'name': 'BTC SMA 2.5×', 'asset': 'BTC-USD', 'lev': 2.5, 'worst_hist_mr': 0.344},
]


# ── Margin ratio math ─────────────────────────────────────────────────────────
def mr_after_drop(mr_current, drop_frac):
    """MR after price drops by drop_frac from current level."""
    return 1.0 - (1.0 - mr_current) / (1.0 - drop_frac)


def min_mr_to_survive(drop_frac, threshold):
    """Minimum starting MR to remain above threshold after a drop of drop_frac."""
    return 1.0 - (1.0 - threshold) * (1.0 - drop_frac)


# ── Fetch data ────────────────────────────────────────────────────────────────
data = {}
for ticker in ['ETH-USD', 'BTC-USD']:
    print(f"Fetching {ticker}...")
    raw = yf.download(ticker, start='2018-01-01', auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw[['Open', 'High', 'Low', 'Close']].dropna().copy()
    df['prev_close']     = df['Close'].shift(1)
    df['intraday_drop']  = (df['Low'] - df['Open']) / df['Open']       # open → low
    df['ctc_drop']       = (df['Close'] - df['prev_close']) / df['prev_close']  # close-to-close
    df['ctl_drop']       = (df['Low'] - df['prev_close']) / df['prev_close']    # prev_close → low
    df = df.dropna()
    data[ticker] = df
    print(f"  {df.index[0].date()} → {df.index[-1].date()}  ({len(df)} bars)")

print()

# ── STEP 1 — Worst drops ─────────────────────────────────────────────────────
for ticker, label in [('ETH-USD', 'ETH'), ('BTC-USD', 'BTC')]:
    df = data[ticker]
    print("=" * 70)
    print(f"STEP 1 — {label} Worst Single-Day Drops")
    print("=" * 70)

    # Intraday (open → low)
    worst_intra = df.nsmallest(TOP_N, 'intraday_drop')[
        ['Open', 'Low', 'Close', 'intraday_drop']]
    print(f"\n  {label} Worst intraday drops (open → low):")
    print(f"  {'Date':>12}  {'Open':>10}  {'Low':>10}  {'Close':>10}  {'Drop %':>8}")
    print(f"  {'─'*55}")
    for dt, row in worst_intra.iterrows():
        print(f"  {str(dt.date()):>12}  {row['Open']:>10,.0f}  {row['Low']:>10,.0f}  "
              f"{row['Close']:>10,.0f}  {row['intraday_drop']*100:>7.1f}%")

    # Close-to-close
    worst_ctc = df.nsmallest(TOP_N, 'ctc_drop')[
        ['prev_close', 'Close', 'ctc_drop']]
    print(f"\n  {label} Worst close-to-close drops (prev close → close):")
    print(f"  {'Date':>12}  {'Prev Close':>10}  {'Close':>10}  {'Drop %':>8}")
    print(f"  {'─'*45}")
    for dt, row in worst_ctc.iterrows():
        print(f"  {str(dt.date()):>12}  {row['prev_close']:>10,.0f}  "
              f"{row['Close']:>10,.0f}  {row['ctc_drop']*100:>7.1f}%")

    # Prev-close → low (most relevant for open leveraged positions)
    worst_ctl = df.nsmallest(TOP_N, 'ctl_drop')[
        ['prev_close', 'Open', 'Low', 'ctl_drop']]
    print(f"\n  {label} Worst prev-close-to-low drops (overnight gap + intraday):")
    print(f"  {'Date':>12}  {'Prev Close':>10}  {'Open':>10}  {'Low':>10}  {'Drop %':>8}")
    print(f"  {'─'*55}")
    for dt, row in worst_ctl.iterrows():
        print(f"  {str(dt.date()):>12}  {row['prev_close']:>10,.0f}  "
              f"{row['Open']:>10,.0f}  {row['Low']:>10,.0f}  "
              f"{row['ctl_drop']*100:>7.1f}%")

    # Summary stats
    print(f"\n  {label} drop summary (as % of prior reference price):")
    print(f"  {'Metric':>35}  {'Worst':>8}  {'5th worst':>10}  {'10th worst':>11}")
    print(f"  {'─'*68}")
    for col, label2 in [
        ('intraday_drop', 'Intraday (open→low)'),
        ('ctc_drop',      'Close-to-close'),
        ('ctl_drop',      'Prev close→low (gap+intraday)'),
    ]:
        vals = df[col].nsmallest(TOP_N).values
        print(f"  {label2:>35}  {vals[0]*100:>7.1f}%  "
              f"{vals[4]*100:>9.1f}%  {vals[9]*100:>10.1f}%")
    print()


# ── STEP 2 — Margin ratio impact ─────────────────────────────────────────────
print("=" * 70)
print("STEP 2 — Margin Ratio Impact at Recommended Leverage Levels")
print("=" * 70)
print()
print("  Using prev-close→low drop as the worst-case measure for open positions.")
print("  This is (today's low - yesterday's close) / yesterday's close —")
print("  the maximum intraday adverse move an open position can experience.")
print()

for sc in SCENARIOS:
    ticker  = sc['asset']
    lev     = sc['lev']
    name    = sc['name']
    hist_mr = sc['worst_hist_mr']
    df      = data[ticker]

    # Worst intraday drops (prev_close → low) as positive fractions
    worst_drops_ctl = df['ctl_drop'].nsmallest(5).abs().values   # 5 worst positive drops

    # Also use worst intraday (open → low)
    worst_drops_intra = df['intraday_drop'].nsmallest(5).abs().values

    mr_at_entry = 1.0 / lev   # MR immediately at trade entry

    print(f"  ── {name}  (entry MR = {mr_at_entry*100:.1f}%, worst historical MR = {hist_mr*100:.1f}%)")
    print(f"     Worst 5 prev-close→low drops: "
          + "  ".join(f"{d*100:.1f}%" for d in worst_drops_ctl))
    print()

    worst_d = worst_drops_ctl[0]   # single worst drop
    print(f"     Scenario A — worst drop ({worst_d*100:.1f}%) starting from ENTRY (MR = {mr_at_entry*100:.1f}%):")
    mr_a = mr_after_drop(mr_at_entry, worst_d)
    print(f"     → MR after drop: {mr_a*100:.1f}%", end='')
    if mr_a < MAINT_MARGIN:      print("  ✗ LIQUIDATED")
    elif mr_a < HARD_FLOOR:      print(f"  ✗ below 25% hard floor")
    elif mr_a < WORK_MIN:        print(f"  ⚠ below 33% working minimum")
    else:                        print(f"  ✓ above 33%")

    print()
    print(f"     Scenario B — worst drop ({worst_d*100:.1f}%) starting from WORST HISTORICAL MR ({hist_mr*100:.1f}%):")
    print(f"     (Most realistic: worst observed price conditions AND worst margin position)")
    mr_b = mr_after_drop(hist_mr, worst_d)
    print(f"     → MR after drop: {mr_b*100:.1f}%", end='')
    if mr_b < MAINT_MARGIN:      print("  ✗ LIQUIDATED")
    elif mr_b < HARD_FLOOR:      print(f"  ✗ below 25% hard floor")
    elif mr_b < WORK_MIN:        print(f"  ⚠ below 33% working minimum")
    else:                        print(f"  ✓ above 33%")

    print()
    print(f"     MR after each of the 5 worst drops, starting from worst historical ({hist_mr*100:.1f}%):")
    print(f"     {'Drop':>8}  {'MR after':>9}  {'Status':}")
    for d in worst_drops_ctl:
        mr_new = mr_after_drop(hist_mr, d)
        if mr_new < MAINT_MARGIN: status = '✗ LIQUIDATED'
        elif mr_new < HARD_FLOOR: status = '✗ below 25% floor'
        elif mr_new < WORK_MIN:   status = '⚠ below 33% minimum'
        else:                     status = '✓ above 33%'
        print(f"     {-d*100:>7.1f}%  {mr_new*100:>8.1f}%  {status}")
    print()


# ── STEP 3 — Evidence-based minimum buffer ────────────────────────────────────
print("=" * 70)
print("STEP 3 — Evidence-Based Minimum Buffer Requirements")
print("=" * 70)
print()
print("  Formula: min_MR_start = 1 − (1 − threshold) × (1 − drop)")
print()

for sc in SCENARIOS:
    ticker = sc['asset']
    lev    = sc['lev']
    name   = sc['name']
    df     = data[ticker]

    worst_d   = df['ctl_drop'].min()          # most negative (as a negative fraction)
    worst_abs = abs(worst_d)
    p5_abs    = abs(df['ctl_drop'].nsmallest(5).iloc[4])   # 5th worst

    print(f"  ── {name}")
    print(f"     Worst ever prev-close→low drop: {worst_d*100:.1f}%")
    print(f"     5th-worst prev-close→low drop:  {-p5_abs*100:.1f}%")
    print()

    for drop_label, drop in [
        (f'worst ever ({worst_abs*100:.1f}%)', worst_abs),
        (f'5th worst  ({p5_abs*100:.1f}%)', p5_abs),
    ]:
        min_liq  = min_mr_to_survive(drop, MAINT_MARGIN)
        min_hard = min_mr_to_survive(drop, HARD_FLOOR)
        min_work = min_mr_to_survive(drop, WORK_MIN)
        print(f"     If drop = {drop_label}:")
        print(f"       Min MR to avoid liquidation (>5%):    {min_liq*100:>5.1f}%")
        print(f"       Min MR to stay above 25% hard floor:  {min_hard*100:>5.1f}%")
        print(f"       Min MR to stay above 33% working min: {min_work*100:>5.1f}%")
    print()


# ── STEP 4 — Recommended buffer revision ─────────────────────────────────────
print("=" * 70)
print("STEP 4 — Recommended Buffer Revision")
print("=" * 70)
print()

# Collect the key worst drops for each asset
eth_worst_ctl = abs(data['ETH-USD']['ctl_drop'].min())
btc_worst_ctl = abs(data['BTC-USD']['ctl_drop'].min())
eth_p5_ctl    = abs(data['ETH-USD']['ctl_drop'].nsmallest(5).iloc[4])
btc_p5_ctl    = abs(data['BTC-USD']['ctl_drop'].nsmallest(5).iloc[4])

print("  Summary — Does the current working minimum (33%) survive each scenario?")
print()
print(f"  {'Strategy':>15}  {'Worst drop':>11}  {'MR from hist worst':>19}  {'Survives 25%?':>14}  {'Survives 33%?':>14}")
print(f"  {'─'*78}")

for sc in SCENARIOS:
    ticker  = sc['asset']
    name    = sc['name']
    hist_mr = sc['worst_hist_mr']
    df      = data[ticker]
    worst_d = abs(df['ctl_drop'].min())
    mr_new  = mr_after_drop(hist_mr, worst_d)
    surv_25 = '✓' if mr_new >= HARD_FLOOR else '✗'
    surv_33 = '✓' if mr_new >= WORK_MIN   else '✗'
    print(f"  {name:>15}  {-worst_d*100:>10.1f}%  "
          f"{hist_mr*100:.1f}% → {mr_new*100:.1f}%{' '*7}"
          f"{surv_25:>14}  {surv_33:>14}")

print()
print("  Interpretation and recommendation:")
print()

for sc in SCENARIOS:
    ticker  = sc['asset']
    name    = sc['name']
    hist_mr = sc['worst_hist_mr']
    lev     = sc['lev']
    df      = data[ticker]
    worst_d = abs(df['ctl_drop'].min())

    mr_after_worst = mr_after_drop(hist_mr, worst_d)
    min_to_surv_liq  = min_mr_to_survive(worst_d, MAINT_MARGIN) * 100
    min_to_surv_hard = min_mr_to_survive(worst_d, HARD_FLOOR) * 100
    min_to_surv_work = min_mr_to_survive(worst_d, WORK_MIN) * 100

    print(f"  {name}:")
    print(f"    Worst single-day move vs open position: {-worst_d*100:.1f}%")
    print(f"    Starting from worst historical MR {hist_mr*100:.1f}%  →  MR after: {mr_after_worst*100:.1f}%")
    print(f"    To survive worst drop and stay above 5%:  need MR ≥ {min_to_surv_liq:.1f}%")
    print(f"    To survive worst drop and stay above 25%: need MR ≥ {min_to_surv_hard:.1f}%")
    print(f"    To survive worst drop and stay above 33%: need MR ≥ {min_to_surv_work:.1f}%")
    if mr_after_worst < MAINT_MARGIN:
        verdict = f"CRITICAL: worst-case drop would LIQUIDATE from hist worst MR"
    elif mr_after_worst < HARD_FLOOR:
        verdict = f"WARNING: worst-case drop would breach 25% hard floor from hist worst MR"
    elif mr_after_worst < WORK_MIN:
        verdict = f"CAUTION: worst-case drop would breach 33% minimum from hist worst MR"
    else:
        verdict = f"OK: worst-case drop stays above 33% minimum from hist worst MR"
    print(f"    Verdict: {verdict}")
    print()

print("  ── Buffer threshold assessment:")
print()
print(f"  25% hard floor:")
for sc in SCENARIOS:
    ticker = sc['asset']
    df = data[ticker]
    d = abs(df['ctl_drop'].min())
    needed = min_mr_to_survive(d, HARD_FLOOR)
    sufficient = needed <= HARD_FLOOR
    print(f"    {sc['name']:>15}: need {needed*100:.1f}% to survive worst drop above 25% "
          f"— {'SELF-SUFFICIENT' if sufficient else f'NOT SELF-SUFFICIENT (need {needed*100:.1f}%)'}")

print()
print(f"  33% working minimum:")
for sc in SCENARIOS:
    ticker = sc['asset']
    df = data[ticker]
    d = abs(df['ctl_drop'].min())
    needed = min_mr_to_survive(d, WORK_MIN)
    sufficient = needed <= WORK_MIN
    print(f"    {sc['name']:>15}: need {needed*100:.1f}% to survive worst drop above 33% "
          f"— {'SELF-SUFFICIENT' if sufficient else f'NOT SELF-SUFFICIENT (need {needed*100:.1f}%)'}")

print()
print("  NOTE: 'self-sufficient' means the threshold is high enough to guarantee")
print("  survival of the worst historical drop even when starting at exactly that MR.")
print("  A threshold that is NOT self-sufficient provides no guarantee — a position")
print("  sitting exactly at the threshold can still be liquidated by a bad day.")
print()
print("=" * 70)
print("Buffer analysis complete.")
print("=" * 70)
