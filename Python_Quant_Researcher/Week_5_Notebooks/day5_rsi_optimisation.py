# [MODULE] Day 5b - RSI Parameter Optimisation
# Week 5 Part B
#
# Runs a joint grid search across all RSI parameters simultaneously:
#   - RSI period      : lookback window for RSI calculation
#   - Oversold level  : RSI threshold that triggers buy signal
#   - Exit level      : RSI level that triggers exit
#   - Stop %          : hard stop-loss distance
#   - MA filter       : regime filter period
#
# MINIMUM TRADES: 20
#   Results with fewer than 20 trades are discarded as statistically
#   unreliable. RSI < 30 with 150MA produced only 6 trades — unusable.
#
# GOAL: Find parameter combination that balances:
#   - Enough trades (20+) for statistical reliability
#   - High profit factor
#   - Acceptable max drawdown
#   - Win rate above 60%

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from itertools import product

# ---------------------------------------------------------------------------
# [FUNCTION] calculate_rsi
# ---------------------------------------------------------------------------

def calculate_rsi(close: pd.Series, period: int) -> pd.Series:
    """
    [FUNCTION] Calculate RSI using Wilder's smoothing method.

    Args:
        close  : Series of closing prices
        period : RSI lookback window

    Returns:
        Series of RSI values (0-100)
    """
    delta:    pd.Series = close.diff()
    gains:    pd.Series = delta.clip(lower=0)
    losses:   pd.Series = -delta.clip(upper=0)

    avg_gain: pd.Series = gains.ewm(
        alpha=1/period, min_periods=period, adjust=False
    ).mean()
    avg_loss: pd.Series = losses.ewm(
        alpha=1/period, min_periods=period, adjust=False
    ).mean()

    rs:  pd.Series = avg_gain / avg_loss.replace(0, 1e-9)
    rsi: pd.Series = 100 - (100 / (1 + rs))

    return rsi


# ---------------------------------------------------------------------------
# [FUNCTION] run_rsi_backtest
# ---------------------------------------------------------------------------

def run_rsi_backtest(
    df:         pd.DataFrame,
    rsi_period: int,
    oversold:   float,
    exit_level: float,
    stop_pct:   float,
    ma_filter:  int,
    min_trades: int = 20,
) -> dict:
    """
    [FUNCTION] Run one RSI backtest for a single parameter combination.

    Args:
        df         : OHLCV DataFrame (fetched once, reused)
        rsi_period : RSI calculation window
        oversold   : RSI buy threshold (e.g. 35 = buy when RSI < 35)
        exit_level : RSI exit threshold (e.g. 50 = exit when RSI > 50)
        stop_pct   : hard stop-loss as fraction of entry price
        ma_filter  : MA period for regime filter
        min_trades : minimum trades to accept result

    Returns:
        dict of metrics, or None if insufficient trades
    """

    # Calculate RSI and MA filter
    rsi: pd.Series = calculate_rsi(df['Close'], period=rsi_period)
    ma:  pd.Series = df['Close'].rolling(window=ma_filter).mean()

    # Signals
    entry_signal: pd.Series = (rsi < oversold) & (df['Close'] > ma)
    exit_signal:  pd.Series = rsi > exit_level

    # Skip NaN warmup period
    valid_from: int = max(rsi_period * 3, ma_filter)

    closes  = df['Close'].values
    lows    = df['Low'].values
    entries = entry_signal.values
    exits   = exit_signal.values

    # Bar-by-bar simulation
    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    for i in range(valid_from, len(df)):
        low:       float = lows[i]
        close:     float = closes[i]
        entry_sig: bool  = entries[i]
        exit_sig:  bool  = exits[i]

        if position == 1:
            if low <= stop_price:
                trades.append({
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            elif exit_sig:
                trades.append({
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'RSI_EXIT',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and entry_sig:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

      # Skip logically invalid combinations
    if exit_level <= oversold:
        return None
    
    if len(trades) < min_trades:
        return None

    trades_df = pd.DataFrame(trades)
    returns   = trades_df['return'].values

    winners = trades_df[trades_df['return'] > 0]
    losers  = trades_df[trades_df['return'] <= 0]

    win_rate      = len(winners) / len(trades_df)
    gross_profit  = winners['return'].sum() if len(winners) > 0 else 0.0
    gross_loss    = abs(losers['return'].sum()) if len(losers) > 0 else 1e-9
    profit_factor = gross_profit / gross_loss

    equity    = np.cumprod(1 + returns)
    peak      = np.maximum.accumulate(equity)
    drawdown  = (equity - peak) / peak
    max_dd    = drawdown.min()

    stop_exits    = (trades_df['exit_reason'] == 'STOP_LOSS').sum()
    total_return  = (1 + returns).prod() - 1

    return {
        'rsi_period':     rsi_period,
        'oversold':       oversold,
        'exit_level':     exit_level,
        'stop_pct':       stop_pct,
        'ma_filter':      ma_filter,
        'total_trades':   len(trades_df),
        'win_rate':       win_rate,
        'avg_win':        winners['return'].mean() if len(winners) > 0 else 0.0,
        'avg_loss':       losers['return'].mean()  if len(losers)  > 0 else 0.0,
        'profit_factor':  profit_factor,
        'max_drawdown':   max_dd,
        'total_return':   total_return,
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
# DEFINE PARAMETER GRID
# ---------------------------------------------------------------------------

# [VARIABLE - list] RSI calculation periods
rsi_periods:   list = [12, 13, 14, 15, 16]

# [VARIABLE - list] oversold thresholds — how low RSI must fall to signal
# Starting higher than 30 since 30 generates too few trades on ETH
oversold_levels: list = [42.0, 43.0, 44.0, 45.0, 46.0, 47.0, 48.0]

# [VARIABLE - list] exit levels — RSI recovery threshold
exit_levels:   list = [42.0, 43.0, 44.0, 45.0, 46.0, 47.0, 48.0]

# [VARIABLE - list] stop-loss percentages
stops:         list = [0.11, 0.12, 0.13, 0.14, 0.15]

# [VARIABLE - list] MA filter periods
ma_filters:    list = [80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130]

total = (len(rsi_periods) * len(oversold_levels) *
         len(exit_levels) * len(stops) * len(ma_filters))

print(f"\nGrid: {len(rsi_periods)} periods × {len(oversold_levels)} oversold × "
      f"{len(exit_levels)} exits × {len(stops)} stops × {len(ma_filters)} MAs")
print(f"Total combinations: {total}")
print(f"Minimum trades threshold: 20")
print(f"Running — this will take several minutes...\n")


# ---------------------------------------------------------------------------
# RUN GRID SEARCH
# ---------------------------------------------------------------------------

results:   list = []
completed: int  = 0

for rsi_period, oversold, exit_level, stop_pct, ma_filter in product(
    rsi_periods, oversold_levels, exit_levels, stops, ma_filters
):
    result = run_rsi_backtest(
        df, rsi_period, oversold, exit_level, stop_pct, ma_filter
    )
    if result is not None:
        results.append(result)
    completed += 1
    if completed % 1347 == 0:
        print(f"  {completed}/{total} combinations tested...")

results_df = pd.DataFrame(results)
print(f"\nGrid search complete.")
print(f"  Valid combinations (≥20 trades): {len(results_df)} of {total}")
print(f"  Discarded (too few trades):      {total - len(results_df)}")


# ---------------------------------------------------------------------------
# RANK AND PRINT RESULTS
# ---------------------------------------------------------------------------

ranked = results_df.sort_values('profit_factor', ascending=False).reset_index(drop=True)

print(f"\n{'='*105}")
print(f"TOP 15 RSI COMBINATIONS (ranked by profit factor)")
print(f"{'='*105}")
print(f"\n{'Rank':<5} {'Period':>8} {'Oversold':>10} {'Exit':>6} "
      f"{'Stop%':>7} {'MA':>6} {'Trades':>8} {'Win Rate':>10} "
      f"{'Profit Factor':>14} {'Max DD':>10} {'Stop Exits':>12}")
print(f"{'-'*105}")

for i, row in ranked.head(15).iterrows():
    print(f"  {i+1:<4} {int(row.rsi_period):>8} {row.oversold:>10.0f} "
          f"{row.exit_level:>6.0f} {row.stop_pct*100:>6.0f}% "
          f"{int(row.ma_filter):>6} {int(row.total_trades):>8} "
          f"{row.win_rate:>10.1%} {row.profit_factor:>14.3f} "
          f"{row.max_drawdown:>10.1%} {row.stop_exits_pct:>11.1%}")

# Best combination
best = ranked.iloc[0]
print(f"\n{'='*105}")
print(f"BEST COMBINATION:")
print(f"  RSI period:    {int(best.rsi_period)}")
print(f"  Oversold:      {best.oversold:.0f}")
print(f"  Exit level:    {best.exit_level:.0f}")
print(f"  Stop:          {best.stop_pct*100:.0f}%")
print(f"  MA filter:     {int(best.ma_filter)}")
print(f"  Profit factor: {best.profit_factor:.3f}")
print(f"  Win rate:      {best.win_rate:.1%}")
print(f"  Total trades:  {int(best.total_trades)}")
print(f"  Max drawdown:  {best.max_drawdown:.1%}")


# ---------------------------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------------------------

os.makedirs('data', exist_ok=True)
ranked.to_csv('data/rsi_optimisation_results.csv', index=False)
print(f"\n✅ Full results saved → data/rsi_optimisation_results.csv")


# ---------------------------------------------------------------------------
# HEATMAPS — profit factor by oversold vs exit level
# One panel per MA filter, fixed at best RSI period and stop
# ---------------------------------------------------------------------------

best_period = int(best.rsi_period)
best_stop   = best.stop_pct

print(f"\nGenerating heatmaps "
      f"(period={best_period}, stop={best_stop*100:.0f}%)...")

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

n_ma = len(ma_filters)
n_cols = 4
n_rows = (n_ma + n_cols - 1) // n_cols
fig, axes = plt.subplots(n_rows, n_cols, figsize=(24, 6 * n_rows))
axes = axes.flatten()

fig.suptitle(
    f'RSI Optimisation — Profit Factor Heatmaps '
    f'(Period={best_period}, Stop={best_stop*100:.0f}%) (Week 5 Day 5b)',
    fontsize=13, fontweight='bold'
)

heat_data = results_df[
    (results_df['rsi_period'] == best_period) &
    (results_df['stop_pct'] == best_stop)
]

vmin = heat_data['profit_factor'].min() if len(heat_data) > 0 else 0
vmax = heat_data['profit_factor'].max() if len(heat_data) > 0 else 1

for idx, ma in enumerate(ma_filters):
    ax = axes[idx]

    panel = heat_data[heat_data['ma_filter'] == ma]

    if len(panel) == 0:
        ax.text(0.5, 0.5, 'No valid\ncombinations',
                ha='center', va='center', transform=ax.transAxes)
        ax.set_title(f'MA Filter = {ma}')
        continue

    pivot = panel.pivot_table(
        index='oversold',
        columns='exit_level',
        values='profit_factor'
    )

    im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto',
                   vmin=vmin, vmax=vmax)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f">{int(c)}" for c in pivot.columns], fontsize=9)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"<{int(o)}" for o in pivot.index], fontsize=9)
    ax.set_xlabel('Exit Level (RSI >)', fontsize=9)
    ax.set_ylabel('Oversold Level (RSI <)', fontsize=9)
    ax.set_title(f'MA Filter = {ma} days', fontsize=11, fontweight='bold')

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.2f}',
                        ha='center', va='center',
                        fontsize=8, fontweight='bold')

# Hide unused subplot panels
for idx in range(len(ma_filters), len(axes)):
    axes[idx].axis('off')

fig.colorbar(im, ax=axes.tolist(),
             label='Profit Factor', shrink=0.6)

plt.tight_layout()
heatmap_path = 'Week_5_Notebooks/results/day5b_rsi_heatmaps.png'
plt.savefig(heatmap_path, dpi=150)
plt.close()
print(f"✅ Heatmaps saved → {heatmap_path}")

# ---------------------------------------------------------------------------
# TOP 15 BAR CHART
# ---------------------------------------------------------------------------

fig, ax = plt.subplots(figsize=(12, 7))
top15 = ranked.head(15).copy()
top15['label'] = top15.apply(
    lambda r: f"RSI{int(r.rsi_period)} OS{int(r.oversold)}\n"
              f"Exit{int(r.exit_level)} Stop{int(r.stop_pct*100)}% MA{int(r.ma_filter)}",
    axis=1
)

ax.barh(range(len(top15)), top15['profit_factor'], color='steelblue')
ax.set_yticks(range(len(top15)))
ax.set_yticklabels(top15['label'], fontsize=8)
ax.invert_yaxis()
ax.set_xlabel('Profit Factor')
ax.set_title('Top 15 RSI Combinations (Week 5 Day 5b)', fontweight='bold')
ax.axvline(1.0, color='red', linestyle='--', alpha=0.5, label='Break-even')
ax.grid(alpha=0.3, axis='x')
ax.legend()

plt.tight_layout()
bar_path = 'Week_5_Notebooks/results/day5b_rsi_top15.png'
plt.savefig(bar_path, dpi=150)
plt.close()
print(f"✅ Bar chart saved → {bar_path}")

print(f"\n{'='*105}")
print(f"RSI OPTIMISATION COMPLETE")
print(f"{'='*105}\n")