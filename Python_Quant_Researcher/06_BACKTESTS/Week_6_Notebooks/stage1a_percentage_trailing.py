# Stage 1a — Percentage Trailing Stop Grid Search (ETH ADX)
# Week 6 Optimisation Plan
#
# Replaces fixed 5% stop with a percentage trailing stop.
# Trailing stop moves up with peak price since entry.
# Grid: ADX threshold (15-22) × ADX period (8-14) × trail_pct (3-15%, step 1%)
# 728 total combinations, ranked by Calmar ratio.
#
# Live baseline: ADX 20/10, fixed 5% stop — Calmar 1.645 (Week 5 daily equity method)

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from ta.trend import ADXIndicator
import os
from itertools import product

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LIVE_THRESHOLD   = 20
LIVE_PERIOD      = 10
LIVE_CALMAR      = 1.645   # Week 5 confirmed — fixed 5% stop, daily equity method
LIVE_FIXED_STOP  = 0.05
MIN_TRADES       = 10
COST_PER_TRADE   = 0.00075 * 2  # 0.15% round-trip (entry + exit taker fees)

# ---------------------------------------------------------------------------
# [FUNCTION] run_backtest_trailing
# ---------------------------------------------------------------------------

def run_backtest_trailing(
    closes:    np.ndarray,
    lows:      np.ndarray,
    signals:   np.ndarray,
    dates:     pd.DatetimeIndex,
    trail_pct: float,
) -> list:
    """
    Bar-by-bar ADX backtest with percentage trailing stop.

    Trailing stop logic:
      - On entry: peak = entry_close, stop = peak * (1 - trail_pct)
      - Each bar while long: stop = max(peak, close) * (1 - trail_pct)
      - Stop checked against daily LOW (same conservative assumption as fixed stop)
      - Stop only moves UP — never locks in a new stop below current stop

    Returns list of trade dicts (empty if no trades).
    """
    position:    int   = 0
    entry_price: float = 0.0
    peak_price:  float = 0.0
    stop_price:  float = 0.0
    entry_date:  object = None
    trades:      list  = []

    for i in range(1, len(closes)):
        low:    float = lows[i]
        close:  float = closes[i]
        signal: bool  = signals[i]

        if position == 1:
            # Stop check comes before peak update (stop was set at yesterday's close)
            if low <= stop_price:
                trades.append({
                    'entry_date':  entry_date,
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'TRAIL_STOP',
                })
                position = 0
                entry_date = None
            elif not signal:
                trades.append({
                    'entry_date':  entry_date,
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'ADX_EXIT',
                })
                position = 0
                entry_date = None
            else:
                # Still long — trail the stop upward with today's close
                if close > peak_price:
                    peak_price = close
                    stop_price = peak_price * (1 - trail_pct)

        elif position == 0 and signal:
            entry_price = close
            peak_price  = close
            stop_price  = peak_price * (1 - trail_pct)
            entry_date  = dates[i]
            position    = 1

    return trades


# ---------------------------------------------------------------------------
# [FUNCTION] build_daily_equity
# ---------------------------------------------------------------------------

def build_daily_equity(trades_df: pd.DataFrame, close_series: pd.Series) -> np.ndarray:
    """
    Mark-to-market daily equity curve (consistent with Week 5 method).
    Equity tracks daily close while in position; flat at 1.0 (or last portfolio
    value) between trades.  Cost is deducted at exit.
    """
    n          = len(close_series)
    closes_arr = close_series.values
    date_to_i  = pd.Series(np.arange(n), index=close_series.index)

    equity    = np.ones(n)
    portfolio = 1.0
    prev_i    = 0

    for _, trade in trades_df.iterrows():
        ei = date_to_i.get(pd.Timestamp(trade['entry_date']))
        xi = date_to_i.get(pd.Timestamp(trade['exit_date']))
        if ei is None or xi is None:
            continue
        equity[prev_i:ei]    = portfolio
        entry_px             = trade['entry_price']
        equity[ei:xi + 1]    = portfolio * closes_arr[ei:xi + 1] / entry_px
        portfolio           *= (1 + trade['return'] - COST_PER_TRADE)
        equity[xi]           = portfolio
        prev_i               = xi + 1

    equity[prev_i:] = portfolio
    return equity


# ---------------------------------------------------------------------------
# [FUNCTION] metrics_from_trades
# ---------------------------------------------------------------------------

def metrics_from_trades(
    trades:       list,
    years:        float,
    close_series: pd.Series,
) -> dict | None:
    """
    Compute performance metrics from a list of trade dicts.

    Calmar  — per-trade equity cumprod (fast; matches Week 5 grid method).
    Sortino — daily equity curve (mark-to-market); consistent with Week 5
              Sharpe correction: mean(daily_ret) / std(downside) * sqrt(365).
    """
    if len(trades) < MIN_TRADES:
        return None

    trades_df = pd.DataFrame(trades)
    returns   = trades_df['return'].values - COST_PER_TRADE

    winners_mask = returns > 0
    losers_mask  = returns <= 0

    win_rate      = winners_mask.mean()
    gross_profit  = returns[winners_mask].sum() if winners_mask.any() else 0.0
    gross_loss    = abs(returns[losers_mask].sum()) if losers_mask.any() else 1e-9
    profit_factor = gross_profit / gross_loss

    equity   = np.cumprod(1 + returns)
    peak     = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_dd   = drawdown.min()

    total_return  = equity[-1] - 1
    annual_return = (1 + total_return) ** (1 / years) - 1
    calmar        = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    # Sortino — daily equity curve, Week 5 method
    first_entry = pd.Timestamp(trades_df['entry_date'].min())
    last_exit   = pd.Timestamp(trades_df['exit_date'].max())
    close_slice = close_series.loc[first_entry:last_exit]
    daily_eq    = build_daily_equity(trades_df, close_slice)
    dr          = np.diff(daily_eq) / daily_eq[:-1]
    downside    = dr[dr < 0]
    sortino     = (dr.mean() / downside.std() * np.sqrt(365)
                   if len(downside) > 0 and downside.std() > 0 else 0.0)

    trail_exits = (trades_df['exit_reason'] == 'TRAIL_STOP').sum()

    return {
        'total_trades':    len(trades_df),
        'win_rate':        win_rate,
        'avg_win':         returns[winners_mask].mean() if winners_mask.any() else 0.0,
        'avg_loss':        returns[losers_mask].mean()  if losers_mask.any() else 0.0,
        'profit_factor':   profit_factor,
        'total_return':    total_return,
        'annual_return':   annual_return,
        'max_drawdown':    max_dd,
        'calmar':          calmar,
        'sortino':         sortino,
        'trail_exits_pct': trail_exits / len(trades_df),
    }


# ---------------------------------------------------------------------------
# FETCH DATA
# ---------------------------------------------------------------------------

print("\nFetching ETH-USD daily data...")
raw = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)

df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.dropna(inplace=True)

years = (df.index[-1] - df.index[0]).days / 365.25
print(f"Data loaded: {df.index[0].date()} → {df.index[-1].date()} ({years:.1f} yrs)")


# ---------------------------------------------------------------------------
# PARAMETER GRID
# ---------------------------------------------------------------------------

thresholds  = list(range(15, 23))               # 15-22 inclusive (8 values)
periods     = list(range(8, 15))                # 8-14 inclusive  (7 values)
trail_pcts  = [round(p / 100, 2) for p in range(3, 16)]  # 3-15% step 1% (13 values)

total = len(thresholds) * len(periods) * len(trail_pcts)
print(f"\nGrid: {len(thresholds)} thresholds × {len(periods)} periods × {len(trail_pcts)} trail_pcts")
print(f"Total combinations: {total}")
print(f"Running grid search...\n")


# ---------------------------------------------------------------------------
# GRID SEARCH — precompute ADX for each period to avoid redundant recalculation
# ---------------------------------------------------------------------------

closes = df['Close'].values
lows   = df['Low'].values
dates  = df.index

# Pre-compute signals for every (threshold, period) pair
adx_signals: dict = {}
for period in periods:
    adx_ind = ADXIndicator(df['High'], df['Low'], df['Close'], window=period)
    adx     = adx_ind.adx().values
    di_pos  = adx_ind.adx_pos().values
    di_neg  = adx_ind.adx_neg().values
    for threshold in thresholds:
        key = (threshold, period)
        adx_signals[key] = (adx >= threshold) & (di_pos > di_neg)

results: list = []
completed:  int = 0

for (threshold, period), trail_pct in product(adx_signals.keys(), trail_pcts):
    signals = adx_signals[(threshold, period)]
    trades  = run_backtest_trailing(closes, lows, signals, dates, trail_pct)
    metrics = metrics_from_trades(trades, years, df['Close'])
    if metrics is not None:
        metrics.update({
            'threshold': threshold,
            'period':    period,
            'trail_pct': trail_pct,
        })
        results.append(metrics)
    completed += 1
    if completed % 100 == 0:
        pct = 100 * completed / total
        print(f"  {completed}/{total} ({pct:.0f}%) combinations done...")

results_df = pd.DataFrame(results)
print(f"\nGrid search complete. {len(results_df)} valid combinations (of {total} tested).\n")


# ---------------------------------------------------------------------------
# RANK BY CALMAR
# ---------------------------------------------------------------------------

ranked = results_df.sort_values('calmar', ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# PRINT TOP 10
# ---------------------------------------------------------------------------

print(f"{'='*115}")
print(f"TOP 10 COMBINATIONS — PERCENTAGE TRAILING STOP (ranked by Calmar ratio, costs included)")
print(f"{'='*115}")
print(f"\n{'Rank':<5} {'Threshold':>10} {'Period':>8} {'Trail%':>8} {'Trades':>8} "
      f"{'Win%':>7} {'Calmar':>8} {'Sortino':>8} {'Annual%':>9} {'Max DD':>8} {'PF':>7} {'StopExit%':>10}")
print(f"{'-'*115}")

for rank, (_, row) in enumerate(ranked.head(10).iterrows(), 1):
    live = (int(row.threshold) == LIVE_THRESHOLD and int(row.period) == LIVE_PERIOD)
    marker = ' <- LIVE ADX' if live else ''
    print(f"  {rank:<4} {int(row.threshold):>10} {int(row.period):>8} "
          f"{row.trail_pct*100:>7.0f}% {int(row.total_trades):>8} "
          f"{row.win_rate:>7.1%} {row.calmar:>8.3f} {row.sortino:>8.3f} "
          f"{row.annual_return:>9.1%} {row.max_drawdown:>8.1%} "
          f"{row.profit_factor:>7.3f} {row.trail_exits_pct:>9.1%}{marker}")


# ---------------------------------------------------------------------------
# CURRENT LIVE PARAMS — ADX 20/10 at all trail_pcts
# ---------------------------------------------------------------------------

live_rows = ranked[
    (ranked['threshold'] == LIVE_THRESHOLD) &
    (ranked['period']    == LIVE_PERIOD)
].sort_values('trail_pct')

print(f"\n{'='*115}")
print(f"LIVE ADX PARAMS (threshold={LIVE_THRESHOLD}, period={LIVE_PERIOD}) — ALL TRAILING STOP LEVELS")
print(f"  Baseline (LIVE, fixed {LIVE_FIXED_STOP*100:.0f}% stop): Calmar {LIVE_CALMAR:.3f}")
print(f"{'='*115}")
print(f"\n{'Trail%':>8} {'Calmar':>8} {'Sortino':>8} {'Annual%':>9} {'Max DD':>8} {'Trades':>8} "
      f"{'Win%':>7} {'PF':>7} {'StopExit%':>10} {'Rank':>6}")
print(f"{'-'*90}")

for _, row in live_rows.iterrows():
    overall_rank = ranked.index[
        (ranked['threshold'] == row.threshold) &
        (ranked['period']    == row.period) &
        (ranked['trail_pct'] == row.trail_pct)
    ][0] + 1
    better = " +" if row.calmar > LIVE_CALMAR else "  "
    print(f"{row.trail_pct*100:>7.0f}%{better} {row.calmar:>8.3f} {row.sortino:>8.3f} "
          f"{row.annual_return:>9.1%} {row.max_drawdown:>8.1%} "
          f"{int(row.total_trades):>8} {row.win_rate:>7.1%} "
          f"{row.profit_factor:>7.3f} {row.trail_exits_pct:>9.1%} "
          f"{overall_rank:>6}")

best_live = live_rows.iloc[live_rows['calmar'].argmax()]
print(f"\n  Best ADX 20/10 trailing: {best_live.trail_pct*100:.0f}% — "
      f"Calmar {best_live.calmar:.3f} vs live fixed-stop Calmar {LIVE_CALMAR:.3f} "
      f"({'IMPROVEMENT' if best_live.calmar > LIVE_CALMAR else 'NO IMPROVEMENT'})")


# ---------------------------------------------------------------------------
# OVERALL SUMMARY
# ---------------------------------------------------------------------------

best = ranked.iloc[0]
print(f"\n{'='*115}")
print(f"OVERALL BEST COMBINATION")
print(f"{'='*115}")
print(f"  ADX {int(best.threshold)}/{int(best.period)} | "
      f"Trail {best.trail_pct*100:.0f}%")
print(f"  Calmar:       {best.calmar:.3f}   (live baseline: {LIVE_CALMAR:.3f})")
print(f"  Sortino:      {best.sortino:.3f}")
print(f"  Annual:       {best.annual_return:.1%}")
print(f"  Max Drawdown: {best.max_drawdown:.1%}")
print(f"  Trades:       {int(best.total_trades)}")
print(f"  Win Rate:     {best.win_rate:.1%}")
print(f"  Profit Factor:{best.profit_factor:.3f}")
print(f"  Stop Exit%:   {best.trail_exits_pct:.1%}")


# ---------------------------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------------------------

os.makedirs('Week_6_Notebooks/results', exist_ok=True)

col_order = [
    'threshold', 'period', 'trail_pct', 'calmar', 'sortino', 'annual_return',
    'max_drawdown', 'total_return', 'total_trades', 'win_rate',
    'avg_win', 'avg_loss', 'profit_factor', 'trail_exits_pct',
]
ranked[col_order].to_csv('Week_6_Notebooks/results/stage1a_results.csv', index=False)
print(f"\n✅ Full results saved → Week_6_Notebooks/results/stage1a_results.csv")


# ---------------------------------------------------------------------------
# HEATMAP — trail_pct vs ADX threshold at best ADX period
# ---------------------------------------------------------------------------

# Find best ADX period by average Calmar across all threshold/trail_pct combos
period_calmar = (
    results_df.groupby('period')['calmar']
    .mean()
    .sort_values(ascending=False)
)
best_period = int(period_calmar.idxmax())
print(f"\nBest ADX period by avg Calmar: {best_period} (avg Calmar {period_calmar.max():.3f})")

period_data = results_df[results_df['period'] == best_period]

pivot = period_data.pivot_table(
    index='threshold',
    columns='trail_pct',
    values='calmar',
)

fig, ax = plt.subplots(figsize=(14, 7))
fig.suptitle(
    f'Stage 1a — Percentage Trailing Stop Grid Search (ETH ADX)\n'
    f'Calmar Ratio Heatmap | ADX Period = {best_period} (best period)',
    fontsize=13, fontweight='bold'
)

vmin = pivot.values.min()
vmax = pivot.values.max()
im   = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto', vmin=vmin, vmax=vmax)

ax.set_xticks(range(len(pivot.columns)))
ax.set_xticklabels([f"{int(c*100)}%" for c in pivot.columns], fontsize=9)
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels([str(int(t)) for t in pivot.index], fontsize=9)
ax.set_xlabel('Trailing Stop %', fontsize=11)
ax.set_ylabel('ADX Threshold', fontsize=11)

# Annotate cells with Calmar values
for i in range(len(pivot.index)):
    for j in range(len(pivot.columns)):
        val = pivot.values[i, j]
        if not np.isnan(val):
            text_color = 'black' if 0.3 < (val - vmin) / (vmax - vmin + 1e-9) < 0.7 else 'white'
            ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                    fontsize=7.5, fontweight='bold', color=text_color)

# Mark live params (threshold=20) on this heatmap
if LIVE_THRESHOLD in list(pivot.index) and best_period == LIVE_PERIOD:
    t_idx = list(pivot.index).index(LIVE_THRESHOLD)
    ax.axhline(t_idx, color='blue', linewidth=0, alpha=0)   # placeholder
    for j in range(len(pivot.columns)):
        ax.add_patch(plt.Rectangle(
            (j - 0.5, t_idx - 0.5), 1, 1,
            fill=False, edgecolor='blue', linewidth=2, linestyle='--'
        ))
    ax.text(-0.8, t_idx, 'LIVE\nADX 20', ha='center', va='center',
            fontsize=8, color='blue', fontweight='bold')

elif LIVE_THRESHOLD in list(pivot.index):
    t_idx = list(pivot.index).index(LIVE_THRESHOLD)
    for j in range(len(pivot.columns)):
        ax.add_patch(plt.Rectangle(
            (j - 0.5, t_idx - 0.5), 1, 1,
            fill=False, edgecolor='blue', linewidth=2, linestyle='--'
        ))
    ax.text(-0.8, t_idx, 'LIVE\nADX 20', ha='center', va='center',
            fontsize=8, color='blue', fontweight='bold')

# Mark the single best cell
best_in_period = period_data.loc[period_data['calmar'].idxmax()]
if best_in_period['threshold'] in list(pivot.index) and best_in_period['trail_pct'] in list(pivot.columns):
    t_idx = list(pivot.index).index(best_in_period['threshold'])
    p_idx = list(pivot.columns).index(best_in_period['trail_pct'])
    ax.add_patch(plt.Rectangle(
        (p_idx - 0.5, t_idx - 0.5), 1, 1,
        fill=False, edgecolor='gold', linewidth=3
    ))

cbar = fig.colorbar(im, ax=ax, label='Calmar Ratio', shrink=0.8)

# Annotation box
textstr = (
    f"Live baseline (fixed 5% stop): Calmar {LIVE_CALMAR:.3f}\n"
    f"Gold border = best in this period\n"
    f"Blue dashed = ADX 20 threshold row"
)
ax.text(1.18, 0.5, textstr, transform=ax.transAxes, fontsize=8,
        verticalalignment='center',
        bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

plt.tight_layout()
heatmap_path = 'Week_6_Notebooks/results/stage1a_heatmap.png'
plt.savefig(heatmap_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Heatmap saved → {heatmap_path}")


# ---------------------------------------------------------------------------
# SECONDARY HEATMAP — average Calmar by period (bar chart)
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle('Stage 1a — Percentage Trailing Stop: Parameter Overview', fontsize=12, fontweight='bold')

# Left: avg Calmar by ADX period
period_avg = results_df.groupby('period')['calmar'].mean().reset_index()
colors_bar = ['gold' if p == best_period else 'steelblue' for p in period_avg['period']]
axes[0].bar(period_avg['period'].astype(str), period_avg['calmar'], color=colors_bar, edgecolor='black')
axes[0].axhline(LIVE_CALMAR, color='red', linestyle='--', linewidth=1.5, label=f'Live baseline {LIVE_CALMAR:.3f}')
axes[0].set_xlabel('ADX Period')
axes[0].set_ylabel('Avg Calmar Ratio')
axes[0].set_title('Average Calmar by ADX Period')
axes[0].legend(fontsize=9)
axes[0].grid(alpha=0.3, axis='y')

# Right: avg Calmar by trail_pct
trail_avg = results_df.groupby('trail_pct')['calmar'].mean().reset_index()
axes[1].bar(
    [f"{int(p*100)}%" for p in trail_avg['trail_pct']],
    trail_avg['calmar'],
    color='steelblue', edgecolor='black'
)
axes[1].axhline(LIVE_CALMAR, color='red', linestyle='--', linewidth=1.5, label=f'Live baseline {LIVE_CALMAR:.3f}')
axes[1].set_xlabel('Trailing Stop %')
axes[1].set_ylabel('Avg Calmar Ratio')
axes[1].set_title('Average Calmar by Trailing Stop %')
axes[1].legend(fontsize=9)
axes[1].grid(alpha=0.3, axis='y')

plt.tight_layout()
overview_path = 'Week_6_Notebooks/results/stage1a_overview.png'
plt.savefig(overview_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Overview chart saved → {overview_path}")


# ---------------------------------------------------------------------------
# RISK REGISTER UPDATE
# ---------------------------------------------------------------------------

print(f"\n{'='*105}")
print(f"STAGE 1a COMPLETE")
print(f"{'='*105}")
print(f"  Risk register A011 (fixed stop, not trailing): EVIDENCE GATHERED")
print(f"  Next step: Stage 1b (ATR trailing stop) then 1c (stability) and 1d (comparison)")
print(f"{'='*105}\n")
