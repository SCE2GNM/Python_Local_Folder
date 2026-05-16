# [MODULE] Day 4 - Bollinger Bands Mean Reversion Strategy (FINAL)
# Week 5 Part B
#
# PARAMETER HISTORY:
#   v1: window=20, std=2.0, stop=5%,  no filter   → profit factor 0.962 (LOSS)
#   v2: window=20, std=2.0, stop=10%, 200MA filter → profit factor 1.615
#   v3: window=15, std=2.0, stop=10%, 150MA filter → profit factor 3.497 (FINAL)
#
# KEY CHANGES FROM v2:
#   - BB window reduced from 20 to 15 days
#     → Shorter window reacts faster to price deviations
#     → Generates more signals without sacrificing quality
#   - MA filter reduced from 200 to 150 days
#     → Less restrictive regime filter
#     → Captures more valid bull market mean reversion opportunities
#     → 200MA was excluding too many profitable trades
#
# WHAT STAYED THE SAME:
#   - Std deviations: 2.0 (grid search confirmed this is optimal)
#   - Stop-loss: 10% (mean reversion needs room to breathe)
#   - Entry logic: close below lower band
#   - Exit logic: close above middle band
#
# STRATEGY ID: BB_15_2_v3

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
    [FUNCTION] Calculate Bollinger Bands from closing price series.

    Middle band = N-day simple moving average
    Upper band  = middle + (num_std × N-day standard deviation)
    Lower band  = middle - (num_std × N-day standard deviation)

    Args:
        close   : Series of closing prices
        window  : lookback period (optimised: 15 days)
        num_std : band width (optimised: 2.0 std deviations)

    Returns:
        DataFrame with middle, upper, lower bands and %B indicator
    """
    middle: pd.Series = close.rolling(window=window).mean()
    std:    pd.Series = close.rolling(window=window).std()
    upper:  pd.Series = middle + (num_std * std)
    lower:  pd.Series = middle - (num_std * std)

    # [VARIABLE - Series] %B: position of price within the bands
    # <0 = below lower band (our buy zone)
    # 0.5 = at middle band (our exit zone)
    # >1 = above upper band
    pct_b: pd.Series = (close - lower) / (upper - lower)

    return pd.DataFrame({
        'middle': middle,
        'upper':  upper,
        'lower':  lower,
        'pct_b':  pct_b,
    })


# ---------------------------------------------------------------------------
# [FUNCTION] backtest_bollinger_final
# ---------------------------------------------------------------------------

def backtest_bollinger_final(
    symbol:    str   = 'ETH-USD',
    start:     str   = '2018-01-01',
    window:    int   = 15,
    num_std:   float = 2.0,
    stop_pct:  float = 0.10,
    ma_filter: int   = 150,
) -> dict:
    """
    [FUNCTION] Final Bollinger Bands backtest with optimised parameters.

    Entry:  Close < lower band AND Close > 150MA (bull regime)
    Exit:   Close > middle band (price recovered to average)
    Stop:   10% below entry price

    Args:
        symbol    : yfinance ticker
        start     : backtest start date
        window    : BB period (optimised: 15)
        num_std   : band width (optimised: 2.0)
        stop_pct  : stop-loss (optimised: 10%)
        ma_filter : regime filter period (optimised: 150)
    """

    print(f"\nBacktesting Bollinger Bands FINAL | window={window} | "
          f"std={num_std} | stop={stop_pct*100:.0f}% | "
          f"{ma_filter}MA filter | {symbol} from {start}")

    # ------------------------------------------------------------------
    # 1. Fetch data
    # ------------------------------------------------------------------
    raw = yf.download(symbol, start=start, interval='1d', progress=False)

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)

    df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.dropna(inplace=True)

    # ------------------------------------------------------------------
    # 2. Calculate indicators
    # ------------------------------------------------------------------
    bb = calculate_bollinger_bands(df['Close'], window=window, num_std=num_std)
    df['BB_middle'] = bb['middle']
    df['BB_upper']  = bb['upper']
    df['BB_lower']  = bb['lower']
    df['BB_pct_b']  = bb['pct_b']

    # [VARIABLE - Series] 150-day MA regime filter
    df['MA150'] = df['Close'].rolling(window=ma_filter).mean()

    df.dropna(inplace=True)

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    # Entry: oversold (below lower band) AND in bull regime (above 150MA)
    df['Entry_Signal'] = (
        (df['Close'] < df['BB_lower']) &
        (df['Close'] > df['MA150'])
    )

    # Exit: price recovered to middle band
    df['Exit_Signal'] = df['Close'] > df['BB_middle']

    # ------------------------------------------------------------------
    # 4. Bar-by-bar simulation
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
            # Stop-loss first
            if low <= stop_price:
                trade_return = (stop_price - entry_price) / entry_price
                trades.append({
                    'strategy_id': 'BB_15_2_v3',
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      trade_return,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            # Mean reversion exit
            elif exit_sig:
                trade_return = (close - entry_price) / entry_price
                trades.append({
                    'strategy_id': 'BB_15_2_v3',
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                    'exit_reason': 'BB_EXIT',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and entry_sig:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    # ------------------------------------------------------------------
    # 5. Build trades DataFrame
    # ------------------------------------------------------------------
    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        print("⚠️  No trades generated.")
        return {}

    # ------------------------------------------------------------------
    # 6. Performance metrics
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

    downside: np.ndarray = returns[returns < 0]
    sortino:  float = (
        returns.mean() / downside.std() * np.sqrt(365)
        if len(downside) > 0 and downside.std() > 0 else 0.0
    )

    equity:   np.ndarray = np.cumprod(1 + returns)
    peak:     np.ndarray = np.maximum.accumulate(equity)
    drawdown: np.ndarray = (equity - peak) / peak
    max_dd:   float      = drawdown.min()

    stop_exits: int = (trades_df['exit_reason'] == 'STOP_LOSS').sum()
    bb_exits:   int = (trades_df['exit_reason'] == 'BB_EXIT').sum()

    years:           float = (df.index[-1] - df.index[0]).days / 365.25
    trades_per_year: float = total_trades / years

    # Kelly inputs for this strategy
    kelly_b:    float = avg_win / abs(avg_loss) if avg_loss != 0 else 0.0
    kelly_full: float = (win_rate * kelly_b - (1 - win_rate)) / kelly_b if kelly_b > 0 else 0.0
    kelly_half: float = kelly_full * 0.5
    kelly_rec:  float = max(0.0, min(kelly_half, 0.25))

    # ------------------------------------------------------------------
    # 7. Print results
    # ------------------------------------------------------------------
    print(f"\n{'='*80}")
    print(f"BOLLINGER BANDS FINAL BACKTEST RESULTS (BB_15_2_v3)")
    print(f"{'='*80}")
    print(f"Strategy:         BB window={window} | std={num_std} | "
          f"stop={stop_pct*100:.0f}% | {ma_filter}MA filter")
    print(f"Period:           {df.index[0].date()} → {df.index[-1].date()}")
    print(f"Days:             {len(df):,}")
    print(f"\nPERFORMANCE:")
    print(f"  Gross Return:   {total_return:+.2%}")
    print(f"  Net Return:     {net_return:+.2%}")
    print(f"  Annualised:     {net_return / years:+.2%}/yr  ({years:.1f} yrs)")
    print(f"  Sortino Ratio:  {sortino:.3f}")
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
    print(f"  BB exit:        {bb_exits} ({bb_exits/total_trades:.1%} of trades)")
    print(f"\nKELLY CRITERION (BB strategy):")
    print(f"  Reward:risk (b): {kelly_b:.2f}x")
    print(f"  Full Kelly:      {kelly_full:.2%}")
    print(f"  Half Kelly:      {kelly_half:.2%}")
    print(f"  Recommended:     {kelly_rec:.2%} (capped at 25%)")
    print(f"\nCOMPARISON — BB v3 vs ADX 20/10:")
    print(f"  {'Metric':<22} {'ADX 20/10':>12} {'BB v3':>12}")
    print(f"  {'-'*48}")
    print(f"  {'Win rate':<22} {'34.3%':>12} {win_rate:>12.1%}")
    print(f"  {'Avg win':<22} {'+24.04%':>12} {avg_win:>+12.2%}")
    print(f"  {'Avg loss':<22} {'-3.92%':>12} {avg_loss:>+12.2%}")
    print(f"  {'Profit factor':<22} {'3.197':>12} {profit_factor:>12.3f}")
    print(f"  {'Max drawdown':<22} {'-30.3%':>12} {max_dd:>12.1%}")
    print(f"  {'Trades/year':<22} {'13.1':>12} {trades_per_year:>12.1f}")
    print(f"  {'Kelly recommended':<22} {'11.77%':>12} {kelly_rec:>12.2%}")
    print(f"{'='*80}\n")

    # ------------------------------------------------------------------
    # 8. Save trade log
    # ------------------------------------------------------------------
    os.makedirs('data', exist_ok=True)
    trades_df.to_csv('data/trade_log_bollinger_final.csv', index=False)
    print("✅ Trade log saved → data/trade_log_bollinger_final.csv")

    # ------------------------------------------------------------------
    # 9. Plots
    # ------------------------------------------------------------------
    os.makedirs('Week_5_Notebooks/results', exist_ok=True)

    fig, axes = plt.subplots(3, 1, figsize=(16, 14))
    fig.suptitle(
        f'Bollinger Bands Final (BB_15_2_v3) — window=15 | std=2.0 | '
        f'stop=10% | 150MA (Week 5 Day 4)',
        fontsize=13, fontweight='bold'
    )

    # --- Price chart with bands and 150MA (last 2 years) ---
    cutoff  = df.index[-1] - pd.DateOffset(years=2)
    plot_df = df[df.index >= cutoff]

    axes[0].plot(plot_df.index, plot_df['Close'],
                 color='black', linewidth=1, label='ETH Close', zorder=3)
    axes[0].plot(plot_df.index, plot_df['BB_middle'],
                 color='blue', linewidth=1, linestyle='--',
                 label='Middle band (15MA)', alpha=0.7)
    axes[0].plot(plot_df.index, plot_df['MA150'],
                 color='orange', linewidth=1.5,
                 label='150MA (regime filter)', alpha=0.9)
    axes[0].fill_between(plot_df.index,
                         plot_df['BB_upper'], plot_df['BB_lower'],
                         alpha=0.15, color='blue', label='Bollinger Bands')

    buy_signals = plot_df[plot_df['Entry_Signal']]
    axes[0].scatter(buy_signals.index, buy_signals['Close'],
                    color='green', marker='^', s=80,
                    zorder=5, label='Buy signal')

    axes[0].set_title('ETH Price with Bollinger Bands + 150MA Filter (last 2 years)')
    axes[0].set_ylabel('Price (USD)')
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)

    # --- Equity curve ---
    equity_curve = np.concatenate([[1.0], equity])
    axes[1].plot(equity_curve, color='steelblue',
                 linewidth=1.5, label='BB_15_2_v3')
    axes[1].axhline(1.0, color='gray', linestyle='--', alpha=0.6)
    axes[1].set_title('Cumulative Equity (per-trade)')
    axes[1].set_ylabel('Equity multiplier')
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    # --- Drawdown ---
    axes[2].fill_between(range(len(drawdown)), drawdown * 100, 0,
                         color='crimson', alpha=0.5)
    axes[2].set_title('Drawdown (%)')
    axes[2].set_ylabel('Drawdown %')
    axes[2].grid(alpha=0.3)

    plt.tight_layout()
    chart_path = 'Week_5_Notebooks/results/day4_bollinger_final.png'
    plt.savefig(chart_path, dpi=150)
    print(f"✅ Chart saved → {chart_path}")
    plt.close()

    return {
        'total_return':    total_return,
        'net_return':      net_return,
        'sortino':         sortino,
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
    results = backtest_bollinger_final(
        symbol='ETH-USD',
        start='2018-01-01',
        window=15,
        num_std=2.0,
        stop_pct=0.10,
        ma_filter=150,
    )