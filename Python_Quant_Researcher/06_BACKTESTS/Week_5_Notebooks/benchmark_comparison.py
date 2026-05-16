# [MODULE] Benchmark Comparison
# Week 5
#
# WHAT THIS SCRIPT DOES:
#   Compares all three trading strategies against passive benchmarks.
#   Benchmarks represent what you'd have made doing nothing active.
#
# BENCHMARKS:
#   1. Buy & Hold ETH        — direct comparison for ADX/BB/RSI strategies
#   2. Buy & Hold BTC        — crypto market benchmark
#   3. Equal-weight basket   — BTC, ETH, BNB, SOL, ADA (rebalanced monthly)
#   4. 60/40 BTC/ETH         — simple two-asset portfolio
#
# STRATEGIES (from Week 5):
#   ADX 20/10  — trend following, 108 trades, PF 3.197
#   BB v3      — mean reversion, 26 trades, PF 3.497
#   RSI final  — mean reversion, 31 trades, PF 5.593
#
# KEY QUESTION:
#   Do our strategies outperform simply buying and holding on a
#   risk-adjusted basis? If not, the complexity is not justified.

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from ta.trend import ADXIndicator

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta    = close.diff()
    gains    = delta.clip(lower=0)
    losses   = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def performance_metrics(
    equity_curve: np.ndarray,
    label: str,
    years: float,
) -> dict:
    """
    [FUNCTION] Calculate standard performance metrics from an equity curve.

    Args:
        equity_curve : array of portfolio values (starting at 1.0)
        label        : strategy name for reporting
        years        : length of period in years

    Returns:
        dict of metrics
    """
    returns = np.diff(equity_curve) / equity_curve[:-1]

    total_return   = equity_curve[-1] / equity_curve[0] - 1
    annual_return  = (1 + total_return) ** (1 / years) - 1

    # Daily Sharpe (annualised with sqrt(365))
    sharpe = (
        returns.mean() / returns.std() * np.sqrt(365)
        if returns.std() > 0 else 0.0
    )

    # Sortino
    downside = returns[returns < 0]
    sortino = (
        returns.mean() / downside.std() * np.sqrt(365)
        if len(downside) > 0 and downside.std() > 0 else 0.0
    )

    # Max drawdown
    peak     = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - peak) / peak
    max_dd   = drawdown.min()

    # Calmar ratio
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    return {
        'label':         label,
        'total_return':  total_return,
        'annual_return': annual_return,
        'sharpe':        sharpe,
        'sortino':       sortino,
        'max_drawdown':  max_dd,
        'calmar':        calmar,
        'equity':        equity_curve,
    }


# ---------------------------------------------------------------------------
# FETCH ALL DATA
# ---------------------------------------------------------------------------

START = '2018-01-01'
END   = '2026-04-06'

print("\nFetching price data...")

tickers = {
    'ETH-USD': 'ETH',
    'BTC-USD': 'BTC',
    'BNB-USD': 'BNB',
    'SOL-USD': 'SOL',
    'ADA-USD': 'ADA',
}

# [VARIABLE - dict] raw price DataFrames keyed by ticker name
prices: dict = {}

for ticker, name in tickers.items():
    try:
        raw = yf.download(ticker, start=START, interval='1d', progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)
        prices[name] = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        prices[name].dropna(inplace=True)
        print(f"  {name}: {prices[name].index[0].date()} → "
              f"{prices[name].index[-1].date()} ({len(prices[name]):,} days)")
    except Exception as e:
        print(f"  {name}: Failed to fetch — {e}")

eth = prices['ETH']
btc = prices['BTC']

# Common date range for fair comparison
# Use ETH start date as baseline (2018-01-01)
common_start = pd.Timestamp('2018-01-01')
common_end   = pd.Timestamp('2026-04-06')

years = (common_end - common_start).days / 365.25
print(f"\nCommon period: {common_start.date()} → {common_end.date()} ({years:.1f} years)")


# ---------------------------------------------------------------------------
# BENCHMARK 1: BUY AND HOLD ETH
# ---------------------------------------------------------------------------

eth_filtered = eth[(eth.index >= common_start) & (eth.index <= common_end)]
eth_bh_equity = eth_filtered['Close'].values / eth_filtered['Close'].values[0]
bh_eth = performance_metrics(eth_bh_equity, 'Buy & Hold ETH', years)


# ---------------------------------------------------------------------------
# BENCHMARK 2: BUY AND HOLD BTC
# ---------------------------------------------------------------------------

btc_filtered = btc[(btc.index >= common_start) & (btc.index <= common_end)]
# Align BTC to ETH dates
btc_aligned = btc_filtered.reindex(eth_filtered.index, method='ffill')
btc_bh_equity = btc_aligned['Close'].values / btc_aligned['Close'].iloc[0]
bh_btc = performance_metrics(btc_bh_equity, 'Buy & Hold BTC', years)


# ---------------------------------------------------------------------------
# BENCHMARK 3: EQUAL-WEIGHT CRYPTO BASKET
# ---------------------------------------------------------------------------
# Assets: BTC, ETH, BNB, SOL, ADA
# Rebalance monthly — each asset gets equal weight on rebalance date
# Assets that don't exist yet are excluded from the basket until they do

print("\nBuilding equal-weight crypto basket...")

basket_assets = ['BTC', 'ETH', 'BNB', 'SOL', 'ADA']
basket_prices: dict = {}

for name in basket_assets:
    if name in prices:
        p = prices[name].copy()
        p = p[(p.index >= common_start) & (p.index <= common_end)]
        p = p.reindex(eth_filtered.index, method='ffill')
        basket_prices[name] = p['Close']

# [VARIABLE - DataFrame] all basket prices aligned to ETH dates
basket_df = pd.DataFrame(basket_prices)
basket_df.dropna(how='all', inplace=True)

# Calculate daily returns for each asset
basket_returns = basket_df.pct_change().fillna(0)

# Monthly rebalancing — equal weight among available assets each month
# [VARIABLE - Series] basket equity curve
basket_equity = [1.0]
current_weights = None
current_value   = 1.0

for i in range(1, len(basket_returns)):
    date = basket_returns.index[i]

    # Rebalance at start of each month OR on first day
    is_month_start = (date.month != basket_returns.index[i-1].month)

    if is_month_start or current_weights is None:
        # Equal weight among assets available on this date
        available = basket_df.iloc[i].dropna().index.tolist()
        n = len(available)
        current_weights = {a: 1/n for a in available}

    # Apply daily returns
    day_return = sum(
        current_weights.get(asset, 0) * basket_returns.iloc[i][asset]
        for asset in basket_returns.columns
        if asset in current_weights
    )

    current_value *= (1 + day_return)
    basket_equity.append(current_value)

basket_equity = np.array(basket_equity)
basket_result = performance_metrics(basket_equity, 'Equal-Weight Basket (5 assets)', years)


# ---------------------------------------------------------------------------
# BENCHMARK 4: 60/40 BTC/ETH
# ---------------------------------------------------------------------------

btc_returns = btc_aligned['Close'].pct_change().fillna(0).values
eth_returns = eth_filtered['Close'].pct_change().fillna(0).values

# 60% BTC, 40% ETH — rebalanced monthly
equity_6040 = [1.0]
value_6040   = 1.0

for i in range(1, len(eth_returns)):
    day_ret = 0.60 * btc_returns[i] + 0.40 * eth_returns[i]
    value_6040 *= (1 + day_ret)
    equity_6040.append(value_6040)

equity_6040  = np.array(equity_6040)
result_6040  = performance_metrics(equity_6040, '60/40 BTC/ETH', years)


# ---------------------------------------------------------------------------
# STRATEGY EQUITY CURVES
# ---------------------------------------------------------------------------
# Rebuild strategy equity curves from saved trade logs

def equity_from_tradelog(filepath: str, label: str) -> dict:
    """
    [FUNCTION] Build equity curve from a saved trade log CSV.

    Args:
        filepath : path to trade log CSV with 'return' column
        label    : strategy name

    Returns:
        dict with equity array and metrics
    """
    if not os.path.exists(filepath):
        print(f"  ⚠️  Trade log not found: {filepath}")
        return None

    trades  = pd.read_csv(filepath)
    returns = trades['return'].values

    equity  = np.concatenate([[1.0], np.cumprod(1 + returns)])

    # Approximate years from trade dates
    trades['exit_date']  = pd.to_datetime(trades['exit_date'])
    trades['entry_date'] = pd.to_datetime(trades['entry_date'])
    trade_years = (
        trades['exit_date'].max() - trades['entry_date'].min()
    ).days / 365.25

    return performance_metrics(equity, label, trade_years)


print("\nLoading strategy trade logs...")
strat_adx = equity_from_tradelog('data/trade_log_with_stoploss.csv', 'ADX 20/10 ETH')
strat_bb  = equity_from_tradelog('data/trade_log_bollinger_final.csv', 'BB v3 ETH')
strat_rsi = equity_from_tradelog('data/trade_log_rsi_final.csv', 'RSI Final ETH')


# ---------------------------------------------------------------------------
# PRINT COMPARISON TABLE
# ---------------------------------------------------------------------------

all_results = [
    bh_eth, bh_btc, basket_result, result_6040,
]

if strat_adx: all_results.append(strat_adx)
if strat_bb:  all_results.append(strat_bb)
if strat_rsi: all_results.append(strat_rsi)

print(f"\n{'='*100}")
print(f"STRATEGY vs BENCHMARK COMPARISON")
print(f"{'='*100}")
print(f"\n{'Strategy':<30} {'Total Return':>14} {'Annual Return':>14} "
      f"{'Sharpe':>8} {'Sortino':>8} {'Max DD':>10} {'Calmar':>8}")
print(f"{'-'*95}")

# Benchmarks first
print(f"\n  --- PASSIVE BENCHMARKS ---")
for r in [bh_eth, bh_btc, basket_result, result_6040]:
    print(f"  {r['label']:<28} {r['total_return']:>14.1%} "
          f"{r['annual_return']:>14.1%} {r['sharpe']:>8.3f} "
          f"{r['sortino']:>8.3f} {r['max_drawdown']:>10.1%} "
          f"{r['calmar']:>8.3f}")

# Strategies
print(f"\n  --- ACTIVE STRATEGIES ---")
for r in [strat_adx, strat_bb, strat_rsi]:
    if r:
        print(f"  {r['label']:<28} {r['total_return']:>14.1%} "
              f"{r['annual_return']:>14.1%} {r['sharpe']:>8.3f} "
              f"{r['sortino']:>8.3f} {r['max_drawdown']:>10.1%} "
              f"{r['calmar']:>8.3f}")

print(f"\n{'='*100}")
print(f"\nNOTES:")
print(f"  - Strategy returns are per-trade compounded (not daily equity curve)")
print(f"  - Strategy Sharpe uses trade-level returns — not directly comparable")
print(f"    to benchmark daily Sharpe. Use Calmar ratio for fairer comparison.")
print(f"  - Benchmark Sharpe calculated on daily returns — the correct method")
print(f"  - BB and RSI have very few trades — treat metrics with caution")
print(f"{'='*100}")


# ---------------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------------

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

fig, axes = plt.subplots(2, 1, figsize=(16, 12))
fig.suptitle(
    'Strategy vs Benchmark Comparison — Week 5\n'
    '$1,000 invested January 2018',
    fontsize=14, fontweight='bold'
)

# Colours
bench_colors = {
    'Buy & Hold ETH':               ('steelblue',  2.0, '--'),
    'Buy & Hold BTC':               ('orange',     2.0, '--'),
    'Equal-Weight Basket (5 assets)': ('green',    1.5, '--'),
    '60/40 BTC/ETH':                ('purple',     1.5, '--'),
}
strat_colors = {
    'ADX 20/10 ETH': ('crimson',   2.5, '-'),
    'BB v3 ETH':     ('teal',      2.0, '-'),
    'RSI Final ETH': ('darkgreen', 2.0, '-'),
}

# --- Equity curves (dollar value from $1,000) ---
for r in [bh_eth, bh_btc, basket_result, result_6040]:
    color, lw, ls = bench_colors[r['label']]
    eq = r['equity'] * 1000
    axes[0].plot(eq, color=color, linewidth=lw, linestyle=ls,
                 label=f"{r['label']} (${eq[-1]:,.0f})", alpha=0.8)

for r in [strat_adx, strat_bb, strat_rsi]:
    if r:
        color, lw, ls = strat_colors.get(r['label'], ('gray', 1.5, '-'))
        eq = r['equity'] * 1000
        axes[0].plot(eq, color=color, linewidth=lw, linestyle=ls,
                     label=f"{r['label']} (${eq[-1]:,.0f})")

axes[0].axhline(1000, color='gray', linestyle=':', alpha=0.5, label='Start ($1,000)')
axes[0].set_title('Portfolio Growth from $1,000 (log scale)')
axes[0].set_ylabel('Portfolio Value ($)')
axes[0].set_yscale('log')
axes[0].legend(fontsize=8, loc='upper left')
axes[0].grid(alpha=0.3)

# --- Drawdown comparison ---
for r in [bh_eth, bh_btc, basket_result, result_6040]:
    color, lw, ls = bench_colors[r['label']]
    eq   = r['equity']
    peak = np.maximum.accumulate(eq)
    dd   = (eq - peak) / peak * 100
    axes[1].plot(dd, color=color, linewidth=lw,
                 linestyle=ls, alpha=0.8, label=r['label'])

for r in [strat_adx, strat_bb, strat_rsi]:
    if r:
        color, lw, ls = strat_colors.get(r['label'], ('gray', 1.5, '-'))
        eq   = r['equity']
        peak = np.maximum.accumulate(eq)
        dd   = (eq - peak) / peak * 100
        axes[1].plot(dd, color=color, linewidth=lw,
                     linestyle=ls, label=r['label'])

axes[1].set_title('Drawdown Comparison (%)')
axes[1].set_ylabel('Drawdown (%)')
axes[1].legend(fontsize=8, loc='lower left')
axes[1].grid(alpha=0.3)

plt.tight_layout()
chart_path = 'Week_5_Notebooks/results/benchmark_comparison.png'
plt.savefig(chart_path, dpi=150)
plt.close()
print(f"\n✅ Chart saved → {chart_path}")
print(f"\n✅ Benchmark comparison complete")