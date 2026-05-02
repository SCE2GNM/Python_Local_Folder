# Stage 2 — Enhanced Results Analysis Suite
# Produces three focused charts from Stage 2a grid results:
#   Chart 1: Parallel coordinates — top 50 by annual return
#   Chart 2: Plateau stability — SMA and trail sweeps for SMA 135/25%
#   Chart 3: Drawdown profile (underwater curve) — two candidates vs B&H
#
# Primary metric throughout: Annual Return %
# Data source: data/stage2a_results_extended.csv (171 combos, includes 22.5% and 25% trail)

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import yfinance as yf

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)

COST_PER_TRADE  = 0.00075 * 2
MIN_TRADES      = 5
LOW_TRADES_FLAG = 30

PRIMARY_SMA     = 135;  PRIMARY_TRAIL   = 0.25
SECONDARY_SMA   = 145;  SECONDARY_TRAIL = 0.20

# Annual return and Sortino thresholds for Chart 2 shading
ANNUAL_MIN  = 20.0   # %
SORTINO_MIN = 0.8

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

print("Fetching BTC-USD daily data...")
raw = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = raw[['Open', 'High', 'Low', 'Close']].dropna().copy()
df.index = pd.to_datetime(df.index)
closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index
years_full = (df.index[-1] - df.index[0]).days / 365.25
print(f"  {df.index[0].date()} → {df.index[-1].date()} ({len(df)} bars, {years_full:.2f} yrs)")

# Load grid results — use extended CSV (includes 25% trail)
csv_path = os.path.join(DATA_DIR, 'stage2a_results_extended.csv')
df_grid = pd.read_csv(csv_path)
df_grid['annual_return_pct'] = df_grid['annual_return']   # CSV already stores as % (e.g. 46.9)
df_grid['max_drawdown_pct']  = df_grid['max_drawdown']    # CSV already stores as % (e.g. -15.1)
# Confirm
print(f"  Loaded {len(df_grid)} grid rows from {os.path.basename(csv_path)}")

# ---------------------------------------------------------------------------
# Backtest (needed for Chart 3 daily equity)
# ---------------------------------------------------------------------------

def run_sma_pct_trail(sma_period, trail_pct):
    sma_vals = pd.Series(closes).rolling(sma_period, min_periods=sma_period).mean().values
    fv = int(np.argmax(~np.isnan(sma_vals)))
    position = entry_i = 0
    entry_price = peak_price = stop_price = 0.0
    trades = []; sig_prev = False
    for i in range(fv, len(closes)):
        close, low, sv = closes[i], lows[i], sma_vals[i]
        if np.isnan(sv): continue
        sig_cur = close > sv
        if position == 1:
            if close > peak_price:
                peak_price = close; stop_price = peak_price * (1 - trail_pct)
            if low <= stop_price:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': stop_price,
                               'return': (stop_price - entry_price) / entry_price,
                               'exit_reason': 'TRAIL_STOP'}); position = 0
            elif not sig_cur:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': close,
                               'return': (close - entry_price) / entry_price,
                               'exit_reason': 'SMA_EXIT'}); position = 0
        if position == 0 and sig_cur and not sig_prev:
            position = 1; entry_i = i; entry_price = close
            peak_price = close; stop_price = close * (1 - trail_pct)
        sig_prev = sig_cur
    if position == 1:
        trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                       'exit_date': dates[-1], 'exit_price': closes[-1],
                       'return': (closes[-1] - entry_price) / entry_price,
                       'exit_reason': 'END'})
    return trades


def build_daily_equity_full(trades_list):
    """Return equity curve as pd.Series indexed by df.index (full date range)."""
    n  = len(df)
    d2i = pd.Series(np.arange(n), index=df.index)
    eq  = np.ones(n)
    port = 1.0; prev = 0
    for t in trades_list:
        ei = d2i.get(pd.Timestamp(t['entry_date']))
        xi = d2i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None: continue
        eq[prev:ei] = port
        eq[ei:xi+1] = port * closes[ei:xi+1] / t['entry_price']
        port *= (1 + t['return'] - COST_PER_TRADE)
        eq[xi] = port; prev = xi + 1
    eq[prev:] = port
    return pd.Series(eq, index=df.index)


def underwater_curve(equity_series):
    """Returns drawdown % series: (current - peak) / peak * 100."""
    peak = equity_series.cummax()
    return (equity_series - peak) / peak * 100


def max_drawdown_info(dd_series):
    """Returns (trough_date, trough_value, recovery_date_or_None)."""
    trough_val  = dd_series.min()
    trough_date = dd_series.idxmin()
    # Recovery: first date after trough where dd >= 0
    after = dd_series[trough_date:]
    recovered = after[after >= -0.001]
    rec_date = recovered.index[0] if len(recovered) > 0 else None
    return trough_date, trough_val, rec_date

# ---------------------------------------------------------------------------
# Run backtests for the two candidates
# ---------------------------------------------------------------------------

print("\nRunning backtests for primary and secondary candidates...")
trades_pri  = run_sma_pct_trail(PRIMARY_SMA,   PRIMARY_TRAIL)
trades_sec  = run_sma_pct_trail(SECONDARY_SMA, SECONDARY_TRAIL)

eq_pri = build_daily_equity_full(trades_pri)
eq_sec = build_daily_equity_full(trades_sec)
eq_bnh = pd.Series(closes / closes[0], index=df.index)

dd_pri = underwater_curve(eq_pri)
dd_sec = underwater_curve(eq_sec)
dd_bnh = underwater_curve(eq_bnh)

print(f"  Primary   SMA {PRIMARY_SMA}/{PRIMARY_TRAIL*100:.0f}%: {len(trades_pri)} trades")
print(f"  Secondary SMA {SECONDARY_SMA}/{SECONDARY_TRAIL*100:.0f}%: {len(trades_sec)} trades")

# ---------------------------------------------------------------------------
# CHART 1 — Parallel Coordinates: Top 50 by Annual Return
# ---------------------------------------------------------------------------
print("\nBuilding Chart 1 — Parallel Coordinates...")

top50 = df_grid.nlargest(50, 'annual_return_pct').reset_index(drop=True)
best  = top50.iloc[0]   # highest annual return

# Five axes in display order.
# MaxDD uses max_drawdown_pct directly (all-negative). Standard minmax:
#   most negative (worst) → 0 (bottom)   least negative (best) → 1 (top)
#   → "up = less negative = better" with no extra inversion step.
axes_cols   = ['annual_return_pct', 'sortino', 'max_drawdown_pct', 'calmar', 'total_trades']
axes_labels = ['Annual\nReturn %', 'Sortino', 'Max DD\n(↑ = less negative)', 'Calmar', 'Trades']

# Normalise each axis to [0, 1] for parallel coords display
norms = {}
for col in axes_cols:
    lo, hi = top50[col].min(), top50[col].max()
    norms[col] = (top50[col] - lo) / (hi - lo) if hi > lo else pd.Series(0.5, index=top50.index)

# Colour by annual return (green = high, red = low)
norm_colour = mcolors.Normalize(vmin=top50['annual_return_pct'].min(),
                                 vmax=top50['annual_return_pct'].max())
cmap = plt.cm.RdYlGn

fig, ax = plt.subplots(figsize=(13, 7))
ax.set_xlim(-0.1, len(axes_cols) - 0.9)
ax.set_ylim(-0.05, 1.15)
ax.axis('off')

# Draw vertical axis lines and tick labels
for j, (col, label) in enumerate(zip(axes_cols, axes_labels)):
    ax.axvline(j, color='#888888', linewidth=1.2, alpha=0.5)
    ax.text(j, -0.04, label, ha='center', va='top', fontsize=9, color='#333333', fontweight='bold')
    lo, hi = top50[col].min(), top50[col].max()
    # Tick at top and bottom with actual values
    if col == 'max_drawdown_pct':
        # All-negative: lo = worst (most negative), hi = best (least negative)
        ax.text(j, 0.0,  f'{lo:.1f}%', ha='center', va='top',   fontsize=7, color='#555555')
        ax.text(j, 1.01, f'{hi:.1f}%', ha='center', va='bottom', fontsize=7, color='#555555')
        ax.text(j, 1.09, '(inverted)', ha='center', va='bottom', fontsize=6.5, color='#888888')
    elif col == 'annual_return_pct':
        ax.text(j, 0.0,  f'{lo:.1f}%',  ha='center', va='top',   fontsize=7, color='#555555')
        ax.text(j, 1.01, f'{hi:.1f}%',  ha='center', va='bottom', fontsize=7, color='#555555')
    elif col == 'total_trades':
        ax.text(j, 0.0,  f'{lo:.0f}',   ha='center', va='top',   fontsize=7, color='#555555')
        ax.text(j, 1.01, f'{hi:.0f}',   ha='center', va='bottom', fontsize=7, color='#555555')
    else:
        ax.text(j, 0.0,  f'{lo:.2f}',   ha='center', va='top',   fontsize=7, color='#555555')
        ax.text(j, 1.01, f'{hi:.2f}',   ha='center', va='bottom', fontsize=7, color='#555555')

# Draw lines for each strategy (back to front so best strategy drawn last / on top)
for idx in reversed(top50.index):
    row    = top50.loc[idx]
    colour = cmap(norm_colour(row['annual_return_pct']))
    ys     = [norms[col].loc[idx] for col in axes_cols]
    xs     = list(range(len(axes_cols)))
    # Slightly bolder for the primary and secondary candidates
    is_pri = (row['sma_period'] == PRIMARY_SMA   and abs(row['trail_pct'] - PRIMARY_TRAIL*100)   < 0.1)
    is_sec = (row['sma_period'] == SECONDARY_SMA and abs(row['trail_pct'] - SECONDARY_TRAIL*100) < 0.1)
    lw     = 2.5 if (is_pri or is_sec) else 0.9
    alpha  = 0.95 if (is_pri or is_sec) else 0.55
    ax.plot(xs, ys, color=colour, linewidth=lw, alpha=alpha, zorder=3 if (is_pri or is_sec) else 2)

# Annotate best strategy by annual return
best_ys = [norms[col].loc[0] for col in axes_cols]
ax.scatter(range(len(axes_cols)), best_ys, color='#00AA44', s=50, zorder=6)
label_txt = (f"Best by Annual%:\n"
             f"SMA {int(best['sma_period'])} / trail {best['trail_pct']:.1f}%\n"
             f"Ann: {best['annual_return_pct']:.1f}%  DD: {best['max_drawdown_pct']:.1f}%\n"
             f"Sortino: {best['sortino']:.2f}  Calmar: {best['calmar']:.2f}")
ax.annotate(label_txt, xy=(0, best_ys[0]), xytext=(-0.06, best_ys[0] + 0.18),
            fontsize=8, color='#006622', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#006622', lw=1.2),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8FFE8', edgecolor='#006622', alpha=0.9))

# Colorbar
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm_colour)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax, orientation='vertical', fraction=0.025, pad=0.01,
                    shrink=0.65, aspect=20)
cbar.set_label('Annual Return %', fontsize=9)

ax.set_title('BTC SMA Strategy Space — Top 50 by Annual Return',
             fontsize=14, fontweight='bold', pad=15)

fig.tight_layout()
out1 = os.path.join(RESULTS_DIR, 'stage2_parallel_coordinates.png')
fig.savefig(out1, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"  Saved → {out1}")

# ---------------------------------------------------------------------------
# CHART 2 — Plateau Stability Charts
# ---------------------------------------------------------------------------
print("Building Chart 2 — Plateau Stability Charts...")

# SMA sweep at trail = 25%
trail_fixed = PRIMARY_TRAIL * 100   # 25.0
sma_sweep   = df_grid[np.abs(df_grid['trail_pct'] - trail_fixed) < 0.01].sort_values('sma_period')

# Trail sweep at SMA = 135
sma_fixed   = PRIMARY_SMA
trail_sweep = df_grid[df_grid['sma_period'] == sma_fixed].sort_values('trail_pct')

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle('Parameter Sensitivity — SMA 135 / Trail 25%',
             fontsize=13, fontweight='bold', y=1.01)

ANNUAL_COLOR  = '#1565C0'   # deep blue
SORTINO_COLOR = '#B71C1C'   # deep red
SHADE_COLOR   = '#C8E6C9'   # light green

def draw_sensitivity_subplot(ax, x_vals, annual_pct, sortino_vals, xlabel,
                              highlight_x, x_fmt='.0f'):
    ax2r = ax.twinx()

    # Identify where BOTH thresholds are met
    both_met = (annual_pct >= ANNUAL_MIN) & (sortino_vals >= SORTINO_MIN)

    # Shade region where both conditions met
    if isinstance(x_vals.iloc[0], float) and x_vals.iloc[0] < 1:
        xs_plot = x_vals * 100   # convert fraction to %
        hl_x    = highlight_x * 100
    else:
        xs_plot = x_vals.copy()
        hl_x    = float(highlight_x)

    # Shade each passing segment
    for i in range(len(xs_plot) - 1):
        if both_met.iloc[i]:
            lo_x = xs_plot.iloc[i]
            hi_x = xs_plot.iloc[i+1] if i+1 < len(xs_plot) else xs_plot.iloc[i]
            ax.axvspan(lo_x - (hi_x - lo_x)*0.5, lo_x + (hi_x - lo_x)*0.5,
                       alpha=0.35, color=SHADE_COLOR, zorder=0)
    # Also shade last point if it passes
    if len(xs_plot) > 0 and both_met.iloc[-1]:
        step = xs_plot.iloc[-1] - xs_plot.iloc[-2] if len(xs_plot) > 1 else 1
        ax.axvspan(xs_plot.iloc[-1] - step*0.5, xs_plot.iloc[-1] + step*0.5,
                   alpha=0.35, color=SHADE_COLOR, zorder=0)

    # Reference lines
    ax.axhline(ANNUAL_MIN,  color='#777777', linestyle='--', linewidth=1.2,
               alpha=0.8, label=f'Annual {ANNUAL_MIN}% floor', zorder=1)
    ax2r.axhline(SORTINO_MIN, color='#AAAAAA', linestyle=':', linewidth=1.2,
                 alpha=0.8, label=f'Sortino {SORTINO_MIN} floor', zorder=1)

    # Lines
    ax.plot(xs_plot, annual_pct, color=ANNUAL_COLOR, linewidth=2.2,
            marker='o', markersize=5, label='Annual Return %', zorder=4)
    ax2r.plot(xs_plot, sortino_vals, color=SORTINO_COLOR, linewidth=2.0,
              marker='s', markersize=4.5, linestyle='--', label='Sortino', zorder=4)

    # Mark the primary candidate
    ax.axvline(hl_x, color='#006622', linestyle='-', linewidth=1.5, alpha=0.5, zorder=2)
    ax.scatter([hl_x], [annual_pct[x_vals == highlight_x].values[0]],
               color=ANNUAL_COLOR, s=80, zorder=5, edgecolors='white', linewidths=1.5)
    ax2r.scatter([hl_x], [sortino_vals[x_vals == highlight_x].values[0]],
                 color=SORTINO_COLOR, s=60, zorder=5, marker='D',
                 edgecolors='white', linewidths=1.5)

    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel('Annual Return %', color=ANNUAL_COLOR, fontsize=10)
    ax2r.set_ylabel('Sortino Ratio', color=SORTINO_COLOR, fontsize=10)
    ax.tick_params(axis='y', labelcolor=ANNUAL_COLOR)
    ax2r.tick_params(axis='y', labelcolor=SORTINO_COLOR)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.0f%%'))

    # Combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2r.get_legend_handles_labels()
    green_patch = mpatches.Patch(color=SHADE_COLOR, alpha=0.7, label='Both thresholds met')
    ax.legend(lines1 + lines2 + [green_patch], labels1 + labels2 + ['Both thresholds met'],
              fontsize=8, loc='upper left')

    ax.grid(axis='y', alpha=0.3)
    return ax2r

# Left subplot: SMA sweep, trail fixed at 25%
draw_sensitivity_subplot(ax1,
    x_vals      = sma_sweep['sma_period'],
    annual_pct  = sma_sweep['annual_return_pct'],
    sortino_vals = sma_sweep['sortino'],
    xlabel      = 'SMA Period  (trail fixed at 25%)',
    highlight_x = PRIMARY_SMA,
    x_fmt       = '.0f')
ax1.set_title(f'SMA Sensitivity  (trail = {trail_fixed:.0f}%)', fontsize=11)
ax1.xaxis.set_major_formatter(mticker.FormatStrFormatter('%d'))

# Right subplot: trail sweep, SMA fixed at 135
draw_sensitivity_subplot(ax2,
    x_vals       = trail_sweep['trail_pct'] / 100,   # stored as % in CSV e.g. 25.0 → pass as 0.25
    annual_pct   = trail_sweep['annual_return_pct'],
    sortino_vals = trail_sweep['sortino'],
    xlabel       = 'Trail Stop %  (SMA fixed at 135)',
    highlight_x  = PRIMARY_TRAIL,
    x_fmt        = '.1f')
ax2.set_title(f'Trail Stop Sensitivity  (SMA = {sma_fixed})', fontsize=11)
ax2.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.0f%%'))

fig.tight_layout()
out2 = os.path.join(RESULTS_DIR, 'stage2_plateau_charts.png')
fig.savefig(out2, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"  Saved → {out2}")

# ---------------------------------------------------------------------------
# CHART 3 — Drawdown Profile (Underwater Curve)
# ---------------------------------------------------------------------------
print("Building Chart 3 — Drawdown Profile...")

trough_date_pri, trough_val_pri, rec_date_pri = max_drawdown_info(dd_pri)
trough_date_sec, trough_val_sec, rec_date_sec = max_drawdown_info(dd_sec)
trough_date_bnh, trough_val_bnh, rec_date_bnh = max_drawdown_info(dd_bnh)

def recovery_label(trough_date, rec_date):
    if rec_date is None:
        return 'No recovery yet'
    days = (rec_date - trough_date).days
    if days < 30:
        return f'Recovered in {days}d'
    months = days / 30.44
    if months < 24:
        return f'Recovered in {months:.0f}m'
    return f'Recovered in {months/12:.1f}yr'

fig, ax = plt.subplots(figsize=(14, 6))

# 2021 bull run shaded region: roughly Jan 2021 – Nov 2021
bull_start = pd.Timestamp('2021-01-01')
bull_end   = pd.Timestamp('2021-11-10')
ax.axvspan(bull_start, bull_end, alpha=0.12, color='gold', zorder=0,
           label='2021 bull run')

# Draw underwater curves
ax.plot(df.index, dd_bnh,  color='#E53935', linewidth=1.4, alpha=0.8, label='BTC Buy-and-Hold')
ax.plot(df.index, dd_sec,  color='#7B1FA2', linewidth=1.6, alpha=0.85,
        label=f'SMA {SECONDARY_SMA}/trail {SECONDARY_TRAIL*100:.0f}%  (secondary)')
ax.plot(df.index, dd_pri,  color='#1565C0', linewidth=2.0, alpha=0.9,
        label=f'SMA {PRIMARY_SMA}/trail {PRIMARY_TRAIL*100:.0f}%  (primary)')

# Fill under primary
ax.fill_between(df.index, dd_pri, 0, alpha=0.12, color='#1565C0')

# Reference zero line
ax.axhline(0, color='#333333', linewidth=0.8, alpha=0.5)

# Annotate max drawdown for each strategy
for (td, tv, rd, colour, name) in [
    (trough_date_bnh, trough_val_bnh, rec_date_bnh, '#E53935', 'B&H'),
    (trough_date_sec, trough_val_sec, rec_date_sec, '#7B1FA2', f'SMA{SECONDARY_SMA}/{SECONDARY_TRAIL*100:.0f}%'),
    (trough_date_pri, trough_val_pri, rec_date_pri, '#1565C0', f'SMA{PRIMARY_SMA}/{PRIMARY_TRAIL*100:.0f}%'),
]:
    ax.scatter([td], [tv], color=colour, s=70, zorder=5, edgecolors='white', linewidths=1.5)
    rec_str = recovery_label(td, rd)
    offset_x = pd.DateOffset(days=90)
    v_offset  = -3 if tv > -70 else 3
    ax.annotate(
        f'{name}\n{tv:.1f}%\n{rec_str}',
        xy=(td, tv),
        xytext=(td + offset_x, tv + v_offset),
        fontsize=7.5, color=colour, fontweight='bold',
        arrowprops=dict(arrowstyle='->', color=colour, lw=0.9),
        bbox=dict(boxstyle='round,pad=0.25', facecolor='white', edgecolor=colour, alpha=0.85)
    )

# Label 2021 bull run
ax.text(pd.Timestamp('2021-01-15'), ax.get_ylim()[0] * 0.05 + 0.5,
        '2021\nbull run', fontsize=8, color='#856404', ha='left', va='bottom',
        style='italic')

ax.set_ylabel('Drawdown from Peak (%)', fontsize=11)
ax.set_xlabel('Date', fontsize=11)
ax.set_title('Drawdown Profile — How Long and Deep Are the Losing Periods?',
             fontsize=13, fontweight='bold')
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.0f%%'))
ax.legend(fontsize=9, loc='lower left')
ax.grid(axis='both', alpha=0.25)
ax.set_xlim(df.index[0], df.index[-1])

fig.tight_layout()
out3 = os.path.join(RESULTS_DIR, 'stage2_drawdown_profile.png')
fig.savefig(out3, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"  Saved → {out3}")

# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("SUMMARY REPORT")
print("=" * 70)

# Q1: Which strategy has highest annual return with Sortino > 0.8 and MaxDD > -25%?
filtered = df_grid[(df_grid['sortino'] >= SORTINO_MIN) &
                   (df_grid['max_drawdown_pct'] > -25.0)].copy()
filtered = filtered.sort_values('annual_return_pct', ascending=False)

print(f"\n  Filter: Sortino ≥ {SORTINO_MIN}  AND  MaxDD better than -25%")
print(f"  Qualifying strategies: {len(filtered)} / {len(df_grid)}")
if len(filtered) > 0:
    top = filtered.iloc[0]
    print(f"\n  ┌─ BEST QUALIFYING STRATEGY (highest annual return) ───────────────")
    print(f"  │  SMA period: {int(top['sma_period'])}  |  Trail: {top['trail_pct']:.1f}%")
    print(f"  │  Annual return: {top['annual_return_pct']:.1f}%")
    print(f"  │  Max drawdown:  {top['max_drawdown_pct']:.1f}%")
    print(f"  │  Sortino:       {top['sortino']:.3f}")
    print(f"  │  Calmar:        {top['calmar']:.3f}")
    print(f"  │  Trades:        {int(top['total_trades'])}  {'[!low n]' if top['low_trades'] else ''}")
    print(f"  └───────────────────────────────────────────────────────────────────")
    # Compare to primary candidate
    pri_row = df_grid[(df_grid['sma_period'] == PRIMARY_SMA) &
                      (np.abs(df_grid['trail_pct'] - PRIMARY_TRAIL*100) < 0.1)]
    if len(pri_row) > 0:
        pri = pri_row.iloc[0]
        print(f"\n  Primary candidate (SMA {PRIMARY_SMA}/trail {PRIMARY_TRAIL*100:.0f}%):")
        print(f"    Annual return: {pri['annual_return_pct']:.1f}%  |  MaxDD: {pri['max_drawdown_pct']:.1f}%")
        print(f"    Sortino: {pri['sortino']:.3f}  |  Calmar: {pri['calmar']:.3f}")
        same = (int(top['sma_period']) == PRIMARY_SMA and
                abs(top['trail_pct'] - PRIMARY_TRAIL*100) < 0.1)
        if same:
            print(f"\n  → SMA {PRIMARY_SMA}/trail {PRIMARY_TRAIL*100:.0f}% IS the best under the return-first "
                  f"  (Sortino ≥ {SORTINO_MIN}, MaxDD > -25%) framework.")
        else:
            print(f"\n  → Different candidate emerges: SMA {int(top['sma_period'])}/{top['trail_pct']:.1f}% "
                  f"beats primary on annual return within these constraints.")
            print(f"  Tradeoff: Ann {top['annual_return_pct']:.1f}% vs {pri['annual_return_pct']:.1f}% — "
                  f"DD {top['max_drawdown_pct']:.1f}% vs {pri['max_drawdown_pct']:.1f}%")

print(f"\n  Drawdown recovery:")
print(f"    SMA {PRIMARY_SMA}/{PRIMARY_TRAIL*100:.0f}%: worst DD {trough_val_pri:.1f}% on {trough_date_pri.date()}  — "
      f"{recovery_label(trough_date_pri, rec_date_pri)}")
print(f"    SMA {SECONDARY_SMA}/{SECONDARY_TRAIL*100:.0f}%: worst DD {trough_val_sec:.1f}% on {trough_date_sec.date()} — "
      f"{recovery_label(trough_date_sec, rec_date_sec)}")
print(f"    BTC B&H:            worst DD {trough_val_bnh:.1f}% on {trough_date_bnh.date()}  — "
      f"{recovery_label(trough_date_bnh, rec_date_bnh)}")

print("\n  Top 10 by annual return (Sortino ≥ 0.8, MaxDD > -25%):")
print(f"  {'Rank':>4}  {'SMA':>4}  {'Trail':>6}  {'Ann%':>7}  {'MaxDD%':>7}  "
      f"{'Sortino':>8}  {'Calmar':>7}  {'n':>4}")
print("  " + "─" * 62)
for rank, (_, row) in enumerate(filtered.head(10).iterrows(), 1):
    flag = ' !' if row['low_trades'] else ''
    print(f"  {rank:>4}  {int(row['sma_period']):>4}  {row['trail_pct']:>5.1f}%  "
          f"{row['annual_return_pct']:>6.1f}%  {row['max_drawdown_pct']:>6.1f}%  "
          f"{row['sortino']:>8.3f}  {row['calmar']:>7.3f}  "
          f"{int(row['total_trades']):>3}{flag}")

print("\n" + "=" * 70)
print("Charts saved:")
print(f"  {out1}")
print(f"  {out2}")
print(f"  {out3}")
print("=" * 70)
