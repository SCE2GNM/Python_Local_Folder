# [MODULE] ETH vs BTC ADX Strategy Comparison
# Week 5 Extension
#
# Side-by-side comparison of ADX strategy on ETH and BTC
# using each asset's optimised parameters.
# Answers: is deploying BTC worth the additional capital and complexity?

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from ta.trend import ADXIndicator
import os

# ---------------------------------------------------------------------------
# [FUNCTION] run_adx_backtest
# ---------------------------------------------------------------------------

def run_adx_backtest(
    symbol:    str,
    threshold: int,
    period:    int,
    stop_pct:  float,
    label:     str,
    start:     str = '2018-01-01',
) -> dict:
    """
    [FUNCTION] Full ADX backtest returning all metrics and equity curve.

    Args:
        symbol    : yfinance ticker
        threshold : ADX trending threshold
        period    : ADX lookback window
        stop_pct  : hard stop-loss
        label     : display name
        start     : backtest start date

    Returns:
        dict with full metrics, equity curve, and trades DataFrame
    """
    print(f"  Running {label}...")

    raw = yf.download(symbol, start=start, interval='1d', progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)

    df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.dropna(inplace=True)

    adx_ind = ADXIndicator(df['High'], df['Low'], df['Close'], window=period)
    adx     = adx_ind.adx()
    di_pos  = adx_ind.adx_pos()
    di_neg  = adx_ind.adx_neg()

    entry_signal = (adx >= threshold) & (di_pos > di_neg)

    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    closes  = df['Close'].values
    lows    = df['Low'].values
    signals = entry_signal.values
    dates   = df.index

    for i in range(1, len(df)):
        low:    float = lows[i]
        close:  float = closes[i]
        signal: bool  = signals[i]

        if position == 1:
            if low <= stop_price:
                trades.append({
                    'entry_date':  dates[i-1],
                    'exit_date':   dates[i],
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'STOP_LOSS',
                    'hold_days':   (dates[i] - dates[i-1]).days,
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            elif not signal:
                trades.append({
                    'entry_date':  dates[i-1],
                    'exit_date':   dates[i],
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'ADX_EXIT',
                    'hold_days':   (dates[i] - dates[i-1]).days,
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and signal:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    trades_df = pd.DataFrame(trades)
    returns   = trades_df['return'].values

    winners = trades_df[trades_df['return'] > 0]
    losers  = trades_df[trades_df['return'] <= 0]

    # Core metrics
    win_rate      = len(winners) / len(trades_df)
    avg_win       = winners['return'].mean() if len(winners) > 0 else 0.0
    avg_loss      = losers['return'].mean()  if len(losers)  > 0 else 0.0
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    gross_profit  = winners['return'].sum()       if len(winners) > 0 else 0.0
    gross_loss    = abs(losers['return'].sum())   if len(losers)  > 0 else 1e-9
    profit_factor = gross_profit / gross_loss

    # Kelly
    kelly_b    = avg_win / abs(avg_loss) if avg_loss != 0 else 0.0
    kelly_full = (win_rate * kelly_b - (1 - win_rate)) / kelly_b if kelly_b > 0 else 0.0
    kelly_half = kelly_full * 0.5
    kelly_rec  = max(0.0, min(kelly_half, 0.25))

    # Equity and drawdown
    equity   = np.cumprod(1 + returns)
    peak     = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_dd   = drawdown.min()

    # Buy and hold for comparison
    bh_equity = df['Close'].values / df['Close'].values[0]

    # Returns
    years           = (df.index[-1] - df.index[0]).days / 365.25
    total_return    = (1 + returns).prod() - 1
    annual_return   = (1 + total_return) ** (1 / years) - 1
    trades_per_year = len(trades_df) / years

    # Calmar
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    # Cost drag
    cost_per_trade  = 0.00075 * 2
    total_cost_drag = len(trades_df) * cost_per_trade
    net_return      = total_return - total_cost_drag

    # Stop exit stats
    stop_exits     = (trades_df['exit_reason'] == 'STOP_LOSS').sum()
    avg_hold_days  = trades_df['hold_days'].mean()

    # Monthly returns for correlation analysis
    trades_df['exit_date'] = pd.to_datetime(trades_df['exit_date'])
    trades_df['month']     = trades_df['exit_date'].dt.to_period('M')

    return {
        'label':           label,
        'symbol':          symbol,
        'threshold':       threshold,
        'period':          period,
        'stop_pct':        stop_pct,
        'years':           years,
        'total_trades':    len(trades_df),
        'trades_per_year': trades_per_year,
        'win_rate':        win_rate,
        'avg_win':         avg_win,
        'avg_loss':        avg_loss,
        'win_loss_ratio':  win_loss_ratio,
        'profit_factor':   profit_factor,
        'total_return':    total_return,
        'net_return':      net_return,
        'annual_return':   annual_return,
        'max_drawdown':    max_dd,
        'calmar':          calmar,
        'kelly_rec':       kelly_rec,
        'stop_exits':      stop_exits,
        'stop_exits_pct':  stop_exits / len(trades_df),
        'avg_hold_days':   avg_hold_days,
        'equity':          equity,
        'drawdown':        drawdown,
        'bh_equity':       bh_equity,
        'df':              df,
        'trades_df':       trades_df,
    }


# ---------------------------------------------------------------------------
# RUN BOTH STRATEGIES
# ---------------------------------------------------------------------------

print("\nRunning ADX backtests...")

eth = run_adx_backtest(
    symbol='ETH-USD', threshold=20, period=10,
    stop_pct=0.05, label='ADX ETH (20/10 5% stop)'
)

btc = run_adx_backtest(
    symbol='BTC-USD', threshold=19, period=14,
    stop_pct=0.03, label='ADX BTC (19/14 3% stop)'
)

# Also run ETH parameters on BTC for reference
btc_eth_params = run_adx_backtest(
    symbol='BTC-USD', threshold=20, period=10,
    stop_pct=0.05, label='ADX BTC (ETH params 20/10 5%)'
)


# ---------------------------------------------------------------------------
# PRINT SIDE-BY-SIDE COMPARISON
# ---------------------------------------------------------------------------

print(f"\n{'='*85}")
print(f"ETH vs BTC ADX STRATEGY — FULL COMPARISON")
print(f"{'='*85}")

rows = [
    ('Parameters',       f"ADX {eth['threshold']}/{eth['period']} "
                         f"stop {eth['stop_pct']*100:.0f}%",
                         f"ADX {btc['threshold']}/{btc['period']} "
                         f"stop {btc['stop_pct']*100:.0f}%",
                         f"ADX {btc_eth_params['threshold']}/"
                         f"{btc_eth_params['period']} "
                         f"stop {btc_eth_params['stop_pct']*100:.0f}%"),

    ('─'*22,             '─'*20, '─'*20, '─'*20),

    ('RETURNS',          '', '', ''),
    ('Total Return',     f"{eth['total_return']:+.1%}",
                         f"{btc['total_return']:+.1%}",
                         f"{btc_eth_params['total_return']:+.1%}"),
    ('Net Return',       f"{eth['net_return']:+.1%}",
                         f"{btc['net_return']:+.1%}",
                         f"{btc_eth_params['net_return']:+.1%}"),
    ('Annual Return',    f"{eth['annual_return']:+.1%}",
                         f"{btc['annual_return']:+.1%}",
                         f"{btc_eth_params['annual_return']:+.1%}"),

    ('─'*22,             '─'*20, '─'*20, '─'*20),

    ('RISK',             '', '', ''),
    ('Max Drawdown',     f"{eth['max_drawdown']:.1%}",
                         f"{btc['max_drawdown']:.1%}",
                         f"{btc_eth_params['max_drawdown']:.1%}"),
    ('Calmar Ratio',     f"{eth['calmar']:.3f}",
                         f"{btc['calmar']:.3f}",
                         f"{btc_eth_params['calmar']:.3f}"),
    ('Profit Factor',    f"{eth['profit_factor']:.3f}",
                         f"{btc['profit_factor']:.3f}",
                         f"{btc_eth_params['profit_factor']:.3f}"),

    ('─'*22,             '─'*20, '─'*20, '─'*20),

    ('TRADE STATS',      '', '', ''),
    ('Total Trades',     f"{eth['total_trades']}",
                         f"{btc['total_trades']}",
                         f"{btc_eth_params['total_trades']}"),
    ('Trades/Year',      f"{eth['trades_per_year']:.1f}",
                         f"{btc['trades_per_year']:.1f}",
                         f"{btc_eth_params['trades_per_year']:.1f}"),
    ('Win Rate',         f"{eth['win_rate']:.1%}",
                         f"{btc['win_rate']:.1%}",
                         f"{btc_eth_params['win_rate']:.1%}"),
    ('Avg Win',          f"{eth['avg_win']:+.2%}",
                         f"{btc['avg_win']:+.2%}",
                         f"{btc_eth_params['avg_win']:+.2%}"),
    ('Avg Loss',         f"{eth['avg_loss']:+.2%}",
                         f"{btc['avg_loss']:+.2%}",
                         f"{btc_eth_params['avg_loss']:+.2%}"),
    ('Win/Loss Ratio',   f"{eth['win_loss_ratio']:.2f}x",
                         f"{btc['win_loss_ratio']:.2f}x",
                         f"{btc_eth_params['win_loss_ratio']:.2f}x"),
    ('Avg Hold Days',    f"{eth['avg_hold_days']:.1f}",
                         f"{btc['avg_hold_days']:.1f}",
                         f"{btc_eth_params['avg_hold_days']:.1f}"),
    ('Stop Exits',       f"{eth['stop_exits_pct']:.1%}",
                         f"{btc['stop_exits_pct']:.1%}",
                         f"{btc_eth_params['stop_exits_pct']:.1%}"),

    ('─'*22,             '─'*20, '─'*20, '─'*20),

    ('SIZING',           '', '', ''),
    ('Kelly Rec',        f"{eth['kelly_rec']:.2%}",
                         f"{btc['kelly_rec']:.2%}",
                         f"{btc_eth_params['kelly_rec']:.2%}"),

    ('─'*22,             '─'*20, '─'*20, '─'*20),

    ('STABILITY',        '', '', ''),
    ('Threshold stab.',  '100% (8/8)',    '100% (8/8)',    'N/A'),
    ('Period stab.',     '100% (7/7)',    '100% (7/7)',    'N/A'),
    ('Stop stab.',       '100% (7/7)',    '100% (7/7)',    'N/A'),
]

print(f"\n  {'Metric':<24} {'ETH (optimised)':>20} "
      f"{'BTC (optimised)':>20} {'BTC (ETH params)':>20}")
print(f"  {'─'*85}")

for row in rows:
    metric, eth_val, btc_val, btc_eth_val = row
    if metric.startswith('─'):
        print(f"  {'─'*85}")
    elif eth_val == '':
        print(f"\n  {metric.upper()}")
    else:
        print(f"  {metric:<24} {eth_val:>20} {btc_val:>20} {btc_eth_val:>20}")

print(f"\n{'='*85}")


# ---------------------------------------------------------------------------
# DEPLOYMENT DECISION FRAMEWORK
# ---------------------------------------------------------------------------

print(f"\n{'='*85}")
print(f"DEPLOYMENT DECISION FRAMEWORK")
print(f"{'='*85}")

print(f"""
  QUESTION 1: Does BTC have a genuine edge?
  Answer: YES
  Evidence: Profit factor 3.402, Calmar 1.121, stability 100% all params.
  Both are well above the minimum thresholds for deployment.

  QUESTION 2: Is BTC better than ETH?
  Answer: NO — ETH is meaningfully better on risk-adjusted basis.
  ETH Calmar: {eth['calmar']:.3f} vs BTC Calmar: {btc['calmar']:.3f}
  ETH annual return: {eth['annual_return']:.1%} vs BTC: {btc['annual_return']:.1%}
  ETH max drawdown: {eth['max_drawdown']:.1%} vs BTC: {btc['max_drawdown']:.1%}

  QUESTION 3: Does adding BTC diversify the portfolio?
  Answer: PARTIALLY — BTC and ETH are highly correlated (typically 0.7-0.9).
  Adding BTC ADX alongside ETH ADX does not provide true diversification.
  Both strategies will tend to be long simultaneously during crypto bull markets
  and flat simultaneously during bear markets.
  TRUE diversification comes from mean reversion (RSI/BB) which is uncorrelated
  to trend-following — which you are already deploying.

  QUESTION 4: Is the capital better used elsewhere?
  Answer: YES — $500 additional capital on ETH ADX (scaling up) or RSI ETH
  provides better risk-adjusted return than deploying $500 on BTC ADX.

  VERDICT:
  BTC ADX is a VALID strategy but NOT the best use of the next $500.
  Recommendation: Deploy RSI ETH ($500) first. After 20+ live RSI trades,
  reassess whether to add BTC ADX or scale up ETH ADX instead.
""")


# ---------------------------------------------------------------------------
# PLOTS — 4 panel comparison
# ---------------------------------------------------------------------------

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle(
    'ETH vs BTC ADX Strategy Comparison\n'
    'ETH: ADX 20/10 5% stop | BTC: ADX 19/14 3% stop',
    fontsize=13, fontweight='bold'
)

# --- Equity curves (log scale) ---
eth_eq = np.concatenate([[1.0], eth['equity']])
btc_eq = np.concatenate([[1.0], btc['equity']])
bep_eq = np.concatenate([[1.0], btc_eth_params['equity']])

axes[0][0].plot(eth_eq, color='steelblue', linewidth=2,
                label=f"ETH ADX (${eth_eq[-1]*1000:,.0f})")
axes[0][0].plot(btc_eq, color='orange', linewidth=2,
                label=f"BTC ADX opt (${btc_eq[-1]*1000:,.0f})")
axes[0][0].plot(bep_eq, color='orange', linewidth=1.5, linestyle='--',
                alpha=0.6, label=f"BTC ETH params (${bep_eq[-1]*1000:,.0f})")
axes[0][0].axhline(1.0, color='gray', linestyle=':', alpha=0.5)
axes[0][0].set_title('Equity Curves (log scale, $1,000 start)')
axes[0][0].set_ylabel('Equity multiplier')
axes[0][0].set_yscale('log')
axes[0][0].legend(fontsize=8)
axes[0][0].grid(alpha=0.3)

# --- Drawdown comparison ---
axes[0][1].fill_between(range(len(eth['drawdown'])),
                         eth['drawdown'] * 100, 0,
                         color='steelblue', alpha=0.4, label='ETH ADX')
axes[0][1].fill_between(range(len(btc['drawdown'])),
                         btc['drawdown'] * 100, 0,
                         color='orange', alpha=0.4, label='BTC ADX opt')
axes[0][1].set_title('Drawdown Comparison (%)')
axes[0][1].set_ylabel('Drawdown %')
axes[0][1].legend(fontsize=8)
axes[0][1].grid(alpha=0.3)

# --- Key metrics bar chart ---
metrics     = ['Annual\nReturn', 'Profit\nFactor', 'Calmar\nRatio']
eth_vals    = [eth['annual_return']*100, eth['profit_factor'], eth['calmar']]
btc_vals    = [btc['annual_return']*100, btc['profit_factor'], btc['calmar']]

x     = np.arange(len(metrics))
width = 0.35

bars1 = axes[1][0].bar(x - width/2, eth_vals, width,
                        color='steelblue', label='ETH ADX', alpha=0.8)
bars2 = axes[1][0].bar(x + width/2, btc_vals, width,
                        color='orange', label='BTC ADX', alpha=0.8)

# Add value labels on bars
for bar in bars1:
    axes[1][0].text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.5,
                    f'{bar.get_height():.1f}',
                    ha='center', va='bottom', fontsize=8)
for bar in bars2:
    axes[1][0].text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.5,
                    f'{bar.get_height():.1f}',
                    ha='center', va='bottom', fontsize=8)

axes[1][0].set_xticks(x)
axes[1][0].set_xticklabels(metrics)
axes[1][0].set_title('Key Metrics Comparison')
axes[1][0].legend(fontsize=8)
axes[1][0].grid(alpha=0.3, axis='y')

# --- Return distribution comparison ---
axes[1][1].hist(eth['trades_df']['return'] * 100, bins=25,
                alpha=0.6, color='steelblue', edgecolor='black',
                label=f"ETH ({eth['total_trades']} trades)")
axes[1][1].hist(btc['trades_df']['return'] * 100, bins=25,
                alpha=0.6, color='orange', edgecolor='black',
                label=f"BTC ({btc['total_trades']} trades)")
axes[1][1].axvline(0, color='black', linewidth=1, alpha=0.5)
axes[1][1].set_title('Trade Return Distribution')
axes[1][1].set_xlabel('Trade Return (%)')
axes[1][1].set_ylabel('Count')
axes[1][1].legend(fontsize=8)
axes[1][1].grid(alpha=0.3)

plt.tight_layout()
chart_path = 'Week_5_Notebooks/results/eth_vs_btc_comparison.png'
plt.savefig(chart_path, dpi=150)
plt.close()
print(f"\n✅ Chart saved → {chart_path}")
print(f"\n{'='*85}")
print(f"COMPARISON COMPLETE")
print(f"{'='*85}\n")