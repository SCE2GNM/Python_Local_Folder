#!/usr/bin/env python3
"""
Stage 3 — Full Equity Curve Chart with Year-by-Year Panels
Main chart: full period 2018-2026, log scale, dual-panel (equity + drawdown).
Below: 8 annual panels (2018-2025), linear scale normalised to 1.0 at year start,
each with drawdown sub-panel and year return% annotations.
Self-contained HTML — opens directly in browser.
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
COSTS        = 0.0015
INT_RATE     = 0.00015
MAINT_MARGIN = 0.05
STOP_SLIP    = 0.0025
LIQ_SLIP     = 0.005

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

# ── Signals ───────────────────────────────────────────────────────────────────
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
                    'entry_date': entry_date, 'exit_date': dt,
                    'entry_price': ep, 'exit_price': exit_px,
                    'return': r, 'exit_reason': ex_rsn,
                    'hold_days': days_held, 'entry_bar': entry_bar,
                    'exit_bar': i, 'entry_port': entry_port,
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
        portfolio = p0 * (1.0 + t['return'])
        equity[xi] = portfolio; prev_i = xi + 1
    equity[prev_i:] = portfolio
    return equity


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

ann19  = eq19[-1]  ** (1.0 / YEARS) - 1.0
ann10  = eq10[-1]  ** (1.0 / YEARS) - 1.0
ann_bh = eth_bh[-1] ** (1.0 / YEARS) - 1.0
maxdd19  = dd19.min(); maxdd10 = dd10.min(); maxdd_bh = dd_bh.min()

n_stop = sum(1 for t in t19 if t['exit_reason'] != 'ADX_EXIT')
n_adx  = sum(1 for t in t19 if t['exit_reason'] == 'ADX_EXIT')

print(f"1.9×: {ann19*100:.1f}%/yr  MaxDD {maxdd19:.1f}%  ({len(t19)} trades)")
print(f"1.0×: {ann10*100:.1f}%/yr  MaxDD {maxdd10:.1f}%  ({len(t10)} trades)")
print(f"ETH:  {ann_bh*100:.1f}%/yr  MaxDD {maxdd_bh:.1f}%")

dates_list = list(dates)
date_to_i  = {dt: i for i, dt in enumerate(dates)}

# ── Marker helper ─────────────────────────────────────────────────────────────
def get_markers(trades, eq):
    entry_x, entry_y = [], []
    adx_x,   adx_y   = [], []
    stop_x,  stop_y  = [], []
    for t in trades:
        ei = date_to_i.get(pd.Timestamp(t['entry_date']))
        xi = date_to_i.get(pd.Timestamp(t['exit_date']))
        if ei is not None:
            entry_x.append(dates[ei]); entry_y.append(float(eq[ei]))
        if xi is not None:
            if t['exit_reason'] == 'ADX_EXIT':
                adx_x.append(dates[xi]); adx_y.append(float(eq[xi]))
            else:
                stop_x.append(dates[xi]); stop_y.append(float(eq[xi]))
    return (entry_x, entry_y), (adx_x, adx_y), (stop_x, stop_y)


(ex19, ey19), (ax19, ay19), (sx19, sy19) = get_markers(t19, eq19)
(ex10, ey10), (ax10, ay10), (sx10, sy10) = get_markers(t10, eq10)

# ── Build main figure ─────────────────────────────────────────────────────────
fig_main = make_subplots(
    rows=2, cols=1, row_heights=[0.67, 0.33],
    shared_xaxes=True, vertical_spacing=0.035,
)

def add_equity_traces(fig, eq_19, eq_10, bh, markers_19, markers_10,
                      dd_19, dd_10, dd_bh_, dates_x,
                      ann_19, ann_10, ann_bh_, mdd_19, mdd_10, mdd_bh_,
                      n_trades, n_stop_, n_adx_,
                      show_legend=True, log_y=True):
    (ex_19, ey_19), (ax_19, ay_19), (sx_19, sy_19) = markers_19
    (ex_10, ey_10), (ax_10, ay_10), (sx_10, sy_10) = markers_10

    fig.add_trace(go.Scatter(
        x=dates_x, y=eq_19,
        name=f'1.9× ({ann_19*100:.1f}%/yr  MaxDD {mdd_19:.0f}%)',
        line=dict(color='#2980b9', width=2.0), showlegend=show_legend,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates_x, y=eq_10,
        name=f'1.0× ({ann_10*100:.1f}%/yr  MaxDD {mdd_10:.0f}%)',
        line=dict(color='#27ae60', width=2.0), showlegend=show_legend,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates_x, y=bh,
        name=f'ETH B&H ({ann_bh_*100:.1f}%/yr  MaxDD {mdd_bh_:.0f}%)',
        line=dict(color='#e74c3c', width=1.5, dash='dot'), showlegend=show_legend,
    ), row=1, col=1)

    # Markers 1.9×
    fig.add_trace(go.Scatter(
        x=ex_19, y=ey_19, mode='markers',
        name=f'▲ Entry ×{len(ex_19)}',
        marker=dict(symbol='triangle-up', size=5, opacity=0.55, color='#2ecc71',
                    line=dict(color='#1a7a36', width=0.5)),
        showlegend=show_legend,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=ax_19, y=ay_19, mode='markers',
        name=f'▼ ADX Exit ×{len(ax_19)}',
        marker=dict(symbol='triangle-down', size=5, opacity=0.55, color='#e74c3c',
                    line=dict(color='#8b0000', width=0.5)),
        showlegend=show_legend,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=sx_19, y=sy_19, mode='markers',
        name=f'▼ Stop Exit ×{len(sx_19)}',
        marker=dict(symbol='triangle-down', size=5, opacity=0.55, color='#e67e22',
                    line=dict(color='#7d3c00', width=0.5)),
        showlegend=show_legend,
    ), row=1, col=1)

    # Markers 1.0× (no legend duplication)
    fig.add_trace(go.Scatter(
        x=ex_10, y=ey_10, mode='markers',
        name='Entry (1.0×)', showlegend=False,
        marker=dict(symbol='triangle-up', size=5, opacity=0.55, color='#2ecc71',
                    line=dict(color='#1a7a36', width=0.5)),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=ax_10, y=ay_10, mode='markers',
        name='ADX Exit (1.0×)', showlegend=False,
        marker=dict(symbol='triangle-down', size=5, opacity=0.55, color='#e74c3c',
                    line=dict(color='#8b0000', width=0.5)),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=sx_10, y=sy_10, mode='markers',
        name='Stop Exit (1.0×)', showlegend=False,
        marker=dict(symbol='triangle-down', size=5, opacity=0.55, color='#e67e22',
                    line=dict(color='#7d3c00', width=0.5)),
    ), row=1, col=1)

    # Drawdown panel
    for dd_, color, dash, lbl in [
        (dd_19,  '#2980b9', 'solid', '1.9×'),
        (dd_10,  '#27ae60', 'solid', '1.0×'),
        (dd_bh_, '#e74c3c', 'dot',   'ETH B&H'),
    ]:
        fig.add_trace(go.Scatter(
            x=dates_x, y=dd_,
            name=lbl, showlegend=False,
            line=dict(color=color, width=1.5, dash=dash),
        ), row=2, col=1)


add_equity_traces(
    fig_main,
    eq19.tolist(), eq10.tolist(), eth_bh.tolist(),
    ((ex19, ey19), (ax19, ay19), (sx19, sy19)),
    ((ex10, ey10), (ax10, ay10), (sx10, sy10)),
    dd19.tolist(), dd10.tolist(), dd_bh.tolist(),
    dates_list,
    ann19, ann10, ann_bh, maxdd19, maxdd10, maxdd_bh,
    len(t19), n_stop, n_adx,
)

fig_main.update_layout(
    title=dict(
        text=(
            'ADX 19/9 pct 8% Trailing Stop — Full Period 2018–2026: '
            '1.9× Leveraged  vs  1.0× Unleveraged  vs  ETH B&H<br>'
            f'<sup>1.9×: {ann19*100:.1f}%/yr  ·  '
            f'1.0×: {ann10*100:.1f}%/yr  ·  '
            f'ETH B&H: {ann_bh*100:.1f}%/yr  |  '
            f'{len(t19)} trades: {n_stop} stop ▼  {n_adx} signal ▼</sup>'
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
    ),
)
fig_main.update_yaxes(
    row=1, col=1, type='log',
    title_text='Portfolio (log, start=1.0)',
    tickvals=[1, 2, 5, 10, 20, 50, 100, 200, 500, 1000],
    ticktext=['1×', '2×', '5×', '10×', '20×', '50×', '100×', '200×', '500×', '1000×'],
    gridcolor='#e8e8e8',
)
fig_main.update_xaxes(row=1, col=1, gridcolor='#e8e8e8', showticklabels=False)
fig_main.update_yaxes(
    row=2, col=1,
    title_text='Drawdown %',
    tickformat='.0f', ticksuffix='%', gridcolor='#e8e8e8',
)
fig_main.update_xaxes(row=2, col=1, gridcolor='#e8e8e8', title_text='Date')

# ── Year-by-year panels ───────────────────────────────────────────────────────
YEARS_LIST = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

year_figs = []

for yr in YEARS_LIST:
    yr_start = pd.Timestamp(f'{yr}-01-01')
    yr_end   = pd.Timestamp(f'{yr}-12-31')

    mask = (dates >= yr_start) & (dates <= yr_end)
    if mask.sum() == 0:
        print(f"  {yr}: no data")
        year_figs.append(None)
        continue

    yr_dates  = dates[mask]
    yr_eq19   = eq19[mask]
    yr_eq10   = eq10[mask]
    yr_eth_bh = eth_bh[mask]

    # Normalise all three to 1.0 at first bar of year
    base19 = yr_eq19[0];   base10 = yr_eq10[0];   base_bh = yr_eth_bh[0]
    yr_eq19n  = yr_eq19   / base19
    yr_eq10n  = yr_eq10   / base10
    yr_eth_n  = yr_eth_bh / base_bh

    yr_dd19 = drawdown_pct(yr_eq19n)
    yr_dd10 = drawdown_pct(yr_eq10n)
    yr_ddbh = drawdown_pct(yr_eth_n)

    # Year returns for each series
    ret19 = yr_eq19n[-1] - 1.0
    ret10 = yr_eq10n[-1] - 1.0
    ret_bh = yr_eth_n[-1] - 1.0

    # Markers for this year's trades (normalised y)
    yr_date_set = set(yr_dates)

    def yr_markers(trades, eq_full, base):
        ex, ey = [], []
        ax, ay = [], []
        sx, sy = [], []
        for t in trades:
            ed = pd.Timestamp(t['entry_date'])
            xd = pd.Timestamp(t['exit_date'])
            ei = date_to_i.get(ed)
            xi = date_to_i.get(xd)
            # Include marker if entry OR exit falls in this year,
            # or if trade spans the whole year (open at start, exit later)
            if ei is not None and dates[ei] in yr_date_set:
                ex.append(dates[ei]); ey.append(float(eq_full[ei]) / base)
            if xi is not None and dates[xi] in yr_date_set:
                y_val = float(eq_full[xi]) / base
                if t['exit_reason'] == 'ADX_EXIT':
                    ax.append(dates[xi]); ay.append(y_val)
                else:
                    sx.append(dates[xi]); sy.append(y_val)
        return (ex, ey), (ax, ay), (sx, sy)

    m19 = yr_markers(t19, eq19, base19)
    m10 = yr_markers(t10, eq10, base10)

    fig_yr = make_subplots(
        rows=2, cols=1, row_heights=[0.65, 0.35],
        shared_xaxes=True, vertical_spacing=0.04,
    )

    yr_dates_list = list(yr_dates)

    # Equity lines
    for eq_n, color, dash, lbl in [
        (yr_eq19n, '#2980b9', 'solid', '1.9×'),
        (yr_eq10n, '#27ae60', 'solid', '1.0×'),
        (yr_eth_n, '#e74c3c', 'dot',   'ETH B&H'),
    ]:
        fig_yr.add_trace(go.Scatter(
            x=yr_dates_list, y=eq_n.tolist(),
            name=lbl, line=dict(color=color, width=1.8, dash=dash),
            showlegend=False,
        ), row=1, col=1)

    # Markers 1.9×
    (ex_, ey_), (ax_, ay_), (sx_, sy_) = m19
    fig_yr.add_trace(go.Scatter(
        x=ex_, y=ey_, mode='markers', showlegend=False,
        marker=dict(symbol='triangle-up', size=7, opacity=0.65, color='#2ecc71',
                    line=dict(color='#1a7a36', width=0.5)),
        hovertemplate='<b>▲ Entry 1.9×</b><br>%{x|%Y-%m-%d}<extra></extra>',
    ), row=1, col=1)
    fig_yr.add_trace(go.Scatter(
        x=ax_, y=ay_, mode='markers', showlegend=False,
        marker=dict(symbol='triangle-down', size=7, opacity=0.65, color='#e74c3c',
                    line=dict(color='#8b0000', width=0.5)),
        hovertemplate='<b>▼ ADX Exit 1.9×</b><br>%{x|%Y-%m-%d}<extra></extra>',
    ), row=1, col=1)
    fig_yr.add_trace(go.Scatter(
        x=sx_, y=sy_, mode='markers', showlegend=False,
        marker=dict(symbol='triangle-down', size=7, opacity=0.65, color='#e67e22',
                    line=dict(color='#7d3c00', width=0.5)),
        hovertemplate='<b>▼ Stop Exit 1.9×</b><br>%{x|%Y-%m-%d}<extra></extra>',
    ), row=1, col=1)

    # Markers 1.0×
    (ex_, ey_), (ax_, ay_), (sx_, sy_) = m10
    fig_yr.add_trace(go.Scatter(
        x=ex_, y=ey_, mode='markers', showlegend=False,
        marker=dict(symbol='triangle-up', size=7, opacity=0.65, color='#2ecc71',
                    line=dict(color='#1a7a36', width=0.5)),
        hovertemplate='<b>▲ Entry 1.0×</b><br>%{x|%Y-%m-%d}<extra></extra>',
    ), row=1, col=1)
    fig_yr.add_trace(go.Scatter(
        x=ax_, y=ay_, mode='markers', showlegend=False,
        marker=dict(symbol='triangle-down', size=7, opacity=0.65, color='#e74c3c',
                    line=dict(color='#8b0000', width=0.5)),
        hovertemplate='<b>▼ ADX Exit 1.0×</b><br>%{x|%Y-%m-%d}<extra></extra>',
    ), row=1, col=1)
    fig_yr.add_trace(go.Scatter(
        x=sx_, y=sy_, mode='markers', showlegend=False,
        marker=dict(symbol='triangle-down', size=7, opacity=0.65, color='#e67e22',
                    line=dict(color='#7d3c00', width=0.5)),
        hovertemplate='<b>▼ Stop Exit 1.0×</b><br>%{x|%Y-%m-%d}<extra></extra>',
    ), row=1, col=1)

    # Drawdown panel
    for dd_, color, dash in [
        (yr_dd19, '#2980b9', 'solid'),
        (yr_dd10, '#27ae60', 'solid'),
        (yr_ddbh, '#e74c3c', 'dot'),
    ]:
        fig_yr.add_trace(go.Scatter(
            x=yr_dates_list, y=dd_.tolist(),
            showlegend=False,
            line=dict(color=color, width=1.2, dash=dash),
        ), row=2, col=1)

    # Return% annotation box inside chart
    sign = lambda v: '+' if v >= 0 else ''
    ann_text = (
        f'<b>1.9×: {sign(ret19)}{ret19*100:.1f}%</b><br>'
        f'1.0×: {sign(ret10)}{ret10*100:.1f}%<br>'
        f'ETH: {sign(ret_bh)}{ret_bh*100:.1f}%'
    )
    fig_yr.add_annotation(
        xref='paper', yref='paper',
        x=0.99, y=0.97,
        text=ann_text,
        showarrow=False,
        align='right',
        font=dict(size=10, color='#222'),
        bgcolor='rgba(255,255,255,0.82)',
        bordercolor='#ccc', borderwidth=1,
        borderpad=4,
    )

    fig_yr.update_layout(
        title=dict(
            text=f'<b>{yr}</b>',
            font=dict(size=11, color='#333'),
            x=0.5, xanchor='center', y=0.97,
        ),
        height=260,
        hovermode='x unified',
        paper_bgcolor='white',
        plot_bgcolor='#fafafa',
        margin=dict(l=60, r=12, t=28, b=30),
    )
    fig_yr.update_yaxes(
        row=1, col=1,
        title_text='Return (base=1)', gridcolor='#ececec',
        tickformat='.2f',
    )
    fig_yr.update_xaxes(row=1, col=1, gridcolor='#ececec', showticklabels=False)
    fig_yr.update_yaxes(
        row=2, col=1,
        title_text='DD%', tickformat='.0f', ticksuffix='%',
        gridcolor='#ececec',
    )
    fig_yr.update_xaxes(row=2, col=1, gridcolor='#ececec')

    year_figs.append((yr, fig_yr, ret19, ret10, ret_bh))
    print(f"  {yr}: 1.9×={ret19*100:+.1f}%  1.0×={ret10*100:+.1f}%  ETH={ret_bh*100:+.1f}%")

# ── Assemble HTML ─────────────────────────────────────────────────────────────
print("\nAssembling HTML...")
main_html = fig_main.to_html(
    full_html=False, include_plotlyjs='cdn',
    config={'displayModeBar': True, 'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']},
)

year_blocks = []
for item in year_figs:
    if item is None:
        year_blocks.append('<div class="yr-panel"><p style="color:#999;text-align:center">No data</p></div>')
        continue
    yr, fig_yr, *_ = item
    inner = fig_yr.to_html(
        full_html=False, include_plotlyjs=False,
        config={'displayModeBar': False, 'displaylogo': False},
    )
    year_blocks.append(f'<div class="yr-panel">{inner}</div>')

# Legend strip (shown once above year panels)
legend_html = """
<div id="yr-legend">
  <span style="color:#2980b9;font-weight:700">━━</span> 1.9× Leveraged &nbsp;&nbsp;
  <span style="color:#27ae60;font-weight:700">━━</span> 1.0× Unleveraged &nbsp;&nbsp;
  <span style="color:#e74c3c;font-weight:700">┅┅</span> ETH B&H &nbsp;&nbsp;
  <span style="color:#2ecc71;font-weight:700">▲</span> Entry &nbsp;
  <span style="color:#e74c3c;font-weight:700">▼</span> ADX Exit &nbsp;
  <span style="color:#e67e22;font-weight:700">▼</span> Stop Exit
</div>
"""

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Stage 3 — Equity Curve Full (2018–2025)</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #f0f2f5; color: #222; }}
#main-chart {{ background: white; padding: 4px; margin-bottom: 12px; }}
#yr-section {{ background: #f0f2f5; padding: 12px 16px 20px; }}
#yr-title {{
  font-size: 14px; font-weight: 700; color: #333;
  margin-bottom: 6px; padding-left: 2px;
}}
#yr-legend {{
  font-size: 12px; color: #555;
  margin-bottom: 10px; padding-left: 2px;
}}
#yr-grid {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}}
.yr-panel {{
  background: white;
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.10);
  overflow: hidden;
}}
</style>
</head>
<body>

<div id="main-chart">
{main_html}
</div>

<div id="yr-section">
  <div id="yr-title">Year-by-Year Breakdown  (linear scale, normalised to 1.0 at year start)</div>
  {legend_html}
  <div id="yr-grid">
    {''.join(year_blocks)}
  </div>
</div>

</body>
</html>"""

out_path = os.path.join(RESULTS_DIR, 'stage3_equity_curve_full.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(full_html)

sz = os.path.getsize(out_path) / 1024
print(f'\nSaved → results/stage3_equity_curve_full.html  ({sz:.0f} KB)')
