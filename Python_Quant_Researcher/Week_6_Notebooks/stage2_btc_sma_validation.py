# Stage 2 — BTC SMA 125 Complete Validation
# Week 6 Optimisation Plan
#
# Strategy: BTC-USD SMA crossover with trailing stop
#   Entry:  close crosses ABOVE N-day SMA (strict crossover — not just being above)
#   Exit:   close crosses BELOW N-day SMA  OR  trailing stop hit on daily LOW
#
# Stages:
#   2a — Pct trailing stop grid   (SMA 80-170 × trail 5-20%)
#   2b — ATR trailing stop grid   (SMA × ATR period × multiplier)
#   2c — Stability analysis        (param sweep + year-by-year + half-split)
#   2d — Walk-forward validation   (3 expanding windows)
#   2e — Cross-asset check         (best BTC params on ETH-USD)
#   final — Comparison table + equity chart + go/no-go
#
# STOP_AFTER_STAGE: set to pause after a stage, awaiting instruction.
#   Values: '2a' | '2b' | '2c' | '2d' | '2e' | 'final' | None

import sys, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import yfinance as yf
from ta.trend import ADXIndicator
from itertools import product

# ---------------------------------------------------------------------------
# Control
# ---------------------------------------------------------------------------

STOP_AFTER_STAGE = '2a'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COST_PER_TRADE   = 0.00075 * 2              # 0.15% round-trip
MIN_TRADES       = 5                        # minimum for metric computation
LOW_TRADES_FLAG  = 30                       # flag if n < 30
CALMAR_THRESHOLD = 1.5                      # stability score threshold

SMA_PERIODS = list(range(80, 171, 5))                   # 19 values
TRAIL_PCTS  = [round(x, 4) for x in np.arange(0.05, 0.201, 0.025)]  # 7 values → 133 combos
ATR_PERIODS = list(range(7, 22, 2))                     # 8 values
ATR_MULTS   = [round(x, 1) for x in np.arange(1.5, 4.1, 0.5)]       # 6 values → 912 combos

# BTC ADX reference params for final comparison (user-specified; Week 5 optimum was 16/8)
BTC_ADX_THRESHOLD = 19
BTC_ADX_PERIOD    = 14
BTC_ADX_STOP_PCT  = 0.05

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

print("Fetching BTC-USD daily data...")
raw_btc = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw_btc.columns, pd.MultiIndex):
    raw_btc.columns = raw_btc.columns.droplevel(1)
df_btc = raw_btc[['Open', 'High', 'Low', 'Close']].dropna().copy()
df_btc.index = pd.to_datetime(df_btc.index)
print(f"  BTC: {df_btc.index[0].date()} → {df_btc.index[-1].date()} ({len(df_btc)} bars)")

closes_btc = df_btc['Close'].values.astype(float)
highs_btc  = df_btc['High'].values.astype(float)
lows_btc   = df_btc['Low'].values.astype(float)
dates_btc  = df_btc.index
years_btc  = (df_btc.index[-1] - df_btc.index[0]).days / 365.25

# ---------------------------------------------------------------------------
# Helper: compute ATR (Wilder EWM)
# ---------------------------------------------------------------------------

def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    n  = len(closes)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i]  - closes[i - 1]),
        )
    return pd.Series(tr).ewm(alpha=1.0 / period, adjust=False).mean().values


# ---------------------------------------------------------------------------
# Helper: build daily mark-to-market equity curve
# ---------------------------------------------------------------------------

def build_daily_equity(trades_df: pd.DataFrame, close_series: pd.Series) -> np.ndarray:
    n          = len(close_series)
    closes_arr = close_series.values
    date_to_i  = pd.Series(np.arange(n), index=close_series.index)
    equity     = np.ones(n)
    portfolio  = 1.0
    prev_i     = 0

    for _, trade in trades_df.iterrows():
        ei = date_to_i.get(pd.Timestamp(trade['entry_date']))
        xi = date_to_i.get(pd.Timestamp(trade['exit_date']))
        if ei is None or xi is None:
            continue
        equity[prev_i : ei]  = portfolio
        equity[ei : xi + 1]  = portfolio * closes_arr[ei : xi + 1] / trade['entry_price']
        portfolio            *= (1 + trade['return'] - COST_PER_TRADE)
        equity[xi]            = portfolio
        prev_i                = xi + 1

    equity[prev_i:] = portfolio
    return equity


# ---------------------------------------------------------------------------
# Helper: compute metrics from trade list
# ---------------------------------------------------------------------------

def metrics_from_trades(trades: list, years: float, close_series: pd.Series) -> dict | None:
    if len(trades) < MIN_TRADES:
        return None

    df_t = pd.DataFrame(trades)
    df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
    df_t['exit_date']  = pd.to_datetime(df_t['exit_date'])
    df_t = df_t.sort_values('entry_date').reset_index(drop=True)

    returns      = df_t['return'].values - COST_PER_TRADE
    winners_mask = returns > 0
    losers_mask  = returns <= 0

    win_rate      = winners_mask.sum() / len(returns)
    gross_profit  = returns[winners_mask].sum() if winners_mask.any() else 0.0
    gross_loss    = abs(returns[losers_mask].sum()) if losers_mask.any() else 1e-9
    profit_factor = gross_profit / gross_loss
    avg_win       = returns[winners_mask].mean() if winners_mask.any() else 0.0
    avg_loss      = returns[losers_mask].mean()  if losers_mask.any() else 0.0

    total_return  = np.prod(1 + returns) - 1
    annual_return = (1 + total_return) ** (1 / years) - 1

    cum_eq = np.cumprod(1 + returns)
    peak   = np.maximum.accumulate(cum_eq)
    max_dd = ((cum_eq - peak) / peak).min()
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    first_entry = df_t['entry_date'].min()
    last_exit   = df_t['exit_date'].max()
    close_slice = close_series.loc[first_entry : last_exit]

    daily_eq = build_daily_equity(df_t, close_slice)
    dr       = np.diff(daily_eq) / daily_eq[:-1]
    downside = dr[dr < 0]

    sharpe  = dr.mean() / dr.std()       * np.sqrt(365) if dr.std()  > 0                          else 0.0
    sortino = dr.mean() / downside.std() * np.sqrt(365) if (len(downside) > 0 and downside.std() > 0) else 0.0

    stop_pct = 0.0
    if 'exit_reason' in df_t.columns:
        stop_pct = (df_t['exit_reason'] == 'TRAIL_STOP').sum() / len(df_t) * 100

    return {
        'total_trades':  len(trades),
        'win_rate':      win_rate,
        'avg_win':       avg_win,
        'avg_loss':      avg_loss,
        'profit_factor': profit_factor,
        'annual_return': annual_return,
        'max_drawdown':  max_dd,
        'calmar':        calmar,
        'sharpe':        sharpe,
        'sortino':       sortino,
        'stop_exit_pct': stop_pct,
        'low_trades':    len(trades) < LOW_TRADES_FLAG,
    }


# ---------------------------------------------------------------------------
# Backtest: SMA crossover + percentage trailing stop
#
# Entry:  close[i] > sma[i]  AND  close[i-1] <= sma[i-1]   (fresh crossover)
# Exit:   close[i] < sma[i]  (level exit)  OR  low[i] <= stop  (checked first)
# Note:   level exit and crossover exit are equivalent here — after a crossover
#         entry, sig_prev is always True, so any close < sma satisfies both.
# ---------------------------------------------------------------------------

def run_sma_pct_trail(
    closes:    np.ndarray,
    lows:      np.ndarray,
    dates:     pd.DatetimeIndex,
    sma_vals:  np.ndarray,
    trail_pct: float,
) -> list:
    first_valid = int(np.argmax(~np.isnan(sma_vals)))

    position    = 0
    entry_i     = 0
    entry_price = 0.0
    peak_price  = 0.0
    stop_price  = 0.0
    trades      = []
    sig_prev    = False

    for i in range(first_valid, len(closes)):
        close   = closes[i]
        low     = lows[i]
        sma_val = sma_vals[i]
        if np.isnan(sma_val):
            continue

        sig_cur   = close > sma_val
        crossover = sig_cur and not sig_prev

        if position == 1:
            # Ratchet stop upward only
            if close > peak_price:
                peak_price = close
                stop_price = peak_price * (1 - trail_pct)

            # Stop checked against daily LOW first
            if low <= stop_price:
                trades.append({
                    'entry_date':  dates[entry_i],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'TRAIL_STOP',
                })
                position = 0

            elif not sig_cur:
                trades.append({
                    'entry_date':  dates[entry_i],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'SMA_EXIT',
                })
                position = 0

        if position == 0 and crossover:
            position    = 1
            entry_i     = i
            entry_price = close
            peak_price  = close
            stop_price  = close * (1 - trail_pct)

        sig_prev = sig_cur

    if position == 1:
        trades.append({
            'entry_date':  dates[entry_i],
            'entry_price': entry_price,
            'exit_date':   dates[-1],
            'exit_price':  closes[-1],
            'return':      (closes[-1] - entry_price) / entry_price,
            'exit_reason': 'END',
        })

    return trades


# ---------------------------------------------------------------------------
# Backtest: SMA crossover + ATR trailing stop
# ---------------------------------------------------------------------------

def run_sma_atr_trail(
    closes:   np.ndarray,
    lows:     np.ndarray,
    dates:    pd.DatetimeIndex,
    sma_vals: np.ndarray,
    atr_vals: np.ndarray,
    atr_mult: float,
) -> list:
    first_valid = int(np.argmax(~np.isnan(sma_vals)))

    position    = 0
    entry_i     = 0
    entry_price = 0.0
    peak_price  = 0.0
    stop_price  = 0.0
    trades      = []
    sig_prev    = False

    for i in range(first_valid, len(closes)):
        close   = closes[i]
        low     = lows[i]
        sma_val = sma_vals[i]
        atr_val = atr_vals[i]
        if np.isnan(sma_val) or np.isnan(atr_val) or atr_val <= 0:
            continue

        sig_cur   = close > sma_val
        crossover = sig_cur and not sig_prev

        if position == 1:
            if close > peak_price:
                peak_price = close
            new_stop = peak_price - atr_mult * atr_val
            if new_stop > stop_price:
                stop_price = new_stop

            if low <= stop_price:
                trades.append({
                    'entry_date':  dates[entry_i],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'TRAIL_STOP',
                })
                position = 0

            elif not sig_cur:
                trades.append({
                    'entry_date':  dates[entry_i],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'SMA_EXIT',
                })
                position = 0

        if position == 0 and crossover:
            position    = 1
            entry_i     = i
            entry_price = close
            peak_price  = close
            stop_price  = close - atr_mult * atr_val

        sig_prev = sig_cur

    if position == 1:
        trades.append({
            'entry_date':  dates[entry_i],
            'entry_price': entry_price,
            'exit_date':   dates[-1],
            'exit_price':  closes[-1],
            'return':      (closes[-1] - entry_price) / entry_price,
            'exit_reason': 'END',
        })

    return trades


# ---------------------------------------------------------------------------
# Backtest: BTC ADX fixed stop (final comparison reference)
# ---------------------------------------------------------------------------

def run_btc_adx_fixed(df: pd.DataFrame) -> list:
    adx_ind  = ADXIndicator(
        high=df['High'], low=df['Low'], close=df['Close'],
        window=BTC_ADX_PERIOD, fillna=False,
    )
    signals = np.where(
        (adx_ind.adx().values > BTC_ADX_THRESHOLD) &
        (adx_ind.adx_pos().values > adx_ind.adx_neg().values), 1, 0
    )
    closes = df['Close'].values.astype(float)
    lows   = df['Low'].values.astype(float)
    dates  = df.index

    position    = 0
    entry_i     = 0
    entry_price = 0.0
    stop_price  = 0.0
    trades      = []

    for i in range(1, len(closes)):
        close, low = closes[i], lows[i]
        if position == 1:
            if low <= stop_price:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                                'exit_date': dates[i], 'exit_price': stop_price,
                                'return': (stop_price - entry_price) / entry_price,
                                'exit_reason': 'STOP'})
                position = 0
            elif signals[i] == 0:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                                'exit_date': dates[i], 'exit_price': close,
                                'return': (close - entry_price) / entry_price,
                                'exit_reason': 'SIGNAL'})
                position = 0
        if position == 0 and signals[i] == 1:
            position = 1; entry_i = i; entry_price = close
            stop_price = close * (1 - BTC_ADX_STOP_PCT)

    if position == 1:
        trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                        'exit_date': dates[-1], 'exit_price': closes[-1],
                        'return': (closes[-1] - entry_price) / entry_price,
                        'exit_reason': 'END'})
    return trades


# ---------------------------------------------------------------------------
# Pre-compute caches
# ---------------------------------------------------------------------------

print("Pre-computing SMA arrays...")
sma_cache = {p: pd.Series(closes_btc).rolling(p, min_periods=p).mean().values for p in SMA_PERIODS}

print("Pre-computing ATR arrays...")
atr_cache = {p: compute_atr(highs_btc, lows_btc, closes_btc, p) for p in ATR_PERIODS}

# ===========================================================================
# STAGE 2a — SMA × Percentage Trailing Stop Grid
# ===========================================================================

print("\n" + "=" * 72)
print("STAGE 2a — SMA × Percentage Trailing Stop Grid")
print(f"  {len(SMA_PERIODS)} SMA periods × {len(TRAIL_PCTS)} trail pcts = "
      f"{len(SMA_PERIODS) * len(TRAIL_PCTS)} combos  |  costs: {COST_PER_TRADE*100:.2f}% r/t")
print("=" * 72)

rows_2a = []
combos_2a = list(product(SMA_PERIODS, TRAIL_PCTS))
for idx, (sma_p, trail_p) in enumerate(combos_2a):
    if idx % 25 == 24:
        print(f"  {idx+1}/{len(combos_2a)}...")
    trades = run_sma_pct_trail(closes_btc, lows_btc, dates_btc, sma_cache[sma_p], trail_p)
    m = metrics_from_trades(trades, years_btc, df_btc['Close'])
    if m is None:
        continue
    rows_2a.append({
        'sma_period':    sma_p,
        'trail_pct':     round(trail_p * 100, 2),
        'total_trades':  m['total_trades'],
        'win_rate':      round(m['win_rate'] * 100, 1),
        'avg_win':       round(m['avg_win'] * 100, 2),
        'avg_loss':      round(m['avg_loss'] * 100, 2),
        'profit_factor': round(m['profit_factor'], 3),
        'annual_return': round(m['annual_return'] * 100, 1),
        'max_drawdown':  round(m['max_drawdown'] * 100, 1),
        'calmar':        round(m['calmar'], 3),
        'sharpe':        round(m['sharpe'], 3),
        'sortino':       round(m['sortino'], 3),
        'stop_exit_pct': round(m['stop_exit_pct'], 1),
        'low_trades':    m['low_trades'],
    })

df_2a = pd.DataFrame(rows_2a).sort_values('calmar', ascending=False).reset_index(drop=True)
df_2a.to_csv(os.path.join(DATA_DIR, 'stage2a_results.csv'), index=False)
print(f"\n  {len(df_2a)} valid combos. Saved → data/stage2a_results.csv")

print("\n--- Stage 2a: Top 10 by Calmar ---")
H = f"{'Rk':>2}  {'SMA':>4}  {'Trail%':>6}  {'n':>4}  {'Win%':>5}  {'PF':>5}  {'Ann%':>6}  {'MaxDD%':>7}  {'Calmar':>7}  {'Sortino':>7}  {'Stop%':>5}"
print(H); print("-" * len(H))
for rk, (_, row) in enumerate(df_2a.head(10).iterrows(), 1):
    flag = " !" if row['low_trades'] else ""
    print(f"{rk:>2}  {int(row['sma_period']):>4}  {row['trail_pct']:>6.2f}  "
          f"{int(row['total_trades']):>4}  {row['win_rate']:>5.1f}  {row['profit_factor']:>5.3f}  "
          f"{row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  {row['calmar']:>7.3f}  "
          f"{row['sortino']:>7.3f}  {row['stop_exit_pct']:>5.1f}{flag}")

print("\n--- SMA 125 across all trail_pcts ---")
s125 = df_2a[df_2a['sma_period'] == 125].sort_values('trail_pct')
H2 = f"{'Trail%':>6}  {'n':>4}  {'Win%':>5}  {'PF':>5}  {'Ann%':>6}  {'MaxDD%':>7}  {'Calmar':>7}  {'Sortino':>7}"
print(H2); print("-" * len(H2))
for _, row in s125.iterrows():
    print(f"{row['trail_pct']:>6.2f}  {int(row['total_trades']):>4}  {row['win_rate']:>5.1f}  "
          f"{row['profit_factor']:>5.3f}  {row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  "
          f"{row['calmar']:>7.3f}  {row['sortino']:>7.3f}")

best_2a = df_2a.iloc[0]
print(f"\n  Stage 2a best: SMA {int(best_2a['sma_period'])} / trail {best_2a['trail_pct']:.2f}%  "
      f"→  Calmar {best_2a['calmar']:.3f}  Ann {best_2a['annual_return']:.1f}%  "
      f"MaxDD {best_2a['max_drawdown']:.1f}%  n={int(best_2a['total_trades'])}"
      + (" [!low n]" if best_2a['low_trades'] else ""))

if STOP_AFTER_STAGE == '2a':
    print("\n[Paused after Stage 2a — awaiting instruction to continue.]")
    sys.exit(0)

# ===========================================================================
# STAGE 2b — SMA × ATR Trailing Stop Grid
# ===========================================================================

print("\n" + "=" * 72)
print("STAGE 2b — SMA × ATR Trailing Stop Grid")
print(f"  {len(SMA_PERIODS)} SMA × {len(ATR_PERIODS)} ATR periods × {len(ATR_MULTS)} mults = "
      f"{len(SMA_PERIODS)*len(ATR_PERIODS)*len(ATR_MULTS)} combos")
print("=" * 72)

rows_2b = []
combos_2b = list(product(SMA_PERIODS, ATR_PERIODS, ATR_MULTS))
for idx, (sma_p, atr_p, atr_m) in enumerate(combos_2b):
    if idx % 100 == 99:
        print(f"  {idx+1}/{len(combos_2b)}...")
    trades = run_sma_atr_trail(closes_btc, lows_btc, dates_btc,
                                sma_cache[sma_p], atr_cache[atr_p], atr_m)
    m = metrics_from_trades(trades, years_btc, df_btc['Close'])
    if m is None:
        continue
    rows_2b.append({
        'sma_period':    sma_p,
        'atr_period':    atr_p,
        'atr_mult':      atr_m,
        'total_trades':  m['total_trades'],
        'win_rate':      round(m['win_rate'] * 100, 1),
        'avg_win':       round(m['avg_win'] * 100, 2),
        'avg_loss':      round(m['avg_loss'] * 100, 2),
        'profit_factor': round(m['profit_factor'], 3),
        'annual_return': round(m['annual_return'] * 100, 1),
        'max_drawdown':  round(m['max_drawdown'] * 100, 1),
        'calmar':        round(m['calmar'], 3),
        'sharpe':        round(m['sharpe'], 3),
        'sortino':       round(m['sortino'], 3),
        'stop_exit_pct': round(m['stop_exit_pct'], 1),
        'low_trades':    m['low_trades'],
    })

df_2b = pd.DataFrame(rows_2b).sort_values('calmar', ascending=False).reset_index(drop=True)
df_2b.to_csv(os.path.join(DATA_DIR, 'stage2b_results.csv'), index=False)
print(f"\n  {len(df_2b)} valid combos. Saved → data/stage2b_results.csv")

print("\n--- Stage 2b: Top 10 by Calmar ---")
H3 = f"{'Rk':>2}  {'SMA':>4}  {'ATRp':>4}  {'Mult':>4}  {'n':>4}  {'Win%':>5}  {'PF':>5}  {'Ann%':>6}  {'MaxDD%':>7}  {'Calmar':>7}  {'Sortino':>7}  {'Stop%':>5}"
print(H3); print("-" * len(H3))
for rk, (_, row) in enumerate(df_2b.head(10).iterrows(), 1):
    flag = " !" if row['low_trades'] else ""
    print(f"{rk:>2}  {int(row['sma_period']):>4}  {int(row['atr_period']):>4}  {row['atr_mult']:>4.1f}  "
          f"{int(row['total_trades']):>4}  {row['win_rate']:>5.1f}  {row['profit_factor']:>5.3f}  "
          f"{row['annual_return']:>6.1f}  {row['max_drawdown']:>7.1f}  {row['calmar']:>7.3f}  "
          f"{row['sortino']:>7.3f}  {row['stop_exit_pct']:>5.1f}{flag}")

best_2b = df_2b.iloc[0]
print(f"\n  Stage 2b best: SMA {int(best_2b['sma_period'])} / ATR {int(best_2b['atr_period'])} / "
      f"mult {best_2b['atr_mult']}  →  Calmar {best_2b['calmar']:.3f}  "
      f"Ann {best_2b['annual_return']:.1f}%  MaxDD {best_2b['max_drawdown']:.1f}%  "
      f"n={int(best_2b['total_trades'])}" + (" [!low n]" if best_2b['low_trades'] else ""))

if STOP_AFTER_STAGE == '2b':
    print("\n[Paused after Stage 2b — awaiting instruction to continue.]")
    sys.exit(0)

# ===========================================================================
# STAGE 2c — Stability Analysis
# ===========================================================================

print("\n" + "=" * 72)
print("STAGE 2c — Stability Analysis")
print("=" * 72)

CAND_A_SMA   = int(best_2a['sma_period'])
CAND_A_TRAIL = round(best_2a['trail_pct'] / 100.0, 4)
CAND_B_SMA   = int(best_2b['sma_period'])
CAND_B_ATR   = int(best_2b['atr_period'])
CAND_B_MULT  = best_2b['atr_mult']

print(f"\n  Candidate A (pct): SMA {CAND_A_SMA} / trail {CAND_A_TRAIL*100:.2f}%")
print(f"  Candidate B (ATR): SMA {CAND_B_SMA} / ATR {CAND_B_ATR} / mult {CAND_B_MULT}")


def param_sweep_1d(label: str, param_values: list, run_fn, threshold: float) -> float:
    """Vary one parameter, print Calmar per value, return stability % (fraction above threshold)."""
    n_above = 0
    print(f"    {label}")
    for v in param_values:
        trades_s = run_fn(v)
        m_s = metrics_from_trades(trades_s, years_btc, df_btc['Close'])
        calmar = m_s['calmar'] if m_s else 0.0
        n_trades = m_s['total_trades'] if m_s else 0
        above = calmar >= threshold
        n_above += above
        marker = ">" if above else " "
        flag   = " [!n]" if (m_s and m_s['low_trades']) else ""
        print(f"      {marker} {str(v):>8}  Calmar {calmar:>7.3f}  n={n_trades:>3}{flag}")
    pct = n_above / len(param_values) * 100
    print(f"      Stability: {n_above}/{len(param_values)} values ≥ {threshold} Calmar = {pct:.0f}%")
    return pct


def year_by_year_breakdown(trades_list: list, close_series: pd.Series) -> tuple[dict, float]:
    """Return per-year metrics dict and stability score (% years with Calmar >= threshold)."""
    if not trades_list:
        return {}, 0.0
    df_t = pd.DataFrame(trades_list)
    df_t['exit_date'] = pd.to_datetime(df_t['exit_date'])
    df_t['exit_year'] = df_t['exit_date'].dt.year
    results = {}
    for yr, grp in df_t.groupby('exit_year'):
        yr_trades = grp.to_dict('records')
        yr_days   = max(1, (pd.Timestamp(f'{yr}-12-31') - pd.Timestamp(f'{yr}-01-01')).days)
        cs = close_series.loc[
            pd.Timestamp(grp['entry_date'].min()) : pd.Timestamp(grp['exit_date'].max())
        ]
        m_yr = metrics_from_trades(yr_trades, yr_days / 365.25, cs)
        if m_yr:
            results[yr] = m_yr
    n_pos  = sum(1 for m in results.values() if m['calmar'] >= CALMAR_THRESHOLD)
    n_yrs  = len(results)
    return results, (n_pos / n_yrs * 100 if n_yrs > 0 else 0.0)


def half_split_test(trades_list: list, close_series: pd.Series) -> tuple:
    if not trades_list:
        return None, None
    df_t = pd.DataFrame(trades_list)
    df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
    split  = close_series.index[len(close_series) // 2]
    h1_t   = df_t[df_t['entry_date'] < split].to_dict('records')
    h2_t   = df_t[df_t['entry_date'] >= split].to_dict('records')
    cs_h1  = close_series.iloc[: len(close_series) // 2]
    cs_h2  = close_series.iloc[len(close_series) // 2 :]
    m1 = metrics_from_trades(h1_t, years_btc / 2, cs_h1) if h1_t else None
    m2 = metrics_from_trades(h2_t, years_btc / 2, cs_h2) if h2_t else None
    return m1, m2


for cand_label, trail_type in [('A (pct trail)', 'pct'), ('B (ATR trail)', 'atr')]:
    if trail_type == 'pct':
        cand_sma, cand_trail, cand_atr_p, cand_atr_m = CAND_A_SMA, CAND_A_TRAIL, None, None
        def _base_trades():
            return run_sma_pct_trail(closes_btc, lows_btc, dates_btc,
                                     sma_cache[CAND_A_SMA], CAND_A_TRAIL)
    else:
        cand_sma, cand_trail, cand_atr_p, cand_atr_m = CAND_B_SMA, None, CAND_B_ATR, CAND_B_MULT
        def _base_trades():
            return run_sma_atr_trail(closes_btc, lows_btc, dates_btc,
                                     sma_cache[CAND_B_SMA], atr_cache[CAND_B_ATR], CAND_B_MULT)

    trades_base = _base_trades()
    m_full = metrics_from_trades(trades_base, years_btc, df_btc['Close'])

    print(f"\n{'='*60}")
    print(f"  Candidate {cand_label}")
    print(f"{'='*60}")
    if m_full:
        print(f"  Full period: Calmar {m_full['calmar']:.3f}  Ann {m_full['annual_return']*100:.1f}%  "
              f"MaxDD {m_full['max_drawdown']*100:.1f}%  Sharpe {m_full['sharpe']:.3f}  "
              f"Sortino {m_full['sortino']:.3f}  n={m_full['total_trades']}"
              + (" [!low n]" if m_full['low_trades'] else ""))

    # --- Parameter sweep ---
    print(f"\n  [Parameter sweep — vary each param independently, others fixed at best]")
    scores = []

    if trail_type == 'pct':
        # SMA sweep
        sc1 = param_sweep_1d(
            f"SMA period (trail_pct fixed at {CAND_A_TRAIL*100:.2f}%):",
            SMA_PERIODS,
            lambda p: run_sma_pct_trail(closes_btc, lows_btc, dates_btc, sma_cache[p], CAND_A_TRAIL),
            CALMAR_THRESHOLD,
        )
        scores.append(sc1)
        # Trail_pct sweep
        sc2 = param_sweep_1d(
            f"Trail pct (SMA fixed at {CAND_A_SMA}):",
            TRAIL_PCTS,
            lambda t: run_sma_pct_trail(closes_btc, lows_btc, dates_btc, sma_cache[CAND_A_SMA], t),
            CALMAR_THRESHOLD,
        )
        scores.append(sc2)
    else:
        # SMA sweep
        sc1 = param_sweep_1d(
            f"SMA period (ATR {CAND_B_ATR}/{CAND_B_MULT} fixed):",
            SMA_PERIODS,
            lambda p: run_sma_atr_trail(closes_btc, lows_btc, dates_btc,
                                         sma_cache[p], atr_cache[CAND_B_ATR], CAND_B_MULT),
            CALMAR_THRESHOLD,
        )
        scores.append(sc1)
        # ATR period sweep
        sc2 = param_sweep_1d(
            f"ATR period (SMA {CAND_B_SMA}, mult {CAND_B_MULT} fixed):",
            ATR_PERIODS,
            lambda a: run_sma_atr_trail(closes_btc, lows_btc, dates_btc,
                                         sma_cache[CAND_B_SMA], atr_cache[a], CAND_B_MULT),
            CALMAR_THRESHOLD,
        )
        scores.append(sc2)
        # Multiplier sweep
        sc3 = param_sweep_1d(
            f"ATR multiplier (SMA {CAND_B_SMA}, ATR {CAND_B_ATR} fixed):",
            ATR_MULTS,
            lambda m: run_sma_atr_trail(closes_btc, lows_btc, dates_btc,
                                         sma_cache[CAND_B_SMA], atr_cache[CAND_B_ATR], m),
            CALMAR_THRESHOLD,
        )
        scores.append(sc3)

    composite = sum(scores) / len(scores)
    print(f"\n  Composite stability score: {composite:.0f}%  "
          f"(avg of {len(scores)} param sweeps, Calmar ≥ {CALMAR_THRESHOLD})")

    # --- Year-by-year ---
    print(f"\n  [Year-by-year breakdown]")
    yby, yby_score = year_by_year_breakdown(trades_base, df_btc['Close'])
    H_yr = f"    {'Year':>4}  {'n':>3}  {'Win%':>5}  {'Ann%':>6}  {'MaxDD%':>7}  {'Calmar':>7}"
    print(H_yr); print("    " + "-" * (len(H_yr) - 4))
    for yr in sorted(yby.keys()):
        m = yby[yr]
        tick = "✓" if m['calmar'] >= CALMAR_THRESHOLD else "✗"
        print(f"    {yr:>4}  {m['total_trades']:>3}  {m['win_rate']*100:>5.1f}  "
              f"{m['annual_return']*100:>6.1f}  {m['max_drawdown']*100:>7.1f}  "
              f"{m['calmar']:>7.3f}  {tick}")
    n_pos = sum(1 for m in yby.values() if m['calmar'] >= CALMAR_THRESHOLD)
    print(f"    Year stability: {n_pos}/{len(yby)} years ≥ {CALMAR_THRESHOLD} Calmar = {yby_score:.0f}%")

    # --- Half-split ---
    print(f"\n  [Half-split test]")
    split_date = df_btc.index[len(df_btc) // 2]
    print(f"    Split at {split_date.date()}")
    m_h1, m_h2 = half_split_test(trades_base, df_btc['Close'])
    for hlabel, m_h in [('H1 (earlier)', m_h1), ('H2 (later)', m_h2)]:
        if m_h:
            tick = "✓" if m_h['calmar'] >= CALMAR_THRESHOLD else "✗"
            print(f"    {hlabel}: Calmar {m_h['calmar']:.3f}  Ann {m_h['annual_return']*100:.1f}%  "
                  f"MaxDD {m_h['max_drawdown']*100:.1f}%  n={m_h['total_trades']}  {tick}")
        else:
            print(f"    {hlabel}: insufficient trades")

if STOP_AFTER_STAGE == '2c':
    print("\n[Paused after Stage 2c — awaiting instruction to continue.]")
    sys.exit(0)

# ===========================================================================
# STAGE 2d — Walk-Forward Validation
# ===========================================================================

print("\n" + "=" * 72)
print("STAGE 2d — Walk-Forward Validation  (fixed params, expanding train windows)")
print("=" * 72)

# Windows: train_end, test_start, test_end, display label
WF_WINDOWS = [
    ('2021-12-31', '2022-01-01', '2022-12-31', 'Train 2018-2021 → Test 2022'),
    ('2022-12-31', '2023-01-01', '2023-12-31', 'Train 2018-2022 → Test 2023'),
    ('2023-12-31', '2024-01-01', '2024-12-31', 'Train 2018-2023 → Test 2024'),
]

for trail_type, cand_sma, cand_trail, cand_atr_p, cand_atr_m, cand_lbl in [
    ('pct', CAND_A_SMA, CAND_A_TRAIL, None, None,
     f"Candidate A — SMA {CAND_A_SMA} / trail {CAND_A_TRAIL*100:.2f}%"),
    ('atr', CAND_B_SMA, None, CAND_B_ATR, CAND_B_MULT,
     f"Candidate B — SMA {CAND_B_SMA} / ATR {CAND_B_ATR}/{CAND_B_MULT}"),
]:
    # Run full backtest once and filter per window
    if trail_type == 'pct':
        all_t = run_sma_pct_trail(closes_btc, lows_btc, dates_btc,
                                   sma_cache[cand_sma], cand_trail)
    else:
        all_t = run_sma_atr_trail(closes_btc, lows_btc, dates_btc,
                                   sma_cache[cand_sma], atr_cache[cand_atr_p], cand_atr_m)

    print(f"\n  {cand_lbl}")
    H_wf = f"  {'Window':<38}  {'n':>3}  {'Win%':>5}  {'Ann%':>6}  {'MaxDD%':>7}  {'Calmar':>7}  {'Sortino':>7}  {'Result':>6}"
    print(H_wf); print("  " + "-" * (len(H_wf) - 2))

    n_pass = 0
    for tr_end, te_start, te_end, win_lbl in WF_WINDOWS:
        test_trades = [t for t in all_t
                       if str(t['exit_date'])[:10] >= te_start
                       and str(t['exit_date'])[:10] <= te_end]
        te_yrs = (pd.Timestamp(te_end) - pd.Timestamp(te_start)).days / 365.25
        m_wf   = metrics_from_trades(test_trades, te_yrs, df_btc['Close'])

        if m_wf is None:
            print(f"  {win_lbl:<38}  [< {MIN_TRADES} trades in window]")
            continue

        passed = m_wf['calmar'] > 0
        n_pass += passed
        flag   = " !" if m_wf['low_trades'] else ""
        print(f"  {win_lbl:<38}  {m_wf['total_trades']:>3}  "
              f"{m_wf['win_rate']*100:>5.1f}  {m_wf['annual_return']*100:>6.1f}  "
              f"{m_wf['max_drawdown']*100:>7.1f}  {m_wf['calmar']:>7.3f}  "
              f"{m_wf['sortino']:>7.3f}  {'PASS' if passed else 'FAIL':>6}{flag}")

    print(f"  Walk-forward: {n_pass}/{len(WF_WINDOWS)} windows profitable")

if STOP_AFTER_STAGE == '2d':
    print("\n[Paused after Stage 2d — awaiting instruction to continue.]")
    sys.exit(0)

# ===========================================================================
# STAGE 2e — Cross-Asset Check
# ===========================================================================

print("\n" + "=" * 72)
print("STAGE 2e — Cross-Asset Check  (best BTC SMA params applied to ETH-USD)")
print("=" * 72)

print("\nFetching ETH-USD daily data...")
raw_eth = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw_eth.columns, pd.MultiIndex):
    raw_eth.columns = raw_eth.columns.droplevel(1)
df_eth = raw_eth[['Open', 'High', 'Low', 'Close']].dropna().copy()
df_eth.index = pd.to_datetime(df_eth.index)
print(f"  ETH: {df_eth.index[0].date()} → {df_eth.index[-1].date()} ({len(df_eth)} bars)")

closes_eth = df_eth['Close'].values.astype(float)
highs_eth  = df_eth['High'].values.astype(float)
lows_eth   = df_eth['Low'].values.astype(float)
dates_eth  = df_eth.index
years_eth  = (df_eth.index[-1] - df_eth.index[0]).days / 365.25

for trail_type, cand_sma, cand_trail, cand_atr_p, cand_atr_m, cand_lbl in [
    ('pct', CAND_A_SMA, CAND_A_TRAIL, None, None,
     f"SMA {CAND_A_SMA} / trail {CAND_A_TRAIL*100:.2f}%"),
    ('atr', CAND_B_SMA, None, CAND_B_ATR, CAND_B_MULT,
     f"SMA {CAND_B_SMA} / ATR {CAND_B_ATR}/{CAND_B_MULT}"),
]:
    sma_eth = pd.Series(closes_eth).rolling(cand_sma, min_periods=cand_sma).mean().values
    if trail_type == 'pct':
        t_eth = run_sma_pct_trail(closes_eth, lows_eth, dates_eth, sma_eth, cand_trail)
    else:
        atr_eth = compute_atr(highs_eth, lows_eth, closes_eth, cand_atr_p)
        t_eth   = run_sma_atr_trail(closes_eth, lows_eth, dates_eth, sma_eth, atr_eth, cand_atr_m)

    m_eth = metrics_from_trades(t_eth, years_eth, df_eth['Close'])
    if m_eth:
        flag = " [!low n]" if m_eth['low_trades'] else ""
        print(f"\n  {cand_lbl} on ETH-USD:")
        print(f"    Calmar {m_eth['calmar']:.3f}  Ann {m_eth['annual_return']*100:.1f}%  "
              f"MaxDD {m_eth['max_drawdown']*100:.1f}%  Sortino {m_eth['sortino']:.3f}  "
              f"n={m_eth['total_trades']}{flag}")
    else:
        print(f"\n  {cand_lbl} on ETH-USD: insufficient trades (<{MIN_TRADES})")

if STOP_AFTER_STAGE == '2e':
    print("\n[Paused after Stage 2e — awaiting instruction to continue.]")
    sys.exit(0)

# ===========================================================================
# FINAL — Comparison Table + Equity Curve + Go/No-Go
# ===========================================================================

print("\n" + "=" * 72)
print("FINAL — Strategy Comparison: BTC SMA vs ADX vs Buy-and-Hold")
print("=" * 72)

strats = {
    'SMA pct': {
        'trades': run_sma_pct_trail(closes_btc, lows_btc, dates_btc,
                                     sma_cache[CAND_A_SMA], CAND_A_TRAIL),
        'label': f'BTC SMA {CAND_A_SMA} pct {CAND_A_TRAIL*100:.1f}%',
        'color': '#2196F3',
    },
    'SMA ATR': {
        'trades': run_sma_atr_trail(closes_btc, lows_btc, dates_btc,
                                     sma_cache[CAND_B_SMA], atr_cache[CAND_B_ATR], CAND_B_MULT),
        'label': f'BTC SMA {CAND_B_SMA} ATR {CAND_B_ATR}/{CAND_B_MULT}',
        'color': '#4CAF50',
    },
    'BTC ADX': {
        'trades': run_btc_adx_fixed(df_btc),
        'label': f'BTC ADX {BTC_ADX_THRESHOLD}/{BTC_ADX_PERIOD} fixed {int(BTC_ADX_STOP_PCT*100)}%',
        'color': '#FF5722',
    },
}

bh_eq     = closes_btc / closes_btc[0]
bh_dr     = np.diff(bh_eq) / bh_eq[:-1]
bh_annual = (bh_eq[-1]) ** (1 / years_btc) - 1
bh_peak   = np.maximum.accumulate(bh_eq)
bh_dd     = ((bh_eq - bh_peak) / bh_peak).min()
bh_calmar = bh_annual / abs(bh_dd) if bh_dd != 0 else 0

HC = (f"{'Strategy':<36}  {'n':>4}  {'Win%':>5}  {'PF':>5}  {'Ann%':>6}  "
      f"{'MaxDD%':>7}  {'Calmar':>7}  {'Sharpe':>7}  {'Sortino':>7}  {'Stop%':>5}")
print("\n" + HC); print("-" * len(HC))

metrics_final = {}
for key, s in strats.items():
    m = metrics_from_trades(s['trades'], years_btc, df_btc['Close'])
    metrics_final[key] = m
    if m:
        flag = " !" if m['low_trades'] else ""
        print(f"{s['label']:<36}  {m['total_trades']:>4}  {m['win_rate']*100:>5.1f}  "
              f"{m['profit_factor']:>5.3f}  {m['annual_return']*100:>6.1f}  "
              f"{m['max_drawdown']*100:>7.1f}  {m['calmar']:>7.3f}  "
              f"{m['sharpe']:>7.3f}  {m['sortino']:>7.3f}  {m['stop_exit_pct']:>5.1f}{flag}")
    else:
        print(f"{s['label']:<36}  [insufficient trades]")

print(f"{'BTC Buy-and-Hold':<36}  {'n/a':>4}  {'n/a':>5}  {'n/a':>5}  "
      f"{bh_annual*100:>6.1f}  {bh_dd*100:>7.1f}  {bh_calmar:>7.3f}  {'n/a':>7}  {'n/a':>7}  {'n/a':>5}")

# Equity curves
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9),
                                gridspec_kw={'height_ratios': [3, 1]})

ax1.plot(dates_btc, bh_eq, color='#BDBDBD', linewidth=1, label='BTC Buy-and-Hold', zorder=1)

for key, s in strats.items():
    trades = s['trades']
    if not trades:
        continue
    df_t = pd.DataFrame(trades)
    df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
    df_t['exit_date']  = pd.to_datetime(df_t['exit_date'])
    df_t['return']     = df_t['return'] - COST_PER_TRADE
    eq = build_daily_equity(df_t, df_btc['Close'])
    ax1.plot(dates_btc[:len(eq)], eq, color=s['color'], linewidth=1.5, label=s['label'], zorder=2)
    # Drawdown in lower panel
    pk = np.maximum.accumulate(eq)
    dd = (eq - pk) / pk * 100
    ax2.plot(dates_btc[:len(eq)], dd, color=s['color'], linewidth=1, alpha=0.8)

ax1.set_yscale('log')
ax1.set_ylabel('Portfolio value (log, start=1)')
ax1.set_title('Stage 2 — BTC SMA Strategy Comparison', fontweight='bold')
ax1.legend(loc='upper left', fontsize=9)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f'{y:.2f}'))
ax1.grid(True, alpha=0.3)
ax2.axhline(0, color='black', linewidth=0.5)
ax2.set_ylabel('Drawdown (%)')
ax2.set_xlabel('Date')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
chart_path = os.path.join(RESULTS_DIR, 'stage2_equity_curves.png')
plt.savefig(chart_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"\n  Chart saved → {chart_path}")

# Go / No-Go
print("\n--- Go / No-Go Recommendation ---")
best_key = max(metrics_final, key=lambda k: metrics_final[k]['calmar'] if metrics_final[k] else -1)
best_m   = metrics_final[best_key]
best_lbl = strats[best_key]['label']

criteria = {
    'Calmar ≥ 1.0':   best_m['calmar']        >= 1.0  if best_m else False,
    'Sortino ≥ 1.0':  best_m['sortino']        >= 1.0  if best_m else False,
    'n ≥ 30 trades':  not best_m['low_trades']         if best_m else False,
    'MaxDD > −50%':   best_m['max_drawdown']   > -0.50 if best_m else False,
    'Annual return > 0': best_m['annual_return'] > 0   if best_m else False,
}
all_pass = all(criteria.values())

print(f"\n  Best candidate: {best_lbl}")
for crit, passed in criteria.items():
    print(f"    {'PASS' if passed else 'FAIL'}  {crit}")

print(f"\n  Recommendation: {'GO' if all_pass else 'CONDITIONAL / NO-GO'}")
if not all_pass:
    print("  Walk-forward or stability criteria not fully met.")
    print(f"  Fallback: BTC ADX {BTC_ADX_THRESHOLD}/{BTC_ADX_PERIOD} (validated Week 5 optimum was ADX 16/8)")
    print("  ADX strategy requires trailing stop optimisation before deployment (see A011 pattern).")
if best_m and best_m['low_trades']:
    print("  WARNING: fewer than 30 trades — interpret results with caution.")
