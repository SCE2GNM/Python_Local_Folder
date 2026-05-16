# [MODULE] Day 7 - Walk-Forward Validation (RSI Mean Reversion)
# Week 5 Part B
#
# WHAT THIS SCRIPT DOES:
#   Tests whether the RSI strategy parameters generalise to unseen data.
#   Uses rolling walk-forward windows: train on N years, test on M years,
#   step forward 1 year at a time.
#
# WHY THIS MATTERS:
#   All optimisation was done on the full 2018-2026 dataset.
#   Walk-forward validation checks if the edge persists out-of-sample.
#   If it does — the strategy has a genuine edge.
#   If it doesn't — the parameters are overfit to history.
#
# WINDOW SETUP:
#   Training: 4 years | Test: 2 years | Step: 1 year
#   Window 1: Train 2018-2022 | Test 2022-2024
#   Window 2: Train 2019-2023 | Test 2023-2025
#   Window 3: Train 2020-2024 | Test 2024-2026
#
# PARAMETERS TESTED (from Day 5 optimisation):
#   RSI period: 14 | Oversold: 43 | Exit: 48
#   Stop: 15%      | MA filter: 120 days
#
# ALSO VALIDATES: Bollinger Bands v3 (BB_15_2_v3) for comparison

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# [FUNCTION] calculate_rsi
# ---------------------------------------------------------------------------

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    [FUNCTION] Calculate RSI using Wilder's smoothing.

    Args:
        close  : closing price Series
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
# [FUNCTION] calculate_bollinger_bands
# ---------------------------------------------------------------------------

def calculate_bollinger_bands(
    close:   pd.Series,
    window:  int   = 15,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """
    [FUNCTION] Calculate Bollinger Bands.

    Args:
        close   : closing price Series
        window  : lookback period
        num_std : band width in standard deviations

    Returns:
        DataFrame with middle, upper, lower bands
    """
    middle: pd.Series = close.rolling(window=window).mean()
    std:    pd.Series = close.rolling(window=window).std()
    upper:  pd.Series = middle + (num_std * std)
    lower:  pd.Series = middle - (num_std * std)

    return pd.DataFrame({
        'middle': middle,
        'upper':  upper,
        'lower':  lower,
    })


# ---------------------------------------------------------------------------
# [FUNCTION] run_rsi_on_window
# ---------------------------------------------------------------------------

def run_rsi_on_window(
    df:         pd.DataFrame,
    start_date: str,
    end_date:   str,
    rsi_period: int   = 14,
    oversold:   float = 43.0,
    exit_level: float = 48.0,
    stop_pct:   float = 0.15,
    ma_filter:  int   = 120,
    label:      str   = '',
) -> dict:
    """
    [FUNCTION] Run RSI backtest on a specific date window.

    Filters the full DataFrame to start_date → end_date,
    then runs the bar-by-bar RSI simulation on that slice only.

    Args:
        df         : full OHLCV DataFrame with pre-calculated indicators
        start_date : window start (string 'YYYY-MM-DD')
        end_date   : window end (string 'YYYY-MM-DD')
        rsi_period : RSI calculation window
        oversold   : RSI buy threshold
        exit_level : RSI exit threshold
        stop_pct   : hard stop-loss
        ma_filter  : regime filter MA period
        label      : window label for reporting

    Returns:
        dict of performance metrics for this window
    """

    # Filter to window — but include warmup period before start
    # so indicators are fully calculated at window start
    warmup_days: int = max(rsi_period * 3, ma_filter) + 30
    warmup_start = pd.Timestamp(start_date) - pd.Timedelta(days=warmup_days)

    window_df = df[df.index >= warmup_start].copy()

    # Calculate indicators on window (including warmup)
    window_df['RSI']       = calculate_rsi(window_df['Close'], period=rsi_period)
    window_df['MA_filter'] = window_df['Close'].rolling(window=ma_filter).mean()
    window_df.dropna(inplace=True)

    # Signals
    window_df['Entry_Signal'] = (
        (window_df['RSI'] < oversold) &
        (window_df['Close'] > window_df['MA_filter'])
    )
    window_df['Exit_Signal'] = window_df['RSI'] > exit_level

    # Now restrict to actual test window (after warmup)
    test_df = window_df[
        (window_df.index >= start_date) &
        (window_df.index <= end_date)
    ]

    if len(test_df) == 0:
        return {'label': label, 'trades': 0, 'error': 'No data in window'}

    # Bar-by-bar simulation on test window only
    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    closes        = test_df['Close'].values
    lows          = test_df['Low'].values
    entry_signals = test_df['Entry_Signal'].values
    exit_signals  = test_df['Exit_Signal'].values
    dates         = test_df.index

    for i in range(1, len(test_df)):
        low:       float = lows[i]
        close:     float = closes[i]
        entry_sig: bool  = entry_signals[i]
        exit_sig:  bool  = exit_signals[i]

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

    if len(trades) == 0:
        return {
            'label':         label,
            'start':         start_date,
            'end':           end_date,
            'trades':        0,
            'win_rate':      None,
            'profit_factor': None,
            'max_drawdown':  None,
            'total_return':  None,
        }

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

    total_return = (1 + returns).prod() - 1

    return {
        'label':         label,
        'start':         start_date,
        'end':           end_date,
        'trades':        len(trades_df),
        'win_rate':      win_rate,
        'profit_factor': profit_factor,
        'max_drawdown':  max_dd,
        'total_return':  total_return,
        'equity':        equity,
    }


# ---------------------------------------------------------------------------
# [FUNCTION] run_bb_on_window
# ---------------------------------------------------------------------------

def run_bb_on_window(
    df:         pd.DataFrame,
    start_date: str,
    end_date:   str,
    bb_window:  int   = 15,
    bb_std:     float = 2.0,
    stop_pct:   float = 0.10,
    ma_filter:  int   = 150,
    label:      str   = '',
) -> dict:
    """
    [FUNCTION] Run Bollinger Bands backtest on a specific date window.

    Same structure as run_rsi_on_window but for the BB strategy.

    Args:
        df        : full OHLCV DataFrame
        start_date: window start
        end_date  : window end
        bb_window : BB lookback period
        bb_std    : BB standard deviations
        stop_pct  : hard stop-loss
        ma_filter : regime filter MA period
        label     : window label for reporting
    """

    warmup_days: int = max(bb_window * 3, ma_filter) + 30
    warmup_start = pd.Timestamp(start_date) - pd.Timedelta(days=warmup_days)

    window_df = df[df.index >= warmup_start].copy()

    bb = calculate_bollinger_bands(
        window_df['Close'], window=bb_window, num_std=bb_std
    )
    window_df['BB_middle'] = bb['middle']
    window_df['BB_lower']  = bb['lower']
    window_df['MA_filter'] = window_df['Close'].rolling(window=ma_filter).mean()
    window_df.dropna(inplace=True)

    window_df['Entry_Signal'] = (
        (window_df['Close'] < window_df['BB_lower']) &
        (window_df['Close'] > window_df['MA_filter'])
    )
    window_df['Exit_Signal'] = window_df['Close'] > window_df['BB_middle']

    test_df = window_df[
        (window_df.index >= start_date) &
        (window_df.index <= end_date)
    ]

    if len(test_df) == 0:
        return {'label': label, 'trades': 0, 'error': 'No data in window'}

    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    closes        = test_df['Close'].values
    lows          = test_df['Low'].values
    entry_signals = test_df['Entry_Signal'].values
    exit_signals  = test_df['Exit_Signal'].values

    for i in range(1, len(test_df)):
        low:       float = lows[i]
        close:     float = closes[i]
        entry_sig: bool  = entry_signals[i]
        exit_sig:  bool  = exit_signals[i]

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

    if len(trades) == 0:
        return {
            'label':         label,
            'start':         start_date,
            'end':           end_date,
            'trades':        0,
            'win_rate':      None,
            'profit_factor': None,
            'max_drawdown':  None,
            'total_return':  None,
        }

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

    return {
        'label':         label,
        'start':         start_date,
        'end':           end_date,
        'trades':        len(trades_df),
        'win_rate':      win_rate,
        'profit_factor': profit_factor,
        'max_drawdown':  max_dd,
        'total_return':  (1 + returns).prod() - 1,
        'equity':        equity,
    }


# ---------------------------------------------------------------------------
# FETCH DATA
# ---------------------------------------------------------------------------

print("\nFetching ETH-USD daily data...")
raw = yf.download('ETH-USD', start='2017-01-01', interval='1d', progress=False)

if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)

df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.dropna(inplace=True)
print(f"Data loaded: {df.index[0].date()} → {df.index[-1].date()} ({len(df):,} days)")


# ---------------------------------------------------------------------------
# DEFINE WALK-FORWARD WINDOWS
# ---------------------------------------------------------------------------
# Each window has a training period (for context/reference) and
# a test period (where the strategy runs with frozen parameters).
# Parameters are NOT re-optimised per window — they stay fixed at
# the values found in the full-sample optimisation.
# This is the strictest form of out-of-sample testing.

# [VARIABLE - list] each tuple is (train_start, train_end, test_start, test_end)
windows: list = [
    ('2018-01-01', '2021-12-31', '2022-01-01', '2023-12-31', 'Window 1'),
    ('2019-01-01', '2022-12-31', '2023-01-01', '2024-12-31', 'Window 2'),
    ('2020-01-01', '2023-12-31', '2024-01-01', '2026-04-06', 'Window 3'),
]

print(f"\nWalk-forward setup:")
print(f"  Training: 4 years | Test: ~2 years | Step: 1 year")
print(f"  Parameters: FIXED at full-sample optimised values")
print(f"  RSI: period=14, oversold=43, exit=48, stop=15%, MA=120")
print(f"  BB:  window=15, std=2.0, stop=10%, MA=150")


# ---------------------------------------------------------------------------
# RUN WALK-FORWARD FOR RSI
# ---------------------------------------------------------------------------

print(f"\n{'='*80}")
print(f"RSI WALK-FORWARD VALIDATION")
print(f"{'='*80}")

rsi_results: list = []

for train_start, train_end, test_start, test_end, label in windows:
    result = run_rsi_on_window(
        df=df,
        start_date=test_start,
        end_date=test_end,
        rsi_period=14,
        oversold=43.0,
        exit_level=48.0,
        stop_pct=0.15,
        ma_filter=120,
        label=label,
    )
    rsi_results.append(result)

    trades     = result['trades']
    pf         = f"{result['profit_factor']:.3f}" if result['profit_factor'] else "N/A"
    wr         = f"{result['win_rate']:.1%}"       if result['win_rate']      else "N/A"
    dd         = f"{result['max_drawdown']:.1%}"   if result['max_drawdown']  else "N/A"
    ret        = f"{result['total_return']:+.1%}"  if result['total_return']  else "N/A"

    # Pass/fail assessment
    if result['profit_factor'] is None:
        verdict = "⚠️  NO TRADES"
    elif result['profit_factor'] >= 1.5 and result['win_rate'] >= 0.60:
        verdict = "✅ PASS"
    elif result['profit_factor'] >= 1.0:
        verdict = "⚠️  MARGINAL"
    else:
        verdict = "❌ FAIL"

    print(f"\n  {label}: {test_start} → {test_end}")
    print(f"    Trades:        {trades}")
    print(f"    Win rate:      {wr}")
    print(f"    Profit factor: {pf}")
    print(f"    Max drawdown:  {dd}")
    print(f"    Total return:  {ret}")
    print(f"    Verdict:       {verdict}")


# ---------------------------------------------------------------------------
# RUN WALK-FORWARD FOR BB
# ---------------------------------------------------------------------------

print(f"\n{'='*80}")
print(f"BOLLINGER BANDS WALK-FORWARD VALIDATION")
print(f"{'='*80}")

bb_results: list = []

for train_start, train_end, test_start, test_end, label in windows:
    result = run_bb_on_window(
        df=df,
        start_date=test_start,
        end_date=test_end,
        bb_window=15,
        bb_std=2.0,
        stop_pct=0.10,
        ma_filter=150,
        label=label,
    )
    bb_results.append(result)

    trades = result['trades']
    pf     = f"{result['profit_factor']:.3f}" if result['profit_factor'] else "N/A"
    wr     = f"{result['win_rate']:.1%}"       if result['win_rate']      else "N/A"
    dd     = f"{result['max_drawdown']:.1%}"   if result['max_drawdown']  else "N/A"
    ret    = f"{result['total_return']:+.1%}"  if result['total_return']  else "N/A"

    if result['profit_factor'] is None:
        verdict = "⚠️  NO TRADES"
    elif result['profit_factor'] >= 1.5 and result['win_rate'] >= 0.60:
        verdict = "✅ PASS"
    elif result['profit_factor'] >= 1.0:
        verdict = "⚠️  MARGINAL"
    else:
        verdict = "❌ FAIL"

    print(f"\n  {label}: {test_start} → {test_end}")
    print(f"    Trades:        {trades}")
    print(f"    Win rate:      {wr}")
    print(f"    Profit factor: {pf}")
    print(f"    Max drawdown:  {dd}")
    print(f"    Total return:  {ret}")
    print(f"    Verdict:       {verdict}")


# ---------------------------------------------------------------------------
# SUMMARY TABLE
# ---------------------------------------------------------------------------

print(f"\n{'='*80}")
print(f"WALK-FORWARD SUMMARY")
print(f"{'='*80}")
print(f"\n{'Window':<12} {'Period':<25} {'RSI PF':>8} {'RSI WR':>8} "
      f"{'BB PF':>8} {'BB WR':>8}")
print(f"{'-'*72}")

for rsi_r, bb_r, (_, _, test_start, test_end, label) in zip(
    rsi_results, bb_results, windows
):
    rsi_pf = f"{rsi_r['profit_factor']:.3f}" if rsi_r['profit_factor'] else "N/A"
    rsi_wr = f"{rsi_r['win_rate']:.1%}"       if rsi_r['win_rate']      else "N/A"
    bb_pf  = f"{bb_r['profit_factor']:.3f}"   if bb_r['profit_factor']  else "N/A"
    bb_wr  = f"{bb_r['win_rate']:.1%}"         if bb_r['win_rate']       else "N/A"

    print(f"  {label:<10} {test_start} → {test_end}   "
          f"{rsi_pf:>8} {rsi_wr:>8} {bb_pf:>8} {bb_wr:>8}")

# Overall verdict
rsi_pfs = [r['profit_factor'] for r in rsi_results if r['profit_factor']]
bb_pfs  = [r['profit_factor'] for r in bb_results  if r['profit_factor']]

rsi_pass = sum(1 for pf in rsi_pfs if pf >= 1.0)
bb_pass  = sum(1 for pf in bb_pfs  if pf >= 1.0)

print(f"\n{'='*80}")
print(f"OVERALL VERDICT")
print(f"{'='*80}")

# RSI verdict
print(f"\nRSI Strategy:")
print(f"  Windows profitable: {rsi_pass}/{len(windows)}")
if len(rsi_pfs) > 0:
    print(f"  Avg profit factor:  {np.mean(rsi_pfs):.3f}")
if rsi_pass == len(windows) and len(rsi_pfs) == len(windows):
    print(f"  ✅ DEPLOY — profitable in all windows")
    rsi_deploy = True
elif rsi_pass >= 2:
    print(f"  ⚠️  BORDERLINE — profitable in {rsi_pass}/3 windows")
    print(f"      Consider paper trading first")
    rsi_deploy = False
else:
    print(f"  ❌ DO NOT DEPLOY — strategy fails out-of-sample")
    rsi_deploy = False

# BB verdict
print(f"\nBollinger Bands Strategy:")
print(f"  Windows profitable: {bb_pass}/{len(windows)}")
if len(bb_pfs) > 0:
    print(f"  Avg profit factor:  {np.mean(bb_pfs):.3f}")
if bb_pass == len(windows) and len(bb_pfs) == len(windows):
    print(f"  ✅ DEPLOY — profitable in all windows")
    bb_deploy = True
elif bb_pass >= 2:
    print(f"  ⚠️  BORDERLINE — profitable in {bb_pass}/3 windows")
    bb_deploy = False
else:
    print(f"  ❌ DO NOT DEPLOY — strategy fails out-of-sample")
    bb_deploy = False


# ---------------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------------

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle(
    'Walk-Forward Validation — RSI (top) vs BB (bottom) (Week 5 Day 7)',
    fontsize=13, fontweight='bold'
)

colors_rsi = ['steelblue', 'green', 'purple']
colors_bb  = ['crimson', 'orange', 'teal']

for idx, (rsi_r, bb_r, (_, _, test_start, test_end, label)) in enumerate(
    zip(rsi_results, bb_results, windows)
):
    # RSI equity curve
    ax_rsi = axes[0][idx]
    if rsi_r['trades'] > 0 and 'equity' in rsi_r:
        eq = np.concatenate([[1.0], rsi_r['equity']])
        ax_rsi.plot(eq, color=colors_rsi[idx], linewidth=2)
        ax_rsi.axhline(1.0, color='gray', linestyle='--', alpha=0.5)
        pf_text = f"PF: {rsi_r['profit_factor']:.2f}"
        wr_text = f"WR: {rsi_r['win_rate']:.0%}"
        t_text  = f"Trades: {rsi_r['trades']}"
    else:
        ax_rsi.text(0.5, 0.5, 'No trades\nin window',
                    ha='center', va='center', transform=ax_rsi.transAxes,
                    fontsize=12)
        pf_text = "PF: N/A"
        wr_text = "WR: N/A"
        t_text  = "Trades: 0"

    ax_rsi.set_title(f'RSI — {label}\n{test_start} → {test_end}\n'
                     f'{pf_text} | {wr_text} | {t_text}',
                     fontsize=9)
    ax_rsi.set_ylabel('Equity multiplier' if idx == 0 else '')
    ax_rsi.grid(alpha=0.3)

    # BB equity curve
    ax_bb = axes[1][idx]
    if bb_r['trades'] > 0 and 'equity' in bb_r:
        eq = np.concatenate([[1.0], bb_r['equity']])
        ax_bb.plot(eq, color=colors_bb[idx], linewidth=2)
        ax_bb.axhline(1.0, color='gray', linestyle='--', alpha=0.5)
        pf_text = f"PF: {bb_r['profit_factor']:.2f}"
        wr_text = f"WR: {bb_r['win_rate']:.0%}"
        t_text  = f"Trades: {bb_r['trades']}"
    else:
        ax_bb.text(0.5, 0.5, 'No trades\nin window',
                   ha='center', va='center', transform=ax_bb.transAxes,
                   fontsize=12)
        pf_text = "PF: N/A"
        wr_text = "WR: N/A"
        t_text  = "Trades: 0"

    ax_bb.set_title(f'BB — {label}\n{test_start} → {test_end}\n'
                    f'{pf_text} | {wr_text} | {t_text}',
                    fontsize=9)
    ax_bb.set_ylabel('Equity multiplier' if idx == 0 else '')
    ax_bb.grid(alpha=0.3)

plt.tight_layout()
chart_path = 'Week_5_Notebooks/results/day7_walk_forward.png'
plt.savefig(chart_path, dpi=150)
print(f"\n✅ Chart saved → {chart_path}")
plt.close()

print(f"\n{'='*80}")
print(f"DAY 7 COMPLETE — WALK-FORWARD VALIDATION")
print(f"{'='*80}\n")