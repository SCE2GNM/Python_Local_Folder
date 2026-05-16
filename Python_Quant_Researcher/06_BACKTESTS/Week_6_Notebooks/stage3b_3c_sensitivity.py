#!/usr/bin/env python3
"""
Stage 3b — Leverage Stability Analysis (±1.0x around optimal 1.9x)
Stage 3c — Interest Rate Sensitivity (0.010%, 0.015%, 0.020%/day)

Set 2 (ADX 19/9, pct 8% trailing stop) — deployment target.
Set 1 (ADX 20/10, ATR 9/2.5x) shown for comparison in 3b.

Stage 3b confirms the 1.9x optimal is a genuine plateau, not a sharp peak.
Stage 3c confirms strategy robustness to realistic interest rate variation.
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

# ── Constants (identical to stage3_eth_leverage.py) ──────────────────────────
COSTS        = 0.0015
MAINT_MARGIN = 0.05
STOP_SLIP    = 0.0025
LIQ_SLIP     = 0.005
SAFETY_WARN  = 33.0
SAFETY_VETO  = 25.0
CAPITAL      = 1500.0

BASE_INT_RATE = 0.00015   # 0.015%/day — baseline
INT_RATES     = [0.00010, 0.00015, 0.00020]  # 3c: low / base / high
INT_LABELS    = ['0.010%/day (low)', '0.015%/day (base)', '0.020%/day (stress)']

# Stage 3b: ±1.0x around optimal 1.9x
LEV_3B = np.round(np.arange(0.9, 3.0, 0.1), 2)   # 0.9x–2.9x, 21 levels
# Stage 3c: full grid at each rate (to show rate sensitivity curve)
LEV_3C = np.round(np.arange(1.0, 5.1, 0.1), 2)   # 1.0x–5.0x

OPTIMAL_LEV  = 1.9   # Set 2 optimal from Stage 3a

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
print(f"Data: {dates[0].date()} → {dates[-1].date()}  ({YEARS:.2f} yrs, {N} bars)\n")

# ── Signals ───────────────────────────────────────────────────────────────────
def get_adx_signal(adx_thresh, adx_per):
    ind      = ADXIndicator(eth['High'], eth['Low'], eth['Close'],
                            window=adx_per, fillna=False)
    adx      = ind.adx().values
    plus_di  = ind.adx_pos().values
    minus_di = ind.adx_neg().values
    return (adx >= adx_thresh) & (plus_di > minus_di)


def get_atr(period):
    prev = eth['Close'].shift(1)
    tr   = pd.concat([eth['High'] - eth['Low'],
                      (eth['High'] - prev).abs(),
                      (eth['Low']  - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean().values


sig1 = get_adx_signal(20, 10)
sig2 = get_adx_signal(19,  9)
atr9 = get_atr(9)


# ── Backtest engines ──────────────────────────────────────────────────────────
def liq_px(ep, lev):
    if lev <= 1.0:
        return 0.0
    return ep * (lev - 1.0) / (lev * (1.0 - MAINT_MARGIN))


def run_pct_lev(sig, lev, trail_pct=0.08, int_rate=BASE_INT_RATE):
    portfolio = 1.0; pos = 0
    ep = peak = stop = lp = 0.0
    entry_date = None; entry_bar = 0; entry_port = 0.0
    trades = []; min_mr = 1.0; n_liq = 0

    for i in range(1, N):
        cl = closes[i]; lo = lows[i]; dt = dates[i]
        if pos == 1:
            days_held = i - entry_bar
            if lev > 1.0:
                mr = 1.0 - (lev - 1.0) * ep / (lev * lo)
                min_mr = min(min_mr, mr)
            exit_px = None; ex_rsn = None; is_liq = False
            if lev > 1.0 and lp > stop and lo <= lp:
                exit_px = lp * (1.0 - LIQ_SLIP); ex_rsn = 'LIQUIDATION'
                is_liq = True; n_liq += 1
            elif lo <= stop:
                exit_px = stop * (1.0 - STOP_SLIP); ex_rsn = 'TRAIL_STOP'
            elif not sig[i]:
                exit_px = cl; ex_rsn = 'ADX_EXIT'
            if exit_px is not None:
                r = lev * (exit_px / ep - 1.0 - COSTS) \
                    - days_held * int_rate * (lev - 1.0)
                int_frac = days_held * int_rate * (lev - 1.0) * entry_port
                trades.append({
                    'entry_date': entry_date, 'exit_date': dt,
                    'entry_price': ep, 'exit_price': exit_px,
                    'return': r, 'exit_reason': ex_rsn,
                    'hold_days': days_held, 'int_frac': int_frac,
                    'entry_port': entry_port,
                })
                portfolio = entry_port * (1.0 + r); pos = 0; entry_date = None
            else:
                if cl > peak:
                    peak = cl; stop = peak * (1.0 - trail_pct)
        else:
            if sig[i]:
                ep = cl; peak = cl; stop = cl * (1.0 - trail_pct)
                lp = liq_px(ep, lev)
                entry_date = dt; entry_bar = i; entry_port = portfolio; pos = 1

    return trades, min_mr, n_liq


def run_atr_lev(sig, atr_vals, lev, atr_mult=2.5, int_rate=BASE_INT_RATE):
    portfolio = 1.0; pos = 0
    ep = peak = stop = lp = 0.0
    entry_date = None; entry_bar = 0; entry_port = 0.0
    trades = []; min_mr = 1.0; n_liq = 0

    for i in range(1, N):
        cl = closes[i]; lo = lows[i]; dt = dates[i]; atr_i = atr_vals[i]
        if pos == 1:
            days_held = i - entry_bar
            if lev > 1.0:
                mr = 1.0 - (lev - 1.0) * ep / (lev * lo)
                min_mr = min(min_mr, mr)
            exit_px = None; ex_rsn = None; is_liq = False
            if lev > 1.0 and lp > stop and lo <= lp:
                exit_px = lp * (1.0 - LIQ_SLIP); ex_rsn = 'LIQUIDATION'
                is_liq = True; n_liq += 1
            elif lo <= stop:
                exit_px = stop * (1.0 - STOP_SLIP); ex_rsn = 'TRAIL_STOP'
            elif not sig[i]:
                exit_px = cl; ex_rsn = 'ADX_EXIT'
            if exit_px is not None:
                r = lev * (exit_px / ep - 1.0 - COSTS) \
                    - days_held * int_rate * (lev - 1.0)
                int_frac = days_held * int_rate * (lev - 1.0) * entry_port
                trades.append({
                    'entry_date': entry_date, 'exit_date': dt,
                    'entry_price': ep, 'exit_price': exit_px,
                    'return': r, 'exit_reason': ex_rsn,
                    'hold_days': days_held, 'int_frac': int_frac,
                    'entry_port': entry_port,
                })
                portfolio = entry_port * (1.0 + r); pos = 0; entry_date = None
            else:
                if cl > peak:
                    peak = cl
                candidate = peak - atr_mult * atr_i
                stop = max(stop, candidate)
        else:
            if sig[i] and not np.isnan(atr_i):
                ep = cl; peak = cl; stop = cl - atr_mult * atr_i
                lp = liq_px(ep, lev)
                entry_date = dt; entry_bar = i; entry_port = portfolio; pos = 1

    return trades, min_mr, n_liq


def build_lev_equity(trades, lev, int_rate=BASE_INT_RATE):
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
        accrued  = days_arr * int_rate * (lev - 1.0) * p0
        equity[ei:xi+1] = p0 * (1.0 + lev * (closes[ei:xi+1] / ep - 1.0)) - accrued
        portfolio = p0 * (1.0 + t['return'])
        equity[xi] = portfolio; prev_i = xi + 1
    equity[prev_i:] = portfolio
    return equity


def compute_metrics(trades, eq, min_mr, n_liq, int_rate=BASE_INT_RATE):
    if not trades:
        return None
    ann_ret  = eq[-1] ** (1.0 / YEARS) - 1.0
    pk_mtm   = np.maximum.accumulate(eq)
    dd_mtm   = ((eq - pk_mtm) / pk_mtm).min()
    t_eq     = np.cumprod([1.0 + t['return'] for t in trades])
    t_pk     = np.maximum.accumulate(t_eq)
    dd_trade = ((t_eq - t_pk) / t_pk).min()
    dr = np.diff(eq) / eq[:-1]
    dn = dr[dr < 0]
    sortino  = (dr.mean() / dn.std() * np.sqrt(365)
                if len(dn) > 0 and dn.std() > 0 else 0.0)
    calmar   = ann_ret / abs(dd_mtm) if dd_mtm < 0 else 0.0
    total_int_usd = sum(t['int_frac'] * CAPITAL for t in trades)
    return {
        'annual_return':  round(ann_ret  * 100, 2),
        'max_dd_mtm':     round(dd_mtm   * 100, 2),
        'max_dd_trade':   round(dd_trade * 100, 2),
        'sortino':        round(sortino, 3),
        'calmar':         round(calmar, 3),
        'safety_buffer':  round(min_mr  * 100, 2),
        'total_int_usd':  round(total_int_usd, 2),
        'int_per_yr_usd': round(total_int_usd / YEARS, 2),
        'n_liquidations': n_liq,
        'n_trades':       len(trades),
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3b — Leverage stability ±1.0x around optimal 1.9x
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 68)
print("STAGE 3b — Leverage Stability Analysis  (0.9×–2.9×)")
print(f"Optimal from Stage 3a: {OPTIMAL_LEV:.1f}×  |  Safety floor: {SAFETY_WARN:.0f}%")
print("=" * 68)
print(f"{'Lev':>5} | {'Set2 Annual%':>12} {'MaxDD%':>7} {'Sortino':>8} "
      f"{'Buffer%':>8} {'Liq':>4}")
print("-" * 55)

res3b_s2 = []; res3b_s1 = []

for lev in LEV_3B:
    t2, mr2, nl2 = run_pct_lev(sig2, lev)
    eq2 = build_lev_equity(t2, lev)
    m2  = compute_metrics(t2, eq2, mr2, nl2)
    res3b_s2.append({'leverage': lev, **m2})

    t1, mr1, nl1 = run_atr_lev(sig1, atr9, lev)
    eq1 = build_lev_equity(t1, lev)
    m1  = compute_metrics(t1, eq1, mr1, nl1)
    res3b_s1.append({'leverage': lev, **m1})

    flag = ' ← OPTIMAL' if abs(lev - OPTIMAL_LEV) < 0.05 else \
           (' WARN' if m2['safety_buffer'] < SAFETY_WARN else '')
    print(f"{lev:>5.1f} | {m2['annual_return']:>11.1f}%"
          f" {m2['max_dd_mtm']:>7.1f}%"
          f" {m2['sortino']:>8.3f}"
          f" {m2['safety_buffer']:>7.1f}%"
          f" {nl2:>4}liq{flag}")

print()

# ── 3b sensitivity chart ──────────────────────────────────────────────────────
fig3b = make_subplots(
    rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
    row_heights=[0.40, 0.30, 0.30],
    subplot_titles=[
        'Annual Return % (Set 2 vs Set 1)',
        'Daily MtM MaxDD %',
        'Safety Buffer %  (margin ratio)',
    ],
)

levs3b   = [r['leverage']       for r in res3b_s2]
ret3b_s2 = [r['annual_return']  for r in res3b_s2]
mdd3b_s2 = [r['max_dd_mtm']    for r in res3b_s2]
buf3b_s2 = [r['safety_buffer']  for r in res3b_s2]
sor3b_s2 = [r['sortino']        for r in res3b_s2]
ret3b_s1 = [r['annual_return']  for r in res3b_s1]
mdd3b_s1 = [r['max_dd_mtm']    for r in res3b_s1]
buf3b_s1 = [r['safety_buffer']  for r in res3b_s1]

ht2 = ('<b>%{x:.1f}×</b><br>'
       'Return: %{y:.1f}%<br>'
       '<extra>%{fullData.name}</extra>')

# Row 1: Annual return
fig3b.add_trace(go.Scatter(x=levs3b, y=ret3b_s2, name='Set 2 (ADX 19/9, pct 8%)',
    line=dict(color='#27ae60', width=2.5),
    hovertemplate=ht2), row=1, col=1)
fig3b.add_trace(go.Scatter(x=levs3b, y=ret3b_s1, name='Set 1 (ADX 20/10, ATR)',
    line=dict(color='#2980b9', width=2.0, dash='dash'),
    hovertemplate=ht2), row=1, col=1)

# Mark optimal on return panel
opt_idx = min(range(len(levs3b)), key=lambda i: abs(levs3b[i] - OPTIMAL_LEV))
fig3b.add_trace(go.Scatter(
    x=[OPTIMAL_LEV], y=[ret3b_s2[opt_idx]],
    mode='markers', name=f'★ Optimal {OPTIMAL_LEV:.1f}× (Set 2)',
    marker=dict(symbol='star', size=14, color='#27ae60'),
    hovertemplate=f'Optimal {OPTIMAL_LEV:.1f}×<br>Return: {ret3b_s2[opt_idx]:.1f}%<extra></extra>',
), row=1, col=1)

# ±0.5x shaded band
fig3b.add_vrect(
    x0=OPTIMAL_LEV - 0.5, x1=OPTIMAL_LEV + 0.5,
    fillcolor='#f9e4b7', opacity=0.4, layer='below', line_width=0,
    annotation_text='±0.5×', annotation_position='top left',
    annotation_font=dict(size=10, color='#b8860b'),
    row=1, col=1,
)

# Row 2: MaxDD
fig3b.add_trace(go.Scatter(x=levs3b, y=mdd3b_s2, name='Set 2 MaxDD%',
    line=dict(color='#27ae60', width=2.5), showlegend=False,
    hovertemplate='<b>%{x:.1f}×</b><br>MaxDD: %{y:.1f}%<extra>Set 2</extra>',
), row=2, col=1)
fig3b.add_trace(go.Scatter(x=levs3b, y=mdd3b_s1, name='Set 1 MaxDD%',
    line=dict(color='#2980b9', width=2.0, dash='dash'), showlegend=False,
    hovertemplate='<b>%{x:.1f}×</b><br>MaxDD: %{y:.1f}%<extra>Set 1</extra>',
), row=2, col=1)

# Row 3: Safety buffer
fig3b.add_trace(go.Scatter(x=levs3b, y=buf3b_s2, name='Set 2 Buffer%',
    line=dict(color='#27ae60', width=2.5), showlegend=False,
    hovertemplate='<b>%{x:.1f}×</b><br>Buffer: %{y:.1f}%<extra>Set 2</extra>',
), row=3, col=1)
fig3b.add_trace(go.Scatter(x=levs3b, y=buf3b_s1, name='Set 1 Buffer%',
    line=dict(color='#2980b9', width=2.0, dash='dash'), showlegend=False,
    hovertemplate='<b>%{x:.1f}×</b><br>Buffer: %{y:.1f}%<extra>Set 1</extra>',
), row=3, col=1)

# Safety thresholds on row 3
for thresh, color, lbl in [
    (SAFETY_WARN, '#f39c12', f'{SAFETY_WARN:.0f}% working min'),
    (SAFETY_VETO, '#e74c3c', f'{SAFETY_VETO:.0f}% hard veto'),
]:
    fig3b.add_trace(go.Scatter(
        x=[levs3b[0], levs3b[-1]], y=[thresh, thresh],
        mode='lines', line=dict(color=color, dash='dash', width=1.5),
        name=lbl, showlegend=False,
        hoverinfo='skip',
    ), row=3, col=1)

# Optimal vertical line across all rows
for row_n in [1, 2, 3]:
    fig3b.add_vline(x=OPTIMAL_LEV, line_dash='longdash', line_color='#888',
                    line_width=1.2, row=row_n, col=1)

fig3b.update_layout(
    title=dict(
        text=(
            f'Stage 3b — Leverage Sensitivity ±1.0× around Optimal {OPTIMAL_LEV:.1f}×<br>'
            f'<sup>Set 2: ADX 19/9 + pct 8% (green)  ·  '
            f'Set 1: ADX 20/10 + ATR 9/2.5x (blue dashed)  ·  '
            f'Amber band = ±0.5× plateau zone  ·  '
            f'Vertical dashed = optimal {OPTIMAL_LEV:.1f}×</sup>'
        ),
        font=dict(size=12, color='#1a1a1a'),
        x=0.5, xanchor='center', y=0.98,
    ),
    height=680,
    hovermode='x unified',
    paper_bgcolor='white',
    plot_bgcolor='#fafafa',
    margin=dict(l=75, r=50, t=105, b=50),
    legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.88)',
                bordercolor='#ccc', borderwidth=1, font=dict(size=10)),
)
for row_n in [1, 2, 3]:
    fig3b.update_xaxes(row=row_n, col=1, gridcolor='#e8e8e8',
                       showticklabels=(row_n == 3))
    fig3b.update_yaxes(row=row_n, col=1, gridcolor='#e8e8e8')
fig3b.update_xaxes(row=3, col=1, title_text='Leverage (×)', dtick=0.2)
fig3b.update_yaxes(row=1, col=1, title_text='Annual Return%')
fig3b.update_yaxes(row=2, col=1, title_text='MaxDD%')
fig3b.update_yaxes(row=3, col=1, title_text='Buffer%')

out3b = os.path.join(RESULTS_DIR, 'stage3b_stability.html')
fig3b.write_html(out3b, include_plotlyjs='cdn',
                 config={'displayModeBar': True, 'displaylogo': False,
                         'modeBarButtonsToRemove': ['lasso2d', 'select2d']})
sz3b = os.path.getsize(out3b) / 1024
print(f"Saved → results/stage3b_stability.html  ({sz3b:.0f} KB)")

# ── 3b terminal summary ───────────────────────────────────────────────────────
opt_at = next(r for r in res3b_s2 if abs(r['leverage'] - OPTIMAL_LEV) < 0.05)
pm1    = next(r for r in res3b_s2 if abs(r['leverage'] - (OPTIMAL_LEV + 0.1)) < 0.05)
mm1    = next(r for r in res3b_s2 if abs(r['leverage'] - (OPTIMAL_LEV - 0.1)) < 0.05)
pm5    = next((r for r in res3b_s2 if abs(r['leverage'] - (OPTIMAL_LEV + 0.5)) < 0.05), None)
mm5    = next((r for r in res3b_s2 if abs(r['leverage'] - (OPTIMAL_LEV - 0.5)) < 0.05), None)

print()
print("  Stage 3b — Set 2 sensitivity around optimal 1.9×  (return plateau check)")
print(f"  {'Leverage':>10}  {'Annual%':>9}  {'MaxDD%':>8}  {'Sortino':>8}  {'Buffer%':>8}")
print(f"  {'─'*50}")
for r in res3b_s2:
    marker = ' ← OPTIMAL' if abs(r['leverage'] - OPTIMAL_LEV) < 0.05 else \
             (' WARN' if r['safety_buffer'] < SAFETY_WARN else '')
    print(f"  {r['leverage']:>10.1f}  {r['annual_return']:>9.1f}%  "
          f"{r['max_dd_mtm']:>8.1f}%  {r['sortino']:>8.3f}  "
          f"{r['safety_buffer']:>7.1f}%{marker}")

print()
print(f"  Plateau check (Set 2 — annual return sensitivity):")
print(f"  At {OPTIMAL_LEV:.1f}×:        {opt_at['annual_return']:.1f}%  (base)")
if mm1: print(f"  At {OPTIMAL_LEV-0.1:.1f}× (−0.1×): {mm1['annual_return']:.1f}%  "
              f"({mm1['annual_return']-opt_at['annual_return']:+.1f}pp)")
if pm1: print(f"  At {OPTIMAL_LEV+0.1:.1f}× (+0.1×): {pm1['annual_return']:.1f}%  "
              f"({pm1['annual_return']-opt_at['annual_return']:+.1f}pp)")
if mm5: print(f"  At {OPTIMAL_LEV-0.5:.1f}× (−0.5×): {mm5['annual_return']:.1f}%  "
              f"({mm5['annual_return']-opt_at['annual_return']:+.1f}pp)")
if pm5: print(f"  At {OPTIMAL_LEV+0.5:.1f}× (+0.5×): {pm5['annual_return']:.1f}%  "
              f"({pm5['annual_return']-opt_at['annual_return']:+.1f}pp)")

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3c — Interest rate sensitivity
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 68)
print("STAGE 3c — Interest Rate Sensitivity")
print(f"Rates tested: {', '.join(f'{r*100:.3f}%/day' for r in INT_RATES)}")
print(f"Set 2 (ADX 19/9, pct 8%) — full leverage grid 1.0×–5.0×")
print("=" * 68)

# Run full grid at each interest rate
res3c = {}   # rate → list of row dicts
for rate, label in zip(INT_RATES, INT_LABELS):
    print(f"\nRate: {label}")
    rows = []
    for lev in LEV_3C:
        t2, mr2, nl2 = run_pct_lev(sig2, lev, int_rate=rate)
        eq2 = build_lev_equity(t2, lev, int_rate=rate)
        m   = compute_metrics(t2, eq2, mr2, nl2, int_rate=rate)
        rows.append({'leverage': lev, **m})
        if abs(lev - OPTIMAL_LEV) < 0.05:
            flag = ' ← optimal' if nl2 == 0 else ' ← optimal (but liq!)'
            print(f"  {lev:.1f}×: {m['annual_return']:.1f}%/yr  "
                  f"MaxDD {m['max_dd_mtm']:.1f}%  "
                  f"Sortino {m['sortino']:.3f}  "
                  f"Buffer {m['safety_buffer']:.1f}%  "
                  f"{nl2}liq{flag}")
    res3c[rate] = rows

# ── 3c chart: return sensitivity across full leverage grid, 3 rates ───────────
COLORS_3C = ['#2980b9', '#27ae60', '#e74c3c']

fig3c = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04,
    row_heights=[0.55, 0.45],
    subplot_titles=['Annual Return % by Interest Rate', 'Daily MtM MaxDD %'],
)

for (rate, label), color in zip(zip(INT_RATES, INT_LABELS), COLORS_3C):
    rows = res3c[rate]
    levs_c  = [r['leverage']      for r in rows]
    ret_c   = [r['annual_return'] for r in rows]
    mdd_c   = [r['max_dd_mtm']   for r in rows]

    fig3c.add_trace(go.Scatter(
        x=levs_c, y=ret_c, name=label,
        line=dict(color=color, width=2.2),
        hovertemplate=f'<b>%{{x:.1f}}×</b><br>Return: %{{y:.1f}}%<extra>{label}</extra>',
    ), row=1, col=1)
    fig3c.add_trace(go.Scatter(
        x=levs_c, y=mdd_c, name=label, showlegend=False,
        line=dict(color=color, width=2.2),
        hovertemplate=f'<b>%{{x:.1f}}×</b><br>MaxDD: %{{y:.1f}}%<extra>{label}</extra>',
    ), row=2, col=1)

# Vertical line at optimal
for row_n in [1, 2]:
    fig3c.add_vline(x=OPTIMAL_LEV, line_dash='longdash', line_color='#888',
                    line_width=1.2, row=row_n, col=1)
    fig3c.add_annotation(
        x=OPTIMAL_LEV, y=1.02, yref='paper',
        text=f'Optimal {OPTIMAL_LEV:.1f}×', xanchor='center',
        font=dict(size=10, color='#555'), showarrow=False,
    )

# Safety buffer threshold on buffer secondary axis would be complex — skip; rows already printed
fig3c.update_layout(
    title=dict(
        text=(
            'Stage 3c — Interest Rate Sensitivity: 0.010% / 0.015% / 0.020%/day<br>'
            '<sup>Set 2: ADX 19/9 + pct 8% trailing stop  ·  '
            f'Vertical dashed = optimal {OPTIMAL_LEV:.1f}×  ·  '
            'Interest accrues on borrowed amount during open positions only</sup>'
        ),
        font=dict(size=12, color='#1a1a1a'),
        x=0.5, xanchor='center', y=0.98,
    ),
    height=580,
    hovermode='x unified',
    paper_bgcolor='white',
    plot_bgcolor='#fafafa',
    margin=dict(l=75, r=50, t=105, b=55),
    legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.88)',
                bordercolor='#ccc', borderwidth=1, font=dict(size=10)),
)
fig3c.update_xaxes(row=1, col=1, gridcolor='#e8e8e8', showticklabels=False)
fig3c.update_xaxes(row=2, col=1, gridcolor='#e8e8e8', title_text='Leverage (×)', dtick=0.5)
fig3c.update_yaxes(row=1, col=1, gridcolor='#e8e8e8', title_text='Annual Return%')
fig3c.update_yaxes(row=2, col=1, gridcolor='#e8e8e8', title_text='MaxDD%')

out3c = os.path.join(RESULTS_DIR, 'stage3c_rate_sensitivity.html')
fig3c.write_html(out3c, include_plotlyjs='cdn',
                 config={'displayModeBar': True, 'displaylogo': False,
                         'modeBarButtonsToRemove': ['lasso2d', 'select2d']})
sz3c = os.path.getsize(out3c) / 1024
print(f"\nSaved → results/stage3c_rate_sensitivity.html  ({sz3c:.0f} KB)")

# ── 3c terminal summary table at optimal leverage ─────────────────────────────
print()
print("  Stage 3c — Set 2 at optimal 1.9× across three interest rates:")
print(f"  {'Rate':>25}  {'Annual%':>9}  {'MaxDD%':>8}  {'Sortino':>8}  "
      f"{'Int$/yr':>9}  {'Buffer%':>8}")
print(f"  {'─'*70}")
for rate, label in zip(INT_RATES, INT_LABELS):
    r = next(row for row in res3c[rate] if abs(row['leverage'] - OPTIMAL_LEV) < 0.05)
    # Simple interest on initial capital (not compounded)
    simple_int_per_yr = CAPITAL * (OPTIMAL_LEV - 1.0) * rate * 365
    print(f"  {label:>25}  {r['annual_return']:>9.1f}%  "
          f"{r['max_dd_mtm']:>8.1f}%  {r['sortino']:>8.3f}  "
          f"${simple_int_per_yr:>8.0f}/yr  {r['safety_buffer']:>7.1f}%")

print()
print("  Note: Int$/yr = simple interest on initial $1,500 × (lev−1) per year.")
print("        (Compounded figures in CSV are much larger as portfolio grows.)")

# ── Save 3c CSV ───────────────────────────────────────────────────────────────
rows_all = []
for rate, label in zip(INT_RATES, INT_LABELS):
    for r in res3c[rate]:
        rows_all.append({'rate_pct_day': rate * 100, 'rate_label': label, **r})
csv3c_path = os.path.join(SCRIPT_DIR, '..', 'data', 'stage3c_results.csv')
pd.DataFrame(rows_all).to_csv(csv3c_path, index=False)

print()
print("=" * 68)
print("Stages 3b and 3c complete.")
print("=" * 68)
