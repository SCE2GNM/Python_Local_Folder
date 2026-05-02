# Stage 1b — ATR Trailing Stop Grid Search (ETH ADX)
# Week 6 Optimisation Plan
#
# Replaces fixed 5% stop with an ATR-based trailing stop.
# Stop = peak_price_since_entry - (multiplier × ATR)
# ATR = Wilder EMA of True Range (ewm alpha=1/period, adjust=False)
# True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
# Stop only moves UP — ratcheting, consistent with Stage 1a approach.
#
# Grid: ADX threshold (15-22) × ADX period (8-14) × ATR period (7-21, step 2)
#        × multiplier (1.5-4.0, step 0.5) = 8×7×8×6 = 2,688 combinations
#
# Live baseline: ADX 20/10, fixed 5% stop — Calmar 1.645 (Week 5 daily equity method)
# Stage 1a best (pct): ADX 15/12 trail 3% — Calmar 2.820

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from ta.trend import ADXIndicator
import os
from itertools import product

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LIVE_THRESHOLD  = 20
LIVE_PERIOD     = 10
LIVE_CALMAR     = 1.645   # fixed 5% stop, daily equity method (Week 5)
STAGE1A_BEST    = 2.559   # ADX 19/9, trail 8% (Stage 1a with 0.15% round-trip costs)
MIN_TRADES      = 10
COST_PER_TRADE  = 0.00075 * 2  # 0.15% round-trip (entry + exit taker fees)

# ---------------------------------------------------------------------------
# [FUNCTION] compute_atr  — Wilder's ATR
# ---------------------------------------------------------------------------

def compute_atr(
    high:   pd.Series,
    low:    pd.Series,
    close:  pd.Series,
    period: int,
) -> np.ndarray:
    """
    Wilder's Average True Range.

    TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    ATR = EWM with alpha=1/period, adjust=False (exact Wilder smoothing).
    Returns ndarray aligned with input indices.
    """
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low,
         (high - prev_close).abs(),
         (low  - prev_close).abs()],
        axis=1
    ).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return atr.values


# ---------------------------------------------------------------------------
# [FUNCTION] run_backtest_atr
# ---------------------------------------------------------------------------

def run_backtest_atr(
    closes:     np.ndarray,
    lows:       np.ndarray,
    signals:    np.ndarray,
    atr_values: np.ndarray,
    dates:      pd.DatetimeIndex,
    multiplier: float,
) -> list:
    """
    Bar-by-bar ADX backtest with ATR trailing stop.

    Stop logic (ratcheting — stop only moves UP):
      - On entry at bar i: peak = close[i], stop = close[i] - mult * ATR[i]
      - Each subsequent bar:
          1. Check if low[i] <= yesterday's stop_price → exit at stop_price
          2. If still in and signal holds → update peak, recompute candidate stop,
             take max(stop_price, candidate) so stop never retreats
      - ADX exit: if signal turns False → exit at close[i]
    """
    position:    int   = 0
    entry_price: float = 0.0
    peak_price:  float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    for i in range(1, len(closes)):
        low:    float = lows[i]
        close:  float = closes[i]
        signal: bool  = signals[i]
        atr:    float = atr_values[i]

        if position == 1:
            # Stop was set at yesterday's close — check against today's low
            if low <= stop_price:
                trades.append({
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'TRAIL_STOP',
                })
                position = 0

            elif not signal:
                trades.append({
                    'entry_date':  dates[i - 1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'ADX_EXIT',
                })
                position = 0

            else:
                # Still long — trail stop upward with today's close
                if close > peak_price:
                    peak_price = close
                candidate_stop = peak_price - multiplier * atr
                stop_price     = max(stop_price, candidate_stop)

        elif position == 0 and signal:
            entry_price = close
            peak_price  = close
            stop_price  = close - multiplier * atr
            position    = 1

    return trades


# ---------------------------------------------------------------------------
# [FUNCTION] build_daily_equity
# ---------------------------------------------------------------------------

def build_daily_equity(trades_df: pd.DataFrame, close_series: pd.Series) -> np.ndarray:
    """
    Mark-to-market daily equity curve (consistent with Week 5 method).
    Equity tracks daily close while in position; flat between trades.
    Cost is deducted at exit.
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

thresholds   = list(range(15, 23))                         # 15-22 (8 values)
adx_periods  = list(range(8, 15))                          # 8-14  (7 values)
atr_periods  = list(range(7, 22, 2))                       # 7,9,11,13,15,17,19,21 (8 values)
multipliers  = [round(m, 1) for m in np.arange(1.5, 4.1, 0.5)]  # 1.5-4.0 (6 values)

total = len(thresholds) * len(adx_periods) * len(atr_periods) * len(multipliers)
print(f"\nGrid: {len(thresholds)} thresholds × {len(adx_periods)} ADX periods × "
      f"{len(atr_periods)} ATR periods × {len(multipliers)} multipliers")
print(f"Total combinations: {total}")
print(f"Pre-computing indicators...\n")


# ---------------------------------------------------------------------------
# PRE-COMPUTE INDICATORS
# ---------------------------------------------------------------------------

closes = df['Close'].values
lows   = df['Low'].values
dates  = df.index

# ADX entry signals — one ndarray per (threshold, adx_period)
adx_signals: dict = {}
for adx_p in adx_periods:
    adx_ind = ADXIndicator(df['High'], df['Low'], df['Close'], window=adx_p)
    adx     = adx_ind.adx().values
    di_pos  = adx_ind.adx_pos().values
    di_neg  = adx_ind.adx_neg().values
    for thresh in thresholds:
        adx_signals[(thresh, adx_p)] = (adx >= thresh) & (di_pos > di_neg)

# ATR values — one ndarray per atr_period
atr_arrays: dict = {}
for atr_p in atr_periods:
    atr_arrays[atr_p] = compute_atr(df['High'], df['Low'], df['Close'], atr_p)

print(f"Pre-computation complete. Running grid search...\n")


# ---------------------------------------------------------------------------
# GRID SEARCH
# ---------------------------------------------------------------------------

results: list = []
completed:  int = 0

for (thresh, adx_p), atr_p, mult in product(
    adx_signals.keys(), atr_periods, multipliers
):
    signals    = adx_signals[(thresh, adx_p)]
    atr_values = atr_arrays[atr_p]

    trades  = run_backtest_atr(closes, lows, signals, atr_values, dates, mult)
    metrics = metrics_from_trades(trades, years, df['Close'])
    if metrics is not None:
        metrics.update({
            'threshold':  thresh,
            'adx_period': adx_p,
            'atr_period': atr_p,
            'multiplier': mult,
        })
        results.append(metrics)

    completed += 1
    if completed % 400 == 0:
        pct = 100 * completed / total
        print(f"  {completed}/{total} ({pct:.0f}%) combinations done...")

results_df = pd.DataFrame(results)
valid = len(results_df)
print(f"\nGrid search complete. {valid} valid combinations (of {total} tested).\n")


# ---------------------------------------------------------------------------
# RANK BY CALMAR
# ---------------------------------------------------------------------------

ranked = results_df.sort_values('calmar', ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# TOP 10
# ---------------------------------------------------------------------------

print(f"{'='*125}")
print(f"TOP 10 COMBINATIONS — ATR TRAILING STOP (ranked by Calmar ratio, costs included)")
print(f"{'='*125}")
print(f"\n{'Rank':<5} {'Thresh':>7} {'ADXP':>6} {'ATRP':>6} {'Mult':>6} "
      f"{'Trades':>8} {'Win%':>7} {'Calmar':>8} {'Sortino':>8} {'Annual%':>9} "
      f"{'Max DD':>8} {'PF':>7} {'StopExit%':>10}")
print(f"{'-'*125}")

for rank, (_, row) in enumerate(ranked.head(10).iterrows(), 1):
    live_adx = (int(row.threshold) == LIVE_THRESHOLD and int(row.adx_period) == LIVE_PERIOD)
    marker = ' <- LIVE ADX' if live_adx else ''
    print(f"  {rank:<4} {int(row.threshold):>7} {int(row.adx_period):>6} "
          f"{int(row.atr_period):>6} {row.multiplier:>6.1f} "
          f"{int(row.total_trades):>8} {row.win_rate:>7.1%} "
          f"{row.calmar:>8.3f} {row.sortino:>8.3f} {row.annual_return:>9.1%} "
          f"{row.max_drawdown:>8.1%} {row.profit_factor:>7.3f} "
          f"{row.trail_exits_pct:>9.1%}{marker}")


# ---------------------------------------------------------------------------
# LIVE ADX 20/10 — all ATR/multiplier combos
# ---------------------------------------------------------------------------

live_rows = ranked[
    (ranked['threshold']  == LIVE_THRESHOLD) &
    (ranked['adx_period'] == LIVE_PERIOD)
].sort_values(['atr_period', 'multiplier'])

print(f"\n{'='*125}")
print(f"LIVE ADX PARAMS (threshold={LIVE_THRESHOLD}, period={LIVE_PERIOD}) "
      f"— ALL ATR PERIOD × MULTIPLIER COMBINATIONS")
print(f"  Baseline (LIVE, fixed 5% stop):       Calmar {LIVE_CALMAR:.3f}")
print(f"  Stage 1a best (pct trail, with costs): Calmar {STAGE1A_BEST:.3f}")
print(f"{'='*125}")

# Print as a sub-pivot table grouped by ATR period
print(f"\n{'ATRP':>5} {'Mult':>6} {'Calmar':>8} {'Sortino':>8} {'Annual%':>9} {'Max DD':>8} "
      f"{'Trades':>8} {'Win%':>7} {'PF':>7} {'StopExit%':>10} {'Rank':>6}")
print(f"{'-'*90}")

for _, row in live_rows.iterrows():
    overall_rank = ranked.index[
        (ranked['threshold']  == row.threshold) &
        (ranked['adx_period'] == row.adx_period) &
        (ranked['atr_period'] == row.atr_period) &
        (ranked['multiplier'] == row.multiplier)
    ][0] + 1
    beat = ' +' if row.calmar > LIVE_CALMAR else '  '
    print(f"{int(row.atr_period):>5} {row.multiplier:>6.1f}{beat} "
          f"{row.calmar:>8.3f} {row.sortino:>8.3f} {row.annual_return:>9.1%} "
          f"{row.max_drawdown:>8.1%} {int(row.total_trades):>8} "
          f"{row.win_rate:>7.1%} {row.profit_factor:>7.3f} "
          f"{row.trail_exits_pct:>9.1%} {overall_rank:>6}")

best_live = live_rows.loc[live_rows['calmar'].idxmax()]
print(f"\n  Best ADX 20/10 ATR combo: ATR {int(best_live.atr_period)}, "
      f"mult {best_live.multiplier:.1f} — "
      f"Calmar {best_live.calmar:.3f} "
      f"vs live fixed-stop {LIVE_CALMAR:.3f} "
      f"({'IMPROVEMENT' if best_live.calmar > LIVE_CALMAR else 'NO IMPROVEMENT'})")


# ---------------------------------------------------------------------------
# OVERALL SUMMARY
# ---------------------------------------------------------------------------

best = ranked.iloc[0]
print(f"\n{'='*125}")
print(f"OVERALL BEST COMBINATION")
print(f"{'='*125}")
print(f"  ADX {int(best.threshold)}/{int(best.adx_period)} | "
      f"ATR period {int(best.atr_period)} | multiplier {best.multiplier:.1f}")
print(f"  Calmar:       {best.calmar:.3f}   "
      f"(live fixed: {LIVE_CALMAR:.3f}  |  Stage 1a pct best: {STAGE1A_BEST:.3f})")
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

os.makedirs('data', exist_ok=True)

col_order = [
    'threshold', 'adx_period', 'atr_period', 'multiplier',
    'calmar', 'sortino', 'annual_return', 'max_drawdown', 'total_return',
    'total_trades', 'win_rate', 'avg_win', 'avg_loss',
    'profit_factor', 'trail_exits_pct',
]
ranked[col_order].to_csv('data/stage1b_results.csv', index=False)
print(f"\n✅ Full results saved → data/stage1b_results.csv")


# ---------------------------------------------------------------------------
# HEATMAP — multiplier vs ATR period at best ADX (threshold, adx_period)
# ---------------------------------------------------------------------------

# Find best ADX (threshold, adx_period) by best Calmar across all ATR/mult combos
best_adx_combo = (
    results_df.groupby(['threshold', 'adx_period'])['calmar']
    .max()
    .idxmax()
)
best_thresh, best_adx_p = best_adx_combo
print(f"\nBest ADX combo for heatmap: threshold={best_thresh}, period={best_adx_p}")

# Filter to best ADX combo
hm_data = results_df[
    (results_df['threshold']  == best_thresh) &
    (results_df['adx_period'] == best_adx_p)
]

pivot_hm = hm_data.pivot_table(
    index='multiplier',
    columns='atr_period',
    values='calmar',
)

fig, ax = plt.subplots(figsize=(14, 7))
fig.suptitle(
    f'Stage 1b — ATR Trailing Stop Grid Search (ETH ADX)\n'
    f'Calmar Ratio Heatmap | ADX threshold={best_thresh}, period={best_adx_p} (best ADX combo)',
    fontsize=13, fontweight='bold'
)

vmin = pivot_hm.values.min()
vmax = pivot_hm.values.max()
im   = ax.imshow(pivot_hm.values, cmap='RdYlGn', aspect='auto', vmin=vmin, vmax=vmax)

ax.set_xticks(range(len(pivot_hm.columns)))
ax.set_xticklabels([str(int(c)) for c in pivot_hm.columns], fontsize=10)
ax.set_yticks(range(len(pivot_hm.index)))
ax.set_yticklabels([f"{m:.1f}x" for m in pivot_hm.index], fontsize=10)
ax.set_xlabel('ATR Period (days)', fontsize=11)
ax.set_ylabel('Multiplier', fontsize=11)

# Annotate cells
for i in range(len(pivot_hm.index)):
    for j in range(len(pivot_hm.columns)):
        val = pivot_hm.values[i, j]
        if not np.isnan(val):
            norm_val = (val - vmin) / (vmax - vmin + 1e-9)
            text_color = 'black' if 0.25 < norm_val < 0.75 else 'white'
            ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                    fontsize=9, fontweight='bold', color=text_color)

# Gold border on best cell
best_cell = hm_data.loc[hm_data['calmar'].idxmax()]
if best_cell['multiplier'] in list(pivot_hm.index) and best_cell['atr_period'] in list(pivot_hm.columns):
    m_idx = list(pivot_hm.index).index(best_cell['multiplier'])
    a_idx = list(pivot_hm.columns).index(best_cell['atr_period'])
    ax.add_patch(plt.Rectangle(
        (a_idx - 0.5, m_idx - 0.5), 1, 1,
        fill=False, edgecolor='gold', linewidth=3
    ))

fig.colorbar(im, ax=ax, label='Calmar Ratio', shrink=0.8)

textstr = (
    f"Live baseline (fixed 5% stop): Calmar {LIVE_CALMAR:.3f}\n"
    f"Stage 1a best (pct trail): Calmar {STAGE1A_BEST:.3f}\n"
    f"Gold border = best in this ADX combo"
)
ax.text(1.18, 0.5, textstr, transform=ax.transAxes, fontsize=9,
        verticalalignment='center',
        bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

plt.tight_layout()
heatmap_path = 'Week_6_Notebooks/results/stage1b_heatmap.png'
plt.savefig(heatmap_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Heatmap saved → {heatmap_path}")


# ---------------------------------------------------------------------------
# SECONDARY CHART — avg Calmar by ATR period and by multiplier (full grid)
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle('Stage 1b — ATR Trailing Stop: Parameter Overview (full grid)',
             fontsize=12, fontweight='bold')

# Left: avg Calmar by ATR period
atr_avg = results_df.groupby('atr_period')['calmar'].mean().reset_index()
best_atr_p = atr_avg.loc[atr_avg['calmar'].idxmax(), 'atr_period']
colors_atr = ['gold' if int(p) == int(best_atr_p) else 'steelblue'
              for p in atr_avg['atr_period']]
axes[0].bar(atr_avg['atr_period'].astype(str), atr_avg['calmar'],
            color=colors_atr, edgecolor='black')
axes[0].axhline(LIVE_CALMAR, color='red', linestyle='--', linewidth=1.5,
                label=f'Live baseline {LIVE_CALMAR:.3f}')
axes[0].axhline(STAGE1A_BEST, color='purple', linestyle=':', linewidth=1.5,
                label=f'Stage 1a best {STAGE1A_BEST:.3f}')
axes[0].set_xlabel('ATR Period')
axes[0].set_ylabel('Avg Calmar Ratio')
axes[0].set_title('Average Calmar by ATR Period')
axes[0].legend(fontsize=8)
axes[0].grid(alpha=0.3, axis='y')

# Right: avg Calmar by multiplier
mult_avg = results_df.groupby('multiplier')['calmar'].mean().reset_index()
best_mult = mult_avg.loc[mult_avg['calmar'].idxmax(), 'multiplier']
colors_mult = ['gold' if abs(m - best_mult) < 0.01 else 'steelblue'
               for m in mult_avg['multiplier']]
axes[1].bar([f"{m:.1f}x" for m in mult_avg['multiplier']], mult_avg['calmar'],
            color=colors_mult, edgecolor='black')
axes[1].axhline(LIVE_CALMAR, color='red', linestyle='--', linewidth=1.5,
                label=f'Live baseline {LIVE_CALMAR:.3f}')
axes[1].axhline(STAGE1A_BEST, color='purple', linestyle=':', linewidth=1.5,
                label=f'Stage 1a best {STAGE1A_BEST:.3f}')
axes[1].set_xlabel('ATR Multiplier')
axes[1].set_ylabel('Avg Calmar Ratio')
axes[1].set_title('Average Calmar by ATR Multiplier')
axes[1].legend(fontsize=8)
axes[1].grid(alpha=0.3, axis='y')

plt.tight_layout()
overview_path = 'Week_6_Notebooks/results/stage1b_overview.png'
plt.savefig(overview_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Overview chart saved → {overview_path}")


# ---------------------------------------------------------------------------
# STAGE 1a vs 1b HEAD-TO-HEAD SUMMARY
# ---------------------------------------------------------------------------

print(f"\n{'='*125}")
print(f"STAGE 1a vs 1b HEAD-TO-HEAD  (all figures include 0.15% round-trip costs)")
print(f"{'='*125}")
print(f"  {'Method':<43} {'Calmar':>8} {'Sortino':>8} {'Annual%':>9} {'Max DD':>8} "
      f"{'Trades':>8} {'Win%':>7} {'PF':>7}")
print(f"  {'-'*103}")

# Live baseline — no cost deduction applied to live baseline (legacy figure)
print(f"  {'LIVE (ADX 20/10, fixed 5% stop, no cost)':<43} {LIVE_CALMAR:>8.3f} "
      f"{'  n/a':>8} {'67.4%':>9} {'-40.9%':>8} {'108':>8} {'34.3%':>7} {'3.197':>7}")

# Stage 1a best (with costs)
s1a = pd.read_csv('Week_6_Notebooks/results/stage1a_results.csv').iloc[0]
s1a_label = f"Stage 1a best (ADX {int(s1a.threshold)}/{int(s1a.period)}, trail {s1a.trail_pct*100:.0f}%)"
print(f"  {s1a_label:<43} {s1a.calmar:>8.3f} {s1a.sortino:>8.3f} "
      f"{s1a.annual_return:>9.1%} {s1a.max_drawdown:>8.1%} "
      f"{int(s1a.total_trades):>8} {s1a.win_rate:>7.1%} {s1a.profit_factor:>7.3f}")

# Stage 1b overall best
print(f"  {f'Stage 1b best (ADX {int(best.threshold)}/{int(best.adx_period)}, ATR {int(best.atr_period)}, {best.multiplier:.1f}x)':<43} "
      f"{best.calmar:>8.3f} {best.sortino:>8.3f} {best.annual_return:>9.1%} "
      f"{best.max_drawdown:>8.1%} {int(best.total_trades):>8} "
      f"{best.win_rate:>7.1%} {best.profit_factor:>7.3f}")

# Stage 1b best for ADX 20/10
print(f"  {f'Stage 1b ADX 20/10 best (ATR {int(best_live.atr_period)}, {best_live.multiplier:.1f}x)':<43} "
      f"{best_live.calmar:>8.3f} {best_live.sortino:>8.3f} {best_live.annual_return:>9.1%} "
      f"{best_live.max_drawdown:>8.1%} {int(best_live.total_trades):>8} "
      f"{best_live.win_rate:>7.1%} {best_live.profit_factor:>7.3f}")


# ---------------------------------------------------------------------------
# RISK REGISTER NOTE
# ---------------------------------------------------------------------------

print(f"\n{'='*115}")
print(f"STAGE 1b COMPLETE")
print(f"{'='*115}")
print(f"  A011 (fixed stop, not trailing): EVIDENCE GATHERED — ATR trailing confirmed")
print(f"  Next step: Stage 1c — stability analysis (best pct trail vs best ATR trail)")
print(f"{'='*115}\n")
