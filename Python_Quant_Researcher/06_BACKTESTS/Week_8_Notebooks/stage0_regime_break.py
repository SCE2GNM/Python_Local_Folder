#!/usr/bin/env python3
"""
Stage 0 — ETH ADX Regime Break Analysis (A022 pre-requisite)
Splits the full ETH ADX 19/9 (8% trail) backtest trade record at the
ETH spot ETF approval date (1 May 2024) and compares strategy character
across the two regimes.

Methodology: identical to stage5_final_comparison.py
  - Daily MtM equity curve (not per-trade compounding)
  - Stop checked against daily LOW before close/signal each bar
  - ADX peak updated on CLOSE
  - 0.15% round-trip costs per trade
  - Annual return, MaxDD, Calmar from daily equity curve
  - Annual return for sub-periods scaled by sub-period length in years

Outputs:
  06_BACKTESTS/Week_8_Notebooks/stage0_regime_break.html
"""

import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from ta.trend import ADXIndicator

warnings.filterwarnings('ignore')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_HTML   = os.path.join(SCRIPT_DIR, 'stage0_regime_break.html')

# ── Strategy constants — must match deployed bot exactly ─────────────────────
COSTS     = 0.0015   # 0.15% round-trip
ADX_WIN   = 9
ADX_THR   = 19
TRAIL_PCT = 0.08

# ── Regime split date ─────────────────────────────────────────────────────────
ETF_DATE = pd.Timestamp('2024-05-01')


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA
# ─────────────────────────────────────────────────────────────────────────────

print("Fetching ETH-USD daily data (2018-01-01 → today)...")
raw = yf.download('ETH-USD', start='2018-01-01', auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)

df     = raw[['High', 'Low', 'Close']].copy().dropna()
closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index
N      = len(df)
print(f"  {dates[0].date()} → {dates[-1].date()}  ({N} bars)")


# ─────────────────────────────────────────────────────────────────────────────
# 2. ADX SIGNALS
# ─────────────────────────────────────────────────────────────────────────────

print("Computing ADX 19/9 signals...")
_adx_ind = ADXIndicator(df['High'], df['Low'], df['Close'], window=ADX_WIN, fillna=False)
adx_vals = _adx_ind.adx().values
plus_di  = _adx_ind.adx_pos().values
minus_di = _adx_ind.adx_neg().values
adx_sig  = (adx_vals >= ADX_THR) & (plus_di > minus_di)


# ─────────────────────────────────────────────────────────────────────────────
# 3. BACKTEST  (bar-by-bar, stop against daily LOW)
# ─────────────────────────────────────────────────────────────────────────────

print("Running ADX backtest...")

pos = 0; ep = peak = stop = 0.0; entry_date = None
trades = []

for i in range(1, N):
    lo = lows[i]; cl = closes[i]

    if pos == 1:
        if lo <= stop:
            trades.append({
                'entry_date':  entry_date,
                'exit_date':   dates[i],
                'entry_price': ep,
                'exit_price':  stop,
                'return':      (stop - ep) / ep,
                'exit_reason': 'TRAIL_STOP',
            })
            pos = 0; entry_date = None

        elif not adx_sig[i]:
            trades.append({
                'entry_date':  entry_date,
                'exit_date':   dates[i],
                'entry_price': ep,
                'exit_price':  cl,
                'return':      (cl - ep) / ep,
                'exit_reason': 'ADX_EXIT',
            })
            pos = 0; entry_date = None

        else:
            if cl > peak:
                peak = cl
                stop = peak * (1 - TRAIL_PCT)

    elif adx_sig[i]:
        ep   = cl
        peak = cl
        stop = cl * (1 - TRAIL_PCT)
        entry_date = dates[i]
        pos  = 1

print(f"  → {len(trades)} trades total")
tdf = pd.DataFrame(trades)
tdf['entry_date'] = pd.to_datetime(tdf['entry_date'])
tdf['exit_date']  = pd.to_datetime(tdf['exit_date'])
tdf['hold_days']  = (tdf['exit_date'] - tdf['entry_date']).dt.days


# ─────────────────────────────────────────────────────────────────────────────
# 4. DAILY MtM EQUITY CURVE
# ─────────────────────────────────────────────────────────────────────────────

close_s = pd.Series(closes, index=dates)

equity = np.ones(N)
for t in trades:
    ei   = df.index.get_loc(t['entry_date'])
    xi   = df.index.get_loc(t['exit_date'])
    base = equity[ei]

    # Intermediate bars: MtM at daily close, no costs yet
    for j in range(ei + 1, xi):
        equity[j] = base * (closes[j] / closes[ei])

    # Exit bar: use trade return (correct exit price: close or stop) + costs once
    equity[xi] = base * (1 + t['return']) * (1 - COSTS)

    # Carry flat after exit until next trade overwrites
    for j in range(xi + 1, N):
        equity[j] = equity[xi]

equity_s = pd.Series(equity, index=dates)


# ─────────────────────────────────────────────────────────────────────────────
# 5. SPLIT AT ETF DATE
# ─────────────────────────────────────────────────────────────────────────────

pre_trades  = tdf[tdf['entry_date'] < ETF_DATE].copy()
post_trades = tdf[tdf['entry_date'] >= ETF_DATE].copy()

pre_equity  = equity_s[equity_s.index < ETF_DATE]
post_equity = equity_s[equity_s.index >= ETF_DATE]

print(f"  Pre-ETF  trades (before 2024-05-01): {len(pre_trades)}")
print(f"  Post-ETF trades (from  2024-05-01):  {len(post_trades)}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. METRICS HELPER
# ─────────────────────────────────────────────────────────────────────────────

def period_metrics(period_trades: pd.DataFrame, period_equity: pd.Series, label: str) -> dict:
    if len(period_trades) == 0:
        return {'period': label, 'n_trades': 0}

    rets    = period_trades['return'].values
    wins    = rets[rets > 0]
    losses  = rets[rets <= 0]

    win_rate    = len(wins) / len(rets) * 100
    avg_win     = wins.mean()   * 100 if len(wins) > 0 else 0.0
    avg_loss    = losses.mean() * 100 if len(losses) > 0 else 0.0
    worst_loss  = losses.min()  * 100 if len(losses) > 0 else 0.0
    pf_denom    = abs(losses.sum()) if len(losses) > 0 else 1e-9
    profit_factor = wins.sum() / pf_denom if len(wins) > 0 else 0.0
    avg_hold    = period_trades['hold_days'].mean()

    # Annual return from daily equity curve for this sub-period
    eq_vals  = period_equity.values
    years    = (period_equity.index[-1] - period_equity.index[0]).days / 365.25
    ann_ret  = (eq_vals[-1] / eq_vals[0]) ** (1 / years) - 1 if years > 0 else 0.0

    # MtM max drawdown from sub-period equity curve
    rolling_max = np.maximum.accumulate(eq_vals)
    drawdowns   = (eq_vals - rolling_max) / rolling_max
    max_dd      = drawdowns.min() * 100

    return {
        'period':         label,
        'n_trades':       len(period_trades),
        'win_rate_pct':   round(win_rate, 1),
        'avg_win_pct':    round(avg_win, 2),
        'avg_loss_pct':   round(avg_loss, 2),
        'worst_loss_pct': round(worst_loss, 2),
        'annual_ret_pct': round(ann_ret * 100, 2),
        'max_dd_pct':     round(max_dd, 2),
        'profit_factor':  round(profit_factor, 3),
        'avg_hold_days':  round(avg_hold, 1),
    }


pre_m  = period_metrics(pre_trades,  pre_equity,  'Pre-ETF  (Jan 2018 – Apr 2024)')
post_m = period_metrics(post_trades, post_equity, 'Post-ETF (May 2024 – present)')
full_years = (dates[-1] - dates[0]).days / 365.25
full_ann   = (equity[-1] / equity[0]) ** (1 / full_years) - 1


# ─────────────────────────────────────────────────────────────────────────────
# 7. PRINT COMPARISON TABLE
# ─────────────────────────────────────────────────────────────────────────────

COL_W = 32
SEP   = '=' * 72

print(f"\n{SEP}")
print("ETH ADX 19/9 (8% trail) — Regime Break Analysis at May 2024")
print(SEP)
print(f"{'Metric':<28}  {'Pre-ETF':>18}  {'Post-ETF':>18}")
print('-' * 72)

rows = [
    ('Trades',             'n_trades',       '{}',     '{}'),
    ('Win rate',           'win_rate_pct',   '{:.1f}%', '{:.1f}%'),
    ('Avg win',            'avg_win_pct',    '{:+.2f}%', '{:+.2f}%'),
    ('Avg loss',           'avg_loss_pct',   '{:+.2f}%', '{:+.2f}%'),
    ('Worst single loss',  'worst_loss_pct', '{:+.2f}%', '{:+.2f}%'),
    ('Annual return',      'annual_ret_pct', '{:+.2f}%', '{:+.2f}%'),
    ('Max drawdown (MtM)', 'max_dd_pct',     '{:.2f}%', '{:.2f}%'),
    ('Profit factor',      'profit_factor',  '{:.3f}',  '{:.3f}'),
    ('Avg hold (days)',    'avg_hold_days',  '{:.1f}',  '{:.1f}'),
]

for label, key, fmt_pre, fmt_post in rows:
    v_pre  = pre_m.get(key, 'n/a')
    v_post = post_m.get(key, 'n/a')
    p_str  = fmt_pre.format(v_pre)   if isinstance(v_pre,  (int, float)) else str(v_pre)
    q_str  = fmt_post.format(v_post) if isinstance(v_post, (int, float)) else str(v_post)
    print(f"  {label:<26}  {p_str:>18}  {q_str:>18}")

print(SEP)
print(f"  Full-period annual return: {full_ann*100:+.2f}%")
print(SEP)


# ─────────────────────────────────────────────────────────────────────────────
# 8. PLOTLY EQUITY CURVE — split coloured segments
# ─────────────────────────────────────────────────────────────────────────────

print("\nBuilding equity curve chart...")

C_PRE  = '#2196F3'   # blue — pre-ETF
C_POST = '#FF9800'   # orange — post-ETF
C_LINE = '#E53935'   # red dashed — ETF date marker

fig = go.Figure()

# Pre-ETF segment
fig.add_trace(go.Scatter(
    x=pre_equity.index,
    y=pre_equity.values,
    mode='lines',
    name='Pre-ETF (Jan 2018 – Apr 2024)',
    line=dict(color=C_PRE, width=2),
    hovertemplate='%{x|%Y-%m-%d}<br>Portfolio: %{y:.3f}x<extra>Pre-ETF</extra>',
))

# Post-ETF segment — start from last pre-ETF value to keep curve continuous
post_x = post_equity.index
post_y = post_equity.values

# Bridge: last point of pre-ETF connects to first post-ETF
bridge_x = [pre_equity.index[-1], post_equity.index[0]]
bridge_y = [pre_equity.values[-1], post_equity.values[0]]
fig.add_trace(go.Scatter(
    x=bridge_x, y=bridge_y,
    mode='lines',
    line=dict(color=C_POST, width=2),
    showlegend=False,
    hoverinfo='skip',
))

fig.add_trace(go.Scatter(
    x=post_x,
    y=post_y,
    mode='lines',
    name='Post-ETF (May 2024 – present)',
    line=dict(color=C_POST, width=2),
    hovertemplate='%{x|%Y-%m-%d}<br>Portfolio: %{y:.3f}x<extra>Post-ETF</extra>',
))

# Vertical dashed line at ETF date
fig.add_vline(
    x=ETF_DATE.timestamp() * 1000,
    line_dash='dash',
    line_color=C_LINE,
    line_width=1.5,
    annotation_text='ETH Spot ETF<br>May 2024',
    annotation_position='top right',
    annotation_font_size=11,
    annotation_font_color=C_LINE,
)

# Trade entry/exit markers
if len(pre_trades) > 0:
    entry_idx = [df.index.get_loc(d) for d in pre_trades['entry_date']]
    entry_eq  = [equity[i] for i in entry_idx]
    fig.add_trace(go.Scatter(
        x=pre_trades['entry_date'], y=entry_eq,
        mode='markers', name='Pre-ETF entries',
        marker=dict(color=C_PRE, symbol='triangle-up', size=7, opacity=0.7),
        hovertemplate='Entry %{x|%Y-%m-%d}<extra>Pre-ETF</extra>',
    ))

if len(post_trades) > 0:
    entry_idx = [df.index.get_loc(d) for d in post_trades['entry_date']]
    entry_eq  = [equity[i] for i in entry_idx]
    fig.add_trace(go.Scatter(
        x=post_trades['entry_date'], y=entry_eq,
        mode='markers', name='Post-ETF entries',
        marker=dict(color=C_POST, symbol='triangle-up', size=7, opacity=0.7),
        hovertemplate='Entry %{x|%Y-%m-%d}<extra>Post-ETF</extra>',
    ))

# Annotation boxes: regime summary stats
pre_ann = (
    f"<b>Pre-ETF</b><br>"
    f"Trades: {pre_m['n_trades']}<br>"
    f"Win rate: {pre_m['win_rate_pct']:.1f}%<br>"
    f"Annual ret: {pre_m['annual_ret_pct']:+.1f}%<br>"
    f"Max DD: {pre_m['max_dd_pct']:.1f}%<br>"
    f"PF: {pre_m['profit_factor']:.2f}"
)
post_ann = (
    f"<b>Post-ETF</b><br>"
    f"Trades: {post_m['n_trades']}<br>"
    f"Win rate: {post_m['win_rate_pct']:.1f}%<br>"
    f"Annual ret: {post_m['annual_ret_pct']:+.1f}%<br>"
    f"Max DD: {post_m['max_dd_pct']:.1f}%<br>"
    f"PF: {post_m['profit_factor']:.2f}"
)

fig.add_annotation(
    x=pd.Timestamp('2021-06-01'), y=equity_s.max() * 0.95,
    text=pre_ann, showarrow=False, align='left',
    bgcolor='rgba(33,150,243,0.10)', bordercolor=C_PRE, borderwidth=1,
    font=dict(size=11),
)
fig.add_annotation(
    x=pd.Timestamp('2024-10-01'), y=equity_s.max() * 0.60,
    text=post_ann, showarrow=False, align='left',
    bgcolor='rgba(255,152,0,0.10)', bordercolor=C_POST, borderwidth=1,
    font=dict(size=11),
)

fig.update_layout(
    title=dict(
        text=(
            'ETH ADX 19/9 (8% trail) — Regime Break Analysis<br>'
            '<sup>Pre-ETF (blue) vs Post-ETF (orange) · '
            'Dashed line = ETH Spot ETF approval May 2024 · '
            'Portfolio normalised to 1.0 at 2018-01-01</sup>'
        ),
        font=dict(size=15),
    ),
    xaxis=dict(title='Date', showgrid=True, gridcolor='rgba(0,0,0,0.06)'),
    yaxis=dict(title='Portfolio value (normalised to 1.0)', showgrid=True, gridcolor='rgba(0,0,0,0.06)'),
    legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='left', x=0),
    hovermode='x unified',
    plot_bgcolor='white',
    paper_bgcolor='white',
    height=550,
    margin=dict(t=100, b=60, l=70, r=40),
)

fig.write_html(OUT_HTML, include_plotlyjs='cdn')
print(f"Chart saved → {OUT_HTML}")
print("\nStage 0 complete.")
