# [MODULE] Day 3 - Joint Parameter Optimisation (Refined Grid)
# Week 5: Resolves A006 (ADX parameters not re-optimised with stop-loss)
#
# SECOND PASS — tighter grid around the best region found in pass 1:
#   Thresholds: 15-22 (step 1)
#   Periods:    8-14  (step 1)
#   Stops:      3-6%  (step 0.5%)
#
# Total combinations: 8 × 7 × 7 = 392

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from ta.trend import ADXIndicator
import os
from itertools import product

# ---------------------------------------------------------------------------
# [FUNCTION] Single backtest
# ---------------------------------------------------------------------------

def run_backtest(df: pd.DataFrame, threshold: int, period: int, stop_pct: float) -> dict:
    """
    [FUNCTION] Run one bar-by-bar backtest for a single parameter combination.

    Args:
        df        : OHLCV DataFrame (fetched once, reused for all combinations)
        threshold : ADX level to define trending regime
        period    : ADX lookback window
        stop_pct  : stop-loss as fraction of entry price

    Returns:
        dict of performance metrics, or None if fewer than 10 trades
    """

    # Recalculate ADX for this period
    adx_ind  = ADXIndicator(df['High'], df['Low'], df['Close'], window=period)
    adx      = adx_ind.adx()
    di_pos   = adx_ind.adx_pos()
    di_neg   = adx_ind.adx_neg()

    # Entry signal: trending AND bullish
    entry_signal = (adx >= threshold) & (di_pos > di_neg)

    # Bar-by-bar simulation
    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    closes  = df['Close'].values
    lows    = df['Low'].values
    signals = entry_signal.values

    for i in range(1, len(df)):
        low:    float = lows[i]
        close:  float = closes[i]
        signal: bool  = signals[i]

        if position == 1:
            if low <= stop_price:
                trades.append({
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'STOP_LOSS'
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            elif not signal:
                trades.append({
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'ADX_EXIT'
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and signal:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    if len(trades) < 10:
        return None

    trades_df = pd.DataFrame(trades)
    returns   = trades_df['return'].values

    winners = trades_df[trades_df['return'] > 0]
    losers  = trades_df[trades_df['return'] <= 0]

    win_rate      = len(winners) / len(trades_df)
    gross_profit  = winners['return'].sum() if len(winners) > 0 else 0.0
    gross_loss    = abs(losers['return'].sum()) if len(losers) > 0 else 1e-9
    profit_factor = gross_profit / gross_loss

    equity   = np.cumprod(1 + returns)
    peak     = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_dd   = drawdown.min()

    stop_exits = (trades_df['exit_reason'] == 'STOP_LOSS').sum()

    return {
        'threshold':      threshold,
        'period':         period,
        'stop_pct':       stop_pct,
        'total_trades':   len(trades_df),
        'win_rate':       win_rate,
        'avg_win':        winners['return'].mean() if len(winners) > 0 else 0.0,
        'avg_loss':       losers['return'].mean()  if len(losers)  > 0 else 0.0,
        'profit_factor':  profit_factor,
        'max_drawdown':   max_dd,
        'total_return':   (1 + returns).prod() - 1,
        'stop_exits_pct': stop_exits / len(trades_df),
    }


# ---------------------------------------------------------------------------
# FETCH DATA ONCE
# ---------------------------------------------------------------------------

print("\nFetching ETH-USD daily data...")
raw = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)

if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)

df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.dropna(inplace=True)
print(f"Data loaded: {df.index[0].date()} → {df.index[-1].date()} ({len(df):,} days)")


# ---------------------------------------------------------------------------
# DEFINE REFINED PARAMETER GRID
# ---------------------------------------------------------------------------

# Tighter grid centred on best region from pass 1
thresholds: list = [15, 16, 17, 18, 19, 20, 21, 22]
periods:    list = [8, 9, 10, 11, 12, 13, 14]
stops:      list = [0.030, 0.035, 0.040, 0.045, 0.050, 0.055, 0.060]

total = len(thresholds) * len(periods) * len(stops)
print(f"\nRefined grid: {len(thresholds)} thresholds × {len(periods)} periods × {len(stops)} stops")
print(f"Total combinations: {total}")
print(f"Running backtests — this will take a few minutes...\n")


# ---------------------------------------------------------------------------
# RUN GRID SEARCH
# ---------------------------------------------------------------------------

results: list = []
completed:  int = 0

for threshold, period, stop_pct in product(thresholds, periods, stops):
    result = run_backtest(df, threshold, period, stop_pct)
    if result is not None:
        results.append(result)
    completed += 1
    if completed % 50 == 0:
        print(f"  {completed}/{total} combinations tested...")

results_df = pd.DataFrame(results)
print(f"\nGrid search complete. {len(results_df)} valid combinations found.")


# ---------------------------------------------------------------------------
# RANK RESULTS
# ---------------------------------------------------------------------------

ranked = results_df.sort_values('profit_factor', ascending=False).reset_index(drop=True)

print(f"\n{'='*95}")
print(f"TOP 15 PARAMETER COMBINATIONS (ranked by profit factor)")
print(f"{'='*95}")
print(f"\n{'Rank':<5} {'Threshold':>10} {'Period':>8} {'Stop%':>7} {'Trades':>8} "
      f"{'Win Rate':>10} {'Profit Factor':>14} {'Max DD':>10} {'Stop Exits':>12}")
print(f"{'-'*95}")

for i, row in ranked.head(15).iterrows():
    # Mark live parameters with an arrow
    live = (row.threshold == 20 and row.period == 10 and row.stop_pct == 0.05)
    marker = ' ← LIVE' if live else ''
    print(f"  {i+1:<4} {int(row.threshold):>10} {int(row.period):>8} "
          f"{row.stop_pct*100:>6.1f}% {int(row.total_trades):>8} "
          f"{row.win_rate:>10.1%} {row.profit_factor:>14.3f} "
          f"{row.max_drawdown:>10.1%} {row.stop_exits_pct:>11.1%}{marker}")


# ---------------------------------------------------------------------------
# LIVE PARAMETER RANKING
# ---------------------------------------------------------------------------

live_row  = ranked[(ranked['threshold'] == 20) &
                   (ranked['period'] == 10) &
                   (ranked['stop_pct'] == 0.05)]
live_rank = live_row.index[0] + 1

print(f"\n{'='*95}")
print(f"YOUR LIVE PARAMETERS: ADX 20/10 with 5% stop")
print(f"{'='*95}")
print(f"  Rank:          {live_rank} of {len(results_df)}")
print(f"  Profit Factor: {live_row['profit_factor'].values[0]:.3f}")
print(f"  Win Rate:      {live_row['win_rate'].values[0]:.1%}")
print(f"  Max Drawdown:  {live_row['max_drawdown'].values[0]:.1%}")
print(f"  Stop Exits:    {live_row['stop_exits_pct'].values[0]:.1%} of trades")

best = ranked.iloc[0]
if live_rank <= 10:
    print(f"\n✅ VERDICT: Live parameters rank {live_rank} of {len(results_df)} — no change needed.")
elif live_rank <= 25:
    print(f"\n⚠️  VERDICT: Live parameters rank {live_rank} — acceptable, note best combo.")
else:
    print(f"\n❌ VERDICT: Live parameters rank {live_rank} — consider updating parameters.")

print(f"\n  Best combination found: ADX {int(best.threshold)}/{int(best.period)} "
      f"with {best.stop_pct*100:.1f}% stop "
      f"(profit factor: {best.profit_factor:.3f})")


# ---------------------------------------------------------------------------
# SAVE RESULTS CSV
# ---------------------------------------------------------------------------

os.makedirs('data', exist_ok=True)
ranked.to_csv('data/joint_optimisation_results_refined.csv', index=False)
print(f"\n✅ Full results saved → data/joint_optimisation_results_refined.csv")


# ---------------------------------------------------------------------------
# HEATMAPS — one per ADX period
# ---------------------------------------------------------------------------
# For each period value, produce a heatmap of profit factor
# with ADX threshold on Y axis and stop % on X axis.
# This lets you see the full 3D picture across all parameter values.

print(f"\nGenerating heatmaps...")

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

n_periods = len(periods)
fig, axes = plt.subplots(2, 4, figsize=(20, 10))
fig.suptitle('Joint Optimisation — Profit Factor Heatmaps by ADX Period (Week 5 Day 3)',
             fontsize=13, fontweight='bold')

# Colour scale fixed across all heatmaps for fair comparison
vmin = results_df['profit_factor'].min()
vmax = results_df['profit_factor'].max()

for idx, period in enumerate(periods):
    ax = axes[idx // 4][idx % 4]

    # Filter to this period
    period_data = results_df[results_df['period'] == period]

    # Pivot: rows = threshold, columns = stop_pct
    pivot = period_data.pivot_table(
        index='threshold',
        columns='stop_pct',
        values='profit_factor'
    )

    im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto',
                   vmin=vmin, vmax=vmax)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{int(c*100)}%" for c in pivot.columns], fontsize=7)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(int(t)) for t in pivot.index], fontsize=7)
    ax.set_xlabel('Stop %', fontsize=8)
    ax.set_ylabel('ADX Threshold', fontsize=8)
    ax.set_title(f'Period = {period}', fontsize=10, fontweight='bold')

    # Annotate cells
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                        fontsize=6, fontweight='bold')

    # Mark live parameters (period=10, threshold=20, stop=5%)
    if period == 10:
        if 20 in pivot.index and 0.05 in pivot.columns:
            t_idx = list(pivot.index).index(20)
            s_idx = list(pivot.columns).index(0.05)
            ax.add_patch(plt.Rectangle(
                (s_idx - 0.5, t_idx - 0.5), 1, 1,
                fill=False, edgecolor='blue', linewidth=3
            ))
            ax.set_title(f'Period = {period} ← LIVE', fontsize=10,
                        fontweight='bold', color='blue')

# Hide the unused 8th subplot (7 periods, 8 subplot slots)
axes[1][3].axis('off')

# Shared colourbar
fig.colorbar(im, ax=axes.ravel().tolist(), label='Profit Factor', shrink=0.6)

plt.tight_layout()
heatmap_path = 'Week_5_Notebooks/results/day3_heatmaps_all_periods.png'
plt.savefig(heatmap_path, dpi=150)
plt.close()
print(f"✅ Heatmaps saved → {heatmap_path}")

# ---------------------------------------------------------------------------
# TOP 10 BAR CHART
# ---------------------------------------------------------------------------

fig, ax = plt.subplots(figsize=(12, 7))
fig.suptitle('Top 15 Parameter Combinations by Profit Factor (Week 5 Day 3)',
             fontsize=13, fontweight='bold')

top15 = ranked.head(15).copy()
top15['label'] = top15.apply(
    lambda r: f"ADX{int(r.threshold)}/{int(r.period)} Stop{r.stop_pct*100:.1f}%", axis=1
)
colors = ['gold' if (r.threshold == 20 and r.period == 10 and r.stop_pct == 0.05)
          else 'steelblue' for _, r in top15.iterrows()]

ax.barh(range(len(top15)), top15['profit_factor'], color=colors)
ax.set_yticks(range(len(top15)))
ax.set_yticklabels(top15['label'], fontsize=9)
ax.invert_yaxis()
ax.set_xlabel('Profit Factor')
ax.set_title('Gold bar = your live parameters')
ax.axvline(1.0, color='red', linestyle='--', alpha=0.5, label='Break-even')
ax.grid(alpha=0.3, axis='x')
ax.legend()

plt.tight_layout()
bar_path = 'Week_5_Notebooks/results/day3_top15_bar.png'
plt.savefig(bar_path, dpi=150)
plt.close()
print(f"✅ Bar chart saved → {bar_path}")

print(f"\n{'='*95}")
print(f"DAY 3 COMPLETE — RESOLVES: A006 (joint parameter optimisation)")
print(f"{'='*95}\n")