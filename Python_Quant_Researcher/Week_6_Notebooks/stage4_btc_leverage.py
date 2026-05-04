#!/usr/bin/env python3
"""
Stage 4 — BTC SMA Leverage Optimisation
BTC SMA 120 with 25% percentage trailing stop.
Capital: $1,000.

Stage 4a: leverage grid search 1.0x–5.0x (41 levels). RUNS BY DEFAULT.
Stage 4b: leverage stability ±1.0x around optimal. Set RUN_4B = True to run.
Stage 4c: interest rate sensitivity 0.010%/0.015%/0.020%/day. Set RUN_4C = True to run.

Signal logic:
  Entry: fresh crossover — close crosses above SMA 120 (was below on previous bar).
  Exit:  close drops below SMA 120  OR  25% trailing stop fires  (whichever is first).
  Stop:  peak × (1 − 0.25), checked against daily LOW. Ratchets upward only.

Interest note: avg hold ~45 days vs ETH ADX ~8 days.
  At 0.9x borrowed capital, 45-day hold costs 45 × 0.015%/day × 0.9 = 0.61% per trade.
  This is 5-6× higher than ETH ADX and will visibly reduce leveraged returns.
"""

import os, warnings
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ── Run flags ─────────────────────────────────────────────────────────────────
RUN_4B = False   # Set True after Stage 4a reviewed
RUN_4C = False   # Set True after Stage 4b reviewed

# ── Strategy parameters ───────────────────────────────────────────────────────
SMA_PERIOD = 120
TRAIL_PCT  = 0.25    # 25% trailing stop

# ── Constants (identical to Stage 3) ─────────────────────────────────────────
COSTS        = 0.0015    # 0.15% round-trip on notional
INT_RATE     = 0.00015   # 0.015%/day on borrowed amount (Stage 4a/4b baseline)
MAINT_MARGIN = 0.05      # 5% maintenance margin
STOP_SLIP    = 0.0025    # 0.25% below intended stop price
LIQ_SLIP     = 0.005     # 0.5% below liquidation price
SAFETY_WARN  = 33.0      # working minimum buffer %
SAFETY_VETO  = 25.0      # hard floor — auto-reject
CAPITAL      = 1000.0    # BTC allocation ($)

LEVERAGES = np.round(np.arange(1.0, 5.1, 0.1), 2)   # 41 levels

INT_RATES_3C  = [0.00010, 0.00015, 0.00020]
INT_LABELS_3C = ['0.010%/day (low)', '0.015%/day (base)', '0.020%/day (stress)']

# ── Fetch data ────────────────────────────────────────────────────────────────
print("Fetching BTC-USD daily data...")
raw = yf.download('BTC-USD', start='2018-01-01', auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
btc = raw[['High', 'Low', 'Close']].dropna()

closes = btc['Close'].values.astype(float)
lows   = btc['Low'].values.astype(float)
dates  = btc.index
N      = len(closes)
YEARS  = (dates[-1] - dates[0]).days / 365.25
print(f"Data: {dates[0].date()} → {dates[-1].date()}  ({YEARS:.2f} yrs, {N} bars)")

# ── SMA 120 signal ────────────────────────────────────────────────────────────
sma_vals = pd.Series(closes).rolling(SMA_PERIOD, min_periods=SMA_PERIOD).mean().values
# above_sma[i] = True when close is above SMA (NaN bars → False)
above_sma = np.where(np.isnan(sma_vals), False, closes > sma_vals).astype(bool)
print(f"SMA {SMA_PERIOD}: {np.isnan(sma_vals).sum()} warmup bars  |  "
      f"{above_sma.sum()} bars above SMA  ({above_sma.mean()*100:.1f}% of data)\n")


# ── Helpers ───────────────────────────────────────────────────────────────────
def liq_px(ep, lev):
    if lev <= 1.0:
        return 0.0
    return ep * (lev - 1.0) / (lev * (1.0 - MAINT_MARGIN))


def run_btc_sma(lev, trail_pct=TRAIL_PCT, int_rate=INT_RATE):
    """
    Bar-by-bar backtest: BTC SMA crossover + percentage trailing stop + leverage.
    Entry: fresh crossover above SMA (above_sma[i] and not above_sma[i-1]).
    Exit: close drops below SMA (SMA_EXIT) OR trail stop (TRAIL_STOP) OR liquidation.
    CORRECT stop order: check exit → signal check → update peak (for next bar).
    """
    portfolio = 1.0; pos = 0
    ep = peak = stop = lp = 0.0
    entry_date = None; entry_bar = 0; entry_port = 0.0
    trades = []; min_mr = 1.0; n_liq = 0

    for i in range(1, N):
        cl = closes[i]; lo = lows[i]; dt = dates[i]

        if pos == 1:
            days_held = i - entry_bar

            # Track margin ratio at daily LOW on every open bar
            if lev > 1.0:
                mr = 1.0 - (lev - 1.0) * ep / (lev * lo)
                min_mr = min(min_mr, mr)

            # Exit checks (order: liquidation → stop → signal)
            exit_px = None; ex_rsn = None; is_liq = False

            if lev > 1.0 and lp > stop and lo <= lp:
                exit_px = lp * (1.0 - LIQ_SLIP); ex_rsn = 'LIQUIDATION'
                is_liq = True; n_liq += 1
            elif lo <= stop:
                exit_px = stop * (1.0 - STOP_SLIP); ex_rsn = 'TRAIL_STOP'
            elif not above_sma[i]:
                exit_px = cl; ex_rsn = 'SMA_EXIT'

            if exit_px is not None:
                r = lev * (exit_px / ep - 1.0 - COSTS) \
                    - days_held * int_rate * (lev - 1.0)
                int_frac = days_held * int_rate * (lev - 1.0) * entry_port
                trades.append({
                    'entry_date':  entry_date,   'exit_date':  dt,
                    'entry_price': ep,           'exit_price': exit_px,
                    'return':      r,            'exit_reason': ex_rsn,
                    'hold_days':   days_held,    'int_frac':   int_frac,
                    'entry_port':  entry_port,
                })
                portfolio = entry_port * (1.0 + r)
                pos = 0; entry_date = None
            else:
                # Update peak/stop AFTER exit check (for next bar)
                if cl > peak:
                    peak = cl; stop = peak * (1.0 - trail_pct)

        else:
            # Entry only on fresh crossover above SMA
            if above_sma[i] and not above_sma[i - 1]:
                ep = cl; peak = cl; stop = cl * (1.0 - trail_pct)
                lp = liq_px(ep, lev)
                entry_date = dt; entry_bar = i; entry_port = portfolio; pos = 1

    return trades, min_mr, n_liq


def build_lev_equity(trades, lev, int_rate=INT_RATE):
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


def compute_metrics(trades, eq, min_mr, n_liq, int_rate=INT_RATE):
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
    sortino = (dr.mean() / dn.std() * np.sqrt(365)
               if len(dn) > 0 and dn.std() > 0 else 0.0)
    calmar  = ann_ret / abs(dd_mtm) if dd_mtm < 0 else 0.0
    avg_hold = np.mean([t['hold_days'] for t in trades]) if trades else 0.0
    total_int_usd = sum(t['int_frac'] * CAPITAL for t in trades)
    return {
        'annual_return':  round(ann_ret  * 100, 2),
        'max_dd_mtm':     round(dd_mtm   * 100, 2),
        'max_dd_trade':   round(dd_trade * 100, 2),
        'sortino':        round(sortino, 3),
        'calmar':         round(calmar, 3),
        'safety_buffer':  round(min_mr  * 100, 2),
        'avg_hold_days':  round(avg_hold, 1),
        'total_int_usd':  round(total_int_usd, 2),
        'int_per_yr_usd': round(total_int_usd / YEARS, 2),
        'n_liquidations': n_liq,
        'n_trades':       len(trades),
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4a — Leverage grid search 1.0x–5.0x
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 70)
print(f"STAGE 4a — BTC SMA {SMA_PERIOD}/{int(TRAIL_PCT*100)}% Leverage Grid Search")
print(f"Grid: {LEVERAGES[0]:.1f}x – {LEVERAGES[-1]:.1f}x  ({len(LEVERAGES)} levels)")
print(f"Interest: {INT_RATE*100:.3f}%/day  |  Capital: ${CAPITAL:,.0f}")
print("=" * 70)
print(f"\n{'Lev':>5} | {'Annual%':>9} {'MaxDD%':>8} {'Sortino':>8} {'Calmar':>7} "
      f"{'Buf%':>6} {'Avg Hold':>9} {'Int$/yr':>9} {'Liq':>4}")
print("-" * 72)

results = []
for lev in LEVERAGES:
    t, mr, nl = run_btc_sma(lev)
    eq = build_lev_equity(t, lev)
    m  = compute_metrics(t, eq, mr, nl)
    results.append({'leverage': lev, **m})

    flag = ' VETO' if m['safety_buffer'] < SAFETY_VETO else \
           (' WARN' if m['safety_buffer'] < SAFETY_WARN else '')
    # Simple annual interest on initial capital (not compounded)
    simple_int = CAPITAL * (lev - 1.0) * INT_RATE * 365
    print(f"{lev:>5.1f} | {m['annual_return']:>9.1f}% {m['max_dd_mtm']:>8.1f}% "
          f"{m['sortino']:>8.3f} {m['calmar']:>7.3f} "
          f"{m['safety_buffer']:>5.1f}% {m['avg_hold_days']:>8.1f}d "
          f"${simple_int:>7,.0f}/yr {nl:>4}liq{flag}")

# ── Optimal leverage ─────────────────────────────────────────────────────────
valid = [r for r in results if r['safety_buffer'] >= SAFETY_WARN
         and r['n_liquidations'] == 0]
opt = max(valid, key=lambda x: x['annual_return']) if valid else None

# Also find calmar-optimal (return / abs(maxdd)) within safe zone
calmar_opt = max(valid, key=lambda x: x['calmar']) if valid else None

print()
print("=" * 70)
print("STAGE 4a — SUMMARY")
print("=" * 70)
print(f"\n  1x baseline (matches Stage 2a):")
base = next(r for r in results if abs(r['leverage'] - 1.0) < 0.05)
print(f"  Annual return:        {base['annual_return']:.1f}%")
print(f"  Daily MtM MaxDD:      {base['max_dd_mtm']:.1f}%")
print(f"  Per-trade MaxDD:      {base['max_dd_trade']:.1f}%")
print(f"  Sortino:              {base['sortino']:.3f}")
print(f"  Calmar:               {base['calmar']:.3f}")
print(f"  Avg hold days:        {base['avg_hold_days']:.1f}d")
print(f"  Trades:               {base['n_trades']}")

if opt:
    print(f"\n  Optimal leverage (max return, buffer ≥ {SAFETY_WARN:.0f}%, zero liq):")
    print(f"  Leverage:             {opt['leverage']:.1f}×")
    print(f"  Annual return:        {opt['annual_return']:.1f}%  "
          f"(vs {base['annual_return']:.1f}% at 1x, "
          f"+{opt['annual_return']-base['annual_return']:.1f}pp)")
    print(f"  Annual return $:      ${opt['annual_return']/100 * CAPITAL:,.0f}")
    print(f"  Daily MtM MaxDD:      {opt['max_dd_mtm']:.1f}%")
    print(f"  Sortino:              {opt['sortino']:.3f}")
    print(f"  Calmar:               {opt['calmar']:.3f}")
    print(f"  Safety buffer:        {opt['safety_buffer']:.1f}%")
    print(f"  Simple interest/yr:   ${CAPITAL * (opt['leverage']-1.0) * INT_RATE * 365:,.0f}")
    print(f"  Avg hold days:        {opt['avg_hold_days']:.1f}d")
    print(f"  Liquidations:         {opt['n_liquidations']}")

    # Interest per trade at optimal
    int_per_trade = opt['avg_hold_days'] * INT_RATE * (opt['leverage'] - 1.0) * 100
    print(f"\n  Interest drag per trade at {opt['leverage']:.1f}×:")
    print(f"  {opt['avg_hold_days']:.0f}d × {INT_RATE*100:.3f}%/day × "
          f"{opt['leverage']-1.0:.1f} borrowed = {int_per_trade:.3f}% per trade")
    print(f"  (ETH ADX reference: ~8d × 0.015% × 0.9 = 0.108% per trade)")
else:
    print("\n  No leverage level meets criteria (buffer ≥ 33% + zero liquidations)")

# Buffer breach thresholds
warn_lev = next((r['leverage'] for r in results
                 if r['safety_buffer'] < SAFETY_WARN), None)
veto_lev = next((r['leverage'] for r in results
                 if r['safety_buffer'] < SAFETY_VETO), None)
print()
if warn_lev: print(f"  Buffer < {SAFETY_WARN:.0f}% first at: {warn_lev:.1f}×")
if veto_lev: print(f"  Buffer < {SAFETY_VETO:.0f}% first at: {veto_lev:.1f}×  (hard floor)")
print()

# ── Save CSV ─────────────────────────────────────────────────────────────────
df = pd.DataFrame(results)
csv_path = os.path.join(DATA_DIR, 'stage4a_results.csv')
df.to_csv(csv_path, index=False)
print(f"  Saved CSV → data/stage4a_results.csv  ({len(df)} rows)")

# ── BTC B&H for comparison ────────────────────────────────────────────────────
btc_bh    = closes / closes[0]
ann_bh    = btc_bh[-1] ** (1.0 / YEARS) - 1.0
pk_bh     = np.maximum.accumulate(btc_bh)
maxdd_bh  = ((btc_bh - pk_bh) / pk_bh).min() * 100

print(f"\n  BTC Buy-and-Hold reference:")
print(f"  Annual return: {ann_bh*100:.1f}%  |  MaxDD: {maxdd_bh:.1f}%")

# ── Build chart: return% and safety buffer% vs leverage ───────────────────────
levs   = [r['leverage']       for r in results]
ret    = [r['annual_return']  for r in results]
buf    = [r['safety_buffer']  for r in results]
mdd    = [r['max_dd_mtm']    for r in results]
sor    = [r['sortino']        for r in results]
cal    = [r['calmar']         for r in results]
liq    = [r['n_liquidations'] for r in results]
avg_hd = [r['avg_hold_days']  for r in results]

cd = np.column_stack([buf, mdd, sor, cal, liq, avg_hd])
ht = ('<b>Leverage: %{x:.1f}×</b><br>'
      'Annual Return: <b>%{y:.1f}%</b><br>'
      'Safety Buffer: %{customdata[0]:.1f}%<br>'
      'MaxDD (MtM): %{customdata[1]:.1f}%<br>'
      'Sortino: %{customdata[2]:.3f}<br>'
      'Calmar: %{customdata[3]:.3f}<br>'
      'Liquidations: %{customdata[4]:.0f}<br>'
      'Avg Hold: %{customdata[5]:.1f}d'
      '<extra></extra>')

fig = make_subplots(specs=[[{"secondary_y": True}]])

# Primary: annual return
fig.add_trace(go.Scatter(
    x=levs, y=ret, name=f'Annual Return% (SMA {SMA_PERIOD}/{int(TRAIL_PCT*100)}% trail)',
    line=dict(color='#e67e22', width=2.5),
    customdata=cd, hovertemplate=ht,
), secondary_y=False)

# Secondary: safety buffer
fig.add_trace(go.Scatter(
    x=levs, y=buf, name='Safety Buffer% (min margin ratio)',
    line=dict(color='#e67e22', width=1.5, dash='dot'), opacity=0.75,
    hovertemplate='Leverage: %{x:.1f}×<br>Buffer: %{y:.1f}%<extra>Buffer</extra>',
), secondary_y=True)

# BTC B&H reference line
fig.add_trace(go.Scatter(
    x=[levs[0], levs[-1]], y=[ann_bh * 100, ann_bh * 100],
    name=f'BTC B&H {ann_bh*100:.1f}%/yr',
    line=dict(color='#95a5a6', dash='dash', width=1.2),
    hoverinfo='skip',
), secondary_y=False)

# Safety thresholds on secondary y
for thresh, color, lbl in [
    (SAFETY_WARN, '#f39c12', f'{SAFETY_WARN:.0f}% working minimum'),
    (SAFETY_VETO, '#e74c3c', f'{SAFETY_VETO:.0f}% hard floor veto'),
]:
    fig.add_trace(go.Scatter(
        x=[levs[0], levs[-1]], y=[thresh, thresh],
        name=lbl, line=dict(color=color, dash='dash', width=1.5),
        hoverinfo='skip',
    ), secondary_y=True)

# Optimal marker
if opt:
    fig.add_trace(go.Scatter(
        x=[opt['leverage']], y=[opt['annual_return']],
        mode='markers', name=f'★ Optimal {opt["leverage"]:.1f}×',
        marker=dict(symbol='star', size=14, color='#e67e22'),
        hovertemplate=(f'<b>★ Optimal {opt["leverage"]:.1f}×</b><br>'
                       f'Return: {opt["annual_return"]:.1f}%<br>'
                       f'Buffer: {opt["safety_buffer"]:.1f}%<extra></extra>'),
    ), secondary_y=False)

    # Vertical line at optimal
    fig.add_vline(x=opt['leverage'], line_dash='longdash', line_color='#e67e22',
                  line_width=1.5)
    fig.add_annotation(
        x=opt['leverage'], y=1.03, yref='paper',
        text=f'Optimal {opt["leverage"]:.1f}×', xanchor='center',
        font=dict(size=10, color='#a04000'), showarrow=False,
    )

# Warning line — first leverage where buffer drops below 33%
if warn_lev:
    fig.add_vline(x=warn_lev, line_dash='dash', line_color='#f39c12', line_width=1.2)

subtitle_parts = [
    f'BTC SMA {SMA_PERIOD} / {int(TRAIL_PCT*100)}% trailing stop  ·  '
    f'Capital: ${CAPITAL:,.0f}  ·  Interest: {INT_RATE*100:.3f}%/day on borrowed',
    f'Slippage: {STOP_SLIP*100:.2f}% stop / {LIQ_SLIP*100:.1f}% liq  ·  '
    f'Avg hold ~{base["avg_hold_days"]:.0f}d  ·  {base["n_trades"]} trades  ·  '
    f'★ = optimal leverage',
]
if opt:
    subtitle_parts.append(
        f'1× baseline: {base["annual_return"]:.1f}%/yr  →  '
        f'Optimal {opt["leverage"]:.1f}×: {opt["annual_return"]:.1f}%/yr'
    )

fig.update_layout(
    title=dict(
        text='Stage 4a — BTC SMA Annual Return% vs Leverage<br>'
             f'<sup>{"  ·  ".join(subtitle_parts[:2])}</sup>',
        font=dict(size=12, color='#1a1a1a'),
        x=0.5, xanchor='center', y=0.98,
    ),
    height=560, margin=dict(l=70, r=90, t=100, b=60),
    hovermode='x unified', paper_bgcolor='white',
    legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.88)',
                bordercolor='#ccc', borderwidth=1, font=dict(size=10)),
)
fig.update_xaxes(title_text='Leverage (×)', dtick=0.5, gridcolor='#eee')
fig.update_yaxes(title_text='Annual Return%', gridcolor='#eee', secondary_y=False)
fig.update_yaxes(title_text='Safety Buffer% (margin ratio)', gridcolor=None,
                 showgrid=False, secondary_y=True)

out4a = os.path.join(RESULTS_DIR, 'stage4a_btc_leverage.html')
fig.write_html(out4a, include_plotlyjs='cdn',
               config={'displayModeBar': True, 'displaylogo': False,
                       'modeBarButtonsToRemove': ['lasso2d', 'select2d']})
sz4a = os.path.getsize(out4a) / 1024
print(f"  Saved chart → results/stage4a_btc_leverage.html  ({sz4a:.0f} KB)")

print()
print("=" * 70)
print("Stage 4a complete. Awaiting instruction before Stage 4b and 4c.")
print("  Set RUN_4B = True at top of script to run Stage 4b (stability ±1.0×).")
print("  Set RUN_4C = True to run Stage 4c (interest rate sensitivity).")
print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4b — Leverage stability ±1.0x around optimal
# ─────────────────────────────────────────────────────────────────────────────
if RUN_4B:
    if opt is None:
        print("\nStage 4b skipped — no valid optimal found in Stage 4a.")
    else:
        OPT_LEV = opt['leverage']
        LEV_4B = np.round(np.arange(max(0.9, OPT_LEV - 1.0),
                                     min(5.0, OPT_LEV + 1.0) + 0.05, 0.1), 2)

        print()
        print("=" * 70)
        print(f"STAGE 4b — Leverage Stability ±1.0× around Optimal {OPT_LEV:.1f}×")
        print("=" * 70)
        print(f"{'Lev':>5} | {'Annual%':>9} {'MaxDD%':>8} {'Sortino':>8} "
              f"{'Calmar':>7} {'Buffer%':>8} {'Liq':>4}")
        print("-" * 60)

        res4b = []
        for lev in LEV_4B:
            t, mr, nl = run_btc_sma(lev)
            eq = build_lev_equity(t, lev)
            m  = compute_metrics(t, eq, mr, nl)
            res4b.append({'leverage': lev, **m})
            flag = ' ← OPTIMAL' if abs(lev - OPT_LEV) < 0.05 else \
                   (' WARN' if m['safety_buffer'] < SAFETY_WARN else '')
            print(f"{lev:>5.1f} | {m['annual_return']:>9.1f}% {m['max_dd_mtm']:>8.1f}% "
                  f"{m['sortino']:>8.3f} {m['calmar']:>7.3f} "
                  f"{m['safety_buffer']:>7.1f}% {nl:>4}liq{flag}")

        opt_r = next(r for r in res4b if abs(r['leverage'] - OPT_LEV) < 0.05)
        for delta, label in [(-0.1, '−0.1×'), (+0.1, '+0.1×'),
                             (-0.5, '−0.5×'), (+0.5, '+0.5×')]:
            ref_lev = round(OPT_LEV + delta, 1)
            ref = next((r for r in res4b if abs(r['leverage'] - ref_lev) < 0.05), None)
            if ref:
                print(f"  At {ref_lev:.1f}× ({label}): {ref['annual_return']:.1f}%  "
                      f"({ref['annual_return']-opt_r['annual_return']:+.1f}pp vs optimal)")

        # 4b chart
        fig4b = make_subplots(rows=2, cols=1, shared_xaxes=True,
                              vertical_spacing=0.04, row_heights=[0.55, 0.45],
                              subplot_titles=['Annual Return%', 'Safety Buffer%'])
        levs4b = [r['leverage']      for r in res4b]
        ret4b  = [r['annual_return'] for r in res4b]
        buf4b  = [r['safety_buffer'] for r in res4b]
        mdd4b  = [r['max_dd_mtm']   for r in res4b]

        fig4b.add_trace(go.Scatter(x=levs4b, y=ret4b, name='Annual Return%',
            line=dict(color='#e67e22', width=2.5)), row=1, col=1)
        fig4b.add_trace(go.Scatter(x=levs4b, y=mdd4b, name='MaxDD% (MtM)',
            line=dict(color='#e74c3c', width=2.0, dash='dash')), row=1, col=1)
        fig4b.add_trace(go.Scatter(x=levs4b, y=buf4b, name='Safety Buffer%',
            line=dict(color='#27ae60', width=2.0), showlegend=True), row=2, col=1)
        for thresh, color in [(SAFETY_WARN, '#f39c12'), (SAFETY_VETO, '#e74c3c')]:
            fig4b.add_trace(go.Scatter(
                x=[levs4b[0], levs4b[-1]], y=[thresh, thresh],
                line=dict(color=color, dash='dash', width=1.2),
                showlegend=False, hoverinfo='skip',
            ), row=2, col=1)
        fig4b.add_vline(x=OPT_LEV, line_dash='longdash', line_color='#888', line_width=1.2)
        fig4b.add_vrect(x0=OPT_LEV - 0.5, x1=OPT_LEV + 0.5,
                        fillcolor='#fde8cc', opacity=0.4, layer='below', line_width=0,
                        row=1, col=1)
        fig4b.update_layout(
            title=dict(
                text=(f'Stage 4b — BTC SMA Leverage Stability ±1.0× around {OPT_LEV:.1f}×<br>'
                      f'<sup>Amber band = ±0.5× plateau zone  ·  '
                      f'Vertical dashed = optimal {OPT_LEV:.1f}×</sup>'),
                font=dict(size=12), x=0.5, xanchor='center', y=0.98,
            ),
            height=540, hovermode='x unified', paper_bgcolor='white',
            plot_bgcolor='#fafafa', margin=dict(l=70, r=50, t=100, b=50),
            legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.88)',
                        bordercolor='#ccc', borderwidth=1, font=dict(size=10)),
        )
        fig4b.update_xaxes(row=2, col=1, title_text='Leverage (×)', dtick=0.2)
        for row_n in [1, 2]:
            fig4b.update_xaxes(row=row_n, col=1, gridcolor='#e8e8e8')
            fig4b.update_yaxes(row=row_n, col=1, gridcolor='#e8e8e8')

        out4b = os.path.join(RESULTS_DIR, 'stage4b_stability.html')
        fig4b.write_html(out4b, include_plotlyjs='cdn',
                         config={'displayModeBar': True, 'displaylogo': False})
        print(f"\n  Saved → results/stage4b_stability.html  "
              f"({os.path.getsize(out4b)//1024} KB)")
        print("\nStage 4b complete.")


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4c — Interest rate sensitivity at optimal leverage
# ─────────────────────────────────────────────────────────────────────────────
if RUN_4C:
    if opt is None:
        print("\nStage 4c skipped — no valid optimal found in Stage 4a.")
    else:
        OPT_LEV = opt['leverage']
        print()
        print("=" * 70)
        print(f"STAGE 4c — Interest Rate Sensitivity at {OPT_LEV:.1f}×")
        print(f"BTC SMA avg hold {base['avg_hold_days']:.0f}d — "
              f"rate sensitivity higher than ETH ADX (~8d hold)")
        print("=" * 70)

        res4c_full = {}
        for rate, label in zip(INT_RATES_3C, INT_LABELS_3C):
            print(f"\nRate: {label}")
            rows = []
            for lev in LEVERAGES:
                t, mr, nl = run_btc_sma(lev, int_rate=rate)
                eq = build_lev_equity(t, lev, int_rate=rate)
                m  = compute_metrics(t, eq, mr, nl, int_rate=rate)
                rows.append({'leverage': lev, **m})
            res4c_full[rate] = rows

            # Print at optimal
            r_opt = next(r for r in rows if abs(r['leverage'] - OPT_LEV) < 0.05)
            simple_int = CAPITAL * (OPT_LEV - 1.0) * rate * 365
            int_per_trade = base['avg_hold_days'] * rate * (OPT_LEV - 1.0) * 100
            print(f"  {OPT_LEV:.1f}×: {r_opt['annual_return']:.1f}%/yr  "
                  f"MaxDD {r_opt['max_dd_mtm']:.1f}%  Sortino {r_opt['sortino']:.3f}  "
                  f"Int/trade ≈{int_per_trade:.3f}%  Simple int ${simple_int:,.0f}/yr")

        # Summary table
        print()
        print(f"  {'Rate':>25}  {'Annual%':>9}  {'MaxDD%':>8}  {'Sortino':>8}  "
              f"{'Int/trade':>10}  {'Int$/yr':>9}")
        print(f"  {'─'*75}")
        for rate, label in zip(INT_RATES_3C, INT_LABELS_3C):
            r = next(row for row in res4c_full[rate]
                     if abs(row['leverage'] - OPT_LEV) < 0.05)
            int_per_trade = base['avg_hold_days'] * rate * (OPT_LEV - 1.0) * 100
            simple_int = CAPITAL * (OPT_LEV - 1.0) * rate * 365
            print(f"  {label:>25}  {r['annual_return']:>9.1f}%  "
                  f"{r['max_dd_mtm']:>8.1f}%  {r['sortino']:>8.3f}  "
                  f"{int_per_trade:>9.3f}%  ${simple_int:>8,.0f}/yr")

        print(f"\n  Note: int/trade = avg_hold({base['avg_hold_days']:.0f}d) × "
              f"rate × {OPT_LEV-1.0:.1f} borrowed.")
        print(f"  ETH ADX reference: 8d × 0.015%/day × 0.9 = 0.108%/trade.")
        print(f"  BTC SMA at base rate: "
              f"{base['avg_hold_days'] * INT_RATE * (OPT_LEV-1.0) * 100:.3f}%/trade "
              f"— {base['avg_hold_days'] * INT_RATE * (OPT_LEV-1.0) / (8 * INT_RATE * 0.9):.1f}× higher.")

        # 4c chart
        COLORS_4C = ['#2980b9', '#e67e22', '#e74c3c']
        fig4c = go.Figure()
        for (rate, label), color in zip(zip(INT_RATES_3C, INT_LABELS_3C), COLORS_4C):
            rows = res4c_full[rate]
            fig4c.add_trace(go.Scatter(
                x=[r['leverage'] for r in rows],
                y=[r['annual_return'] for r in rows],
                name=label, line=dict(color=color, width=2.0),
                hovertemplate=(f'<b>%{{x:.1f}}×</b><br>'
                               f'Return: %{{y:.1f}}%<extra>{label}</extra>'),
            ))
        fig4c.add_vline(x=OPT_LEV, line_dash='longdash', line_color='#888', line_width=1.2)
        fig4c.update_layout(
            title=dict(
                text=(f'Stage 4c — BTC SMA Interest Rate Sensitivity at {OPT_LEV:.1f}×<br>'
                      f'<sup>Avg hold {base["avg_hold_days"]:.0f}d — rate sensitivity '
                      f'{base["avg_hold_days"]*INT_RATE*(OPT_LEV-1.0)/(8*INT_RATE*0.9):.1f}× '
                      f'higher than ETH ADX  ·  Vertical = optimal {OPT_LEV:.1f}×</sup>'),
                font=dict(size=12), x=0.5, xanchor='center', y=0.98,
            ),
            height=480, hovermode='x unified', paper_bgcolor='white',
            plot_bgcolor='#fafafa', margin=dict(l=70, r=50, t=100, b=55),
            legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.88)',
                        bordercolor='#ccc', borderwidth=1),
        )
        fig4c.update_xaxes(title_text='Leverage (×)', dtick=0.5, gridcolor='#eee')
        fig4c.update_yaxes(title_text='Annual Return%', gridcolor='#eee')

        out4c = os.path.join(RESULTS_DIR, 'stage4c_rate_sensitivity.html')
        fig4c.write_html(out4c, include_plotlyjs='cdn',
                         config={'displayModeBar': True, 'displaylogo': False})
        print(f"\n  Saved → results/stage4c_rate_sensitivity.html  "
              f"({os.path.getsize(out4c)//1024} KB)")
        print("\nStage 4c complete.")
