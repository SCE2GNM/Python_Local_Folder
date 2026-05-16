#!/usr/bin/env python3
"""
BTC SMA Crossover — Stage A: Stop Type Grid Search
SMA period: 120 (anchor from prior validation; Stage B sweeps 100-150)

Grid: 18 configs + 1 no-stop baseline
  Fixed stops:     3%, 5%, 8%, 10%
  Pct trailing:    5%, 8%, 10%, 20%, 25%, 30%, 35%
  ATR trailing:    ATR9/2.0x, ATR9/2.5x, ATR14/2.0x
  SMA-relative:    3%, 5%, 8% below SMA

Ranking: annual return descending. No composite score.
Qualification filter: MtM MaxDD >= -50% (worse -> disqualified, separate table).
Baseline (no-stop): reference only — not deployable regardless of rank.

Methodology (METHODOLOGY_STANDARDS.md):
  - Stop checked against daily LOW before signal-based exit each bar
  - Daily mark-to-market equity curve for Sortino and MtM MaxDD
  - Per-trade compounding for annual return and Calmar
  - 0.15% round-trip costs per trade

Outputs:
  data/btc_sma_stage_a_results.csv
  results/btc_sma_stage_a_ranked.png
  results/btc_sma_stage_a_equity.png
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import yfinance as yf

warnings.filterwarnings('ignore')

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
SMA_PERIOD    = 120
COSTS         = 0.0015      # 0.15% round-trip
MtM_DQ        = -0.50       # MtM MaxDD worse than this -> disqualified
MIN_TRADES    = 5
DATA_START    = '2017-01-01'
TOP_N_YOY     = 10

FIXED_STOPS = [0.03, 0.05, 0.08, 0.10]
PCT_TRAILS  = [0.05, 0.08, 0.10, 0.20, 0.25, 0.30, 0.35]
ATR_CONFIGS = [(9, 2.0), (9, 2.5), (14, 2.0)]   # (period, multiplier)
SMA_BUFFERS = [0.03, 0.05, 0.08]

TYPE_COLORS = {
    'none':      '#9E9E9E',
    'fixed':     '#F44336',
    'trail_pct': '#2196F3',
    'trail_atr': '#FF9800',
    'sma_rel':   '#4CAF50',
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
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

    eq_pt  = np.cumprod(1 + rets)
    pk_pt  = np.maximum.accumulate(eq_pt)
    dd_pt  = ((eq_pt - pk_pt) / pk_pt).min()
    ann    = (eq_pt[-1]) ** (1/years) - 1
    calmar = ann / abs(dd_pt) if dd_pt != 0 else 0.0

    equity = build_equity_curve(trades_df, close_series)
    dr     = np.diff(equity) / equity[:-1]
    down   = dr[dr < 0]
    sortino = (dr.mean() / down.std() * np.sqrt(365)
               if len(down) > 0 and down.std() > 0 else 0.0)
    pk_eq  = np.maximum.accumulate(equity)
    dd_mtm = ((equity - pk_eq) / pk_eq).min()

    gl = abs(losers.sum()) if len(losers) > 0 else 1e-9
    pf = winners.sum() / gl if len(winners) > 0 else 0.0

    return {
        'n_trades':      len(trades_df),
        'win_rate':      (rets > 0).mean(),
        'avg_win':       winners.mean() if len(winners) > 0 else 0.0,
        'avg_loss':      losers.mean()  if len(losers)  > 0 else 0.0,
        'profit_factor': pf,
        'annual_return': ann,
        'max_dd_trade':  dd_pt,
        'max_dd_mtm':    dd_mtm,
        'calmar':        calmar,
        'sortino':       sortino,
        'stop_exit_pct': (trades_df['exit_reason'] != 'SMA_EXIT').sum() / len(trades_df),
    }


def year_returns(equity, dates):
    result = {}
    for yr in sorted(set(d.year for d in dates)):
        idx = [i for i, d in enumerate(dates) if d.year == yr]
        if not idx:
            continue
        result[yr] = equity[idx[-1]] / equity[idx[0]] - 1
    return result


# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def run_sma_no_stop(closes, lows, sma_vals, dates):
    """Pure SMA crossover. No stop. BASELINE — not deployable."""
    pos = 0; ep = 0.0; entry_date = None
    trades = []
    for i in range(1, len(closes)):
        cl, sma = closes[i], sma_vals[i]
        if np.isnan(sma):
            continue
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
    """SMA crossover + fixed stop anchored at entry price."""
    pos = 0; ep = sp = 0.0; entry_date = None
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sma = lows[i], closes[i], sma_vals[i]
        if np.isnan(sma):
            continue
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
    """SMA crossover + percentage trailing stop from peak close."""
    pos = 0; ep = pk = sp = 0.0; entry_date = None
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sma = lows[i], closes[i], sma_vals[i]
        if np.isnan(sma):
            continue
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
    """SMA crossover + ATR trailing stop (ratcheted — never moves down)."""
    pos = 0; ep = pk = sp = 0.0; entry_date = None
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sma, atr = lows[i], closes[i], sma_vals[i], atr_vals[i]
        if np.isnan(sma) or np.isnan(atr):
            continue
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
                if cl > pk:
                    pk = cl
                sp = max(sp, pk - atr_mult*atr)
        elif cl > sma:
            ep = pk = cl; sp = cl - atr_mult*atr; pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)


def run_sma_relative_stop(closes, lows, sma_vals, dates, buffer_pct):
    """
    SMA crossover + stop set buffer_pct below the current SMA.
    No separate SMA-level exit — the relative stop IS the exit.
    Stop moves with the SMA including downward (no ratchet).
    """
    pos = 0; ep = 0.0; entry_date = None
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sma = lows[i], closes[i], sma_vals[i]
        if np.isnan(sma):
            continue
        stop_level = sma * (1 - buffer_pct)
        if pos == 1:
            if lo <= stop_level:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': stop_level,
                                'return': (stop_level-ep)/ep,
                                'exit_reason': 'SMA_REL_STOP'})
                pos = 0; ep = 0.0; entry_date = None
            elif cl <= stop_level:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': cl,
                                'return': (cl-ep)/ep, 'exit_reason': 'SMA_REL_STOP'})
                pos = 0; ep = 0.0; entry_date = None
        elif cl > sma:
            ep = cl; pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)


# ─────────────────────────────────────────────────────────────────────────────
# 1. FETCH DATA
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*72)
print("BTC SMA CROSSOVER — STAGE A: STOP TYPE GRID SEARCH")
print("="*72)
print(f"\nFetching BTC-USD daily data ({DATA_START} → present)...")

raw = yf.download('BTC-USD', start=DATA_START, auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
df = raw[['High','Low','Close']].copy().dropna()

closes    = df['Close'].values.astype(float)
lows      = df['Low'].values.astype(float)
highs     = df['High'].values.astype(float)
dates     = df.index
N         = len(df)
YEARS     = (dates[-1] - dates[0]).days / 365.25
ALL_YEARS = sorted(set(d.year for d in dates))

print(f"  {dates[0].date()} → {dates[-1].date()}  ({YEARS:.2f} yrs, {N} bars)")
print(f"  First close: ${closes[0]:,.0f}   Last: ${closes[-1]:,.0f}")

sma_vals = pd.Series(closes).rolling(SMA_PERIOD).mean().values
first_valid = int(np.where(~np.isnan(sma_vals))[0][0])
print(f"  SMA-{SMA_PERIOD} warmup complete from: {dates[first_valid].date()}")

atr_cache = {}
for p in {ap for ap, _ in ATR_CONFIGS}:
    atr_cache[p] = compute_atr(highs, lows, closes, p)

bh_eq = closes / closes[0]
bh_yr = year_returns(bh_eq, dates)


# ─────────────────────────────────────────────────────────────────────────────
# 2. RUN GRID
# ─────────────────────────────────────────────────────────────────────────────

n_total = 1 + len(FIXED_STOPS) + len(PCT_TRAILS) + len(ATR_CONFIGS) + len(SMA_BUFFERS)
print(f"\nRunning {n_total} configurations (SMA-{SMA_PERIOD})...")

raw_configs = []  # (label, stop_type, param_a, param_b, is_baseline, trades_df)

t = run_sma_no_stop(closes, lows, sma_vals, dates)
raw_configs.append(('No Stop (SMA only)', 'none', None, None, True, t))
print(f"  [BASELINE] No Stop:      {len(t):3d} trades")

for sp in FIXED_STOPS:
    t = run_sma_fixed_stop(closes, lows, sma_vals, dates, sp)
    raw_configs.append((f'Fixed {sp*100:.0f}%', 'fixed', sp, None, False, t))
    print(f"  Fixed {sp*100:.0f}%:           {len(t):3d} trades")

for tp in PCT_TRAILS:
    t = run_sma_pct_trail(closes, lows, sma_vals, dates, tp)
    raw_configs.append((f'PCT Trail {tp*100:.0f}%', 'trail_pct', tp, None, False, t))
    print(f"  PCT Trail {tp*100:.0f}%:       {len(t):3d} trades")

for (ap, am) in ATR_CONFIGS:
    t = run_sma_atr_trail(closes, lows, sma_vals, atr_cache[ap], dates, am)
    raw_configs.append((f'ATR{ap} {am}x', 'trail_atr', ap, am, False, t))
    print(f"  ATR{ap}/{am}x:          {len(t):3d} trades")

for bp in SMA_BUFFERS:
    t = run_sma_relative_stop(closes, lows, sma_vals, dates, bp)
    raw_configs.append((f'SMA-Rel {bp*100:.0f}%', 'sma_rel', bp, None, False, t))
    print(f"  SMA-Rel {bp*100:.0f}%:         {len(t):3d} trades")


# ─────────────────────────────────────────────────────────────────────────────
# 3. COMPUTE METRICS
# ─────────────────────────────────────────────────────────────────────────────

print("\nComputing metrics...")
results = []
for (label, stype, pa, pb, is_bl, t_df) in raw_configs:
    if len(t_df) == 0:
        continue
    m = calc_metrics(t_df, df['Close'], YEARS)
    if m is None:
        continue
    equity = build_equity_curve(t_df, df['Close'])
    results.append({
        'label': label, 'stop_type': stype,
        'param_a': pa, 'param_b': pb, 'is_baseline': is_bl,
        'equity': equity,
        'yr_returns': year_returns(equity, dates),
        **m,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 4. FILTER + RANK
# ─────────────────────────────────────────────────────────────────────────────

baseline_rows = [r for r in results if r['is_baseline']]
active        = [r for r in results if not r['is_baseline']]
qualified     = sorted([r for r in active if r['max_dd_mtm'] >= MtM_DQ],
                       key=lambda x: x['annual_return'], reverse=True)
disqualified  = [r for r in active if r['max_dd_mtm'] < MtM_DQ]


# ─────────────────────────────────────────────────────────────────────────────
# 5. PRINT RANKED TABLE
# ─────────────────────────────────────────────────────────────────────────────

HDR = (f"  {'#':>3}  {'Label':<22} {'Type':<11} {'N':>4}  "
       f"{'Annual%':>8}  {'MtMMaxDD%':>10}  {'TrMaxDD%':>9}  "
       f"{'Sortino':>8}  {'Calmar':>7}  {'WR%':>5}  {'StpExit%':>9}")
SEP = "  " + "─"*100

def fmt_row(rank_str, r, suffix=''):
    return (f"  {rank_str:>3}  {r['label']:<22} {r['stop_type']:<11} "
            f"{r['n_trades']:>4}  "
            f"{r['annual_return']*100:>+7.1f}%  {r['max_dd_mtm']*100:>9.1f}%  "
            f"{r['max_dd_trade']*100:>8.1f}%  "
            f"{r['sortino']:>8.3f}  {r['calmar']:>7.3f}  "
            f"{r['win_rate']*100:>4.0f}%  {r['stop_exit_pct']*100:>8.0f}%"
            f"{suffix}")

print("\n" + "="*72)
print(f"STAGE A — RANKED RESULTS  (MtM MaxDD ≥ −50%,  ranked by Annual Return%)")
print("="*72)
print(HDR)
print(SEP)
for rank, r in enumerate(qualified, 1):
    print(fmt_row(str(rank), r))

print(f"\n  {'─'*55}")
print(f"  [REFERENCE — NOT DEPLOYABLE — no stop means no controlled downside]")
for r in baseline_rows:
    print(fmt_row('REF', r))

if disqualified:
    print(f"\n  {'─'*55}")
    print(f"  [DISQUALIFIED — MtM MaxDD worse than −50%]")
    for r in sorted(disqualified, key=lambda x: x['annual_return'], reverse=True):
        print(fmt_row('DQ', r))

print(f"\n  FOOTNOTES:")
print(f"  [1] SMA-Rel StpExit% = 100% by construction: the relative stop IS")
print(f"      the exit signal. Not comparable to stop_exit_pct for other types.")
print(f"  [2] SMA-Rel stop moves down as SMA declines — no ratchet. Delays")
print(f"      (does not prevent) exit in prolonged downtrends vs pure SMA exit.")


# ─────────────────────────────────────────────────────────────────────────────
# 6. YEAR-BY-YEAR TABLE  (top N qualified + B&H)
# ─────────────────────────────────────────────────────────────────────────────

top_n = qualified[:TOP_N_YOY]
CW    = 8   # column width

print(f"\n{'='*72}")
print(f"YEAR-BY-YEAR RETURNS  (top {len(top_n)} qualified + B&H BTC)")
print(f"  ⚠ = 2021 calendar-year return >100% (high concentration risk — see BS002)")
print(f"{'='*72}")

yr_hdr = f"  {'Strategy':<26}" + "".join(f"{yr:>{CW}}" for yr in ALL_YEARS)
print(yr_hdr)
print("  " + "─"*(26 + CW*len(ALL_YEARS)))

def fmt_yy(v):
    if abs(v) < 0.0005:
        return f"{'—':>{CW}}"
    return f"{v*100:>+7.1f}%"

for rank, r in enumerate(top_n, 1):
    yr_d  = r['yr_returns']
    flag  = ' ⚠' if yr_d.get(2021, 0) > 1.0 else ''
    label = f"{rank}. {r['label']}"
    row   = f"  {label:<26}" + "".join(fmt_yy(yr_d.get(yr, 0)) for yr in ALL_YEARS) + flag
    print(row)

bh_row = f"  {'B&H BTC':<26}" + "".join(fmt_yy(bh_yr.get(yr, 0)) for yr in ALL_YEARS)
print(bh_row)


# ─────────────────────────────────────────────────────────────────────────────
# 7. GRID BOUNDARY CHECKS
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n{'='*72}")
print("GRID BOUNDARY CHECKS")
print(f"{'='*72}")

def boundary_check(label, best_val, all_vals):
    lo, hi = min(all_vals), max(all_vals)
    if abs(best_val - hi) < 1e-9:
        return f"⚠ AT MAX ({best_val*100:.0f}%) — consider extending grid"
    if abs(best_val - lo) < 1e-9:
        return f"⚠ AT MIN ({best_val*100:.0f}%) — consider extending grid"
    return f"✓ interior ({best_val*100:.0f}%)"

q_trail = [r for r in qualified if r['stop_type'] == 'trail_pct']
if q_trail:
    best_tp = q_trail[0]['param_a']
    print(f"  PCT Trail:   {boundary_check('PCT', best_tp, PCT_TRAILS)}"
          f"  (range {min(PCT_TRAILS)*100:.0f}%–{max(PCT_TRAILS)*100:.0f}%)")

q_fixed = [r for r in qualified if r['stop_type'] == 'fixed']
if q_fixed:
    best_fp = q_fixed[0]['param_a']
    print(f"  Fixed Stop:  {boundary_check('Fixed', best_fp, FIXED_STOPS)}"
          f"  (range {min(FIXED_STOPS)*100:.0f}%–{max(FIXED_STOPS)*100:.0f}%)")

q_atr = [r for r in qualified if r['stop_type'] == 'trail_atr']
if q_atr:
    best_am = q_atr[0]['param_b']
    all_mults = [m for _, m in ATR_CONFIGS]
    if abs(best_am - max(all_mults)) < 1e-9:
        atrf = f"⚠ AT MAX mult ({best_am}x)"
    elif abs(best_am - min(all_mults)) < 1e-9:
        atrf = f"⚠ AT MIN mult ({best_am}x)"
    else:
        atrf = f"✓ interior mult ({best_am}x)"
    print(f"  ATR mult:    {atrf}  (range {min(all_mults)}x–{max(all_mults)}x)")

q_rel = [r for r in qualified if r['stop_type'] == 'sma_rel']
if q_rel:
    best_bp = q_rel[0]['param_a']
    print(f"  SMA Buffer:  {boundary_check('SMA-Rel', best_bp, SMA_BUFFERS)}"
          f"  (range {min(SMA_BUFFERS)*100:.0f}%–{max(SMA_BUFFERS)*100:.0f}%)")


# ─────────────────────────────────────────────────────────────────────────────
# 8. BEST CANDIDATE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

if qualified:
    best = qualified[0]
    print(f"\n{'='*72}")
    print(f"BEST CANDIDATE  (highest annual return, MtM MaxDD ≥ −50%)")
    print(f"{'='*72}")
    print(f"  Config:         {best['label']}  (SMA-{SMA_PERIOD})")
    print(f"  Annual return:  {best['annual_return']*100:.1f}%")
    print(f"  MtM MaxDD:      {best['max_dd_mtm']*100:.1f}%")
    print(f"  Per-trade MaxDD:{best['max_dd_trade']*100:.1f}%")
    print(f"  Sortino:        {best['sortino']:.3f}")
    print(f"  Calmar:         {best['calmar']:.3f}")
    print(f"  N trades:       {best['n_trades']}")
    print(f"  Win rate:       {best['win_rate']*100:.0f}%")
    print(f"  Stop exit %:    {best['stop_exit_pct']*100:.0f}%")
    print(f"\n  → Advances to Stage B: SMA stability sweep 100–150")


# ─────────────────────────────────────────────────────────────────────────────
# 9. CHARTS
# ─────────────────────────────────────────────────────────────────────────────

print("\nGenerating charts...")

# ── Chart 1: Ranked horizontal bar chart ─────────────────────────────────────
n_q  = len(qualified)
n_dq = len(disqualified)
n_bl = len(baseline_rows)
n_rows_chart = n_q + n_dq + n_bl + (1 if n_dq > 0 else 0)  # +1 for divider gap

fig_h = max(7, n_rows_chart * 0.42)
fig1, ax1 = plt.subplots(figsize=(12, fig_h))
fig1.patch.set_facecolor('#0e1117')
ax1.set_facecolor('#0e1117')
for sp in ax1.spines.values():
    sp.set_edgecolor('#444')

# Build ordered rows bottom-to-top: DQ (bottom), divider gap, qualified, baseline (top)
plot_rows = []
for r in reversed(sorted(disqualified, key=lambda x: x['annual_return'])):
    plot_rows.append((r, 'dq'))
for r in reversed(qualified):
    plot_rows.append((r, 'q'))
for r in baseline_rows:
    plot_rows.append((r, 'bl'))

y_pos    = list(range(len(plot_rows)))
y_labels = []
y_vals   = []
y_colors = []
y_alphas = []

for i, (r, tier) in enumerate(plot_rows):
    suffix = ' [REF]' if tier == 'bl' else ''
    y_labels.append(r['label'] + suffix)
    y_vals.append(r['annual_return'] * 100)
    y_colors.append(TYPE_COLORS.get(r['stop_type'], '#9E9E9E'))
    y_alphas.append(0.30 if tier == 'dq' else 0.55 if tier == 'bl' else 0.90)

for yp, yv, yc, ya, (r, tier) in zip(y_pos, y_vals, y_colors, y_alphas, plot_rows):
    ax1.barh(yp, yv, color=yc, alpha=ya, height=0.62)
    ha = 'left' if yv >= 0 else 'right'
    offset = 0.8 if yv >= 0 else -0.8
    ax1.text(yv + offset, yp, f'{yv:+.1f}%', va='center', ha=ha,
             color='white', fontsize=7.5, alpha=ya + 0.1)

# DQ divider
if n_dq > 0:
    dq_line = n_dq - 0.5
    ax1.axhline(dq_line, color='#FF5722', lw=1.2, ls='--', alpha=0.7)
    x_max = max(y_vals) * 1.15 if max(y_vals) > 0 else 20
    ax1.text(x_max * 0.02, dq_line + 0.25,
             'DISQUALIFIED  (MtM MaxDD < −50%)',
             color='#FF5722', fontsize=7.5, alpha=0.8, va='bottom')

ax1.set_yticks(y_pos)
ax1.set_yticklabels(y_labels, color='white', fontsize=8.5)
ax1.axvline(0, color='#888', lw=0.8)
ax1.set_xlabel('Annual Return %', color='white', fontsize=10)
ax1.tick_params(colors='white')

legend_els = [
    Patch(color=TYPE_COLORS['trail_pct'], label='PCT Trailing'),
    Patch(color=TYPE_COLORS['fixed'],     label='Fixed Stop'),
    Patch(color=TYPE_COLORS['trail_atr'], label='ATR Trailing'),
    Patch(color=TYPE_COLORS['sma_rel'],   label='SMA-Relative'),
    Patch(color=TYPE_COLORS['none'], alpha=0.5, label='No Stop [REF]'),
]
ax1.legend(handles=legend_els, loc='lower right', fontsize=8,
           facecolor='#1a1a2e', labelcolor='white', framealpha=0.85)
ax1.set_title(f'BTC SMA-{SMA_PERIOD} Stage A — Stop Grid  '
              f'(ranked by Annual Return%,  MtM MaxDD ≥ −50% to qualify)',
              color='white', fontsize=10, pad=10)
plt.tight_layout()
path1 = os.path.join(RESULTS_DIR, 'btc_sma_stage_a_ranked.png')
plt.savefig(path1, dpi=130, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"  Saved → results/btc_sma_stage_a_ranked.png")


# ── Chart 2: Equity curves — top 3 qualified + baseline + B&H ────────────────
fig2, (ax2a, ax2b) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
fig2.patch.set_facecolor('#0e1117')
for ax in [ax2a, ax2b]:
    ax.set_facecolor('#0e1117')
    for sp in ax.spines.values():
        sp.set_edgecolor('#444')

date_strs   = [d.strftime('%Y-%m-%d') for d in dates]
top3_colors = ['#2196F3', '#4CAF50', '#FF9800']

for i, r in enumerate(qualified[:3]):
    lbl = f"#{i+1} {r['label']}  ({r['annual_return']*100:+.1f}%/yr | Sortino {r['sortino']:.3f})"
    ax2a.plot(date_strs, r['equity'], color=top3_colors[i], lw=1.8, label=lbl)
    pk = np.maximum.accumulate(r['equity'])
    ax2b.plot(date_strs, (r['equity'] - pk)/pk*100, color=top3_colors[i], lw=1.4)

if baseline_rows:
    br = baseline_rows[0]
    ax2a.plot(date_strs, br['equity'], color='#9E9E9E', lw=1.2, ls='--', alpha=0.65,
              label=f"Baseline — no stop  ({br['annual_return']*100:+.1f}%/yr)")
    pk = np.maximum.accumulate(br['equity'])
    ax2b.plot(date_strs, (br['equity'] - pk)/pk*100, color='#9E9E9E', lw=1.0, ls='--', alpha=0.5)

ax2a.plot(date_strs, bh_eq, color='#607D8B', lw=1.0, ls=':', alpha=0.6, label='B&H BTC')

ax2a.set_yscale('log')
ax2a.set_ylabel('Equity (log, $1 start)', color='white', fontsize=10)
ax2a.tick_params(colors='white')
ax2a.legend(fontsize=8, facecolor='#1a1a2e', labelcolor='white', loc='upper left')
ax2a.set_title(f'BTC SMA-{SMA_PERIOD} Stage A — Top 3 Equity Curves vs Baseline & B&H',
               color='white', fontsize=11, pad=8)

ax2b.axhline(0, color='#888', lw=0.6)
ax2b.set_ylabel('Drawdown %', color='white', fontsize=10)
ax2b.set_xlabel('Date', color='white', fontsize=10)
ax2b.tick_params(colors='white')

plt.tight_layout()
path2 = os.path.join(RESULTS_DIR, 'btc_sma_stage_a_equity.png')
plt.savefig(path2, dpi=130, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"  Saved → results/btc_sma_stage_a_equity.png")


# ─────────────────────────────────────────────────────────────────────────────
# 10. SAVE CSV
# ─────────────────────────────────────────────────────────────────────────────

csv_rows = []
for rank, r in enumerate(qualified, 1):
    csv_rows.append({'rank': rank, 'qualified': 'Y',
                     **{k: v for k, v in r.items() if k not in ('equity','yr_returns')}})
for r in baseline_rows:
    csv_rows.append({'rank': 'REF', 'qualified': 'REF',
                     **{k: v for k, v in r.items() if k not in ('equity','yr_returns')}})
for r in sorted(disqualified, key=lambda x: x['annual_return'], reverse=True):
    csv_rows.append({'rank': 'DQ', 'qualified': 'N',
                     **{k: v for k, v in r.items() if k not in ('equity','yr_returns')}})

cols = ['rank', 'qualified', 'label', 'stop_type', 'param_a', 'param_b',
        'n_trades', 'annual_return', 'max_dd_trade', 'max_dd_mtm', 'calmar',
        'sortino', 'win_rate', 'avg_win', 'avg_loss', 'profit_factor',
        'stop_exit_pct', 'is_baseline']
pd.DataFrame(csv_rows)[cols].to_csv(
    os.path.join(DATA_DIR, 'btc_sma_stage_a_results.csv'), index=False)
print(f"  Saved → data/btc_sma_stage_a_results.csv")


print(f"\n{'='*72}")
print(f"STAGE A COMPLETE")
print(f"  Best candidate: {qualified[0]['label'] if qualified else 'none'}")
print(f"  Qualified configs: {len(qualified)} / {len(active)}")
print(f"  Disqualified:      {len(disqualified)} / {len(active)}")
if qualified:
    print(f"  → Stage B: sweep SMA 100–150 with "
          f"stop type '{qualified[0]['stop_type']}' "
          f"param {qualified[0]['param_a']}")
print(f"{'='*72}\n")
