# [MODULE] Day 5 - RSI Mean Reversion Strategy
# Week 5 Part B
#
# WHAT THIS SCRIPT DOES:
#   Builds and backtests an RSI mean reversion strategy on ETH daily candles.
#   Buys when RSI drops below 30 (oversold) in a bull regime (above 150MA).
#   Exits when RSI recovers above 50 (back to neutral momentum).
#
# HOW RSI WORKS:
#   RSI = 100 - (100 / (1 + RS))
#   where RS = avg gain over N days / avg loss over N days
#
#   RSI < 30 = oversold — price fell unusually fast, recovery likely
#   RSI > 70 = overbought — price rose unusually fast, pullback likely
#   RSI = 50 = neutral momentum
#
# HOW RSI DIFFERS FROM BOLLINGER BANDS:
#   BB measures WHERE price is relative to its average (price-based)
#   RSI measures HOW FAST price moved to get there (momentum-based)
#   Different signals, same regime — combining them filters noise
#
# REGIME FILTER: Same 150MA as BB strategy for consistency
# STRATEGY ID: RSI_14_v1

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from itertools import product

# ---------------------------------------------------------------------------
# [FUNCTION] calculate_rsi
# ---------------------------------------------------------------------------

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    [FUNCTION] Calculate RSI from closing price series.

    Uses Wilder's smoothing method (exponential moving average with
    alpha = 1/period) — the original RSI formula.

    Args:
        close  : Series of closing prices
        period : lookback window (default 14 days — Wilder's original)

    Returns:
        Series of RSI values (0-100)
    """
    # [VARIABLE - Series] daily price changes
    delta: pd.Series = close.diff()

    # [VARIABLE - Series] separate gains and losses
    gains:  pd.Series = delta.clip(lower=0)   # positive changes only
    losses: pd.Series = -delta.clip(upper=0)  # negative changes (made positive)

    # Wilder's smoothing — exponential moving average with alpha = 1/period
    # [VARIABLE - Series] average gain and loss over the period
    avg_gain: pd.Series = gains.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss: pd.Series = losses.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # [VARIABLE - Series] relative strength ratio
    rs: pd.Series = avg_gain / avg_loss.replace(0, 1e-9)  # avoid division by zero

    # [VARIABLE - Series] RSI formula
    rsi: pd.Series = 100 - (100 / (1 + rs))

    return rsi


# ---------------------------------------------------------------------------
# [FUNCTION] backtest_rsi
# ---------------------------------------------------------------------------

def backtest_rsi(
    symbol:       str   = 'ETH-USD',
    start:        str   = '2018-01-01',
    rsi_period:   int   = 14,
    oversold:     float = 35.0,
    exit_level:   float = 50.0,
    stop_pct:     float = 0.10,
    ma_filter:    int   = 150,
) -> dict:
    """
    [FUNCTION] Backtest RSI mean reversion strategy.

    Entry:  RSI < oversold (default 30) AND Close > MA filter
    Exit:   RSI > exit_level (default 50) OR stop-loss hit
    Stop:   stop_pct below entry price (default 10%)

    Args:
        symbol     : yfinance ticker
        start      : backtest start date
        rsi_period : RSI lookback window (default 14)
        oversold   : RSI level that triggers buy (default 30)
        exit_level : RSI level that triggers exit (default 50)
        stop_pct   : hard stop-loss (default 10%)
        ma_filter  : regime filter period (default 150)
    """

    print(f"\nBacktesting RSI | period={rsi_period} | oversold={oversold} | "
          f"exit={exit_level} | stop={stop_pct*100:.0f}% | "
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
    # [VARIABLE - Series] RSI values
    df['RSI'] = calculate_rsi(df['Close'], period=rsi_period)

    # [VARIABLE - Series] regime filter
    df['MA_filter'] = df['Close'].rolling(window=ma_filter).mean()

    df.dropna(inplace=True)

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    # Entry: RSI oversold AND in bull regime
    df['Entry_Signal'] = (
        (df['RSI'] < oversold) &
        (df['Close'] > df['MA_filter'])
    )

    # Exit: RSI back to neutral
    df['Exit_Signal'] = df['RSI'] > exit_level

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
                    'strategy_id': 'RSI_14_v1',
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      trade_return,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            # RSI exit
            elif exit_sig:
                trade_return = (close - entry_price) / entry_price
                trades.append({
                    'strategy_id': 'RSI_14_v1',
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                    'exit_reason': 'RSI_EXIT',
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

    equity:   np.ndarray = np.cumprod(1 + returns)
    peak:     np.ndarray = np.maximum.accumulate(equity)
    drawdown: np.ndarray = (equity - peak) / peak
    max_dd:   float      = drawdown.min()

    stop_exits: int = (trades_df['exit_reason'] == 'STOP_LOSS').sum()
    rsi_exits:  int = (trades_df['exit_reason'] == 'RSI_EXIT').sum()

    years:           float = (df.index[-1] - df.index[0]).days / 365.25
    trades_per_year: float = total_trades / years

    # Kelly
    kelly_b:    float = avg_win / abs(avg_loss) if avg_loss != 0 else 0.0
    kelly_full: float = (win_rate * kelly_b - (1 - win_rate)) / kelly_b if kelly_b > 0 else 0.0
    kelly_half: float = kelly_full * 0.5
    kelly_rec:  float = max(0.0, min(kelly_half, 0.25))

    # ------------------------------------------------------------------
    # 7. Print results
    # ------------------------------------------------------------------
    print(f"\n{'='*80}")
    print(f"RSI MEAN REVERSION BACKTEST RESULTS")
    print(f"{'='*80}")
    print(f"Strategy:         RSI {rsi_period} | oversold<{oversold} | "
          f"exit>{exit_level} | stop={stop_pct*100:.0f}% | {ma_filter}MA")
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
    print(f"  RSI exit:       {rsi_exits} ({rsi_exits/total_trades:.1%} of trades)")
    print(f"\nKELLY CRITERION:")
    print(f"  Reward:risk (b): {kelly_b:.2f}x")
    print(f"  Full Kelly:      {kelly_full:.2%}")
    print(f"  Half Kelly:      {kelly_half:.2%}")
    print(f"  Recommended:     {kelly_rec:.2%}")
    print(f"\nCOMPARISON — RSI vs BB v3 vs ADX:")
    print(f"  {'Metric':<22} {'ADX 20/10':>12} {'BB v3':>12} {'RSI 14':>12}")
    print(f"  {'-'*60}")
    print(f"  {'Win rate':<22} {'34.3%':>12} {'80.8%':>12} {win_rate:>12.1%}")
    print(f"  {'Avg win':<22} {'+24.04%':>12} {'+8.33%':>12} {avg_win:>+12.2%}")
    print(f"  {'Avg loss':<22} {'-3.92%':>12} {'-10.00%':>12} {avg_loss:>+12.2%}")
    print(f"  {'Profit factor':<22} {'3.197':>12} {'3.497':>12} {profit_factor:>12.3f}")
    print(f"  {'Max drawdown':<22} {'-30.3%':>12} {'-19.0%':>12} {max_dd:>12.1%}")
    print(f"  {'Trades/year':<22} {'13.1':>12} {'3.3':>12} {trades_per_year:>12.1f}")
    print(f"{'='*80}\n")

    # ------------------------------------------------------------------
    # 8. Save trade log
    # ------------------------------------------------------------------
    os.makedirs('data', exist_ok=True)
    trades_df.to_csv('data/trade_log_rsi.csv', index=False)
    print("✅ Trade log saved → data/trade_log_rsi.csv")

    # ------------------------------------------------------------------
    # 9. Plots
    # ------------------------------------------------------------------
    os.makedirs('Week_5_Notebooks/results', exist_ok=True)

    fig, axes = plt.subplots(3, 1, figsize=(16, 14))
    fig.suptitle(
        f'RSI Mean Reversion (RSI_14_v1) — oversold<{oversold} | '
        f'exit>{exit_level} | stop={stop_pct*100:.0f}% | {ma_filter}MA (Week 5 Day 5)',
        fontsize=13, fontweight='bold'
    )

    # --- RSI chart (last 2 years) ---
    cutoff  = df.index[-1] - pd.DateOffset(years=2)
    plot_df = df[df.index >= cutoff]

    axes[0].plot(plot_df.index, plot_df['RSI'],
                 color='purple', linewidth=1.5, label='RSI (14)')
    axes[0].axhline(oversold, color='green', linestyle='--',
                    linewidth=1, label=f'Oversold ({oversold})')
    axes[0].axhline(exit_level, color='blue', linestyle='--',
                    linewidth=1, label=f'Exit level ({exit_level})')
    axes[0].axhline(70, color='red', linestyle='--',
                    linewidth=0.8, alpha=0.5, label='Overbought (70)')
    axes[0].fill_between(plot_df.index, plot_df['RSI'], oversold,
                         where=plot_df['RSI'] < oversold,
                         alpha=0.3, color='green', label='Buy zone')
    axes[0].set_ylim(0, 100)
    axes[0].set_title('RSI Indicator (last 2 years)')
    axes[0].set_ylabel('RSI')
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)

    # --- Equity curve ---
    equity_curve = np.concatenate([[1.0], equity])
    axes[1].plot(equity_curve, color='purple',
                 linewidth=1.5, label='RSI strategy')
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
    chart_path = 'Week_5_Notebooks/results/day5_rsi_strategy.png'
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
    results = backtest_rsi(
        symbol='ETH-USD',
        start='2018-01-01',
        rsi_period=14,
        oversold=35.0,
        exit_level=50.0,
        stop_pct=0.10,
        ma_filter=150,
    )