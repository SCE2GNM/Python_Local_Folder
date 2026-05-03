# BTC ADX 19/14 Full Validation — SI001
# Week 6 / Week 7 Priority 2
#
# Validates the BTC ADX 19/14 starting configuration with trailing stop
# optimisation, stability analysis, walk-forward, and ETH cross-asset check.
#
# Week 5 uncorrected baseline: ADX 19/14 fixed 3% stop → Calmar 1.121
# Known issues: per-trade Sortino (inflated), no round-trip costs applied.
# This script corrects both.
#
# Stages:
#   A — Trailing stop grid search (PCT and ATR) with correct methodology
#   B — Stability analysis on best candidate
#   C — Walk-forward validation (expanding + rolling, 3 windows)
#   D — ETH-USD cross-asset check
#   Final — GO / NO-GO summary, comparison vs BTC SMA 120/25%

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from ta.trend import ADXIndicator
import os
from itertools import product

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADX_THRESHOLD  = 19
ADX_PERIOD     = 14
COST_PER_TRADE = 0.00075 * 2    # 0.15% round-trip
MIN_TRADES     = 10
LOW_N          = 3              # flag windows with < 3 trades
COMP_THRESHOLD = 0.70           # composite ≥ this = "passes" for stability
FIXED_STOP_SWEEP = [0.02, 0.025, 0.03, 0.035, 0.04, 0.045,
                    0.05, 0.055, 0.06, 0.07, 0.08]

# PCT trail sweep: 5% to 20% step 2.5%
PCT_TRAILS = [0.05, 0.075, 0.10, 0.125, 0.15, 0.175, 0.20]

# ATR grid
ATR_PERIODS = list(range(7, 22, 2))       # [7,9,11,13,15,17,19,21]
ATR_MULTS   = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]

RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'results')
DATA_DIR    = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)

# BTC SMA comparison anchor (from Stage 2e)
BTC_SMA_ANN   = 48.9
BTC_SMA_MAXDD_TRADE = -17.8
BTC_SMA_MAXDD_MTM   = -30.5
BTC_SMA_SORTINO     = 1.246
BTC_SMA_CALMAR      = 2.752
BTC_SMA_TRADES      = 34


# ---------------------------------------------------------------------------
# Helper: ATR
# ---------------------------------------------------------------------------

def compute_atr(high, low, close, period):
    prev = close.shift(1)
    tr   = pd.concat([high - low,
                      (high - prev).abs(),
                      (low  - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean().values


# ---------------------------------------------------------------------------
# Backtests — bar-by-bar, stop checked against daily LOW
# ---------------------------------------------------------------------------

def run_pct_trail(closes, lows, signals, dates, trail_pct):
    pos = ep = pk = sp = 0.0
    entry_date = None
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sig = lows[i], closes[i], signals[i]
        if pos == 1:
            if lo <= sp:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price':  sp,
                                'return': (sp - ep) / ep, 'exit_reason': 'TRAIL_STOP'})
                pos = ep = pk = sp = 0.0
                entry_date = None
            elif not sig:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price':  cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'ADX_EXIT'})
                pos = ep = pk = sp = 0.0
                entry_date = None
            else:
                if cl > pk:
                    pk = cl
                    sp = pk * (1 - trail_pct)
        elif pos == 0 and sig:
            ep = pk = cl
            sp = cl * (1 - trail_pct)
            pos = 1
            entry_date = dates[i]
    return trades


def run_atr_trail(closes, lows, signals, atr_vals, dates, mult):
    pos = ep = pk = sp = 0.0
    entry_date = None
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sig, atr = lows[i], closes[i], signals[i], atr_vals[i]
        if pos == 1:
            if lo <= sp:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price':  sp,
                                'return': (sp - ep) / ep, 'exit_reason': 'TRAIL_STOP'})
                pos = ep = pk = sp = 0.0
                entry_date = None
            elif not sig:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price':  cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'ADX_EXIT'})
                pos = ep = pk = sp = 0.0
                entry_date = None
            else:
                if cl > pk:
                    pk = cl
                candidate = pk - mult * atr
                sp = max(sp, candidate)
        elif pos == 0 and sig:
            ep = pk = cl
            sp = cl - mult * atr
            pos = 1
            entry_date = dates[i]
    return trades


def run_fixed_stop(closes, lows, signals, dates, stop_pct):
    pos = ep = sp = 0.0
    entry_date = None
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sig = lows[i], closes[i], signals[i]
        if pos == 1:
            if lo <= sp:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price':  sp,
                                'return': (sp - ep) / ep, 'exit_reason': 'FIXED_STOP'})
                pos = ep = sp = 0.0
                entry_date = None
            elif not sig:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price':  cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'ADX_EXIT'})
                pos = ep = sp = 0.0
                entry_date = None
        elif pos == 0 and sig:
            ep = cl
            sp = cl * (1 - stop_pct)
            pos = 1
            entry_date = dates[i]
    return trades


# ---------------------------------------------------------------------------
# Daily equity curve (mark-to-market)
# ---------------------------------------------------------------------------

def build_daily_equity(trades_df, close_series):
    n         = len(close_series)
    closes_a  = close_series.values
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
        equity[ei:xi + 1]  = portfolio * closes_a[ei:xi + 1] / t['entry_price']
        portfolio          *= (1 + t['return'] - COST_PER_TRADE)
        equity[xi]          = portfolio
        prev_i              = xi + 1

    equity[prev_i:] = portfolio
    return equity


# ---------------------------------------------------------------------------
# Metrics (per-trade compounding + daily equity for Sortino / MtM MaxDD)
# ---------------------------------------------------------------------------

def calc_metrics(trades, close_series, years):
    if len(trades) < MIN_TRADES:
        return None

    df_t    = pd.DataFrame(trades)
    rets    = df_t['return'].values - COST_PER_TRADE

    winners = rets[rets > 0]
    losers  = rets[rets <= 0]
    win_rate      = (rets > 0).mean()
    avg_win       = winners.mean() if len(winners) else 0.0
    avg_loss      = losers.mean()  if len(losers)  else 0.0
    gross_loss    = abs(losers.sum()) if len(losers) else 1e-9
    profit_factor = winners.sum() / gross_loss if len(winners) else 0.0

    # --- Per-trade MaxDD ---
    eq_pt    = np.cumprod(1 + rets)
    peak_pt  = np.maximum.accumulate(eq_pt)
    max_dd_trade = ((eq_pt - peak_pt) / peak_pt).min()

    total_ret    = eq_pt[-1] - 1
    annual_ret   = (1 + total_ret) ** (1 / years) - 1
    calmar       = annual_ret / abs(max_dd_trade) if max_dd_trade != 0 else 0.0

    # --- Daily equity → Sortino + daily MtM MaxDD ---
    full_eq  = build_daily_equity(df_t, close_series)
    dr       = np.diff(full_eq) / full_eq[:-1]
    downside = dr[dr < 0]
    sortino  = (dr.mean() / downside.std() * np.sqrt(365)
                if len(downside) > 0 and downside.std() > 0 else 0.0)

    eq_peak      = np.maximum.accumulate(full_eq)
    max_dd_mtm   = ((full_eq - eq_peak) / eq_peak).min()

    stop_exits = (df_t['exit_reason'] != 'ADX_EXIT').sum()

    return {
        'n_trades':       len(df_t),
        'win_rate':       win_rate,
        'avg_win':        avg_win,
        'avg_loss':       avg_loss,
        'profit_factor':  profit_factor,
        'annual_return':  annual_ret,
        'max_dd_trade':   max_dd_trade,
        'max_dd_mtm':     max_dd_mtm,
        'calmar':         calmar,
        'sortino':        sortino,
        'stop_exit_pct':  stop_exits / len(df_t),
    }


# ---------------------------------------------------------------------------
# Composite score (normalise across a DataFrame, 3 metrics)
# ---------------------------------------------------------------------------

def add_composite(df, ann_col='annual_return', sort_col='sortino',
                  mdd_col='max_dd_trade', ref_df=None):
    """Normalise annual%, Sortino, MaxDD and return equal-weight composite.
    ref_df: if provided, compute min/max from ref_df (for stability re-use)."""
    src = ref_df if ref_df is not None else df

    def mm(col, invert=False):
        lo, hi = src[col].min(), src[col].max()
        if hi == lo:
            return pd.Series(0.5, index=df.index)
        n = (df[col] - lo) / (hi - lo)
        return 1 - n if invert else n

    df['norm_ann']  = mm(ann_col)
    df['norm_sort'] = mm(sort_col)
    df['norm_mdd']  = mm(mdd_col)   # all-negative: less negative = higher = better
    df['composite'] = (df['norm_ann'] + df['norm_sort'] + df['norm_mdd']) / 3.0
    return df


def classify_stability(pct):
    if pct > 60:   return 'STABLE'
    elif pct >= 40: return 'MARGINAL'
    else:           return 'FRAGILE'


# ---------------------------------------------------------------------------
# Fetch data
# ---------------------------------------------------------------------------

print("\n" + "=" * 60)
print("BTC ADX 19/14 FULL VALIDATION — SI001")
print("=" * 60)
print("\nFetching BTC-USD daily data (2018-2026)...")

raw = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False,
                  auto_adjust=True)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df_btc = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df_btc.dropna(inplace=True)

years_btc = (df_btc.index[-1] - df_btc.index[0]).days / 365.25
print(f"BTC data: {df_btc.index[0].date()} → {df_btc.index[-1].date()} ({years_btc:.1f} yrs)")

closes_btc = df_btc['Close'].values
lows_btc   = df_btc['Low'].values
dates_btc  = df_btc.index

# Compute ADX 19/14 signals once (level signal: ADX>19 AND DI+>DI-)
adx_ind   = ADXIndicator(df_btc['High'], df_btc['Low'], df_btc['Close'],
                          window=ADX_PERIOD)
adx_vals  = adx_ind.adx().values
di_pos    = adx_ind.adx_pos().values
di_neg    = adx_ind.adx_neg().values
sig_btc   = (adx_vals >= ADX_THRESHOLD) & (di_pos > di_neg)

# Pre-compute all ATR periods needed
atr_cache = {}
for p in ATR_PERIODS:
    atr_cache[p] = compute_atr(df_btc['High'], df_btc['Low'], df_btc['Close'], p)

print(f"ADX {ADX_THRESHOLD}/{ADX_PERIOD} signals computed.")


# ===========================================================================
#  STAGE A — Trailing Stop Grid Search
# ===========================================================================

print("\n" + "=" * 60)
print("STAGE A — TRAILING STOP GRID SEARCH")
print(f"  ADX {ADX_THRESHOLD}/{ADX_PERIOD} fixed | 0.15% round-trip costs")
print(f"  PCT trail: {[f'{p*100:.1f}%' for p in PCT_TRAILS]}")
print(f"  ATR grid:  period {ATR_PERIODS}, mult {ATR_MULTS}")
print("=" * 60)

rows_a = []

# Fixed 3% stop baseline
print("\nRunning fixed 3% stop baseline...", end=' ')
t_fixed = run_fixed_stop(closes_btc, lows_btc, sig_btc, dates_btc, 0.03)
m_fixed = calc_metrics(t_fixed, df_btc['Close'], years_btc)
if m_fixed:
    rows_a.append({'stop_type': 'fixed', 'param_a': 0.03, 'param_b': None,
                   'label': 'Fixed 3%', **m_fixed})
    print(f"{m_fixed['n_trades']} trades, "
          f"Ann {m_fixed['annual_return']*100:.1f}%, "
          f"Calmar {m_fixed['calmar']:.3f}")

# PCT trail sweep
print("\nRunning PCT trail sweep...")
for tp in PCT_TRAILS:
    t = run_pct_trail(closes_btc, lows_btc, sig_btc, dates_btc, tp)
    m = calc_metrics(t, df_btc['Close'], years_btc)
    if m:
        rows_a.append({'stop_type': 'pct', 'param_a': tp, 'param_b': None,
                       'label': f'PCT {tp*100:.1f}%', **m})
    print(f"  PCT {tp*100:.1f}%: {m['n_trades'] if m else '—'} trades | "
          f"Ann {m['annual_return']*100:.1f}% | "
          f"Calmar {m['calmar']:.3f}" if m else
          f"  PCT {tp*100:.1f}%: insufficient trades")

# ATR trail grid
total_atr = len(ATR_PERIODS) * len(ATR_MULTS)
done = 0
print(f"\nRunning ATR trail grid ({total_atr} combinations)...")
for ap in ATR_PERIODS:
    for mult in ATR_MULTS:
        t = run_atr_trail(closes_btc, lows_btc, sig_btc,
                          atr_cache[ap], dates_btc, mult)
        m = calc_metrics(t, df_btc['Close'], years_btc)
        done += 1
        if m:
            rows_a.append({'stop_type': 'atr', 'param_a': ap, 'param_b': mult,
                           'label': f'ATR{ap} {mult}x', **m})
        if done % 12 == 0 or done == total_atr:
            print(f"  {done}/{total_atr} done...")

df_a = pd.DataFrame(rows_a)
df_a = add_composite(df_a)

# Sort by annual return descending
df_a_sorted = df_a.sort_values('annual_return', ascending=False).reset_index(drop=True)

# Save to CSV (convert to % for readability)
csv_df = df_a_sorted.copy()
for col in ['annual_return', 'max_dd_trade', 'max_dd_mtm']:
    csv_df[col] = (csv_df[col] * 100).round(2)
csv_df.to_csv(os.path.join(DATA_DIR, 'btc_adx_stage_a_results.csv'), index=False)
print(f"\nResults saved → data/btc_adx_stage_a_results.csv ({len(df_a)} configs)")

# --- Print tables ---
print("\n" + "-" * 80)
print("STAGE A — FIXED STOP BASELINE")
print("-" * 80)
if m_fixed:
    print(f"  {'Config':<12} {'Trades':>6} {'Annual%':>8} {'MaxDD%(trade)':>14} "
          f"{'MaxDD%(MtM)':>12} {'Sortino':>8} {'Calmar':>8}")
    print(f"  {'Fixed 3%':<12} {m_fixed['n_trades']:>6} "
          f"{m_fixed['annual_return']*100:>7.1f}% "
          f"{m_fixed['max_dd_trade']*100:>13.1f}% "
          f"{m_fixed['max_dd_mtm']*100:>11.1f}% "
          f"{m_fixed['sortino']:>8.3f} "
          f"{m_fixed['calmar']:>8.3f}")

print("\n" + "-" * 80)
print("STAGE A — PCT TRAIL RESULTS (ranked by Annual Return%)")
print("-" * 80)
print(f"  {'Config':<12} {'Trades':>6} {'Annual%':>8} {'MaxDD%(trade)':>14} "
      f"{'MaxDD%(MtM)':>12} {'Sortino':>8} {'Calmar':>8} {'Composite':>10}")
pct_rows = df_a_sorted[df_a_sorted['stop_type'] == 'pct']
for _, r in pct_rows.iterrows():
    print(f"  {r['label']:<12} {r['n_trades']:>6} "
          f"{r['annual_return']*100:>7.1f}% "
          f"{r['max_dd_trade']*100:>13.1f}% "
          f"{r['max_dd_mtm']*100:>11.1f}% "
          f"{r['sortino']:>8.3f} "
          f"{r['calmar']:>8.3f} "
          f"{r['composite']:>10.3f}")

print("\n" + "-" * 80)
print("STAGE A — ATR TRAIL TOP 15 BY ANNUAL RETURN%")
print("-" * 80)
print(f"  {'Config':<14} {'Trades':>6} {'Annual%':>8} {'MaxDD%(trade)':>14} "
      f"{'MaxDD%(MtM)':>12} {'Sortino':>8} {'Calmar':>8} {'Composite':>10}")
atr_rows = df_a_sorted[df_a_sorted['stop_type'] == 'atr'].head(15)
for _, r in atr_rows.iterrows():
    print(f"  {r['label']:<14} {r['n_trades']:>6} "
          f"{r['annual_return']*100:>7.1f}% "
          f"{r['max_dd_trade']*100:>13.1f}% "
          f"{r['max_dd_mtm']*100:>11.1f}% "
          f"{r['sortino']:>8.3f} "
          f"{r['calmar']:>8.3f} "
          f"{r['composite']:>10.3f}")

print("\n" + "-" * 80)
print("STAGE A — TOP 10 OVERALL (ALL STOP TYPES, BY ANNUAL RETURN%)")
print("-" * 80)
print(f"  {'#':<3} {'Config':<14} {'Type':<6} {'Trades':>6} {'Annual%':>8} "
      f"{'MaxDD%(trade)':>14} {'MaxDD%(MtM)':>12} {'Sortino':>8} {'Calmar':>8} {'Composite':>10}")
for rank, (_, r) in enumerate(df_a_sorted.head(10).iterrows(), 1):
    print(f"  {rank:<3} {r['label']:<14} {r['stop_type'].upper():<6} {r['n_trades']:>6} "
          f"{r['annual_return']*100:>7.1f}% "
          f"{r['max_dd_trade']*100:>13.1f}% "
          f"{r['max_dd_mtm']*100:>11.1f}% "
          f"{r['sortino']:>8.3f} "
          f"{r['calmar']:>8.3f} "
          f"{r['composite']:>10.3f}")

# Identify best candidates
best_ann   = df_a_sorted.iloc[0]
best_comp  = df_a.loc[df_a['composite'].idxmax()]
print(f"\n  Best by Annual Return%:  {best_ann['label']} "
      f"({best_ann['annual_return']*100:.1f}%)")
print(f"  Best by Composite Score: {best_comp['label']} "
      f"(composite {best_comp['composite']:.3f})")

# --- Grid boundary check ---
print("\n  GRID BOUNDARY CHECK:")
best_pct = pct_rows.iloc[0] if len(pct_rows) else None
if best_pct is not None:
    pct_vals = sorted(pct_rows['param_a'].values)
    if best_pct['param_a'] == pct_vals[-1]:
        print(f"  ⚠ PCT trail: best is at MAX boundary ({best_pct['param_a']*100:.1f}%) "
              f"— consider extending grid")
    elif best_pct['param_a'] == pct_vals[0]:
        print(f"  ⚠ PCT trail: best is at MIN boundary ({best_pct['param_a']*100:.1f}%) "
              f"— consider extending grid")
    else:
        print(f"  ✓ PCT trail: best ({best_pct['param_a']*100:.1f}%) not at grid boundary")

best_atr = df_a_sorted[df_a_sorted['stop_type'] == 'atr'].iloc[0] if \
           len(df_a_sorted[df_a_sorted['stop_type'] == 'atr']) > 0 else None
if best_atr is not None:
    if best_atr['param_a'] in [min(ATR_PERIODS), max(ATR_PERIODS)]:
        print(f"  ⚠ ATR period: best at boundary (period {best_atr['param_a']}) "
              f"— consider extending grid")
    else:
        print(f"  ✓ ATR period: best (period {best_atr['param_a']}) not at boundary")
    if best_atr['param_b'] in [min(ATR_MULTS), max(ATR_MULTS)]:
        print(f"  ⚠ ATR mult: best at boundary ({best_atr['param_b']}x) "
              f"— consider extending grid")
    else:
        print(f"  ✓ ATR mult: best ({best_atr['param_b']}x) not at boundary")


# --- Parallel coordinates — top 50 by annual return ---
top50 = df_a_sorted.head(50).copy()

fig_a, ax_a = plt.subplots(figsize=(13, 7))
ax_a.set_xlim(0, 1)
ax_a.set_ylim(0, 1)
ax_a.axis('off')
fig_a.patch.set_facecolor('#0e1117')

AXES_A = ['annual_return', 'max_dd_trade', 'sortino', 'calmar', 'n_trades']
LABELS_A = ['Annual\nReturn%', 'MaxDD%\n(Trade)', 'Sortino', 'Calmar', 'N Trades']
N_AX = len(AXES_A)
x_pos = np.linspace(0.08, 0.92, N_AX)

# Normalise each axis
norms_a = {}
for col in AXES_A:
    lo, hi = df_a[col].min(), df_a[col].max()
    norms_a[col] = (lo, hi)

def norm_val(val, lo, hi):
    if hi == lo:
        return 0.5
    return (val - lo) / (hi - lo)

cmap   = plt.cm.plasma
c_norm = Normalize(vmin=top50['composite'].min(), vmax=top50['composite'].max())

for _, row in top50.iloc[::-1].iterrows():
    ys = [norm_val(row[c], *norms_a[c]) for c in AXES_A]
    color = cmap(c_norm(row['composite']))
    lw = 2.5 if (row['label'] == best_ann['label'] or
                  row['label'] == best_comp['label']) else 0.8
    alpha = 0.95 if lw > 1 else 0.45
    ax_a.plot(x_pos, ys, color=color, lw=lw, alpha=alpha,
              transform=ax_a.transAxes)
    if row['label'] == best_ann['label']:
        ax_a.annotate(f"◀ {row['label']}  (Ann {row['annual_return']*100:.1f}%)",
                      xy=(x_pos[0], ys[0]), xycoords='axes fraction',
                      fontsize=7.5, color='#00BFFF',
                      xytext=(-4, 0), textcoords='offset points', ha='right')
    if (row['label'] == best_comp['label'] and
            best_comp['label'] != best_ann['label']):
        ax_a.annotate(f"◀ {row['label']}  (comp {row['composite']:.3f})",
                      xy=(x_pos[0], ys[0]), xycoords='axes fraction',
                      fontsize=7.5, color='#7FFF00',
                      xytext=(-4, 0), textcoords='offset points', ha='right')

# Draw axis lines (use plot with transAxes to avoid axvline transform restriction)
for i, (xp, lbl) in enumerate(zip(x_pos, LABELS_A)):
    ax_a.plot([xp, xp], [0.03, 0.97], color='#555', lw=1.2,
              transform=ax_a.transAxes, zorder=0)
    ax_a.text(xp, 1.04, lbl, ha='center', va='bottom', fontsize=9,
              color='white', transform=ax_a.transAxes)
    lo, hi = norms_a[AXES_A[i]]
    for frac, val in [(0.0, lo), (0.5, (lo + hi) / 2), (1.0, hi)]:
        ax_a.text(xp, frac, f'{val*100:.0f}%' if AXES_A[i] in
                  ['annual_return', 'max_dd_trade'] else f'{val:.2f}',
                  ha='center', va='center', fontsize=7, color='#aaa',
                  transform=ax_a.transAxes)

sm = ScalarMappable(cmap=cmap, norm=c_norm)
sm.set_array([])
cbar = fig_a.colorbar(sm, ax=ax_a, orientation='vertical',
                       fraction=0.02, pad=0.01)
cbar.set_label('Composite score', color='white', fontsize=9)
cbar.ax.yaxis.set_tick_params(color='white')
plt.setp(cbar.ax.yaxis.get_ticklabels(), color='white', fontsize=8)

fig_a.text(0.5, 0.97,
           f'BTC ADX {ADX_THRESHOLD}/{ADX_PERIOD} — Stage A: Top 50 by Annual Return%  '
           f'(PCT + ATR trailing stops, 0.15% costs)',
           ha='center', va='top', fontsize=11, color='white', fontweight='bold')
fig_a.text(0.5, 0.01,
           f'Blue = best annual return  |  Green = best composite  '
           f'|  Total configs: {len(df_a)}',
           ha='center', va='bottom', fontsize=8, color='#aaa')
fig_a.set_facecolor('#0e1117')

plt.savefig(os.path.join(RESULTS_DIR, 'btc_adx_stage_a_parcoords.png'),
            dpi=140, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"\n  Chart saved → results/btc_adx_stage_a_parcoords.png")

input("\n  ▶ Stage A complete. Review results and press Enter to continue to Stage B...")


# ===========================================================================
#  STAGE B — Stability Analysis
# ===========================================================================

print("\n" + "=" * 60)
print("STAGE B — STABILITY ANALYSIS")
print("=" * 60)

# Use best by annual return as primary candidate
CAND = best_ann
print(f"\n  Primary candidate: {CAND['label']} "
      f"(Ann {CAND['annual_return']*100:.1f}%, "
      f"Calmar {CAND['calmar']:.3f}, "
      f"Sortino {CAND['sortino']:.3f})")

CAND_TYPE = CAND['stop_type']

# --- Rebuild sweep from Stage A results ---
if CAND_TYPE == 'pct':
    sweep_df  = df_a[df_a['stop_type'] == 'pct'].copy().sort_values('param_a')
    best_val  = CAND['param_a']
elif CAND_TYPE == 'atr':
    best_ap   = CAND['param_a']
    best_mult = CAND['param_b']
    sweep_period = df_a[(df_a['stop_type'] == 'atr') &
                        (df_a['param_b'] == best_mult)].copy().sort_values('param_a')
    sweep_mult   = df_a[(df_a['stop_type'] == 'atr') &
                        (df_a['param_a'] == best_ap)].copy().sort_values('param_b')
elif CAND_TYPE == 'fixed':
    # Build fixed-stop sweep for stability
    print(f"  NOTE: Best candidate is the FIXED stop — trailing stops do not improve")
    print(f"  BTC ADX 19/14. Running fixed stop sweep ({FIXED_STOP_SWEEP}) for stability.")
    fixed_sweep_rows = []
    for sp in FIXED_STOP_SWEEP:
        t_sp = run_fixed_stop(closes_btc, lows_btc, sig_btc, dates_btc, sp)
        m_sp = calc_metrics(t_sp, df_btc['Close'], years_btc)
        if m_sp:
            fixed_sweep_rows.append({'stop_type': 'fixed', 'param_a': sp,
                                     'param_b': None, 'label': f'Fixed {sp*100:.1f}%',
                                     **m_sp})
    sweep_df = pd.DataFrame(fixed_sweep_rows)
    best_val = CAND['param_a']
    print(f"  Fixed stop sweep complete ({len(sweep_df)} values)")
else:
    sweep_df = None

# --- Composite normalisation using Stage A reference ---
def stability_composite(sweep, ref_df=df_a):
    sweep = sweep.copy()
    for col in ['annual_return', 'sortino', 'max_dd_trade']:
        lo, hi = ref_df[col].min(), ref_df[col].max()
        if hi != lo:
            sweep[f'norm_{col}'] = (sweep[col] - lo) / (hi - lo)
        else:
            sweep[f'norm_{col}'] = 0.5
    sweep['comp_stab'] = (sweep['norm_annual_return'] +
                          sweep['norm_sortino'] +
                          sweep['norm_max_dd_trade']) / 3.0
    return sweep

# --- Year-by-year profitability ---
print("\n  YEAR-BY-YEAR PROFITABILITY")
print(f"  Candidate: {CAND['label']}")
print(f"  {'Year':<6} {'Trades':>6} {'Annual%':>9} {'MaxDD%(trade)':>14} "
      f"{'MaxDD%(MtM)':>12} {'Calmar':>8} {'Note'}")
print(f"  {'-'*70}")

years_list = sorted(df_btc.index.year.unique())
if CAND_TYPE == 'pct':
    tp_cand = CAND['param_a']
    t_cand  = run_pct_trail(closes_btc, lows_btc, sig_btc, dates_btc, tp_cand)
elif CAND_TYPE == 'atr':
    ap_cand   = int(CAND['param_a'])
    mult_cand = CAND['param_b']
    t_cand    = run_atr_trail(closes_btc, lows_btc, sig_btc,
                               atr_cache[ap_cand], dates_btc, mult_cand)
else:  # fixed
    t_cand = run_fixed_stop(closes_btc, lows_btc, sig_btc, dates_btc, CAND['param_a'])

df_cand = pd.DataFrame(t_cand)
df_cand['exit_year'] = pd.to_datetime(df_cand['exit_date']).dt.year

yy_rows = []
for yr in years_list:
    yr_trades = df_cand[df_cand['exit_year'] == yr]
    if len(yr_trades) == 0:
        print(f"  {yr:<6} {'—':>6}")
        continue
    rets_yr = yr_trades['return'].values - COST_PER_TRADE
    eq_yr   = np.cumprod(1 + rets_yr)
    ann_yr  = eq_yr[-1] - 1
    pk_yr   = np.maximum.accumulate(eq_yr)
    dd_yr   = ((eq_yr - pk_yr) / pk_yr).min()

    yr_close = df_btc['Close'].loc[str(yr)]
    eq_mtm   = build_daily_equity(yr_trades, yr_close) if len(yr_close) > 0 else np.array([1.0])
    pk_mtm   = np.maximum.accumulate(eq_mtm)
    dd_mtm   = ((eq_mtm - pk_mtm) / pk_mtm).min()

    note = ''
    if len(yr_trades) < LOW_N:
        note = f'⚠ n={len(yr_trades)} (<{LOW_N}, unreliable)'
    calmar_yr = ann_yr / abs(dd_yr) if dd_yr != 0 else 0.0

    yy_rows.append({'year': yr, 'n': len(yr_trades), 'ann': ann_yr,
                    'dd_trade': dd_yr, 'dd_mtm': dd_mtm, 'calmar': calmar_yr})
    marker = '✓' if ann_yr > 0 else '✗'
    print(f"  {yr:<6} {len(yr_trades):>6} {ann_yr*100:>8.1f}% "
          f"{dd_yr*100:>13.1f}% {dd_mtm*100:>11.1f}% "
          f"{calmar_yr:>8.3f}  {marker} {note}")

positive_years = sum(1 for r in yy_rows if r['ann'] > 0)
total_years    = len(yy_rows)
print(f"\n  Positive years: {positive_years}/{total_years} "
      f"({100*positive_years/total_years:.0f}%)")

# --- Half-split ---
mid_year = years_list[len(years_list) // 2]
h1_trades = df_cand[df_cand['exit_year'] < mid_year]
h2_trades = df_cand[df_cand['exit_year'] >= mid_year]

print(f"\n  HALF-SPLIT TEST  (split at {mid_year})")
print(f"  {'Half':<20} {'Trades':>6} {'Ann%':>8} {'MaxDD%':>8} {'Calmar':>8}")
for label_h, h_df in [('2018 – '+str(mid_year-1), h1_trades),
                       (str(mid_year)+' – now',     h2_trades)]:
    if len(h_df) < 2:
        print(f"  {label_h:<20} {'—':>6}")
        continue
    rets_h = h_df['return'].values - COST_PER_TRADE
    eq_h   = np.cumprod(1 + rets_h)
    ann_h  = eq_h[-1] - 1
    pk_h   = np.maximum.accumulate(eq_h)
    dd_h   = ((eq_h - pk_h) / pk_h).min()
    cal_h  = ann_h / abs(dd_h) if dd_h != 0 else 0.0
    n_yrs  = len(h_df['exit_year'].unique())
    ann_pa = (1 + ann_h) ** (1 / max(n_yrs, 1)) - 1
    print(f"  {label_h:<20} {len(h_df):>6} {ann_pa*100:>7.1f}% "
          f"{dd_h*100:>7.1f}% {cal_h:>8.3f}")

# --- Stability sweeps ---
print(f"\n  PARAMETER STABILITY SWEEPS  (threshold: composite ≥ {COMP_THRESHOLD})")
stab_overall = 0.0  # will be set below

if CAND_TYPE in ('pct', 'fixed'):
    sw = stability_composite(sweep_df)
    passing = (sw['comp_stab'] >= COMP_THRESHOLD).sum()
    total_sw = len(sw)
    pct_stable = passing / total_sw * 100
    stab_overall = pct_stable
    param_name = 'Trail%' if CAND_TYPE == 'pct' else 'Stop%'
    sweep_name  = 'PCT trail' if CAND_TYPE == 'pct' else 'Fixed stop'
    print(f"\n  {sweep_name} sweep ({total_sw} values): "
          f"{passing}/{total_sw} ≥ {COMP_THRESHOLD} → {pct_stable:.1f}% "
          f"→ {classify_stability(pct_stable)}")
    print(f"\n  {param_name:<10} {'Ann%':>8} {'MaxDD%':>8} {'Sortino':>8} "
          f"{'Composite':>10} {'Pass?':>6}")
    for _, r in sw.iterrows():
        p = '✓' if r['comp_stab'] >= COMP_THRESHOLD else '✗'
        mark = ' ◀ BEST' if r['param_a'] == best_val else ''
        pval = f"{r['param_a']*100:.1f}%"
        print(f"  {pval:<10} {r['annual_return']*100:>7.1f}% "
              f"{r['max_dd_trade']*100:>7.1f}% {r['sortino']:>8.3f} "
              f"{r['comp_stab']:>10.3f} {p:>6}{mark}")

elif CAND_TYPE == 'atr':
    sw_p = stability_composite(sweep_period)
    sw_m = stability_composite(sweep_mult)

    pass_p = (sw_p['comp_stab'] >= COMP_THRESHOLD).sum()
    pass_m = (sw_m['comp_stab'] >= COMP_THRESHOLD).sum()
    pct_p  = pass_p / len(sw_p) * 100
    pct_m  = pass_m / len(sw_m) * 100
    overall = (pct_p + pct_m) / 2
    stab_overall = overall

    print(f"\n  ATR Period sweep (mult fixed at {best_mult}x): "
          f"{pass_p}/{len(sw_p)} ≥ {COMP_THRESHOLD} → {pct_p:.1f}% "
          f"→ {classify_stability(pct_p)}")
    print(f"  {'Period':<10} {'Ann%':>8} {'MaxDD%':>8} {'Sortino':>8} "
          f"{'Composite':>10} {'Pass?':>6}")
    for _, r in sw_p.iterrows():
        p = '✓' if r['comp_stab'] >= COMP_THRESHOLD else '✗'
        mark = ' ◀ BEST' if r['param_a'] == best_ap else ''
        print(f"  {int(r['param_a']):<10} {r['annual_return']*100:>7.1f}% "
              f"{r['max_dd_trade']*100:>7.1f}% {r['sortino']:>8.3f} "
              f"{r['comp_stab']:>10.3f} {p:>6}{mark}")

    print(f"\n  ATR Mult sweep (period fixed at {best_ap}): "
          f"{pass_m}/{len(sw_m)} ≥ {COMP_THRESHOLD} → {pct_m:.1f}% "
          f"→ {classify_stability(pct_m)}")
    print(f"  {'Mult':<10} {'Ann%':>8} {'MaxDD%':>8} {'Sortino':>8} "
          f"{'Composite':>10} {'Pass?':>6}")
    for _, r in sw_m.iterrows():
        p = '✓' if r['comp_stab'] >= COMP_THRESHOLD else '✗'
        mark = ' ◀ BEST' if r['param_b'] == best_mult else ''
        print(f"  {r['param_b']:<10.1f} {r['annual_return']*100:>7.1f}% "
              f"{r['max_dd_trade']*100:>7.1f}% {r['sortino']:>8.3f} "
              f"{r['comp_stab']:>10.3f} {p:>6}{mark}")

    print(f"\n  Overall stability: ({pct_p:.1f}% + {pct_m:.1f}%) / 2 = "
          f"{overall:.1f}% → {classify_stability(overall)}")

# --- Plateau sensitivity chart ---
if CAND_TYPE in ('pct', 'fixed'):
    fig_b, ax_b = plt.subplots(figsize=(9, 5))
    x_vals = sw.sort_values('param_a')['param_a'].values * 100
    y_vals = sw.sort_values('param_a')['annual_return'].values * 100
    color_line = '#2196F3' if CAND_TYPE == 'pct' else '#FF9800'
    ax_b.plot(x_vals, y_vals, 'o-', color=color_line, lw=2)
    best_x = CAND['param_a'] * 100
    best_y = CAND['annual_return'] * 100
    ax_b.plot(best_x, best_y, 'ro', ms=10, zorder=5,
              label=f"Best: {best_x:.1f}% ({best_y:.1f}%)")
    xlabel = 'Trail Stop %' if CAND_TYPE == 'pct' else 'Fixed Stop %'
    title_stop = 'PCT Trail' if CAND_TYPE == 'pct' else 'Fixed Stop'
    ax_b.set_xlabel(xlabel)
    ax_b.set_ylabel('Annual Return %')
    ax_b.set_title(f'BTC ADX {ADX_THRESHOLD}/{ADX_PERIOD} — {title_stop} Sensitivity\n'
                   'Cliff-edge check: red dot should sit at or near PEAK, not on slope')
    ax_b.legend()
    ax_b.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, 'btc_adx_stage_b_plateau.png'),
                dpi=130, bbox_inches='tight')
    plt.close()

elif CAND_TYPE == 'atr':
    fig_b, (ax_b1, ax_b2) = plt.subplots(1, 2, figsize=(13, 5))
    # Period sweep
    xp = sw_p.sort_values('param_a')['param_a'].values
    yp = sw_p.sort_values('param_a')['annual_return'].values * 100
    ax_b1.plot(xp, yp, 'o-', color='#2196F3', lw=2)
    ax_b1.axhline(m_fixed['annual_return'] * 100, color='gray', ls='--', lw=1,
                  label=f"Fixed 3% baseline")
    ax_b1.plot(best_ap, CAND['annual_return'] * 100, 'ro', ms=10, zorder=5,
               label=f"Best: period {best_ap}")
    ax_b1.set_xlabel(f'ATR Period  (mult fixed at {best_mult}x)')
    ax_b1.set_ylabel('Annual Return %')
    ax_b1.set_title('ATR Period Sensitivity')
    ax_b1.legend(fontsize=8)
    ax_b1.grid(alpha=0.3)
    # Mult sweep
    xm = sw_m.sort_values('param_b')['param_b'].values
    ym = sw_m.sort_values('param_b')['annual_return'].values * 100
    ax_b2.plot(xm, ym, 'o-', color='#4CAF50', lw=2)
    ax_b2.axhline(m_fixed['annual_return'] * 100, color='gray', ls='--', lw=1,
                  label=f"Fixed 3% baseline")
    ax_b2.plot(best_mult, CAND['annual_return'] * 100, 'ro', ms=10, zorder=5,
               label=f"Best: {best_mult}x")
    ax_b2.set_xlabel(f'ATR Multiplier  (period fixed at {best_ap})')
    ax_b2.set_ylabel('Annual Return %')
    ax_b2.set_title('ATR Multiplier Sensitivity')
    ax_b2.legend(fontsize=8)
    ax_b2.grid(alpha=0.3)
    fig_b.suptitle(f'BTC ADX {ADX_THRESHOLD}/{ADX_PERIOD} — Stage B Plateau Charts\n'
                   'Cliff-edge check: red dot should sit at or near PEAK',
                   fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, 'btc_adx_stage_b_plateau.png'),
                dpi=130, bbox_inches='tight')
    plt.close()

print(f"\n  Chart saved → results/btc_adx_stage_b_plateau.png")

input("\n  ▶ Stage B complete. Review results and press Enter to continue to Stage C...")


# ===========================================================================
#  STAGE C — Walk-Forward Validation
# ===========================================================================

print("\n" + "=" * 60)
print("STAGE C — WALK-FORWARD VALIDATION")
print(f"  Candidate: {CAND['label']}")
print("  Test windows: 2022, 2023, 2024")
print("  Methods: expanding (anchored) + rolling (3-yr train)")
print("  Note: with fixed parameters, both methods produce identical")
print("        test-period results — expanding vs rolling is a")
print("        disclosure structure, not a numerical distinction here.")
print("=" * 60)

TRAIN_START  = pd.Timestamp('2018-01-01')
TEST_WINDOWS = [
    {'test_start': pd.Timestamp('2022-01-01'), 'test_end': pd.Timestamp('2022-12-31')},
    {'test_start': pd.Timestamp('2023-01-01'), 'test_end': pd.Timestamp('2023-12-31')},
    {'test_start': pd.Timestamp('2024-01-01'), 'test_end': pd.Timestamp('2024-12-31')},
]
ROLL_YEARS = 3


def window_metrics(trades_df, test_start, test_end, close_series):
    """Metrics for trades exiting within the test window."""
    mask = ((pd.to_datetime(trades_df['exit_date']) >= test_start) &
            (pd.to_datetime(trades_df['exit_date']) <= test_end))
    wt = trades_df[mask].copy()

    cross_period = ((pd.to_datetime(wt['entry_date']) < test_start)).sum()

    if len(wt) == 0:
        return None, 0

    rets = wt['return'].values - COST_PER_TRADE

    # Per-trade equity / MaxDD
    eq_pt  = np.cumprod(1 + rets)
    pk_pt  = np.maximum.accumulate(eq_pt)
    dd_pt  = ((eq_pt - pk_pt) / pk_pt).min()
    ann_pt = eq_pt[-1] - 1

    # Daily MtM equity for the test window
    try:
        cs_win = close_series.loc[test_start:test_end]
        # Normalise equity to 1 at window start
        eq_mtm = build_daily_equity(wt, cs_win)
        pk_mtm = np.maximum.accumulate(eq_mtm)
        dd_mtm = ((eq_mtm - pk_mtm) / pk_mtm).min()
    except Exception:
        dd_mtm = dd_pt

    return {
        'n':             len(wt),
        'ann_return':    ann_pt,
        'max_dd_trade':  dd_pt,
        'max_dd_mtm':    dd_mtm,
        'cross_period':  cross_period,
        'low_n':         len(wt) < LOW_N,
    }, cross_period


df_cand_full = pd.DataFrame(t_cand)

print(f"\n  Full-period trade count: {len(df_cand_full)} trades")
print(f"\n  {'Window':<8} {'Method':<12} {'Train Period':<22} {'Trades':>6} "
      f"{'Annual%':>8} {'MaxDD%(trade)':>14} {'MaxDD%(MtM)':>12} {'Pass?':>6} {'Notes'}")
print(f"  {'-'*98}")

wf_results = []

for i, w in enumerate(TEST_WINDOWS, 1):
    ts, te = w['test_start'], w['test_end']
    yr = ts.year

    for method_name, train_start in [
        ('Expanding', TRAIN_START),
        (f'Rolling({ROLL_YEARS}y)', ts - pd.DateOffset(years=ROLL_YEARS)),
    ]:
        train_label = f"{train_start.year}–{(ts - pd.Timedelta(days=1)).year}"
        m, cp = window_metrics(df_cand_full, ts, te, df_btc['Close'])

        if m is None:
            print(f"  W{i} ({yr}) {method_name:<12} {train_label:<22} {'—':>6}")
            continue

        passes = m['ann_return'] > 0
        note = ''
        if m['low_n']:
            note += f'⚠ n={m["n"]} (<{LOW_N}) '
        if cp > 0:
            note += f'[{cp} cross-period trade{"s" if cp > 1 else ""}]'

        wf_results.append({
            'window': i, 'year': yr, 'method': method_name,
            **m, 'pass': passes,
        })

        marker = '✓ PASS' if passes else '✗ FAIL'
        print(f"  W{i} ({yr}) {method_name:<12} {train_label:<22} {m['n']:>6} "
              f"{m['ann_return']*100:>7.1f}% "
              f"{m['max_dd_trade']*100:>13.1f}% "
              f"{m['max_dd_mtm']*100:>11.1f}% "
              f"{marker:>6}  {note}")

# Walk-forward summary
exp_results = [r for r in wf_results if r['method'] == 'Expanding']
pass_count  = sum(1 for r in exp_results if r['pass'])
total_wf    = len(exp_results)
pos_yr_pct  = positive_years / total_years * 100

print(f"\n  WALK-FORWARD SUMMARY (expanding windows):")
print(f"  Windows passing: {pass_count}/{total_wf}")

if pass_count == total_wf:
    wf_verdict = 'PASS — profitable in all windows'
elif pass_count >= 2:
    wf_verdict = (f'CONDITIONAL PASS — {pass_count}/{total_wf} windows positive '
                  f'(check rationale for failing window)')
else:
    wf_verdict = f'FAIL — only {pass_count}/{total_wf} windows positive'

print(f"  Verdict: {wf_verdict}")

# Bear-year note
fail_years = [r['year'] for r in exp_results if not r['pass']]
if 2022 in fail_years:
    print(f"\n  2022 BEAR-YEAR NOTE:")
    print(f"  BTC fell ~65% in 2022. A loss in W1(2022) is expected for a long-only")
    print(f"  trend-following strategy. This is the same pattern seen in BTC SMA")
    print(f"  validation (BS003). If loss is small relative to the -65% BTC decline,")
    print(f"  it can be accepted as structural (not an artifact), with disclosure.")
    r22 = next((r for r in exp_results if r['year'] == 2022), None)
    if r22:
        print(f"  2022 strategy return: {r22['ann_return']*100:.1f}%  "
              f"vs BTC buy-and-hold: approx -65%")

input("\n  ▶ Stage C complete. Review results and press Enter to continue to Stage D...")


# ===========================================================================
#  STAGE D — ETH Cross-Asset Check
# ===========================================================================

print("\n" + "=" * 60)
print("STAGE D — ETH CROSS-ASSET CHECK")
print(f"  Applying BTC-optimised params ({CAND['label']}) to ETH-USD")
print("  Note: failure is informative (asset-specific edge) not")
print("        automatically disqualifying for BTC deployment.")
print("=" * 60)

print("\nFetching ETH-USD daily data (2018-2026)...")
raw_eth = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False,
                       auto_adjust=True)
if isinstance(raw_eth.columns, pd.MultiIndex):
    raw_eth.columns = raw_eth.columns.droplevel(1)
df_eth = raw_eth[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df_eth.dropna(inplace=True)
years_eth = (df_eth.index[-1] - df_eth.index[0]).days / 365.25
print(f"ETH data: {df_eth.index[0].date()} → {df_eth.index[-1].date()} ({years_eth:.1f} yrs)")

# ADX signals for ETH (same threshold/period)
adx_eth   = ADXIndicator(df_eth['High'], df_eth['Low'], df_eth['Close'],
                          window=ADX_PERIOD)
sig_eth   = ((adx_eth.adx().values >= ADX_THRESHOLD) &
             (adx_eth.adx_pos().values > adx_eth.adx_neg().values))

closes_eth = df_eth['Close'].values
lows_eth   = df_eth['Low'].values
dates_eth  = df_eth.index

if CAND_TYPE == 'pct':
    t_eth = run_pct_trail(closes_eth, lows_eth, sig_eth, dates_eth, CAND['param_a'])
elif CAND_TYPE == 'atr':
    atr_eth = compute_atr(df_eth['High'], df_eth['Low'], df_eth['Close'],
                          int(CAND['param_a']))
    t_eth   = run_atr_trail(closes_eth, lows_eth, sig_eth, atr_eth, dates_eth,
                             CAND['param_b'])
else:  # fixed
    t_eth = run_fixed_stop(closes_eth, lows_eth, sig_eth, dates_eth, CAND['param_a'])

m_eth = calc_metrics(t_eth, df_eth['Close'], years_eth)

print(f"\n  ETH RESULTS — {CAND['label']} (BTC-optimised params)")
if m_eth:
    print(f"  Annual Return%:       {m_eth['annual_return']*100:.1f}%")
    print(f"  MaxDD% (per-trade):   {m_eth['max_dd_trade']*100:.1f}%")
    print(f"  MaxDD% (daily MtM):   {m_eth['max_dd_mtm']*100:.1f}%")
    print(f"  Sortino:              {m_eth['sortino']:.3f}")
    print(f"  Calmar:               {m_eth['calmar']:.3f}")
    print(f"  N trades:             {m_eth['n_trades']}")
    print(f"  Win rate:             {m_eth['win_rate']*100:.1f}%")
    print(f"  Profit Factor:        {m_eth['profit_factor']:.3f}")

    # Year-by-year for ETH
    df_eth_t = pd.DataFrame(t_eth)
    df_eth_t['exit_year'] = pd.to_datetime(df_eth_t['exit_date']).dt.year
    print(f"\n  ETH YEAR-BY-YEAR (exit year):")
    print(f"  {'Year':<6} {'Trades':>6} {'Ann%':>9} {'Note'}")
    for yr in sorted(df_eth_t['exit_year'].unique()):
        yr_t = df_eth_t[df_eth_t['exit_year'] == yr]
        rets_y = yr_t['return'].values - COST_PER_TRADE
        ann_y  = np.cumprod(1 + rets_y)[-1] - 1
        flag   = f'  ⚠ n={len(yr_t)}' if len(yr_t) < LOW_N else ''
        marker = '✓' if ann_y > 0 else '✗'
        print(f"  {yr:<6} {len(yr_t):>6} {ann_y*100:>8.1f}%  {marker}{flag}")

    # Cross-asset verdict
    print(f"\n  CROSS-ASSET VERDICT:")
    sortino_ok = m_eth['sortino'] >= 0.8
    calmar_ok  = m_eth['calmar'] >= 1.0
    if sortino_ok and calmar_ok:
        eth_verdict = 'PASS — edge generalises to ETH (Sortino ≥ 0.8, Calmar ≥ 1.0)'
    elif sortino_ok or calmar_ok:
        eth_verdict = 'PARTIAL — one threshold met, one missed (informative, not disqualifying)'
    else:
        eth_verdict = ('FAIL — edge does not generalise to ETH '
                       '(Sortino < 0.8 and Calmar < 1.0)')
    print(f"  Sortino ≥ 0.8: {'✓' if sortino_ok else '✗'} ({m_eth['sortino']:.3f})")
    print(f"  Calmar  ≥ 1.0: {'✓' if calmar_ok else '✗'} ({m_eth['calmar']:.3f})")
    print(f"  → {eth_verdict}")
    print(f"\n  Context: BTC SMA 120/25% on ETH scored Sortino 0.505, Calmar 0.291.")
    print(f"  ETH already has its own validated ADX strategy (ADX 19/9, ATR 9/2.5x,")
    print(f"  Calmar 2.642). Cross-asset failure here means BTC ADX edge is BTC-specific,")
    print(f"  not that ADX fails on ETH in general.")
else:
    print("  Insufficient ETH trades for metrics.")
    eth_verdict = 'INCONCLUSIVE — insufficient trades'

input("\n  ▶ Stage D complete. Review results and press Enter for Final Summary...")


# ===========================================================================
#  FINAL SUMMARY
# ===========================================================================

print("\n" + "=" * 70)
print("FINAL SUMMARY — BTC ADX 19/14 VALIDATION (SI001)")
print("=" * 70)

# Restate candidate
print(f"\n  Validated configuration: ADX {ADX_THRESHOLD}/{ADX_PERIOD}, {CAND['label']}")
print(f"  Data: BTC-USD {df_btc.index[0].year}–{df_btc.index[-1].year}, "
      f"{years_btc:.1f} years, {CAND['n_trades']:.0f} trades")
print(f"  Costs: 0.15% round-trip  |  Bar-by-bar stop on daily LOW")

print(f"\n  ── KEY METRICS ──────────────────────────────────────────")
print(f"  Annual Return %:          {CAND['annual_return']*100:.1f}%")
print(f"  MaxDD % (per-trade):      {CAND['max_dd_trade']*100:.1f}%")
print(f"  MaxDD % (daily MtM):      {CAND['max_dd_mtm']*100:.1f}%")
print(f"  Sortino (daily equity):   {CAND['sortino']:.3f}")
print(f"  Calmar:                   {CAND['calmar']:.3f}")
print(f"  N Trades:                 {CAND['n_trades']:.0f}")

stab_label = classify_stability(stab_overall)

print(f"\n  ── STAGE OUTCOMES ───────────────────────────────────────")
print(f"  Stage A (grid search):    {CAND['label']} — best by Annual Return%")
print(f"  Stage B (stability):      {stab_label}")
print(f"  Stage C (walk-forward):   {wf_verdict}")
print(f"  Stage D (ETH check):      {eth_verdict}")

# --- Comparison vs BTC SMA ---
print(f"\n  ── BTC CAPITAL ALLOCATION: ADX vs SMA ──────────────────")
print(f"  {'Metric':<28} {'BTC ADX ' + CAND['label']:>22} {'BTC SMA 120/25%':>18}")
print(f"  {'-'*70}")
print(f"  {'Annual Return %':<28} {CAND['annual_return']*100:>21.1f}% {BTC_SMA_ANN:>17.1f}%")
print(f"  {'MaxDD % (per-trade)':<28} {CAND['max_dd_trade']*100:>21.1f}% {BTC_SMA_MAXDD_TRADE:>17.1f}%")
print(f"  {'MaxDD % (daily MtM)':<28} {CAND['max_dd_mtm']*100:>21.1f}% {BTC_SMA_MAXDD_MTM:>17.1f}%")
print(f"  {'Sortino':<28} {CAND['sortino']:>22.3f} {BTC_SMA_SORTINO:>18.3f}")
print(f"  {'Calmar':<28} {CAND['calmar']:>22.3f} {BTC_SMA_CALMAR:>18.3f}")
print(f"  {'N Trades':<28} {CAND['n_trades']:>22.0f} {BTC_SMA_TRADES:>18}")
print(f"  {'ETH cross-asset':<28} {'(see Stage D)':>22} {'FAIL':>18}")

# GO / NO-GO decision
print(f"\n  ── GO / NO-GO ───────────────────────────────────────────")
go_flags = []
nogo_flags = []

if CAND['n_trades'] >= 30:
    go_flags.append(f"✓ N trades ≥ 30 ({CAND['n_trades']:.0f})")
else:
    nogo_flags.append(f"✗ N trades < 30 ({CAND['n_trades']:.0f})")

if CAND['sortino'] >= 0.8:
    go_flags.append(f"✓ Sortino ≥ 0.8 ({CAND['sortino']:.3f})")
else:
    nogo_flags.append(f"✗ Sortino < 0.8 ({CAND['sortino']:.3f})")

if CAND['calmar'] >= 1.0:
    go_flags.append(f"✓ Calmar ≥ 1.0 ({CAND['calmar']:.3f})")
else:
    nogo_flags.append(f"✗ Calmar < 1.0 ({CAND['calmar']:.3f})")

if pass_count >= 2:
    go_flags.append(f"✓ Walk-forward: {pass_count}/{total_wf} windows pass")
else:
    nogo_flags.append(f"✗ Walk-forward: {pass_count}/{total_wf} windows pass")

if stab_label in ('STABLE', 'MARGINAL'):
    go_flags.append(f"✓ Stability: {stab_label}")
else:
    nogo_flags.append(f"✗ Stability: {stab_label}")

for f in go_flags:
    print(f"  {f}")
for f in nogo_flags:
    print(f"  {f}")

if len(nogo_flags) == 0:
    decision = 'GO'
    decision_note = 'All thresholds met. Strategy eligible for deployment.'
elif len(nogo_flags) == 1 and '2022' in wf_verdict:
    decision = 'CONDITIONAL GO'
    decision_note = ('One walk-forward failure in 2022 bear market — same pattern as '
                     'BTC SMA. Acceptable with disclosure if loss is small vs BTC -65%.')
elif len(nogo_flags) <= 2:
    decision = 'CONDITIONAL'
    decision_note = f'{len(nogo_flags)} threshold(s) missed. Review before deployment.'
else:
    decision = 'NO-GO'
    decision_note = f'{len(nogo_flags)} thresholds missed. Do not deploy.'

print(f"\n  ┌─────────────────────────────────────────────────────┐")
print(f"  │  FINAL DECISION: {decision:<35}│")
print(f"  │  {decision_note:<53}│")
print(f"  └─────────────────────────────────────────────────────┘")

if decision in ('GO', 'CONDITIONAL GO'):
    print(f"\n  RECOMMENDED NEXT STEPS:")
    print(f"  1. Create RISK_REGISTER_BTC_ADX.md documenting validation outcomes")
    print(f"  2. Complete LIVE_TRADING_CHECKLIST.md for BTC ADX deployment")
    stop_desc = (f"PCT {CAND['param_a']*100:.1f}% trail" if CAND_TYPE == 'pct' else
                 f"ATR{int(CAND['param_a'])} {CAND['param_b']}x trail" if CAND_TYPE == 'atr' else
                 f"fixed {CAND['param_a']*100:.1f}% stop")
    print(f"  3. Build production bot: BTC-USD, ADX {ADX_THRESHOLD}/{ADX_PERIOD}, {stop_desc}")
    print(f"  4. Test on Binance testnet — full trade cycle (entry → {stop_desc} or ADX signal exit)")
    print(f"  5. Allocate $1,000 BTC capital (separate from ETH ADX)")
    if 2022 in fail_years:
        print(f"  6. Document 2022 bear-year context in deployment risk disclosure")
elif decision == 'NO-GO':
    print(f"\n  NO-GO rationale documented above.")
    print(f"  Review whether BTC capital remains undeployed (pending re-investigation)")
    print(f"  or whether BTC SMA warrants re-investigation with extended parameter range.")

print(f"\n  Week 5 uncorrected baseline: Calmar 1.121 (per-trade Sortino, no costs)")
print(f"  This validation (corrected):  Calmar {CAND['calmar']:.3f} "
      f"(daily equity Sortino, 0.15% costs)")
print()
