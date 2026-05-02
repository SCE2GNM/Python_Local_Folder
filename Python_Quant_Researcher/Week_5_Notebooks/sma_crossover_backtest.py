# [MODULE] SMA Crossover Backtest — ETH and BTC
# Week 5 Extension
#
# STRATEGY:
#   Buy when daily close crosses ABOVE the N-day SMA
#   Sell when daily close crosses BELOW the N-day SMA
#   No separate stop-loss — SMA cross below is the exit
#
# OPTIMISATION:
#   Grid search across SMA periods 10-200 (step 5)
#   Ranked by Calmar ratio (most reliable metric)
#
# SHARPE/SORTINO FIX:
#   All risk metrics calculated on DAILY equity curve
#   (one value per calendar day, not per trade)
#   This produces honest, comparable figures.
#
# COMPARISON:
#   ETH SMA optimal vs BTC SMA optimal vs ADX strategies

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ---------------------------------------------------------------------------
# [FUNCTION] build_daily_equity_curve
# ---------------------------------------------------------------------------

def build_daily_equity_curve(
    df:      pd.DataFrame,
    trades:  list,
    initial: float = 1.0,
) -> np.ndarray:
    """
    [FUNCTION] Build a daily equity curve from a list of trades.

    For each calendar day in df:
      - If in a position: value = initial * (current_close / entry_price)
      - If flat (in cash): value stays at last exit value

    This produces one equity value per day — the correct input
    for Sharpe and Sortino calculations.

    Args:
        df      : full OHLCV DataFrame (all calendar days)
        trades  : list of trade dicts with entry_date, exit_date,
                  entry_price, exit_price
        initial : starting portfolio value (default 1.0)

    Returns:
        np.ndarray of daily equity values
    """
    if len(trades) == 0:
        return np.ones(len(df))

    trades_df = pd.DataFrame(trades)
    trades_df['entry_date'] = pd.to_datetime(trades_df['entry_date'])
    trades_df['exit_date']  = pd.to_datetime(trades_df['exit_date'])

    equity      = np.ones(len(df))
    portfolio   = initial
    trade_idx   = 0
    in_position = False
    entry_price = 0.0
    entry_value = 0.0

    for i, (date, row) in enumerate(df.iterrows()):
        # Check if a new trade starts today
        if (not in_position and
            trade_idx < len(trades_df) and
            date >= trades_df.iloc[trade_idx]['entry_date']):

            in_position = True
            entry_price = trades_df.iloc[trade_idx]['entry_price']
            entry_value = portfolio

        if in_position:
            # Mark to market using today's close
            current_return = (row['Close'] - entry_price) / entry_price
            equity[i]      = entry_value * (1 + current_return)

            # Check if trade exits today
            if (trade_idx < len(trades_df) and
                date >= trades_df.iloc[trade_idx]['exit_date']):

                portfolio   = entry_value * (
                    1 + trades_df.iloc[trade_idx]['return']
                )
                in_position = False
                trade_idx  += 1
                equity[i]   = portfolio
        else:
            equity[i] = portfolio

    return equity


# ---------------------------------------------------------------------------
# [FUNCTION] calculate_metrics_from_daily_equity
# ---------------------------------------------------------------------------

def calculate_metrics_from_daily_equity(
    equity: np.ndarray,
    years:  float,
    label:  str,
) -> dict:
    """
    [FUNCTION] Calculate all performance metrics from a daily equity curve.

    This is the CORRECT way to calculate Sharpe and Sortino —
    using daily returns from a daily equity curve, then annualising
    with sqrt(365).

    Args:
        equity : array of daily portfolio values
        years  : total period length in years
        label  : strategy name

    Returns:
        dict of performance metrics
    """
    # [VARIABLE - ndarray] daily percentage returns
    daily_returns: np.ndarray = np.diff(equity) / equity[:-1]

    total_return  = equity[-1] / equity[0] - 1
    annual_return = (1 + total_return) ** (1 / years) - 1

    # Sharpe — daily returns annualised correctly with sqrt(365)
    sharpe: float = (
        daily_returns.mean() / daily_returns.std() * np.sqrt(365)
        if daily_returns.std() > 0 else 0.0
    )

    # Sortino — only penalises downside daily returns
    downside: np.ndarray = daily_returns[daily_returns < 0]
    sortino: float = (
        daily_returns.mean() / downside.std() * np.sqrt(365)
        if len(downside) > 0 and downside.std() > 0 else 0.0
    )

    # Max drawdown
    peak:     np.ndarray = np.maximum.accumulate(equity)
    drawdown: np.ndarray = (equity - peak) / peak
    max_dd:   float      = drawdown.min()

    # Calmar
    calmar: float = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    return {
        'label':         label,
        'total_return':  total_return,
        'annual_return': annual_return,
        'sharpe':        sharpe,
        'sortino':       sortino,
        'max_drawdown':  max_dd,
        'calmar':        calmar,
        'equity':        equity,
        'drawdown':      drawdown,
        'daily_returns': daily_returns,
    }


# ---------------------------------------------------------------------------
# [FUNCTION] run_sma_backtest
# ---------------------------------------------------------------------------

def run_sma_backtest(
    df:         pd.DataFrame,
    sma_period: int,
) -> dict:
    """
    [FUNCTION] Run SMA crossover backtest for a single period value.

    Entry:  Close crosses above SMA (today close > SMA, yesterday close < SMA)
    Exit:   Close crosses below SMA (today close < SMA, yesterday close > SMA)

    Uses a strict crossover (not just above/below) to avoid
    re-entering immediately after exit on flat markets.

    Args:
        df         : OHLCV DataFrame
        sma_period : SMA lookback period

    Returns:
        dict of metrics, or None if fewer than 5 trades
    """
    # [VARIABLE - Series] N-day simple moving average
    sma: pd.Series = df['Close'].rolling(window=sma_period).mean()

    position:    int   = 0
    entry_price: float = 0.0
    trades:      list  = []

    closes = df['Close'].values
    smas   = sma.values
    dates  = df.index

    for i in range(sma_period + 1, len(df)):
        close:      float = closes[i]
        close_prev: float = closes[i - 1]
        sma_val:    float = smas[i]
        sma_prev:   float = smas[i - 1]

        if np.isnan(sma_val) or np.isnan(sma_prev):
            continue

        if position == 1:
            # Exit: close crosses below SMA
            if close < sma_val and close_prev >= sma_prev:
                trade_return = (close - entry_price) / entry_price
                trades.append({
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                })
                position    = 0
                entry_price = 0.0

        elif position == 0:
            # Entry: close crosses above SMA
            if close > sma_val and close_prev <= sma_prev:
                entry_price = close
                position    = 1

    # Close any open position at end of data
    if position == 1:
        trade_return = (closes[-1] - entry_price) / entry_price
        trades.append({
            'entry_date':  dates[-2],
            'entry_price': entry_price,
            'exit_date':   dates[-1],
            'exit_price':  closes[-1],
            'return':      trade_return,
        })

    if len(trades) < 5:
        return None

    trades_df = pd.DataFrame(trades)
    returns   = np.array([t['return'] for t in trades])

    winners = trades_df[trades_df['return'] > 0]
    losers  = trades_df[trades_df['return'] <= 0]

    win_rate      = len(winners) / len(trades_df)
    gross_profit  = winners['return'].sum() if len(winners) > 0 else 0.0
    gross_loss    = abs(losers['return'].sum()) if len(losers) > 0 else 1e-9
    profit_factor = gross_profit / gross_loss

    total_return  = (1 + returns).prod() - 1
    years         = (df.index[-1] - df.index[0]).days / 365.25
    annual_return = (1 + total_return) ** (1 / years) - 1

    # Build daily equity curve for correct Sharpe/Sortino
    daily_equity  = build_daily_equity_curve(df, trades)
    daily_metrics = calculate_metrics_from_daily_equity(
        daily_equity, years, f'SMA {sma_period}'
    )

    max_dd = daily_metrics['max_drawdown']
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    return {
        'sma_period':    sma_period,
        'total_trades':  len(trades_df),
        'win_rate':      win_rate,
        'avg_win':       winners['return'].mean() if len(winners) > 0 else 0.0,
        'avg_loss':      losers['return'].mean()  if len(losers)  > 0 else 0.0,
        'profit_factor': profit_factor,
        'total_return':  total_return,
        'annual_return': annual_return,
        'max_drawdown':  max_dd,
        'calmar':        calmar,
        'sharpe':        daily_metrics['sharpe'],
        'sortino':       daily_metrics['sortino'],
        'daily_equity':  daily_equity,
        'trades':        trades,
    }


# ---------------------------------------------------------------------------
# FETCH DATA
# ---------------------------------------------------------------------------

print("\nFetching data...")
results = {}

for symbol, name in [('ETH-USD', 'ETH'), ('BTC-USD', 'BTC')]:
    raw = yf.download(symbol, start='2018-01-01', interval='1d', progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)
    df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.dropna(inplace=True)
    print(f"  {name}: {df.index[0].date()} → {df.index[-1].date()} "
          f"({len(df):,} days)")
    results[name] = {'df': df}


# ---------------------------------------------------------------------------
# GRID SEARCH — SMA periods 10 to 200 step 5
# ---------------------------------------------------------------------------

sma_periods = list(range(10, 205, 5))   # 39 values
print(f"\nTesting {len(sma_periods)} SMA periods (10 to 200, step 5)...")

for name in ['ETH', 'BTC']:
    df          = results[name]['df']
    grid_results = []

    for period in sma_periods:
        r = run_sma_backtest(df, period)
        if r is not None:
            grid_results.append(r)

    ranked = sorted(grid_results, key=lambda x: x['calmar'], reverse=True)
    results[name]['grid']  = grid_results
    results[name]['ranked'] = ranked
    results[name]['best']  = ranked[0]

    print(f"\n  {name} — best SMA period: {ranked[0]['sma_period']} "
          f"(Calmar: {ranked[0]['calmar']:.3f})")


# ---------------------------------------------------------------------------
# PRINT RESULTS
# ---------------------------------------------------------------------------

print(f"\n{'='*90}")
print(f"SMA CROSSOVER OPTIMISATION RESULTS")
print(f"{'='*90}")

for name in ['ETH', 'BTC']:
    ranked = results[name]['ranked']
    print(f"\n  {name} — TOP 10 SMA PERIODS (ranked by Calmar ratio)")
    print(f"  {'SMA':>6} {'Trades':>8} {'Win Rate':>10} {'PF':>8} "
          f"{'Annual':>10} {'Max DD':>10} {'Calmar':>8} {'Sharpe':>8} {'Sortino':>8}")
    print(f"  {'-'*82}")

    for r in ranked[:10]:
        print(f"  {r['sma_period']:>6} {r['total_trades']:>8} "
              f"{r['win_rate']:>10.1%} {r['profit_factor']:>8.3f} "
              f"{r['annual_return']:>10.1%} {r['max_drawdown']:>10.1%} "
              f"{r['calmar']:>8.3f} {r['sharpe']:>8.3f} {r['sortino']:>8.3f}")


# ---------------------------------------------------------------------------
# SIDE-BY-SIDE BEST SMA vs ADX COMPARISON
# ---------------------------------------------------------------------------

eth_best = results['ETH']['best']
btc_best = results['BTC']['best']

# ADX reference values (from Week 5)
adx_eth = {
    'label': 'ADX ETH 20/10',
    'annual_return': 0.674, 'max_drawdown': -0.303,
    'calmar': 2.222, 'profit_factor': 3.197,
    'win_rate': 0.343, 'total_trades': 108,
    'sharpe': None,  # not calculated correctly previously
}
adx_btc = {
    'label': 'ADX BTC 19/14',
    'annual_return': 0.453, 'max_drawdown': -0.404,
    'calmar': 1.121, 'profit_factor': 3.402,
    'win_rate': 0.272, 'total_trades': 103,
    'sharpe': None,
}

print(f"\n{'='*90}")
print(f"SMA vs ADX — SIDE BY SIDE COMPARISON")
print(f"{'='*90}")
print(f"\n  {'Metric':<22} "
      f"{'ETH SMA '+str(eth_best['sma_period']):>16} "
      f"{'ETH ADX 20/10':>16} "
      f"{'BTC SMA '+str(btc_best['sma_period']):>16} "
      f"{'BTC ADX 19/14':>16}")
print(f"  {'-'*88}")

comparison_rows = [
    ('Annual Return',
     f"{eth_best['annual_return']:+.1%}",
     f"{adx_eth['annual_return']:+.1%}",
     f"{btc_best['annual_return']:+.1%}",
     f"{adx_btc['annual_return']:+.1%}"),
    ('Max Drawdown',
     f"{eth_best['max_drawdown']:.1%}",
     f"{adx_eth['max_drawdown']:.1%}",
     f"{btc_best['max_drawdown']:.1%}",
     f"{adx_btc['max_drawdown']:.1%}"),
    ('Calmar Ratio',
     f"{eth_best['calmar']:.3f}",
     f"{adx_eth['calmar']:.3f}",
     f"{btc_best['calmar']:.3f}",
     f"{adx_btc['calmar']:.3f}"),
    ('Profit Factor',
     f"{eth_best['profit_factor']:.3f}",
     f"{adx_eth['profit_factor']:.3f}",
     f"{btc_best['profit_factor']:.3f}",
     f"{adx_btc['profit_factor']:.3f}"),
    ('Win Rate',
     f"{eth_best['win_rate']:.1%}",
     f"{adx_eth['win_rate']:.1%}",
     f"{btc_best['win_rate']:.1%}",
     f"{adx_btc['win_rate']:.1%}"),
    ('Total Trades',
     f"{eth_best['total_trades']}",
     f"{adx_eth['total_trades']}",
     f"{btc_best['total_trades']}",
     f"{adx_btc['total_trades']}"),
    ('Sharpe (daily)',
     f"{eth_best['sharpe']:.3f}",
     "recalc needed",
     f"{btc_best['sharpe']:.3f}",
     "recalc needed"),
    ('Sortino (daily)',
     f"{eth_best['sortino']:.3f}",
     "recalc needed",
     f"{btc_best['sortino']:.3f}",
     "recalc needed"),
]

for row in comparison_rows:
    print(f"  {row[0]:<22} {row[1]:>16} {row[2]:>16} {row[3]:>16} {row[4]:>16}")

print(f"\n  NOTE: ADX Sharpe/Sortino marked 'recalc needed' — previously")
print(f"  calculated using per-trade returns (incorrect). Will recalculate")
print(f"  using daily equity curve in a follow-up script.")


# ---------------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------------

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle(
    'SMA Crossover Optimisation — ETH and BTC\n'
    'Daily equity curve used for Sharpe/Sortino (correct method)',
    fontsize=13, fontweight='bold'
)

for row_idx, name in enumerate(['ETH', 'BTC']):
    grid    = results[name]['grid']
    ranked  = results[name]['ranked']
    best    = results[name]['best']
    df      = results[name]['df']
    years   = (df.index[-1] - df.index[0]).days / 365.25

    # --- Calmar vs SMA period ---
    periods = [r['sma_period'] for r in grid]
    calmars = [r['calmar']     for r in grid]
    sharpes = [r['sharpe']     for r in grid]

    axes[row_idx][0].plot(periods, calmars,
                          color='steelblue' if name == 'ETH' else 'orange',
                          linewidth=2)
    axes[row_idx][0].axvline(best['sma_period'], color='gold',
                              linewidth=2, linestyle='--',
                              label=f"Best: SMA {best['sma_period']}")
    axes[row_idx][0].axhline(0, color='red', linestyle=':', alpha=0.5)
    axes[row_idx][0].set_title(f'{name} — Calmar by SMA Period')
    axes[row_idx][0].set_xlabel('SMA Period (days)')
    axes[row_idx][0].set_ylabel('Calmar Ratio')
    axes[row_idx][0].legend(fontsize=8)
    axes[row_idx][0].grid(alpha=0.3)

    # --- Sharpe vs SMA period ---
    axes[row_idx][1].plot(periods, sharpes,
                          color='green' if name == 'ETH' else 'purple',
                          linewidth=2)
    axes[row_idx][1].axvline(best['sma_period'], color='gold',
                              linewidth=2, linestyle='--',
                              label=f"Best: SMA {best['sma_period']}")
    axes[row_idx][1].axhline(0, color='red', linestyle=':', alpha=0.5)
    axes[row_idx][1].set_title(f'{name} — Sharpe by SMA Period')
    axes[row_idx][1].set_xlabel('SMA Period (days)')
    axes[row_idx][1].set_ylabel('Sharpe Ratio (daily, annualised)')
    axes[row_idx][1].legend(fontsize=8)
    axes[row_idx][1].grid(alpha=0.3)

    # --- Best SMA equity curve vs buy and hold ---
    best_equity = best['daily_equity']
    bh_equity   = df['Close'].values / df['Close'].iloc[0]

    axes[row_idx][2].plot(best_equity, linewidth=2,
                          color='steelblue' if name == 'ETH' else 'orange',
                          label=f"SMA {best['sma_period']} "
                                f"(${best_equity[-1]*1000:,.0f})")
    axes[row_idx][2].plot(bh_equity, linewidth=1.5, linestyle='--',
                          color='gray', alpha=0.7,
                          label=f"Buy & Hold "
                                f"(${bh_equity[-1]*1000:,.0f})")
    axes[row_idx][2].axhline(1.0, color='gray', linestyle=':', alpha=0.4)
    axes[row_idx][2].set_title(f'{name} — Best SMA vs Buy & Hold')
    axes[row_idx][2].set_ylabel('Portfolio value ($1,000 start)')
    axes[row_idx][2].legend(fontsize=8)
    axes[row_idx][2].grid(alpha=0.3)

plt.tight_layout()
chart_path = 'Week_5_Notebooks/results/sma_crossover_optimisation.png'
plt.savefig(chart_path, dpi=150)
plt.close()
print(f"\n✅ Chart saved → {chart_path}")

print(f"\n{'='*90}")
print(f"SMA CROSSOVER BACKTEST COMPLETE")
print(f"{'='*90}\n")