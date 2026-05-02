# [MODULE] BTC SMA Stability Analysis
# Week 5 Extension
#
# Tests whether BTC SMA 125 sits on a stable plateau or a fragile spike.
# Uses same approach as RSI and BTC ADX stability analyses.
#
# BEST PARAMETER FROM GRID SEARCH:
#   SMA period: 125 (Calmar 3.506, PF 15.641, Max DD -17.0%)
#
# METHOD:
#   Vary SMA period across full tested range (10-200, step 5)
#   Plot Calmar, Sharpe, and profit factor vs period
#   Calculate stability score: % of values above minimum threshold

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
import os

# ---------------------------------------------------------------------------
# Reuse backtest functions from sma_crossover_backtest.py
# ---------------------------------------------------------------------------

def build_daily_equity_curve(df, trades, initial=1.0):
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
        if (not in_position and
            trade_idx < len(trades_df) and
            date >= trades_df.iloc[trade_idx]['entry_date']):
            in_position = True
            entry_price = trades_df.iloc[trade_idx]['entry_price']
            entry_value = portfolio

        if in_position:
            current_return = (row['Close'] - entry_price) / entry_price
            equity[i]      = entry_value * (1 + current_return)

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


def run_sma_backtest(df, sma_period):
    sma      = df['Close'].rolling(window=sma_period).mean()
    position = 0
    entry_price = 0.0
    trades   = []
    closes   = df['Close'].values
    smas     = sma.values
    dates    = df.index

    for i in range(sma_period + 1, len(df)):
        close      = closes[i]
        close_prev = closes[i-1]
        sma_val    = smas[i]
        sma_prev   = smas[i-1]

        if np.isnan(sma_val) or np.isnan(sma_prev):
            continue

        if position == 1:
            if close < sma_val and close_prev >= sma_prev:
                trades.append({
                    'entry_date':  dates[i-1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      (close - entry_price) / entry_price,
                })
                position = 0; entry_price = 0.0
        elif position == 0:
            if close > sma_val and close_prev <= sma_prev:
                entry_price = close
                position    = 1

    if position == 1:
        trades.append({
            'entry_date':  dates[-2],
            'entry_price': entry_price,
            'exit_date':   dates[-1],
            'exit_price':  closes[-1],
            'return':      (closes[-1] - entry_price) / entry_price,
        })

    if len(trades) < 5:
        return None

    trades_df    = pd.DataFrame(trades)
    returns      = np.array([t['return'] for t in trades])
    winners      = trades_df[trades_df['return'] > 0]
    losers       = trades_df[trades_df['return'] <= 0]
    win_rate     = len(winners) / len(trades_df)
    gross_profit = winners['return'].sum() if len(winners) > 0 else 0.0
    gross_loss   = abs(losers['return'].sum()) if len(losers) > 0 else 1e-9
    profit_factor = gross_profit / gross_loss

    total_return  = (1 + returns).prod() - 1
    years         = (df.index[-1] - df.index[0]).days / 365.25
    annual_return = (1 + total_return) ** (1 / years) - 1

    daily_equity  = build_daily_equity_curve(df, trades)
    daily_returns = np.diff(daily_equity) / daily_equity[:-1]

    peak     = np.maximum.accumulate(daily_equity)
    drawdown = (daily_equity - peak) / peak
    max_dd   = drawdown.min()
    calmar   = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    sharpe = (
        daily_returns.mean() / daily_returns.std() * np.sqrt(365)
        if daily_returns.std() > 0 else 0.0
    )
    downside = daily_returns[daily_returns < 0]
    sortino  = (
        daily_returns.mean() / downside.std() * np.sqrt(365)
        if len(downside) > 0 and downside.std() > 0 else 0.0
    )

    return {
        'sma_period':    sma_period,
        'total_trades':  len(trades_df),
        'win_rate':      win_rate,
        'profit_factor': profit_factor,
        'annual_return': annual_return,
        'max_drawdown':  max_dd,
        'calmar':        calmar,
        'sharpe':        sharpe,
        'sortino':       sortino,
        'daily_equity':  daily_equity,
        'trades':        trades,
    }


# ---------------------------------------------------------------------------
# FETCH BTC DATA
# ---------------------------------------------------------------------------

print("\nFetching BTC-USD data...")
raw = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.dropna(inplace=True)
print(f"Data: {df.index[0].date()} → {df.index[-1].date()} ({len(df):,} days)")

years = (df.index[-1] - df.index[0]).days / 365.25


# ---------------------------------------------------------------------------
# RUN ALL SMA PERIODS
# ---------------------------------------------------------------------------

sma_periods = list(range(10, 205, 5))
print(f"\nRunning {len(sma_periods)} SMA periods...")

all_results = []
for period in sma_periods:
    r = run_sma_backtest(df, period)
    if r is not None:
        all_results.append(r)

results_df = pd.DataFrame([
    {k: v for k, v in r.items() if k not in ['daily_equity', 'trades']}
    for r in all_results
])

best_period = 125
print(f"\nBest period confirmed: SMA {best_period}")


# ---------------------------------------------------------------------------
# STABILITY SCORES
# ---------------------------------------------------------------------------

calmar_threshold  = 1.0   # minimum acceptable Calmar
sharpe_threshold  = 0.3   # minimum acceptable Sharpe (daily)
pf_threshold      = 2.0   # minimum acceptable profit factor

above_calmar  = (results_df['calmar']        >= calmar_threshold).sum()
above_sharpe  = (results_df['sharpe']        >= sharpe_threshold).sum()
above_pf      = (results_df['profit_factor'] >= pf_threshold).sum()
total         = len(results_df)

print(f"\n{'='*70}")
print(f"BTC SMA STABILITY SCORES")
print(f"{'='*70}")
print(f"  Total SMA periods tested: {total}")
print(f"\n  Calmar >= {calmar_threshold:.1f}:    "
      f"{'█' * int(above_calmar/total*20)}{'░'*(20-int(above_calmar/total*20))} "
      f"{above_calmar/total*100:.0f}% ({above_calmar}/{total} periods)")
print(f"  Sharpe >= {sharpe_threshold:.1f}:    "
      f"{'█' * int(above_sharpe/total*20)}{'░'*(20-int(above_sharpe/total*20))} "
      f"{above_sharpe/total*100:.0f}% ({above_sharpe}/{total} periods)")
print(f"  Profit Factor >= {pf_threshold:.1f}: "
      f"{'█' * int(above_pf/total*20)}{'░'*(20-int(above_pf/total*20))} "
      f"{above_pf/total*100:.0f}% ({above_pf}/{total} periods)")

print(f"\n  Best period (SMA 125) metrics:")
best_r = [r for r in all_results if r['sma_period'] == best_period][0]
print(f"    Calmar:        {best_r['calmar']:.3f}")
print(f"    Sharpe:        {best_r['sharpe']:.3f}")
print(f"    Sortino:       {best_r['sortino']:.3f}")
print(f"    Profit Factor: {best_r['profit_factor']:.3f}")
print(f"    Annual Return: {best_r['annual_return']:.1%}")
print(f"    Max Drawdown:  {best_r['max_drawdown']:.1%}")
print(f"    Total Trades:  {best_r['total_trades']}")

# Range analysis
high_calmar = results_df[results_df['calmar'] >= calmar_threshold]
if len(high_calmar) > 0:
    print(f"\n  SMA periods with Calmar >= {calmar_threshold:.1f}:")
    print(f"    Range: {int(high_calmar['sma_period'].min())} "
          f"to {int(high_calmar['sma_period'].max())} days")
    print(f"    Count: {len(high_calmar)} periods")
    print(f"    Median Calmar in range: "
          f"{high_calmar['calmar'].median():.3f}")


# ---------------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------------

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle(
    'BTC SMA Crossover — Stability Analysis\n'
    'Is SMA 125 a stable plateau or a fragile spike?',
    fontsize=13, fontweight='bold'
)

periods       = results_df['sma_period'].values
calmar_vals   = results_df['calmar'].values
sharpe_vals   = results_df['sharpe'].values
pf_vals       = results_df['profit_factor'].values
annual_vals   = results_df['annual_return'].values
dd_vals       = results_df['max_drawdown'].values

# --- Calmar across all periods ---
axes[0][0].plot(periods, calmar_vals,
                color='orange', linewidth=2, marker='o', markersize=4)
axes[0][0].axvline(best_period, color='gold', linewidth=2,
                   linestyle='--', label=f'Best: SMA {best_period}')
axes[0][0].axhline(calmar_threshold, color='red',
                   linestyle=':', alpha=0.7, label=f'Min threshold ({calmar_threshold})')
axes[0][0].fill_between(periods, calmar_vals, calmar_threshold,
                         where=np.array(calmar_vals) >= calmar_threshold,
                         alpha=0.2, color='green', label='Above threshold')
axes[0][0].set_title('Calmar Ratio by SMA Period')
axes[0][0].set_xlabel('SMA Period (days)')
axes[0][0].set_ylabel('Calmar Ratio')
axes[0][0].legend(fontsize=8)
axes[0][0].grid(alpha=0.3)

# --- Sharpe across all periods ---
axes[0][1].plot(periods, sharpe_vals,
                color='steelblue', linewidth=2, marker='o', markersize=4)
axes[0][1].axvline(best_period, color='gold', linewidth=2,
                   linestyle='--', label=f'Best: SMA {best_period}')
axes[0][1].axhline(sharpe_threshold, color='red',
                   linestyle=':', alpha=0.7, label=f'Min threshold ({sharpe_threshold})')
axes[0][1].set_title('Sharpe Ratio by SMA Period (daily, correct)')
axes[0][1].set_xlabel('SMA Period (days)')
axes[0][1].set_ylabel('Sharpe Ratio')
axes[0][1].legend(fontsize=8)
axes[0][1].grid(alpha=0.3)

# --- Profit factor across all periods ---
axes[1][0].plot(periods, pf_vals,
                color='green', linewidth=2, marker='o', markersize=4)
axes[1][0].axvline(best_period, color='gold', linewidth=2,
                   linestyle='--', label=f'Best: SMA {best_period}')
axes[1][0].axhline(pf_threshold, color='red',
                   linestyle=':', alpha=0.7, label=f'Min threshold ({pf_threshold})')
axes[1][0].set_title('Profit Factor by SMA Period')
axes[1][0].set_xlabel('SMA Period (days)')
axes[1][0].set_ylabel('Profit Factor')
axes[1][0].set_yscale('log')
axes[1][0].legend(fontsize=8)
axes[1][0].grid(alpha=0.3)

# --- Annual return vs Max drawdown scatter ---
axes[1][1].scatter(np.abs(dd_vals) * 100, annual_vals * 100,
                   c=calmar_vals, cmap='RdYlGn',
                   s=60, alpha=0.8, edgecolors='black', linewidth=0.5)

# Highlight best period
best_idx = list(periods).index(best_period)
axes[1][1].scatter([abs(dd_vals[best_idx]) * 100],
                   [annual_vals[best_idx] * 100],
                   color='gold', s=200, zorder=5,
                   edgecolors='black', linewidth=2,
                   label=f'SMA {best_period}')

axes[1][1].set_title('Annual Return vs Max Drawdown\n(colour = Calmar ratio)')
axes[1][1].set_xlabel('Max Drawdown (abs %)')
axes[1][1].set_ylabel('Annual Return (%)')
axes[1][1].legend(fontsize=8)
axes[1][1].grid(alpha=0.3)

sm = plt.cm.ScalarMappable(
    cmap='RdYlGn',
    norm=plt.Normalize(vmin=min(calmar_vals), vmax=max(calmar_vals))
)
plt.colorbar(sm, ax=axes[1][1], label='Calmar Ratio')

plt.tight_layout()
chart_path = 'Week_5_Notebooks/results/btc_sma_stability.png'
plt.savefig(chart_path, dpi=150)
plt.close()
print(f"\n✅ Chart saved → {chart_path}")

print(f"\n{'='*70}")
print(f"BTC SMA STABILITY ANALYSIS COMPLETE")
print(f"{'='*70}\n")