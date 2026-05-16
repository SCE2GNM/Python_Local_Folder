#!/usr/bin/env python3
"""
Build ETH ADX Deployment Card v1
Output: Deployment_Documents/Week_6/ETH_ADX_Deployment_Card_v1.html

Self-contained: re-runs the ADX backtest (same logic as stage5_final_comparison.py)
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
from ta.trend import ADXIndicator

warnings.filterwarnings('ignore')

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR  = os.path.join(SCRIPT_DIR, '..', 'Deployment_Documents', 'Week_6')
os.makedirs(DEPLOY_DIR, exist_ok=True)

RUN_DATE = _date.today().strftime('%Y-%m-%d')

# ── Strategy constants (match deployed bot exactly) ──────────────────────────
ADX_WIN   = 9
ADX_THR   = 19
TRAIL_PCT = 0.08
COSTS     = 0.0015

# ── Stage 5 authoritative metrics (from stage5_final_comparison.csv) ─────────
M = {
    'annual_ret':   0.7971,
    'total_ret':    133.48,
    'mtm_maxdd':   -0.3690,
    'calmar':       2.160,
    'sharpe':       1.425,
    'sortino':      1.761,
    'n_trades':     159,
    'win_rate':     0.4151,
    'avg_win':      0.1614,
    'avg_loss':    -0.0450,
    'pf':           2.546,
    'stop_exit':    0.6101,
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

print("Computing ADX signals...")
_ind     = ADXIndicator(df['High'], df['Low'], df['Close'], window=ADX_WIN, fillna=False)
adx_sig  = (_ind.adx().values >= ADX_THR) & (_ind.adx_pos().values > _ind.adx_neg().values)

print("Running ADX backtest...")
pos = 0; ep = peak = stop = 0.0; entry_date = None
trades = []
for i in range(1, N):
    lo = lows[i]; cl = closes[i]
    if pos == 1:
        if lo <= stop:
            trades.append({'entry_date': entry_date, 'exit_date': dates[i],
                           'entry_price': ep, 'exit_price': stop,
                           'return': (stop - ep) / ep})
            pos = 0; entry_date = None
        elif not adx_sig[i]:
            trades.append({'entry_date': entry_date, 'exit_date': dates[i],
                           'entry_price': ep, 'exit_price': cl,
                           'return': (cl - ep) / ep})
            pos = 0; entry_date = None
        else:
            if cl > peak:
                peak = cl; stop = peak * (1 - TRAIL_PCT)
    elif adx_sig[i]:
        ep = cl; peak = cl; stop = cl * (1 - TRAIL_PCT)
        entry_date = dates[i]; pos = 1

print(f"  {len(trades)} trades")

print("Building equity curve...")
n         = len(df)
arr       = closes.copy()
date_to_i = pd.Series(np.arange(n), index=df.index)
equity    = np.ones(n)
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

bh_eq      = closes / closes[0]
date_list  = [d.strftime('%Y-%m-%d') for d in dates]

# Year-by-year returns
def yr_rets(eq):
    res = {}
    for yr in sorted(set(d.year for d in dates)):
        idx = [i for i, d in enumerate(dates) if d.year == yr]
        if idx: res[yr] = eq[idx[-1]] / eq[idx[0]] - 1
    return res

adx_yr = yr_rets(equity)
bh_yr  = yr_rets(bh_eq)
all_years = sorted(adx_yr)


# ─────────────────────────────────────────────────────────────────────────────
# 2. PLOTLY EQUITY CHART
# ─────────────────────────────────────────────────────────────────────────────

C_ADX = '#1565C0'
C_BH  = '#9E9E9E'

fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True,
    row_heights=[0.68, 0.32], vertical_spacing=0.05,
    subplot_titles=('Equity Curve (log scale, $1 start, 0.15% round-trip costs)',
                    'Drawdown from Peak'),
)

fig.add_trace(go.Scatter(
    x=date_list, y=equity.tolist(), name='ETH ADX 19/9 (8% trail)',
    line=dict(color=C_ADX, width=2),
    hovertemplate='%{x}<br>Equity: %{y:.3f}×<extra>ETH ADX</extra>',
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=date_list, y=bh_eq.tolist(), name='Buy & Hold ETH',
    line=dict(color=C_BH, width=1.5, dash='dot'),
    hovertemplate='%{x}<br>Equity: %{y:.3f}×<extra>B&H ETH</extra>',
), row=1, col=1)

adx_peak = np.maximum.accumulate(equity)
adx_dd   = (equity - adx_peak) / adx_peak
bh_peak  = np.maximum.accumulate(bh_eq)
bh_dd    = (bh_eq - bh_peak) / bh_peak

fig.add_trace(go.Scatter(
    x=date_list, y=(adx_dd * 100).tolist(), name='ADX DD',
    line=dict(color=C_ADX, width=1.4), showlegend=False,
    fill='tozeroy', fillcolor='rgba(21,101,192,0.08)',
    hovertemplate='%{x}<br>DD: %{y:.1f}%<extra>ETH ADX</extra>',
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=date_list, y=(bh_dd * 100).tolist(), name='B&H DD',
    line=dict(color=C_BH, width=1.2, dash='dot'), showlegend=False,
    hovertemplate='%{x}<br>DD: %{y:.1f}%<extra>B&H ETH</extra>',
), row=2, col=1)

fig.update_yaxes(type='log', tickformat='.1f', title_text='Equity (×)', row=1, col=1)
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

yr_adx_cells = "".join(
    f"<td class='{'pos' if adx_yr.get(yr,0)>0 else 'neg'}'>{adx_yr.get(yr,0)*100:+.1f}%</td>"
    for yr in all_years
)
yr_bh_cells = "".join(
    f"<td class='{'pos' if bh_yr.get(yr,0)>0 else 'neg'}'>{bh_yr.get(yr,0)*100:+.1f}%</td>"
    for yr in all_years
)
yr_headers = "".join(f"<th>{yr}</th>" for yr in all_years)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ETH ADX — Deployment Card v1</title>
  <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #ECEFF1; color: #212121; margin: 0; padding: 0; font-size: 14px; }}

    /* ── Header ── */
    .header {{ background: linear-gradient(135deg, #0D47A1 0%, #1565C0 60%, #1976D2 100%);
               color: #fff; padding: 28px 32px 24px; }}
    .header h1 {{ margin: 0 0 6px; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.3px; }}
    .header .sub {{ font-size: 0.88rem; opacity: 0.85; margin: 0; }}
    .status-badge {{ display: inline-block; background: #4CAF50; color: #fff;
                     font-size: 0.75rem; font-weight: 700; padding: 4px 10px;
                     border-radius: 12px; letter-spacing: 0.5px; margin-top: 10px; }}
    .status-badge.pending {{ background: #FF9800; }}

    /* ── Layout ── */
    .wrapper {{ max-width: 1100px; margin: 0 auto; padding: 24px 20px 48px; }}
    .card {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.10);
             padding: 22px 24px; margin-bottom: 20px; }}
    .card h2 {{ font-size: 1rem; font-weight: 700; color: #0D47A1; margin: 0 0 14px;
                border-bottom: 2px solid #E3F2FD; padding-bottom: 8px;
                text-transform: uppercase; letter-spacing: 0.4px; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    @media(max-width: 700px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

    /* ── Tables ── */
    table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
    thead th {{ background: #1565C0; color: #fff; padding: 8px 11px; text-align: center;
                font-weight: 600; white-space: nowrap; }}
    thead th:first-child {{ text-align: left; }}
    tbody tr:nth-child(even) {{ background: #F5F5F5; }}
    tbody td {{ padding: 7px 11px; border-bottom: 1px solid #EEEEEE; text-align: center; }}
    tbody td:first-child {{ text-align: left; font-weight: 500; }}
    .highlight-row td {{ background: #E3F2FD !important; font-weight: 600; color: #0D47A1; }}
    .bh-row td {{ color: #757575; }}
    td.pos {{ color: #2E7D32; font-weight: 600; }}
    td.neg {{ color: #C62828; font-weight: 600; }}

    /* ── Params table ── */
    .param-table td:first-child {{ color: #555; width: 52%; }}
    .param-table td:last-child {{ font-weight: 600; font-family: 'SF Mono', monospace; font-size: 0.82rem; }}

    /* ── Validation checklist ── */
    .stage-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }}
    .stage-item {{ display: flex; align-items: flex-start; gap: 8px; padding: 8px 10px;
                   border-radius: 6px; background: #F1F8E9; border: 1px solid #C5E1A5; }}
    .stage-item.warn {{ background: #FFF8E1; border-color: #FFE082; }}
    .stage-icon {{ font-size: 1rem; flex-shrink: 0; line-height: 1.4; }}
    .stage-label {{ font-size: 0.78rem; color: #333; line-height: 1.4; }}
    .stage-label strong {{ display: block; font-size: 0.80rem; color: #1B5E20; }}
    .stage-item.warn .stage-label strong {{ color: #E65100; }}

    /* ── Risk register ── */
    .risk-block {{ border-radius: 6px; padding: 14px 16px; margin-bottom: 12px;
                   border-left: 4px solid; }}
    .risk-high {{ background: #FFF3E0; border-color: #E65100; }}
    .risk-medium {{ background: #FFFDE7; border-color: #F9A825; }}
    .risk-block .risk-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
    .risk-id {{ font-family: monospace; font-weight: 700; font-size: 0.82rem;
                background: rgba(0,0,0,0.07); padding: 2px 7px; border-radius: 4px; }}
    .risk-priority {{ font-size: 0.70rem; font-weight: 700; padding: 2px 7px;
                      border-radius: 10px; text-transform: uppercase; letter-spacing: 0.4px; }}
    .prio-high {{ background: #E65100; color: #fff; }}
    .prio-medium {{ background: #F9A825; color: #fff; }}
    .risk-title {{ font-weight: 600; font-size: 0.86rem; }}
    .risk-desc {{ font-size: 0.82rem; color: #444; margin: 4px 0 6px; line-height: 1.5; }}
    .risk-mitigation {{ font-size: 0.80rem; color: #555; }}
    .risk-mitigation strong {{ color: #333; }}

    /* ── Decision banner ── */
    .decision-row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
    .decision-card {{ flex: 1; min-width: 220px; border-radius: 8px; padding: 16px 20px; }}
    .decision-go {{ background: #E8F5E9; border: 2px solid #4CAF50; }}
    .decision-pending {{ background: #FFF8E1; border: 2px solid #FF9800; }}
    .decision-card h3 {{ margin: 0 0 8px; font-size: 0.9rem; text-transform: uppercase;
                         letter-spacing: 0.5px; }}
    .decision-go h3 {{ color: #2E7D32; }}
    .decision-pending h3 {{ color: #E65100; }}
    .decision-card p {{ margin: 4px 0; font-size: 0.82rem; color: #444; line-height: 1.5; }}
    .decision-card .verdict {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; }}
    .decision-go .verdict {{ color: #1B5E20; }}
    .decision-pending .verdict {{ color: #BF360C; }}

    /* ── Methodology note ── */
    .methodology {{ font-size: 0.77rem; color: #666; background: #F5F5F5;
                    border-left: 3px solid #1565C0; padding: 9px 13px;
                    border-radius: 0 4px 4px 0; margin-top: 10px; line-height: 1.6; }}

    /* ── Overview text ── */
    .overview-text {{ font-size: 0.84rem; line-height: 1.7; color: #333; }}
    .overview-text h3 {{ font-size: 0.82rem; font-weight: 700; color: #0D47A1;
                         margin: 12px 0 4px; text-transform: uppercase; letter-spacing: 0.3px; }}

    /* ── Live config ── */
    .live-config {{ background: #E3F2FD; border-radius: 6px; padding: 14px 16px; }}
    .live-config table {{ font-size: 0.82rem; }}
    .live-config td {{ padding: 5px 8px; border-bottom: 1px solid rgba(0,0,0,0.06); }}
    .live-config td:first-child {{ color: #555; width: 48%; }}
    .live-config td:last-child {{ font-weight: 600; font-family: monospace; }}

    .section-note {{ font-size: 0.78rem; color: #888; margin-top: 8px; }}
  </style>
</head>
<body>

<!-- ── HEADER ── -->
<div class="header">
  <h1>ETH ADX — Deployment Card</h1>
  <p class="sub">ETH/USDT · Binance Spot · Strategy ID: eth_adx · v1.0</p>
  <div>
    <span class="status-badge">● LIVE — Full Deployment ($1,000 capital)</span>
    <span class="status-badge pending" style="margin-left:8px">⚠ Leverage Upgrade Pending</span>
  </div>
</div>

<div class="wrapper">

<!-- ── OVERVIEW + LIVE CONFIG ── -->
<div class="card">
  <h2>Strategy Overview</h2>
  <div class="two-col">
    <div class="overview-text">
      <h3>What it does</h3>
      <p>Trend-following strategy on ETH/USDT daily candles. Enters long when ETH is in a
         confirmed directional trend, rides the trend with a trailing stop that locks in gains
         as price rises, and exits automatically when trend strength fades or the trailing
         stop is triggered.</p>

      <h3>Entry condition</h3>
      <p>ADX(9) ≥ 19 <strong>AND</strong> DI+ > DI−. Both conditions must hold at the
         daily close. ADX measures trend strength (above 19 = strong trend); DI+/DI−
         comparison confirms the trend is upward.</p>

      <h3>Exit conditions</h3>
      <p><strong>Trail stop:</strong> stop price = peak_close × (1 − 8%). Ratchets upward
         as each daily close sets a new peak. Stop never moves down. Checked against daily
         LOW before the close — so a gap-down day exits at the stop price (conservative).<br>
         <strong>Signal exit:</strong> if ADX drops below 19 or DI+ crosses below DI−,
         exit at next close regardless of stop distance.</p>

      <h3>Why it works</h3>
      <p>ADX isolates periods of genuine directional strength, filtering out sideways chop
         that generates false entries. The 8% trailing stop allows trades to breathe through
         normal volatility while automatically capturing a large fraction of each trending
         move. 61% of exits are stop-triggered (trend exhaustion), 39% are signal-triggered
         (ADX fade) — both are intentional exit paths.</p>
    </div>

    <div>
      <div class="live-config">
        <table>
          <tbody>
            <tr><td>Status</td><td>LIVE</td></tr>
            <tr><td>Asset</td><td>ETHUSDT (Spot)</td></tr>
            <tr><td>Exchange</td><td>Binance</td></tr>
            <tr><td>Capital allocated</td><td>$1,000</td></tr>
            <tr><td>Current position</td><td>LONG 0.419 ETH</td></tr>
            <tr><td>Entry price</td><td>$2,368.52 (blended)</td></tr>
            <tr><td>Stop order</td><td>STOP_LOSS (market)</td></tr>
            <tr><td>Live since</td><td>2026-04-04</td></tr>
            <tr><td>Trailing stop live</td><td>2026-05-13</td></tr>
            <tr><td>Bot file</td><td>day5_production_bot.py</td></tr>
            <tr><td>Schedule</td><td>4× daily (00:05, 06:05, 12:05, 18:05 UTC)</td></tr>
            <tr><td>Kelly fraction</td><td>8% (TRAIL_PCT = risk fraction)</td></tr>
            <tr><td>Leverage</td><td>1× (unleveraged) — 1.9× pending</td></tr>
          </tbody>
        </table>
      </div>
      <p class="section-note" style="margin-top:8px">
        Bot runs every 6 hours on EC2 (ap-southeast-2). Health check Telegram message
        sent every run. Stop order verified ACTIVE on every run while LONG.
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
          <tr><td>ADX window (period)</td><td>9</td></tr>
          <tr><td>ADX threshold</td><td>19</td></tr>
          <tr><td>DI confirmation</td><td>DI+ > DI− required</td></tr>
          <tr><td>Trailing stop %</td><td>8% from peak close</td></tr>
          <tr><td>Peak update method</td><td>Daily close (conservative)</td></tr>
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
          <tr><td>Min improvement to move stop</td><td>0.25%</td></tr>
          <tr><td>Position size formula</td><td>(Kelly% × capital) / TRAIL_PCT</td></tr>
          <tr><td>Max position size</td><td>balance − $5 (fee buffer)</td></tr>
          <tr><td>Stop verification</td><td>Every bot run while LONG</td></tr>
          <tr><td>Telegram alerts</td><td>Entry / Exit / Stop verified / Health check</td></tr>
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
        <td>ETH ADX 19/9 (8% trail)</td>
        <td>+79.7%</td>
        <td>+13,348%</td>
        <td>-36.9%</td>
        <td>2.160</td>
        <td>1.425</td>
        <td>1.761</td>
        <td>159</td>
        <td>41.5%</td>
        <td>+16.1%</td>
        <td>-4.5%</td>
        <td>2.546</td>
        <td>61.0%</td>
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

  <div class="methodology">
    <strong>Methodology:</strong> Daily mark-to-market equity curve · Stop checked vs daily LOW
    · ADX peak updated on close (conservative — live bot checks 4× daily vs live price)
    · Costs 0.15% round-trip deducted at exit · Sharpe / Sortino / Calmar derived from
    daily equity curve, annualised × √365 · Data: {DATA_START} → {DATA_END} ({YEARS:.1f} yrs)
    · Run: {RUN_DATE}
  </div>

  <div style="margin-top: 18px;">
    <table>
      <thead>
        <tr><th>Year-by-Year</th>{yr_headers}</tr>
      </thead>
      <tbody>
        <tr class="highlight-row"><td>ETH ADX 19/9</td>{yr_adx_cells}</tr>
        <tr class="bh-row"><td>B&amp;H ETH</td>{yr_bh_cells}</tr>
      </tbody>
    </table>
  </div>
</div>

<!-- ── EQUITY CURVE ── -->
<div class="card">
  <h2>Equity Curve</h2>
  {chart_html}
  <p class="section-note">Log scale. $1 start. Blue = ETH ADX 19/9 (8% trail, 0.15% costs).
     Grey dotted = Buy &amp; Hold ETH (no costs). Shaded area = strategy drawdown.</p>
</div>

<!-- ── VALIDATION PIPELINE ── -->
<div class="card">
  <h2>Validation Pipeline Status</h2>
  <div class="stage-grid">
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 1a — Pct Trail Grid</strong>
        ADX 19/9 + 8% trail confirmed best. Calmar 2.160. 728 combos tested.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 1b — ATR Trail Grid</strong>
        ATR 9/2.5× tested. Pct 8% wins on annual return (+79.7% vs +73.4%).</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 1c — Stability</strong>
        5/6 walk-forward years positive. Parameters confirmed stable.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 1d — Final Comparison</strong>
        Pct 8% selected over ATR. Decision: ADX 19/9 + pct 8% primary path.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 2a — Composite Analysis</strong>
        Full parameter surface mapped. Plateau confirmed around ADX 19/9.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 2b — Extended Run</strong>
        Full run with corrected methodology. Consistent with 2a findings.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 2c — Stability Heatmap</strong>
        Heatmap of Calmar by parameter. Plateau centred on selected params.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 2d — Walk-Forward v2</strong>
        Rolling window validation. 2022 tested — strategy outperforms B&H.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 2e — ETH Cross-Asset</strong>
        Validated on BTC: Sortino 0.794, Calmar 1.069. PARTIAL (Sortino borderline).</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 3 — Leverage Analysis</strong>
        1.9× selected. Ann +121.7% vs +79.7% unleveraged. Interest cost negligible.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 3b — Leverage Stability</strong>
        Stable performance 1.0×–2.5×. Degradation onset above 2.5×.</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 3c — Rate Sensitivity</strong>
        Low sensitivity to interest rate assumptions at 1.9×.</div>
    </div>
    <div class="stage-item warn">
      <span class="stage-icon">⚠️</span>
      <div class="stage-label"><strong>Stage 4 — Leverage Optimisation</strong>
        1.9× provisionally selected. Formal grid search with trailing stop pending (A013).</div>
    </div>
    <div class="stage-item">
      <span class="stage-icon">✅</span>
      <div class="stage-label"><strong>Stage 5 — Final Comparison</strong>
        Authoritative run {RUN_DATE}. Resolves 74.89% vs 80.1% discrepancy. Annual +79.7%.</div>
    </div>
  </div>
</div>

<!-- ── RISK REGISTER ── -->
<div class="card">
  <h2>Risk Register — Open Items</h2>

  <!-- HIGH: A013 -->
  <div class="risk-block risk-high">
    <div class="risk-header">
      <span class="risk-id">A013</span>
      <span class="risk-priority prio-high">High</span>
      <span class="risk-title">Margin leverage not yet optimised for ETH ADX</span>
    </div>
    <p class="risk-desc">
      1.9× leverage was selected from preliminary analysis (fixed stop baseline).
      A formal leverage grid search using the percentage trailing stop (8%) as the
      base strategy has not been run. Optimal leverage level under current stop
      configuration is unconfirmed.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Current deployment is unleveraged (1×) — no leverage
      risk while A013 is open. 1.9× is the planned upgrade target only.
      <strong>Blocker for:</strong> leveraged deployment.
    </p>
  </div>

  <!-- HIGH: A016 -->
  <div class="risk-block risk-high">
    <div class="risk-header">
      <span class="risk-id">A016</span>
      <span class="risk-priority prio-high">High — Accepted</span>
      <span class="risk-title">Tail liquidation risk at 1.9× leverage in extreme crash events</span>
    </div>
    <p class="risk-desc">
      At 1.9× leverage, if the position is at the worst historical margin ratio
      (34.4%) and a −42.9% single-day drop occurs simultaneously, the position
      is liquidated before the trailing stop fires. This requires two extreme
      conditions at once (low probability, non-zero). Relevant only to the
      leveraged deployment — not applicable at current 1× operation.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Trailing stop historically exits before worst intraday
      lows across 8+ years of backtest. Margin ratio Telegram alert at 40% MR provides
      early warning. Accepted with mitigations documented before leveraged deployment.
      <strong>Blocker for:</strong> leveraged deployment only.
    </p>
  </div>

  <!-- MEDIUM: A010 -->
  <div class="risk-block risk-medium">
    <div class="risk-header">
      <span class="risk-id">A010</span>
      <span class="risk-priority prio-medium">Medium</span>
      <span class="risk-title">Daily loss limit not calibrated for daily candle strategies</span>
    </div>
    <p class="risk-desc">
      2% daily loss limit was set from intraday norms. Backtesting showed it fires
      on normal ETH volatility, reducing annual return from 67.4% to 8.8% when
      active. May remain in live bot code, causing unnecessary exits on valid positions.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Remove or raise daily loss limit to 8–10% in live bot.
      Per-trade trailing stop provides sufficient protection at 8% distance.
    </p>
  </div>

  <!-- MEDIUM: A014 -->
  <div class="risk-block risk-medium">
    <div class="risk-header">
      <span class="risk-id">A014</span>
      <span class="risk-priority prio-medium">Medium</span>
      <span class="risk-title">RiskManager guardrails not calibrated for daily candle strategy</span>
    </div>
    <p class="risk-desc">
      Guardrails (daily loss limit, max drawdown threshold, stop distance) were set
      from professional intraday norms, not backtested against the trailing stop
      configuration. May create suboptimal exits that introduce drift vs backtest.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> After 20+ live trades, run joint optimisation of
      ATR multiplier vs max drawdown guardrail. Target: Week 7.
    </p>
  </div>

  <!-- MEDIUM: A015 -->
  <div class="risk-block risk-medium">
    <div class="risk-header">
      <span class="risk-id">A015</span>
      <span class="risk-priority prio-medium">Medium</span>
      <span class="risk-title">ADX 19/9 + 8% trail deployed simultaneously — attribution harder</span>
    </div>
    <p class="risk-desc">
      Two changes deployed at once: ADX parameters (20/10 → 19/9) and stop type
      (fixed 5% → trailing 8%). If live performance deviates from backtest, root
      cause attribution (which change?) requires careful analysis.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Decision documented in A015 with full rationale.
      Primary path selected: pct 8% wins on annual return (+79.7% vs +73.4%) and
      Sortino (1.761 vs 1.423). Review after 20 live trades.
    </p>
  </div>

  <!-- MEDIUM: A009 -->
  <div class="risk-block risk-medium">
    <div class="risk-header">
      <span class="risk-id">A009</span>
      <span class="risk-priority prio-medium">Medium</span>
      <span class="risk-title">Walk-forward validation used fixed parameters, not rolling re-optimisation</span>
    </div>
    <p class="risk-desc">
      Stage 1c tested the selected parameter set across rolling 1-year windows but
      did not re-optimise parameters per window. Less rigorous than true walk-forward.
      Low signal frequency (15–20 trades/year) makes true walk-forward impractical
      with current data length.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Live performance data is the primary validation
      path. Results supported robustness (5/6 years positive). Accepted at this
      validation stage. Review after 3+ years of live data.
    </p>
  </div>

  <!-- MEDIUM: A003 -->
  <div class="risk-block risk-medium">
    <div class="risk-header">
      <span class="risk-id">A003</span>
      <span class="risk-priority prio-medium">Medium</span>
      <span class="risk-title">Slippage modelled as flat cost, not variable</span>
    </div>
    <p class="risk-desc">
      Costs modelled at flat 0.15% round-trip. Does not model variable slippage on
      stop exits during low-liquidity periods (weekends, off-hours). Real fills may
      be 0.1–0.5% worse in adverse conditions.
    </p>
    <p class="risk-mitigation">
      <strong>Mitigation:</strong> Immaterial at current position sizes (~$1,000 per trade
      — extra slippage ≤ $5). Monitor actual fill prices vs stop prices in live data.
      Target: flag if consistent slippage &gt;0.3% observed over 10+ live trades.
    </p>
  </div>

</div>

<!-- ── DEPLOYMENT DECISION ── -->
<div class="card">
  <h2>Deployment Decision</h2>
  <div class="decision-row">
    <div class="decision-card decision-go">
      <h3>Unleveraged (1×) — $1,000</h3>
      <p class="verdict">✅ GO — Live since 2026-04-04</p>
      <p>Trailing stop (8%) deployed 2026-05-13. All critical execution bugs resolved
         (A017: stop order type, A018: silent failures, A019: Kelly sizing, A020: trailing
         stop baseline). Position: LONG 0.419 ETH @ $2,368.52 blended entry.</p>
      <p style="margin-top:8px"><strong>Conditions met:</strong> Backtest methodology
         corrected · Position sizing correct · Stop order verified · Telegram monitoring
         live · EC2 deployment confirmed.</p>
    </div>
    <div class="decision-card decision-pending">
      <h3>Leveraged (1.9×) — $1,500 target</h3>
      <p class="verdict">⚠️ PENDING — Awaiting A013</p>
      <p>1.9× leverage selected from preliminary analysis. Deployment blocked until
         A013 (leverage grid search with trailing stop baseline) is resolved.
         A016 (tail liquidation risk) accepted with mitigations — not a blocker.</p>
      <p style="margin-top:8px"><strong>Blockers:</strong> A013 (formal leverage optimisation)
         · A010 (daily loss limit recalibration) · Margin ratio alert (40% MR) must be
         added to bot before leveraged deployment.</p>
    </div>
  </div>
</div>

</div><!-- /wrapper -->
</body>
</html>"""

out_path = os.path.join(DEPLOY_DIR, 'ETH_ADX_Deployment_Card_v1.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ Saved → Deployment_Documents/Week_6/ETH_ADX_Deployment_Card_v1.html")
print(f"   File size: {os.path.getsize(out_path):,} bytes")
