# Stage 2a — Full Re-analysis with Composite Scoring
#
# Composite score = equal-weight average of 4 min-max normalised metrics:
#   1. Calmar ratio       (higher is better)
#   2. Sortino ratio      (higher is better)
#   3. Annual return %    (higher is better)
#   4. Max drawdown %     (less negative is better → inverted)
#
# All normalised to [0, 1] across the full 133-combo grid.
# Ranking and charts use composite score, not single-metric Calmar.

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import yfinance as yf

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')

COST_PER_TRADE  = 0.00075 * 2
LOW_TRADES_FLAG = 30

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
lows   = df['Low'].values.astype(float)
dates  = df.index
years  = (df.index[-1] - df.index[0]).days / 365.25
print(f"  {df.index[0].date()} → {df.index[-1].date()} ({len(df)} bars)")

# ---------------------------------------------------------------------------
# Backtest (self-contained)
# ---------------------------------------------------------------------------

def run_sma_pct_trail(sma_period, trail_pct):
    sma_vals = pd.Series(closes).rolling(sma_period, min_periods=sma_period).mean().values
    first_valid = int(np.argmax(~np.isnan(sma_vals)))
    position = entry_i = 0
    entry_price = peak_price = stop_price = 0.0
    trades = []
    sig_prev = False
    for i in range(first_valid, len(closes)):
        close, low, sma_val = closes[i], lows[i], sma_vals[i]
        if np.isnan(sma_val):
            continue
        sig_cur = close > sma_val
        if position == 1:
            if close > peak_price:
                peak_price = close
                stop_price = peak_price * (1 - trail_pct)
            if low <= stop_price:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': stop_price,
                               'return': (stop_price - entry_price) / entry_price,
                               'exit_reason': 'TRAIL_STOP'})
                position = 0
            elif not sig_cur:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': close,
                               'return': (close - entry_price) / entry_price,
                               'exit_reason': 'SMA_EXIT'})
                position = 0
        if position == 0 and sig_cur and not sig_prev:
            position = 1; entry_i = i; entry_price = close
            peak_price = close; stop_price = close * (1 - trail_pct)
        sig_prev = sig_cur
    if position == 1:
        trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                       'exit_date': dates[-1], 'exit_price': closes[-1],
                       'return': (closes[-1] - entry_price) / entry_price,
                       'exit_reason': 'END'})
    return trades


def build_daily_equity(trades_df, close_series):
    n = len(close_series)
    closes_arr = close_series.values
    date_to_i = pd.Series(np.arange(n), index=close_series.index)
    equity = np.ones(n); portfolio = 1.0; prev_i = 0
    for _, trade in trades_df.iterrows():
        ei = date_to_i.get(pd.Timestamp(trade['entry_date']))
        xi = date_to_i.get(pd.Timestamp(trade['exit_date']))
        if ei is None or xi is None:
            continue
        equity[prev_i:ei] = portfolio
        equity[ei:xi+1]   = portfolio * closes_arr[ei:xi+1] / trade['entry_price']
        portfolio         *= (1 + trade['return'] - COST_PER_TRADE)
        equity[xi]         = portfolio
        prev_i             = xi + 1
    equity[prev_i:] = portfolio
    return equity

# ---------------------------------------------------------------------------
# Load and augment results
# ---------------------------------------------------------------------------

df_res = pd.read_csv(os.path.join(DATA_DIR, 'stage2a_results.csv'))

# Min-max normalise each metric to [0,1] across all 133 combos
def minmax(series, invert=False):
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(0.5, index=series.index)
    normed = (series - lo) / (hi - lo)
    return 1 - normed if invert else normed

df_res['norm_calmar']  = minmax(df_res['calmar'])
df_res['norm_sortino'] = minmax(df_res['sortino'])
df_res['norm_annual']  = minmax(df_res['annual_return'])
# max_drawdown is all-negative. Less negative = better = higher raw value.
# Standard minmax already maps: most negative (worst) → 0, least negative (best) → 1. No invert.
df_res['norm_maxdd']   = minmax(df_res['max_drawdown'], invert=False)

df_res['composite'] = (
    df_res['norm_calmar'] +
    df_res['norm_sortino'] +
    df_res['norm_annual'] +
    df_res['norm_maxdd']
) / 4.0

df_comp = df_res.sort_values('composite', ascending=False).reset_index(drop=True)
df_cal  = df_res.sort_values('calmar',    ascending=False).reset_index(drop=True)
n_total = len(df_res)

# ===========================================================================
# HEADER
# ===========================================================================

print("\n" + "=" * 88)
print("STAGE 2a — Re-analysis with Composite Scoring")
print("Composite = equal-weight average of min-max normalised Calmar, Sortino,")
print("Annual Return, Max Drawdown (0=worst, 1=best across 133 combos)")
print("=" * 88)

# ===========================================================================
# 1. Top 20 by Composite Score
# ===========================================================================

print("\n--- Top 20: ranked by COMPOSITE score (all 4 metrics equally weighted) ---\n")
H = (f"{'Rk':>2}  {'SMA':>4}  {'Trail%':>6}  {'Comp':>5}  "
     f"{'Calmar':>7}  {'Sortino':>7}  {'Ann%':>6}  {'MaxDD%':>7}  "
     f"{'n':>3}  {'Win%':>5}  {'PF':>6}  {'Stop%':>5}")
print(H)
print("─" * len(H))
for rk, (_, row) in enumerate(df_comp.head(20).iterrows(), 1):
    flag = " !" if row['low_trades'] else ""
    # Show whether Calmar rank differs
    cal_rk = df_cal[df_cal['sma_period'] == row['sma_period']].index[
        df_cal[df_cal['sma_period'] == row['sma_period']]['trail_pct'] == row['trail_pct']
    ].tolist()
    cal_rk_val = cal_rk[0] + 1 if cal_rk else '?'
    rk_note = f"(C#{cal_rk_val})" if cal_rk_val != rk else ""
    print(f"{rk:>2}  {int(row['sma_period']):>4}  {row['trail_pct']:>6.2f}  "
          f"{row['composite']:>5.3f}  "
          f"{row['calmar']:>7.3f}  {row['sortino']:>7.3f}  "
          f"{row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  "
          f"{int(row['total_trades']):>3}  {row['win_rate']:>5.1f}  "
          f"{row['profit_factor']:>6.3f}  {row['stop_exit_pct']:>5.1f}{flag}  {rk_note}")

print("\n  Note: (C#N) = Calmar-only rank, shown where it differs from composite rank")
print("  ! = n < 30 trades (interpret with caution)")

# ===========================================================================
# 2. Bottom 5 by Composite Score
# ===========================================================================

print("\n--- Bottom 5: lowest composite score ---\n")
print(H)
print("─" * len(H))
for rk, (_, row) in enumerate(df_comp.tail(5).iterrows(), n_total - 4):
    flag = " !" if row['low_trades'] else ""
    print(f"{rk:>2}  {int(row['sma_period']):>4}  {row['trail_pct']:>6.2f}  "
          f"{row['composite']:>5.3f}  "
          f"{row['calmar']:>7.3f}  {row['sortino']:>7.3f}  "
          f"{row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  "
          f"{int(row['total_trades']):>3}  {row['win_rate']:>5.1f}  "
          f"{row['profit_factor']:>6.3f}  {row['stop_exit_pct']:>5.1f}{flag}")

# ===========================================================================
# 3. SMA 125 sensitivity — all trail% values, all 4 metrics
# ===========================================================================

print("\n--- SMA 125 sensitivity across all trail% values (composite score + 4 metrics) ---\n")
sma125 = df_res[df_res['sma_period'] == 125].sort_values('trail_pct')
H2 = (f"{'Trail%':>6}  {'Comp':>5}  {'Calmar':>7}  {'Sortino':>7}  "
      f"{'Ann%':>6}  {'MaxDD%':>7}  {'n':>3}  {'Win%':>5}  {'Stop%':>5}")
print(H2)
print("─" * len(H2))
for _, row in sma125.iterrows():
    flag = " !" if row['low_trades'] else ""
    print(f"{row['trail_pct']:>6.2f}  {row['composite']:>5.3f}  "
          f"{row['calmar']:>7.3f}  {row['sortino']:>7.3f}  "
          f"{row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  "
          f"{int(row['total_trades']):>3}  {row['win_rate']:>5.1f}  "
          f"{row['stop_exit_pct']:>5.1f}{flag}")

# ===========================================================================
# 4a. Heatmap: composite score
# ===========================================================================

print("\n4. Generating composite score heatmap...")

sma_uniq   = sorted(df_res['sma_period'].unique())
trail_uniq = sorted(df_res['trail_pct'].unique())
comp_matrix = np.full((len(trail_uniq), len(sma_uniq)), np.nan)
cal_matrix  = np.full((len(trail_uniq), len(sma_uniq)), np.nan)

for _, row in df_res.iterrows():
    ri = trail_uniq.index(row['trail_pct'])
    ci = sma_uniq.index(row['sma_period'])
    comp_matrix[ri, ci] = row['composite']
    cal_matrix[ri, ci]  = row['calmar']

fig, axes = plt.subplots(1, 2, figsize=(18, 5))

for ax, matrix, title, cmap in [
    (axes[0], comp_matrix, 'Composite Score (Calmar+Sortino+Ann%+MaxDD equally weighted)', 'RdYlGn'),
    (axes[1], cal_matrix,  'Calmar Ratio (for reference)',                                  'RdYlGn'),
]:
    im = ax.imshow(matrix, aspect='auto', cmap=cmap, origin='lower',
                   vmin=0, vmax=np.nanmax(matrix))
    ax.set_xticks(range(len(sma_uniq)))
    ax.set_xticklabels([str(p) for p in sma_uniq], rotation=45, ha='right', fontsize=7.5)
    ax.set_yticks(range(len(trail_uniq)))
    ax.set_yticklabels([f"{t:.1f}%" for t in trail_uniq], fontsize=8)
    ax.set_xlabel('SMA Period')
    ax.set_ylabel('Trail %')
    ax.set_title(title, fontweight='bold', fontsize=9)
    for ri in range(len(trail_uniq)):
        for ci in range(len(sma_uniq)):
            v = matrix[ri, ci]
            if not np.isnan(v):
                ax.text(ci, ri, f'{v:.2f}', ha='center', va='center',
                        fontsize=6, color='black' if v > np.nanmax(matrix)*0.4 else 'white')
    plt.colorbar(im, ax=ax)

plt.suptitle('Stage 2a — SMA × Trail%: Composite Score vs Calmar', fontweight='bold', fontsize=11)
plt.tight_layout()
hm_path = os.path.join(RESULTS_DIR, 'stage2a_heatmap_composite.png')
plt.savefig(hm_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"   Saved → {hm_path}")

# ===========================================================================
# 5. Equity curves: top 3 by composite score + BTC B&H
# ===========================================================================

print("\n5. Building equity curves — top 3 by composite score vs BTC Buy-and-Hold...")

top3 = df_comp.head(3)
colors_top = ['#1565C0', '#2E7D32', '#E65100']

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9),
                                gridspec_kw={'height_ratios': [3, 1]})

bh_eq = closes / closes[0]
ax1.plot(dates, bh_eq, color='#BDBDBD', linewidth=1.2, label='BTC Buy-and-Hold', zorder=1)

eq_curves = {}
for i, (_, row) in enumerate(top3.iterrows()):
    sma_p   = int(row['sma_period'])
    trail_p = row['trail_pct'] / 100.0
    trades  = run_sma_pct_trail(sma_p, trail_p)
    df_t    = pd.DataFrame(trades)
    df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
    df_t['exit_date']  = pd.to_datetime(df_t['exit_date'])
    eq = build_daily_equity(df_t, df['Close'])
    eq_curves[i] = eq
    lbl = (f"SMA {sma_p} / {row['trail_pct']:.1f}%  "
           f"[Comp {row['composite']:.3f}  Cal {row['calmar']:.3f}  "
           f"Sor {row['sortino']:.3f}  Ann {row['annual_return']:.1f}%  "
           f"DD {row['max_drawdown']:.1f}%]")
    ax1.plot(dates[:len(eq)], eq, color=colors_top[i], linewidth=1.5, label=lbl, zorder=i+2)
    pk = np.maximum.accumulate(eq)
    ax2.plot(dates[:len(eq)], (eq - pk) / pk * 100, color=colors_top[i], linewidth=1, alpha=0.8)

ax1.set_yscale('log')
ax1.set_ylabel('Portfolio value (log, start=1)')
ax1.set_title('Stage 2a — Top 3 by Composite Score vs BTC Buy-and-Hold',
              fontweight='bold')
ax1.legend(loc='upper left', fontsize=8)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f'{y:.1f}'))
ax1.grid(True, alpha=0.3)
ax2.axhline(0, color='black', linewidth=0.5)
ax2.set_ylabel('Drawdown (%)')
ax2.set_xlabel('Date')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
eq_path = os.path.join(RESULTS_DIR, 'stage2a_equity_composite.png')
plt.savefig(eq_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"   Saved → {eq_path}")

# ===========================================================================
# 6 & 7. Year-by-year + trade log — composite score winner
# ===========================================================================

best_row = df_comp.iloc[0]
best_sma   = int(best_row['sma_period'])
best_trail = best_row['trail_pct'] / 100.0

print(f"\n6 & 7. Detailed breakdown — composite score winner: "
      f"SMA {best_sma} / trail {best_row['trail_pct']:.2f}%")
print(f"   Composite {best_row['composite']:.3f}  |  Calmar {best_row['calmar']:.3f}  "
      f"|  Sortino {best_row['sortino']:.3f}  |  Ann {best_row['annual_return']:.1f}%  "
      f"|  MaxDD {best_row['max_drawdown']:.1f}%")

trades_best = run_sma_pct_trail(best_sma, best_trail)
df_best = pd.DataFrame(trades_best)
df_best['entry_date'] = pd.to_datetime(df_best['entry_date'])
df_best['exit_date']  = pd.to_datetime(df_best['exit_date'])
df_best['return_net'] = df_best['return'] - COST_PER_TRADE
df_best['exit_year']  = df_best['exit_date'].dt.year
df_best['hold_days']  = (df_best['exit_date'] - df_best['entry_date']).dt.days

print("\n  6. Year-by-year breakdown (based on exit year):")
H3 = (f"  {'Year':>4}  {'n':>3}  {'Win%':>5}  {'Avg win':>8}  "
      f"{'Avg loss':>9}  {'Net ret':>8}  {'Note':}")
print(H3); print("  " + "─" * (len(H3) - 2))
for yr in sorted(df_best['exit_year'].unique()):
    grp  = df_best[df_best['exit_year'] == yr]
    rets = grp['return_net'].values
    wins   = rets[rets > 0]
    losses = rets[rets <= 0]
    net_ret = (1 + rets).prod() - 1
    win_pct = len(wins) / len(rets) * 100
    avg_win  = wins.mean()   * 100 if len(wins)   > 0 else float('nan')
    avg_loss = losses.mean() * 100 if len(losses) > 0 else float('nan')
    note = "(partial)" if yr == df_best['exit_year'].max() else ""
    w_str = f"{avg_win:>7.1f}%" if not np.isnan(avg_win)  else "    n/a"
    l_str = f"{avg_loss:>8.1f}%" if not np.isnan(avg_loss) else "     n/a"
    print(f"  {yr:>4}  {len(grp):>3}  {win_pct:>5.1f}  {w_str}  {l_str}  "
          f"{net_ret*100:>7.1f}%  {note}")

print(f"\n  7. Trade log summary (per exit year):")
H4 = f"  {'Year':>4}  {'n':>3}  {'Avg hold (days)':>16}  {'Avg win':>8}  {'Avg loss':>9}"
print(H4); print("  " + "─" * (len(H4) - 2))
for yr in sorted(df_best['exit_year'].unique()):
    grp  = df_best[df_best['exit_year'] == yr]
    rets = grp['return_net'].values
    wins   = rets[rets > 0]
    losses = rets[rets <= 0]
    avg_win  = wins.mean()   * 100 if len(wins)   > 0 else float('nan')
    avg_loss = losses.mean() * 100 if len(losses) > 0 else float('nan')
    w_str = f"{avg_win:>7.1f}%" if not np.isnan(avg_win)  else "    n/a"
    l_str = f"{avg_loss:>8.1f}%" if not np.isnan(avg_loss) else "     n/a"
    print(f"  {yr:>4}  {len(grp):>3}  {grp['hold_days'].mean():>16.1f}  {w_str}  {l_str}")

all_rets = df_best['return_net'].values
all_wins  = all_rets[all_rets > 0]
all_loss  = all_rets[all_rets <= 0]
stop_n  = (df_best['exit_reason'] == 'TRAIL_STOP').sum()
sma_n   = (df_best['exit_reason'] == 'SMA_EXIT').sum()
end_n   = (df_best['exit_reason'] == 'END').sum()

print(f"\n  Full-period totals:")
print(f"    Trades:       {len(df_best)}"
      + (" [!low n]" if len(df_best) < LOW_TRADES_FLAG else ""))
print(f"    Avg hold:     {df_best['hold_days'].mean():.1f} days")
print(f"    Avg win:      {all_wins.mean()*100:.1f}%  (n={len(all_wins)})")
print(f"    Avg loss:     {all_loss.mean()*100:.1f}%  (n={len(all_loss)})")
print(f"    Trail exits:  {stop_n} ({stop_n/len(df_best)*100:.1f}%)")
print(f"    SMA exits:    {sma_n} ({sma_n/len(df_best)*100:.1f}%)")
print(f"    End-of-data:  {end_n}")

# Also show Calmar-only winner if different from composite winner
cal_best = df_cal.iloc[0]
if int(cal_best['sma_period']) != best_sma or cal_best['trail_pct'] != best_row['trail_pct']:
    print(f"\n  [Note: Calmar-only winner differs from composite winner]")
    print(f"    Calmar winner:    SMA {int(cal_best['sma_period'])} / {cal_best['trail_pct']:.2f}%  "
          f"→ Calmar {cal_best['calmar']:.3f}  Sortino {cal_best['sortino']:.3f}  "
          f"Ann {cal_best['annual_return']:.1f}%  MaxDD {cal_best['max_drawdown']:.1f}%  "
          f"Composite {cal_best['composite']:.3f}")
    print(f"    Composite winner: SMA {best_sma} / {best_row['trail_pct']:.2f}%  "
          f"→ Calmar {best_row['calmar']:.3f}  Sortino {best_row['sortino']:.3f}  "
          f"Ann {best_row['annual_return']:.1f}%  MaxDD {best_row['max_drawdown']:.1f}%  "
          f"Composite {best_row['composite']:.3f}")

# ===========================================================================
# 8. Grid coverage statistics
# ===========================================================================

print("\n" + "=" * 88)
print("8. Grid coverage — composite score and Calmar thresholds")
print("=" * 88)

print(f"\n  Total combos tested: {n_total}")

for label, col, thresh_list in [
    ("Composite score", "composite", [0.5, 0.6, 0.7]),
    ("Calmar",          "calmar",    [1.0, 1.5, 2.0]),
]:
    print(f"\n  {label} coverage:")
    for t in thresh_list:
        n_a = (df_res[col] >= t).sum()
        print(f"    ≥ {t:.1f}:  {n_a:>3} / {n_total}  ({n_a/n_total*100:.1f}%)")

print(f"\n  Composite ≥ 0.5 breakdown by trail%:")
for t in sorted(df_res['trail_pct'].unique()):
    sub = df_res[df_res['trail_pct'] == t]
    n_p = (sub['composite'] >= 0.5).sum()
    bar = "█" * n_p
    print(f"    trail {t:>5.2f}%:  {n_p}/{len(sub)}  {bar}")

print(f"\n  Composite ≥ 0.5 breakdown by SMA period:")
for p in sorted(df_res['sma_period'].unique()):
    sub = df_res[df_res['sma_period'] == p]
    n_p = (sub['composite'] >= 0.5).sum()
    bar = "█" * n_p
    print(f"    SMA {p:>4}:  {n_p}/{len(sub)}  {bar}")

# ===========================================================================
# Summary comparison table
# ===========================================================================

print("\n" + "=" * 88)
print("SUMMARY — Composite winner vs Calmar-only winner vs SMA 125 reference")
print("=" * 88)
print(f"\n{'Candidate':<36}  {'Comp':>5}  {'Calmar':>7}  {'Sortino':>7}  "
      f"{'Ann%':>6}  {'MaxDD%':>7}  {'n':>3}  {'Flag'}")
print("─" * 88)

candidates = [
    ('Composite winner', df_comp.iloc[0]),
]
if int(cal_best['sma_period']) != best_sma or cal_best['trail_pct'] != best_row['trail_pct']:
    candidates.append(('Calmar-only winner', df_cal.iloc[0]))

sma125_20 = df_res[(df_res['sma_period'] == 125) & (df_res['trail_pct'] == 20.0)]
if len(sma125_20) > 0:
    candidates.append(('SMA 125 / 20% (Week 5 reference SMA)', sma125_20.iloc[0]))

for cname, row in candidates:
    flag = "!low n" if row['low_trades'] else ""
    print(f"{cname:<36}  {row['composite']:>5.3f}  {row['calmar']:>7.3f}  "
          f"{row['sortino']:>7.3f}  {row['annual_return']:>6.1f}  "
          f"{row['max_drawdown']:>7.1f}  {int(row['total_trades']):>3}  {flag}")

print("\n[Stage 2a composite re-analysis complete — awaiting instruction to continue.]")
