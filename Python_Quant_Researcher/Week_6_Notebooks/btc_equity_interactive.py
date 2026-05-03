"""
btc_equity_interactive.py
Week 6 — Interactive Plotly equity comparison
BTC SMA 120/25% vs BTC ADX 19/14 vs Buy-and-Hold

Bug fix applied: all backtest functions now store entry_date at entry time
(previously stored as dates[exit_index-1], which caused build_daily_equity
to mark each trade to market for only 2 days; equity was flat for all other
holding-period days).

Output: Week_6_Notebooks/results/btc_equity_interactive.html
"""

import numpy as np
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SMA_PERIOD = 120
TRAIL_PCT  = 0.25
ADX_THRESH = 19
ADX_PERIOD = 14
FIXED_STOP = 0.03
COST       = 0.00075 * 2   # 0.15% round-trip

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
os.makedirs(RESULTS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Backtest functions — entry_date stored at entry, not at exit
# ---------------------------------------------------------------------------
def run_sma_pct_trail(closes, lows, dates, sma_vals, trail_pct):
    first_valid = int(np.argmax(~np.isnan(sma_vals)))
    pos = ep = pk = sp = 0.0
    entry_date = None
    trades = []
    sig_prev = False
    for i in range(first_valid, len(closes)):
        cl, lo, sv = closes[i], lows[i], sma_vals[i]
        if np.isnan(sv):
            continue
        sig_cur   = cl > sv
        crossover = sig_cur and not sig_prev
        if pos == 1:
            if cl > pk:
                pk = cl
                sp = pk * (1 - trail_pct)
            if lo <= sp:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': sp,
                                'return': (sp - ep) / ep, 'exit_reason': 'TRAIL'})
                pos = ep = pk = sp = 0.0
                entry_date = None
            elif not sig_cur:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'SMA'})
                pos = ep = pk = sp = 0.0
                entry_date = None
        if pos == 0 and crossover:
            pos = 1
            ep = pk = cl
            sp = cl * (1 - trail_pct)
            entry_date = dates[i]
        sig_prev = sig_cur
    if pos == 1:
        trades.append({'entry_date': entry_date, 'entry_price': ep,
                       'exit_date': dates[-1], 'exit_price': closes[-1],
                       'return': (closes[-1] - ep) / ep, 'exit_reason': 'EOD'})
    return trades


def run_fixed_stop(closes, lows, signals, dates, stop_pct):
    pos = ep = sp = 0.0
    entry_date = None
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sig = lows[i], closes[i], signals[i]
        if pos == 1:
            if lo <= sp:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': sp,
                                'return': (sp - ep) / ep, 'exit_reason': 'STOP'})
                pos = ep = sp = 0.0
                entry_date = None
            elif not sig:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                                'exit_date': dates[i], 'exit_price': cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'ADX'})
                pos = ep = sp = 0.0
                entry_date = None
        elif pos == 0 and sig:
            ep = cl
            sp = cl * (1 - stop_pct)
            pos = 1
            entry_date = dates[i]
    return trades


def build_daily_equity(trades, close_series):
    n         = len(close_series)
    closes_a  = close_series.values
    date_idx  = {d: i for i, d in enumerate(close_series.index)}
    equity    = np.ones(n)
    portfolio = 1.0
    prev_i    = 0
    for t in trades:
        ei = date_idx.get(pd.Timestamp(t['entry_date']))
        xi = date_idx.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None or xi >= n:
            continue
        equity[prev_i:ei]  = portfolio
        equity[ei:xi+1]    = portfolio * closes_a[ei:xi+1] / t['entry_price']
        portfolio          *= (1 + t['return'] - COST)
        equity[xi]          = portfolio
        prev_i              = xi + 1
    equity[prev_i:] = portfolio
    return equity


def build_position_mask(trades, date_index):
    """Return arrays: pos_open (bool), days_in_trade (int) for each calendar day."""
    n             = len(date_index)
    pos_open      = np.zeros(n, dtype=bool)
    days_in_trade = np.zeros(n, dtype=int)
    date_to_idx   = {d: i for i, d in enumerate(date_index)}
    for t in trades:
        ei = date_to_idx.get(pd.Timestamp(t['entry_date']))
        xi = date_to_idx.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None:
            continue
        xi_c = min(xi, n - 1)
        length = xi_c - ei + 1
        pos_open[ei:xi_c+1]      = True
        days_in_trade[ei:xi_c+1] = np.arange(length)
    return pos_open, days_in_trade


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
print("Fetching BTC-USD data (2018–present)...")
raw = yf.download('BTC-USD', start='2018-01-01', interval='1d',
                  progress=False, auto_adjust=True)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = raw[['Open', 'High', 'Low', 'Close']].dropna().copy()
df.index = pd.to_datetime(df.index)
dates  = df.index
closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)

# ---------------------------------------------------------------------------
# Backtests
# ---------------------------------------------------------------------------
print(f"Running SMA {SMA_PERIOD}/{int(TRAIL_PCT*100)}%...")
sma_vals   = pd.Series(closes).rolling(SMA_PERIOD).mean().values
sma_trades = run_sma_pct_trail(closes, lows, dates, sma_vals, TRAIL_PCT)
sma_eq     = build_daily_equity(sma_trades, df['Close'])
sma_pos, sma_days = build_position_mask(sma_trades, dates)
print(f"  {len(sma_trades)} trades")

print(f"Running ADX {ADX_THRESH}/{ADX_PERIOD} fixed {int(FIXED_STOP*100)}%...")
adx_ind    = ADXIndicator(df['High'], df['Low'], df['Close'], window=ADX_PERIOD)
sig_adx    = (adx_ind.adx().values >= ADX_THRESH) & \
             (adx_ind.adx_pos().values > adx_ind.adx_neg().values)
adx_trades = run_fixed_stop(closes, lows, sig_adx, dates, FIXED_STOP)
adx_eq     = build_daily_equity(adx_trades, df['Close'])
adx_pos, adx_days = build_position_mask(adx_trades, dates)
print(f"  {len(adx_trades)} trades")

bh_eq = closes / closes[0]

# Quick corrected metrics summary
def quick_metrics(equity, trades, label):
    dr       = np.diff(equity) / equity[:-1]
    dn       = dr[dr < 0]
    sortino  = dr.mean() / dn.std() * np.sqrt(365) if len(dn) > 0 else 0
    pk       = np.maximum.accumulate(equity)
    dd_mtm   = ((equity - pk) / pk).min()
    rets_net = np.array([t['return'] for t in trades]) - COST
    eq_pt    = np.cumprod(1 + rets_net)
    dd_trade = ((eq_pt - np.maximum.accumulate(eq_pt)) / np.maximum.accumulate(eq_pt)).min()
    years    = (dates[-1] - dates[0]).days / 365.25
    ann      = eq_pt[-1] ** (1 / years) - 1
    print(f"  {label}: Ann {ann*100:.1f}%, MaxDD_trade {dd_trade*100:.1f}%, "
          f"MaxDD_MtM {dd_mtm*100:.1f}%, Sortino {sortino:.3f}")

print("\n--- Corrected metrics (entry_date bug fixed) ---")
quick_metrics(sma_eq, sma_trades, f"SMA {SMA_PERIOD}/{int(TRAIL_PCT*100)}%")
quick_metrics(adx_eq, adx_trades, f"ADX {ADX_THRESH}/{ADX_PERIOD} fixed {int(FIXED_STOP*100)}%")

# ---------------------------------------------------------------------------
# Derived series
# ---------------------------------------------------------------------------
def dd_pct(equity):
    pk = np.maximum.accumulate(equity)
    return (equity - pk) / pk * 100

dd_sma = dd_pct(sma_eq)
dd_adx = dd_pct(adx_eq)
dd_bh  = dd_pct(bh_eq)

# ---------------------------------------------------------------------------
# Hover text builders
# ---------------------------------------------------------------------------
def equity_hover(label, equity, dd, pos_open, days_in_trade):
    out = []
    for i, d in enumerate(dates):
        t = (f"<b>{d.date()}</b><br>"
             f"{label}: {equity[i]:.2f}x<br>"
             f"DD from peak: {dd[i]:.1f}%<br>"
             f"Position: {'Open' if pos_open[i] else 'Flat'}")
        if pos_open[i]:
            t += f"<br>Days in trade: {int(days_in_trade[i])}"
        out.append(t)
    return out

def dd_hover(label, dd, equity, pos_open):
    return [
        f"<b>{d.date()}</b><br>"
        f"{label} DD: {dd[i]:.1f}%<br>"
        f"Portfolio: {equity[i]:.2f}x<br>"
        f"Position: {'Open' if pos_open[i] else 'Flat'}"
        for i, d in enumerate(dates)
    ]

ht_sma_eq = equity_hover('SMA 120/25%', sma_eq, dd_sma, sma_pos, sma_days)
ht_adx_eq = equity_hover('ADX 19/14',   adx_eq, dd_adx, adx_pos, adx_days)
ht_bh_eq  = [f"<b>{d.date()}</b><br>B&H: {bh_eq[i]:.2f}x<br>DD: {dd_bh[i]:.1f}%"
             for i, d in enumerate(dates)]
ht_sma_dd = dd_hover('SMA', dd_sma, sma_eq, sma_pos)
ht_adx_dd = dd_hover('ADX', dd_adx, adx_eq, adx_pos)
ht_bh_dd  = [f"<b>{d.date()}</b><br>B&H DD: {dd_bh[i]:.1f}%<br>B&H: {bh_eq[i]:.2f}x"
             for i, d in enumerate(dates)]

# ---------------------------------------------------------------------------
# Trade marker helpers
# ---------------------------------------------------------------------------
def marker_equity(equity, trade_dates):
    didx = pd.DatetimeIndex(dates)
    idxs = didx.get_indexer(pd.to_datetime(trade_dates), method='nearest')
    return [equity[j] for j in idxs]

df_sma     = pd.DataFrame(sma_trades)
sma_ent_d  = pd.to_datetime(df_sma['entry_date'])
sma_ex_d   = pd.to_datetime(df_sma['exit_date'])
sma_ent_y  = marker_equity(sma_eq, sma_ent_d)
sma_ex_y   = marker_equity(sma_eq, sma_ex_d)
sma_ent_hv = [f"<b>SMA Entry</b><br>{d.date()}<br>Portfolio: {p:.2f}x"
              for d, p in zip(sma_ent_d, sma_ent_y)]
sma_ex_hv  = [f"<b>SMA Exit ({df_sma['exit_reason'].iloc[i]})</b><br>"
              f"{d.date()}<br>Portfolio: {p:.2f}x<br>"
              f"Return: {df_sma['return'].iloc[i]*100:.1f}%"
              for i, (d, p) in enumerate(zip(sma_ex_d, sma_ex_y))]

df_adx     = pd.DataFrame(adx_trades)
adx_ent_d  = pd.to_datetime(df_adx['entry_date'])
adx_ex_d   = pd.to_datetime(df_adx['exit_date'])
adx_ent_y  = marker_equity(adx_eq, adx_ent_d)
adx_ex_y   = marker_equity(adx_eq, adx_ex_d)
adx_ent_hv = [f"<b>ADX Entry</b><br>{d.date()}<br>Portfolio: {p:.2f}x"
              for d, p in zip(adx_ent_d, adx_ent_y)]
adx_ex_hv  = [f"<b>ADX Exit ({df_adx['exit_reason'].iloc[i]})</b><br>"
              f"{d.date()}<br>Portfolio: {p:.2f}x<br>"
              f"Return: {df_adx['return'].iloc[i]*100:.1f}%"
              for i, (d, p) in enumerate(zip(adx_ex_d, adx_ex_y))]

# ---------------------------------------------------------------------------
# Build figure
# ---------------------------------------------------------------------------
C_SMA = '#2196F3'
C_ADX = '#FF9800'
C_BH  = '#9E9E9E'

fig = make_subplots(
    rows=2, cols=1,
    row_heights=[0.65, 0.35],
    shared_xaxes=True,
    vertical_spacing=0.06,
    subplot_titles=(
        f'Portfolio Value — BTC SMA {SMA_PERIOD}/{int(TRAIL_PCT*100)}% '
        f'vs ADX {ADX_THRESH}/{ADX_PERIOD} vs Buy-and-Hold',
        'Drawdown from Peak'
    )
)

# --- Equity lines ---
fig.add_trace(go.Scatter(
    x=dates, y=sma_eq, mode='lines', name='SMA 120/25%',
    line=dict(color=C_SMA, width=2.2),
    hovertext=ht_sma_eq, hoverinfo='text',
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=dates, y=adx_eq, mode='lines', name='ADX 19/14 fixed 3%',
    line=dict(color=C_ADX, width=1.8),
    hovertext=ht_adx_eq, hoverinfo='text',
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=dates, y=bh_eq, mode='lines', name='Buy-and-Hold',
    line=dict(color=C_BH, width=1.4, dash='dash'),
    hovertext=ht_bh_eq, hoverinfo='text',
), row=1, col=1)

# --- SMA entry/exit markers ---
fig.add_trace(go.Scatter(
    x=sma_ent_d, y=sma_ent_y, mode='markers', name='SMA entry',
    marker=dict(symbol='triangle-up', color='#4CAF50', size=10,
                line=dict(color='white', width=0.6)),
    hovertext=sma_ent_hv, hoverinfo='text',
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=sma_ex_d, y=sma_ex_y, mode='markers', name='SMA exit',
    marker=dict(symbol='triangle-down', color='#F44336', size=10,
                line=dict(color='white', width=0.6)),
    hovertext=sma_ex_hv, hoverinfo='text',
), row=1, col=1)

# --- ADX entry/exit markers ---
fig.add_trace(go.Scatter(
    x=adx_ent_d, y=adx_ent_y, mode='markers', name='ADX entry',
    marker=dict(symbol='triangle-up', color='#00BCD4', size=6, opacity=0.70),
    hovertext=adx_ent_hv, hoverinfo='text',
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=adx_ex_d, y=adx_ex_y, mode='markers', name='ADX exit',
    marker=dict(symbol='triangle-down', color='#FF5722', size=6, opacity=0.70),
    hovertext=adx_ex_hv, hoverinfo='text',
), row=1, col=1)

# --- Drawdown lines (no fill) ---
fig.add_trace(go.Scatter(
    x=dates, y=dd_sma, mode='lines', name='SMA DD',
    line=dict(color=C_SMA, width=1.5),
    hovertext=ht_sma_dd, hoverinfo='text', showlegend=False,
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=dates, y=dd_adx, mode='lines', name='ADX DD',
    line=dict(color=C_ADX, width=1.5),
    hovertext=ht_adx_dd, hoverinfo='text', showlegend=False,
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=dates, y=dd_bh, mode='lines', name='B&H DD',
    line=dict(color=C_BH, width=1.2, dash='dash'),
    hovertext=ht_bh_dd, hoverinfo='text', showlegend=False,
), row=2, col=1)

# --- Region shading (both panels) ---
for x0, x1, fill, text_col, label in [
    ('2021-01-01', '2021-11-10', 'rgba(76,175,80,0.08)',  '#81C784', '2021 Bull'),
    ('2022-01-01', '2022-12-31', 'rgba(244,67,54,0.08)',  '#EF9A9A', '2022 Bear'),
]:
    for r in [1, 2]:
        fig.add_vrect(x0=x0, x1=x1, fillcolor=fill, layer='below',
                      line_width=0, row=r, col=1)
    # Text annotation on equity panel only
    fig.add_annotation(
        x=x0, xref='x', y=0.97, yref='paper',
        text=f'<b>{label}</b>',
        font=dict(color=text_col, size=11),
        showarrow=False, xanchor='left', yanchor='top',
    )

# --- Layout ---
fig.update_yaxes(
    type='log', row=1, col=1,
    tickformat='.2f',
    title_text='Portfolio value (log, starts = 1.00)',
    gridcolor='rgba(100,100,100,0.18)',
    minor=dict(showgrid=False),
)
fig.update_yaxes(
    row=2, col=1,
    tickformat='.0f', ticksuffix='%',
    title_text='Drawdown %',
    gridcolor='rgba(100,100,100,0.18)',
)
fig.update_xaxes(showgrid=True, gridcolor='rgba(100,100,100,0.15)')

fig.update_layout(
    title=dict(
        text=(f'BTC SMA {SMA_PERIOD}/{int(TRAIL_PCT*100)}% vs '
              f'ADX {ADX_THRESH}/{ADX_PERIOD} fixed {int(FIXED_STOP*100)}% vs Buy-and-Hold'
              f'<br><sup>2018–2026  |  0.15% round-trip costs  |  '
              f'Daily mark-to-market equity — entry_date bug corrected</sup>'),
        font=dict(size=14, color='white'),
        x=0.5, xanchor='center',
    ),
    template='plotly_dark',
    hovermode='closest',
    height=900,
    legend=dict(
        orientation='v', x=1.01, y=1.0, xanchor='left',
        bgcolor='rgba(15,15,25,0.88)',
        font=dict(size=11),
        bordercolor='rgba(100,100,100,0.35)', borderwidth=1,
    ),
    margin=dict(l=70, r=175, t=85, b=50),
    paper_bgcolor='#0e1117',
    plot_bgcolor='#0e1117',
)

out_html = os.path.join(RESULTS_DIR, 'btc_equity_interactive.html')
fig.write_html(out_html, include_plotlyjs='cdn')
sz = os.path.getsize(out_html) / 1024
print(f"\nSaved → results/btc_equity_interactive.html  ({sz:.0f} KB)")
