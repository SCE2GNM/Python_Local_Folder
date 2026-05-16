#!/usr/bin/env python3
"""
BTC ADX 19/14 — Stage A: Stop Type and Parameter Optimisation Grid Search

Tests three stop families against the fixed ADX 19/14 signal:
  - Fixed percentage stops: 3%, 5%, 8%, 10%
  - Percentage trailing stops: 5%, 8%, 10%, 12%
  - ATR trailing stops: period 9 or 14, multiplier 2.0×, 2.5×, 3.0×

Methodology (non-negotiable, consistent with Week 6 ETH ADX pipeline):
  - Bar-by-bar simulation, stop checked vs daily LOW (gap protection)
  - 0.15% round-trip transaction costs per trade
  - Daily mark-to-market equity curve for all ratio metrics
  - Sortino and Sharpe derived from daily equity curve (not per-trade)
  - Entry at close of signal bar

Signal: ADX period=14 (Wilder), threshold=19, +DI > -DI
Data: BTC-USD daily from Yahoo Finance, 2018-01-01 to present

Output: results/btc_adx_stageA_results.csv
"""

import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator

warnings.filterwarnings('ignore')

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
os.makedirs(RESULTS_DIR, exist_ok=True)

COSTS   = 0.0015   # 0.15% round-trip
ADX_WIN = 14       # BTC: longer period vs ETH (9) — filters slower BTC trend noise
ADX_THR = 19       # threshold confirmed from prior Week 5 analysis


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA
# ─────────────────────────────────────────────────────────────────────────────

print("\nFetching BTC-USD daily data...")
raw = yf.download('BTC-USD', start='2018-01-01', auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)

df     = raw[['High', 'Low', 'Close']].copy().dropna()
closes = df['Close'].values.astype(float)
highs  = df['High'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index
N      = len(df)
YEARS  = (dates[-1] - dates[0]).days / 365.25
print(f"Data: {dates[0].date()} → {dates[-1].date()}  ({YEARS:.2f} yrs, {N} bars)")


# ─────────────────────────────────────────────────────────────────────────────
# 2. INDICATORS
# ─────────────────────────────────────────────────────────────────────────────

print(f"Computing ADX {ADX_THR}/{ADX_WIN} signals...")
_adx     = ADXIndicator(df['High'], df['Low'], df['Close'], window=ADX_WIN, fillna=False)
adx_v    = _adx.adx().values
plus_di  = _adx.adx_pos().values
minus_di = _adx.adx_neg().values
signal   = (adx_v >= ADX_THR) & (plus_di > minus_di)


def calc_atr(period: int) -> np.ndarray:
    """Wilder's ATR using EWM (alpha=1/period), consistent with ta library."""
    prev_close = np.roll(closes, 1)
    prev_close[0] = closes[0]
    tr = np.maximum(highs - lows,
         np.maximum(np.abs(highs - prev_close),
                    np.abs(lows  - prev_close)))
    return pd.Series(tr).ewm(alpha=1 / period, min_periods=period,
                              adjust=False).mean().values

atr = {p: calc_atr(p) for p in [9, 14]}


# ─────────────────────────────────────────────────────────────────────────────
# 3. BACKTEST FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def run_fixed(stop_pct: float) -> list:
    """Fixed stop — does not move after entry."""
    pos = 0; ep = stop = 0.0; ed = None
    trades = []
    for i in range(1, N):
        lo = lows[i]; cl = closes[i]
        if pos == 1:
            if lo <= stop:
                trades.append({'entry_date': ed, 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': stop,
                                'return': (stop - ep) / ep, 'exit_reason': 'STOP'})
                pos = 0; ed = None
            elif not signal[i]:
                trades.append({'entry_date': ed, 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'ADX_EXIT'})
                pos = 0; ed = None
        elif signal[i]:
            ep = cl; stop = cl * (1 - stop_pct); ed = dates[i]; pos = 1
    return trades


def run_pct_trail(trail_pct: float) -> list:
    """Percentage trailing stop — ratchets up with peak price on close."""
    pos = 0; ep = peak = stop = 0.0; ed = None
    trades = []
    for i in range(1, N):
        lo = lows[i]; cl = closes[i]
        if pos == 1:
            if lo <= stop:
                trades.append({'entry_date': ed, 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': stop,
                                'return': (stop - ep) / ep, 'exit_reason': 'TRAIL_STOP'})
                pos = 0; ed = None
            elif not signal[i]:
                trades.append({'entry_date': ed, 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'ADX_EXIT'})
                pos = 0; ed = None
            else:
                if cl > peak:
                    peak = cl
                    stop = peak * (1 - trail_pct)
        elif signal[i]:
            ep = cl; peak = cl; stop = cl * (1 - trail_pct); ed = dates[i]; pos = 1
    return trades


def run_atr_trail(atr_period: int, multiplier: float) -> list:
    """ATR trailing stop — ratchets up only (stop never decreases)."""
    atr_arr = atr[atr_period]
    pos = 0; ep = peak = stop = 0.0; ed = None
    trades = []
    for i in range(1, N):
        lo = lows[i]; cl = closes[i]
        if pos == 1:
            if lo <= stop:
                trades.append({'entry_date': ed, 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': stop,
                                'return': (stop - ep) / ep, 'exit_reason': 'TRAIL_STOP'})
                pos = 0; ed = None
            elif not signal[i]:
                trades.append({'entry_date': ed, 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': cl,
                                'return': (cl - ep) / ep, 'exit_reason': 'ADX_EXIT'})
                pos = 0; ed = None
            else:
                if cl > peak:
                    peak = cl
                new_stop = peak - multiplier * atr_arr[i]
                if new_stop > stop:
                    stop = new_stop
        elif signal[i]:
            ep = cl; peak = cl
            stop = cl - multiplier * atr_arr[i]
            ed = dates[i]; pos = 1
    return trades


# ─────────────────────────────────────────────────────────────────────────────
# 4. EQUITY CURVE AND METRICS
# ─────────────────────────────────────────────────────────────────────────────

def build_equity_curve(trades: list) -> np.ndarray:
    """Daily mark-to-market equity curve. Costs deducted at exit."""
    date_to_i = pd.Series(np.arange(N), index=df.index)
    equity    = np.ones(N)
    portfolio = 1.0
    prev_i    = 0
    for t in trades:
        ei = date_to_i.get(pd.Timestamp(t['entry_date']))
        xi = date_to_i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None:
            continue
        equity[prev_i:ei]  = portfolio
        equity[ei:xi + 1]  = portfolio * closes[ei:xi + 1] / t['entry_price']
        portfolio          *= (1 + t['return'] - COSTS)
        equity[xi]          = portfolio
        prev_i              = xi + 1
    equity[prev_i:] = portfolio
    return equity


def calc_metrics(trades: list, equity: np.ndarray, label: str) -> dict:
    dr      = np.diff(equity) / equity[:-1]
    down    = dr[dr < 0]
    sortino = (dr.mean() / down.std() * np.sqrt(365)
               if len(down) > 0 and down.std() > 0 else 0.0)
    sharpe  = (dr.mean() / dr.std() * np.sqrt(365)
               if dr.std() > 0 else 0.0)

    peak_eq  = np.maximum.accumulate(equity)
    dd       = (equity - peak_eq) / peak_eq
    mtm_dd   = dd.min()
    annual   = equity[-1] ** (1 / YEARS) - 1
    calmar   = annual / abs(mtm_dd) if mtm_dd != 0 else 0.0

    n = len(trades)
    if n > 0:
        net     = pd.DataFrame(trades)['return'].values - COSTS
        winners = net[net > 0]; losers = net[net <= 0]
        wr      = len(winners) / n
        avg_w   = winners.mean() if len(winners) > 0 else 0.0
        avg_l   = losers.mean()  if len(losers)  > 0 else 0.0
        stop_ex = sum(1 for t in trades if t['exit_reason'] in ('STOP', 'TRAIL_STOP'))
    else:
        wr = avg_w = avg_l = stop_ex = 0

    return {
        'label':        label,
        'annual_return': annual,
        'mtm_max_dd':   mtm_dd,
        'sortino':      sortino,
        'sharpe':       sharpe,
        'calmar':       calmar,
        'n_trades':     n,
        'win_rate':     wr,
        'avg_win':      avg_w,
        'avg_loss':     avg_l,
        'stop_exit_pct': stop_ex / n if n > 0 else 0.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. GRID SEARCH
# ─────────────────────────────────────────────────────────────────────────────

results = []

print("\nRunning grid search...")

# Fixed stops
for sp in [0.03, 0.05, 0.08, 0.10]:
    trades = run_fixed(sp)
    eq     = build_equity_curve(trades)
    m      = calc_metrics(trades, eq, f'Fixed {int(sp*100)}%')
    results.append(m)
    print(f"  {m['label']:<20}  Ann {m['annual_return']:+.1%}  "
          f"Sortino {m['sortino']:.3f}  Calmar {m['calmar']:.3f}  "
          f"MaxDD {m['mtm_max_dd']:.1%}  Trades {m['n_trades']}")

# Percentage trailing stops
for tp in [0.05, 0.08, 0.10, 0.12]:
    trades = run_pct_trail(tp)
    eq     = build_equity_curve(trades)
    m      = calc_metrics(trades, eq, f'Pct Trail {int(tp*100)}%')
    results.append(m)
    print(f"  {m['label']:<20}  Ann {m['annual_return']:+.1%}  "
          f"Sortino {m['sortino']:.3f}  Calmar {m['calmar']:.3f}  "
          f"MaxDD {m['mtm_max_dd']:.1%}  Trades {m['n_trades']}")

# ATR trailing stops
for atr_per in [9, 14]:
    for mult in [2.0, 2.5, 3.0]:
        trades = run_atr_trail(atr_per, mult)
        eq     = build_equity_curve(trades)
        m      = calc_metrics(trades, eq, f'ATR {atr_per}/{mult}x')
        results.append(m)
        print(f"  {m['label']:<20}  Ann {m['annual_return']:+.1%}  "
              f"Sortino {m['sortino']:.3f}  Calmar {m['calmar']:.3f}  "
              f"MaxDD {m['mtm_max_dd']:.1%}  Trades {m['n_trades']}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. YEAR-BY-YEAR RETURNS (for regime analysis)
# ─────────────────────────────────────────────────────────────────────────────

def year_returns(equity: np.ndarray) -> dict:
    result = {}
    for yr in sorted(set(d.year for d in dates)):
        idx = [i for i, d in enumerate(dates) if d.year == yr]
        if idx:
            result[yr] = equity[idx[-1]] / equity[idx[0]] - 1
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 7. RESULTS
# ─────────────────────────────────────────────────────────────────────────────

df_out = pd.DataFrame(results).sort_values('sortino', ascending=False)
out_path = os.path.join(RESULTS_DIR, 'btc_adx_stageA_results.csv')
df_out.to_csv(out_path, index=False)

print(f"\n{'='*80}")
print(f"STAGE A RESULTS — ranked by Sortino (primary), Calmar shown as reference")
print(f"{'='*80}")
hdr = f"  {'Stop Config':<20} {'Annual':>8} {'MtM DD':>8} {'Sortino':>8} {'Calmar':>8} {'Trades':>7} {'WR':>7} {'StopEx':>7}"
print(hdr)
print(f"  {'-'*78}")
for _, r in df_out.iterrows():
    print(f"  {r['label']:<20} {r['annual_return']:>+8.1%} {r['mtm_max_dd']:>8.1%} "
          f"{r['sortino']:>8.3f} {r['calmar']:>8.3f} {r['n_trades']:>7} "
          f"{r['win_rate']:>7.1%} {r['stop_exit_pct']:>7.1%}")

# Post-2022 regime check for the top candidate
print(f"\n── Post-2022 Regime Check (top candidate by Sortino) ────────────────────────")
top_label = df_out.iloc[0]['label']

# Re-run the top candidate to get year-by-year equity
top_row = df_out.iloc[0]
if 'Fixed' in top_label:
    pct = int(top_label.split()[1].replace('%', '')) / 100
    top_trades = run_fixed(pct)
elif 'Pct Trail' in top_label:
    pct = int(top_label.split()[2].replace('%', '')) / 100
    top_trades = run_pct_trail(pct)
else:
    parts = top_label.split('/')
    per   = int(parts[0].replace('ATR ', ''))
    mult  = float(parts[1].replace('x', ''))
    top_trades = run_atr_trail(per, mult)

top_eq = build_equity_curve(top_trades)
yr_ret = year_returns(top_eq)

# BTC B&H year returns for comparison
bh_eq  = closes / closes[0]
bh_yr  = year_returns(bh_eq)

all_years = sorted(yr_ret.keys())
print(f"  {'Year':<6} {top_label:>20} {'BTC B&H':>10}")
for yr in all_years:
    print(f"  {yr:<6} {yr_ret.get(yr, 0):>+20.1%} {bh_yr.get(yr, 0):>+10.1%}")

pre_2022  = [v for yr, v in yr_ret.items() if yr <= 2021]
post_2022 = [v for yr, v in yr_ret.items() if yr >= 2022]
if pre_2022:
    pre_ann  = (np.prod([1 + r for r in pre_2022]) ** (1 / len(pre_2022))) - 1
    print(f"\n  2018–2021 avg annual: {pre_ann:+.1%}")
if post_2022:
    post_ann = (np.prod([1 + r for r in post_2022]) ** (1 / len(post_2022))) - 1
    print(f"  2022–present avg annual: {post_ann:+.1%}")

print(f"\n✅ Results saved → {out_path}")
print(f"{'='*80}\n")
