# [MODULE] Day 6 - Combined BB + RSI Mean Reversion Strategy
# Week 5 Part B
#
# WHAT THIS SCRIPT DOES:
#   Combines Bollinger Bands and RSI signals into a single strategy.
#   Only enters when BOTH indicators simultaneously signal oversold.
#   This is called signal confluence — two independent signals agreeing.
#
# ENTRY LOGIC:
#   BB condition:  Close < BB lower band (price below 2std from mean)
#   RSI condition: RSI < 43 (momentum oversold)
#   Regime filter: Close > 120MA (bull market only)
#   ALL THREE must be true simultaneously to enter.
#
# EXIT LOGIC:
#   RSI > 48 (momentum recovered) — primary exit
#   OR Close > BB middle band (price recovered to mean) — secondary exit
#   OR stop-loss hit (15% below entry)
#
# WHY THIS IS STRONGER THAN EITHER ALONE:
#   BB alone: price can drift below band slowly without momentum collapse
#   RSI alone: momentum can drop without price reaching statistical extreme
#   Combined: both conditions = genuine capitulation selloff with high
#   probability of snapback recovery
#
# STRATEGY ID: BB_RSI_combined_v1

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

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
        window  : lookback period (BB optimised: 15)
        num_std : band width (BB optimised: 2.0)

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
# [FUNCTION] calculate_rsi
# ---------------------------------------------------------------------------

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    [FUNCTION] Calculate RSI using Wilder's smoothing.

    Args:
        close  : closing price Series
        period : RSI lookback window (RSI optimised: 14)

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
# [FUNCTION] backtest_combined
# ---------------------------------------------------------------------------

def backtest_combined(
    symbol:     str   = 'ETH-USD',
    start:      str   = '2018-01-01',
    bb_window:  int   = 15,
    bb_std:     float = 2.0,
    rsi_period: int   = 14,
    rsi_os:     float = 43.0,
    rsi_exit:   float = 48.0,
    stop_pct:   float = 0.15,
    ma_filter:  int   = 120,
) -> dict:
    """
    [FUNCTION] Backtest combined BB + RSI mean reversion strategy.

    Uses optimised parameters from Day 4 (BB) and Day 5 (RSI).
    Entry requires ALL conditions simultaneously:
      1. Close < BB lower band
      2. RSI < rsi_os (43)
      3. Close > MA filter (120MA)

    Exit on first of:
      1. RSI > rsi_exit (48) — momentum recovered
      2. Close > BB middle band — price recovered to mean
      3. Stop-loss at stop_pct below entry

    Args:
        symbol     : yfinance ticker
        start      : backtest start date
        bb_window  : BB lookback period (optimised: 15)
        bb_std     : BB standard deviations (optimised: 2.0)
        rsi_period : RSI period (optimised: 14)
        rsi_os     : RSI oversold threshold (optimised: 43)
        rsi_exit   : RSI exit threshold (optimised: 48)
        stop_pct   : hard stop-loss (optimised: 15%)
        ma_filter  : regime filter MA period (optimised: 120)
    """

    print(f"\nBacktesting BB+RSI Combined | BB {bb_window}/{bb_std} | "
          f"RSI {rsi_period} os<{rsi_os} exit>{rsi_exit} | "
          f"stop={stop_pct*100:.0f}% | {ma_filter}MA | {symbol} from {start}")

    # ------------------------------------------------------------------
    # 1. Fetch data
    # ------------------------------------------------------------------
    raw = yf.download(symbol, start=start, interval='1d', progress=False)

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)

    df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.dropna(inplace=True)

    # ------------------------------------------------------------------
    # 2. Calculate all indicators
    # ------------------------------------------------------------------
    # Bollinger Bands
    bb = calculate_bollinger_bands(df['Close'], window=bb_window, num_std=bb_std)
    df['BB_middle'] = bb['middle']
    df['BB_upper']  = bb['upper']
    df['BB_lower']  = bb['lower']

    # RSI
    df['RSI'] = calculate_rsi(df['Close'], period=rsi_period)

    # Regime filter
    df['MA_filter'] = df['Close'].rolling(window=ma_filter).mean()

    df.dropna(inplace=True)

    # ------------------------------------------------------------------
    # 3. Combined entry signal
    # ------------------------------------------------------------------
    # ALL three conditions must be true simultaneously
    # [VARIABLE - Series] BB oversold condition
    bb_oversold:  pd.Series = df['Close'] < df['BB_lower']

    # [VARIABLE - Series] RSI oversold condition
    rsi_oversold: pd.Series = df['RSI'] < rsi_os

    # [VARIABLE - Series] bull regime condition
    bull_regime:  pd.Series = df['Close'] > df['MA_filter']

    # [VARIABLE - Series] combined entry — all three must agree
    df['Entry_Signal'] = bb_oversold & rsi_oversold & bull_regime

    # ------------------------------------------------------------------
    # 4. Combined exit signal
    # ------------------------------------------------------------------
    # Exit on EITHER indicator recovering — whichever comes first
    # [VARIABLE - Series] RSI recovery
    rsi_recovered: pd.Series = df['RSI'] > rsi_exit

    # [VARIABLE - Series] BB middle band recovery
    bb_recovered:  pd.Series = df['Close'] > df['BB_middle']

    # [VARIABLE - Series] combined exit — either condition sufficient
    df['Exit_Signal'] = rsi_recovered | bb_recovered

    # ------------------------------------------------------------------
    # 5. Bar-by-bar simulation
    # ------------------------------------------------------------------
    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    closes        = df['Close'].values
    lows          = df['Low'].values
    entry_signals = df['Entry_Signal'].values
    exit_signals  = df['Exit_Signal'].values
    dates         = df.index

    for i in range(1, len(df)):
        low:       float = lows[i]
        close:     float = closes[i]
        entry_sig: bool  = entry_signals[i]
        exit_sig:  bool  = exit_signals[i]

        if position == 1:
            if low <= stop_price:
                trade_return = (stop_price - entry_price) / entry_price
                trades.append({
                    'strategy_id': 'BB_RSI_combined_v1',
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      trade_return,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            elif exit_sig:
                trade_return = (close - entry_price) / entry_price
                trades.append({
                    'strategy_id': 'BB_RSI_combined_v1',
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                    'exit_reason': 'COMBINED_EXIT',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and entry_sig:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    # ------------------------------------------------------------------
    # 6. Build trades DataFrame
    # ------------------------------------------------------------------
    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        print("⚠️  No trades generated — signals too restrictive.")
        print("    Consider relaxing BB std or RSI oversold threshold.")
        return {}

    # ------------------------------------------------------------------
    # 7. Performance metrics
    # ------------------------------------------------------------------
    total_trades:    int   = len(trades_df)
    returns: np.ndarray    = trades_df['return'].values

    cost_per_trade:  float = 0.00075 * 2
    total_cost_drag: float = total_trades * cost_per_trade
    total_return:    float = (1 + returns).prod() - 1
    net_return:      float = total_return - total_cost_drag

    winners = trades_df[trades_df['return'] > 0]
    losers  = trades_df[trades_df['return'] <= 0]

    win_rate:       float = len(winners) / total_trades
    avg_win:        float = winners['return'].mean() if len(winners) > 0 else 0.0
    avg_loss:       float = losers['return'].mean()  if len(losers)  > 0 else 0.0
    win_loss_ratio: float = abs(avg_win / avg_loss)  if avg_loss != 0 else float('inf')

    gross_profit:   float = winners['return'].sum()     if len(winners) > 0 else 0.0
    gross_loss:     float = abs(losers['return'].sum()) if len(losers)  > 0 else 1e-9
    profit_factor:  float = gross_profit / gross_loss

    equity:   np.ndarray = np.cumprod(1 + returns)
    peak:     np.ndarray = np.maximum.accumulate(equity)
    drawdown: np.ndarray = (equity - peak) / peak
    max_dd:   float      = drawdown.min()

    stop_exits:     int = (trades_df['exit_reason'] == 'STOP_LOSS').sum()
    combined_exits: int = (trades_df['exit_reason'] == 'COMBINED_EXIT').sum()

    years:           float = (df.index[-1] - df.index[0]).days / 365.25
    trades_per_year: float = total_trades / years

    # Kelly
    kelly_b:    float = avg_win / abs(avg_loss) if avg_loss != 0 else 0.0
    kelly_full: float = (
        (win_rate * kelly_b - (1 - win_rate)) / kelly_b
        if kelly_b > 0 else 0.0
    )
    kelly_half: float = kelly_full * 0.5
    kelly_rec:  float = max(0.0, min(kelly_half, 0.25))

    # ------------------------------------------------------------------
    # 8. Print results
    # ------------------------------------------------------------------
    print(f"\n{'='*80}")
    print(f"BB + RSI COMBINED STRATEGY RESULTS (BB_RSI_combined_v1)")
    print(f"{'='*80}")
    print(f"BB params:        window={bb_window} | std={bb_std}")
    print(f"RSI params:       period={rsi_period} | oversold<{rsi_os} | exit>{rsi_exit}")
    print(f"Risk params:      stop={stop_pct*100:.0f}% | {ma_filter}MA filter")
    print(f"Period:           {df.index[0].date()} → {df.index[-1].date()}")
    print(f"Days:             {len(df):,}")
    print(f"\nPERFORMANCE:")
    print(f"  Gross Return:   {total_return:+.2%}")
    print(f"  Net Return:     {net_return:+.2%}")
    print(f"  Annualised:     {net_return / years:+.2%}/yr  ({years:.1f} yrs)")
    print(f"  Profit Factor:  {profit_factor:.3f}")
    print(f"  Max Drawdown:   {max_dd:.2%}")
    print(f"\nTRADING STATS:")
    print(f"  Total Trades:   {total_trades}")
    print(f"  Trades/Year:    {trades_per_year:.1f}")
    print(f"  Winners:        {len(winners)} ({win_rate:.1%} win rate)")
    print(f"  Losers:         {len(losers)}")
    print(f"  Avg Win:        {avg_win:+.2%}")
    print(f"  Avg Loss:       {avg_loss:+.2%}")
    print(f"  Win/Loss Ratio: {win_loss_ratio:.2f}x")
    print(f"\nEXIT BREAKDOWN:")
    print(f"  Stop-loss:      {stop_exits} ({stop_exits/total_trades:.1%} of trades)")
    print(f"  Combined exit:  {combined_exits} ({combined_exits/total_trades:.1%} of trades)")
    print(f"\nKELLY CRITERION:")
    print(f"  Reward:risk (b): {kelly_b:.2f}x")
    print(f"  Full Kelly:      {kelly_full:.2%}")
    print(f"  Half Kelly:      {kelly_half:.2%}")
    print(f"  Recommended:     {kelly_rec:.2%}")
    print(f"\nFULL STRATEGY COMPARISON:")
    print(f"  {'Metric':<22} {'ADX':>10} {'BB v3':>10} "
          f"{'RSI':>10} {'Combined':>10}")
    print(f"  {'-'*64}")
    print(f"  {'Win rate':<22} {'34.3%':>10} {'80.8%':>10} "
          f"{'93.5%':>10} {win_rate:>10.1%}")
    print(f"  {'Profit factor':<22} {'3.197':>10} {'3.497':>10} "
          f"{'5.593':>10} {profit_factor:>10.3f}")
    print(f"  {'Max drawdown':<22} {'-30.3%':>10} {'-19.0%':>10} "
          f"{'-15.0%':>10} {max_dd:>10.1%}")
    print(f"  {'Trades/year':<22} {'13.1':>10} {'3.3':>10} "
          f"{'3.9':>10} {trades_per_year:>10.1f}")
    print(f"  {'Sample size':<22} {'108':>10} {'26':>10} "
          f"{'31':>10} {total_trades:>10}")
    print(f"  {'Kelly rec':<22} {'11.77%':>10} {'10-12%':>10} "
          f"{'25%cap':>10} {kelly_rec:>10.2%}")
    print(f"{'='*80}\n")

    # ------------------------------------------------------------------
    # 9. Save trade log
    # ------------------------------------------------------------------
    os.makedirs('data', exist_ok=True)
    trades_df.to_csv('data/trade_log_combined.csv', index=False)
    print("✅ Trade log saved → data/trade_log_combined.csv")

    # ------------------------------------------------------------------
    # 10. Plots
    # ------------------------------------------------------------------
    os.makedirs('Week_5_Notebooks/results', exist_ok=True)

    fig, axes = plt.subplots(4, 1, figsize=(16, 18))
    fig.suptitle(
        'BB + RSI Combined Mean Reversion Strategy (Week 5 Day 6)',
        fontsize=14, fontweight='bold'
    )

    # --- Price chart with BB and MA (last 3 years) ---
    cutoff  = df.index[-1] - pd.DateOffset(years=3)
    plot_df = df[df.index >= cutoff]

    axes[0].plot(plot_df.index, plot_df['Close'],
                 color='black', linewidth=1, label='ETH Close', zorder=3)
    axes[0].plot(plot_df.index, plot_df['BB_middle'],
                 color='blue', linewidth=1, linestyle='--',
                 label='BB Middle (15MA)', alpha=0.7)
    axes[0].plot(plot_df.index, plot_df['MA_filter'],
                 color='orange', linewidth=1.5,
                 label=f'{ma_filter}MA (regime)', alpha=0.9)
    axes[0].fill_between(plot_df.index,
                         plot_df['BB_upper'], plot_df['BB_lower'],
                         alpha=0.15, color='blue', label='Bollinger Bands')

    # Mark combined entry signals
    buy_signals = plot_df[plot_df['Entry_Signal']]
    axes[0].scatter(buy_signals.index, buy_signals['Close'],
                    color='green', marker='^', s=100,
                    zorder=5, label='Combined buy signal')

    axes[0].set_title('ETH Price with BB + 120MA (last 3 years)')
    axes[0].set_ylabel('Price (USD)')
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)

    # --- RSI chart ---
    axes[1].plot(plot_df.index, plot_df['RSI'],
                 color='purple', linewidth=1.5, label='RSI (14)')
    axes[1].axhline(rsi_os, color='green', linestyle='--',
                    linewidth=1.5, label=f'Oversold (<{rsi_os})')
    axes[1].axhline(rsi_exit, color='blue', linestyle='--',
                    linewidth=1.5, label=f'Exit (>{rsi_exit})')
    axes[1].fill_between(
        plot_df.index, plot_df['RSI'], rsi_os,
        where=plot_df['RSI'] < rsi_os,
        alpha=0.3, color='green'
    )
    axes[1].set_ylim(0, 100)
    axes[1].set_title('RSI Indicator (last 3 years)')
    axes[1].set_ylabel('RSI')
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)

    # --- Equity curve ---
    equity_curve = np.concatenate([[1.0], equity])
    axes[2].plot(equity_curve, color='teal',
                 linewidth=2, label='BB+RSI Combined')
    axes[2].axhline(1.0, color='gray', linestyle='--', alpha=0.6)
    axes[2].set_title('Cumulative Equity (per-trade)')
    axes[2].set_ylabel('Equity multiplier')
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    # --- Drawdown ---
    axes[3].fill_between(range(len(drawdown)), drawdown * 100, 0,
                         color='crimson', alpha=0.5)
    axes[3].set_title('Drawdown (%)')
    axes[3].set_ylabel('Drawdown %')
    axes[3].grid(alpha=0.3)

    plt.tight_layout()
    chart_path = 'Week_5_Notebooks/results/day6_combined_strategy.png'
    plt.savefig(chart_path, dpi=150)
    print(f"✅ Chart saved → {chart_path}")
    plt.close()

    return {
        'total_return':    total_return,
        'net_return':      net_return,
        'profit_factor':   profit_factor,
        'max_drawdown':    max_dd,
        'total_trades':    total_trades,
        'trades_per_year': trades_per_year,
        'win_rate':        win_rate,
        'avg_win':         avg_win,
        'avg_loss':        avg_loss,
        'win_loss_ratio':  win_loss_ratio,
        'stop_exits':      stop_exits,
        'kelly_rec':       kelly_rec,
        'trades_df':       trades_df,
    }


# ---------------------------------------------------------------------------
# [ENTRY POINT]
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    results = backtest_combined(
        symbol='ETH-USD',
        start='2018-01-01',
        bb_window=15,
        bb_std=1.75,
        rsi_period=14,
        rsi_os=43.0,
        rsi_exit=48.0,
        stop_pct=0.15,
        ma_filter=120,
    )