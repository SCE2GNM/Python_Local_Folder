#!/usr/bin/env python3
"""
BTC SMA Stage A — Three Pre-Stage-B Investigations

Investigation 1: PCT Trail 25% reconciliation (2018-start only)
  Reproduce register figures: annual 48.9%, MtM MaxDD -30.5%, Sortino 1.246.
  Confirm whether disqualification in Stage A is a 2017 data inclusion artifact.

Investigation 2: Post-2019 MtM MaxDD for all 18 configurations
  MaxDD measured from 2019-01-01 onward only (peak reset at that date).
  Separates 2017-2018 bull/crash period from ongoing risk profile.

Investigation 3: Ex-outlier annual returns (excluding 2017 and 2021)
  Top 5 qualified + top 5 disqualified by Stage A annual return.
  Shows year-by-year returns and arithmetic mean for "normal years".
  2026 is partial (Jan-May) — included but flagged.
"""

import os, warnings
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

COSTS      = 0.0015
MIN_TRADES = 5
SMA_PERIOD = 120

FIXED_STOPS = [0.03, 0.05, 0.08, 0.10]
PCT_TRAILS  = [0.05, 0.08, 0.10, 0.20, 0.25, 0.30, 0.35]
ATR_CONFIGS = [(9, 2.0), (9, 2.5), (14, 2.0)]
SMA_BUFFERS = [0.03, 0.05, 0.08]

EXCLUDE_YEARS    = {2017, 2021}   # outlier years for Investigation 3
POST_MAXDD_START = pd.Timestamp('2019-01-01')


# ─────────────────────────────────────────────────────────────────────────────
# SHARED FUNCTIONS  (identical methodology to btc_sma_stage_a.py)
# ─────────────────────────────────────────────────────────────────────────────

def compute_atr(high, low, close, period):
    prev = pd.Series(close).shift(1)
    tr   = pd.concat([pd.Series(high - low),
                      (pd.Series(high) - prev).abs(),
                      (pd.Series(low)  - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/period, adjust=False).mean().values


def build_equity_curve(trades_df, close_series):
    n         = len(close_series)
    arr       = close_series.values.astype(float)
    date_idx  = pd.Series(np.arange(n), index=close_series.index)
    equity    = np.ones(n)
    portfolio = 1.0
    prev_i    = 0
    for _, t in trades_df.iterrows():
        ei = date_idx.get(pd.Timestamp(t['entry_date']))
        xi = date_idx.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None or xi >= n:
            continue
        equity[prev_i:ei]  = portfolio
        equity[ei:xi+1]    = portfolio * arr[ei:xi+1] / t['entry_price']
        portfolio          *= (1 + t['return'] - COSTS)
        equity[xi]          = portfolio
        prev_i              = xi + 1
    equity[prev_i:] = portfolio
    return equity


def calc_metrics(trades_df, close_series, years):
    if len(trades_df) < MIN_TRADES:
        return None
    rets    = trades_df['return'].values - COSTS
    winners = rets[rets > 0]
    losers  = rets[rets <= 0]
    eq_pt   = np.cumprod(1 + rets)
    pk_pt   = np.maximum.accumulate(eq_pt)
    dd_pt   = ((eq_pt - pk_pt) / pk_pt).min()
    ann     = (eq_pt[-1]) ** (1/years) - 1
    calmar  = ann / abs(dd_pt) if dd_pt != 0 else 0.0
    equity  = build_equity_curve(trades_df, close_series)
    dr      = np.diff(equity) / equity[:-1]
    down    = dr[dr < 0]
    sortino = (dr.mean() / down.std() * np.sqrt(365)
               if len(down) > 0 and down.std() > 0 else 0.0)
    pk_eq   = np.maximum.accumulate(equity)
    dd_mtm  = ((equity - pk_eq) / pk_eq).min()
    return {
        'n_trades': len(trades_df), 'annual_return': ann,
        'max_dd_trade': dd_pt, 'max_dd_mtm': dd_mtm,
        'calmar': calmar, 'sortino': sortino,
        'win_rate': (rets > 0).mean(),
        'avg_win': winners.mean() if len(winners) > 0 else 0.0,
        'avg_loss': losers.mean() if len(losers) > 0 else 0.0,
    }


def post_date_maxdd(equity, dates, start_dt):
    """MtM MaxDD measured from start_dt onwards (peak reset at that date)."""
    idx = next((i for i, d in enumerate(dates) if d >= start_dt), None)
    if idx is None or idx >= len(equity):
        return np.nan
    eq_sl = equity[idx:]
    pk    = np.maximum.accumulate(eq_sl)
    return ((eq_sl - pk) / pk).min()


def year_returns_from_equity(equity, dates):
    result = {}
    for yr in sorted(set(d.year for d in dates)):
        idx = [i for i, d in enumerate(dates) if d.year == yr]
        if not idx:
            continue
        result[yr] = equity[idx[-1]] / equity[idx[0]] - 1
    return result


# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST FUNCTIONS  (identical to Stage A)
# ─────────────────────────────────────────────────────────────────────────────

def run_sma_no_stop(closes, lows, sma_vals, dates):
    pos = 0; ep = 0.0; entry_date = None; trades = []
    for i in range(1, len(closes)):
        cl, sma = closes[i], sma_vals[i]
        if np.isnan(sma): continue
        if pos == 1:
            if cl < sma:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': cl,
                                'return': (cl-ep)/ep, 'exit_reason': 'SMA_EXIT'})
                pos = 0; ep = 0.0; entry_date = None
        elif cl > sma:
            ep = cl; pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)


def run_sma_fixed_stop(closes, lows, sma_vals, dates, stop_pct):
    pos = 0; ep = sp = 0.0; entry_date = None; trades = []
    for i in range(1, len(closes)):
        lo, cl, sma = lows[i], closes[i], sma_vals[i]
        if np.isnan(sma): continue
        if pos == 1:
            if lo <= sp:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': sp,
                                'return': (sp-ep)/ep, 'exit_reason': 'STOP'})
                pos = 0; ep = sp = 0.0; entry_date = None
            elif cl < sma:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': cl,
                                'return': (cl-ep)/ep, 'exit_reason': 'SMA_EXIT'})
                pos = 0; ep = sp = 0.0; entry_date = None
        elif cl > sma:
            ep = cl; sp = cl*(1-stop_pct); pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)


def run_sma_pct_trail(closes, lows, sma_vals, dates, trail_pct):
    pos = 0; ep = pk = sp = 0.0; entry_date = None; trades = []
    for i in range(1, len(closes)):
        lo, cl, sma = lows[i], closes[i], sma_vals[i]
        if np.isnan(sma): continue
        if pos == 1:
            if lo <= sp:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': sp,
                                'return': (sp-ep)/ep, 'exit_reason': 'TRAIL_STOP'})
                pos = 0; ep = pk = sp = 0.0; entry_date = None
            elif cl < sma:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': cl,
                                'return': (cl-ep)/ep, 'exit_reason': 'SMA_EXIT'})
                pos = 0; ep = pk = sp = 0.0; entry_date = None
            else:
                if cl > pk:
                    pk = cl; sp = pk*(1-trail_pct)
        elif cl > sma:
            ep = pk = cl; sp = cl*(1-trail_pct); pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)


def run_sma_atr_trail(closes, lows, sma_vals, atr_vals, dates, atr_mult):
    pos = 0; ep = pk = sp = 0.0; entry_date = None; trades = []
    for i in range(1, len(closes)):
        lo, cl, sma, atr = lows[i], closes[i], sma_vals[i], atr_vals[i]
        if np.isnan(sma) or np.isnan(atr): continue
        if pos == 1:
            if lo <= sp:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': sp,
                                'return': (sp-ep)/ep, 'exit_reason': 'ATR_STOP'})
                pos = 0; ep = pk = sp = 0.0; entry_date = None
            elif cl < sma:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': cl,
                                'return': (cl-ep)/ep, 'exit_reason': 'SMA_EXIT'})
                pos = 0; ep = pk = sp = 0.0; entry_date = None
            else:
                if cl > pk: pk = cl
                sp = max(sp, pk - atr_mult*atr)
        elif cl > sma:
            ep = pk = cl; sp = cl - atr_mult*atr; pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)


def run_sma_relative_stop(closes, lows, sma_vals, dates, buffer_pct):
    pos = 0; ep = 0.0; entry_date = None; trades = []
    for i in range(1, len(closes)):
        lo, cl, sma = lows[i], closes[i], sma_vals[i]
        if np.isnan(sma): continue
        sl = sma * (1 - buffer_pct)
        if pos == 1:
            if lo <= sl:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': sl,
                                'return': (sl-ep)/ep, 'exit_reason': 'SMA_REL_STOP'})
                pos = 0; ep = 0.0; entry_date = None
            elif cl <= sl:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': cl,
                                'return': (cl-ep)/ep, 'exit_reason': 'SMA_REL_STOP'})
                pos = 0; ep = 0.0; entry_date = None
        elif cl > sma:
            ep = cl; pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)


# ─────────────────────────────────────────────────────────────────────────────
# FETCH DATA — both start dates
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*72)
print("BTC SMA STAGE A — THREE PRE-STAGE-B INVESTIGATIONS")
print("="*72)

print("\nFetching BTC-USD (2017-01-01)...")
raw17 = yf.download('BTC-USD', start='2017-01-01', auto_adjust=True, progress=False)
if isinstance(raw17.columns, pd.MultiIndex):
    raw17.columns = raw17.columns.get_level_values(0)
df17 = raw17[['High','Low','Close']].copy().dropna()

print("Fetching BTC-USD (2018-01-01)...")
raw18 = yf.download('BTC-USD', start='2018-01-01', auto_adjust=True, progress=False)
if isinstance(raw18.columns, pd.MultiIndex):
    raw18.columns = raw18.columns.get_level_values(0)
df18 = raw18[['High','Low','Close']].copy().dropna()

# 2017-start arrays
closes17 = df17['Close'].values.astype(float)
lows17   = df17['Low'].values.astype(float)
highs17  = df17['High'].values.astype(float)
dates17  = df17.index
years17  = (dates17[-1] - dates17[0]).days / 365.25
sma17    = pd.Series(closes17).rolling(SMA_PERIOD).mean().values

# 2018-start arrays
closes18 = df18['Close'].values.astype(float)
lows18   = df18['Low'].values.astype(float)
highs18  = df18['High'].values.astype(float)
dates18  = df18.index
years18  = (dates18[-1] - dates18[0]).days / 365.25
sma18    = pd.Series(closes18).rolling(SMA_PERIOD).mean().values

# ATR caches
atr_cache17 = {p: compute_atr(highs17, lows17, closes17, p) for p in {ap for ap,_ in ATR_CONFIGS}}
atr_cache18 = {p: compute_atr(highs18, lows18, closes18, p) for p in {ap for ap,_ in ATR_CONFIGS}}

print(f"  2017-start: {dates17[0].date()} → {dates17[-1].date()}  ({years17:.2f} yrs)")
print(f"  2018-start: {dates18[0].date()} → {dates18[-1].date()}  ({years18:.2f} yrs)")


# ─────────────────────────────────────────────────────────────────────────────
# INVESTIGATION 1 — PCT Trail 25% on 2018-start data
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*72)
print("INVESTIGATION 1 — PCT Trail 25%: 2018-start Reconciliation")
print("  Register figures: Annual 48.9%, MtM MaxDD -30.5%, Sortino 1.246, N~34")
print("="*72)

# Run on 2017-start (already have from Stage A)
t25_17 = run_sma_pct_trail(closes17, lows17, sma17, dates17, 0.25)
m25_17 = calc_metrics(t25_17, df17['Close'], years17)
eq25_17 = build_equity_curve(t25_17, df17['Close'])

# Run on 2018-start
t25_18 = run_sma_pct_trail(closes18, lows18, sma18, dates18, 0.25)
m25_18 = calc_metrics(t25_18, df18['Close'], years18)
eq25_18 = build_equity_curve(t25_18, df18['Close'])

print(f"\n  {'Metric':<30} {'2017-start':>14} {'2018-start':>14} {'Register':>14}")
print(f"  {'─'*74}")
print(f"  {'N trades':<30} {m25_17['n_trades']:>14} {m25_18['n_trades']:>14} {'~34':>14}")
print(f"  {'Annual return %':<30} {m25_17['annual_return']*100:>13.1f}% {m25_18['annual_return']*100:>13.1f}% {'48.9%':>14}")
print(f"  {'MtM MaxDD %':<30} {m25_17['max_dd_mtm']*100:>13.1f}% {m25_18['max_dd_mtm']*100:>13.1f}% {'-30.5%':>14}")
print(f"  {'Per-trade MaxDD %':<30} {m25_17['max_dd_trade']*100:>13.1f}% {m25_18['max_dd_trade']*100:>13.1f}% {'-17.8%':>14}")
print(f"  {'Sortino':<30} {m25_17['sortino']:>14.3f} {m25_18['sortino']:>14.3f} {'1.246':>14}")
print(f"  {'Calmar':<30} {m25_17['calmar']:>14.3f} {m25_18['calmar']:>14.3f} {'2.752':>14}")
print(f"  {'Win rate %':<30} {m25_17['win_rate']*100:>13.0f}% {m25_18['win_rate']*100:>13.0f}% {'~60%':>14}")

# Qualification check
dq_17 = m25_17['max_dd_mtm'] < -0.50
dq_18 = m25_18['max_dd_mtm'] < -0.50
print(f"\n  MtM MaxDD < -50% filter:")
print(f"    2017-start: {'DISQUALIFIED' if dq_17 else 'QUALIFIES'} (MtM MaxDD {m25_17['max_dd_mtm']*100:.1f}%)")
print(f"    2018-start: {'DISQUALIFIED' if dq_18 else 'QUALIFIES'} (MtM MaxDD {m25_18['max_dd_mtm']*100:.1f}%)")

# Year-by-year for PCT Trail 25% — 2017 start, to show what caused DQ
yr25_17 = year_returns_from_equity(eq25_17, dates17)
yr25_18 = year_returns_from_equity(eq25_18, dates18)
all_yrs = sorted(set(yr25_17) | set(yr25_18))

print(f"\n  Year-by-year (to identify the DQ driver):")
print(f"  {'Year':<6} {'2017-start':>12} {'2018-start':>12}")
print(f"  {'─'*32}")
for yr in all_yrs:
    v17 = yr25_17.get(yr, None)
    v18 = yr25_18.get(yr, None)
    s17 = f"{v17*100:>+11.1f}%" if v17 is not None else f"{'—':>12}"
    s18 = f"{v18*100:>+11.1f}%" if v18 is not None else f"{'—':>12}"
    flag = ' ← DQ driver' if yr == 2018 and v17 is not None and v17 < -0.40 else ''
    print(f"  {yr:<6} {s17} {s18}{flag}")

if dq_17 and not dq_18:
    print(f"\n  VERDICT: Disqualification is a 2017 data inclusion artifact.")
    print(f"  The 2017 bull run (+1318% BTC) set a peak that the 2018 crash pulled")
    print(f"  the equity deep below. With 2018-start the MtM MaxDD is within the")
    print(f"  -50% threshold. The register figures are reproducible with 2018-start.")
elif dq_17 and dq_18:
    print(f"\n  VERDICT: Disqualified on BOTH starts. Genuine risk concern, not artifact.")
elif not dq_17 and not dq_18:
    print(f"\n  VERDICT: Qualifies on both starts. No data-start sensitivity.")
else:
    print(f"\n  VERDICT: Qualifies on 2017-start but not 2018-start — unexpected.")


# ─────────────────────────────────────────────────────────────────────────────
# INVESTIGATION 2 — Post-2019 MtM MaxDD for all 18 configurations
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*72)
print("INVESTIGATION 2 — Post-2019 MtM MaxDD for All 18 Configurations")
print(f"  Full-period MaxDD vs MaxDD measured from {POST_MAXDD_START.date()} only")
print(f"  (Peak reset at 2019-01-01 — 2017-2018 bull/crash excluded from measure)")
print("="*72)

# Run all configs on 2017-start data, compute equity curves, then post-2019 MaxDD
all_cfgs = [('No Stop (SMA only)', 'none', None, None, True)]
for sp in FIXED_STOPS:
    all_cfgs.append((f'Fixed {sp*100:.0f}%', 'fixed', sp, None, False))
for tp in PCT_TRAILS:
    all_cfgs.append((f'PCT Trail {tp*100:.0f}%', 'trail_pct', tp, None, False))
for (ap, am) in ATR_CONFIGS:
    all_cfgs.append((f'ATR{ap} {am}x', 'trail_atr', ap, am, False))
for bp in SMA_BUFFERS:
    all_cfgs.append((f'SMA-Rel {bp*100:.0f}%', 'sma_rel', bp, None, False))

inv2_rows = []
for (label, stype, pa, pb, is_bl) in all_cfgs:
    if stype == 'none':
        t = run_sma_no_stop(closes17, lows17, sma17, dates17)
    elif stype == 'fixed':
        t = run_sma_fixed_stop(closes17, lows17, sma17, dates17, pa)
    elif stype == 'trail_pct':
        t = run_sma_pct_trail(closes17, lows17, sma17, dates17, pa)
    elif stype == 'trail_atr':
        t = run_sma_atr_trail(closes17, lows17, sma17, atr_cache17[pa], dates17, pb)
    elif stype == 'sma_rel':
        t = run_sma_relative_stop(closes17, lows17, sma17, dates17, pa)
    else:
        continue

    if len(t) < MIN_TRADES:
        continue
    m      = calc_metrics(t, df17['Close'], years17)
    if m is None:
        continue
    equity = build_equity_curve(t, df17['Close'])
    dd_post = post_date_maxdd(equity, dates17, POST_MAXDD_START)
    qualified_full = m['max_dd_mtm'] >= -0.50
    qualified_post = dd_post >= -0.50

    inv2_rows.append({
        'label': label, 'stop_type': stype, 'is_baseline': is_bl,
        'n_trades': m['n_trades'],
        'annual_return': m['annual_return'],
        'full_mtm_dd': m['max_dd_mtm'],
        'post2019_dd': dd_post,
        'sortino': m['sortino'],
        'calmar': m['calmar'],
        'q_full': qualified_full,
        'q_post': qualified_post,
    })

# Sort by annual return descending
inv2_rows.sort(key=lambda x: x['annual_return'], reverse=True)

print(f"\n  {'Label':<24} {'N':>4}  {'Annual%':>8}  {'FullMtMDD%':>11}  "
      f"{'Post-2019DD%':>13}  {'Sortino':>8}  {'Q-Full':>7}  {'Q-Post':>7}")
print(f"  {'─'*100}")

changed = []
for r in inv2_rows:
    bl_tag = ' [REF]' if r['is_baseline'] else ''
    q_full = '✓' if r['q_full'] else '✗'
    q_post = '✓' if r['q_post'] else '✗'
    flip   = ' ← flips' if r['q_full'] != r['q_post'] else ''
    if r['q_full'] != r['q_post']:
        changed.append(r['label'])
    print(f"  {r['label']+bl_tag:<24} {r['n_trades']:>4}  "
          f"{r['annual_return']*100:>+7.1f}%  {r['full_mtm_dd']*100:>10.1f}%  "
          f"{r['post2019_dd']*100:>12.1f}%  {r['sortino']:>8.3f}  "
          f"{q_full:>7}  {q_post:>7}{flip}")

print(f"\n  Q-Full = qualifies under full-period MtM MaxDD ≥ -50%")
print(f"  Q-Post = qualifies under post-2019 MtM MaxDD ≥ -50%")
if changed:
    print(f"\n  Configs that change qualification status when using Post-2019 MaxDD:")
    for lbl in changed:
        row = next(r for r in inv2_rows if r['label'] == lbl)
        direction = 'DQ→Q' if not row['q_full'] and row['q_post'] else 'Q→DQ'
        print(f"    {lbl}: {direction}  "
              f"(Full {row['full_mtm_dd']*100:.1f}%  Post-2019 {row['post2019_dd']*100:.1f}%)")
else:
    print(f"\n  No configs change qualification status. "
          f"Full-period and Post-2019 MaxDD agree.")

# Summary counts
n_q_full = sum(1 for r in inv2_rows if r['q_full'] and not r['is_baseline'])
n_q_post = sum(1 for r in inv2_rows if r['q_post'] and not r['is_baseline'])
print(f"\n  Qualified (deployable configs only, excl. baseline):")
print(f"    Full-period filter:  {n_q_full} / {len(inv2_rows)-1}")
print(f"    Post-2019 filter:    {n_q_post} / {len(inv2_rows)-1}")


# ─────────────────────────────────────────────────────────────────────────────
# INVESTIGATION 3 — Ex-outlier annual returns
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*72)
print("INVESTIGATION 3 — Ex-Outlier Annual Returns (excl. 2017 and 2021)")
print(f"  Outlier years excluded: {sorted(EXCLUDE_YEARS)}")
print(f"  2026 is partial (Jan–May) — included in average, flagged *")
print("="*72)

# Pull the Stage A qualified + top disqualified, using the full 2017-start data
# Qualified (from Stage A): PCT Trail 8%, PCT Trail 5%
# We already have inv2_rows sorted by annual_return — use those
# Top 5 qualified (excl. baseline): those with q_full = True
# Top 5 disqualified (excl. baseline): those with q_full = False

inv3_qualified = [r for r in inv2_rows if r['q_full'] and not r['is_baseline']][:5]
inv3_disqual   = [r for r in inv2_rows if not r['q_full'] and not r['is_baseline']][:5]
inv3_rows_all  = inv3_qualified + inv3_disqual

# Re-run to get equity curves for year-by-year
def get_equity_for_label(label, stype, pa, pb):
    if stype == 'none':
        t = run_sma_no_stop(closes17, lows17, sma17, dates17)
    elif stype == 'fixed':
        t = run_sma_fixed_stop(closes17, lows17, sma17, dates17, pa)
    elif stype == 'trail_pct':
        t = run_sma_pct_trail(closes17, lows17, sma17, dates17, pa)
    elif stype == 'trail_atr':
        t = run_sma_atr_trail(closes17, lows17, sma17, atr_cache17[pa], dates17, pb)
    elif stype == 'sma_rel':
        t = run_sma_relative_stop(closes17, lows17, sma17, dates17, pa)
    else:
        return None
    if len(t) < MIN_TRADES:
        return None
    return build_equity_curve(t, df17['Close'])

for r in inv3_rows_all:
    # Extract pa, pb from the cfg list
    cfg = next((c for c in all_cfgs if c[0] == r['label']), None)
    if cfg is None:
        continue
    _, stype, pa, pb, _ = cfg
    eq = get_equity_for_label(r['label'], stype, pa, pb)
    if eq is not None:
        r['yr_returns'] = year_returns_from_equity(eq, dates17)
    else:
        r['yr_returns'] = {}

# B&H year-by-year
bh_eq17  = closes17 / closes17[0]
bh_yr17  = year_returns_from_equity(bh_eq17, dates17)

all_yrs_17 = sorted(set(dates17.year))
normal_yrs = [yr for yr in all_yrs_17 if yr not in EXCLUDE_YEARS]

# Print table — years as columns, ex-outlier avg as final column
# Split into two prints: full year-by-year then ex-outlier summary

CW = 8
print(f"\n  Part A: Year-by-year returns (all years, outliers highlighted)")

hdr_years = "".join(f"{'*'+str(yr) if yr in EXCLUDE_YEARS else str(yr):>{CW}}" for yr in all_yrs_17)
print(f"\n  {'Config':<26}{hdr_years}  {'ExOutlierAvg':>13}")
print(f"  {'─'*(26 + CW*len(all_yrs_17) + 15)}")

def fmt_r(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return f"{'—':>{CW}}"
    return f"{v*100:>+7.1f}%"

def section_label(is_q):
    return 'QUALIFIED' if is_q else 'DISQUALIFIED'

prev_tier = None
for r in inv3_rows_all:
    tier = r['q_full']
    if tier != prev_tier:
        lbl = 'QUALIFIED (MtM MaxDD ≥ -50%)' if tier else 'DISQUALIFIED (MtM MaxDD < -50%)'
        print(f"\n  ── {lbl} ──")
        prev_tier = tier

    yr_d = r.get('yr_returns', {})
    row_vals = [yr_d.get(yr) for yr in all_yrs_17]
    normal_vals = [yr_d.get(yr) for yr in normal_yrs if yr_d.get(yr) is not None]
    avg_normal = np.mean(normal_vals) if normal_vals else np.nan

    flag_2026 = '*' if 2026 in normal_yrs else ''
    row = f"  {r['label']:<26}"
    row += "".join(fmt_r(v) for v in row_vals)
    avg_str = f"{avg_normal*100:>+12.1f}%" if not np.isnan(avg_normal) else f"{'—':>13}"
    print(row + f"  {avg_str}")

# B&H row
bh_row_vals  = [bh_yr17.get(yr) for yr in all_yrs_17]
bh_normal    = [bh_yr17.get(yr) for yr in normal_yrs if bh_yr17.get(yr) is not None]
bh_avg       = np.mean(bh_normal)
bh_row_str   = f"  {'B&H BTC':<26}" + "".join(fmt_r(v) for v in bh_row_vals)
print(bh_row_str + f"  {bh_avg*100:>+12.1f}%")

print(f"\n  * Columns marked * are outlier years (excluded from ExOutlierAvg)")
print(f"  * 2026 column is partial year (Jan–May) — included in ExOutlierAvg")
print(f"  Normal years used in average: {normal_yrs}")

# Part B: Summary table — ex-outlier avg vs full-period annual
print(f"\n  Part B: Ex-Outlier Average vs Full-Period Annual Return")
print(f"\n  {'Config':<26} {'FullPeriod%':>12} {'ExOutlierAvg%':>14} {'Difference':>11} {'Q-Full':>7}")
print(f"  {'─'*74}")
for r in inv3_rows_all:
    yr_d = r.get('yr_returns', {})
    normal_vals = [yr_d.get(yr) for yr in normal_yrs if yr_d.get(yr) is not None]
    avg_normal  = np.mean(normal_vals) if normal_vals else np.nan
    diff        = avg_normal - r['annual_return'] if not np.isnan(avg_normal) else np.nan
    q_str = '✓' if r['q_full'] else '✗'
    avg_s = f"{avg_normal*100:>+13.1f}%" if not np.isnan(avg_normal) else f"{'—':>14}"
    dif_s = f"{diff*100:>+10.1f}pp" if not np.isnan(diff) else f"{'—':>11}"
    print(f"  {r['label']:<26} {r['annual_return']*100:>+11.1f}% {avg_s} {dif_s} {q_str:>7}")

bh_normal_avg = np.mean(bh_normal) if bh_normal else np.nan
bh_full_ann   = (bh_eq17[-1]) ** (1/years17) - 1
bh_diff       = bh_normal_avg - bh_full_ann
print(f"  {'B&H BTC':<26} {bh_full_ann*100:>+11.1f}% {bh_normal_avg*100:>+13.1f}%"
      f" {bh_diff*100:>+10.1f}pp {'REF':>7}")

print(f"\n  KEY OBSERVATIONS:")

# Find best ex-outlier performer among qualified
q_with_avg = [(r, np.mean([r['yr_returns'].get(yr) for yr in normal_yrs
                            if r['yr_returns'].get(yr) is not None]))
              for r in inv3_qualified if r.get('yr_returns')]
q_with_avg = [(r, a) for r, a in q_with_avg if not np.isnan(a)]
if q_with_avg:
    best_q = max(q_with_avg, key=lambda x: x[1])
    print(f"  Best qualified ex-outlier avg: {best_q[0]['label']} "
          f"({best_q[1]*100:+.1f}%/yr in normal years)")

dq_with_avg = [(r, np.mean([r['yr_returns'].get(yr) for yr in normal_yrs
                             if r['yr_returns'].get(yr) is not None]))
               for r in inv3_disqual if r.get('yr_returns')]
dq_with_avg = [(r, a) for r, a in dq_with_avg if not np.isnan(a)]
if dq_with_avg:
    best_dq = max(dq_with_avg, key=lambda x: x[1])
    print(f"  Best DQ ex-outlier avg:        {best_dq[0]['label']} "
          f"({best_dq[1]*100:+.1f}%/yr in normal years)")
    print(f"  Note: {best_dq[0]['label']} is disqualified on full-period MtM MaxDD")
    print(f"        but its normal-year performance may be competitive. Consider")
    print(f"        re-evaluating with Post-2019 MaxDD from Investigation 2.")

print(f"\n{'='*72}")
print("ALL THREE INVESTIGATIONS COMPLETE")
print("Review before proceeding to Stage B.")
print(f"{'='*72}\n")
