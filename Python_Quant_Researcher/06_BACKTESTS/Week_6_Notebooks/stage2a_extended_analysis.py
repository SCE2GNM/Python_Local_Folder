# Stage 2a — Extended Analysis
# Reads stage2a_results.csv, re-runs backtests for selected candidates,
# produces charts and detailed breakdowns.

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
MIN_TRADES      = 5
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
print(f"  {df.index[0].date()} → {df.index[-1].date()} ({len(df)} bars)")

closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index
years  = (df.index[-1] - df.index[0]).days / 365.25

# ---------------------------------------------------------------------------
# Backtest: SMA pct trail (self-contained copy)
# ---------------------------------------------------------------------------

def run_sma_pct_trail(closes, lows, dates, sma_period, trail_pct):
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
        crossover = sig_cur and not sig_prev
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
        if position == 0 and crossover:
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
    equity = np.ones(n)
    portfolio = 1.0
    prev_i = 0
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
# Load results CSV
# ---------------------------------------------------------------------------

df_res = pd.read_csv(os.path.join(DATA_DIR, 'stage2a_results.csv'))
df_res = df_res.sort_values('calmar', ascending=False).reset_index(drop=True)
n_total = len(df_res)

# ===========================================================================
# 1. Full Top 20
# ===========================================================================

print("\n" + "=" * 80)
print("1. STAGE 2a — Top 20 results (ranked by Calmar)")
print("=" * 80)

H = (f"{'Rk':>2}  {'SMA':>4}  {'Trail%':>6}  {'Calmar':>7}  {'Sortino':>7}  "
     f"{'Ann%':>6}  {'MaxDD%':>7}  {'n':>3}  {'Win%':>5}  {'PF':>6}  {'Stop%':>5}")
print(H)
print("─" * len(H))
for rk, (_, row) in enumerate(df_res.head(20).iterrows(), 1):
    flag = " !" if row['low_trades'] else ""
    print(f"{rk:>2}  {int(row['sma_period']):>4}  {row['trail_pct']:>6.2f}  "
          f"{row['calmar']:>7.3f}  {row['sortino']:>7.3f}  "
          f"{row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  "
          f"{int(row['total_trades']):>3}  {row['win_rate']:>5.1f}  "
          f"{row['profit_factor']:>6.3f}  {row['stop_exit_pct']:>5.1f}{flag}")

# ===========================================================================
# 2. Bottom 5
# ===========================================================================

print("\n" + "=" * 80)
print("2. STAGE 2a — Bottom 5 results (lowest Calmar)")
print("=" * 80)

print(H)
print("─" * len(H))
for rk, (_, row) in enumerate(df_res.tail(5).iterrows(), n_total - 4):
    flag = " !" if row['low_trades'] else ""
    print(f"{rk:>2}  {int(row['sma_period']):>4}  {row['trail_pct']:>6.2f}  "
          f"{row['calmar']:>7.3f}  {row['sortino']:>7.3f}  "
          f"{row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  "
          f"{int(row['total_trades']):>3}  {row['win_rate']:>5.1f}  "
          f"{row['profit_factor']:>6.3f}  {row['stop_exit_pct']:>5.1f}{flag}")

# ===========================================================================
# 3. SMA 125 at every trail%
# ===========================================================================

print("\n" + "=" * 80)
print("3. SMA 125 — sensitivity to trail% (all values tested)")
print("=" * 80)

sma125 = df_res[df_res['sma_period'] == 125].sort_values('trail_pct')
H2 = (f"{'Trail%':>6}  {'Calmar':>7}  {'Sortino':>7}  {'Ann%':>6}  "
      f"{'MaxDD%':>7}  {'n':>3}  {'Win%':>5}  {'PF':>6}  {'Stop%':>5}")
print(H2)
print("─" * len(H2))
for _, row in sma125.iterrows():
    flag = " !" if row['low_trades'] else ""
    print(f"{row['trail_pct']:>6.2f}  {row['calmar']:>7.3f}  {row['sortino']:>7.3f}  "
          f"{row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  "
          f"{int(row['total_trades']):>3}  {row['win_rate']:>5.1f}  "
          f"{row['profit_factor']:>6.3f}  {row['stop_exit_pct']:>5.1f}{flag}")

# ===========================================================================
# 4. Heatmap
# ===========================================================================

print("\n4. Generating heatmap...")

sma_vals_uniq   = sorted(df_res['sma_period'].unique())
trail_vals_uniq = sorted(df_res['trail_pct'].unique())
heat_matrix = np.full((len(trail_vals_uniq), len(sma_vals_uniq)), np.nan)

for _, row in df_res.iterrows():
    ri = trail_vals_uniq.index(row['trail_pct'])
    ci = sma_vals_uniq.index(row['sma_period'])
    heat_matrix[ri, ci] = row['calmar']

fig, ax = plt.subplots(figsize=(13, 5))
im = ax.imshow(heat_matrix, aspect='auto', cmap='RdYlGn', origin='lower',
               vmin=0, vmax=heat_matrix[~np.isnan(heat_matrix)].max())

ax.set_xticks(range(len(sma_vals_uniq)))
ax.set_xticklabels([str(p) for p in sma_vals_uniq], rotation=45, ha='right', fontsize=8)
ax.set_yticks(range(len(trail_vals_uniq)))
ax.set_yticklabels([f"{t:.1f}%" for t in trail_vals_uniq], fontsize=8)
ax.set_xlabel('SMA Period')
ax.set_ylabel('Trail %')
ax.set_title('Stage 2a — Calmar Ratio Heatmap: SMA Period × Trail %\n'
             '(green = high Calmar, red = low Calmar)', fontweight='bold')

for ri in range(len(trail_vals_uniq)):
    for ci in range(len(sma_vals_uniq)):
        v = heat_matrix[ri, ci]
        if not np.isnan(v):
            ax.text(ci, ri, f'{v:.2f}', ha='center', va='center',
                    fontsize=6.5, color='black' if v > 0.5 else 'white')

plt.colorbar(im, ax=ax, label='Calmar Ratio')
plt.tight_layout()
heatmap_path = os.path.join(RESULTS_DIR, 'stage2a_heatmap.png')
plt.savefig(heatmap_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"   Saved → {heatmap_path}")

# ===========================================================================
# 5. Equity curve: Top 3 vs BTC Buy-and-Hold
# ===========================================================================

print("\n5. Building equity curves for top 3 candidates...")

top3 = df_res.head(3)
colors = ['#1565C0', '#2E7D32', '#E65100']

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9),
                                gridspec_kw={'height_ratios': [3, 1]})

bh_eq = closes / closes[0]
ax1.plot(dates, bh_eq, color='#BDBDBD', linewidth=1.2, label='BTC Buy-and-Hold', zorder=1)

for i, (_, row) in enumerate(top3.iterrows()):
    sma_p   = int(row['sma_period'])
    trail_p = row['trail_pct'] / 100.0
    trades  = run_sma_pct_trail(closes, lows, dates, sma_p, trail_p)
    df_t    = pd.DataFrame(trades)
    df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
    df_t['exit_date']  = pd.to_datetime(df_t['exit_date'])
    eq = build_daily_equity(df_t, df['Close'])
    lbl = f'SMA {sma_p} / {row["trail_pct"]:.1f}%  (Calmar {row["calmar"]:.3f})'
    ax1.plot(dates[:len(eq)], eq, color=colors[i], linewidth=1.5, label=lbl, zorder=i+2)
    pk = np.maximum.accumulate(eq)
    ax2.plot(dates[:len(eq)], (eq - pk) / pk * 100, color=colors[i], linewidth=1, alpha=0.8)

ax1.set_yscale('log')
ax1.set_ylabel('Portfolio value (log, start=1)')
ax1.set_title('Stage 2a — Top 3 Candidates vs BTC Buy-and-Hold', fontweight='bold')
ax1.legend(loc='upper left', fontsize=9)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f'{y:.1f}'))
ax1.grid(True, alpha=0.3)
ax2.axhline(0, color='black', linewidth=0.5)
ax2.set_ylabel('Drawdown (%)')
ax2.set_xlabel('Date')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
eq_path = os.path.join(RESULTS_DIR, 'stage2a_equity_curves.png')
plt.savefig(eq_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"   Saved → {eq_path}")

# ===========================================================================
# 6 & 7. Year-by-year + trade log for best candidate (SMA 145 / 20%)
# ===========================================================================

print("\n6 & 7. Detailed analysis — best candidate: SMA 145 / trail 20%")

best_sma   = 145
best_trail = 0.20
trades_best = run_sma_pct_trail(closes, lows, dates, best_sma, best_trail)
df_best = pd.DataFrame(trades_best)
df_best['entry_date'] = pd.to_datetime(df_best['entry_date'])
df_best['exit_date']  = pd.to_datetime(df_best['exit_date'])
df_best['return_net'] = df_best['return'] - COST_PER_TRADE
df_best['exit_year']  = df_best['exit_date'].dt.year
df_best['hold_days']  = (df_best['exit_date'] - df_best['entry_date']).dt.days

print("\n6. Year-by-year annual return (based on exit year)")
print("─" * 72)
H3 = (f"{'Year':>4}  {'Trades':>6}  {'Win%':>5}  {'Avg win':>8}  "
      f"{'Avg loss':>9}  {'Gross ret':>10}  {'Net ret':>9}  {'Note':}")
print(H3)
print("─" * 72)

for yr in sorted(df_best['exit_year'].unique()):
    grp = df_best[df_best['exit_year'] == yr]
    rets_net  = grp['return_net'].values
    rets_raw  = grp['return'].values
    wins      = rets_net[rets_net > 0]
    losses    = rets_net[rets_net <= 0]
    gross_ret = (1 + rets_raw).prod() - 1
    net_ret   = (1 + rets_net).prod() - 1
    win_pct   = len(wins) / len(rets_net) * 100
    avg_win   = wins.mean() * 100  if len(wins)   > 0 else 0.0
    avg_loss  = losses.mean() * 100 if len(losses) > 0 else 0.0
    note = "(partial)" if yr == df_best['exit_year'].max() else ""
    print(f"{yr:>4}  {len(grp):>6}  {win_pct:>5.1f}  {avg_win:>7.1f}%  "
          f"{avg_loss:>8.1f}%  {gross_ret*100:>9.1f}%  {net_ret*100:>8.1f}%  {note}")

print("\n7. Trade log summary per year")
print("─" * 60)
H4 = f"{'Year':>4}  {'Trades':>6}  {'Avg hold days':>13}  {'Avg win%':>9}  {'Avg loss%':>10}"
print(H4)
print("─" * 60)

for yr in sorted(df_best['exit_year'].unique()):
    grp  = df_best[df_best['exit_year'] == yr]
    rets = grp['return_net'].values
    wins  = rets[rets > 0]
    losses = rets[rets <= 0]
    avg_hold = grp['hold_days'].mean()
    avg_win  = wins.mean() * 100  if len(wins)   > 0 else float('nan')
    avg_loss = losses.mean() * 100 if len(losses) > 0 else float('nan')
    print(f"{yr:>4}  {len(grp):>6}  {avg_hold:>13.1f}  "
          f"{avg_win:>8.1f}%  {avg_loss:>9.1f}%")

# Overall summary
all_rets  = df_best['return_net'].values
all_wins  = all_rets[all_rets > 0]
all_losses = all_rets[all_rets <= 0]
print(f"\n  Full period totals:")
print(f"    Total trades:      {len(df_best)}")
print(f"    Avg hold (days):   {df_best['hold_days'].mean():.1f}")
print(f"    Avg win:           {all_wins.mean()*100:.1f}%"  if len(all_wins) > 0  else "    Avg win:  n/a")
print(f"    Avg loss:          {all_losses.mean()*100:.1f}%" if len(all_losses) > 0 else "    Avg loss: n/a")
print(f"    Stop exits:        {(df_best['exit_reason']=='TRAIL_STOP').sum()} "
      f"({(df_best['exit_reason']=='TRAIL_STOP').mean()*100:.1f}%)")
print(f"    SMA exits:         {(df_best['exit_reason']=='SMA_EXIT').sum()} "
      f"({(df_best['exit_reason']=='SMA_EXIT').mean()*100:.1f}%)")
print(f"    End-of-data:       {(df_best['exit_reason']=='END').sum()}")

# ===========================================================================
# 8. Grid coverage statistics
# ===========================================================================

print("\n" + "=" * 80)
print("8. Grid coverage statistics")
print("=" * 80)

n_above_15 = (df_res['calmar'] >= 1.5).sum()
n_above_20 = (df_res['calmar'] >= 2.0).sum()
pct_15 = n_above_15 / n_total * 100
pct_20 = n_above_20 / n_total * 100

print(f"\n  Total grid combinations tested:  {n_total}")
print(f"  Combinations with Calmar ≥ 1.5:  {n_above_15:>3}  ({pct_15:.1f}% of grid)")
print(f"  Combinations with Calmar ≥ 2.0:  {n_above_20:>3}  ({pct_20:.1f}% of grid)")
print(f"  Combinations with Calmar < 0:     {(df_res['calmar'] < 0).sum():>3}  "
      f"({(df_res['calmar'] < 0).sum()/n_total*100:.1f}% of grid)")

# Breakdown by trail%
print(f"\n  Calmar ≥ 1.5 breakdown by trail%:")
for t in sorted(df_res['trail_pct'].unique()):
    sub = df_res[df_res['trail_pct'] == t]
    n_p = (sub['calmar'] >= 1.5).sum()
    print(f"    trail {t:>5.2f}%:  {n_p}/{len(sub)} SMA values  ({n_p/len(sub)*100:.0f}%)")

print(f"\n  Calmar ≥ 1.5 breakdown by SMA period:")
for p in sorted(df_res['sma_period'].unique()):
    sub = df_res[df_res['sma_period'] == p]
    n_p = (sub['calmar'] >= 1.5).sum()
    bar = "█" * n_p
    print(f"    SMA {p:>4}:  {n_p}/{len(sub)} trail values  {bar}")

print("\n[Stage 2a extended analysis complete — awaiting instruction to continue.]")
