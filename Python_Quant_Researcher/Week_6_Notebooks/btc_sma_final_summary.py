# BTC SMA Final Summary — Equity Curve, Year-by-Year, Head-to-Head Table
# Week 6 — comparison of BTC SMA 120/25% vs BTC ADX 19/14 vs Buy-and-Hold
#
# Chart 1: Log-scale equity curves with trade markers and regime annotations
# Chart 2: Year-by-year returns bar chart (three strategies)
# Output:  Head-to-head metrics table + B&H relative threshold check

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
import yfinance as yf
from ta.trend import ADXIndicator
import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SMA_PERIOD  = 120
TRAIL_PCT   = 0.25
ADX_THRESH  = 19
ADX_PERIOD  = 14
FIXED_STOP  = 0.03
COST        = 0.00075 * 2       # 0.15% round-trip

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
os.makedirs(RESULTS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Backtests
# ---------------------------------------------------------------------------

def run_sma_pct_trail(closes, lows, dates, sma_vals, trail_pct):
    first_valid = int(np.argmax(~np.isnan(sma_vals)))
    pos = ep = pk = sp = 0.0
    trades = []
    sig_prev = False
    for i in range(first_valid, len(closes)):
        cl, lo, sv = closes[i], lows[i], sma_vals[i]
        if np.isnan(sv):
            continue
        sig_cur   = cl > sv
        crossover = sig_cur and not sig_prev
        if pos == 1:
            if cl > pk:
                pk = cl
                sp = pk * (1 - trail_pct)
            if lo <= sp:
                trades.append({'entry_date': dates[i-1] if i > 0 else dates[i],
                                'entry_date_i': i, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': sp,
                                'return': (sp - ep) / ep, 'exit_reason': 'TRAIL'})
                pos = ep = pk = sp = 0.0
            elif not sig_cur:
                trades.append({'entry_date': dates[i-1] if i > 0 else dates[i],
                                'entry_date_i': i, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'SMA'})
                pos = ep = pk = sp = 0.0
        if pos == 0 and crossover:
            pos = 1
            ep = pk = cl
            sp = cl * (1 - trail_pct)
            trades[-1]['entry_date'] = dates[i] if trades else dates[i]
            trades.append({'entry_date': dates[i], 'entry_date_i': i,
                           'entry_price': ep, 'exit_date': None,
                           'exit_price': None, 'return': None,
                           'exit_reason': None})
            trades.pop()  # placeholder added then removed — just track entry
            # Re-enter correctly:
            trades.append({'entry_date': dates[i], 'entry_date_i': i,
                           'entry_price': ep})
            ep_stored = ep
            sp_stored = sp
            pk_stored = pk
        sig_prev = sig_cur
    # Close any open position at end
    if pos == 1:
        trades.append({'entry_date': dates[i], 'entry_date_i': i,
                       'entry_price': ep, 'exit_date': dates[-1],
                       'exit_price': closes[-1],
                       'return': (closes[-1] - ep) / ep, 'exit_reason': 'EOD'})
    return trades


def run_fixed_stop(closes, lows, signals, dates, stop_pct):
    pos = ep = sp = 0.0
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sig = lows[i], closes[i], signals[i]
        if pos == 1:
            if lo <= sp:
                trades.append({'entry_date': dates[i-1], 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price': sp,
                                'return': (sp - ep) / ep, 'exit_reason': 'STOP'})
                pos = ep = sp = 0.0
            elif not sig:
                trades.append({'entry_date': dates[i-1], 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price': cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'ADX'})
                pos = ep = sp = 0.0
        elif pos == 0 and sig:
            ep = cl
            sp = cl * (1 - stop_pct)
            pos = 1
    return trades


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
        equity[ei:xi+1]    = portfolio * closes_a[ei:xi+1] / t['entry_price']
        portfolio          *= (1 + t['return'] - COST)
        equity[xi]          = portfolio
        prev_i              = xi + 1
    equity[prev_i:] = portfolio
    return equity


def dd_recovery_days(equity):
    peak     = np.maximum.accumulate(equity)
    dd_curve = (equity - peak) / peak
    worst_i  = np.argmin(dd_curve)
    # Find next time equity reaches the pre-drawdown peak
    pre_dd_peak = peak[worst_i]
    recovery_idx = np.where(equity[worst_i:] >= pre_dd_peak)[0]
    if len(recovery_idx) == 0:
        return None   # not recovered yet
    return recovery_idx[0]   # days from worst to recovery


def full_metrics(trades, close_series, years):
    df_t = pd.DataFrame(trades)
    if len(df_t) == 0:
        return {}
    rets  = df_t['return'].values - COST
    eq_pt = np.cumprod(1 + rets)
    pk_pt = np.maximum.accumulate(eq_pt)
    dd_pt = ((eq_pt - pk_pt) / pk_pt).min()
    ann   = (eq_pt[-1]) ** (1 / years) - 1
    cal   = ann / abs(dd_pt) if dd_pt != 0 else 0

    eq_full = build_daily_equity(df_t, close_series)
    dr      = np.diff(eq_full) / eq_full[:-1]
    dn      = dr[dr < 0]
    sortino = dr.mean() / dn.std() * np.sqrt(365) if len(dn) > 0 else 0
    pk_mtm  = np.maximum.accumulate(eq_full)
    dd_mtm  = ((eq_full - pk_mtm) / pk_mtm).min()
    rec_d   = dd_recovery_days(eq_full)

    win_r   = (rets > 0).mean()
    best_yr = worst_yr = post22_ann = yr22 = None
    df_t['exit_yr'] = pd.to_datetime(df_t['exit_date']).dt.year
    yy = {}
    for yr, grp in df_t.groupby('exit_yr'):
        r = np.cumprod(1 + grp['return'].values - COST)[-1] - 1
        yy[yr] = r
    if yy:
        best_yr  = max(yy, key=yy.get)
        worst_yr = min(yy, key=yy.get)
        yr22     = yy.get(2022, None)
        post22   = {k: v for k, v in yy.items() if k >= 2022}
        if post22:
            tot = np.prod([1 + v for v in post22.values()])
            n22 = len(post22)
            post22_ann = tot ** (1 / n22) - 1

    return {
        'n_trades': len(df_t), 'win_rate': win_r,
        'annual_return': ann, 'max_dd_trade': dd_pt, 'max_dd_mtm': dd_mtm,
        'calmar': cal, 'sortino': sortino,
        'best_year': best_yr, 'best_year_ret': yy.get(best_yr) if best_yr else None,
        'worst_year': worst_yr, 'worst_year_ret': yy.get(worst_yr) if worst_yr else None,
        'yr_2022': yr22, 'post22_ann': post22_ann,
        'recovery_days': rec_d, 'eq_full': eq_full, 'yy': yy,
    }


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

print("Fetching BTC-USD daily data...")
raw = yf.download('BTC-USD', start='2018-01-01', interval='1d',
                  progress=False, auto_adjust=True)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = raw[['Open', 'High', 'Low', 'Close']].dropna().copy()
df.index = pd.to_datetime(df.index)
years = (df.index[-1] - df.index[0]).days / 365.25
print(f"  BTC-USD: {df.index[0].date()} → {df.index[-1].date()} ({years:.1f} yrs)")

closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index


# ---------------------------------------------------------------------------
# BTC SMA 120/25% backtest
# ---------------------------------------------------------------------------

print(f"\nRunning BTC SMA {SMA_PERIOD}/{TRAIL_PCT*100:.0f}%...")
sma_vals = pd.Series(closes).rolling(SMA_PERIOD).mean().values
sig_prev = False
pos = ep = pk = sp = 0.0
sma_trades = []

first_valid = SMA_PERIOD - 1
for i in range(first_valid, len(closes)):
    cl, lo, sv = closes[i], lows[i], sma_vals[i]
    sig_cur   = cl > sv
    crossover = sig_cur and not sig_prev
    if pos == 1:
        if cl > pk:
            pk = cl
            sp = pk * (1 - TRAIL_PCT)
        if lo <= sp:
            sma_trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price': sp,
                                'return': (sp - ep) / ep, 'exit_reason': 'TRAIL'})
            pos = ep = pk = sp = 0.0
        elif not sig_cur:
            sma_trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i],   'exit_price': cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'SMA'})
            pos = ep = pk = sp = 0.0
    if pos == 0 and crossover:
        pos = 1
        ep = pk = cl
        sp = cl * (1 - TRAIL_PCT)
        entry_date = dates[i]
    sig_prev = sig_cur

if pos == 1:
    sma_trades.append({'entry_date': entry_date, 'entry_price': ep,
                       'exit_date': dates[-1], 'exit_price': closes[-1],
                       'return': (closes[-1] - ep) / ep, 'exit_reason': 'EOD'})

print(f"  {len(sma_trades)} trades")
sma_m = full_metrics(sma_trades, df['Close'], years)
sma_eq = sma_m['eq_full']


# ---------------------------------------------------------------------------
# BTC ADX 19/14 fixed 3% backtest
# ---------------------------------------------------------------------------

print(f"Running BTC ADX {ADX_THRESH}/{ADX_PERIOD} fixed {FIXED_STOP*100:.0f}%...")
adx_ind  = ADXIndicator(df['High'], df['Low'], df['Close'], window=ADX_PERIOD)
adx_vals = adx_ind.adx().values
di_pos   = adx_ind.adx_pos().values
di_neg   = adx_ind.adx_neg().values
sig_adx  = (adx_vals >= ADX_THRESH) & (di_pos > di_neg)

adx_trades = run_fixed_stop(closes, lows, sig_adx, dates, FIXED_STOP)
print(f"  {len(adx_trades)} trades")
adx_m  = full_metrics(adx_trades, df['Close'], years)
adx_eq = adx_m['eq_full']


# ---------------------------------------------------------------------------
# Buy-and-Hold
# ---------------------------------------------------------------------------

bh_eq  = closes / closes[0]
bh_ann = bh_eq[-1] ** (1 / years) - 1
bh_dr  = np.diff(bh_eq) / bh_eq[:-1]
bh_dn  = bh_dr[bh_dr < 0]
bh_sort = bh_dr.mean() / bh_dn.std() * np.sqrt(365) if len(bh_dn) > 0 else 0
bh_pk   = np.maximum.accumulate(bh_eq)
bh_dd   = ((bh_eq - bh_pk) / bh_pk).min()
bh_rec  = dd_recovery_days(bh_eq)

# B&H year-by-year
bh_yy = {}
for yr in sorted(df.index.year.unique()):
    yr_df = df[df.index.year == yr]
    if len(yr_df) < 2:
        continue
    bh_yy[yr] = yr_df['Close'].iloc[-1] / yr_df['Close'].iloc[0] - 1

print(f"  B&H: Ann {bh_ann*100:.1f}%, MaxDD {bh_dd*100:.1f}%, Sortino {bh_sort:.3f}")


# ===========================================================================
#  CHART 1 — Log-scale equity curves with annotations
# ===========================================================================

print("\nGenerating Chart 1 — Equity curve...")

fig1, (ax_eq, ax_dd) = plt.subplots(2, 1, figsize=(14, 9),
                                      gridspec_kw={'height_ratios': [3, 1]},
                                      sharex=True)
fig1.patch.set_facecolor('#0e1117')
for ax in (ax_eq, ax_dd):
    ax.set_facecolor('#0e1117')
    ax.spines[:].set_color('#333')
    ax.tick_params(colors='#aaa', labelsize=9)
    ax.yaxis.label.set_color('#aaa')
    ax.xaxis.label.set_color('#aaa')

# Equity curves
ax_eq.semilogy(dates, sma_eq,  color='#2196F3', lw=2.0, label=f'BTC SMA {SMA_PERIOD}/{TRAIL_PCT*100:.0f}%',  zorder=4)
ax_eq.semilogy(dates, adx_eq,  color='#FF9800', lw=1.8, label=f'BTC ADX {ADX_THRESH}/{ADX_PERIOD} fixed {FIXED_STOP*100:.0f}%', zorder=3)
ax_eq.semilogy(dates, bh_eq,   color='#666',   lw=1.4, ls='--', label='BTC Buy-and-Hold', zorder=2, alpha=0.8)

# Entry/exit markers for BTC SMA
df_sma_t = pd.DataFrame(sma_trades)
entry_dates = pd.to_datetime(df_sma_t['entry_date'])
exit_dates  = pd.to_datetime(df_sma_t['exit_date'])
entry_idx   = [df.index.get_indexer([d], method='nearest')[0] for d in entry_dates]
exit_idx    = [df.index.get_indexer([d], method='nearest')[0] for d in exit_dates]
ax_eq.scatter([dates[i] for i in entry_idx], [sma_eq[i] for i in entry_idx],
              marker='^', color='#4CAF50', s=50, zorder=6, label='SMA entry', alpha=0.85)
ax_eq.scatter([dates[i] for i in exit_idx],  [sma_eq[i] for i in exit_idx],
              marker='v', color='#F44336', s=50, zorder=6, label='SMA exit',  alpha=0.85)

# Regime annotations
ax_eq.axvspan(pd.Timestamp('2021-01-01'), pd.Timestamp('2021-11-10'),
              alpha=0.07, color='#4CAF50', zorder=1)
ax_eq.text(pd.Timestamp('2021-04-01'), ax_eq.get_ylim()[0] if ax_eq.get_ylim()[0] > 0 else 1.0,
           '2021\nBull', color='#4CAF50', fontsize=8, ha='center', va='bottom',
           transform=ax_eq.transData)
ax_eq.axvspan(pd.Timestamp('2022-01-01'), pd.Timestamp('2022-12-31'),
              alpha=0.07, color='#F44336', zorder=1)
ax_eq.text(pd.Timestamp('2022-07-01'), 0.8,
           '2022\nBear', color='#F44336', fontsize=8, ha='center', va='center',
           transform=ax_eq.transData)

ax_eq.set_ylabel('Portfolio value (log, starts=1.0)', color='#aaa', fontsize=10)
ax_eq.legend(fontsize=9, loc='upper left', facecolor='#1a1a2e', labelcolor='white',
             framealpha=0.8)
ax_eq.set_title(f'BTC SMA {SMA_PERIOD}/{TRAIL_PCT*100:.0f}% vs ADX {ADX_THRESH}/{ADX_PERIOD} vs Buy-and-Hold\n'
                f'2018 – 2026  |  0.15% round-trip costs  |  Log scale',
                color='white', fontsize=12, pad=10)

# Add final value annotations
for eq, col, label in [(sma_eq, '#2196F3', f'SMA: {sma_eq[-1]:.1f}x'),
                        (adx_eq, '#FF9800', f'ADX: {adx_eq[-1]:.1f}x'),
                        (bh_eq,  '#888',    f'B&H: {bh_eq[-1]:.1f}x')]:
    ax_eq.annotate(label, xy=(dates[-1], eq[-1]), xycoords='data',
                   color=col, fontsize=8.5, ha='left',
                   xytext=(5, 0), textcoords='offset points')

# Drawdown chart
dd_sma = np.minimum.accumulate(sma_eq / np.maximum.accumulate(sma_eq)) - 1
dd_adx = np.minimum.accumulate(adx_eq / np.maximum.accumulate(adx_eq)) - 1
dd_bh  = np.minimum.accumulate(bh_eq  / np.maximum.accumulate(bh_eq))  - 1

# Fix drawdown calculation
pk_sma = np.maximum.accumulate(sma_eq)
pk_adx = np.maximum.accumulate(adx_eq)
pk_bh  = np.maximum.accumulate(bh_eq)
dd_sma = (sma_eq - pk_sma) / pk_sma
dd_adx = (adx_eq - pk_adx) / pk_adx
dd_bh  = (bh_eq  - pk_bh)  / pk_bh

ax_dd.fill_between(dates, dd_sma * 100, 0, color='#2196F3', alpha=0.35, label='SMA')
ax_dd.fill_between(dates, dd_adx * 100, 0, color='#FF9800', alpha=0.25, label='ADX')
ax_dd.plot(dates, dd_bh * 100, color='#666', lw=1, ls='--', alpha=0.7, label='B&H')
ax_dd.set_ylabel('Drawdown %', color='#aaa', fontsize=9)
ax_dd.set_xlabel('Date', color='#aaa', fontsize=10)
ax_dd.legend(fontsize=8, loc='lower left', facecolor='#1a1a2e', labelcolor='white',
             framealpha=0.8)
ax_dd.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.0f}%'))

# Regime shade on dd panel too
ax_dd.axvspan(pd.Timestamp('2021-01-01'), pd.Timestamp('2021-11-10'),
              alpha=0.07, color='#4CAF50')
ax_dd.axvspan(pd.Timestamp('2022-01-01'), pd.Timestamp('2022-12-31'),
              alpha=0.07, color='#F44336')

plt.tight_layout(rect=[0, 0, 0.97, 1])
out1 = os.path.join(RESULTS_DIR, 'btc_final_equity_curve.png')
plt.savefig(out1, dpi=140, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"  Saved → results/btc_final_equity_curve.png")


# ===========================================================================
#  CHART 2 — Year-by-year returns bar chart
# ===========================================================================

print("Generating Chart 2 — Year-by-year returns...")

all_years = sorted(set(list(sma_m['yy'].keys()) +
                       list(adx_m['yy'].keys()) +
                       list(bh_yy.keys())))

x     = np.arange(len(all_years))
width = 0.26

fig2, ax2 = plt.subplots(figsize=(15, 7))
fig2.patch.set_facecolor('#0e1117')
ax2.set_facecolor('#0e1117')
ax2.spines[:].set_color('#333')
ax2.tick_params(colors='#aaa', labelsize=9)

for offset, yy_dict, color_pos, color_neg, lbl in [
    (-width,    sma_m['yy'],    '#1565C0', '#B71C1C', f'SMA {SMA_PERIOD}/{TRAIL_PCT*100:.0f}%'),
    (0,         adx_m['yy'],    '#E65100', '#880E4F', f'ADX {ADX_THRESH}/{ADX_PERIOD} fixed {FIXED_STOP*100:.0f}%'),
    (+width,    bh_yy,          '#2E7D32', '#4A148C', 'B&H'),
]:
    vals   = [yy_dict.get(yr, 0) * 100 for yr in all_years]
    colors = [color_pos if v >= 0 else color_neg for v in vals]
    bars   = ax2.bar(x + offset, vals, width, color=colors, alpha=0.88, label=lbl)
    for bar, val in zip(bars, vals):
        if abs(val) > 3:
            ax2.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + (2 if val >= 0 else -4),
                     f'{val:.0f}%',
                     ha='center', va='bottom' if val >= 0 else 'top',
                     fontsize=6.5, color='#ddd', rotation=90)

ax2.axhline(0, color='#555', lw=1)
ax2.set_xticks(x)
ax2.set_xticklabels(all_years, color='#aaa')
ax2.set_ylabel('Annual Return %', color='#aaa', fontsize=11)
ax2.set_title(f'BTC SMA {SMA_PERIOD}/{TRAIL_PCT*100:.0f}% vs ADX {ADX_THRESH}/{ADX_PERIOD} vs B&H — Year-by-Year Returns\n'
              f'Dark = negative  |  0.15% round-trip costs applied to strategies',
              color='white', fontsize=12)

# Custom legend
patches = [
    mpatches.Patch(color='#1565C0', label=f'SMA {SMA_PERIOD}/{TRAIL_PCT*100:.0f}% (positive)'),
    mpatches.Patch(color='#B71C1C', label=f'SMA (negative)'),
    mpatches.Patch(color='#E65100', label=f'ADX {ADX_THRESH}/{ADX_PERIOD} (positive)'),
    mpatches.Patch(color='#880E4F', label=f'ADX (negative)'),
    mpatches.Patch(color='#2E7D32', label='B&H (positive)'),
    mpatches.Patch(color='#4A148C', label='B&H (negative)'),
]
ax2.legend(handles=patches, fontsize=8, loc='upper left',
           facecolor='#1a1a2e', labelcolor='white', framealpha=0.8,
           ncol=3, columnspacing=1)

ax2.yaxis.label.set_color('#aaa')
plt.tight_layout()
out2 = os.path.join(RESULTS_DIR, 'btc_year_by_year.png')
plt.savefig(out2, dpi=140, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"  Saved → results/btc_year_by_year.png")


# ===========================================================================
#  HEAD-TO-HEAD METRICS TABLE
# ===========================================================================

def fmt_pct(v):
    return f'{v*100:.1f}%' if v is not None else '—'

def fmt_yr(yr, ret):
    return f'{yr} ({ret*100:.0f}%)' if yr is not None and ret is not None else '—'

def fmt_rec(days, close_series_len):
    if days is None:
        return 'Not recovered'
    if days < 60:
        return f'{days}d'
    return f'~{days//30}mo'

bh_rec_fmt  = fmt_rec(bh_rec, len(df))
sma_rec_fmt = fmt_rec(sma_m['recovery_days'], len(df))
adx_rec_fmt = fmt_rec(adx_m['recovery_days'], len(df))

sma_post22 = sma_m['post22_ann']
adx_post22 = adx_m['post22_ann']

# B&H post-2022
bh_post22_vals = {k: v for k, v in bh_yy.items() if k >= 2022}
if bh_post22_vals:
    tot_bh22 = np.prod([1 + v for v in bh_post22_vals.values()])
    n_bh22 = len(bh_post22_vals)
    bh_post22 = tot_bh22 ** (1 / n_bh22) - 1
else:
    bh_post22 = None

print("\n" + "=" * 74)
print("HEAD-TO-HEAD METRICS — BTC SMA 120/25% vs BTC ADX 19/14 vs Buy-and-Hold")
print("=" * 74)

rows = [
    ('Annual return %',        fmt_pct(sma_m['annual_return']),
                               fmt_pct(adx_m['annual_return']),
                               fmt_pct(bh_ann)),
    ('MaxDD (per-trade) %',    fmt_pct(sma_m['max_dd_trade']),
                               fmt_pct(adx_m['max_dd_trade']),
                               '—'),
    ('MaxDD (daily MtM) %',    fmt_pct(sma_m['max_dd_mtm']),
                               fmt_pct(adx_m['max_dd_mtm']),
                               fmt_pct(bh_dd)),
    ('Sortino',                f"{sma_m['sortino']:.3f}",
                               f"{adx_m['sortino']:.3f}",
                               f"{bh_sort:.3f}"),
    ('Calmar',                 f"{sma_m['calmar']:.3f}",
                               f"{adx_m['calmar']:.3f}",
                               f"{bh_ann/abs(bh_dd):.3f}"),
    ('Trades (total)',         str(sma_m['n_trades']),
                               str(adx_m['n_trades']),
                               'continuous'),
    ('Win rate %',             fmt_pct(sma_m['win_rate']),
                               fmt_pct(adx_m['win_rate']),
                               '—'),
    ('Best year',              fmt_yr(sma_m['best_year'],  sma_m['best_year_ret']),
                               fmt_yr(adx_m['best_year'],  adx_m['best_year_ret']),
                               fmt_yr(max(bh_yy, key=bh_yy.get), bh_yy[max(bh_yy, key=bh_yy.get)])),
    ('Worst year',             fmt_yr(sma_m['worst_year'], sma_m['worst_year_ret']),
                               fmt_yr(adx_m['worst_year'], adx_m['worst_year_ret']),
                               fmt_yr(min(bh_yy, key=bh_yy.get), bh_yy[min(bh_yy, key=bh_yy.get)])),
    ('2022 return %',          fmt_pct(sma_m['yr_2022']),
                               fmt_pct(adx_m['yr_2022']),
                               fmt_pct(bh_yy.get(2022))),
    ('Post-2022 annual %',     fmt_pct(sma_post22),
                               fmt_pct(adx_post22),
                               fmt_pct(bh_post22)),
    ('Recovery from worst DD', sma_rec_fmt, adx_rec_fmt, bh_rec_fmt),
]

print(f"  {'Metric':<28} {'BTC SMA 120/25%':>17} {'BTC ADX 19/14':>15} {'BTC B&H':>12}")
print(f"  {'-'*72}")
for m, s, a, b in rows:
    print(f"  {m:<28} {s:>17} {a:>15} {b:>12}")

# ===========================================================================
#  B&H RELATIVE THRESHOLD CHECK
# ===========================================================================

print(f"\n" + "=" * 74)
print("B&H RELATIVE THRESHOLD CHECK — BTC SMA 120/25%")
print("=" * 74)

ann_mult   = sma_m['annual_return'] / bh_ann if bh_ann > 0 else None
mdd_frac   = sma_m['max_dd_mtm']   / bh_dd                        # both negative
sort_mult  = sma_m['sortino']      / bh_sort if bh_sort > 0 else None

ann_pass   = ann_mult  >= 2.0 if ann_mult  is not None else False
mdd_pass   = mdd_frac  <= 0.5                                      # closer to 0 = smaller = better
sort_pass  = sort_mult >= 1.5 if sort_mult is not None else False

print(f"\n  Annual return:  SMA {sma_m['annual_return']*100:.1f}% / B&H {bh_ann*100:.1f}% "
      f"= {ann_mult:.2f}x  (target ≥ 2.0x) → {'✓ PASS' if ann_pass else '✗ FAIL'}")
print(f"  MaxDD (MtM):    SMA {sma_m['max_dd_mtm']*100:.1f}% / B&H {bh_dd*100:.1f}% "
      f"= {mdd_frac:.2f}  (target ≤ 0.50) → {'✓ PASS' if mdd_pass else '✗ FAIL'}")
print(f"  Sortino:        SMA {sma_m['sortino']:.3f} / B&H {bh_sort:.3f} "
      f"= {sort_mult:.2f}x  (target ≥ 1.5x) → {'✓ PASS' if sort_pass else '✗ FAIL'}")

all_pass = ann_pass and mdd_pass and sort_pass
print(f"\n  Overall: {'✓ BTC SMA 120/25% passes all three B&H relative thresholds.' if all_pass else '✗ BTC SMA 120/25% does NOT pass all three B&H relative thresholds.'}")
if not all_pass:
    fails = []
    if not ann_pass:  fails.append(f"Annual return {ann_mult:.2f}x < 2.0x target")
    if not mdd_pass:  fails.append(f"MaxDD ratio {mdd_frac:.2f} > 0.50 target")
    if not sort_pass: fails.append(f"Sortino {sort_mult:.2f}x < 1.5x target")
    for f in fails:
        print(f"  Failing: {f}")

print(f"\n  KEY NUMBERS FOR RISK REGISTER:")
print(f"  SMA MaxDD (daily MtM): {sma_m['max_dd_mtm']*100:.1f}%")
print(f"  B&H MaxDD (daily MtM): {bh_dd*100:.1f}%")
print(f"  SMA MaxDD recovery:    {sma_rec_fmt}")
print(f"  B&H MaxDD recovery:    {bh_rec_fmt}")
print(f"  SMA 2022 return:       {fmt_pct(sma_m['yr_2022'])}")
print(f"  SMA best year:         {fmt_yr(sma_m['best_year'], sma_m['best_year_ret'])}")
print(f"  SMA post-2022 ann:     {fmt_pct(sma_post22)}")
print()
