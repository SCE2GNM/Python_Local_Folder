#!/usr/bin/env python3
"""
Stage 3 — Equity Curve Chart
Set 2 (ADX 19/9, pct 8%) at 1.9x and 1.0x vs ETH Buy-and-Hold.
Interactive Plotly HTML, dual-panel (equity log scale + drawdown lines),
entry/exit markers on 1.9x curve. Daily mark-to-market construction.
"""

import os, warnings
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import ADXIndicator

warnings.filterwarnings('ignore')

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Constants (match stage3_eth_leverage.py exactly) ─────────────────────────
COSTS        = 0.0015    # 0.15% round-trip on notional
INT_RATE     = 0.00015   # 0.015%/day on borrowed
MAINT_MARGIN = 0.05
STOP_SLIP    = 0.0025    # 0.25% below stop price
LIQ_SLIP     = 0.005     # 0.5% below liquidation price

# ── Fetch data ────────────────────────────────────────────────────────────────
print("Fetching ETH-USD daily data...")
raw = yf.download('ETH-USD', start='2018-01-01', auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
eth = raw[['High', 'Low', 'Close']].dropna()
closes = eth['Close'].values.astype(float)
lows   = eth['Low'].values.astype(float)
dates  = eth.index
N      = len(closes)
YEARS  = (dates[-1] - dates[0]).days / 365.25
print(f"Data: {dates[0].date()} → {dates[-1].date()}  ({YEARS:.2f} yrs, {N} bars)")

# ── Signal: ADX 19/9, adx >= 19, +DI > -DI (matches Stage 1d exactly) ────────
print("Computing ADX 19/9 signals...")
ind      = ADXIndicator(eth['High'], eth['Low'], eth['Close'], window=9, fillna=False)
adx      = ind.adx().values
plus_di  = ind.adx_pos().values
minus_di = ind.adx_neg().values
signal   = (adx >= 19) & (plus_di > minus_di)

# ── Helpers ───────────────────────────────────────────────────────────────────
def liq_price(ep, lev):
    if lev <= 1.0:
        return 0.0
    return ep * (lev - 1.0) / (lev * (1.0 - MAINT_MARGIN))


def run_pct_trail(lev, trail_pct=0.08):
    """Bar-by-bar pct trailing stop. Correct order: stop check → signal → peak update."""
    portfolio = 1.0; pos = 0
    ep = peak = stop = lp = 0.0
    entry_date = None; entry_bar = 0; entry_port = 0.0
    trades = []

    for i in range(1, N):
        cl = closes[i]; lo = lows[i]; dt = dates[i]
        if pos == 1:
            days_held = i - entry_bar
            exit_px = None; ex_rsn = None
            if lev > 1.0 and lp > stop and lo <= lp:
                exit_px = lp * (1.0 - LIQ_SLIP); ex_rsn = 'LIQUIDATION'
            elif lo <= stop:
                exit_px = stop * (1.0 - STOP_SLIP); ex_rsn = 'TRAIL_STOP'
            elif not signal[i]:
                exit_px = cl; ex_rsn = 'ADX_EXIT'
            if exit_px is not None:
                r = lev * (exit_px / ep - 1.0 - COSTS) - days_held * INT_RATE * (lev - 1.0)
                trades.append({
                    'entry_date':  entry_date, 'exit_date':  dt,
                    'entry_price': ep,         'exit_price': exit_px,
                    'return':      r,           'exit_reason': ex_rsn,
                    'hold_days':   days_held,   'entry_bar': entry_bar,
                    'exit_bar':    i,           'entry_port': entry_port,
                })
                portfolio = entry_port * (1.0 + r); pos = 0; entry_date = None
            else:
                if cl > peak:
                    peak = cl; stop = peak * (1.0 - trail_pct)
        else:
            if signal[i]:
                ep = cl; peak = cl; stop = cl * (1.0 - trail_pct)
                lp = liq_price(ep, lev)
                entry_date = dt; entry_bar = i; entry_port = portfolio; pos = 1

    return trades


def build_equity(trades, lev):
    """Vectorised daily MtM equity. Matches build_lev_equity in stage3_eth_leverage.py."""
    date_to_i = {dt: i for i, dt in enumerate(dates)}
    equity = np.ones(N); portfolio = 1.0; prev_i = 0
    for t in trades:
        ei = date_to_i.get(pd.Timestamp(t['entry_date']))
        xi = date_to_i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None:
            continue
        equity[prev_i:ei] = portfolio
        ep = t['entry_price']; p0 = portfolio
        days_arr = np.arange(xi - ei + 1, dtype=float)
        accrued  = days_arr * INT_RATE * (lev - 1.0) * p0
        equity[ei:xi+1] = p0 * (1.0 + lev * (closes[ei:xi+1] / ep - 1.0)) - accrued
        portfolio  = p0 * (1.0 + t['return'])
        equity[xi] = portfolio; prev_i = xi + 1
    equity[prev_i:] = portfolio
    return equity


def build_status(trades):
    """Per-bar position label: 'OPEN (Xd)' or 'FLAT'."""
    date_to_i = {dt: i for i, dt in enumerate(dates)}
    pos  = np.zeros(N, dtype=int)
    held = np.zeros(N, dtype=int)
    for t in trades:
        ei = date_to_i.get(pd.Timestamp(t['entry_date']))
        xi = date_to_i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None:
            continue
        pos[ei:xi+1]  = 1
        held[ei:xi+1] = np.arange(xi - ei + 1)
    return ['OPEN (' + str(d) + 'd)' if p else 'FLAT' for p, d in zip(pos, held)]


def drawdown_pct(eq):
    pk = np.maximum.accumulate(eq)
    return (eq - pk) / pk * 100.0


# ── Run backtests ─────────────────────────────────────────────────────────────
print("Running Set 2 at 1.9×...")
t19 = run_pct_trail(1.9)
print("Running Set 2 at 1.0×...")
t10 = run_pct_trail(1.0)

eq19   = build_equity(t19, 1.9)
eq10   = build_equity(t10, 1.0)
eth_bh = closes / closes[0]

dd19  = drawdown_pct(eq19)
dd10  = drawdown_pct(eq10)
dd_bh = drawdown_pct(eth_bh)

s19 = build_status(t19)
s10 = build_status(t10)

ann19  = eq19[-1]  ** (1.0 / YEARS) - 1.0
ann10  = eq10[-1]  ** (1.0 / YEARS) - 1.0
ann_bh = eth_bh[-1] ** (1.0 / YEARS) - 1.0
maxdd19  = dd19.min();  maxdd10  = dd10.min();  maxdd_bh = dd_bh.min()

print(f"1.9×: {ann19*100:.1f}%/yr  MaxDD {maxdd19:.1f}%  ({len(t19)} trades)")
print(f"1.0×: {ann10*100:.1f}%/yr  MaxDD {maxdd10:.1f}%  ({len(t10)} trades)")
print(f"ETH:  {ann_bh*100:.1f}%/yr  MaxDD {maxdd_bh:.1f}%")

# ── Entry / exit marker coordinates on 1.9x curve ────────────────────────────
date_to_i = {dt: i for i, dt in enumerate(dates)}
entry_x, entry_y = [], []
adx_x,   adx_y   = [], []
stop_x,  stop_y  = [], []

for t in t19:
    ei = date_to_i.get(pd.Timestamp(t['entry_date']))
    xi = date_to_i.get(pd.Timestamp(t['exit_date']))
    if ei is not None:
        entry_x.append(dates[ei]); entry_y.append(float(eq19[ei]))
    if xi is not None:
        if t['exit_reason'] == 'ADX_EXIT':
            adx_x.append(dates[xi]); adx_y.append(float(eq19[xi]))
        else:  # TRAIL_STOP or LIQUIDATION
            stop_x.append(dates[xi]); stop_y.append(float(eq19[xi]))

n_entries = len(entry_x); n_adx = len(adx_x); n_stop = len(stop_x)

# ── Custom hover data (list-of-lists supports mixed types in Plotly) ──────────
dates_list = list(dates)
cd19  = [[float(dd19[i]),  s19[i]] for i in range(N)]
cd10  = [[float(dd10[i]),  s10[i]] for i in range(N)]
cd_bh = [[float(dd_bh[i])]         for i in range(N)]

# ── Build figure ──────────────────────────────────────────────────────────────
fig = make_subplots(
    rows=2, cols=1,
    row_heights=[0.67, 0.33],
    shared_xaxes=True,
    vertical_spacing=0.035,
)

# — Equity: 1.9× —
fig.add_trace(go.Scatter(
    x=dates_list, y=eq19.tolist(),
    name=f'1.9× leveraged ({ann19*100:.1f}%/yr  MaxDD {maxdd19:.0f}%)',
    line=dict(color='#2980b9', width=2.0),
    customdata=cd19,
    hovertemplate=(
        '<b>%{x|%Y-%m-%d}</b><br>'
        'Portfolio: <b>%{y:.3f}×</b><br>'
        'Drawdown: %{customdata[0]:.1f}%<br>'
        'Leverage: 1.9×<br>'
        'Position: %{customdata[1]}'
        '<extra>1.9× Leveraged</extra>'
    ),
), row=1, col=1)

# — Equity: 1.0× —
fig.add_trace(go.Scatter(
    x=dates_list, y=eq10.tolist(),
    name=f'1.0× unleveraged ({ann10*100:.1f}%/yr  MaxDD {maxdd10:.0f}%)',
    line=dict(color='#27ae60', width=2.0),
    customdata=cd10,
    hovertemplate=(
        '<b>%{x|%Y-%m-%d}</b><br>'
        'Portfolio: <b>%{y:.3f}×</b><br>'
        'Drawdown: %{customdata[0]:.1f}%<br>'
        'Leverage: 1.0×<br>'
        'Position: %{customdata[1]}'
        '<extra>1.0× Unleveraged</extra>'
    ),
), row=1, col=1)

# — Equity: ETH B&H —
fig.add_trace(go.Scatter(
    x=dates_list, y=eth_bh.tolist(),
    name=f'ETH Buy-and-Hold ({ann_bh*100:.1f}%/yr  MaxDD {maxdd_bh:.0f}%)',
    line=dict(color='#e74c3c', width=1.5, dash='dot'),
    customdata=cd_bh,
    hovertemplate=(
        '<b>%{x|%Y-%m-%d}</b><br>'
        'ETH B&H: <b>%{y:.3f}×</b><br>'
        'Drawdown: %{customdata[0]:.1f}%'
        '<extra>ETH B&H</extra>'
    ),
), row=1, col=1)

# — Entry markers —
fig.add_trace(go.Scatter(
    x=entry_x, y=entry_y,
    mode='markers',
    name=f'Entry ×{n_entries}',
    marker=dict(symbol='triangle-up', size=9, color='#2ecc71',
                line=dict(color='#1a7a36', width=1)),
    hovertemplate=(
        '<b>▲ ENTRY</b><br>%{x|%Y-%m-%d}<br>Portfolio: %{y:.3f}×'
        '<extra></extra>'
    ),
), row=1, col=1)

# — ADX exit markers (red) —
fig.add_trace(go.Scatter(
    x=adx_x, y=adx_y,
    mode='markers',
    name=f'ADX Exit ×{n_adx}',
    marker=dict(symbol='triangle-down', size=9, color='#e74c3c',
                line=dict(color='#8b0000', width=1)),
    hovertemplate=(
        '<b>▼ EXIT (signal)</b><br>%{x|%Y-%m-%d}<br>Portfolio: %{y:.3f}×'
        '<extra></extra>'
    ),
), row=1, col=1)

# — Stop exit markers (orange) —
fig.add_trace(go.Scatter(
    x=stop_x, y=stop_y,
    mode='markers',
    name=f'Stop Exit ×{n_stop}',
    marker=dict(symbol='triangle-down', size=9, color='#e67e22',
                line=dict(color='#7d3c00', width=1)),
    hovertemplate=(
        '<b>▼ EXIT (stop)</b><br>%{x|%Y-%m-%d}<br>Portfolio: %{y:.3f}×'
        '<extra></extra>'
    ),
), row=1, col=1)

# — Drawdown panel —
for y, color, dash, lbl in [
    (dd19,  '#2980b9', 'solid', '1.9×'),
    (dd10,  '#27ae60', 'solid', '1.0×'),
    (dd_bh, '#e74c3c', 'dot',   'ETH B&H'),
]:
    fig.add_trace(go.Scatter(
        x=dates_list, y=y.tolist(),
        name=lbl, showlegend=False,
        line=dict(color=color, width=1.5, dash=dash),
        hovertemplate=f'<b>%{{x|%Y-%m-%d}}</b><br>DD: %{{y:.1f}}%<extra>{lbl}</extra>',
    ), row=2, col=1)

# ── Layout ────────────────────────────────────────────────────────────────────
fig.update_layout(
    title=dict(
        text=(
            'Stage 3 — ADX 19/9 pct 8% Trailing Stop:  1.9× Leveraged  vs  1.0× Unleveraged  vs  ETH B&H<br>'
            f'<sup>'
            f'1.9×: {ann19*100:.1f}%/yr  ·  '
            f'1.0×: {ann10*100:.1f}%/yr  ·  '
            f'ETH B&H: {ann_bh*100:.1f}%/yr  |  '
            f'Slippage: 0.25% stop / 0.5% liq  ·  Interest: 0.015%/day on borrowed  |  '
            f'{len(t19)} trades: {n_stop} stop ▼  {n_adx} signal ▼  {n_entries} entries ▲'
            f'</sup>'
        ),
        font=dict(size=12, color='#1a1a1a'),
        x=0.5, xanchor='center', y=0.98,
    ),
    height=820,
    hovermode='x unified',
    paper_bgcolor='white',
    plot_bgcolor='#fafafa',
    margin=dict(l=85, r=50, t=105, b=60),
    legend=dict(
        x=0.01, y=0.985,
        bgcolor='rgba(255,255,255,0.88)',
        bordercolor='#ccc', borderwidth=1,
        font=dict(size=10.5),
        tracegroupgap=3,
    ),
)

fig.update_yaxes(
    row=1, col=1,
    type='log',
    title_text='Portfolio Value (log scale, start = 1.0)',
    tickvals=[1, 2, 5, 10, 20, 50, 100, 200, 500, 1000],
    ticktext=['1×', '2×', '5×', '10×', '20×', '50×', '100×', '200×', '500×', '1000×'],
    gridcolor='#e8e8e8',
)
fig.update_xaxes(row=1, col=1, gridcolor='#e8e8e8', showticklabels=False)

fig.update_yaxes(
    row=2, col=1,
    title_text='Drawdown %',
    tickformat='.0f', ticksuffix='%',
    gridcolor='#e8e8e8',
)
fig.update_xaxes(row=2, col=1, gridcolor='#e8e8e8', title_text='Date')

# ── Save ──────────────────────────────────────────────────────────────────────
out_path = os.path.join(RESULTS_DIR, 'stage3_equity_curve.html')
fig.write_html(
    out_path, include_plotlyjs='cdn',
    config={'displayModeBar': True, 'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']},
)
sz = os.path.getsize(out_path) / 1024
print(f'\nSaved → results/stage3_equity_curve.html  ({sz:.0f} KB)')
print(f'Entries: {n_entries}  |  ADX exits: {n_adx}  |  Stop exits: {n_stop}')
print(f'Final values:  1.9×={eq19[-1]:.1f}×  |  1.0×={eq10[-1]:.1f}×  |  ETH={eth_bh[-1]:.2f}×')
