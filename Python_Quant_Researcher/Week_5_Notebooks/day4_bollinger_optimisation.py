# [MODULE] Day 4b - Bollinger Bands Parameter Optimisation
# Week 5 Part B
#
# Runs a joint grid search across all four BB parameters simultaneously:
#   - BB window      : how many days define "normal price"
#   - Std deviations : how far from normal triggers a signal
#   - Stop %         : how much room to give the trade
#   - MA filter      : what period defines the bull regime
#
# WHY JOINT OPTIMISATION:
#   All four parameters interact. Changing one affects the others.
#   Testing them separately would miss these interactions.
#
# MINIMUM TRADES THRESHOLD: 15
#   With fewer than 15 trades, results are too noisy to be meaningful.
#   Some tight parameter combinations generate very few signals on ETH.

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from itertools import product

# ---------------------------------------------------------------------------
# [FUNCTION] run_bb_backtest
# ---------------------------------------------------------------------------

def run_bb_backtest(
    df:         pd.DataFrame,
    window:     int,
    num_std:    float,
    stop_pct:   float,
    ma_filter:  int,
    min_trades: int = 15,
) -> dict:
    """
    [FUNCTION] Run one Bollinger Bands backtest for a single parameter set.

    Args:
        df         : full OHLCV DataFrame (fetched once, reused)
        window     : BB lookback period
        num_std    : band width in standard deviations
        stop_pct   : hard stop-loss as fraction of entry price
        ma_filter  : MA period for regime filter
        min_trades : minimum trades required to accept result

    Returns:
        dict of metrics, or None if insufficient trades
    """

    # Calculate Bollinger Bands for this window/std combination
    middle: pd.Series = df['Close'].rolling(window=window).mean()
    std:    pd.Series = df['Close'].rolling(window=window).std()
    upper:  pd.Series = middle + (num_std * std)
    lower:  pd.Series = middle - (num_std * std)

    # [VARIABLE - Series] 200MA regime filter
    ma: pd.Series = df['Close'].rolling(window=ma_filter).mean()

    # Entry: close below lower band AND above MA filter
    entry_signal: pd.Series = (df['Close'] < lower) & (df['Close'] > ma)

    # Exit: close above middle band
    exit_signal: pd.Series = df['Close'] > middle

    # Drop NaN rows (where indicators not yet calculated)
    valid_from: int = max(window, ma_filter)

    closes        = df['Close'].values
    lows          = df['Low'].values
    entries       = entry_signal.values
    exits         = exit_signal.values

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
                    'exit_reason': 'BB_EXIT',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and entry_sig:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

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

    stop_exits = (trades_df['exit_reason'] == 'STOP_LOSS').sum()

    return {
        'window':         window,
        'num_std':        num_std,
        'stop_pct':       stop_pct,
        'ma_filter':      ma_filter,
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
# DEFINE PARAMETER GRID
# ---------------------------------------------------------------------------

# [VARIABLE - list] BB window — how many days define normal price
windows:    list = [10, 15, 20, 25, 30]

# [VARIABLE - list] standard deviations — how far from normal = signal
std_values: list = [1.5, 1.75, 2.0, 2.25]

# [VARIABLE - list] stop-loss percentages
stops:      list = [0.07, 0.10, 0.12, 0.15]

# [VARIABLE - list] MA filter periods — what defines bull regime
ma_filters: list = [50, 100, 150, 200]

total = len(windows) * len(std_values) * len(stops) * len(ma_filters)
print(f"\nGrid: {len(windows)} windows × {len(std_values)} stds × "
      f"{len(stops)} stops × {len(ma_filters)} MA filters")
print(f"Total combinations: {total}")
print(f"Running — this will take a few minutes...\n")


# ---------------------------------------------------------------------------
# RUN GRID SEARCH
# ---------------------------------------------------------------------------

results:   list = []
completed: int  = 0

for window, num_std, stop_pct, ma_filter in product(windows, std_values, stops, ma_filters):
    result = run_bb_backtest(df, window, num_std, stop_pct, ma_filter)
    if result is not None:
        results.append(result)
    completed += 1
    if completed % 80 == 0:
        print(f"  {completed}/{total} combinations tested...")

results_df = pd.DataFrame(results)
print(f"\nGrid search complete.")
print(f"  Valid combinations (≥15 trades): {len(results_df)} of {total}")
print(f"  Discarded (too few trades):      {total - len(results_df)}")


# ---------------------------------------------------------------------------
# RANK AND PRINT RESULTS
# ---------------------------------------------------------------------------

ranked = results_df.sort_values('profit_factor', ascending=False).reset_index(drop=True)

print(f"\n{'='*100}")
print(f"TOP 15 BOLLINGER BANDS COMBINATIONS (ranked by profit factor)")
print(f"{'='*100}")
print(f"\n{'Rank':<5} {'Window':>8} {'Std':>6} {'Stop%':>7} {'MA':>6} "
      f"{'Trades':>8} {'Win Rate':>10} {'Profit Factor':>14} "
      f"{'Max DD':>10} {'Stop Exits':>12}")
print(f"{'-'*100}")

for i, row in ranked.head(15).iterrows():
    # Mark current v2 parameters
    live = (row.window == 20 and row.num_std == 2.0 and
            row.stop_pct == 0.10 and row.ma_filter == 200)
    marker = ' ← CURRENT' if live else ''
    print(f"  {i+1:<4} {int(row.window):>8} {row.num_std:>6.2f} "
          f"{row.stop_pct*100:>6.0f}% {int(row.ma_filter):>6} "
          f"{int(row.total_trades):>8} {row.win_rate:>10.1%} "
          f"{row.profit_factor:>14.3f} {row.max_drawdown:>10.1%} "
          f"{row.stop_exits_pct:>11.1%}{marker}")


# ---------------------------------------------------------------------------
# WHERE DO CURRENT PARAMETERS RANK?
# ---------------------------------------------------------------------------

current = ranked[
    (ranked['window'] == 20) &
    (ranked['num_std'] == 2.0) &
    (ranked['stop_pct'] == 0.10) &
    (ranked['ma_filter'] == 200)
]

if len(current) > 0:
    current_rank = current.index[0] + 1
    print(f"\n{'='*100}")
    print(f"CURRENT PARAMETERS: BB 20 | std 2.0 | stop 10% | 200MA filter")
    print(f"{'='*100}")
    print(f"  Rank:          {current_rank} of {len(results_df)}")
    print(f"  Profit Factor: {current['profit_factor'].values[0]:.3f}")
    print(f"  Win Rate:      {current['win_rate'].values[0]:.1%}")
    print(f"  Max Drawdown:  {current['max_drawdown'].values[0]:.1%}")
    print(f"  Total Trades:  {int(current['total_trades'].values[0])}")

    if current_rank <= 10:
        print(f"\n✅ Current parameters are in the top 10 — strong configuration.")
    elif current_rank <= 30:
        print(f"\n⚠️  Current parameters rank {current_rank} — consider updating.")
    else:
        print(f"\n❌ Current parameters rank {current_rank} — update recommended.")
else:
    print(f"\n⚠️  Current parameters had fewer than 15 trades — below threshold.")

best = ranked.iloc[0]
print(f"\n  Best combination: BB {int(best.window)} | std {best.num_std:.2f} | "
      f"stop {best.stop_pct*100:.0f}% | {int(best.ma_filter)}MA "
      f"(profit factor: {best.profit_factor:.3f})")


# ---------------------------------------------------------------------------
# SAVE RESULTS
# -------------------------------------------------------------------------