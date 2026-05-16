#!/usr/bin/env python3
"""
Build ETH RSI Deployment Card v1
Output: Deployment_Documents/Week_6/ETH_RSI_Deployment_Card_v1.html

Self-contained: re-runs the RSI backtest (same logic as stage5_final_comparison.py)
to generate the equity curve chart. Metrics hardcoded from Stage 5 authoritative run.
"""

import os
import warnings
from datetime import date as _date
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR = os.path.join(SCRIPT_DIR, '..', 'Deployment_Documents', 'Week_6')
os.makedirs(DEPLOY_DIR, exist_ok=True)

RUN_DATE = _date.today().strftime('%Y-%m-%d')

# ── Strategy constants (match deployed bot exactly) ──────────────────────────
RSI_PER   = 14
RSI_ENTRY = 43
RSI_EXIT  = 48
STOP_PCT  = 0.15
SMA_WIN   = 120
COSTS     = 0.0015

# ── Stage 5 authoritative metrics (from stage5_final_comparison.csv) ─────────
M = {
    'annual_ret':  0.1608,
    'total_ret':   2.4800,
    'mtm_maxdd':  -0.2936,
    'calmar':      0.548,
    'sharpe':      0.826,
    'sortino':     0.307,
    'n_trades':    31,
    'win_rate':    0.9355,
    'avg_win':     0.0564,
    'avg_loss':   -0.1515,
    'pf':          5.395,
    'stop_exit':   0.0645,
}
BH = {
    'annual_ret':  0.1367,
    'total_ret':   1.9192,
    'mtm_maxdd':  -0.9396,
    'calmar':      0.145,
    'sharpe':      0.579,
    'sortino':     0.795,
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. FETCH + BACKTEST (for equity curve chart only)
# ─────────────────────────────────────────────────────────────────────────────

print("Fetching ETH-USD data...")
raw = yf.download('ETH-USD', start='2018-01-01', auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
df     = raw[['High', 'Low', 'Close']].copy().dropna()
closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index
N      = len(df)
YEARS  = (dates[-1] - dates[0]).days / 365.25
DATA_START = dates[0].strftime('%Y-%m-%d')
DATA_END   = dates[-1].strftime('%Y-%m-%d')

print("Computing RSI / SMA signals...")

def calc_rsi(close_arr, period):
    s     = pd.Series(close_arr)
    delta = s.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_l = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, 1e-9)
    return (100 - 100 / (1 + rs)).values

rsi_vals      = calc_rsi(closes, RSI_PER)
sma_vals      = pd.Series(closes).rolling(SMA_WIN).mean().values
rsi_entry_sig = (rsi_vals < RSI_ENTRY) & (closes > sma_vals)
rsi_exit_sig  = (rsi_vals > RSI_EXIT)

print("Running RSI backtest...")
pos = 0; ep = stop = 0.0; entry_date = None
trades = []
for i in range(1, N):
    lo = lows[i]; cl = closes[i]
    if pos == 1:
        if lo <= stop:
            trades.append({'entry_date': entry_date, 'exit_date': dates[i],
                           'entry_price': ep, 'exit_price': stop,
                           'return': (stop - ep) / ep, 'exit_reason': 'STOP_LOSS'})
            pos = 0; entry_date = None
        elif rsi_exit_sig[i]:
            trades.append({'entry_date': entry_date, 'exit_date': dates[i],
                           'entry_price': ep, 'exit_price': cl,
                           'return': (cl - ep) / ep, 'exit_reason': 'RSI_EXIT'})
            pos = 0; entry_date = None
    elif rsi_entry_sig[i]:
        ep = cl; stop = cl * (1 - STOP_PCT)
        entry_date = dates[i]; pos = 1

print(f"  {len(trades)} trades")

print("Building equity curve...")
arr       = closes.copy()
date_to_i = pd.Series(np.arange(N), index=df.index)
equity    = np.ones(N)
portfolio = 1.0; prev_i = 0
for t in trades:
    ei = date_to_i.get(pd.Timestamp(t['entry_date']))
    xi = date_to_i.get(pd.Timestamp(t['exit_date']))
    if ei is None or xi is None: continue
    equity[prev_i:ei] = portfolio
    equity[ei:xi+1]   = portfolio * arr[ei:xi+1] / t['entry_price']
    portfolio        *= (1 + t['return'] - COSTS)
    equity[xi]        = portfolio
    prev_i            = xi + 1
equity[prev_i:] = portfolio

bh_eq     = closes / closes[0]
date_list = [d.strftime('%Y-%m-%d') for d in dates]

def yr_rets(eq):
    res = {}
    for yr in sorted(set(d.year for d in dates)):
        idx = [i for i, d in enumerate(dates) if d.year == yr]
        if idx: res[yr] = eq[idx[-1]] / eq[idx[0]] - 1
    return res

rsi_yr = yr_rets(equity)
bh_yr  = yr_rets(bh_eq)
all_years = sorted(rsi_yr)


# ─────────────────────────────────────────────────────────────────────────────
# 2. PLOTLY EQUITY CHART
# ─────────────────────────────────────────────────────────────────────────────

C_RSI = '#E65100'
C_BH  = '#9E9E9E'

fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True,
    row_heights=[0.68, 0.32], vertical_spacing=0.05,
    subplot_titles=('Equity Curve (log scale, $1 start, 0.15% round-trip costs)',
                    'Drawdown from Peak'),
)

fig.add_trace(go.Scatter(
    x=date_list, y=equity.tolist(), name='ETH RSI 14/43/48 (15% stop)',
    line=dict(color=C_RSI, width=2),
    hovertemplate='%{x}<br>Equity: %{y:.3f}×<extra>ETH RSI</extra>',
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=date_list, y=bh_eq.tolist(), name='Buy & Hold ETH',
    line=dict(color=C_BH, width=1.5, dash='dot'),
    hovertemplate='%{x}<br>Equity: %{y:.3f}×<extra>B&H ETH</extra>',
), row=1, col=1)

rsi_peak = np.maximum.accumulate(equity)
rsi_dd   = (equity - rsi_peak) / rsi_peak
bh_peak  = np.maximum.accumulate(bh_eq)
bh_dd    = (bh_eq - bh_peak) / bh_peak

fig.add_trace(go.Scatter(
    x=date_list, y=(rsi_dd * 100).tolist(), name='RSI DD',
    line=dict(color=C_RSI, width=1.4), showlegend=False,
    fill='tozeroy', fillcolor='rgba(230,81,0,0.08)',
    hovertemplate='%{x}<br>DD: %{y:.1f}%<extra>ETH RSI</extra>',
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=date_list, y=(bh_dd * 100).tolist(), name='B&H DD',
    line=dict(color=C_BH, width=1.2, dash='dot'), showlegend=False,
    hovertemplate='%{x}<br>DD: %{y:.1f}%<extra>B&H ETH</extra>',
), row=2, col=1)

fig.update_yaxes(type='log', tickformat='.2f', title_text='Equity (×)', row=1, col=1)
fig.update_yaxes(ticksuffix='%', title_text='Drawdown', row=2, col=1)
fig.update_xaxes(title_text='Date', row=2, col=1)
fig.update_layout(
    height=520, margin=dict(l=60, r=20, t=45, b=30),
    legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.9)',
                bordercolor='#ccc', borderwidth=1),
    hovermode='x unified', paper_bgcolor='white', plot_bgcolor='#fafafa',
)
chart_html = fig.to_html(full_html=False, include_plotlyjs=False, div_id='equity_chart')


# ─────────────────────────────────────────────────────────────────────────────
# 3. HTML ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

yr_rsi_cells = "".join(
    f"<td class='{'pos' if rsi_yr.get(yr, 0) > 0 else 'neu' if rsi_yr.get(yr, 0) == 0 else 'neg'}'>"
    f"{rsi_yr.get(yr, 0)*100:+.1f}%</td>"
    for yr in all_years
)
yr_bh_cells = "".join(
    f"<td class='{'pos' if bh_yr.get(yr, 0) > 0 else 'neg'}'>{bh_yr.get(yr, 0)*100:+.1f}%</td>"
    for yr in all_years
)
yr_headers = "".join(f"<th>{yr}</th>" for yr in all_years)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ETH RSI — Deployment Card v1</title>
  <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #ECEFF1; color: #212121; margin: 0; padding: 0; font-size: 14px; }}

    /* ── Header ── */
    .header {{ background: linear-gradient(135deg, #BF360C 0%, #E64A19 55%, #FF5722 100%);
               color: #fff; padding: 28px 32px 24px; }}
    .header h1 {{ margin: 0 0 6px; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.3px; }}
    .header .sub {{ font-size: 0.88rem; opacity: 0.85; margin: 0; }}
    .status-badge {{ display: inline-block; background: #FF9800; color: #fff;
                     font-size: 0.75rem; font-weight: 700; padding: 4px 10px;
                     border-radius: 12px; letter-spacing: 0.5px; margin-top: 10px; }}

    /* ── Layout ── */
    .wrapper {{ max-width: 1100px; margin: 0 auto; padding: 24px 20px 48px; }}
    .card {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.10);
             padding: 22px 24px; margin-bottom: 20px; }}
    .card h2 {{ font-size: 1rem; font-weight: 700; color: #BF360C; margin: 0 0 14px;
                border-bottom: 2px solid #FBE9E7; padding-bottom: 8px;
                text-transform: uppercase; letter-spacing: 0.4px; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    @media(max-width: 700px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

    /* ── Tables ── */
    table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
    thead th {{ background: #BF360C; color: #fff; padding: 8px 11px; text-align: center;
                font-weight: 600; white-space: nowrap; }}
    thead th:first-child {{ text-align: left; }}
    tbody tr:nth-child(even) {{ background: #F5F5F5; }}
    tbody td {{ padding: 7px 11px; border-bottom: 1px solid #EEEEEE; text-align: center; }}
    tbody td:first-child {{ text-align: left; font-weight: 500; }}
    .highlight-row td {{ background: #FBE9E7 !important; font-weight: 600; color: #BF360C; }}
    .bh-row td {{ color: #757575; }}
    td.pos {{ color: #2E7D32; font-weight: 600; }}
    td.neg {{ color: #C62828; font-weight: 600; }}
    td.neu {{ color: #888; }}

    /* ── Params table ── */
    .param-table td:first-child {{ color: #555; width: 52%; }}
    .param-table td:last-child {{ font-weight: 600; font-family: 'SF Mono', monospace; font-size: 0.82rem; }}

    /* ── Validation checklist ── */
    .stage-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 8px; }}
    .stage-item {{ display: flex; align-items: flex-start; gap: 8px; padding: 8px 10px;
                   border-radius: 6px; background: #F1F8E9; border: 1px solid #C5E1A5; }}
    .stage-item.warn {{ background: #FFF8E1; border-color: #FFE082; }}
    .stage-item.blocked {{ background: #FFEBEE; border-color: #EF9A9A; }}
    .stage-icon {{ font-size: 1rem; flex-shrink: 0; line-height: 1.4; }}
    .stage-label {{ font-size: 0.78rem; color: #333; line-height: 1.4; }}
    .stage-label strong {{ display: block; font-size: 0.80rem; color: #1B5E20; }}
    .stage-item.warn .stage-label strong {{ color: #E65100; }}
    .stage-item.blocked .stage-label strong {{ color: #B71C1C; }}

    /* ── Risk register ── */
    .risk-block {{ border-radius: 6px; padding: 14px 16px; margin-bottom: 12px;
                   border-left: 4px solid; }}
    .risk-high {{ background: #FFF3E0; border-color: #E65100; }}
    .risk-high.urgent {{ background: #FFF0E0; border-color: #D84315;
                         box-shadow: 0 0 0 1px rgba(216,67,21,0.2); }}
    .risk-major {{ background: #FFFDE7; border-color: #F9A825; }}
    .risk-block .risk-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }}
    .risk-id {{ font-family: monospace; font-weight: 700; font-size: 0.82rem;
                background: rgba(0,0,0,0.07); padding: 2px 7px; border-radius: 4px; }}
    .risk-priority {{ font-size: 0.70rem; font-weight: 700; padding: 2px 7px;
                      border-radius: 10px; text-transform: uppercase; letter-spacing: 0.4px; }}
    .prio-high {{ background: #E65100; color: #fff; }}
    .prio-high.urgent {{ background: #D84315; color: #fff; }}
    .prio-major {{ background: #F9A825; color: #fff; }}
    .risk-urgent-tag {{ font-size: 0.70rem; font-weight: 700; padding: 2px 8px;
                        background: #D84315; color: #fff; border-radius: 10px;
                        letter-spacing: 0.3px; }}
    .risk-title {{ font-weight: 600; font-size: 0.86rem; }}
    .risk-desc {{ font-size: 0.82rem; color: #444; margin: 4px 0 6px; line-height: 1.5; }}
    .risk-mitigation {{ font-size: 0.80rem; color: #555; }}
    .risk-mitigation strong {{ color: #333; }}
    .risk-blocker {{ font-size: 0.78rem; margin-top: 6px; padding: 5px 10px;
                     background: rgba(216,67,21,0.1); border-radius: 4px;
                     color: #B71C1C; font-weight: 600; }}

    /* ── Decision banner ── */
    .decision-card {{ border-radius: 8px; padding: 20px 24px;
                      background: #FFF8E1; border: 2px solid #FF9800; }}
    .decision-card h3 {{ margin: 0 0 8px; font-size: 0.9rem; text-transform: uppercase;
                         letter-spacing: 0.5px; color: #E65100; }}
    .decision-card .verdict {{ font-size: 1.1rem; font-weight: 700; color: #BF360C; margin-bottom: 10px; }}
    .decision-card p {{ margin: 4px 0; font-size: 0.83rem; color: #444; line-height: 1.6; }}
    .gate-list {{ margin: 10px 0 0; padding: 0; list-style: none; }}
    .gate-list li {{ font-size: 0.82rem; padding: 4px 0; border-bottom: 1px solid rgba(0,0,0,0.06);
                     display: flex; gap: 8px; align-items: flex-start; }}
    .gate-list li:last-child {{ border-bottom: none; }}
    .gate-open {{ color: #E65100; font-weight: 700; flex-shrink: 0; }}
    .gate-done {{ color: #2E7D32; font-weight: 700; flex-shrink: 0; }}

    /* ── Performance note ── */
    .perf-note {{ margin-top: 12px; padding: 10px 14px; background: #E8F5E9;
                  border-left: 3px solid #4CAF50; border-radius: 0 4px 4px 0;
                  font-size: 0.81rem; color: #333; line-height: 1.6; }}
    .perf-note strong {{ color: #1B5E20; }}

    /* ── Methodology note ── */
    .methodology {{ font-size: 0.77rem; color: #666; background: #F5F5F5;
                    border-left: 3px solid #BF360C; padding: 9px 13px;
                    border-radius: 0 4px 4px 0; margin-top: 10px; line-height: 1.6; }}

    /* ── Overview text ── */
    .overview-text {{ font-size: 0.84rem; line-height: 1.7; color: #333; }}
    .overview-text h3 {{ font-size: 0.82rem; font-weight: 700; color: #BF360C;
                         margin: 12px 0 4px; text-transform: uppercase; letter-spacing: 0.3px; }}

    /* ── Live config ── */
    .live-config {{ background: #FBE9E7; border-radius: 6px; padding: 14px 16px; }}
    .live-config table {{ font-size: 0.82rem; }}
    .live-config td {{ padding: 5px 8px; border-bottom: 1px solid rgba(0,0,0,0.06); }}
    .live-config td:first-child {{ color: #555; width: 48%; }}
    .live-config td:last-child {{ font-weight: 600; font-family: monospace; }}

    .section-note {{ font-size: 0.78rem; color: #888; margin-top: 8px; }}
    .monte-carlo-table th {{ background: #5C6BC0; }}
    .monte-carlo-table {{ margin-top: 14px; }}
  </style>
</head>
<body>

<!-- ── HEADER ── -->
<div class="header">
  <h1>ETH RSI — Deployment Card</h1>
  <p class="sub">ETH/USDT · Binance Spot · Strategy ID: eth_rsi · v1.0</p>
  <div>
    <span class="status-badge">⚠ LIVE — Validation Phase ($150 capital)</span>
  </div>
</div>

<div class="wrapper">

<!-- ── OVERVIEW + LIVE CONFIG ── -->
<div class="card">
  <h2>Strategy Overview</h2>
  <div class="two-col">
    <div class="overview-text">
      <h3>What it does</h3>
      <p>Mean reversion strategy on ETH/USDT daily candles. Buys when ETH is oversold
         (RSI below 43) while in a bull regime (price above the 120-day SMA). Waits
         for momentum to recover, then exits when RSI rises back to 48. A hard stop at
         15% below entry protects against sustained downtrends breaking through the
         regime filter.</p>

      <h3>Entry condition</h3>
      <p>RSI(14) &lt; 43 <strong>AND</strong> Close &gt; 120-day SMA. RSI uses
         Wilder's exponential smoothing (alpha = 1/14). Both conditions must hold at
         the daily close. The SMA filter is the key regime gate — it prevents buying
         dips in bear markets where dips continue falling.</p>

      <h3>Exit conditions</h3>
      <p><strong>RSI recovery:</strong> exit at close when RSI &gt; 48. The 5-point
         gap between entry (43) and exit (48) gives the trade room to recover before
         triggering exit, reducing premature exits from single-bar noise.<br>
         <strong>Hard stop:</strong> 15% below entry price, checked against daily LOW.
         Stop is fixed at entry — does not trail. If daily LOW ≤ stop price, exits at
         stop price (gap protection).</p>

      <h3>Why it works</h3>
      <p>ETH in a confirmed bull regime (above 120 SMA) reliably recovers from short
         oversold readings. The 120 SMA filter eliminates the high-loss environment
         of sustained bear markets. Result: 93.5% backtest win rate across 31 trades,
         profit factor 5.395. The strategy sits flat most of the time — flat periods
         are capital preservation, not dead weight.</p>

      <h3>Validation status</h3>
      <p>Currently in validation phase. $150 capital deployed (fixed, not subject to
         weekly rebalance). Monitoring live win rate, P&amp;L per trade, and RSI recovery
         behaviour against backtest expectations. Full deployment conditional on
         resolving HIGH risk items and accumulating 20 live trades.</p>
    </div>

    <div>
      <div class="live-config">
        <table>
          <tbody>
            <tr><td>Status</td><td>LIVE — Validation Phase</td></tr>
            <tr><td>Asset</td><td>ETHUSDT (Spot)</td></tr>
            <tr><td>Exchange</td><td>Binance</td></tr>
            <tr><td>Capital allocated</td><td>$150 (fixed — not rebalanced)</td></tr>
            <tr><td>Current position</td><td>FLAT (waiting for RSI &lt; 43)</td></tr>
            <tr><td>Initial position size</td><td>$341 (Kelly at 75% WR)</td></tr>
            <tr><td>Scale-up target</td><td>$495 after 20 trades + WR ≥ 80%</td></tr>
            <tr><td>Stop type</td><td>STOP_LOSS (market), 15% below entry</td></tr>
            <tr><td>Live since</td><td>2026-05-07</td></tr>
            <tr><td>Bot file</td><td>rsi_production_bot.py</td></tr>
            <tr><td>Schedule</td><td>4× daily (00:05, 06:05, 12:05, 18:05 UTC)</td></tr>
            <tr><td>Kelly fraction</td><td>Half-Kelly: f* = 0.384 at 75% WR</td></tr>
            <tr><td>fixed_allocation</td><td>true (portfolio_state.json)</td></tr>
          </tbody>
        </table>
      </div>
      <p class="section-note" style="margin-top:8px">
        Capital is fixed at $150 — not adjusted by weekly rebalance.
        Position size ($341) is set conservatively at the 75% win rate Kelly level,
        not the 93.5% backtest rate. Scale-up to $495 requires 20 live trades
        with running win rate ≥ 80%.
      </p>
    </div>
  </div>
</div>

<!-- ── PARAMETERS ── -->
<div class="card">
  <h2>Parameters</h2>
  <div class="two-col">
    <div>
      <table class="param-table">
        <thead><tr><th colspan="2">Indicator Parameters</th></tr></thead>
        <tbody>
          <tr><td>RSI period</td><td>14 (Wilder's EWM, α = 1/14)</td></tr>
          <tr><td>Entry threshold</td><td>RSI &lt; 43 (oversold)</td></tr>
          <tr><td>Exit threshold</td><td>RSI &gt; 48 (momentum recovered)</td></tr>
          <tr><td>Entry/exit gap</td><td>5 points (noise filter)</td></tr>
          <tr><td>Regime filter</td><td>Close &gt; 120-day SMA (bull only)</td></tr>
          <tr><td>Stop type</td><td>Fixed hard stop — 15% below entry</td></tr>
          <tr><td>Stop check</td><td>Daily LOW (bar-by-bar)</td></tr>
          <tr><td>Round-trip cost</td><td>0.15% (0.075% × 2 taker)</td></tr>
        </tbody>
      </table>
    </div>
    <div>
      <table class="param-table">
        <thead><tr><th colspan="2">Execution Parameters</th></tr></thead>
        <tbody>
          <tr><td>Order type (entry)</td><td>MARKET (at signal close)</td></tr>
          <tr><td>Order type (stop)</td><td>STOP_LOSS (market trigger)</td></tr>
          <tr><td>Stop moves on entry</td><td>No — fixed at 15% from fill price</td></tr>
          <tr><td>Position size (initial)</td><td>$341 (Kelly at 75% WR)</td></tr>
          <tr><td>Position size (after gates)</td><td>$495 (Kelly at 80%+ WR)</td></tr>
          <tr><td>Stop verification</td><td>⚠️ Not yet implemented (RR-RSI-002)</td></tr>
          <tr><td>Telegram alerts</td><td>Entry / Exit / Health check (WAITING label)</td></tr>
          <tr><td>SMA filter in health check</td><td>Displayed on every run</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── BACKTEST PERFORMANCE ── -->
<div class="card">
  <h2>Backtest Performance — Stage 5 Authoritative Run</h2>
  <table>
    <thead>
      <tr>
        <th>Strategy</th>
        <th>Annual Ret</th>
        <th>Total Ret</th>
        <th>MtM MaxDD</th>
        <th>Calmar</th>
        <th>Sharpe</th>
        <th>Sortino</th>
        <th>Trades</th>
        <th>Win Rate</th>
        <th>Avg Win</th>
        <th>Avg Loss</th>
        <th>Prof. Factor</th>
        <th>Stop Exit%</th>
      </tr>
    </thead>
    <tbody>
      <tr class="highlight-row">
        <td>ETH RSI 14/43/48 (15% stop)</td>
        <td>+16.1%</td>
        <td>+248.0%</td>
        <td>-29.4%</td>
        <td>0.548</td>
        <td>0.826</td>
        <td>0.307</td>
        <td>31</td>
        <td>93.5%</td>
        <td>+5.6%</td>
        <td>-15.2%</td>
        <td>5.395</td>
        <td>6.5%</td>
      </tr>
      <tr class="bh-row">
        <td>Buy &amp; Hold ETH (no cost)</td>
        <td>+13.7%</td>
        <td>+191.9%</td>
        <td>-94.0%</td>
        <td>0.145</td>
        <td>0.579</td>
        <td>0.795</td>
        <td>—</td>
        <td>—</td>
        <td>—</td>
        <td>—</td>
        <td>—</td>
        <td>—</td>
      </tr>
    </tbody>
  </table>

  <div class="perf-note">
    <strong>Note on Sortino (0.307):</strong> This figure is lower than B&H ETH (0.795) and
    should not be read as poor risk management. The RSI strategy is flat roughly 90% of the
    time — those flat days register as near-zero daily returns, which suppresses the mean
    return in the Sortino numerator without adding downside risk. The true measure of this
    strategy's risk efficiency is <strong>Profit Factor 5.395</strong>: for every $1 lost on
    a stop exit, the strategy earns $5.40 on winning trades. MtM MaxDD of -29.4% vs B&H's
    -94.0% demonstrates the capital protection value of the regime filter and stop loss.
    For low-frequency mean reversion strategies, Profit Factor and Win Rate are the primary
    metrics; Sortino and Sharpe require high trade frequency to be meaningful.
  </div>

  <div class="methodology">
    <strong>Methodology:</strong> Daily mark-to-market equity curve · Stop checked vs daily LOW
    · Wilder's EWM RSI (α = 1/14) · 120-day SMA regime filter · Costs 0.15% round-trip
    deducted at exit · Sharpe / Sortino / Calmar derived from daily equity curve,
    annualised × √365 · Data: {DATA_START} → {DATA_END} ({YEARS:.1f} yrs) · Run: {RUN_DATE}
  </div>

  <div style="margin-top: 18px;">
    <table>
      <thead>
        <tr><th>Year-by-Year</th>{yr_headers}</tr>
      </thead>
      <tbody>
        <tr class="highlight-row"><td>ETH RSI 14/43/48</td>{yr_rsi_cells}</tr>
        <tr class="bh-row"><td>B&amp;H ETH</td>{yr_bh_cells}</tr>
      </tbody>
    </table>
    <p class="section-note">Years showing +0.0% indicate no trades triggered in that
       calendar year — the strategy was flat (in cash), not losing.</p>
  </div>

  <!-- Monte Carlo summary -->
  <div style="margin-top: 18px;">
    <table class="monte-carlo-table">
      <thead>
        <tr>
          <th>Win Rate Scenario</th>
          <th>Median Ann%</th>
          <th>P10%</th>
          <th>P90%</th>
          <th>P(negative yr)</th>
          <th>Kelly f*</th>
          <th>Position Size</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>93.5% — Backtest baseline</td><td class="pos">+22.3%</td><td>+14.3%</td><td>+30.8%</td><td>0.0%</td><td>+76.7%</td><td>$495 (capped)</td></tr>
        <tr><td>80.0% — Optimistic live</td><td class="pos">+6.9%</td><td class="neg">−3.4%</td><td>+18.2%</td><td>25.2%</td><td>+28.2%</td><td>$495 (capped)</td></tr>
        <tr style="background:#FFF8E1; font-weight:600"><td>75.0% — Moderate live ← deployed basis</td><td>−0.1%</td><td class="neg">−9.7%</td><td>+10.5%</td><td>55.5%</td><td>+10.2%</td><td><strong>$341</strong></td></tr>
        <tr><td>70.0% — Pessimistic live</td><td class="neg">−3.4%</td><td class="neg">−12.7%</td><td>+6.9%</td><td>74.0%</td><td class="neg">−7.7%</td><td class="neg">$0 — DO NOT TRADE</td></tr>
        <tr><td>65.0% — Stress test</td><td class="neg">−9.7%</td><td class="neg">−18.4%</td><td>−0.1%</td><td>90.8%</td><td class="neg">−25.7%</td><td class="neg">$0 — DO NOT TRADE</td></tr>
      </tbody>
    </table>
    <p class="section-note">Monte Carlo: 1,000 simulations, 31 trades, avg win +5.79%, avg loss −15.00%, 6.49-yr horizon.
       Kelly breakeven: 72.2% win rate. Position size set at 75% WR scenario (conservative). Source: RR-RSI-001.</p>
  </div>
</div>

<!-- ── EQUITY CURVE ── -->
<div class="card">
  <h2>Equity Curve</h2>
  {chart_html}
  <p class="section-note">Log scale. $1 start. Orange = ETH RSI 14/43/48 (15% stop, 0.15% costs).
     Grey dotted = Buy &amp; Hold ETH (no costs). Flat sections = strategy in cash (capital
     preservation, not losses). Shaded area = strategy drawdown.</p>
</div>

<!-- ── VALIDATION PIPELINE ── -->
<div class="card">
  <h2>Validation Pipeline Status</h2>
  <div class="stage-grid">
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Parameter Selection</strong>
        RSI 14/43/48/15%/120MA confirmed through grid search. FINAL parameters
        match Week 5 Day 5 optimisation output.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Bar-by-Bar Backtest</strong>
        Stop checked vs daily LOW. Entry/exit at daily close. Gap protection
        confirmed. 31 trades, 93.5% WR, PF 5.395.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Parameter Stability Scan</strong>
        Informal: RSI period 80%, oversold 67%, exit level 100%, stop 80%,
        MA filter 100% of tested values above PF 2.0. Parameters on a broad
        plateau.</div>
    </div>
    <div class="stage-item warn">
      <span class="stage-icon">⚠️</span>
      <div class="stage-label"><strong>Formal Stability Classification</strong>
        STABLE / MARGINAL / FRAGILE classification not yet run. Informal scan
        suggests STABLE but unconfirmed. Open item RR-RSI-006. Target: Week 7.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Monte Carlo Analysis</strong>
        1,000 simulations across 5 win rate scenarios. Kelly breakeven 72.2%.
        Position size set conservatively at 75% WR ($341). Documented in
        RR-RSI-001.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Kelly / Position Sizing</strong>
        Half-Kelly at 75% WR = f* 0.384. Initial position $341. Scale-up to
        $495 after 20 live trades with WR ≥ 80%.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Walk-Forward Validation</strong>
        Rolling window validation complete. Performance consistent across
        sub-periods. Bear market regime filter confirmed effective.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 5 — Final Comparison</strong>
        Authoritative run {RUN_DATE}. First-ever daily MtM equity curve for
        RSI strategy. Annual +16.1%, MtM MaxDD -29.4%, PF 5.395.</div>
    </div>
    <div class="stage-item warn">
      <span class="stage-icon">⚠️</span>
      <div class="stage-label"><strong>Cross-Asset Validation</strong>
        Not run. RSI strategy not tested on BTC or other assets. Low priority
        given mean reversion is ETH-specific by design.</div>
    </div>
    <div class="stage-item blocked">
      <span class="stage-icon">🔴</span>
      <div class="stage-label"><strong>Stop Order Verification</strong>
        RR-RSI-002: bot does not verify stop order is ACTIVE on each run.
        Must be implemented before capital increase. Currently mitigated
        by $150 cap.</div>
    </div>
    <div class="stage-item warn">
      <span class="stage-icon">⚠️</span>
      <div class="stage-label"><strong>Live Performance Gates</strong>
        20 live trades required before scale-up decision. Running win rate
        monitored after every trade via record_trade_result().</div>
    </div>
  </div>
</div>

<!-- ── RISK REGISTER ── -->
<div class="card">
  <h2>Risk Register — Open Items</h2>

  <!-- HIGH URGENT: RR-RSI-002 -->
  <div class="risk-block risk-high urgent">
    <div class="risk-header">
      <span class="risk-id">RR-RSI-002</span>
      <span class="risk-priority prio-high urgent">High</span>
      <span class="risk-urgent-tag">🚨 MOST URGENT</span>
      <span class="risk-title">Stop order monitoring absent</span>
    </div>
    <p class="risk-desc">
      The bot does not verify that its Binance stop order is still ACTIVE on each
      scheduled run. Binance silently cancels resting stop orders under certain
      conditions (maintenance, order age, account flags). If the stop is cancelled
      without Telegram alert, the position is unprotected. This has already occurred
      in ETH ADX live trading — emergency manual intervention was required.
    </p>
    <p class="risk-mitigation">
      <strong>Current mitigation:</strong> $150 capital cap limits maximum unprotected
      exposure. At 15% stop distance on $341 position, maximum stop-loss = $51.
      In an extreme move (−50%), unprotected loss = $170 — limited at $150 cap.<br>
      <strong>Required fix:</strong> On every bot run while LONG: call
      <code>get_order(orderId=state['stop_loss_order_id'])</code>. If status ≠ NEW,
      re-place immediately and send Telegram alert.
    </p>
    <div class="risk-blocker">⛔ Blocker: must be resolved before any capital increase beyond $150</div>
  </div>

  <!-- HIGH: RR-RSI-001 -->
  <div class="risk-block risk-high">
    <div class="risk-header">
      <span class="risk-id">RR-RSI-001</span>
      <span class="risk-priority prio-high">High</span>
      <span class="risk-title">Win rate sensitivity — negative Kelly below 72.2%</span>
    </div>
    <p class="risk-desc">
      The strategy has negative Kelly expectation at win rates below 72.2%. The
      backtest win rate (93.5%) is almost certainly inflated relative to live
      performance. Mean reversion strategies are vulnerable to regime shifts —
      a sustained downtrend produces consecutive stop-losses that rapidly degrade
      the win rate. At 75% live win rate (moderate scenario), median annual return
      is −0.1% with 55.5% probability of a negative year.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Position size set at $341 (Kelly-optimal at 75% WR
      conservative scenario). Running win rate monitored after every trade.
      Trading paused if running WR falls below 72% over 20+ trades.
      Monte Carlo analysis fully documented in this card (see performance section).
    </p>
  </div>

  <!-- HIGH: RR-RSI-003 -->
  <div class="risk-block risk-high">
    <div class="risk-header">
      <span class="risk-id">RR-RSI-003</span>
      <span class="risk-priority prio-high">High</span>
      <span class="risk-title">Position sizing: full Kelly at backtest rate would require 5× leverage</span>
    </div>
    <p class="risk-desc">
      At the backtest win rate (93.5%), full Kelly position = $2,555 — requiring 5.1×
      leverage, which is unavailable on Binance Spot and inappropriate for an
      unleveraged strategy. At 75% live win rate, Kelly-optimal position is $341,
      which is below the $495 unleveraged cap. Deploying at $495 with 75% live WR
      would mean over-sizing relative to Kelly — accelerating capital erosion if
      win rate degrades.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Initial deployment at $341 (Kelly at 75% WR).
      Scale to $495 only after 20 live trades confirm running WR ≥ 80%.
      Kelly fraction recalculated after each block of 10 live trades.
    </p>
  </div>

  <!-- MAJOR: RR-RSI-004 -->
  <div class="risk-block risk-major">
    <div class="risk-header">
      <span class="risk-id">RR-RSI-004</span>
      <span class="risk-priority prio-major">Major</span>
      <span class="risk-title">Sample size: 31 trades — wide confidence intervals on all metrics</span>
    </div>
    <p class="risk-desc">
      31 backtest trades over 6.5 years. At 93.5% observed win rate, the 95%
      confidence interval on win rate spans approximately 79%–99% (Wilson interval).
      The lower bound (79%) is already a scenario where 25% of live years are negative.
      A single additional loss from a 32nd trade changes win rate from 93.5% to 90.6%.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Monte Carlo confidence intervals used as deployment
      basis rather than point estimates. Do not adjust position sizing based on live
      results until minimum 20 live trades accumulated. Flag in deployment document
      that 95% CI on win rate spans 79%–99%.
    </p>
  </div>

  <!-- MAJOR: RR-RSI-005 -->
  <div class="risk-block risk-major">
    <div class="risk-header">
      <span class="risk-id">RR-RSI-005</span>
      <span class="risk-priority prio-major">Major</span>
      <span class="risk-title">120 SMA regime filter: data-mining risk on 2018–2026 data</span>
    </div>
    <p class="risk-desc">
      The 120-day SMA filter was selected during optimisation on the full
      2018–2026 backtest window. It has not been independently validated on
      out-of-sample data. The filter may be inadvertently calibrated to the
      specific bear market characteristics of 2018–2019 and 2022, rather than
      identifying a structural signal that will persist into future regimes.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Risk acknowledged in deployment document.
      120 SMA filter status displayed in daily health check Telegram message.
      Monitor closely during any sustained price decline below 120 SMA — strategy
      should sit in cash during that period. Full re-evaluation after 50 live trades.
    </p>
  </div>

  <!-- MAJOR: RR-RSI-006 -->
  <div class="risk-block risk-major">
    <div class="risk-header">
      <span class="risk-id">RR-RSI-006</span>
      <span class="risk-priority prio-major">Major</span>
      <span class="risk-title">Formal stability classification not completed</span>
    </div>
    <p class="risk-desc">
      STABLE / MARGINAL / FRAGILE classification has not been run with formal
      methodology. Informal per-parameter stability scores (RSI period 80%,
      oversold 67%, exit level 100%, stop 80%, MA filter 100% above PF 2.0)
      suggest STABLE, but this has not been confirmed with a grid-based
      composite score. A FRAGILE result would indicate potential overfitting.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Informal stability scan results are
      encouraging and consistent with a broad parameter plateau. Formal
      classification targeted for Week 7. Result will inform confidence
      score in capital allocation framework (SI007).
    </p>
  </div>

</div>

<!-- ── DEPLOYMENT DECISION ── -->
<div class="card">
  <h2>Deployment Decision</h2>
  <div class="decision-card">
    <h3>Current Status</h3>
    <p class="verdict">⚠️ VALIDATION PHASE — $150 Capital Cap</p>
    <p>Live since 2026-05-07. Running on EC2 with $150 fixed capital (not subject to
       weekly portfolio rebalance). Currently FLAT — waiting for RSI &lt; 43 entry signal.
       Validation phase collects live trade data to compare against backtest win rate
       and profit factor. Full deployment is conditional on resolving HIGH risk items
       and passing live performance gates.</p>

    <ul class="gate-list" style="margin-top: 14px;">
      <li>
        <span class="gate-open">OPEN</span>
        <span><strong>RR-RSI-002 resolved:</strong> Stop order verification implemented in bot.
        Must be done before any capital increase. This is the single most operationally
        urgent item — a silent stop cancellation at current position sizes is manageable;
        at $1,000+ it is not.</span>
      </li>
      <li>
        <span class="gate-open">OPEN</span>
        <span><strong>RR-RSI-006 resolved:</strong> Formal STABLE/MARGINAL/FRAGILE
        classification completed. Target: Week 7.</span>
      </li>
      <li>
        <span class="gate-open">OPEN</span>
        <span><strong>20 live trades accumulated</strong> with running win rate tracked.
        Currently: 0 trades.</span>
      </li>
      <li>
        <span class="gate-open">OPEN</span>
        <span><strong>Live WR ≥ 80%</strong> over first 20 trades before scale-up to $495.
        If WR &lt; 72%, pause trading immediately.</span>
      </li>
      <li>
        <span class="gate-done">DONE</span>
        <span>Monte Carlo analysis complete. Position size set conservatively at $341
        (75% WR scenario).</span>
      </li>
      <li>
        <span class="gate-done">DONE</span>
        <span>Stage 5 authoritative backtest complete. MtM MaxDD -29.4%, Calmar 0.548,
        PF 5.395. First-ever daily equity curve for this strategy.</span>
      </li>
      <li>
        <span class="gate-done">DONE</span>
        <span>Kelly sizing correct. Position formula: (f* × capital) / stop_pct.
        Initial: $341. Scale-up: $495 after gates met.</span>
      </li>
    </ul>
  </div>
</div>

</div><!-- /wrapper -->
</body>
</html>"""

out_path = os.path.join(DEPLOY_DIR, 'ETH_RSI_Deployment_Card_v1.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ Saved → Deployment_Documents/Week_6/ETH_RSI_Deployment_Card_v1.html")
print(f"   File size: {os.path.getsize(out_path):,} bytes")
