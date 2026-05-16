#!/usr/bin/env python3
"""
BTC SMA Stage B — SMA Period Stability Sweep
Primary candidate: PCT Trail 8%
Primary data:  2018-01-01 (2017-01-01 as secondary reference column)
SMA sweep:     80, 90, 100, 110, 115, 120, 125, 130, 140, 150, 160
Walk-forward:  expanding train from 2018-01-01; test windows 2022, 2023, 2024
GO/NO-GO:      same 6-check framework as BTC ADX Stage B
"""

import os, warnings
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

COSTS      = 0.0015
TRAIL_PCT  = 0.08
MIN_TRADES = 5

SMA_SWEEP  = [80, 90, 100, 110, 115, 120, 125, 130, 140, 150, 160]

# GO/NO-GO thresholds (2018-start basis)
THRESH_SORTINO     = 0.8
THRESH_CALMAR      = 1.0
THRESH_N_TRADES    = 30
THRESH_POST2022    = 0.15   # 15% per year post-2022
WF_WINDOWS_NEEDED  = 2      # of 3
STABILITY_PASS     = {'STABLE', 'MARGINAL'}

POST2022_START     = pd.Timestamp('2022-01-01')
PRE2022_END        = pd.Timestamp('2021-12-31')

# ─────────────────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 72)
print("BTC SMA STAGE B — SMA Period Stability Sweep (PCT Trail 8%)")
print("=" * 72)
print()
print("Fetching BTC-USD data ...")

raw17 = yf.download('BTC-USD', start='2017-01-01', progress=False, auto_adjust=True)
raw18 = yf.download('BTC-USD', start='2018-01-01', progress=False, auto_adjust=True)

def prep(raw):
    raw.columns = [c[0].lower() if isinstance(c, tuple) else c.lower()
                   for c in raw.columns]
    closes = raw['close'].values.astype(float)
    lows   = raw['low'].values.astype(float)
    dates  = [pd.Timestamp(d) for d in raw.index]
    years  = (pd.Timestamp(dates[-1]) - pd.Timestamp(dates[0])).days / 365.25
    return closes, lows, dates, years

c17, l17, d17, y17 = prep(raw17)
c18, l18, d18, y18 = prep(raw18)

print(f"  2017-start: {d17[0].date()} → {d17[-1].date()}  ({y17:.2f} yrs)")
print(f"  2018-start: {d18[0].date()} → {d18[-1].date()}  ({y18:.2f} yrs)")

# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST — PCT TRAIL
# ─────────────────────────────────────────────────────────────────────────────

def run_pct_trail(closes, lows, sma_vals, dates, trail_pct):
    pos = 0; ep = peak = stop = 0.0; entry_date = None; trades = []
    for i in range(1, len(closes)):
        lo, cl, sm = lows[i], closes[i], sma_vals[i]
        if np.isnan(sm):
            continue
        if pos == 1:
            if cl > peak:
                peak = cl; stop = peak * (1 - trail_pct)
            if lo <= stop:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                               'exit_date': dates[i], 'exit_price': stop,
                               'return': (stop - ep) / ep, 'exit_reason': 'TRAIL_STOP'})
                pos = 0; ep = peak = stop = 0.0; entry_date = None
            elif cl < sm:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                               'exit_date': dates[i], 'exit_price': cl,
                               'return': (cl - ep) / ep, 'exit_reason': 'SMA_EXIT'})
                pos = 0; ep = peak = stop = 0.0; entry_date = None
        elif cl > sm:
            ep = cl; peak = cl; stop = cl * (1 - trail_pct); pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)

# ─────────────────────────────────────────────────────────────────────────────
# EQUITY CURVE + METRICS
# ─────────────────────────────────────────────────────────────────────────────

def build_equity(trades_df, close_vals, date_list):
    n         = len(close_vals)
    date_idx  = {d: i for i, d in enumerate(date_list)}
    equity    = np.ones(n)
    portfolio = 1.0; prev_i = 0
    for _, t in trades_df.iterrows():
        ei = date_idx.get(pd.Timestamp(t['entry_date']))
        xi = date_idx.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None or xi >= n:
            continue
        equity[prev_i:ei] = portfolio
        equity[ei:xi+1]   = portfolio * close_vals[ei:xi+1] / t['entry_price']
        portfolio         *= (1 + t['return'] - COSTS)
        equity[xi]         = portfolio
        prev_i             = xi + 1
    equity[prev_i:] = portfolio
    return equity


def calc_metrics(trades_df, equity, years):
    if len(trades_df) < MIN_TRADES:
        return None
    rets    = trades_df['return'].values - COSTS
    winners = rets[rets > 0]
    losers  = rets[rets <= 0]
    eq_pt   = np.cumprod(1 + rets)
    pk_pt   = np.maximum.accumulate(eq_pt)
    dd_pt   = ((eq_pt - pk_pt) / pk_pt).min()
    ann     = eq_pt[-1] ** (1 / years) - 1
    calmar  = ann / abs(dd_pt) if dd_pt != 0 else 0.0
    dr      = np.diff(equity) / equity[:-1]
    down    = dr[dr < 0]
    sortino = (dr.mean() / down.std() * np.sqrt(365)
               if len(down) > 0 and down.std() > 0 else 0.0)
    pk_eq   = np.maximum.accumulate(equity)
    dd_mtm  = ((equity - pk_eq) / pk_eq).min()
    return {
        'n_trades':     len(trades_df),
        'annual':       ann,
        'max_dd_trade': dd_pt,
        'max_dd_mtm':   dd_mtm,
        'calmar':       calmar,
        'sortino':      sortino,
        'win_rate':     (rets > 0).mean(),
        'avg_win':      winners.mean() if len(winners) > 0 else 0.0,
        'avg_loss':     losers.mean()  if len(losers)  > 0 else 0.0,
    }


def post_date_maxdd(equity, dates, start_dt):
    idx = next((i for i, d in enumerate(dates) if d >= start_dt), None)
    if idx is None or idx >= len(equity):
        return np.nan
    eq_sl = equity[idx:]
    pk    = np.maximum.accumulate(eq_sl)
    return ((eq_sl - pk) / pk).min()


def split_annual(equity, dates, split_dt, start_dt, end_dt=None):
    """Annualised return for equity slice between start_dt and end_dt (or data end)."""
    idx_s = next((i for i, d in enumerate(dates) if d >= start_dt), None)
    if end_dt is not None:
        idx_e = next((i for i, d in enumerate(dates) if d > end_dt), len(dates)) - 1
    else:
        idx_e = len(dates) - 1
    if idx_s is None or idx_e <= idx_s:
        return np.nan
    n_yrs = (dates[idx_e] - dates[idx_s]).days / 365.25
    if n_yrs < 0.5:
        return np.nan
    return (equity[idx_e] / equity[idx_s]) ** (1 / n_yrs) - 1


def year_returns(equity, dates):
    result = {}
    for yr in sorted(set(d.year for d in dates)):
        idx = [i for i, d in enumerate(dates) if d.year == yr]
        if not idx:
            continue
        result[yr] = equity[idx[-1]] / equity[idx[0]] - 1
    return result

# ─────────────────────────────────────────────────────────────────────────────
# RUN SWEEP
# ─────────────────────────────────────────────────────────────────────────────

rows = []

for sma_n in SMA_SWEEP:
    # 2018-start (primary)
    sma18 = pd.Series(c18).rolling(sma_n).mean().values
    tr18  = run_pct_trail(c18, l18, sma18, d18, TRAIL_PCT)
    if len(tr18) == 0:
        continue
    eq18  = build_equity(tr18, c18, d18)
    m18   = calc_metrics(tr18, eq18, y18)
    if m18 is None:
        continue
    pre22_ann  = split_annual(eq18, d18, None, pd.Timestamp('2018-01-01'), PRE2022_END)
    post22_ann = split_annual(eq18, d18, POST2022_START, POST2022_START, None)
    post22_dd  = post_date_maxdd(eq18, d18, POST2022_START)

    # 2017-start (reference)
    sma17 = pd.Series(c17).rolling(sma_n).mean().values
    tr17  = run_pct_trail(c17, l17, sma17, d17, TRAIL_PCT)
    eq17  = build_equity(tr17, c17, d17) if len(tr17) > 0 else None
    m17   = calc_metrics(tr17, eq17, y17) if eq17 is not None else None

    rows.append({
        'sma':              sma_n,
        # 2018-start primary
        'n18':              m18['n_trades'],
        'ann18':            m18['annual'],
        'sortino18':        m18['sortino'],
        'calmar18':         m18['calmar'],
        'dd_trade18':       m18['max_dd_trade'],
        'dd_mtm18':         m18['max_dd_mtm'],
        'win18':            m18['win_rate'],
        'pre22_ann':        pre22_ann,
        'post22_ann':       post22_ann,
        'post22_dd':        post22_dd,
        # 2017-start reference
        'ann17':            m17['annual'] if m17 else np.nan,
        'dd_mtm17':         m17['max_dd_mtm'] if m17 else np.nan,
        'sortino17':        m17['sortino'] if m17 else np.nan,
    })

df = pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE STABILITY SCORE (2018-start metrics)
# ─────────────────────────────────────────────────────────────────────────────

def norm(series):
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - mn) / (mx - mn)

df['comp'] = (
    norm(df['ann18'])        * 0.35 +
    norm(df['sortino18'])    * 0.30 +
    norm(df['calmar18'])     * 0.25 +
    norm(-df['dd_mtm18'])    * 0.10
)

COMP_PASS = 0.70

df['passes_comp'] = df['comp'] >= COMP_PASS

n_pass = df['passes_comp'].sum()
n_total = len(df)
pct_pass = n_pass / n_total

if pct_pass >= 0.60:
    stab_class = 'STABLE'
elif pct_pass >= 0.40:
    stab_class = 'MARGINAL'
else:
    stab_class = 'FRAGILE'

# Cliff-edge check: best SMA at boundary?
best_idx = df['ann18'].idxmax()
best_sma = df.loc[best_idx, 'sma']
at_boundary = (best_sma == SMA_SWEEP[0]) or (best_sma == SMA_SWEEP[-1])
cliff_check = 'FAIL (best at boundary — cliff edge)' if at_boundary else 'PASS (interior peak)'

# ─────────────────────────────────────────────────────────────────────────────
# YEAR-BY-YEAR TABLE (candidate SMA = 120, or best if different)
# ─────────────────────────────────────────────────────────────────────────────

CANDIDATE_SMA = 120

sma_cand18 = pd.Series(c18).rolling(CANDIDATE_SMA).mean().values
tr_cand    = run_pct_trail(c18, l18, sma_cand18, d18, TRAIL_PCT)
eq_cand    = build_equity(tr_cand, c18, d18)
yr_rets    = year_returns(eq_cand, d18)

# B&H equity curve
bh_eq = c18 / c18[0]
bh_yr = year_returns(bh_eq, d18)

# ─────────────────────────────────────────────────────────────────────────────
# WALK-FORWARD VALIDATION (candidate SMA)
# ─────────────────────────────────────────────────────────────────────────────

def wf_window(closes, lows, dates, sma_n, trail_pct, test_start, test_end):
    """Run strategy on full data; extract metrics for test-period trades only."""
    sma_vals = pd.Series(closes).rolling(sma_n).mean().values
    all_tr   = run_pct_trail(closes, lows, sma_vals, dates, trail_pct)
    if len(all_tr) == 0:
        return None
    # Filter trades that EXIT in the test window
    test_tr = all_tr[
        (all_tr['exit_date'] >= test_start) &
        (all_tr['exit_date'] <= test_end)
    ].copy()
    if len(test_tr) < 3:
        return {'n': len(test_tr), 'annual': np.nan, 'win_rate': np.nan,
                'dd_trade': np.nan, 'pass': False}
    # Test-period equity (isolated: start at 1.0 for this window)
    rets    = test_tr['return'].values - COSTS
    eq_pt   = np.cumprod(1 + rets)
    pk_pt   = np.maximum.accumulate(eq_pt)
    dd_pt   = ((eq_pt - pk_pt) / pk_pt).min()
    n_yrs   = (test_end - test_start).days / 365.25
    ann     = eq_pt[-1] ** (1 / n_yrs) - 1
    win     = (rets > 0).mean()
    passed  = ann > 0 and dd_pt > -0.50
    return {'n': len(test_tr), 'annual': ann, 'win_rate': win,
            'dd_trade': dd_pt, 'pass': passed}

wf_windows = [
    {'label': '2022', 'test_start': pd.Timestamp('2022-01-01'), 'test_end': pd.Timestamp('2022-12-31')},
    {'label': '2023', 'test_start': pd.Timestamp('2023-01-01'), 'test_end': pd.Timestamp('2023-12-31')},
    {'label': '2024', 'test_start': pd.Timestamp('2024-01-01'), 'test_end': pd.Timestamp('2024-12-31')},
]

wf_results = []
for w in wf_windows:
    res = wf_window(c18, l18, d18, CANDIDATE_SMA, TRAIL_PCT,
                    w['test_start'], w['test_end'])
    wf_results.append({'window': w['label'], **res})

wf_pass_count = sum(1 for w in wf_results if w.get('pass', False))
wf_verdict = 'PASS' if wf_pass_count >= WF_WINDOWS_NEEDED else 'FAIL'

# ─────────────────────────────────────────────────────────────────────────────
# GO/NO-GO CHECKS (candidate SMA = 120, 2018-start)
# ─────────────────────────────────────────────────────────────────────────────

cand_row = df[df['sma'] == CANDIDATE_SMA].iloc[0]

checks = {
    f'N trades >= {THRESH_N_TRADES}':        (cand_row['n18'] >= THRESH_N_TRADES,  f"{int(cand_row['n18'])} trades"),
    f'Sortino >= {THRESH_SORTINO}':           (cand_row['sortino18'] >= THRESH_SORTINO, f"{cand_row['sortino18']:.3f}"),
    f'Calmar >= {THRESH_CALMAR}':             (cand_row['calmar18']  >= THRESH_CALMAR,  f"{cand_row['calmar18']:.3f}"),
    f'Walk-forward >= {WF_WINDOWS_NEEDED}/3': (wf_pass_count >= WF_WINDOWS_NEEDED, f"{wf_pass_count}/3 windows"),
    'Stability STABLE or MARGINAL':           (stab_class in STABILITY_PASS, f"{stab_class} ({pct_pass:.0%})"),
    f'Post-2022 annual >= {THRESH_POST2022*100:.0f}%/yr': (
        cand_row['post22_ann'] >= THRESH_POST2022,
        f"{cand_row['post22_ann']*100:.1f}%/yr vs {THRESH_POST2022*100:.0f}% threshold"),
}

n_fail = sum(1 for v, _ in checks.values() if not v)
n_crit_fail = 0
crit_fails = []
for label, (passed, detail) in checks.items():
    if not passed and ('Post-2022' in label or 'Stability' in label):
        n_crit_fail += 1
        crit_fails.append(label)

if n_crit_fail >= 2:
    decision = 'NO-GO'
    decision_note = f'{n_crit_fail} hard failures'
elif n_crit_fail == 1:
    decision = 'CONDITIONAL GO' if n_fail <= 2 else 'NO-GO'
    decision_note = f'1 hard failure: {crit_fails[0]}' if decision == 'NO-GO' else '1 hard failure — review required'
elif n_fail == 0:
    decision = 'GO'
    decision_note = 'All checks passed'
elif n_fail == 1:
    decision = 'CONDITIONAL GO'
    decision_note = '1 soft failure'
else:
    decision = 'NO-GO'
    decision_note = f'{n_fail} failures'

# ─────────────────────────────────────────────────────────────────────────────
# PRINT RESULTS
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 72)
print("TABLE 1 — SMA SWEEP (PCT Trail 8%, 2018-start primary)")
print("=" * 72)
hdr = (f"  {'SMA':>4}  {'N':>4}  {'Ann%':>7}  {'Sort':>6}  {'Calm':>6}  "
       f"{'DD-Tr%':>7}  {'DD-MtM%':>8}  {'WinR':>5}  {'Comp':>5}  {'Q?':>4}  "
       f"[2017-ref: Ann%  DD-MtM%]")
print(hdr)
print("  " + "─" * 89)
for _, r in df.iterrows():
    flag = '  ← candidate' if r['sma'] == CANDIDATE_SMA else ''
    q    = '✓' if r['passes_comp'] else '✗'
    ref  = f"  {r['ann17']*100:+.1f}%  {r['dd_mtm17']*100:.1f}%" if not np.isnan(r['ann17']) else '  —      —'
    print(f"  {int(r['sma']):>4}  {int(r['n18']):>4}  {r['ann18']*100:>+6.1f}%  "
          f"{r['sortino18']:>6.3f}  {r['calmar18']:>6.3f}  "
          f"{r['dd_trade18']*100:>+6.1f}%  {r['dd_mtm18']*100:>+7.1f}%  "
          f"{r['win18']*100:>4.0f}%  {r['comp']:>5.3f}  {q:>4}{ref}{flag}")

print()
print(f"  Composite ≥ {COMP_PASS}: {n_pass}/{n_total} SMA values ({pct_pass:.0%})")
print(f"  Stability classification: {stab_class}")
print(f"  Cliff-edge check: {cliff_check}")

print()
print("=" * 72)
print("TABLE 2 — PRE/POST-2022 HALF-SPLIT (2018-start basis)")
print("=" * 72)
print(f"  {'SMA':>4}  {'Pre-2022 Ann%':>14}  {'Post-2022 Ann%':>15}  {'Post-2022 MtM DD%':>18}  {'≥15%?':>6}")
print("  " + "─" * 63)
for _, r in df.iterrows():
    flag  = '  ← candidate' if r['sma'] == CANDIDATE_SMA else ''
    meets = 'PASS' if r['post22_ann'] >= THRESH_POST2022 else 'FAIL'
    print(f"  {int(r['sma']):>4}  {r['pre22_ann']*100:>+13.1f}%  {r['post22_ann']*100:>+14.1f}%  "
          f"{r['post22_dd']*100:>+17.1f}%  {meets:>6}{flag}")

print()
print("=" * 72)
print(f"TABLE 3 — YEAR-BY-YEAR RETURNS (SMA {CANDIDATE_SMA}, PCT Trail 8%, 2018-start)")
print("=" * 72)
all_years = sorted(yr_rets.keys())
print(f"  {'Year':<6}  {'Strategy':>10}  {'B&H BTC':>10}  {'Note'}")
print("  " + "─" * 50)
for yr in all_years:
    strat_r = yr_rets.get(yr, np.nan)
    bh_r    = bh_yr.get(yr, np.nan)
    note    = ''
    if yr == 2022:
        note = '← bear year'
    elif yr == 2026:
        note = '← partial (Jan-May)'
    print(f"  {yr:<6}  {strat_r*100:>+9.1f}%  {bh_r*100:>+9.1f}%  {note}")

print()
print("=" * 72)
print(f"TABLE 4 — WALK-FORWARD VALIDATION (SMA {CANDIDATE_SMA}, PCT Trail 8%)")
print("         Expanding train from 2018-01-01; test windows exit-year")
print("=" * 72)
print(f"  {'Window':<8}  {'N Trades':>9}  {'Annual%':>9}  {'WinRate':>8}  {'DD-Trade%':>10}  {'Pass?'}")
print("  " + "─" * 56)
for w in wf_results:
    ann_s  = f"{w['annual']*100:>+8.1f}%" if not np.isnan(w['annual']) else "      —"
    win_s  = f"{w['win_rate']*100:>7.0f}%" if not np.isnan(w['win_rate']) else "     —"
    dd_s   = f"{w['dd_trade']*100:>+9.1f}%" if not np.isnan(w['dd_trade']) else "         —"
    result = 'PASS' if w.get('pass') else 'FAIL'
    print(f"  {w['window']:<8}  {w['n']:>9}  {ann_s}  {win_s}  {dd_s}  {result}")

print(f"\n  Walk-forward result: {wf_pass_count}/3 windows pass → {wf_verdict}")

print()
print("=" * 72)
print("TABLE 5 — GO/NO-GO DECISION")
print(f"         Candidate: SMA {CANDIDATE_SMA} / PCT Trail 8% / 2018-start basis")
print("=" * 72)
print(f"  {'Check':<45}  {'Result':<6}  {'Detail'}")
print("  " + "─" * 75)
for label, (passed, detail) in checks.items():
    result = 'PASS' if passed else 'FAIL'
    crit   = ' (CRITICAL)' if not passed and ('Post-2022' in label or 'Stability' in label) else ''
    print(f"  {label:<45}  {result:<6}  {detail}{crit}")

print()
print(f"  ═══════════════════════════════════════════════════")
print(f"  OVERALL DECISION:  {decision}")
print(f"  Basis:             {decision_note}")
print(f"  ═══════════════════════════════════════════════════")

# ─────────────────────────────────────────────────────────────────────────────
# SAVE CSV
# ─────────────────────────────────────────────────────────────────────────────

out_dir = '/Users/Greg/Documents/Python_Local_Folder/Python_Quant_Researcher/Week_7_Notebooks/results'
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'btc_sma_stage_b_results.csv')

lines = []
lines.append('BTC SMA PCT Trail 8% — Stage B Results')
lines.append(f'Generated: {pd.Timestamp.now().date()}')
lines.append(f'Candidate: SMA {CANDIDATE_SMA} / PCT Trail 8%')
lines.append(f'Primary data: 2018-start  Secondary reference: 2017-start')
lines.append(f'Decision: {decision} ({decision_note})')
lines.append('')

lines.append('SECTION: SMA SWEEP (primary 2018-start)')
lines.append('sma,n,annual_pct,sortino,calmar,dd_trade_pct,dd_mtm_pct,win_rate_pct,composite,passes_comp,ann_2017start_pct,dd_mtm_2017start_pct')
for _, r in df.iterrows():
    ann17_s = f"{r['ann17']*100:.1f}" if not np.isnan(r['ann17']) else 'nan'
    dd17_s  = f"{r['dd_mtm17']*100:.1f}" if not np.isnan(r['dd_mtm17']) else 'nan'
    lines.append(
        f"{int(r['sma'])},{int(r['n18'])},{r['ann18']*100:.1f},{r['sortino18']:.3f},"
        f"{r['calmar18']:.3f},{r['dd_trade18']*100:.1f},{r['dd_mtm18']*100:.1f},"
        f"{r['win18']*100:.0f},{r['comp']:.3f},{r['passes_comp']},"
        f"{ann17_s},{dd17_s}"
    )
lines.append(f'stability_passing,{n_pass} of {n_total} ({pct_pass:.0%})')
lines.append(f'stability_classification,{stab_class}')
lines.append(f'cliff_edge_check,{cliff_check}')
lines.append('')

lines.append('SECTION: HALF-SPLIT PRE/POST-2022')
lines.append('sma,pre2022_annual_pct,post2022_annual_pct,post2022_dd_mtm_pct,meets_15pct_threshold')
for _, r in df.iterrows():
    meets = r['post22_ann'] >= THRESH_POST2022
    lines.append(
        f"{int(r['sma'])},{r['pre22_ann']*100:.1f},{r['post22_ann']*100:.1f},"
        f"{r['post22_dd']*100:.1f},{meets}"
    )
lines.append('')

lines.append(f'SECTION: YEAR-BY-YEAR (SMA {CANDIDATE_SMA})')
lines.append('year,strategy_pct,bh_pct')
for yr in all_years:
    lines.append(f"{yr},{yr_rets.get(yr,np.nan)*100:.1f},{bh_yr.get(yr,np.nan)*100:.1f}")
lines.append('')

lines.append('SECTION: WALK-FORWARD')
lines.append('window,n_trades,annual_pct,win_rate_pct,dd_trade_pct,pass')
for w in wf_results:
    ann_v  = f"{w['annual']*100:.1f}"  if not np.isnan(w['annual'])   else 'nan'
    win_v  = f"{w['win_rate']*100:.0f}" if not np.isnan(w['win_rate']) else 'nan'
    dd_v   = f"{w['dd_trade']*100:.1f}" if not np.isnan(w['dd_trade']) else 'nan'
    lines.append(f"{w['window']},{w['n']},{ann_v},{win_v},{dd_v},{w.get('pass',False)}")
lines.append(f'walk_forward_verdict,{wf_verdict} ({wf_pass_count}/3)')
lines.append('')

lines.append('SECTION: GO/NO-GO DECISION')
lines.append('check,result,detail')
for label, (passed, detail) in checks.items():
    r_str = 'PASS' if passed else 'FAIL'
    lines.append(f'"{label}",{r_str},"{detail}"')
lines.append(f'overall_decision,{decision}')
lines.append(f'decision_note,"{decision_note}"')
lines.append(f'stage_b_completed,{pd.Timestamp.now().date()}')

with open(out_path, 'w') as f:
    f.write('\n'.join(lines) + '\n')

print()
print(f"Results saved → {out_path}")
print()
print("=" * 72)
print("STAGE B COMPLETE")
print("=" * 72)
