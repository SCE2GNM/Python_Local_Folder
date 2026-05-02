# [MODULE] Day 4 - Bollinger Bands Mean Reversion Strategy (v2)
# Week 5 Part B
#
# VERSION 2 CHANGES vs v1:
#   1. 200-day MA regime filter added — only buy when ETH > 200MA
#      (avoids buying into sustained bear market downtrends)
#   2. Stop widened from 5% to 10%
#      (mean reversion needs room to breathe before recovering)
#
# WHY THESE CHANGES:
#   v1 result: profit factor 0.962, 69.4% of trades stopped out
#   Root cause 1: No regime filter — strategy bought into 2018/2022 bear markets
#   Root cause 2: 5% stop too tight for mean reversion entries into weakness

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ---------------------------------------------------------------------------
# [FUNCTION] calculate_bollinger_bands
# ---------------------------------------------------------------------------

def calculate_bollinger_bands(
    close: pd.Series,
    window: int = 20,
    num_std: float = 2.0
) -> pd.DataFrame:
    """
    [FUNCTION] Calculate Bollinger Bands from closing price series.

    Args:
        close   : Series of closing prices
        window  : lookback period for moving average (default 20)
        num_std : number of standard deviations for band width (default 2.0)

    Returns:
        DataFrame with middle, upper, lower bands plus %B indicator
    """
    # [VARIABLE - Series] 20-day simple moving average
    middle: pd.Series = close.rolling(window=window).mean()

    # [VARIABLE - Series] rolling standard deviation
    std: pd.Series = close.rolling(window=window).std()

    upper: pd.Series = middle + (num_std * std)
    lower: pd.Series = middle - (num_std * std)

    # [VARIABLE - Series] %B: where price sits within bands
    # Below 0 = below lower band (our buy zone)
    # Above 1 = above upper band
    pct_b: pd.Series = (close - lower) / (upper - lower)

    return pd.DataFrame({
        'middle': middle,
        'upper':  upper,
        'lower':  lower,
        'pct_b':  pct_b,
    })


# ---------------------------------------------------------------------------
# [FUNCTION] backtest_bollinger
# ---------------------------------------------------------------------------

def backtest_bollinger(
    symbol:   str   = 'ETH-USD',
    start:    str   = '2018-01-01',
    window:   int   = 20,
    num_std:  float = 2.0,
    stop_pct: float = 0.10,
    ma_filter: int  = 200,
) -> dict:
    """
    [FUNCTION] Backtest Bollinger Bands mean reversion with regime filter.

    Entry:  Close < lower band AND Close > 200-day MA
    Exit:   Close > middle band
    Stop:   10% below entry price

    The 200-day MA filter is the key addition vs v1.
    It prevents buying into sustained downtrends.

    Args:
        symbol    : yfinance ticker
        start     : backtest start date
        window    : Bollinger Bands period
        num_std   : band width in standard deviations
        stop_pct  : hard stop-loss (wider than ADX — mean reversion needs room)
        ma_filter : long-term MA period for regime filter (200 days)
    """

    print(f"\nBacktesting Bollinger Bands v2 | window={window} | std={num_std} | "
          f"stop={stop_pct*100:.0f}% | {ma_filter}MA filter | {symbol} from {start}")

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

    # [VARIABLE - Series] 200-day moving average — the regime filter
    # Price above this = broadly bullish = OK to buy dips
    # Price below this = broadly bearish = avoid buying dips
    df['MA200'] = df['Close'].rolling(window=ma_filter).mean()

    # Drop rows where indicators not yet calculated
    df.dropna(inplace=True)

    # ------------------------------------------------------------------
    # 3. Entry and exit signals
    # ------------------------------------------------------------------
    # Entry: price below lower band (oversold) AND above 200MA (bull regime)
    # [VARIABLE - Series] boolean entry signal
    df['Entry_Signal'] = (
        (df['Close'] < df['BB_lower']) &   # oversold condition
        (df['Close'] > df['MA200'])         # bull regime filter
    )

    # Exit: price recovers above middle band
    # [VARIABLE - Series] boolean exit signal
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
            # Stop-loss check first
            if low <= stop_price:
                trade_return = (stop_price - entry_price) / entry_price
                trades.append({
                    'strategy_id': 'BB_20_2_v2',
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
                    'strategy_id': 'BB_20_2_v2',
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
        print("⚠️  No trades generated — filter may be too restrictive.")
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

    gross_profit:   float = winners['return'].sum()       if len(winners) > 0 else 0.0
    gross_loss:     float = abs(losers['return'].sum())   if len(losers)  > 0 else 1e-9
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

    # ------------------------------------------------------------------
    # 7. Print results
    # ------------------------------------------------------------------
    print(f"\n{'='*80}")
    print(f"BOLLINGER BANDS v2 RESULTS (with 200MA filter + 10% stop)")
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
    print(f"\nCOMPARISON TO v1 AND ADX:")
    print(f"  {'Metric':<22} {'BB v1':>10} {'BB v2':>10} {'ADX':>10}")
    print(f"  {'-'*54}")
    print(f"  {'Win rate':<22} {'30.6%':>10} {win_rate:>10.1%} {'34.3%':>10}")
    print(f"  {'Profit factor':<22} {'0.962':>10} {profit_factor:>10.3f} {'3.197':>10}")
    print(f"  {'Max drawdown':<22} {'-54.1%':>10} {max_dd:>10.1%} {'-30.3%':>10}")
    print(f"  {'Stop exits':<22} {'69.4%':>10} "
          f"{stop_exits/total_trades:>10.1%} {'41.7%':>10}")
    print(f"  {'Trades/year':<22} {'10.4':>10} {trades_per_year:>10.1f} {'13.1':>10}")
    print(f"{'='*80}\n")

    # ------------------------------------------------------------------
    # 8. Save trade log
    # ------------------------------------------------------------------
    os.makedirs('data', exist_ok=True)
    trades_df.to_csv('data/trade_log_bollinger_v2.csv', index=False)
    print("✅ Trade log saved → data/trade_log_bollinger_v2.csv")

    # ------------------------------------------------------------------
    # 9. Plots
    # ------------------------------------------------------------------
    os.makedirs('Week_5_Notebooks/results', exist_ok=True)

    fig, axes = plt.subplots(3, 1, figsize=(16, 14))
    fig.suptitle('Bollinger Bands v2 — 200MA Filter + 10% Stop (Week 5 Day 4)',
                 fontsize=14, fontweight='bold')

    # --- Price chart with bands and 200MA (last 2 years) ---
    cutoff = df.index[-1] - pd.DateOffset(years=2)
    plot_df = df[df.index >= cutoff]

    axes[0].plot(plot_df.index, plot_df['Close'],
                 color='black', linewidth=1, label='ETH Close', zorder=3)
    axes[0].plot(plot_df.index, plot_df['BB_middle'],
                 color='blue', linewidth=1, linestyle='--',
                 label='Middle band (20MA)', alpha=0.7)
    axes[0].plot(plot_df.index, plot_df['MA200'],
                 color='orange', linewidth=1.5,
                 label='200MA (regime filter)', alpha=0.9)
    axes[0].fill_between(plot_df.index,
                         plot_df['BB_upper'], plot_df['BB_lower'],
                         alpha=0.15, color='blue', label='Bollinger Bands')

    # Mark filtered buy signals
    buy_signals = plot_df[plot_df['Entry_Signal']]
    axes[0].scatter(buy_signals.index, buy_signals['Close'],
                    color='green', marker='^', s=80,
                    zorder=5, label='Buy signal (filtered)')

    axes[0].set_title('ETH Price with Bollinger Bands + 200MA Filter (last 2 years)')
    axes[0].set_ylabel('Price (USD)')
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)

    # --- Equity curve ---
    equity_curve = np.concatenate([[1.0], equity])
    axes[1].plot(equity_curve, color='steelblue',
                 linewidth=1.5, label='BB v2 equity')
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
    chart_path = 'Week_5_Notebooks/results/day4_bollinger_v2.png'
    plt.savefig(chart_path, dpi=150)
    print(f"✅ Chart saved → {chart_path}")
    plt.close()

    return {
        'total_return':   total_return,
        'net_return':     net_return,
        'sortino':        sortino,
        'profit_factor':  profit_factor,
        'max_drawdown':   max_dd,
        'total_trades':   total_trades,
        'trades_per_year': trades_per_year,
        'win_rate':       win_rate,
        'avg_win':        avg_win,
        'avg_loss':       avg_loss,
        'win_loss_ratio': win_loss_ratio,
        'stop_exits':     stop_exits,
        'trades_df':      trades_df,
    }


# ---------------------------------------------------------------------------
# [ENTRY POINT]
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    results = backtest_bollinger(
        symbol='ETH-USD',
        start='2018-01-01',
        window=20,
        num_std=2.0,
        stop_pct=0.10,
        ma_filter=200,
    )