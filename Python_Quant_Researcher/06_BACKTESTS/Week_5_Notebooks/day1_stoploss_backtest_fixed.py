# [MODULE] Day 1 - Stop-Loss Aware Backtest
# Week 5: Resolves A002 (stop-loss not in backtest)
#
# KEY CHANGE vs Week 4:
#   Old: strategy_return = position.shift(1) * market_return
#        → Assumes hold until ADX exit. Never checks stop.
#   New: Iterate bar-by-bar. On each LONG day, check daily LOW vs stop level.
#        If LOW <= stop_price → exit at stop_price (assume filled exactly).
#        Only if stop NOT hit → check ADX exit signal.

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from ta.trend import ADXIndicator
import os

# ---------------------------------------------------------------------------
# [FUNCTION] backtest_with_stoploss
# ---------------------------------------------------------------------------
def backtest_with_stoploss(
    symbol: str = 'ETH-USD',
    start: str = '2018-01-01',
    threshold: int = 20,
    period: int = 10,
    stop_pct: float = 0.05,
) -> dict:
    """
    Backtest ADX strategy with explicit stop-loss logic.

    Stop mechanism:
      - Entry at close of bar where ADX signal fires.
      - Stop set at entry_price * (1 - stop_pct).
      - Each subsequent bar: check if daily LOW breached the stop first,
        before checking ADX exit. This is the conservative (realistic)
        assumption — if intraday low touched stop we assume fill at stop.

    Parameters
    ----------
    symbol    : yfinance ticker (daily OHLCV).
    start     : backtest start date string.
    threshold : ADX level to define 'trending' regime.
    period    : ADX lookback window.
    stop_pct  : hard stop distance as fraction of entry price.

    Returns
    -------
    dict with performance metrics + trades_df DataFrame.
    """

    print(f"\nBacktesting ADX {threshold}/{period} | stop={stop_pct*100:.1f}% | {symbol} from {start}")

    # ------------------------------------------------------------------
    # 1. Fetch data
    # ------------------------------------------------------------------
    # [VARIABLE - DataFrame] raw OHLCV from yfinance
    raw: pd.DataFrame = yf.download(symbol, start=start, interval='1d', progress=False)

    # yfinance ≥0.2 returns MultiIndex columns (Price, Ticker) — flatten if needed
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)

    df: pd.DataFrame = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.dropna(inplace=True)

    # ------------------------------------------------------------------
    # 2. ADX indicators
    # ------------------------------------------------------------------
    adx_ind = ADXIndicator(df['High'], df['Low'], df['Close'], window=period)
    # [VARIABLE - Series] ADX line, +DI, -DI
    df['ADX']  = adx_ind.adx()
    df['+DI']  = adx_ind.adx_pos()
    df['-DI']  = adx_ind.adx_neg()

    # Entry signal: trending AND bullish direction
    df['Trending']     = df['ADX'] >= threshold
    df['Bullish']      = df['+DI'] > df['-DI']
    df['Entry_Signal'] = df['Trending'] & df['Bullish']

    # ------------------------------------------------------------------
    # 3. Bar-by-bar simulation
    # ------------------------------------------------------------------
    # [VARIABLE - int] 0 = FLAT, 1 = LONG
    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0

    # [VARIABLE - list] accumulate trade records
    trades: list = []

    # Convert to numpy for speed in the loop
    closes         = df['Close'].values
    lows           = df['Low'].values
    entry_signals  = df['Entry_Signal'].values
    dates          = df.index

    for i in range(1, len(df)):
        low:    float = lows[i]
        close:  float = closes[i]
        signal: bool  = entry_signals[i]

        if position == 1:
            # --- Check stop-loss FIRST (use daily low) ---
            if low <= stop_price:
                # Stop triggered — assume fill exactly at stop_price
                # (conservative; in practice could gap worse)
                exit_price: float   = stop_price
                trade_return: float = (exit_price - entry_price) / entry_price

                trades.append({
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  exit_price,
                    'return':      trade_return,
                    'exit_reason': 'STOP_LOSS',
                })

                position    = 0
                entry_price = 0.0
                stop_price  = 0.0

            # --- Check ADX exit (only if stop not hit) ---
            elif not signal:
                exit_price    = close
                trade_return  = (exit_price - entry_price) / entry_price

                trades.append({
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  exit_price,
                    'return':      trade_return,
                    'exit_reason': 'ADX_EXIT',
                })

                position    = 0
                entry_price = 0.0
                stop_price  = 0.0

            # else: still holding — no action needed

        elif position == 0 and signal:
            # Enter LONG at today's close
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    # ------------------------------------------------------------------
    # 4. Build trades DataFrame
    # ------------------------------------------------------------------
    # [VARIABLE - DataFrame] all completed trades
    trades_df: pd.DataFrame = pd.DataFrame(trades)

    if trades_df.empty:
        print("⚠️  No trades generated. Check parameters.")
        return {}

    # ------------------------------------------------------------------
    # 5. Performance metrics
    # ------------------------------------------------------------------
    total_trades: int = len(trades_df)

    # Transaction costs: 0.075% per side = 0.15% round-trip
    cost_per_trade:   float = 0.00075 * 2
    total_cost_drag:  float = total_trades * cost_per_trade

    # Returns per trade
    returns: np.ndarray = trades_df['return'].values

    # Gross / net total return (compounded)
    total_return: float = (1 + returns).prod() - 1
    net_return:   float = total_return - total_cost_drag

    # Sharpe — annualised using trade-level returns
    # Note: using sqrt(365) because strategy can hold for many days per trade;
    # this is a rough annualisation. Will revisit with daily equity curve.
    sharpe: float = (
        returns.mean() / returns.std() * np.sqrt(365)
        if returns.std() > 0 else 0.0
    )

    # Sortino — same but only downside deviation
    downside: np.ndarray = returns[returns < 0]
    sortino: float = (
        returns.mean() / downside.std() * np.sqrt(365)
        if len(downside) > 0 and downside.std() > 0 else 0.0
    )

    # Max drawdown — on cumulative equity curve
    equity: np.ndarray = np.cumprod(1 + returns)
    peak:   np.ndarray = np.maximum.accumulate(equity)
    drawdown: np.ndarray = (equity - peak) / peak
    max_dd: float = drawdown.min()

    # Win / loss breakdown
    winners_df = trades_df[trades_df['return'] > 0]
    losers_df  = trades_df[trades_df['return'] <= 0]

    win_rate: float = len(winners_df) / total_trades
    avg_win:  float = winners_df['return'].mean() if len(winners_df) > 0 else 0.0
    avg_loss: float = losers_df['return'].mean()  if len(losers_df)  > 0 else 0.0

    win_loss_ratio: float = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # Profit factor
    gross_profit: float = winners_df['return'].sum() if len(winners_df) > 0 else 0.0
    gross_loss:   float = abs(losers_df['return'].sum()) if len(losers_df) > 0 else 1e-9
    profit_factor: float = gross_profit / gross_loss

    # Exit breakdown
    stop_exits: int = (trades_df['exit_reason'] == 'STOP_LOSS').sum()
    adx_exits:  int = (trades_df['exit_reason'] == 'ADX_EXIT').sum()

    # Date range
    years: float = (df.index[-1] - df.index[0]).days / 365.25
    trades_per_year: float = total_trades / years

    # ------------------------------------------------------------------
    # 6. Print results
    # ------------------------------------------------------------------
    print(f"\n{'='*80}")
    print(f"BACKTEST RESULTS WITH STOP-LOSS")
    print(f"{'='*80}")
    print(f"Strategy:         ADX {threshold}/{period} | stop={stop_pct*100:.1f}%")
    print(f"Period:           {df.index[0].date()} → {df.index[-1].date()}")
    print(f"Days:             {len(df):,}")
    print(f"\nPERFORMANCE:")
    print(f"  Gross Return:   {total_return:+.2%}")
    print(f"  Net Return:     {net_return:+.2%}  (after {cost_per_trade*100:.3f}% round-trip costs)")
    print(f"  Annualised:     {net_return / years:+.2%}/yr  ({years:.1f} yrs)")
    print(f"  Sharpe Ratio:   {sharpe:.3f}")
    print(f"  Sortino Ratio:  {sortino:.3f}")
    print(f"  Profit Factor:  {profit_factor:.3f}")
    print(f"  Max Drawdown:   {max_dd:.2%}")
    print(f"\nTRADING STATS:")
    print(f"  Total Trades:   {total_trades}")
    print(f"  Trades/Year:    {trades_per_year:.1f}")
    print(f"  Winners:        {len(winners_df)} ({win_rate:.1%} win rate)")
    print(f"  Losers:         {len(losers_df)}")
    print(f"  Avg Win:        {avg_win:+.2%}")
    print(f"  Avg Loss:       {avg_loss:+.2%}")
    print(f"  Win/Loss Ratio: {win_loss_ratio:.2f}x")
    print(f"\nEXIT BREAKDOWN:")
    print(f"  Stop-loss:      {stop_exits} ({stop_exits/total_trades:.1%} of trades)")
    print(f"  ADX signal:     {adx_exits} ({adx_exits/total_trades:.1%} of trades)")
    print(f"\nCOMPARISON TO WEEK 4 (no stop-loss):")
    print(f"  {'Metric':<22} {'Week 4':>12} {'Week 5':>12} {'Δ':>10}")
    print(f"  {'-'*58}")
    print(f"  {'Sharpe':<22} {'1.111':>12} {sharpe:>12.3f} {sharpe-1.111:>+10.3f}")
    print(f"  {'Win rate':<22} {'37.5%':>12} {win_rate:>12.1%} {(win_rate-0.375)*100:>+9.1f}pp")
    print(f"  {'Profit factor':<22} {'2.71x':>12} {profit_factor:>11.3f}x {'':>10}")
    print(f"{'='*80}\n")

    # ------------------------------------------------------------------
    # 7. Save trade log
    # ------------------------------------------------------------------
    os.makedirs('data', exist_ok=True)
    trades_df.to_csv('data/trade_log_with_stoploss.csv', index=False)
    print("✅ Trade log saved → data/trade_log_with_stoploss.csv")

    # ------------------------------------------------------------------
    # 8. Plots
    # ------------------------------------------------------------------
    os.makedirs('Week_5_Notebooks/results', exist_ok=True)

    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    fig.suptitle(f'ADX {threshold}/{period} — Stop-Loss Backtest (Week 5)', fontsize=14, fontweight='bold')

    # --- 8a. Equity curve ---
    equity_curve = np.concatenate([[1.0], equity])
    axes[0].plot(equity_curve, color='steelblue', linewidth=1.5, label='Equity curve')
    axes[0].axhline(1.0, color='gray', linestyle='--', alpha=0.6, label='Start')
    axes[0].set_title('Cumulative Equity (per-trade, log scale)')
    axes[0].set_ylabel('Equity multiplier')
    axes[0].set_yscale('log')
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    # --- 8b. Drawdown ---
    axes[1].fill_between(range(len(drawdown)), drawdown * 100, 0,
                         color='crimson', alpha=0.5, label='Drawdown')
    axes[1].set_title('Drawdown (%)')
    axes[1].set_ylabel('Drawdown %')
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    # --- 8c. Return distribution with stop vs ADX colour coding ---
    stop_returns = trades_df[trades_df['exit_reason'] == 'STOP_LOSS']['return']
    adx_returns  = trades_df[trades_df['exit_reason'] == 'ADX_EXIT']['return']

    axes[2].hist(stop_returns * 100, bins='auto', alpha=0.7, color='crimson',
                 edgecolor='black', label=f'Stop-loss exits ({len(stop_returns)})')
    axes[2].hist(adx_returns * 100, bins='auto', alpha=0.7, color='steelblue',
                 edgecolor='black', label=f'ADX exits ({len(adx_returns)})')
    axes[2].axvline(-stop_pct * 100, color='orange', linestyle='--', linewidth=2,
                    label=f'Stop level ({-stop_pct*100:.0f}%)')
    axes[2].axvline(0, color='black', linestyle='-', alpha=0.4)
    axes[2].set_title('Return Distribution by Exit Type')
    axes[2].set_xlabel('Trade Return (%)')
    axes[2].set_ylabel('Count')
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    plt.tight_layout()
    chart_path = 'Week_5_Notebooks/results/day1_stoploss_backtest.png'
    plt.savefig(chart_path, dpi=150)
    print(f"✅ Chart saved → {chart_path}")
    plt.close()

    return {
        'total_return':   total_return,
        'net_return':     net_return,
        'sharpe':         sharpe,
        'sortino':        sortino,
        'max_drawdown':   max_dd,
        'profit_factor':  profit_factor,
        'total_trades':   total_trades,
        'win_rate':       win_rate,
        'avg_win':        avg_win,
        'avg_loss':       avg_loss,
        'win_loss_ratio': win_loss_ratio,
        'stop_exits':     stop_exits,
        'adx_exits':      adx_exits,
        'trades_df':      trades_df,
    }


# ---------------------------------------------------------------------------
# [ENTRY POINT]
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    results = backtest_with_stoploss(
        symbol='ETH-USD',
        start='2018-01-01',
        threshold=20,
        period=10,
        stop_pct=0.05,
    )