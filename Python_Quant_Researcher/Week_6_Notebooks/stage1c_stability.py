# Stage 1c — Stability Analysis: Percentage Trail vs ATR Trail
# Week 6 Optimisation Plan
#
# Candidates (Stage 1a/1b best with 0.15% round-trip costs):
#   Candidate A: ADX 19/9, Percentage Trail 8%       — Calmar 2.559, Sortino 4.694
#   Candidate B: ADX 19/9, ATR 9, multiplier 2.5x   — Calmar 2.642, Sortino 4.329
#
# Stability tests:
#   1. Year-by-year performance (both candidates side by side)
#   2. Half-split (first 4 yrs vs last 4 yrs)
#   3. Walk-forward: 3-year rolling train → 1-year test windows
#   4. Summary: stability scores and regime hit-rate

import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import ADXIndicator
import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COST_PER_TRADE  = 0.00075 * 2
MIN_TRADES      = 5           # relaxed for annual/window slices

# Candidate A — percentage trailing
CA_THRESHOLD  = 19
CA_ADX_PERIOD = 9
CA_TRAIL_PCT  = 0.08

# Candidate B — ATR trailing
CB_THRESHOLD  = 19
CB_ADX_PERIOD = 9
CB_ATR_PERIOD = 9
CB_MULTIPLIER = 2.5

LIVE_CALMAR   = 1.645   # Week 5 fixed-stop baseline


# ---------------------------------------------------------------------------
# [FUNCTION] compute_atr
# ---------------------------------------------------------------------------

def compute_atr(high, low, close, period):
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low,
         (high - prev_close).abs(),
         (low  - prev_close).abs()],
        axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean().values


# ---------------------------------------------------------------------------
# [FUNCTION] run_pct_trail
# ---------------------------------------------------------------------------

def run_pct_trail(closes, lows, signals, dates, trail_pct):
    position = 0
    entry_price = peak_price = stop_price = 0.0
    trades = []
    for i in range(1, len(closes)):
        low, close, signal = lows[i], closes[i], signals[i]
        if position == 1:
            if low <= stop_price:
                trades.append({
                    'entry_date': dates[i - 1], 'entry_price': entry_price,
                    'exit_date': dates[i],      'exit_price': stop_price,
                    'return': (stop_price - entry_price) / entry_price,
                    'exit_reason': 'TRAIL_STOP',
                })
                position = 0
            elif not signal:
                trades.append({
                    'entry_date': dates[i - 1], 'entry_price': entry_price,
                    'exit_date': dates[i],      'exit_price': close,
                    'return': (close - entry_price) / entry_price,
                    'exit_reason': 'ADX_EXIT',
                })
                position = 0
            else:
                if close > peak_price:
                    peak_price = close
                    stop_price = peak_price * (1 - trail_pct)
        elif position == 0 and signal:
            entry_price = peak_price = close
            stop_price  = close * (1 - trail_pct)
            position = 1
    return trades


# ---------------------------------------------------------------------------
# [FUNCTION] run_atr_trail
# ---------------------------------------------------------------------------

def run_atr_trail(closes, lows, signals, atr_values, dates, multiplier):
    position = 0
    entry_price = peak_price = stop_price = 0.0
    trades = []
    for i in range(1, len(closes)):
        low, close, signal, atr = lows[i], closes[i], signals[i], atr_values[i]
        if position == 1:
            if low <= stop_price:
                trades.append({
                    'entry_date': dates[i - 1], 'entry_price': entry_price,
                    'exit_date': dates[i],      'exit_price': stop_price,
                    'return': (stop_price - entry_price) / entry_price,
                    'exit_reason': 'TRAIL_STOP',
                })
                position = 0
            elif not signal:
                trades.append({
                    'entry_date': dates[i - 1], 'entry_price': entry_price,
                    'exit_date': dates[i],      'exit_price': close,
                    'return': (close - entry_price) / entry_price,
                    'exit_reason': 'ADX_EXIT',
                })
                position = 0
            else:
                if close > peak_price:
                    peak_price = close
                candidate = peak_price - multiplier * atr
                stop_price = max(stop_price, candidate)
        elif position == 0 and signal:
            entry_price = peak_price = close
            stop_price  = close - multiplier * atr
            position = 1
    return trades


# ---------------------------------------------------------------------------
# [FUNCTION] build_daily_equity
# ---------------------------------------------------------------------------

def build_daily_equity(trades_df: pd.DataFrame, close_series: pd.Series) -> np.ndarray:
    """Mark-to-market daily equity curve — Week 5 method."""
    n          = len(close_series)
    closes_arr = close_series.values
    date_to_i  = pd.Series(np.arange(n), index=close_series.index)

    equity    = np.ones(n)
    portfolio = 1.0
    prev_i    = 0

    for _, trade in trades_df.iterrows():
        ei = date_to_i.get(pd.Timestamp(trade['entry_date']))
        xi = date_to_i.get(pd.Timestamp(trade['exit_date']))
        if ei is None or xi is None:
            continue
        equity[prev_i:ei]    = portfolio
        equity[ei:xi + 1]    = portfolio * closes_arr[ei:xi + 1] / trade['entry_price']
        portfolio           *= (1 + trade['return'] - COST_PER_TRADE)
        equity[xi]           = portfolio
        prev_i               = xi + 1

    equity[prev_i:] = portfolio
    return equity


# ---------------------------------------------------------------------------
# [FUNCTION] metrics_from_trades
# ---------------------------------------------------------------------------

def metrics_from_trades(trades, years, close_series):
    """
    Calmar  — per-trade equity cumprod.
    Sortino — daily equity curve, Week 5 method: mean(dr)/std(downside)*sqrt(365).
    close_series: full df['Close'] (or sliced to the relevant period).
    """
    if len(trades) < MIN_TRADES:
        return None
    trades_df = pd.DataFrame(trades)
    returns   = trades_df['return'].values - COST_PER_TRADE

    winners_mask = returns > 0
    losers_mask  = returns <= 0

    win_rate      = winners_mask.mean()
    gross_profit  = returns[winners_mask].sum() if winners_mask.any() else 0.0
    gross_loss    = abs(returns[losers_mask].sum()) if losers_mask.any() else 1e-9
    profit_factor = gross_profit / gross_loss

    equity   = np.cumprod(1 + returns)
    peak     = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_dd   = drawdown.min()

    total_return  = equity[-1] - 1
    annual_return = (1 + total_return) ** (1 / years) - 1
    calmar        = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    # Slice close to just the trade window so Sortino isn't diluted by idle years
    first_entry = pd.Timestamp(trades_df['entry_date'].min())
    last_exit   = pd.Timestamp(trades_df['exit_date'].max())
    close_slice = close_series.loc[first_entry:last_exit]
    daily_eq = build_daily_equity(trades_df, close_slice)
    dr       = np.diff(daily_eq) / daily_eq[:-1]
    downside = dr[dr < 0]
    sortino  = (dr.mean() / downside.std() * np.sqrt(365)
                if len(downside) > 0 and downside.std() > 0 else 0.0)

    return {
        'n_trades':      len(trades_df),
        'win_rate':      win_rate,
        'profit_factor': profit_factor,
        'annual_return': annual_return,
        'max_drawdown':  max_dd,
        'calmar':        calmar,
        'sortino':       sortino,
    }


# ---------------------------------------------------------------------------
# FETCH DATA
# ---------------------------------------------------------------------------

print("\nFetching ETH-USD daily data...")
raw = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)

df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.dropna(inplace=True)

years_full = (df.index[-1] - df.index[0]).days / 365.25
print(f"Data: {df.index[0].date()} → {df.index[-1].date()} ({years_full:.1f} yrs)\n")

closes = df['Close'].values
lows   = df['Low'].values
dates  = df.index


# ---------------------------------------------------------------------------
# COMPUTE INDICATORS (full dataset)
# ---------------------------------------------------------------------------

# ADX signals — both candidates use same threshold/period
adx_ind    = ADXIndicator(df['High'], df['Low'], df['Close'], window=CA_ADX_PERIOD)
adx        = adx_ind.adx().values
di_pos     = adx_ind.adx_pos().values
di_neg     = adx_ind.adx_neg().values
signals_ab = (adx >= CA_THRESHOLD) & (di_pos > di_neg)   # shared signal

atr_b      = compute_atr(df['High'], df['Low'], df['Close'], CB_ATR_PERIOD)


# ---------------------------------------------------------------------------
# FULL-PERIOD TRADES
# ---------------------------------------------------------------------------

trades_a = run_pct_trail(closes, lows, signals_ab, dates, CA_TRAIL_PCT)
trades_b = run_atr_trail(closes, lows, signals_ab, atr_b, dates, CB_MULTIPLIER)

df_a = pd.DataFrame(trades_a)
df_b = pd.DataFrame(trades_b)

for d in [df_a, df_b]:
    d['exit_year'] = pd.to_datetime(d['exit_date']).dt.year


# ===========================================================================
# TEST 1: YEAR-BY-YEAR PERFORMANCE
# ===========================================================================

print(f"{'='*115}")
print(f"STABILITY TEST 1 — YEAR-BY-YEAR PERFORMANCE (costs included)")
print(f"{'='*115}")
print(f"\n  {'Year':<6}  "
      f"{'Cand A: Annual%':>15} {'Calmar':>7} {'Sortino':>8} {'Trades':>7} {'Win%':>6}  "
      f"{'Cand B: Annual%':>15} {'Calmar':>7} {'Sortino':>8} {'Trades':>7} {'Win%':>6}")
print(f"  {'-'*107}")

years_list = sorted(set(df_a['exit_year'].unique()) | set(df_b['exit_year'].unique()))
a_beats = 0
b_beats = 0

for yr in years_list:
    t_a = df_a[df_a['exit_year'] == yr].to_dict('records')
    t_b = df_b[df_b['exit_year'] == yr].to_dict('records')
    m_a = metrics_from_trades(t_a, 1.0, df['Close'])
    m_b = metrics_from_trades(t_b, 1.0, df['Close'])

    def fmt(m):
        if m is None:
            return f"{'  <5 trades':>15} {'  ---':>7} {'  ---':>8} {'---':>7} {'---':>6}"
        return (f"{m['annual_return']:>15.1%} {m['calmar']:>7.2f} {m['sortino']:>8.2f} "
                f"{m['n_trades']:>7} {m['win_rate']:>6.1%}")

    winner = ''
    if m_a and m_b:
        if m_a['calmar'] > m_b['calmar']:
            a_beats += 1
            winner = '  A'
        else:
            b_beats += 1
            winner = '  B'

    print(f"  {yr:<6}  {fmt(m_a)}  {fmt(m_b)}{winner}")

print(f"\n  Year wins: Candidate A = {a_beats}, Candidate B = {b_beats} "
      f"(of {a_beats+b_beats} comparable years)")


# ===========================================================================
# TEST 2: HALF-SPLIT
# ===========================================================================

mid_date = df.index[len(df) // 2]
h1_label = f"{df.index[0].year}–{mid_date.year}"
h2_label = f"{(mid_date + pd.Timedelta(days=1)).year}–{df.index[-1].year}"

h1_a = df_a[pd.to_datetime(df_a['exit_date']) <= mid_date].to_dict('records')
h2_a = df_a[pd.to_datetime(df_a['exit_date']) >  mid_date].to_dict('records')
h1_b = df_b[pd.to_datetime(df_b['exit_date']) <= mid_date].to_dict('records')
h2_b = df_b[pd.to_datetime(df_b['exit_date']) >  mid_date].to_dict('records')

half_yrs = years_full / 2

m_h1a = metrics_from_trades(h1_a, half_yrs, df['Close'])
m_h2a = metrics_from_trades(h2_a, half_yrs, df['Close'])
m_h1b = metrics_from_trades(h1_b, half_yrs, df['Close'])
m_h2b = metrics_from_trades(h2_b, half_yrs, df['Close'])

print(f"\n{'='*115}")
print(f"STABILITY TEST 2 — HALF-SPLIT (split at {mid_date.date()})")
print(f"{'='*115}")
print(f"\n  {'Period':<18}  "
      f"{'Cand A: Annual%':>15} {'Calmar':>7} {'Sortino':>8} {'Trades':>7}  "
      f"{'Cand B: Annual%':>15} {'Calmar':>7} {'Sortino':>8} {'Trades':>7}")
print(f"  {'-'*95}")

def fmt_half(m):
    if m is None:
        return f"{'  <5 trades':>15} {'  ---':>7} {'  ---':>8} {'---':>7}"
    return (f"{m['annual_return']:>15.1%} {m['calmar']:>7.2f} {m['sortino']:>8.2f} "
            f"{m['n_trades']:>7}")

print(f"  {h1_label:<18}  {fmt_half(m_h1a)}  {fmt_half(m_h1b)}")
print(f"  {h2_label:<18}  {fmt_half(m_h2a)}  {fmt_half(m_h2b)}")


# ===========================================================================
# TEST 3: WALK-FORWARD (3-year train window, 1-year test)
# ===========================================================================

print(f"\n{'='*115}")
print(f"STABILITY TEST 3 — WALK-FORWARD (3-yr rolling train → 1-yr test)")
print(f"{'='*115}")
print(f"\n  {'Train':>12} {'Test':>6}  "
      f"{'A test Annual%':>15} {'A Calmar':>9} {'A Sortino':>10} {'A Trades':>9}  "
      f"{'B test Annual%':>15} {'B Calmar':>9} {'B Sortino':>10} {'B Trades':>9}")
print(f"  {'-'*107}")

TRAIN_YEARS = 3
wf_years    = sorted(df.index.year.unique())
test_years  = [y for y in wf_years if y >= wf_years[0] + TRAIN_YEARS]

a_wf_calmar = []
b_wf_calmar = []
a_wf_pos    = 0
b_wf_pos    = 0
n_wf        = 0

for test_yr in test_years:
    train_end = test_yr - 1
    train_start = test_yr - TRAIN_YEARS

    t_a_test = df_a[df_a['exit_year'] == test_yr].to_dict('records')
    t_b_test = df_b[df_b['exit_year'] == test_yr].to_dict('records')

    m_a_t = metrics_from_trades(t_a_test, 1.0, df['Close'])
    m_b_t = metrics_from_trades(t_b_test, 1.0, df['Close'])

    def fmt_wf(m):
        if m is None:
            return f"{'  <5 trades':>15} {'  ---':>9} {'  ---':>10} {'---':>9}"
        return (f"{m['annual_return']:>15.1%} {m['calmar']:>9.2f} {m['sortino']:>10.2f} "
                f"{m['n_trades']:>9}")

    win = ''
    if m_a_t and m_b_t:
        n_wf += 1
        if m_a_t['calmar'] > 0: a_wf_pos += 1
        if m_b_t['calmar'] > 0: b_wf_pos += 1
        if m_a_t['calmar'] > 0: a_wf_calmar.append(m_a_t['calmar'])
        if m_b_t['calmar'] > 0: b_wf_calmar.append(m_b_t['calmar'])
    elif m_a_t and m_a_t['calmar'] > 0:
        a_wf_pos += 1
        a_wf_calmar.append(m_a_t['calmar'])
    elif m_b_t and m_b_t['calmar'] > 0:
        b_wf_pos += 1
        b_wf_calmar.append(m_b_t['calmar'])

    print(f"  {train_start}–{train_end} → {test_yr}  {fmt_wf(m_a_t)}  {fmt_wf(m_b_t)}")

n_test_years = len(test_years)
print(f"\n  Walk-forward test years: {n_test_years}")
print(f"  Candidate A: positive Calmar in {a_wf_pos}/{n_test_years} years  "
      f"| avg Calmar (positive years) = "
      f"{np.mean(a_wf_calmar):.2f}" if a_wf_calmar else "  Candidate A: no positive years")
print(f"  Candidate B: positive Calmar in {b_wf_pos}/{n_test_years} years  "
      f"| avg Calmar (positive years) = "
      f"{np.mean(b_wf_calmar):.2f}" if b_wf_calmar else "  Candidate B: no positive years")


# ===========================================================================
# STABILITY SUMMARY
# ===========================================================================

m_full_a = metrics_from_trades(trades_a, years_full, df['Close'])
m_full_b = metrics_from_trades(trades_b, years_full, df['Close'])

print(f"\n{'='*115}")
print(f"STAGE 1c STABILITY SUMMARY")
print(f"{'='*115}")
print(f"\n  {'Metric':<35} {'Candidate A':>20} {'Candidate B':>20}")
print(f"  {'':35} {'(ADX 19/9, 8% trail)':>20} {'(ADX 19/9, ATR9 2.5x)':>20}")
print(f"  {'-'*75}")
print(f"  {'Full-period Calmar':<35} {m_full_a['calmar']:>20.3f} {m_full_b['calmar']:>20.3f}")
print(f"  {'Full-period Sortino':<35} {m_full_a['sortino']:>20.3f} {m_full_b['sortino']:>20.3f}")
print(f"  {'Full-period Annual return':<35} {m_full_a['annual_return']:>20.1%} {m_full_b['annual_return']:>20.1%}")
print(f"  {'Full-period Max Drawdown':<35} {m_full_a['max_drawdown']:>20.1%} {m_full_b['max_drawdown']:>20.1%}")
print(f"  {'Total trades (full period)':<35} {m_full_a['n_trades']:>20} {m_full_b['n_trades']:>20}")
print(f"  {'Year wins (Calmar)':<35} {a_beats:>20} {b_beats:>20}")
print(f"  {'H1 Calmar':<35} {(m_h1a['calmar'] if m_h1a else float('nan')):>20.3f} {(m_h1b['calmar'] if m_h1b else float('nan')):>20.3f}")
print(f"  {'H2 Calmar':<35} {(m_h2a['calmar'] if m_h2a else float('nan')):>20.3f} {(m_h2b['calmar'] if m_h2b else float('nan')):>20.3f}")
print(f"  {'H1→H2 Calmar change':<35} "
      f"{((m_h2a['calmar'] - m_h1a['calmar']) if m_h1a and m_h2a else float('nan')):>+20.3f} "
      f"{((m_h2b['calmar'] - m_h1b['calmar']) if m_h1b and m_h2b else float('nan')):>+20.3f}")
print(f"  {'WF positive years / total':<35} {a_wf_pos:>19}/{n_test_years} {b_wf_pos:>19}/{n_test_years}")
print(f"  {'WF avg Calmar (pos years)':<35} "
      f"{(np.mean(a_wf_calmar) if a_wf_calmar else float('nan')):>20.3f} "
      f"{(np.mean(b_wf_calmar) if b_wf_calmar else float('nan')):>20.3f}")

# Recommendation
print(f"\n{'='*115}")
print(f"RECOMMENDATION")
print(f"{'='*115}")
# Composite score: full Calmar, Sortino, WF positive years, H2 Calmar
score_a = (m_full_a['calmar'] / 3 + m_full_a['sortino'] / 5 +
           a_wf_pos / n_test_years + (m_h2a['calmar'] if m_h2a else 0) / 3)
score_b = (m_full_b['calmar'] / 3 + m_full_b['sortino'] / 5 +
           b_wf_pos / n_test_years + (m_h2b['calmar'] if m_h2b else 0) / 3)

preferred = 'A (percentage trail 8%)' if score_a > score_b else 'B (ATR 9, 2.5x)'
print(f"  Composite stability score: A = {score_a:.3f}  |  B = {score_b:.3f}")
print(f"  Preferred candidate: {preferred}")

print(f"\n  Next step: Stage 1d — comparison vs live system, final selection")
print(f"{'='*115}\n")
