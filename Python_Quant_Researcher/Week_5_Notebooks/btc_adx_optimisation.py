# [MODULE] BTC ADX Optimisation
# Week 5 Extension
#
# WHAT THIS SCRIPT DOES:
#   Runs joint parameter optimisation for ADX trend-following
#   on BTC-USD daily candles. Same approach as Week 5 Day 3
#   but optimised specifically for BTC rather than using
#   ETH-derived parameters.
#
# WHY SEPARATE OPTIMISATION:
#   BTC and ETH have different volatility profiles.
#   BTC tends toward stronger, longer-duration trends due to
#   higher institutional participation and liquidity.
#   ETH-optimised parameters (ADX 20/10, 5% stop) may not
#   be optimal for BTC's specific characteristics.
#
# GRID: Same refined grid as ETH Day 3
#   Thresholds: 15-22 (step 1)
#   Periods:    8-14  (step 1)
#   Stops:      3-6%  (step 0.5%)

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from ta.trend import ADXIndicator
import os
from itertools import product

# ---------------------------------------------------------------------------
# [FUNCTION] run_backtest
# ---------------------------------------------------------------------------

def run_backtest(
    df:        pd.DataFrame,
    threshold: int,
    period:    int,
    stop_pct:  float,
) -> dict:
    """
    [FUNCTION] Run one ADX bar-by-bar backtest for a single parameter set.

    Args:
        df        : OHLCV DataFrame
        threshold : ADX level to define trending regime
        period    : ADX lookback window
        stop_pct  : stop-loss as fraction of entry price

    Returns:
        dict of metrics, or None if fewer than 10 trades
    """
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

    for i in range(1, len(df)):
        low:    float = lows[i]
        close:  float = closes[i]
        signal: bool  = signals[i]

        if position == 1:
            if low <= stop_price:
                trades.append({
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            elif not signal:
                trades.append({
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'ADX_EXIT',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and signal:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    if len(trades) < 10:
        return None

    trades_df = pd.DataFrame(trades)
    returns   = trades_df['return'].values

    winners = trades_df[trades_df['return'] > 0]
    losers  = trades_df[trades_df['return'] <= 0]

    win_rate      = len(winners) / len(trades_df)
    gross_profit  = winners['return'].sum() if len(winners) > 0 else 0.0
    gross_loss    = abs(losers['return'].sum()) if len(losers) > 0 else 1e-9
    profit_factor = gross_profit / gross_loss

    equity   = np.cumprod(1 + returns)
    peak     = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_dd   = drawdown.min()

    stop_exits   = (trades_df['exit_reason'] == 'STOP_LOSS').sum()
    total_return = (1 + returns).prod() - 1

    years            = (df.index[-1] - df.index[0]).days / 365.25
    trades_per_year  = len(trades_df) / years
    annual_return    = (1 + total_return) ** (1 / years) - 1

    # Calmar ratio — more reliable than Sharpe for per-trade returns
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    return {
        'threshold':      threshold,
        'period':         period,
        'stop_pct':       stop_pct,
        'total_trades':   len(trades_df),
        'trades_per_year': trades_per_year,
        'win_rate':       win_rate,
        'avg_win':        winners['return'].mean() if len(winners) > 0 else 0.0,
        'avg_loss':       losers['return'].mean()  if len(losers)  > 0 else 0.0,
        'profit_factor':  profit_factor,
        'max_drawdown':   max_dd,
        'total_return':   total_return,
        'annual_return':  annual_return,
        'calmar':         calmar,
        'stop_exits_pct': stop_exits / len(trades_df),
    }


# ---------------------------------------------------------------------------
# FETCH BTC DATA
# ---------------------------------------------------------------------------

print("\nFetching BTC-USD daily data...")
raw = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)

if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)

df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.dropna(inplace=True)
print(f"Data loaded: {df.index[0].date()} → {df.index[-1].date()} ({len(df):,} days)")


# ---------------------------------------------------------------------------
# PARAMETER GRID — same refined grid as ETH Day 3
# ---------------------------------------------------------------------------

thresholds: list = [15, 16, 17, 18, 19, 20, 21, 22]
periods:    list = [8, 9, 10, 11, 12, 13, 14]
stops:      list = [0.030, 0.035, 0.040, 0.045, 0.050, 0.055, 0.060]

total = len(thresholds) * len(periods) * len(stops)
print(f"\nGrid: {len(thresholds)} thresholds × {len(periods)} periods × {len(stops)} stops")
print(f"Total combinations: {total}")
print(f"Running...\n")


# ---------------------------------------------------------------------------
# RUN GRID SEARCH
# ---------------------------------------------------------------------------

results:   list = []
completed: int  = 0

for threshold, period, stop_pct in product(thresholds, periods, stops):
    result = run_backtest(df, threshold, period, stop_pct)
    if result is not None:
        results.append(result)
    completed += 1
    if completed % 100 == 0:
        print(f"  {completed}/{total} combinations tested...")

results_df = pd.DataFrame(results)
print(f"\nGrid search complete. {len(results_df)} valid combinations.")


# ---------------------------------------------------------------------------
# RANK AND PRINT — ranked by profit factor
# ---------------------------------------------------------------------------

ranked = results_df.sort_values('profit_factor', ascending=False).reset_index(drop=True)

# ETH live parameters for comparison
ETH_THRESHOLD = 20
ETH_PERIOD    = 10
ETH_STOP      = 0.05

print(f"\n{'='*100}")
print(f"TOP 15 BTC ADX COMBINATIONS (ranked by profit factor)")
print(f"{'='*100}")
print(f"\n{'Rank':<5} {'Threshold':>10} {'Period':>8} {'Stop%':>7} "
      f"{'Trades':>8} {'Win Rate':>10} {'Profit Factor':>14} "
      f"{'Ann Return':>12} {'Max DD':>10} {'Calmar':>8} {'Stop Exits':>12}")
print(f"{'-'*100}")

for i, row in ranked.head(15).iterrows():
    is_eth = (row.threshold == ETH_THRESHOLD and
              row.period == ETH_PERIOD and
              row.stop_pct == ETH_STOP)
    marker = ' ← ETH params' if is_eth else ''

    print(f"  {i+1:<4} {int(row.threshold):>10} {int(row.period):>8} "
          f"{row.stop_pct*100:>6.1f}% {int(row.total_trades):>8} "
          f"{row.win_rate:>10.1%} {row.profit_factor:>14.3f} "
          f"{row.annual_return:>12.1%} {row.max_drawdown:>10.1%} "
          f"{row.calmar:>8.3f} {row.stop_exits_pct:>11.1%}{marker}")


# ---------------------------------------------------------------------------
# WHERE DO ETH PARAMETERS RANK ON BTC?
# ---------------------------------------------------------------------------

eth_row  = ranked[(ranked['threshold'] == ETH_THRESHOLD) &
                  (ranked['period']    == ETH_PERIOD) &
                  (ranked['stop_pct']  == ETH_STOP)]

print(f"\n{'='*100}")
print(f"ETH PARAMETERS (ADX 20/10, 5% stop) PERFORMANCE ON BTC:")
print(f"{'='*100}")

if len(eth_row) > 0:
    eth_rank = eth_row.index[0] + 1
    r = eth_row.iloc[0]
    print(f"  Rank:          {eth_rank} of {len(results_df)}")
    print(f"  Profit Factor: {r['profit_factor']:.3f}")
    print(f"  Annual Return: {r['annual_return']:.1%}")
    print(f"  Win Rate:      {r['win_rate']:.1%}")
    print(f"  Max Drawdown:  {r['max_drawdown']:.1%}")
    print(f"  Calmar:        {r['calmar']:.3f}")
    print(f"  Total Trades:  {int(r['total_trades'])}")
else:
    print(f"  ETH parameters not in results (may have < 10 trades)")

best = ranked.iloc[0]
print(f"\n  Best BTC combination: ADX {int(best.threshold)}/{int(best.period)} "
      f"with {best.stop_pct*100:.1f}% stop")
print(f"  Profit factor: {best.profit_factor:.3f} | "
      f"Annual: {best.annual_return:.1%} | "
      f"Max DD: {best.max_drawdown:.1%} | "
      f"Calmar: {best.calmar:.3f}")


# ---------------------------------------------------------------------------
# SIDE-BY-SIDE COMPARISON: ETH OPTIMAL vs BTC OPTIMAL vs SHARED PARAMS
# ---------------------------------------------------------------------------

print(f"\n{'='*100}")
print(f"PARAMETER COMPARISON: ETH OPTIMAL vs BTC OPTIMAL vs SHARED (ETH params on BTC)")
print(f"{'='*100}")

# ETH optimal (from Week 5 Day 3 — live params, rank 22 on ETH refined grid)
print(f"\n  {'Metric':<22} {'ETH optimal':>15} {'BTC optimal':>15} {'ETH params on BTC':>18}")
print(f"  {'-'*72}")

eth_opt = {
    'params':         'ADX 20/10 5%',
    'profit_factor':  3.197,
    'annual_return':  0.8428,
    'win_rate':       0.343,
    'max_drawdown':   -0.303,
    'calmar':         2.253,
    'trades':         108,
}

btc_opt_row = ranked.iloc[0]
eth_on_btc  = eth_row.iloc[0] if len(eth_row) > 0 else None

print(f"  {'Parameters':<22} {'ADX 20/10 5%':>15} "
      f"{f'ADX {int(btc_opt_row.threshold)}/{int(btc_opt_row.period)} {btc_opt_row.stop_pct*100:.1f}%':>15} "
      f"{'ADX 20/10 5%':>18}")
print(f"  {'Profit Factor':<22} {eth_opt['profit_factor']:>15.3f} "
      f"{btc_opt_row.profit_factor:>15.3f} "
      f"{eth_on_btc['profit_factor'] if eth_on_btc is not None else 'N/A':>18.3f}")
print(f"  {'Annual Return':<22} {eth_opt['annual_return']:>15.1%} "
      f"{btc_opt_row.annual_return:>15.1%} "
      f"{eth_on_btc['annual_return'] if eth_on_btc is not None else 'N/A':>18.1%}")
print(f"  {'Win Rate':<22} {eth_opt['win_rate']:>15.1%} "
      f"{btc_opt_row.win_rate:>15.1%} "
      f"{eth_on_btc['win_rate'] if eth_on_btc is not None else 'N/A':>18.1%}")
print(f"  {'Max Drawdown':<22} {eth_opt['max_drawdown']:>15.1%} "
      f"{btc_opt_row.max_drawdown:>15.1%} "
      f"{eth_on_btc['max_drawdown'] if eth_on_btc is not None else 'N/A':>18.1%}")
print(f"  {'Calmar':<22} {eth_opt['calmar']:>15.3f} "
      f"{btc_opt_row.calmar:>15.3f} "
      f"{eth_on_btc['calmar'] if eth_on_btc is not None else 'N/A':>18.3f}")
print(f"  {'Total Trades':<22} {eth_opt['trades']:>15} "
      f"{int(btc_opt_row.total_trades):>15} "
      f"{int(eth_on_btc['total_trades']) if eth_on_btc is not None else 'N/A':>18}")


# ---------------------------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------------------------

os.makedirs('data', exist_ok=True)
ranked.to_csv('data/btc_adx_optimisation_results.csv', index=False)
print(f"\n✅ Full results saved → data/btc_adx_optimisation_results.csv")


# ---------------------------------------------------------------------------
# HEATMAP — same format as ETH Day 3
# ---------------------------------------------------------------------------

best_period = int(ranked.iloc[0]['period'])
heatmap_data = results_df[results_df['period'] == best_period].copy()

pivot = heatmap_data.pivot_table(
    index='threshold',
    columns='stop_pct',
    values='profit_factor'
)

fig, axes = plt.subplots(1, 2, figsize=(18, 7))
fig.suptitle(
    f'BTC ADX Optimisation — Profit Factor Heatmap (Period={best_period})',
    fontsize=13, fontweight='bold'
)

# Heatmap
im = axes[0].imshow(pivot.values, cmap='RdYlGn', aspect='auto')
axes[0].set_xticks(range(len(pivot.columns)))
axes[0].set_xticklabels([f"{int(c*100)}%" for c in pivot.columns], fontsize=8)
axes[0].set_yticks(range(len(pivot.index)))
axes[0].set_yticklabels([str(int(t)) for t in pivot.index], fontsize=8)
axes[0].set_xlabel('Stop-Loss %')
axes[0].set_ylabel('ADX Threshold')
axes[0].set_title(f'Profit Factor — BTC (Period={best_period})')
plt.colorbar(im, ax=axes[0])

for i in range(len(pivot.index)):
    for j in range(len(pivot.columns)):
        val = pivot.values[i, j]
        if not np.isnan(val):
            axes[0].text(j, i, f'{val:.2f}',
                        ha='center', va='center',
                        fontsize=7, fontweight='bold')

# Mark ETH parameters if period matches
if best_period == ETH_PERIOD:
    if ETH_THRESHOLD in list(pivot.index) and ETH_STOP in list(pivot.columns):
        t_idx = list(pivot.index).index(ETH_THRESHOLD)
        s_idx = list(pivot.columns).index(ETH_STOP)
        axes[0].add_patch(plt.Rectangle(
            (s_idx - 0.5, t_idx - 0.5), 1, 1,
            fill=False, edgecolor='blue', linewidth=3,
            label='ETH params'
        ))

# Top 15 bar chart
top15 = ranked.head(15).copy()
top15['label'] = top15.apply(
    lambda r: f"ADX{int(r.threshold)}/{int(r.period)}\nStop{r.stop_pct*100:.1f}%",
    axis=1
)
colors = [
    'gold' if (r.threshold == ETH_THRESHOLD and
               r.period == ETH_PERIOD and
               r.stop_pct == ETH_STOP)
    else 'steelblue'
    for _, r in top15.iterrows()
]

axes[1].barh(range(len(top15)), top15['profit_factor'], color=colors)
axes[1].set_yticks(range(len(top15)))
axes[1].set_yticklabels(top15['label'], fontsize=8)
axes[1].invert_yaxis()
axes[1].set_xlabel('Profit Factor')
axes[1].set_title('Top 15 BTC Combinations\nGold = ETH parameters')
axes[1].axvline(1.0, color='red', linestyle='--', alpha=0.5)
axes[1].grid(alpha=0.3, axis='x')

plt.tight_layout()
os.makedirs('Week_5_Notebooks/results', exist_ok=True)
chart_path = 'Week_5_Notebooks/results/btc_adx_optimisation.png'
plt.savefig(chart_path, dpi=150)
plt.close()
print(f"✅ Chart saved → {chart_path}")

print(f"\n{'='*100}")
print(f"BTC ADX OPTIMISATION COMPLETE")
print(f"{'='*100}\n")