#!/usr/bin/env python3
"""
Stage 5 — Final Strategy Comparison (Authoritative Run)
ETH ADX 19/9 (8% pct trail) vs ETH RSI 14/43/48/15%/120MA vs Buy & Hold

Resolves the ADX 74.89% (stage3a) vs 80.1% (earlier HTML) discrepancy with a
single clean run using consistent methodology throughout.

Methodology (non-negotiable):
  - Daily mark-to-market equity curve (not per-trade compounding)
  - Stop checked against daily LOW before close/signal checks each bar
  - ADX peak updated on CLOSE (conservative; live bot checks 4× daily vs ticker)
  - Costs: 0.15% round-trip per trade (0.075% taker × 2 legs)
  - Sharpe / Sortino / Calmar: all derived from daily equity curve
  - Entry: at close of signal bar (same-day execution)
  - ADX parameters: window=9, threshold=19 (deployed bot ADX_PERIOD=9, ADX_THRESHOLD=19)
  - RSI parameters: period=14, entry<43, exit>48, stop=15%, SMA=120

Outputs:
  results/stage5_final_comparison.csv
  ../Deployment_Documents/Week_6/week6_stage5_final_comparison_v2.html
"""

import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.trend import ADXIndicator

warnings.filterwarnings('ignore')

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DEPLOY_DIR  = os.path.join(SCRIPT_DIR, '..', 'Deployment_Documents', 'Week_6')
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(DEPLOY_DIR, exist_ok=True)

# ── Strategy constants (match deployed bots exactly) ─────────────────────────
COSTS     = 0.0015   # 0.15% round-trip
ADX_WIN   = 9        # ADXIndicator window (deployed: ADX_PERIOD=9)
ADX_THR   = 19       # ADX signal threshold (deployed: ADX_THRESHOLD=19)
TRAIL_PCT = 0.08     # ADX trailing stop % (deployed: TRAIL_PCT=0.08)
RSI_PER   = 14       # RSI period (Wilder's smoothing)
RSI_ENTRY = 43       # Entry when RSI < this (deployed: ENTRY_RSI=43)
RSI_EXIT  = 48       # Exit when RSI > this (deployed: EXIT_RSI=48)
STOP_PCT  = 0.15     # RSI hard stop below entry (deployed: STOP_PCT=0.15)
SMA_WIN   = 120      # RSI bull regime filter (deployed: SMA_PERIOD=120)
MIN_TRADES = 5


# ─────────────────────────────────────────────────────────────────────────────
# 1. FETCH DATA
# ─────────────────────────────────────────────────────────────────────────────

print("\nFetching ETH-USD daily data...")
raw = yf.download('ETH-USD', start='2018-01-01', auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)

df = raw[['High', 'Low', 'Close']].copy().dropna()
closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index
N      = len(df)
YEARS  = (dates[-1] - dates[0]).days / 365.25
print(f"Data: {dates[0].date()} → {dates[-1].date()}  ({YEARS:.2f} yrs, {N} bars)")


# ─────────────────────────────────────────────────────────────────────────────
# 2. INDICATORS
# ─────────────────────────────────────────────────────────────────────────────

# ADX 19/9 signals
print("Computing ADX 19/9 signals...")
_adx_ind  = ADXIndicator(df['High'], df['Low'], df['Close'], window=ADX_WIN, fillna=False)
adx_vals  = _adx_ind.adx().values
plus_di   = _adx_ind.adx_pos().values
minus_di  = _adx_ind.adx_neg().values
adx_sig   = (adx_vals >= ADX_THR) & (plus_di > minus_di)

# RSI 14 (Wilder's EWM)
print("Computing RSI 14 / 120 SMA signals...")

def calc_rsi(close_arr: np.ndarray, period: int) -> np.ndarray:
    s     = pd.Series(close_arr)
    delta = s.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_l = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, 1e-9)
    return (100 - 100 / (1 + rs)).values

rsi_vals       = calc_rsi(closes, RSI_PER)
sma_vals       = pd.Series(closes).rolling(SMA_WIN).mean().values
rsi_entry_sig  = (rsi_vals < RSI_ENTRY) & (closes > sma_vals)   # buy signal
rsi_exit_sig   = (rsi_vals > RSI_EXIT)                           # exit signal


# ─────────────────────────────────────────────────────────────────────────────
# 3. ADX BACKTEST — percentage trailing stop
# ─────────────────────────────────────────────────────────────────────────────

def run_adx_backtest(closes, lows, signals, dates, trail_pct):
    """
    Bar-by-bar ADX backtest with percentage trailing stop.
    Stop order of operations each bar:
      1. Check LOW against stop (gap protection — if gap-down below stop, stop wins)
      2. Check signal dropped (ADX_EXIT)
      3. If still long, update peak on close (conservative vs live 4× daily)
    Entry at close of signal bar.
    """
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

            elif not signals[i]:
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
                    stop = peak * (1 - trail_pct)

        elif signals[i]:
            ep   = cl
            peak = cl
            stop = cl * (1 - trail_pct)
            entry_date = dates[i]
            pos  = 1

    return trades


# ─────────────────────────────────────────────────────────────────────────────
# 4. RSI BACKTEST — hard fixed stop
# ─────────────────────────────────────────────────────────────────────────────

def run_rsi_backtest(closes, lows, entry_sigs, exit_sigs, dates, stop_pct):
    """
    Bar-by-bar RSI mean reversion backtest with fixed hard stop.
    Entry: RSI < 43 AND close > 120 SMA — at close of signal bar.
    Exit priority each bar:
      1. LOW <= stop_price → exit at stop (gap protection)
      2. RSI > 48 → exit at close
    Stop does not trail — fixed at entry_price * (1 - stop_pct).
    """
    pos = 0; ep = stop = 0.0; entry_date = None
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
                    'exit_reason': 'STOP_LOSS',
                })
                pos = 0; entry_date = None

            elif exit_sigs[i]:
                trades.append({
                    'entry_date':  entry_date,
                    'exit_date':   dates[i],
                    'entry_price': ep,
                    'exit_price':  cl,
                    'return':      (cl - ep) / ep,
                    'exit_reason': 'RSI_EXIT',
                })
                pos = 0; entry_date = None

        elif entry_sigs[i]:
            ep   = cl
            stop = cl * (1 - stop_pct)
            entry_date = dates[i]
            pos  = 1

    return trades


print("Running ADX backtest...")
adx_trades = run_adx_backtest(closes, lows, adx_sig, dates, TRAIL_PCT)
print(f"  → {len(adx_trades)} trades")

print("Running RSI backtest...")
rsi_trades = run_rsi_backtest(closes, lows, rsi_entry_sig, rsi_exit_sig, dates, STOP_PCT)
print(f"  → {len(rsi_trades)} trades")


# ─────────────────────────────────────────────────────────────────────────────
# 5. DAILY MARK-TO-MARKET EQUITY CURVES
# ─────────────────────────────────────────────────────────────────────────────

def build_equity_curve(trades: list, close_series: pd.Series) -> np.ndarray:
    """
    Mark-to-market daily equity curve (consistent with Week 5/6 method).
    Portfolio tracks daily close price during hold periods.
    Flat between trades — holds last compounded portfolio value.
    Cost deducted at exit (modifying final portfolio value for that trade).
    """
    n         = len(close_series)
    arr       = close_series.values.astype(float)
    date_to_i = pd.Series(np.arange(n), index=close_series.index)

    equity    = np.ones(n)
    portfolio = 1.0
    prev_i    = 0

    for t in trades:
        ei = date_to_i.get(pd.Timestamp(t['entry_date']))
        xi = date_to_i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None:
            continue
        equity[prev_i:ei]  = portfolio
        equity[ei:xi + 1]  = portfolio * arr[ei:xi + 1] / t['entry_price']
        portfolio          *= (1 + t['return'] - COSTS)
        equity[xi]          = portfolio
        prev_i              = xi + 1

    equity[prev_i:] = portfolio
    return equity


print("Building daily equity curves...")
adx_eq = build_equity_curve(adx_trades, df['Close'])
rsi_eq = build_equity_curve(rsi_trades, df['Close'])
bh_eq  = closes / closes[0]      # buy & hold — no costs, full period
print(f"  ADX final equity: {adx_eq[-1]:.3f}×  ({(adx_eq[-1]-1)*100:.1f}% total)")
print(f"  RSI final equity: {rsi_eq[-1]:.3f}×  ({(rsi_eq[-1]-1)*100:.1f}% total)")
print(f"  B&H final equity: {bh_eq[-1]:.3f}×  ({(bh_eq[-1]-1)*100:.1f}% total)")


# ─────────────────────────────────────────────────────────────────────────────
# 6. METRICS FROM DAILY EQUITY CURVE
# ─────────────────────────────────────────────────────────────────────────────

def calc_metrics_from_equity(equity: np.ndarray, trades: list, label: str) -> dict:
    dr       = np.diff(equity) / equity[:-1]
    mean_r   = dr.mean()
    std_r    = dr.std()
    downside = dr[dr < 0]

    sharpe  = mean_r / std_r * np.sqrt(365) if std_r > 0 else 0.0
    sortino = (mean_r / downside.std() * np.sqrt(365)
               if len(downside) > 0 and downside.std() > 0 else 0.0)

    peak       = np.maximum.accumulate(equity)
    dd         = (equity - peak) / peak
    mtm_max_dd = dd.min()

    total_ret  = equity[-1] - 1
    annual_ret = (1 + total_ret) ** (1 / YEARS) - 1
    calmar     = annual_ret / abs(mtm_max_dd) if mtm_max_dd != 0 else 0.0

    if trades:
        tdf         = pd.DataFrame(trades)
        net_rets    = tdf['return'].values - COSTS
        n_trades    = len(tdf)
        winners     = net_rets[net_rets > 0]
        losers      = net_rets[net_rets <= 0]
        win_rate    = len(winners) / n_trades
        avg_win     = winners.mean() if len(winners) > 0 else 0.0
        avg_loss    = losers.mean()  if len(losers)  > 0 else 0.0
        gp          = winners.sum()  if len(winners) > 0 else 0.0
        gl          = abs(losers.sum()) if len(losers) > 0 else 1e-9
        profit_factor = gp / gl
        stop_exits  = tdf['exit_reason'].isin(['TRAIL_STOP', 'STOP_LOSS']).sum()
        stop_pct_val = stop_exits / n_trades
    else:
        n_trades = win_rate = avg_win = avg_loss = profit_factor = stop_pct_val = 0

    return {
        'strategy':       label,
        'total_return':   total_ret,
        'annual_return':  annual_ret,
        'mtm_max_dd':     mtm_max_dd,
        'calmar':         calmar,
        'sharpe':         sharpe,
        'sortino':        sortino,
        'n_trades':       n_trades,
        'win_rate':       win_rate,
        'avg_win':        avg_win,
        'avg_loss':       avg_loss,
        'profit_factor':  profit_factor,
        'stop_exits_pct': stop_pct_val,
    }


adx_m = calc_metrics_from_equity(adx_eq, adx_trades, 'ETH ADX 19/9 (8% trail)')
rsi_m = calc_metrics_from_equity(rsi_eq, rsi_trades, 'ETH RSI 14/43/48 (15% stop)')

# B&H metrics (same equity-curve method)
bh_dr  = np.diff(bh_eq) / bh_eq[:-1]
bh_down = bh_dr[bh_dr < 0]
bh_peak = np.maximum.accumulate(bh_eq)
bh_dd   = (bh_eq - bh_peak) / bh_peak
bh_m = {
    'strategy':       'B&H ETH (no cost)',
    'total_return':   bh_eq[-1] - 1,
    'annual_return':  (bh_eq[-1]) ** (1 / YEARS) - 1,
    'mtm_max_dd':     bh_dd.min(),
    'calmar':         ((bh_eq[-1]) ** (1 / YEARS) - 1) / abs(bh_dd.min()),
    'sharpe':         bh_dr.mean() / bh_dr.std() * np.sqrt(365) if bh_dr.std() > 0 else 0.0,
    'sortino':        (bh_dr.mean() / bh_down.std() * np.sqrt(365)
                       if len(bh_down) > 0 and bh_down.std() > 0 else 0.0),
    'n_trades':       1,
    'win_rate':       1.0 if bh_eq[-1] > 1 else 0.0,
    'avg_win':        bh_eq[-1] - 1,
    'avg_loss':       0.0,
    'profit_factor':  float('inf') if bh_eq[-1] > 1 else 0.0,
    'stop_exits_pct': 0.0,
}

all_metrics = [adx_m, rsi_m, bh_m]

print("\n── Metrics Summary ──────────────────────────────────────────────────────────")
for m in all_metrics:
    print(f"  {m['strategy']}")
    print(f"    Annual: {m['annual_return']:+.1%}  |  MtM MaxDD: {m['mtm_max_dd']:.1%}  |  "
          f"Calmar: {m['calmar']:.3f}  |  Sharpe: {m['sharpe']:.3f}  |  Sortino: {m['sortino']:.3f}")
    if m['n_trades'] > 1:
        print(f"    Trades: {m['n_trades']}  |  WR: {m['win_rate']:.1%}  |  "
              f"PF: {m['profit_factor']:.3f}  |  StopExit%: {m['stop_exits_pct']:.1%}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. YEAR-BY-YEAR RETURNS
# ─────────────────────────────────────────────────────────────────────────────

def year_returns(equity: np.ndarray, dates: pd.DatetimeIndex) -> dict:
    """Calendar-year returns from the equity curve."""
    result = {}
    all_years = sorted(set(d.year for d in dates))
    for yr in all_years:
        idx = [i for i, d in enumerate(dates) if d.year == yr]
        if not idx:
            continue
        result[yr] = equity[idx[-1]] / equity[idx[0]] - 1
    return result

adx_yr = year_returns(adx_eq, dates)
rsi_yr = year_returns(rsi_eq, dates)
bh_yr  = year_returns(bh_eq,  dates)
all_years = sorted(set(adx_yr) | set(rsi_yr) | set(bh_yr))

print("\n── Year-by-Year Returns ─────────────────────────────────────────────────────")
print(f"  {'Year':<6} {'ADX':>8} {'RSI':>8} {'B&H':>8}")
for yr in all_years:
    print(f"  {yr:<6} {adx_yr.get(yr, 0):>+8.1%} {rsi_yr.get(yr, 0):>+8.1%} {bh_yr.get(yr, 0):>+8.1%}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. SAVE CSV
# ─────────────────────────────────────────────────────────────────────────────

csv_cols = ['strategy', 'annual_return', 'total_return', 'mtm_max_dd',
            'calmar', 'sharpe', 'sortino', 'n_trades', 'win_rate',
            'avg_win', 'avg_loss', 'profit_factor', 'stop_exits_pct']
pd.DataFrame(all_metrics)[csv_cols].to_csv(
    os.path.join(RESULTS_DIR, 'stage5_final_comparison.csv'), index=False
)
print(f"\n✅ CSV → results/stage5_final_comparison.csv")


# ─────────────────────────────────────────────────────────────────────────────
# 9. INTERACTIVE HTML — Plotly
# ─────────────────────────────────────────────────────────────────────────────

date_list = [d.strftime('%Y-%m-%d') for d in dates]

# ── Colour palette ────────────────────────────────────────────────────────────
C_ADX = '#2196F3'   # blue
C_RSI = '#FF9800'   # orange
C_BH  = '#9E9E9E'   # grey

# ── Figure 1: Equity curves (log) + Drawdown ─────────────────────────────────
fig1 = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.68, 0.32],
    vertical_spacing=0.04,
    subplot_titles=('Equity Curve (log scale, $1 start, costs included)', 'Drawdown from Peak'),
)

for eq, label, color, dash in [
    (adx_eq, 'ETH ADX 19/9 (8% trail)', C_ADX, 'solid'),
    (rsi_eq, 'ETH RSI 14/43/48 (15% stop)', C_RSI, 'solid'),
    (bh_eq,  'Buy & Hold ETH', C_BH, 'dot'),
]:
    fig1.add_trace(go.Scatter(
        x=date_list, y=eq.tolist(),
        name=label, line=dict(color=color, width=1.8, dash=dash),
        hovertemplate='%{x}<br>Equity: %{y:.3f}×<extra>' + label + '</extra>',
    ), row=1, col=1)

    peak = np.maximum.accumulate(eq)
    dd   = (eq - peak) / peak
    fig1.add_trace(go.Scatter(
        x=date_list, y=(dd * 100).tolist(),
        name=label + ' DD', line=dict(color=color, width=1.4, dash=dash),
        showlegend=False,
        hovertemplate='%{x}<br>DD: %{y:.1f}%<extra>' + label + '</extra>',
    ), row=2, col=1)

fig1.update_yaxes(type='log', tickformat='.2f', title_text='Equity (×)', row=1, col=1)
fig1.update_yaxes(ticksuffix='%', title_text='Drawdown %', row=2, col=1)
fig1.update_xaxes(title_text='Date', row=2, col=1)
fig1.update_layout(
    height=620,
    margin=dict(l=60, r=20, t=50, b=40),
    legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.85)', bordercolor='#ccc', borderwidth=1),
    hovermode='x unified',
    paper_bgcolor='white',
    plot_bgcolor='#fafafa',
)
fig1_html = fig1.to_html(full_html=False, include_plotlyjs=False, div_id='fig1')

# ── Figure 2: Year-by-year bar chart ─────────────────────────────────────────
fig2 = go.Figure()

bar_width = 0.25
x_pos = list(range(len(all_years)))

for offset, (yr_dict, label, color) in enumerate([
    (adx_yr, 'ETH ADX 19/9', C_ADX),
    (rsi_yr, 'ETH RSI 14/43/48', C_RSI),
    (bh_yr,  'B&H ETH', C_BH),
]):
    fig2.add_trace(go.Bar(
        x=[x + (offset - 1) * bar_width for x in x_pos],
        y=[yr_dict.get(yr, 0) * 100 for yr in all_years],
        name=label,
        marker_color=color,
        width=bar_width,
        hovertemplate='%{x}<br>' + label + ': %{y:.1f}%<extra></extra>',
    ))

fig2.add_hline(y=0, line_color='black', line_width=0.8)
fig2.update_layout(
    title='Year-by-Year Calendar Returns',
    xaxis=dict(
        tickvals=x_pos,
        ticktext=[str(yr) for yr in all_years],
        title='Year',
    ),
    yaxis=dict(ticksuffix='%', title='Annual Return'),
    barmode='group',
    height=380,
    margin=dict(l=60, r=20, t=50, b=50),
    legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.85)', bordercolor='#ccc', borderwidth=1),
    paper_bgcolor='white',
    plot_bgcolor='#fafafa',
)
fig2_html = fig2.to_html(full_html=False, include_plotlyjs=False, div_id='fig2')


# ── Metrics table HTML ────────────────────────────────────────────────────────
def pct(v):     return f"{v*100:+.1f}%"
def pct_pos(v): return f"{v*100:.1f}%"
def dec3(v):    return f"{v:.3f}"

def row_html(m):
    pf_val = m['profit_factor']
    pf_str = f"{pf_val:.3f}" if pf_val != float('inf') else "∞"
    return (
        f"<td style='font-weight:600'>{m['strategy']}</td>"
        f"<td>{pct(m['annual_return'])}</td>"
        f"<td>{pct(m['total_return'])}</td>"
        f"<td>{pct_pos(abs(m['mtm_max_dd']))}</td>"
        f"<td>{dec3(m['calmar'])}</td>"
        f"<td>{dec3(m['sharpe'])}</td>"
        f"<td>{dec3(m['sortino'])}</td>"
        f"<td>{m['n_trades']}</td>"
        f"<td>{pct_pos(m['win_rate']) if m['n_trades'] > 1 else '—'}</td>"
        f"<td>{pct(m['avg_win']) if m['n_trades'] > 1 else '—'}</td>"
        f"<td>{pct(m['avg_loss']) if m['n_trades'] > 1 else '—'}</td>"
        f"<td>{pf_str if m['n_trades'] > 1 else '—'}</td>"
        f"<td>{pct_pos(m['stop_exits_pct']) if m['n_trades'] > 1 else '—'}</td>"
    )

yr_header = "".join(f"<th>{yr}</th>" for yr in all_years)
yr_adx = "".join(f"<td>{adx_yr.get(yr,0)*100:+.1f}%</td>" for yr in all_years)
yr_rsi = "".join(f"<td>{rsi_yr.get(yr,0)*100:+.1f}%</td>" for yr in all_years)
yr_bh  = "".join(f"<td>{bh_yr.get(yr,0)*100:+.1f}%</td>"  for yr in all_years)

from datetime import date as _date
run_date = _date.today().strftime('%Y-%m-%d')

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Stage 5 — Final Strategy Comparison</title>
  <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f4f5f7; color: #222; margin: 0; padding: 0; }}
    .wrapper {{ max-width: 1200px; margin: 0 auto; padding: 24px 20px 48px; }}
    h1 {{ font-size: 1.5rem; font-weight: 700; margin: 0 0 4px; color: #111; }}
    .subtitle {{ font-size: 0.85rem; color: #666; margin-bottom: 24px; }}
    .card {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1);
             padding: 20px; margin-bottom: 24px; }}
    h2 {{ font-size: 1.05rem; font-weight: 600; margin: 0 0 14px; color: #333; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
    .methodology {{ font-size: 0.78rem; color: #555; background: #f8f9fa; border-left: 3px solid #2196F3;
                    padding: 10px 14px; border-radius: 0 4px 4px 0; margin-bottom: 10px; line-height: 1.6; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    thead th {{ background: #37474f; color: #fff; padding: 8px 10px; text-align: center;
                font-weight: 600; white-space: nowrap; }}
    thead th:first-child {{ text-align: left; }}
    tbody tr:nth-child(even) {{ background: #f9f9f9; }}
    tbody td {{ padding: 7px 10px; text-align: center; border-bottom: 1px solid #eee; }}
    tbody td:first-child {{ text-align: left; }}
    .yr-table thead th {{ background: #546e7a; }}
    .note {{ font-size: 0.75rem; color: #888; margin-top: 8px; }}
    .adx-row td {{ background: rgba(33,150,243,0.06); }}
    .rsi-row td {{ background: rgba(255,152,0,0.06); }}
    .bh-row  td {{ background: rgba(158,158,158,0.06); }}
  </style>
</head>
<body>
<div class="wrapper">
  <h1>Stage 5 — Final Strategy Comparison</h1>
  <p class="subtitle">
    ETH ADX 19/9 (8% trail) &nbsp;·&nbsp; ETH RSI 14/43/48/15%/120MA &nbsp;·&nbsp;
    Buy &amp; Hold ETH &nbsp;·&nbsp; Run: {run_date} &nbsp;·&nbsp;
    Data: 2018-01-01 → {dates[-1].strftime('%Y-%m-%d')} ({YEARS:.1f} yrs)
  </p>

  <div class="card">
    <h2>Equity Curves &amp; Drawdown</h2>
    <div class="methodology">
      <strong>Methodology:</strong>
      Daily mark-to-market equity curve · Stop checked vs daily LOW · ADX peak on CLOSE
      · Costs 0.15% round-trip · Sharpe/Sortino/Calmar from daily equity curve
      · ADX window=9, threshold=19 · RSI Wilder EWM period=14
    </div>
    {fig1_html}
  </div>

  <div class="card">
    <h2>Performance Metrics</h2>
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
        <tr class="adx-row">{row_html(all_metrics[0])}</tr>
        <tr class="rsi-row">{row_html(all_metrics[1])}</tr>
        <tr class="bh-row">{row_html(all_metrics[2])}</tr>
      </tbody>
    </table>
    <p class="note">
      MtM MaxDD = maximum drawdown from mark-to-market daily equity peak.
      Sortino uses daily downside std, annualised × √365.
      Trade costs (0.15% round-trip) included for both strategies; B&amp;H has no costs.
    </p>
  </div>

  <div class="card">
    <h2>Year-by-Year Calendar Returns</h2>
    {fig2_html}
    <table class="yr-table" style="margin-top:16px">
      <thead>
        <tr><th>Strategy</th>{yr_header}</tr>
      </thead>
      <tbody>
        <tr class="adx-row"><td><strong>ETH ADX 19/9</strong></td>{yr_adx}</tr>
        <tr class="rsi-row"><td><strong>ETH RSI 14/43/48</strong></td>{yr_rsi}</tr>
        <tr class="bh-row"><td><strong>B&amp;H ETH</strong></td>{yr_bh}</tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Parameter Reference</h2>
    <table style="width:auto; font-size:0.82rem">
      <thead>
        <tr><th>Parameter</th><th>ETH ADX</th><th>ETH RSI</th></tr>
      </thead>
      <tbody>
        <tr><td>Indicator period</td><td>ADX window = 9</td><td>RSI period = 14 (Wilder)</td></tr>
        <tr><td>Signal threshold</td><td>ADX ≥ 19, DI+ &gt; DI−</td><td>RSI &lt; 43 (entry); RSI &gt; 48 (exit)</td></tr>
        <tr><td>Regime filter</td><td>None</td><td>Close &gt; 120-day SMA</td></tr>
        <tr><td>Stop type</td><td>Trailing 8% from peak (close-based)</td><td>Fixed 15% from entry</td></tr>
        <tr><td>Live capital</td><td>$1,000 (fixed_allocation=false)</td><td>$150 (fixed_allocation=true, validation)</td></tr>
        <tr><td>Live Kelly fraction</td><td>Half-Kelly (f*=TRAIL_PCT)</td><td>Half-Kelly (f*=STOP_PCT, 0.384)</td></tr>
      </tbody>
    </table>
  </div>

</div>
</body>
</html>"""

html_path = os.path.join(DEPLOY_DIR, 'week6_stage5_final_comparison_v2.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"✅ HTML → Deployment_Documents/Week_6/week6_stage5_final_comparison_v2.html")

print(f"\n{'='*70}")
print(f"STAGE 5 COMPLETE")
print(f"{'='*70}")
print(f"  ETH ADX 19/9 (8% trail) : Annual {adx_m['annual_return']:+.1%} | "
      f"MtM MaxDD {adx_m['mtm_max_dd']:.1%} | Calmar {adx_m['calmar']:.3f} | "
      f"Sortino {adx_m['sortino']:.3f}")
print(f"  ETH RSI 14/43/48        : Annual {rsi_m['annual_return']:+.1%} | "
      f"MtM MaxDD {rsi_m['mtm_max_dd']:.1%} | Calmar {rsi_m['calmar']:.3f} | "
      f"Sortino {rsi_m['sortino']:.3f}")
print(f"  Buy & Hold ETH          : Annual {bh_m['annual_return']:+.1%} | "
      f"MtM MaxDD {bh_m['mtm_max_dd']:.1%} | Calmar {bh_m['calmar']:.3f} | "
      f"Sortino {bh_m['sortino']:.3f}")
print(f"{'='*70}\n")
