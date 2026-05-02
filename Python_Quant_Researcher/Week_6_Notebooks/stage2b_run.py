# Stage 2a Extension + Stage 2b — ATR Trailing Stop Grid
#
# Part 1: Stage 2a extended — adds trail 22.5% and 25% to confirm boundary
# Part 2: Stage 2b — SMA × ATR period × ATR multiplier (912 combos)
#
# All results ranked by composite score:
#   Composite = equal-weight mean of min-max normalised(Calmar, Sortino, Ann%, MaxDD%)
#   MaxDD: less negative = better = higher normalised value (no invert needed)

import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import yfinance as yf
from itertools import product

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)

COST_PER_TRADE  = 0.00075 * 2
MIN_TRADES      = 5
LOW_TRADES_FLAG = 30

SMA_PERIODS  = list(range(80, 171, 5))                          # 19 values
TRAIL_EXT    = [round(x, 4) for x in [0.225, 0.25]]            # new: 22.5%, 25%
ATR_PERIODS  = list(range(7, 22, 2))                            # 8 values
ATR_MULTS    = [round(x, 1) for x in np.arange(1.5, 4.1, 0.5)] # 6 values

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

print("Fetching BTC-USD daily data...")
raw = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = raw[['Open', 'High', 'Low', 'Close']].dropna().copy()
df.index = pd.to_datetime(df.index)
closes = df['Close'].values.astype(float)
highs  = df['High'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index
years  = (df.index[-1] - df.index[0]).days / 365.25
print(f"  {df.index[0].date()} → {df.index[-1].date()} ({len(df)} bars)")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_atr(period):
    n  = len(closes)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
    return pd.Series(tr).ewm(alpha=1.0/period, adjust=False).mean().values


def build_daily_equity(trades_df, close_series):
    n = len(close_series); closes_arr = close_series.values
    date_to_i = pd.Series(np.arange(n), index=close_series.index)
    equity = np.ones(n); portfolio = 1.0; prev_i = 0
    for _, t in trades_df.iterrows():
        ei = date_to_i.get(pd.Timestamp(t['entry_date']))
        xi = date_to_i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None: continue
        equity[prev_i:ei] = portfolio
        equity[ei:xi+1]   = portfolio * closes_arr[ei:xi+1] / t['entry_price']
        portfolio         *= (1 + t['return'] - COST_PER_TRADE)
        equity[xi]         = portfolio; prev_i = xi + 1
    equity[prev_i:] = portfolio
    return equity


def metrics_from_trades(trades, yrs, close_series):
    if len(trades) < MIN_TRADES: return None
    df_t = pd.DataFrame(trades)
    df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
    df_t['exit_date']  = pd.to_datetime(df_t['exit_date'])
    df_t = df_t.sort_values('entry_date').reset_index(drop=True)
    returns = df_t['return'].values - COST_PER_TRADE
    wm = returns > 0; lm = returns <= 0
    win_rate      = wm.sum() / len(returns)
    gross_p       = returns[wm].sum() if wm.any() else 0.0
    gross_l       = abs(returns[lm].sum()) if lm.any() else 1e-9
    profit_factor = gross_p / gross_l
    avg_win       = returns[wm].mean() if wm.any() else 0.0
    avg_loss      = returns[lm].mean() if lm.any() else 0.0
    total_ret     = np.prod(1 + returns) - 1
    ann_ret       = (1 + total_ret) ** (1 / yrs) - 1
    cum_eq        = np.cumprod(1 + returns)
    peak          = np.maximum.accumulate(cum_eq)
    max_dd        = ((cum_eq - peak) / peak).min()
    calmar        = ann_ret / abs(max_dd) if max_dd != 0 else 0.0
    cs = close_series.loc[df_t['entry_date'].min() : df_t['exit_date'].max()]
    eq = build_daily_equity(df_t, cs)
    dr = np.diff(eq) / eq[:-1]; dn = dr[dr < 0]
    sharpe  = dr.mean() / dr.std()  * np.sqrt(365) if dr.std() > 0 else 0.0
    sortino = dr.mean() / dn.std()  * np.sqrt(365) if (len(dn)>0 and dn.std()>0) else 0.0
    stop_pct = 0.0
    if 'exit_reason' in df_t.columns:
        stop_pct = (df_t['exit_reason']=='TRAIL_STOP').sum()/len(df_t)*100
    return {'total_trades': len(trades), 'win_rate': win_rate,
            'avg_win': avg_win, 'avg_loss': avg_loss, 'profit_factor': profit_factor,
            'annual_return': ann_ret, 'max_drawdown': max_dd, 'calmar': calmar,
            'sharpe': sharpe, 'sortino': sortino, 'stop_exit_pct': stop_pct,
            'low_trades': len(trades) < LOW_TRADES_FLAG}


def run_sma_pct_trail(sma_vals, trail_pct):
    fv = int(np.argmax(~np.isnan(sma_vals)))
    position = entry_i = 0; entry_price = peak_price = stop_price = 0.0
    trades = []; sig_prev = False
    for i in range(fv, len(closes)):
        close, low, sv = closes[i], lows[i], sma_vals[i]
        if np.isnan(sv): continue
        sig_cur = close > sv
        if position == 1:
            if close > peak_price:
                peak_price = close; stop_price = peak_price * (1 - trail_pct)
            if low <= stop_price:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': stop_price,
                               'return': (stop_price-entry_price)/entry_price,
                               'exit_reason': 'TRAIL_STOP'}); position = 0
            elif not sig_cur:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': close,
                               'return': (close-entry_price)/entry_price,
                               'exit_reason': 'SMA_EXIT'}); position = 0
        if position == 0 and sig_cur and not sig_prev:
            position = 1; entry_i = i; entry_price = close
            peak_price = close; stop_price = close * (1 - trail_pct)
        sig_prev = sig_cur
    if position == 1:
        trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                       'exit_date': dates[-1], 'exit_price': closes[-1],
                       'return': (closes[-1]-entry_price)/entry_price, 'exit_reason': 'END'})
    return trades


def run_sma_atr_trail(sma_vals, atr_vals, atr_mult):
    fv = int(np.argmax(~np.isnan(sma_vals)))
    position = entry_i = 0; entry_price = peak_price = stop_price = 0.0
    trades = []; sig_prev = False
    for i in range(fv, len(closes)):
        close, low, sv, av = closes[i], lows[i], sma_vals[i], atr_vals[i]
        if np.isnan(sv) or np.isnan(av) or av <= 0: continue
        sig_cur = close > sv
        if position == 1:
            if close > peak_price: peak_price = close
            new_stop = peak_price - atr_mult * av
            if new_stop > stop_price: stop_price = new_stop
            if low <= stop_price:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': stop_price,
                               'return': (stop_price-entry_price)/entry_price,
                               'exit_reason': 'TRAIL_STOP'}); position = 0
            elif not sig_cur:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': close,
                               'return': (close-entry_price)/entry_price,
                               'exit_reason': 'SMA_EXIT'}); position = 0
        if position == 0 and sig_cur and not sig_prev:
            position = 1; entry_i = i; entry_price = close
            peak_price = close; stop_price = close - atr_mult * av
        sig_prev = sig_cur
    if position == 1:
        trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                       'exit_date': dates[-1], 'exit_price': closes[-1],
                       'return': (closes[-1]-entry_price)/entry_price, 'exit_reason': 'END'})
    return trades


def composite_score(df_in):
    """Add normalised columns and composite score. Returns augmented DataFrame."""
    df_out = df_in.copy()
    def mm(s, invert=False):
        lo, hi = s.min(), s.max()
        if hi == lo: return pd.Series(0.5, index=s.index)
        n = (s - lo) / (hi - lo)
        return (1 - n) if invert else n
    # max_drawdown is all-negative: less negative = better = higher value → no invert
    df_out['norm_calmar']  = mm(df_out['calmar'])
    df_out['norm_sortino'] = mm(df_out['sortino'])
    df_out['norm_annual']  = mm(df_out['annual_return'])
    df_out['norm_maxdd']   = mm(df_out['max_drawdown'])
    df_out['composite']    = (df_out['norm_calmar'] + df_out['norm_sortino'] +
                               df_out['norm_annual'] + df_out['norm_maxdd']) / 4.0
    return df_out


def print_table(df_ranked, n=20, label=''):
    if label: print(f"\n--- {label} ---\n")
    H = (f"{'Rk':>2}  {'Comp':>5}  {'Calmar':>7}  {'Sortino':>7}  "
         f"{'Ann%':>6}  {'MaxDD%':>7}  {'n':>3}  {'Win%':>5}  {'PF':>6}  {'Stop%':>5}")
    print(H); print("─" * len(H))
    for rk, (_, row) in enumerate(df_ranked.head(n).iterrows(), 1):
        flag = " !" if row.get('low_trades', False) else ""
        params = ""
        if 'sma_period' in row and 'trail_pct' in row:
            params = f"SMA {int(row['sma_period'])} / pct {row['trail_pct']:.2f}%"
        elif 'sma_period' in row and 'atr_period' in row:
            params = f"SMA {int(row['sma_period'])} / ATR {int(row['atr_period'])} / {row['atr_mult']:.1f}x"
        print(f"{rk:>2}  {row['composite']:>5.3f}  {row['calmar']:>7.3f}  "
              f"{row['sortino']:>7.3f}  {row['annual_return']:>6.1f}  "
              f"{row['max_drawdown']:>7.1f}  {int(row['total_trades']):>3}  "
              f"{row['win_rate']:>5.1f}  {row['profit_factor']:>6.3f}  "
              f"{row['stop_exit_pct']:>5.1f}  {params}{flag}")


def equity_curves_chart(candidates, title, filename, df_close):
    """Plot equity curves for up to 5 candidates + BTC B&H."""
    colors = ['#1565C0', '#2E7D32', '#E65100', '#6A1B9A', '#00838F']
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9),
                                    gridspec_kw={'height_ratios': [3, 1]})
    bh_eq = closes / closes[0]
    ax1.plot(dates, bh_eq, color='#BDBDBD', linewidth=1.2, label='BTC Buy-and-Hold', zorder=1)
    for i, (lbl, trades_fn) in enumerate(candidates):
        trades = trades_fn()
        if not trades: continue
        df_t = pd.DataFrame(trades)
        df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
        df_t['exit_date']  = pd.to_datetime(df_t['exit_date'])
        eq = build_daily_equity(df_t, df_close)
        ax1.plot(dates[:len(eq)], eq, color=colors[i], linewidth=1.5, label=lbl, zorder=i+2)
        pk = np.maximum.accumulate(eq)
        ax2.plot(dates[:len(eq)], (eq-pk)/pk*100, color=colors[i], linewidth=1, alpha=0.8)
    ax1.set_yscale('log')
    ax1.set_ylabel('Portfolio value (log, start=1)')
    ax1.set_title(title, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f'{y:.1f}'))
    ax1.grid(True, alpha=0.3)
    ax2.axhline(0, color='black', linewidth=0.5)
    ax2.set_ylabel('Drawdown (%)'); ax2.set_xlabel('Date'); ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, filename)
    plt.savefig(path, dpi=150, bbox_inches='tight'); plt.close()
    print(f"  Saved → {path}")

# ---------------------------------------------------------------------------
# Pre-compute caches
# ---------------------------------------------------------------------------

print("Pre-computing SMA arrays...")
sma_cache = {p: pd.Series(closes).rolling(p, min_periods=p).mean().values for p in SMA_PERIODS}
print("Pre-computing ATR arrays...")
atr_cache = {p: compute_atr(p) for p in ATR_PERIODS}

# ===========================================================================
# PART 1 — Stage 2a Extension: trail 22.5% and 25%
# ===========================================================================

print("\n" + "=" * 72)
print("STAGE 2a EXTENSION — Trail 22.5% and 25%")
print(f"  {len(SMA_PERIODS)} SMA periods × 2 new trail values = {len(SMA_PERIODS)*2} new combos")
print("=" * 72)

rows_ext = []
for sma_p, trail_p in product(SMA_PERIODS, TRAIL_EXT):
    trades = run_sma_pct_trail(sma_cache[sma_p], trail_p)
    m = metrics_from_trades(trades, years, df['Close'])
    if m is None: continue
    rows_ext.append({
        'sma_period': sma_p, 'trail_pct': round(trail_p*100, 2),
        'total_trades': m['total_trades'], 'win_rate': round(m['win_rate']*100, 1),
        'avg_win': round(m['avg_win']*100, 2), 'avg_loss': round(m['avg_loss']*100, 2),
        'profit_factor': round(m['profit_factor'], 3),
        'annual_return': round(m['annual_return']*100, 1),
        'max_drawdown': round(m['max_drawdown']*100, 1),
        'calmar': round(m['calmar'], 3), 'sharpe': round(m['sharpe'], 3),
        'sortino': round(m['sortino'], 3), 'stop_exit_pct': round(m['stop_exit_pct'], 1),
        'low_trades': m['low_trades'],
    })

df_ext = pd.DataFrame(rows_ext)

# Merge with existing Stage 2a results and re-normalise across full grid
df_2a_orig = pd.read_csv(os.path.join(DATA_DIR, 'stage2a_results.csv'))
df_2a_full = pd.concat([df_2a_orig, df_ext], ignore_index=True)
df_2a_full = composite_score(df_2a_full)
df_2a_full = df_2a_full.sort_values('composite', ascending=False).reset_index(drop=True)
df_2a_full.to_csv(os.path.join(DATA_DIR, 'stage2a_results_extended.csv'), index=False)
print(f"\n  Extended grid: {len(df_2a_full)} total combos "
      f"(133 original + {len(df_ext)} new)")

# Answer the boundary question: best at 22.5% and 25%?
print("\n--- New trail values: top 5 at 22.5% and top 5 at 25% ---\n")
for tval in [22.5, 25.0]:
    sub = df_2a_full[df_2a_full['trail_pct'] == tval].head(5)
    print(f"  Trail {tval:.1f}% — top 5 by composite:")
    print(f"  {'SMA':>4}  {'Comp':>5}  {'Calmar':>7}  {'Sortino':>7}  "
          f"{'Ann%':>6}  {'MaxDD%':>7}  {'n':>3}")
    for _, row in sub.iterrows():
        flag = " !" if row['low_trades'] else ""
        print(f"  {int(row['sma_period']):>4}  {row['composite']:>5.3f}  "
              f"{row['calmar']:>7.3f}  {row['sortino']:>7.3f}  "
              f"{row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  "
              f"{int(row['total_trades']):>3}{flag}")
    print()

# Summary by trail% — Calmar and composite for each level
print("--- Per-trail-% summary: best Calmar and best composite across all SMA periods ---\n")
trail_all = sorted(df_2a_full['trail_pct'].unique())
H_tr = f"{'Trail%':>6}  {'Best Calmar':>11}  {'Best Composite':>14}  {'Best SMA(Cal)':>13}  {'Best SMA(Comp)':>14}"
print(H_tr); print("─" * len(H_tr))
for t in trail_all:
    sub = df_2a_full[df_2a_full['trail_pct'] == t]
    bc  = sub.loc[sub['calmar'].idxmax()]
    bcp = sub.loc[sub['composite'].idxmax()]
    print(f"{t:>6.2f}  {bc['calmar']:>11.3f}  {bcp['composite']:>14.3f}  "
          f"{int(bc['sma_period']):>13}  {int(bcp['sma_period']):>14}")

# Full top-10 of extended grid
print_table(df_2a_full.head(10), n=10, label="Extended Stage 2a — top 10 by composite (all trail% values)")

# Equity curves: best at 20%, best at 22.5%, best at 25%
best_20  = df_2a_full[df_2a_full['trail_pct']==20.0].iloc[0]
best_225 = df_2a_full[df_2a_full['trail_pct']==22.5].iloc[0]
best_25  = df_2a_full[df_2a_full['trail_pct']==25.0].iloc[0]

cands_ext = [
    (f"SMA {int(best_20['sma_period'])}/20%  Comp {best_20['composite']:.3f}  Cal {best_20['calmar']:.3f}",
     lambda: run_sma_pct_trail(sma_cache[int(best_20['sma_period'])], 0.20)),
    (f"SMA {int(best_225['sma_period'])}/22.5%  Comp {best_225['composite']:.3f}  Cal {best_225['calmar']:.3f}",
     lambda: run_sma_pct_trail(sma_cache[int(best_225['sma_period'])], 0.225)),
    (f"SMA {int(best_25['sma_period'])}/25%  Comp {best_25['composite']:.3f}  Cal {best_25['calmar']:.3f}",
     lambda: run_sma_pct_trail(sma_cache[int(best_25['sma_period'])], 0.25)),
]
print("\n5. Equity curves — best combo at 20%, 22.5%, 25% vs BTC B&H")
equity_curves_chart(
    cands_ext,
    'Stage 2a Extended — Best Combo at 20%, 22.5%, 25% Trail vs BTC Buy-and-Hold',
    'stage2a_boundary_check.png',
    df['Close'],
)

# Boundary verdict
best_overall_2a = df_2a_full.iloc[0]
print(f"\n  BOUNDARY VERDICT:")
print(f"    Best 20%:   SMA {int(best_20['sma_period'])} → Comp {best_20['composite']:.3f}, "
      f"Cal {best_20['calmar']:.3f}, Ann {best_20['annual_return']:.1f}%, MaxDD {best_20['max_drawdown']:.1f}%")
print(f"    Best 22.5%: SMA {int(best_225['sma_period'])} → Comp {best_225['composite']:.3f}, "
      f"Cal {best_225['calmar']:.3f}, Ann {best_225['annual_return']:.1f}%, MaxDD {best_225['max_drawdown']:.1f}%")
print(f"    Best 25%:   SMA {int(best_25['sma_period'])} → Comp {best_25['composite']:.3f}, "
      f"Cal {best_25['calmar']:.3f}, Ann {best_25['annual_return']:.1f}%, MaxDD {best_25['max_drawdown']:.1f}%")
print(f"    Overall best (extended 2a): {best_overall_2a['trail_pct']:.2f}% trail, "
      f"SMA {int(best_overall_2a['sma_period'])}")

# ===========================================================================
# PART 2 — Stage 2b: SMA × ATR period × multiplier
# ===========================================================================

print("\n" + "=" * 72)
print("STAGE 2b — ATR Trailing Stop Grid")
print(f"  {len(SMA_PERIODS)} SMA × {len(ATR_PERIODS)} ATR periods × {len(ATR_MULTS)} mults = "
      f"{len(SMA_PERIODS)*len(ATR_PERIODS)*len(ATR_MULTS)} combos  |  costs: {COST_PER_TRADE*100:.2f}% r/t")
print("=" * 72)

rows_2b = []
combos_2b = list(product(SMA_PERIODS, ATR_PERIODS, ATR_MULTS))
for idx, (sma_p, atr_p, atr_m) in enumerate(combos_2b):
    if idx % 100 == 99:
        print(f"  {idx+1}/{len(combos_2b)}...")
    trades = run_sma_atr_trail(sma_cache[sma_p], atr_cache[atr_p], atr_m)
    m = metrics_from_trades(trades, years, df['Close'])
    if m is None: continue
    rows_2b.append({
        'sma_period': sma_p, 'atr_period': atr_p, 'atr_mult': atr_m,
        'total_trades': m['total_trades'], 'win_rate': round(m['win_rate']*100, 1),
        'avg_win': round(m['avg_win']*100, 2), 'avg_loss': round(m['avg_loss']*100, 2),
        'profit_factor': round(m['profit_factor'], 3),
        'annual_return': round(m['annual_return']*100, 1),
        'max_drawdown': round(m['max_drawdown']*100, 1),
        'calmar': round(m['calmar'], 3), 'sharpe': round(m['sharpe'], 3),
        'sortino': round(m['sortino'], 3), 'stop_exit_pct': round(m['stop_exit_pct'], 1),
        'low_trades': m['low_trades'],
    })

df_2b_raw = pd.DataFrame(rows_2b)
df_2b = composite_score(df_2b_raw).sort_values('composite', ascending=False).reset_index(drop=True)
df_2b.to_csv(os.path.join(DATA_DIR, 'stage2b_results.csv'), index=False)
print(f"\n  {len(df_2b)} valid combos. Saved → data/stage2b_results.csv")

# --- Top 20 ---
print_table(df_2b, n=20, label="Stage 2b — Top 20 by composite score")

# --- Bottom 5 ---
df_2b_bot = df_2b.sort_values('composite').head(5)
print_table(df_2b_bot, n=5, label="Stage 2b — Bottom 5 (lowest composite)")

# --- Grid coverage ---
print("\n--- Stage 2b grid coverage ---\n")
n_2b = len(df_2b)
for label, col, thresholds in [
    ("Composite", "composite", [0.5, 0.6, 0.7, 0.8]),
    ("Calmar",    "calmar",    [1.0, 1.5, 2.0, 2.5]),
]:
    print(f"  {label}:")
    for t in thresholds:
        n_a = (df_2b[col] >= t).sum()
        print(f"    ≥ {t:.1f}:  {n_a:>4}/{n_2b}  ({n_a/n_2b*100:.1f}%)")
    print()

# Breakdown by ATR mult — how many SMA×ATR combos clear composite ≥ 0.5?
print("  Composite ≥ 0.5 by ATR multiplier:")
for m_val in sorted(df_2b['atr_mult'].unique()):
    sub = df_2b[df_2b['atr_mult'] == m_val]
    n_p = (sub['composite'] >= 0.5).sum()
    bar = "█" * (n_p // 3)
    print(f"    mult {m_val:.1f}:  {n_p:>3}/{len(sub)}  {bar}")

print("\n  Composite ≥ 0.5 by ATR period:")
for ap in sorted(df_2b['atr_period'].unique()):
    sub = df_2b[df_2b['atr_period'] == ap]
    n_p = (sub['composite'] >= 0.5).sum()
    bar = "█" * (n_p // 3)
    print(f"    ATR {ap:>2}:  {n_p:>3}/{len(sub)}  {bar}")

# --- Heatmaps: two 2D projections ---
print("\n  Generating Stage 2b heatmaps...")

mults_u = sorted(df_2b['atr_mult'].unique())
atrs_u  = sorted(df_2b['atr_period'].unique())
smas_u  = sorted(df_2b['sma_period'].unique())

# Heatmap 1: ATR multiplier (x) vs SMA period (y), best composite over all ATR periods
mat_sma_mult = np.full((len(smas_u), len(mults_u)), np.nan)
for ri, sma_p in enumerate(smas_u):
    for ci, m_v in enumerate(mults_u):
        sub = df_2b[(df_2b['sma_period']==sma_p) & (df_2b['atr_mult']==m_v)]
        if len(sub): mat_sma_mult[ri, ci] = sub['composite'].max()

# Heatmap 2: ATR period (x) vs ATR multiplier (y), best composite over all SMA periods
mat_atr_mult = np.full((len(mults_u), len(atrs_u)), np.nan)
for ri, m_v in enumerate(mults_u):
    for ci, atr_p in enumerate(atrs_u):
        sub = df_2b[(df_2b['atr_mult']==m_v) & (df_2b['atr_period']==atr_p)]
        if len(sub): mat_atr_mult[ri, ci] = sub['composite'].max()

fig, axes = plt.subplots(1, 2, figsize=(18, 6))

for ax, mat, x_labels, y_labels, x_lbl, y_lbl, title in [
    (axes[0], mat_sma_mult, [f'{m:.1f}' for m in mults_u], [str(s) for s in smas_u],
     'ATR Multiplier', 'SMA Period',
     'Best composite score\n(maximised over ATR period)'),
    (axes[1], mat_atr_mult, [str(a) for a in atrs_u], [f'{m:.1f}' for m in mults_u],
     'ATR Period', 'ATR Multiplier',
     'Best composite score\n(maximised over SMA period)'),
]:
    im = ax.imshow(mat, aspect='auto', cmap='RdYlGn', origin='lower',
                   vmin=0, vmax=np.nanmax(mat))
    ax.set_xticks(range(len(x_labels))); ax.set_xticklabels(x_labels, fontsize=8)
    ax.set_yticks(range(len(y_labels))); ax.set_yticklabels(y_labels, fontsize=8)
    ax.set_xlabel(x_lbl); ax.set_ylabel(y_lbl)
    ax.set_title(title, fontweight='bold', fontsize=9)
    for ri in range(mat.shape[0]):
        for ci in range(mat.shape[1]):
            v = mat[ri, ci]
            if not np.isnan(v):
                ax.text(ci, ri, f'{v:.2f}', ha='center', va='center', fontsize=5.5,
                        color='black' if v > np.nanmax(mat)*0.4 else 'white')
    plt.colorbar(im, ax=ax, label='Composite score')

plt.suptitle('Stage 2b — ATR Trailing Stop Grid: Composite Score Heatmaps', fontweight='bold')
plt.tight_layout()
hm_path = os.path.join(RESULTS_DIR, 'stage2b_heatmap.png')
plt.savefig(hm_path, dpi=150, bbox_inches='tight'); plt.close()
print(f"  Saved → {hm_path}")

# --- Equity curves: top 3 by composite ---
best_2b = df_2b.iloc[0]
top3_2b = df_2b.head(3)
cands_2b = []
for _, row in top3_2b.iterrows():
    sp, ap, am = int(row['sma_period']), int(row['atr_period']), row['atr_mult']
    lbl = (f"SMA {sp}/ATR {ap}/{am}x  "
           f"Comp {row['composite']:.3f}  Cal {row['calmar']:.3f}  "
           f"Sor {row['sortino']:.3f}  Ann {row['annual_return']:.1f}%  "
           f"DD {row['max_drawdown']:.1f}%")
    cands_2b.append((lbl, (lambda s=sp, a=ap, m=am:
                           run_sma_atr_trail(sma_cache[s], atr_cache[a], m))))

print("\n  Equity curves — top 3 Stage 2b by composite vs BTC B&H")
equity_curves_chart(
    cands_2b,
    'Stage 2b — Top 3 ATR Trail Candidates vs BTC Buy-and-Hold',
    'stage2b_equity_curves.png',
    df['Close'],
)

# ===========================================================================
# HEAD-TO-HEAD: Stage 2a best vs Stage 2b best
# ===========================================================================

print("\n" + "=" * 72)
print("HEAD-TO-HEAD — Best Stage 2a (pct trail) vs Best Stage 2b (ATR trail)")
print("=" * 72)
print(f"\n{'Candidate':<44}  {'Comp':>5}  {'Calmar':>7}  {'Sortino':>7}  "
      f"{'Ann%':>6}  {'MaxDD%':>7}  {'n':>3}  {'Stop%':>5}  {'Flag'}")
print("─" * 100)

for cname, row in [
    (f"2a best: SMA {int(best_overall_2a['sma_period'])} / "
     f"pct {best_overall_2a['trail_pct']:.2f}%", best_overall_2a),
    (f"2b best: SMA {int(best_2b['sma_period'])} / "
     f"ATR {int(best_2b['atr_period'])} / {best_2b['atr_mult']:.1f}x", best_2b),
]:
    flag = "[!low n]" if row.get('low_trades', False) else ""
    print(f"{cname:<44}  {row['composite']:>5.3f}  {row['calmar']:>7.3f}  "
          f"{row['sortino']:>7.3f}  {row['annual_return']:>6.1f}  "
          f"{row['max_drawdown']:>7.1f}  {int(row['total_trades']):>3}  "
          f"{row['stop_exit_pct']:>5.1f}  {flag}")

print(f"\n  Note: composite scores are normalised within each grid separately —")
print(f"  direct comparison of composite values across 2a vs 2b is not valid.")
print(f"  Compare on raw metrics: Calmar, Sortino, Ann%, MaxDD.")

# Combined equity curve: 2a best vs 2b best vs BTC B&H
s2a_sma   = int(best_overall_2a['sma_period'])
s2a_trail = best_overall_2a['trail_pct'] / 100.0
s2b_sma   = int(best_2b['sma_period'])
s2b_atr   = int(best_2b['atr_period'])
s2b_mult  = best_2b['atr_mult']

cands_h2h = [
    (f"2a: SMA {s2a_sma}/pct {s2a_trail*100:.1f}%  "
     f"Cal {best_overall_2a['calmar']:.3f}  Sor {best_overall_2a['sortino']:.3f}  "
     f"Ann {best_overall_2a['annual_return']:.1f}%  DD {best_overall_2a['max_drawdown']:.1f}%",
     lambda: run_sma_pct_trail(sma_cache[s2a_sma], s2a_trail)),
    (f"2b: SMA {s2b_sma}/ATR {s2b_atr}/{s2b_mult:.1f}x  "
     f"Cal {best_2b['calmar']:.3f}  Sor {best_2b['sortino']:.3f}  "
     f"Ann {best_2b['annual_return']:.1f}%  DD {best_2b['max_drawdown']:.1f}%",
     lambda: run_sma_atr_trail(sma_cache[s2b_sma], atr_cache[s2b_atr], s2b_mult)),
]
equity_curves_chart(
    cands_h2h,
    'Stage 2a vs 2b — Best Pct Trail vs Best ATR Trail vs BTC Buy-and-Hold',
    'stage2_2a_vs_2b.png',
    df['Close'],
)

print("\n[Stage 2a extension + Stage 2b complete — awaiting instruction to continue.]")
