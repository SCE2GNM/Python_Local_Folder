#!/usr/bin/env python3
"""
Stage 3 — ETH ADX Leverage Optimisation (Stage 3a)
Week 6

Grid search 1.0x–5.0x (41 levels) for two parameter sets:
  Set 1: ADX 20/10 + ATR 9/2.5x  (original conservative)
  Set 2: ADX 19/9  + pct 8%       (Candidate A — confirmed deployment)

Interest: 0.015%/day on borrowed amount during open positions only
Borrowed: (leverage-1) × own equity at trade entry (fixed for duration)
Liquidation price: entry × (leverage-1) / (leverage × (1-maintenance_margin))
  → price at which margin_ratio = maintenance_margin = 5%
  → margin_ratio = 1 - (leverage-1)×entry / (leverage×current_price)
Stop slippage:  0.25% below intended stop price
Liq slippage:   0.5% below liquidation price
Safety buffer:  minimum margin ratio across all bars while in any position (using daily LOW)

Pauses after Stage 3a. Stages 3b and 3c run on instruction.
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
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
COSTS        = 0.0015    # 0.15% round-trip on notional (scaled by leverage)
INT_RATE     = 0.00015   # 0.015%/day on borrowed amount
MAINT_MARGIN = 0.05      # 5% maintenance margin
STOP_SLIP    = 0.0025    # 0.25% below intended stop price (calibrated: small pos, liquid ETHUSDT)
LIQ_SLIP     = 0.005     # 0.5% below liquidation price (calibrated: small pos, liquid ETHUSDT)
SAFETY_WARN  = 33.0      # working minimum buffer %
SAFETY_VETO  = 25.0      # hard floor veto % — auto-reject regardless of return
CAPITAL      = 1500.0    # live capital ($)

LEVERAGES = np.round(np.arange(1.0, 5.1, 0.1), 2)   # 41 levels

# ── Fetch data ────────────────────────────────────────────────────────────────
print("Fetching ETH-USD daily data...")
raw = yf.download('ETH-USD', start='2018-01-01', auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
eth = raw[['High', 'Low', 'Close']].dropna()

closes = eth['Close'].values.astype(float)
highs  = eth['High'].values.astype(float)
lows   = eth['Low'].values.astype(float)
dates  = eth.index
N      = len(closes)
YEARS  = (dates[-1] - dates[0]).days / 365.25
print(f"Data: {dates[0].date()} → {dates[-1].date()}  ({YEARS:.2f} yrs, {N} bars)\n")

# ── Indicators ────────────────────────────────────────────────────────────────
def get_signals(adx_thresh, adx_per):
    ind      = ADXIndicator(eth['High'], eth['Low'], eth['Close'],
                            window=adx_per, fillna=False)
    adx      = ind.adx().values
    plus_di  = ind.adx_pos().values
    minus_di = ind.adx_neg().values
    sma200   = eth['Close'].rolling(200).mean().values
    return (closes > sma200) & (adx > adx_thresh) & (plus_di > minus_di)

def get_atr(period):
    prev = eth['Close'].shift(1)
    tr   = pd.concat([eth['High'] - eth['Low'],
                      (eth['High'] - prev).abs(),
                      (eth['Low']  - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean().values

# ── Liquidation price ─────────────────────────────────────────────────────────
def liq_px(entry_price, lev, mm=MAINT_MARGIN):
    """Price where margin_ratio equals maintenance_margin. 0 at lev=1."""
    if lev <= 1.0:
        return 0.0
    return entry_price * (lev - 1.0) / (lev * (1.0 - mm))

# ── Leveraged pct trailing stop backtest ──────────────────────────────────────
def run_pct_lev(signal, lev, trail_pct=0.08):
    """
    Bar-by-bar backtest with percentage trailing stop + leverage.
    CORRECT order (matches Stage 1a): stop check → signal check → peak/stop update.
    Stop checked against daily LOW. Stop only moves UP (ratchet).
    Returns (trades, min_margin_ratio, n_liquidations).
    """
    portfolio  = 1.0
    pos        = 0
    ep = peak = stop = lp = 0.0
    entry_date = None; entry_bar = 0; entry_port = 0.0
    trades = []; min_mr = 1.0; n_liq = 0

    for i in range(1, N):
        cl = closes[i]; lo = lows[i]; dt = dates[i]

        if pos == 1:
            days_held = i - entry_bar

            # Track margin ratio at today's LOW on every open bar (incl. exit bar)
            if lev > 1.0:
                mr = 1.0 - (lev - 1.0) * ep / (lev * lo)
                min_mr = min(min_mr, mr)

            # Exit check uses stop set at the END of the PREVIOUS bar
            exit_px = None; ex_rsn = None; is_liq = False

            if lev > 1.0 and lp > stop and lo <= lp:
                exit_px = lp * (1.0 - LIQ_SLIP)
                ex_rsn  = 'LIQUIDATION'; is_liq = True; n_liq += 1
            elif lo <= stop:
                exit_px = stop * (1.0 - STOP_SLIP)
                ex_rsn  = 'TRAIL_STOP'
            elif not signal[i]:
                exit_px = cl
                ex_rsn  = 'ADX_EXIT'

            if exit_px is not None:
                r = lev * (exit_px / ep - 1.0 - COSTS) \
                    - days_held * INT_RATE * (lev - 1.0)
                int_frac = days_held * INT_RATE * (lev - 1.0) * entry_port
                trades.append({
                    'entry_date':  entry_date,   'exit_date':  dt,
                    'entry_price': ep,           'exit_price': exit_px,
                    'return':      r,            'exit_reason': ex_rsn,
                    'hold_days':   days_held,    'int_frac':   int_frac,
                    'entry_port':  entry_port,   'n_liq':      int(is_liq),
                })
                portfolio = entry_port * (1.0 + r)
                pos = 0; entry_date = None
            else:
                # Still in trade — update peak/stop AFTER exit check (for next bar)
                if cl > peak:
                    peak = cl
                    stop = peak * (1.0 - trail_pct)

        else:
            if signal[i]:
                ep    = cl; peak = cl; stop = peak * (1.0 - trail_pct)
                lp    = liq_px(ep, lev)
                entry_date = dt; entry_bar = i
                entry_port = portfolio; pos = 1

    return trades, min_mr, n_liq

# ── Leveraged ATR trailing stop backtest ─────────────────────────────────────
def run_atr_lev(signal, atr_vals, lev, atr_mult=2.5):
    """
    Bar-by-bar backtest with ATR trailing stop + leverage.
    CORRECT order (matches Stage 1b): stop check → signal check → peak/stop update.
    Stop = max(prev_stop, peak - atr_mult × ATR). Ratchets upward only.
    Returns (trades, min_margin_ratio, n_liquidations).
    """
    portfolio  = 1.0
    pos        = 0
    ep = peak = stop = lp = 0.0
    entry_date = None; entry_bar = 0; entry_port = 0.0
    trades = []; min_mr = 1.0; n_liq = 0

    for i in range(1, N):
        cl = closes[i]; lo = lows[i]; dt = dates[i]
        atr_i = atr_vals[i]

        if pos == 1:
            days_held = i - entry_bar

            # Track margin ratio at today's LOW on every open bar (incl. exit bar)
            if lev > 1.0:
                mr = 1.0 - (lev - 1.0) * ep / (lev * lo)
                min_mr = min(min_mr, mr)

            # Exit check uses stop set at END of previous bar
            exit_px = None; ex_rsn = None; is_liq = False

            if lev > 1.0 and lp > stop and lo <= lp:
                exit_px = lp * (1.0 - LIQ_SLIP)
                ex_rsn  = 'LIQUIDATION'; is_liq = True; n_liq += 1
            elif lo <= stop:
                exit_px = stop * (1.0 - STOP_SLIP)
                ex_rsn  = 'TRAIL_STOP'
            elif not signal[i]:
                exit_px = cl
                ex_rsn  = 'ADX_EXIT'

            if exit_px is not None:
                r = lev * (exit_px / ep - 1.0 - COSTS) \
                    - days_held * INT_RATE * (lev - 1.0)
                int_frac = days_held * INT_RATE * (lev - 1.0) * entry_port
                trades.append({
                    'entry_date':  entry_date,   'exit_date':  dt,
                    'entry_price': ep,           'exit_price': exit_px,
                    'return':      r,            'exit_reason': ex_rsn,
                    'hold_days':   days_held,    'int_frac':   int_frac,
                    'entry_port':  entry_port,   'n_liq':      int(is_liq),
                })
                portfolio = entry_port * (1.0 + r)
                pos = 0; entry_date = None
            else:
                # Still in trade — update ATR stop AFTER exit check (for next bar)
                if cl > peak:
                    peak = cl
                candidate = peak - atr_mult * atr_i
                stop      = max(stop, candidate)

        else:
            if signal[i] and not np.isnan(atr_i):
                ep    = cl; peak = cl; stop = cl - atr_mult * atr_i
                lp    = liq_px(ep, lev)
                entry_date = dt; entry_bar = i
                entry_port = portfolio; pos = 1

    return trades, min_mr, n_liq

# ── Daily equity with leverage ────────────────────────────────────────────────
def build_lev_equity(trades, lev):
    """
    Vectorised daily MtM equity curve.
    During hold: portfolio × (1 + lev × (close/entry − 1)) − interest_accrued
    At exit bar:  uses actual exit price (already in trade['return']).
    """
    date_to_i = {dt: i for i, dt in enumerate(dates)}
    equity    = np.ones(N)
    portfolio = 1.0
    prev_i    = 0

    for t in trades:
        ei = date_to_i.get(pd.Timestamp(t['entry_date']))
        xi = date_to_i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None:
            continue

        equity[prev_i:ei] = portfolio          # flat before this trade
        ep = t['entry_price']
        p0 = portfolio                         # own equity at trade entry

        # MtM during hold (vectorised): interest accrues from day after entry
        days_arr = np.arange(xi - ei + 1, dtype=float)  # 0, 1, 2, ...
        accrued  = days_arr * INT_RATE * (lev - 1.0) * p0
        equity[ei:xi + 1] = p0 * (1.0 + lev * (closes[ei:xi + 1] / ep - 1.0)) - accrued

        # Override exit bar: actual exit P&L baked into trade['return']
        portfolio  = p0 * (1.0 + t['return'])
        equity[xi] = portfolio
        prev_i     = xi + 1

    equity[prev_i:] = portfolio
    return equity

# ── Metrics ───────────────────────────────────────────────────────────────────
def compute_metrics(trades, eq, min_mr, n_liq):
    if not trades:
        return None

    # Annual return from final equity level
    ann_ret = eq[-1] ** (1.0 / YEARS) - 1.0

    # Daily MtM MaxDD
    pk_mtm   = np.maximum.accumulate(eq)
    dd_mtm   = ((eq - pk_mtm) / pk_mtm).min()

    # Per-trade MaxDD (cumprod of trade returns)
    t_eq = np.cumprod([1.0 + t['return'] for t in trades])
    t_pk = np.maximum.accumulate(t_eq)
    dd_trade = ((t_eq - t_pk) / t_pk).min()

    # Sortino from daily equity
    dr = np.diff(eq) / eq[:-1]
    dn = dr[dr < 0]
    sortino = (dr.mean() / dn.std() * np.sqrt(365)
               if len(dn) > 0 and dn.std() > 0 else 0.0)

    # Interest costs
    total_int_usd = sum(t['int_frac'] * CAPITAL for t in trades)
    int_per_yr    = total_int_usd / YEARS

    return {
        'annual_return':  round(ann_ret * 100, 2),
        'max_dd_mtm':     round(dd_mtm  * 100, 2),
        'max_dd_trade':   round(dd_trade * 100, 2),
        'sortino':        round(sortino, 3),
        'safety_buffer':  round(min_mr  * 100, 2),
        'total_int_usd':  round(total_int_usd, 2),
        'int_per_yr_usd': round(int_per_yr, 2),
        'n_liquidations': n_liq,
        'n_trades':       len(trades),
    }

# ── Precompute signals ────────────────────────────────────────────────────────
print("Computing signals...")
sig1  = get_signals(20, 10)   # Set 1
sig2  = get_signals(19,  9)   # Set 2
atr9  = get_atr(9)            # Set 1 uses ATR 9

# ── Grid search ───────────────────────────────────────────────────────────────
print(f"Running leverage grid ({len(LEVERAGES)} levels × 2 sets)...\n")
print(f"{'Lev':>5} | {'Set1 Return%':>12} {'Buf%':>6} {'Liq':>4} | "
      f"{'Set2 Return%':>12} {'Buf%':>6} {'Liq':>4}")
print("-" * 60)

res1, res2 = [], []

for lev in LEVERAGES:
    # Set 1: ADX 20/10 + ATR 9/2.5x
    t1, mr1, nl1 = run_atr_lev(sig1, atr9, lev, atr_mult=2.5)
    eq1 = build_lev_equity(t1, lev)
    m1  = compute_metrics(t1, eq1, mr1, nl1)
    res1.append({'leverage': lev, **m1})

    # Set 2: ADX 19/9 + pct 8%
    t2, mr2, nl2 = run_pct_lev(sig2, lev, trail_pct=0.08)
    eq2 = build_lev_equity(t2, lev)
    m2  = compute_metrics(t2, eq2, mr2, nl2)
    res2.append({'leverage': lev, **m2})

    flag1 = ' VETO' if m1['safety_buffer'] < SAFETY_VETO else \
            (' WARN' if m1['safety_buffer'] < SAFETY_WARN else '')
    flag2 = ' VETO' if m2['safety_buffer'] < SAFETY_VETO else \
            (' WARN' if m2['safety_buffer'] < SAFETY_WARN else '')
    print(f"{lev:>5.1f} | {m1['annual_return']:>11.1f}% "
          f"{m1['safety_buffer']:>5.1f}%{nl1:>4}liq{flag1:<5}| "
          f"{m2['annual_return']:>11.1f}% "
          f"{m2['safety_buffer']:>5.1f}%{nl2:>4}liq{flag2}")

# ── Save CSV ─────────────────────────────────────────────────────────────────
df1 = pd.DataFrame(res1); df1['set'] = 'Set1_ADX20_10_ATR9_2.5x'
df2 = pd.DataFrame(res2); df2['set'] = 'Set2_ADX19_9_pct8'
csv_all = pd.concat([df1, df2], ignore_index=True)
csv_path = os.path.join(DATA_DIR, 'stage3a_results.csv')
csv_all.to_csv(csv_path, index=False)
print(f"\nSaved → data/stage3a_results.csv  ({len(csv_all)} rows)")

# ── Helpers for charts ────────────────────────────────────────────────────────
levs      = [r['leverage']      for r in res1]
ret1      = [r['annual_return'] for r in res1]
ret2      = [r['annual_return'] for r in res2]
buf1      = [r['safety_buffer'] for r in res1]
buf2      = [r['safety_buffer'] for r in res2]
dd_mtm1   = [r['max_dd_mtm']   for r in res1]
dd_mtm2   = [r['max_dd_mtm']   for r in res2]
int1      = [r['int_per_yr_usd'] for r in res1]
int2      = [r['int_per_yr_usd'] for r in res2]
liq1      = [r['n_liquidations'] for r in res1]
liq2      = [r['n_liquidations'] for r in res2]

# First leverage where buffer drops below SAFETY_WARN
def first_warn(buf_list):
    for i, b in enumerate(buf_list):
        if b < SAFETY_WARN:
            return levs[i]
    return None

warn_lev1 = first_warn(buf1)
warn_lev2 = first_warn(buf2)

# Optimal leverage: max annual return with buffer >= SAFETY_WARN and zero liq
def optimal(res):
    valid = [r for r in res if r['safety_buffer'] >= SAFETY_WARN
             and r['n_liquidations'] == 0]
    return max(valid, key=lambda x: x['annual_return']) if valid else None

opt1 = optimal(res1)
opt2 = optimal(res2)

# ── Chart 1: Return % vs Leverage (with safety buffer secondary y-axis) ───────
fig1 = make_subplots(specs=[[{"secondary_y": True}]])

cd1 = np.column_stack([buf1, dd_mtm1, int1, liq1])
cd2 = np.column_stack([buf2, dd_mtm2, int2, liq2])

htmp = ('<b>Leverage: %{x:.1f}x</b><br>'
        'Annual Return: %{y:.1f}%<br>'
        'Safety Buffer: %{customdata[0]:.1f}%<br>'
        'MaxDD (MtM): %{customdata[1]:.1f}%<br>'
        'Interest/yr: $%{customdata[2]:.0f}<br>'
        'Liquidations: %{customdata[3]:.0f}'
        '<extra></extra>')

fig1.add_trace(go.Scatter(x=levs, y=ret1, name='Set1 Annual Return%',
    line=dict(color='#2980b9', width=2.5),
    customdata=cd1, hovertemplate=htmp), secondary_y=False)

fig1.add_trace(go.Scatter(x=levs, y=ret2, name='Set2 Annual Return%',
    line=dict(color='#27ae60', width=2.5),
    customdata=cd2, hovertemplate=htmp), secondary_y=False)

fig1.add_trace(go.Scatter(x=levs, y=buf1, name='Set1 Safety Buffer%',
    line=dict(color='#2980b9', width=1.5, dash='dot'), opacity=0.7,
    hovertemplate='Leverage: %{x:.1f}x<br>Buffer: %{y:.1f}%<extra>Set1</extra>'),
    secondary_y=True)

fig1.add_trace(go.Scatter(x=levs, y=buf2, name='Set2 Safety Buffer%',
    line=dict(color='#27ae60', width=1.5, dash='dot'), opacity=0.7,
    hovertemplate='Leverage: %{x:.1f}x<br>Buffer: %{y:.1f}%<extra>Set2</extra>'),
    secondary_y=True)

# Reference lines on secondary y-axis
fig1.add_trace(go.Scatter(x=[levs[0], levs[-1]], y=[SAFETY_WARN]*2,
    name=f'{SAFETY_WARN:.0f}% working minimum',
    line=dict(color='#f39c12', dash='dash', width=1.5),
    hoverinfo='skip'), secondary_y=True)

fig1.add_trace(go.Scatter(x=[levs[0], levs[-1]], y=[SAFETY_VETO]*2,
    name=f'{SAFETY_VETO:.0f}% hard floor veto',
    line=dict(color='#e74c3c', dash='dash', width=1.5),
    hoverinfo='skip'), secondary_y=True)

# Vertical markers where buffer first drops below 33%
shapes = []
annotations = []
for warn_lev, color, label in [
    (warn_lev1, '#2980b9', 'Set1 warn'),
    (warn_lev2, '#27ae60', 'Set2 warn'),
]:
    if warn_lev:
        shapes.append(dict(type='line', x0=warn_lev, x1=warn_lev,
                           y0=0, y1=1, yref='paper',
                           line=dict(color=color, width=1.5, dash='longdash')))
        annotations.append(dict(x=warn_lev, y=1.02, yref='paper',
                                xanchor='center', text=f'{label}<br>{warn_lev:.1f}x',
                                font=dict(size=10, color=color),
                                showarrow=False))

# Optimal leverage markers on primary axis
for opt, color, lbl in [(opt1,'#2980b9','opt1'), (opt2,'#27ae60','opt2')]:
    if opt:
        fig1.add_trace(go.Scatter(
            x=[opt['leverage']], y=[opt['annual_return']],
            mode='markers', name=f'{lbl} optimal',
            marker=dict(symbol='star', size=14, color=color),
            hovertemplate=f'<b>Optimal {lbl}</b><br>Leverage: {opt["leverage"]:.1f}x<br>'
                          f'Return: {opt["annual_return"]:.1f}%<br>'
                          f'Buffer: {opt["safety_buffer"]:.1f}%<extra></extra>'),
            secondary_y=False)

fig1.update_layout(
    title=dict(text=(
        'Stage 3a — Annual Return% vs Leverage<br>'
        '<sup>Set 1: ADX 20/10 + ATR 9/2.5x  ·  Set 2: ADX 19/9 + pct 8%  ·  '
        f'Safety buffer {SAFETY_WARN:.0f}% working min (amber)  ·  '
        f'{SAFETY_VETO:.0f}% hard veto (red)  ·  ★ = optimal leverage</sup>'
    ), x=0.5, xanchor='center', font=dict(size=13)),
    height=580, margin=dict(l=70, r=80, t=95, b=60),
    hovermode='x unified', paper_bgcolor='white',
    legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.85)',
                bordercolor='#ccc', borderwidth=1),
    shapes=shapes, annotations=annotations,
)
fig1.update_xaxes(title_text='Leverage (×)', dtick=0.5, gridcolor='#eee')
fig1.update_yaxes(title_text='Annual Return%', gridcolor='#eee', secondary_y=False)
fig1.update_yaxes(title_text='Safety Buffer% (margin ratio)', gridcolor=None,
                  showgrid=False, secondary_y=True)

out1 = os.path.join(RESULTS_DIR, 'stage3a_return_vs_leverage.html')
fig1.write_html(out1, include_plotlyjs='cdn',
                config={'displayModeBar': True, 'displaylogo': False})
sz1 = os.path.getsize(out1) / 1024
print(f"Chart 1 → results/stage3a_return_vs_leverage.html  ({sz1:.0f} KB)")

# ── Chart 2: Daily MtM MaxDD% vs Leverage ─────────────────────────────────────
fig2 = go.Figure()

htmp2 = ('<b>Leverage: %{x:.1f}x</b><br>'
         'MaxDD (MtM): %{y:.1f}%<br>'
         'Annual Return: %{customdata[0]:.1f}%<br>'
         'Safety Buffer: %{customdata[1]:.1f}%<br>'
         'Interest/yr: $%{customdata[2]:.0f}<br>'
         'Liquidations: %{customdata[3]:.0f}'
         '<extra></extra>')

cd1b = np.column_stack([ret1, buf1, int1, liq1])
cd2b = np.column_stack([ret2, buf2, int2, liq2])

fig2.add_trace(go.Scatter(x=levs, y=dd_mtm1, name='Set1 MaxDD% (MtM)',
    line=dict(color='#2980b9', width=2.5),
    customdata=cd1b, hovertemplate=htmp2))

fig2.add_trace(go.Scatter(x=levs, y=dd_mtm2, name='Set2 MaxDD% (MtM)',
    line=dict(color='#27ae60', width=2.5),
    customdata=cd2b, hovertemplate=htmp2))

# Optimal markers
for opt, color, lbl in [(opt1,'#2980b9','opt1'), (opt2,'#27ae60','opt2')]:
    if opt:
        fig2.add_trace(go.Scatter(
            x=[opt['leverage']], y=[opt['max_dd_mtm']],
            mode='markers', name=f'{lbl} optimal',
            marker=dict(symbol='star', size=14, color=color),
            hovertemplate=f'<b>Optimal {lbl}</b><br>Leverage: {opt["leverage"]:.1f}x<br>'
                          f'MaxDD: {opt["max_dd_mtm"]:.1f}%<extra></extra>'))

fig2.update_layout(
    title=dict(text=(
        'Stage 3a — Daily MtM MaxDD% vs Leverage<br>'
        '<sup>Set 1: ADX 20/10 + ATR 9/2.5x  ·  Set 2: ADX 19/9 + pct 8%  ·  '
        '★ = optimal leverage (max return, buffer ≥ 33%, zero liquidations)</sup>'
    ), x=0.5, xanchor='center', font=dict(size=13)),
    height=520, margin=dict(l=70, r=60, t=95, b=60),
    hovermode='x unified', paper_bgcolor='white',
    legend=dict(x=0.01, y=0.01, bgcolor='rgba(255,255,255,0.85)',
                bordercolor='#ccc', borderwidth=1),
)
fig2.update_xaxes(title_text='Leverage (×)', dtick=0.5, gridcolor='#eee')
fig2.update_yaxes(title_text='Daily MtM MaxDD%', gridcolor='#eee')

out2 = os.path.join(RESULTS_DIR, 'stage3a_maxdd_vs_leverage.html')
fig2.write_html(out2, include_plotlyjs='cdn',
                config={'displayModeBar': True, 'displaylogo': False})
sz2 = os.path.getsize(out2) / 1024
print(f"Chart 2 → results/stage3a_maxdd_vs_leverage.html  ({sz2:.0f} KB)")

# ── Terminal summary table ────────────────────────────────────────────────────
print()
print("=" * 78)
print("STAGE 3a SUMMARY — Optimal Leverage per Set")
print(f"Criteria: safety buffer ≥ {SAFETY_WARN:.0f}%  ·  zero liquidations  ·  "
      f"ranked by annual return%")
print("=" * 78)

for label, opt, res_list in [
    ("Set 1 — ADX 20/10 + ATR 9/2.5x", opt1, res1),
    ("Set 2 — ADX 19/9  + pct 8%",     opt2, res2),
]:
    print(f"\n  {label}")
    print(f"  {'─'*60}")
    if opt is None:
        print("  No leverage level meets criteria (buffer ≥ 33% + zero liquidations)")
        continue
    print(f"  Optimal leverage:              {opt['leverage']:.1f}×")
    print(f"  Annual return%:               {opt['annual_return']:>7.1f}%")
    print(f"  Annual return$ on ${CAPITAL:.0f}:    "
          f"${opt['annual_return']/100 * CAPITAL:>8,.0f}")
    print(f"  Daily MtM MaxDD%:             {opt['max_dd_mtm']:>7.1f}%")
    print(f"  Per-trade MaxDD%:             {opt['max_dd_trade']:>7.1f}%")
    print(f"  Sortino:                      {opt['sortino']:>7.3f}")
    print(f"  Safety buffer (min margin):   {opt['safety_buffer']:>7.1f}%")
    print(f"  Interest cost/yr:             ${opt['int_per_yr_usd']:>8,.0f}")
    print(f"  Total interest (full period): ${opt['total_int_usd']:>8,.0f}")
    print(f"  Liquidation events:           {opt['n_liquidations']:>7d}")
    print(f"  Total trades:                 {opt['n_trades']:>7d}")

    # Find where buffer first drops below each threshold
    for thresh, label_t in [(SAFETY_WARN, '33% working minimum breach'),
                            (SAFETY_VETO, '25% hard floor veto')]:
        first = next((r['leverage'] for r in res_list
                      if r['safety_buffer'] < thresh), None)
        label_str = f"  Buffer <{thresh:.0f}% first at:"
        print(f"{label_str:<36} {first:.1f}×  ← {label_t}" if first
              else f"{label_str:<36} never in 1.0–5.0× grid")

print()
print("=" * 78)
print("Stage 3a complete.")
print("Awaiting instruction before Stage 3b (stability analysis) and 3c (rate sensitivity).")
print("=" * 78)
