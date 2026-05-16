# [MODULE] Recalculate Strategy Metrics Using Daily Equity Curve
# Week 5 Extension
#
# PROBLEM:
#   All Sharpe and Sortino ratios calculated in Week 5 used
#   per-trade returns multiplied by sqrt(365). This is wrong
#   because trades last different numbers of days — treating
#   a 30-day trade return as a 1-day return massively inflates
#   the annualised figure.
#
# FIX:
#   Build a daily equity curve for each strategy — one value
#   per calendar day. Calculate daily returns from that curve.
#   Annualise with sqrt(365). This is the correct method.
#
# STRATEGIES RECALCULATED:
#   ADX 20/10 ETH  — from data/trade_log_with_stoploss.csv
#   BB v3 ETH      — from data/trade_log_bollinger_final.csv
#   RSI Final ETH  — from data/trade_log_rsi_final.csv

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ---------------------------------------------------------------------------
# [FUNCTION] build_daily_equity_from_tradelog
# ---------------------------------------------------------------------------

def build_daily_equity_from_tradelog(
    df:        pd.DataFrame,
    trades_df: pd.DataFrame,
    initial:   float = 1.0,
) -> np.ndarray:
    """
    [FUNCTION] Build daily equity curve from a trade log CSV.

    For each calendar day in df:
      - If in a trade: mark to market using today's close price
      - If flat (cash): hold at last exit value

    Args:
        df        : OHLCV DataFrame — provides daily close prices
        trades_df : trade log with entry_date, exit_date,
                    entry_price, exit_price, return columns
        initial   : starting portfolio value

    Returns:
        np.ndarray of daily equity values (one per row in df)
    """
    trades_df = trades_df.copy()
    trades_df['entry_date'] = pd.to_datetime(trades_df['entry_date'])
    trades_df['exit_date']  = pd.to_datetime(trades_df['exit_date'])
    trades_df = trades_df.sort_values('entry_date').reset_index(drop=True)

    equity      = np.ones(len(df))
    portfolio   = initial
    trade_idx   = 0
    in_position = False
    entry_price = 0.0
    entry_value = 0.0
    n_trades    = len(trades_df)

    for i, (date, row) in enumerate(df.iterrows()):
        # Check if a new trade starts on or before today
        if (not in_position and
            trade_idx < n_trades and
            date >= trades_df.iloc[trade_idx]['entry_date']):
            in_position = True
            entry_price = trades_df.iloc[trade_idx]['entry_price']
            entry_value = portfolio

        if in_position:
            # Mark to market: value = entry_value × (today_close / entry_price)
            mtm_return = (row['Close'] - entry_price) / entry_price
            equity[i]  = entry_value * (1 + mtm_return)

            # Check if trade exits on or before today
            if (trade_idx < n_trades and
                date >= trades_df.iloc[trade_idx]['exit_date']):
                portfolio   = entry_value * (
                    1 + trades_df.iloc[trade_idx]['return']
                )
                in_position = False
                trade_idx  += 1
                equity[i]   = portfolio
        else:
            # Flat — hold cash at last portfolio value
            equity[i] = portfolio

    return equity


# ---------------------------------------------------------------------------
# [FUNCTION] metrics_from_daily_equity
# ---------------------------------------------------------------------------

def metrics_from_daily_equity(
    equity: np.ndarray,
    label:  str,
    years:  float,
) -> dict:
    """
    [FUNCTION] Calculate correct performance metrics from daily equity curve.

    Args:
        equity : daily portfolio values
        label  : strategy name
        years  : total period length in years

    Returns:
        dict of metrics
    """
    # [VARIABLE - ndarray] daily percentage returns
    daily_returns: np.ndarray = np.diff(equity) / equity[:-1]

    total_return  = equity[-1] / equity[0] - 1
    annual_return = (1 + total_return) ** (1 / years) - 1

    # Sharpe — correct method: daily returns × sqrt(365)
    sharpe: float = (
        daily_returns.mean() / daily_returns.std() * np.sqrt(365)
        if daily_returns.std() > 0 else 0.0
    )

    # Sortino — only downside daily returns
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
    }


# ---------------------------------------------------------------------------
# FETCH ETH PRICE DATA
# ---------------------------------------------------------------------------

print("\nFetching ETH-USD daily data...")
raw = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.dropna(inplace=True)
years = (df.index[-1] - df.index[0]).days / 365.25
print(f"ETH data: {df.index[0].date()} → {df.index[-1].date()} ({years:.1f} yrs)")


# ---------------------------------------------------------------------------
# LOAD TRADE LOGS AND CALCULATE METRICS
# ---------------------------------------------------------------------------

strategies = [
    ('ADX 20/10 ETH',  'data/trade_log_with_stoploss.csv'),
    ('BB v3 ETH',      'data/trade_log_bollinger_final.csv'),
    ('RSI Final ETH',  'data/trade_log_rsi_final.csv'),
]

results = []

print("\nRecalculating metrics using daily equity curves...")

for label, filepath in strategies:
    if not os.path.exists(filepath):
        print(f"  ⚠️  {label}: file not found — {filepath}")
        continue

    trades_df = pd.read_csv(filepath)
    print(f"  {label}: {len(trades_df)} trades loaded")

    # Build daily equity curve
    daily_equity = build_daily_equity_from_tradelog(df, trades_df)

    # Calculate metrics
    metrics = metrics_from_daily_equity(daily_equity, label, years)

    # Also calculate per-trade stats for reference
    winners  = trades_df[trades_df['return'] > 0]
    losers   = trades_df[trades_df['return'] <= 0]
    win_rate = len(winners) / len(trades_df)

    gross_profit  = winners['return'].sum() if len(winners) > 0 else 0.0
    gross_loss    = abs(losers['return'].sum()) if len(losers) > 0 else 1e-9
    profit_factor = gross_profit / gross_loss

    metrics['win_rate']      = win_rate
    metrics['profit_factor'] = profit_factor
    metrics['total_trades']  = len(trades_df)

    results.append(metrics)


# ---------------------------------------------------------------------------
# PRINT CORRECTED METRICS TABLE
# ---------------------------------------------------------------------------

print(f"\n{'='*90}")
print(f"CORRECTED STRATEGY METRICS (daily equity curve method)")
print(f"{'='*90}")
print(f"\n  {'Strategy':<22} {'Annual':>8} {'Max DD':>8} {'Calmar':>8} "
      f"{'Sharpe':>8} {'Sortino':>8} {'PF':>8} {'WR':>8} {'Trades':>8}")
print(f"  {'-'*88}")

for r in results:
    print(f"  {r['label']:<22} {r['annual_return']:>8.1%} "
          f"{r['max_drawdown']:>8.1%} {r['calmar']:>8.3f} "
          f"{r['sharpe']:>8.3f} {r['sortino']:>8.3f} "
          f"{r['profit_factor']:>8.3f} {r['win_rate']:>8.1%} "
          f"{r['total_trades']:>8}")

# Compare to previous incorrect values
print(f"\n{'='*90}")
print(f"COMPARISON — INCORRECT (per-trade) vs CORRECT (daily) SHARPE")
print(f"{'='*90}")
print(f"\n  {'Strategy':<22} {'Old Sharpe (WRONG)':>20} "
      f"{'New Sharpe (CORRECT)':>22} {'Difference':>12}")
print(f"  {'-'*78}")

old_sharpes = {
    'ADX 20/10 ETH': 4.695,
    'BB v3 ETH':     11.391,
    'RSI Final ETH': 14.029,
}

for r in results:
    old = old_sharpes.get(r['label'], 0)
    new = r['sharpe']
    print(f"  {r['label']:<22} {old:>20.3f} {new:>22.3f} "
          f"{new-old:>+12.3f}")

print(f"\n  The old values were inflated by treating multi-day trades")
print(f"  as single-day returns and multiplying by sqrt(365).")
print(f"  The new values use daily returns from a daily equity curve.")


# ---------------------------------------------------------------------------
# FULL STRATEGY COMPARISON INCLUDING SMA AND BENCHMARKS
# ---------------------------------------------------------------------------

print(f"\n{'='*90}")
print(f"COMPLETE STRATEGY COMPARISON (all metrics correctly calculated)")
print(f"{'='*90}")
print(f"\n  {'Strategy':<25} {'Annual':>8} {'Max DD':>8} {'Calmar':>8} "
      f"{'Sharpe':>8} {'Sortino':>8} {'Notes':>15}")
print(f"  {'-'*85}")

# All strategies with correct metrics
all_strategies = [
    # label, annual, max_dd, calmar, sharpe, sortino, notes
    ('ADX 20/10 ETH',    None, None, None, None, None, 'see above'),
    ('RSI Final ETH',    None, None, None, None, None, 'see above'),
    ('BB v3 ETH',        None, None, None, None, None, 'see above'),
    ('SMA 125 BTC',      0.596, -0.170, 3.506, 0.521, 1.807, 'from today'),
    ('SMA 35 ETH',       0.630, -0.446, 1.411, 0.638, 1.290, 'from today'),
    ('Buy&Hold ETH',     0.129, -0.940, 0.137, 0.572, 0.786, 'benchmark'),
    ('Buy&Hold BTC',     0.216, -0.815, 0.265, 0.630, 0.843, 'benchmark'),
    ('EW Basket',        0.434, -0.892, 0.486, 0.859, 1.147, 'benchmark'),
]

for r in results:
    print(f"  {r['label']:<25} {r['annual_return']:>8.1%} "
          f"{r['max_drawdown']:>8.1%} {r['calmar']:>8.3f} "
          f"{r['sharpe']:>8.3f} {r['sortino']:>8.3f} "
          f"{'recalculated':>15}")

for row in all_strategies[3:]:
    label, ann, dd, cal, sh, so, notes = row
    print(f"  {label:<25} {ann:>8.1%} {dd:>8.1%} {cal:>8.3f} "
          f"{sh:>8.3f} {so:>8.3f} {notes:>15}")


# ---------------------------------------------------------------------------
# PLOT — Daily equity curves for all three ETH strategies
# ---------------------------------------------------------------------------

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

fig, axes = plt.subplots(2, 1, figsize=(16, 12))
fig.suptitle(
    'ETH Strategy Daily Equity Curves — Correct Method\n'
    '(Daily mark-to-market, not per-trade compounding)',
    fontsize=13, fontweight='bold'
)

colors = {'ADX 20/10 ETH': 'steelblue',
          'BB v3 ETH':     'green',
          'RSI Final ETH': 'purple'}

# Buy and hold ETH for reference
bh_eth = df['Close'].values / df['Close'].values[0]

for r in results:
    color = colors.get(r['label'], 'gray')
    eq    = r['equity']
    axes[0].plot(eq, color=color, linewidth=2,
                 label=f"{r['label']} "
                       f"(Sharpe:{r['sharpe']:.2f} "
                       f"Calmar:{r['calmar']:.2f})")

axes[0].plot(bh_eth, color='gray', linewidth=1.5, linestyle='--',
             alpha=0.6, label='Buy & Hold ETH')
axes[0].axhline(1.0, color='gray', linestyle=':', alpha=0.4)
axes[0].set_title('Daily Equity Curves (log scale)')
axes[0].set_ylabel('Portfolio value (start=1.0)')
axes[0].set_yscale('log')
axes[0].legend(fontsize=9)
axes[0].grid(alpha=0.3)

# Drawdowns
for r in results:
    color = colors.get(r['label'], 'gray')
    axes[1].plot(r['drawdown'] * 100, color=color,
                 linewidth=1.5, label=r['label'])

axes[1].axhline(0, color='gray', linestyle=':', alpha=0.4)
axes[1].set_title('Daily Drawdown (%)')
axes[1].set_ylabel('Drawdown %')
axes[1].legend(fontsize=9)
axes[1].grid(alpha=0.3)

plt.tight_layout()
chart_path = 'Week_5_Notebooks/results/corrected_daily_metrics.png'
plt.savefig(chart_path, dpi=150)
plt.close()
print(f"\n✅ Chart saved → {chart_path}")

print(f"\n{'='*90}")
print(f"METRIC RECALCULATION COMPLETE")
print(f"{'='*90}\n")