# [MODULE] Day 5 - RSI Mean Reversion Strategy (FINAL)
# Week 5 Part B
#
# PARAMETER HISTORY:
#   v1: period=14, oversold=30, exit=50, stop=10%, MA=150 → 0 trades
#   v2: period=14, oversold=35, exit=50, stop=10%, MA=150 → 6 trades (unusable)
#   v3: period=14, oversold=45, exit=45, stop=15%, MA=100 → fragile (spike)
#   FINAL: period=14, oversold=43, exit=48, stop=15%, MA=120 → stable plateau
#
# STABILITY SCORES (confirmed):
#   RSI Period:    80% (4/5 values above PF 2.0)
#   Oversold:      67% (4/6 values above PF 2.0)
#   Exit Level:   100% (5/5 values above PF 2.0)
#   Stop %:        80% (4/5 values above PF 2.0)
#   MA Filter:    100% (11/11 values above PF 2.0)
#
# STRATEGY ID: RSI_14_v_final

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ---------------------------------------------------------------------------
# [FUNCTION] calculate_rsi
# ---------------------------------------------------------------------------

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    [FUNCTION] Calculate RSI using Wilder's smoothing method.

    Formula: RSI = 100 - (100 / (1 + RS))
    where RS = average gain / average loss over N periods.

    Wilder's smoothing uses exponential moving average with alpha = 1/period.
    This gives more weight to recent price changes than a simple average.

    Args:
        close  : Series of closing prices
        period : RSI lookback window (optimised: 14 days)

    Returns:
        Series of RSI values between 0 and 100
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
# [FUNCTION] backtest_rsi_final
# ---------------------------------------------------------------------------

def backtest_rsi_final(
    symbol:     str   = 'ETH-USD',
    start:      str   = '2018-01-01',
    rsi_period: int   = 14,
    oversold:   float = 43.0,
    exit_level: float = 48.0,
    stop_pct:   float = 0.15,
    ma_filter:  int   = 120,
) -> dict:
    """
    [FUNCTION] Final RSI mean reversion backtest with confirmed parameters.

    Entry:  RSI < 43 AND Close > 120MA (oversold in bull regime)
    Exit:   RSI > 48 (momentum recovered) OR stop-loss hit
    Stop:   15% below entry price

    The 5-point gap between oversold (43) and exit (48) is critical.
    It gives the trade room to recover before triggering exit,
    filtering out noise and reducing premature exits.

    Args:
        symbol     : yfinance ticker
        start      : backtest start date
        rsi_period : RSI calculation window
        oversold   : RSI buy threshold
        exit_level : RSI exit threshold (must be > oversold)
        stop_pct   : hard stop-loss as fraction of entry price
        ma_filter  : MA period for bull regime filter
    """

    print(f"\nBacktesting RSI FINAL | period={rsi_period} | "
          f"oversold<{oversold} | exit>{exit_level} | "
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
    # 2. Calculate indicators
    # ------------------------------------------------------------------
    # [VARIABLE - Series] RSI values
    df['RSI'] = calculate_rsi(df['Close'], period=rsi_period)

    # [VARIABLE - Series] 120-day MA regime filter
    # Price above this = bull regime = valid mean reversion conditions
    # Price below this = bear regime = avoid buying dips
    df['MA_filter'] = df['Close'].rolling(window=ma_filter).mean()

    df.dropna(inplace=True)

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    # Entry: RSI oversold AND price in bull regime
    df['Entry_Signal'] = (
        (df['RSI'] < oversold) &
        (df['Close'] > df['MA_filter'])
    )

    # Exit: RSI recovered to exit level
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
            # Stop-loss check first
            if low <= stop_price:
                trade_return = (stop_price - entry_price) / entry_price
                trades.append({
                    'strategy_id': 'RSI_14_v_final',
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      trade_return,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            # RSI recovery exit
            elif exit_sig:
                trade_return = (close - entry_price) / entry_price
                trades.append({
                    'strategy_id': 'RSI_14_v_final',
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

    # Kelly criterion
    kelly_b:    float = avg_win / abs(avg_loss) if avg_loss != 0 else 0.0
    kelly_full: float = (
        (win_rate * kelly_b - (1 - win_rate)) / kelly_b
        if kelly_b > 0 else 0.0
    )
    kelly_half: float = kelly_full * 0.5
    kelly_rec:  float = max(0.0, min(kelly_half, 0.25))

    # ------------------------------------------------------------------
    # 7. Print results
    # ------------------------------------------------------------------
    print(f"\n{'='*80}")
    print(f"RSI FINAL BACKTEST RESULTS (RSI_14_v_final)")
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
    print(f"  Recommended:     {kelly_rec:.2%} (capped at 25%)")
    print(f"\nSTABILITY SCORES (from grid search):")
    print(f"  RSI Period:     80%  (4/5 values above PF 2.0)")
    print(f"  Oversold:       67%  (4/6 values above PF 2.0)")
    print(f"  Exit Level:    100%  (5/5 values above PF 2.0)")
    print(f"  Stop %:         80%  (4/5 values above PF 2.0)")
    print(f"  MA Filter:     100%  (11/11 values above PF 2.0)")
    print(f"\nFULL STRATEGY COMPARISON:")
    print(f"  {'Metric':<22} {'ADX 20/10':>12} {'BB v3':>12} {'RSI final':>12}")
    print(f"  {'-'*60}")
    print(f"  {'Win rate':<22} {'34.3%':>12} {'80.8%':>12} {win_rate:>12.1%}")
    print(f"  {'Avg win':<22} {'+24.04%':>12} {'+8.33%':>12} {avg_win:>+12.2%}")
    print(f"  {'Avg loss':<22} {'-3.92%':>12} {'-10.00%':>12} {avg_loss:>+12.2%}")
    print(f"  {'Profit factor':<22} {'3.197':>12} {'3.497':>12} {profit_factor:>12.3f}")
    print(f"  {'Max drawdown':<22} {'-30.3%':>12} {'-19.0%':>12} {max_dd:>12.1%}")
    print(f"  {'Trades/year':<22} {'13.1':>12} {'3.3':>12} {trades_per_year:>12.1f}")
    print(f"  {'Kelly rec':<22} {'11.77%':>12} {'10-12%':>12} {kelly_rec:>12.2%}")
    print(f"  {'Sample size':<22} {'108':>12} {'26':>12} {total_trades:>12}")
    print(f"{'='*80}\n")

    # ------------------------------------------------------------------
    # 8. Save trade log
    # ------------------------------------------------------------------
    os.makedirs('data', exist_ok=True)
    trades_df.to_csv('data/trade_log_rsi_final.csv', index=False)
    print("✅ Trade log saved → data/trade_log_rsi_final.csv")

    # ------------------------------------------------------------------
    # 9. Plots
    # ------------------------------------------------------------------
    os.makedirs('Week_5_Notebooks/results', exist_ok=True)

    fig, axes = plt.subplots(3, 1, figsize=(16, 14))
    fig.suptitle(
        f'RSI Final (RSI_14_v_final) — oversold<{oversold} | '
        f'exit>{exit_level} | stop={stop_pct*100:.0f}% | {ma_filter}MA '
        f'(Week 5 Day 5)',
        fontsize=13, fontweight='bold'
    )

    # --- RSI chart with signals (last 3 years) ---
    cutoff  = df.index[-1] - pd.DateOffset(years=3)
    plot_df = df[df.index >= cutoff]

    axes[0].plot(plot_df.index, plot_df['RSI'],
                 color='purple', linewidth=1.5, label='RSI (14)')
    axes[0].axhline(oversold, color='green', linestyle='--',
                    linewidth=1.5, label=f'Oversold (<{oversold})')
    axes[0].axhline(exit_level, color='blue', linestyle='--',
                    linewidth=1.5, label=f'Exit (>{exit_level})')
    axes[0].axhline(70, color='red', linestyle=':',
                    linewidth=0.8, alpha=0.5, label='Overbought (70)')
    axes[0].axhline(30, color='orange', linestyle=':',
                    linewidth=0.8, alpha=0.5, label='Traditional oversold (30)')
    axes[0].fill_between(
        plot_df.index, plot_df['RSI'], oversold,
        where=plot_df['RSI'] < oversold,
        alpha=0.3, color='green', label='Buy zone'
    )
    axes[0].set_ylim(0, 100)
    axes[0].set_title('RSI Indicator with Entry/Exit Zones (last 3 years)')
    axes[0].set_ylabel('RSI')
    axes[0].legend(fontsize=8, loc='upper left')
    axes[0].grid(alpha=0.3)

    # --- Equity curve ---
    equity_curve = np.concatenate([[1.0], equity])
    axes[1].plot(equity_curve, color='purple',
                 linewidth=2, label='RSI_14_v_final')
    axes[1].axhline(1.0, color='gray', linestyle='--', alpha=0.6)
    axes[1].set_title('Cumulative Equity (per-trade)')
    axes[1].set_ylabel('Equity multiplier')
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    # --- Return distribution ---
    win_returns  = trades_df[trades_df['exit_reason'] == 'RSI_EXIT']['return'] * 100
    loss_returns = trades_df[trades_df['exit_reason'] == 'STOP_LOSS']['return'] * 100

    axes[2].hist(win_returns, bins='auto', alpha=0.7, color='green',
                 edgecolor='black', label=f'RSI exits ({len(win_returns)})')
    axes[2].hist(loss_returns, bins='auto', alpha=0.7, color='crimson',
                 edgecolor='black', label=f'Stop exits ({len(loss_returns)})')
    axes[2].axvline(0, color='black', linewidth=1, alpha=0.5)
    axes[2].set_title('Return Distribution by Exit Type')
    axes[2].set_xlabel('Trade Return (%)')
    axes[2].set_ylabel('Count')
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    plt.tight_layout()
    chart_path = 'Week_5_Notebooks/results/day5_rsi_final.png'
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
    results = backtest_rsi_final(
        symbol='ETH-USD',
        start='2018-01-01',
        rsi_period=14,
        oversold=43.0,
        exit_level=48.0,
        stop_pct=0.15,
        ma_filter=120,
    )