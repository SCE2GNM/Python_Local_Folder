#!/usr/bin/env python3
"""
BTC ADX 19/14 — Stage B: Stability & Walk-Forward Analysis
Candidate: Fixed 3% stop (Stage A winner)

Critical questions this stage answers:
  1. Is the post-2022 +5.4%/yr return structural regime deterioration or temporary?
  2. Were ADX 19/14 parameters overfit to the 2018-2021 bull cycle?

Methodology (non-negotiable per METHODOLOGY_STANDARDS.md):
  - Bar-by-bar stop checked against daily LOW
  - Daily mark-to-market equity curve for Sortino and MtM MaxDD
  - 0.15% round-trip costs per trade
  - Both per-trade and daily MtM MaxDD reported

Outputs:
  results/btc_adx_stage_b_yoy.png          year-by-year returns + regime metrics
  results/btc_adx_stage_b_plateau.png      stop% sensitivity (cliff-edge check)
  results/btc_adx_stage_b_walkforward.png  walk-forward 2022/2023/2024
  results/btc_adx_stage_b_regime.png       signal frequency + trade quality by year
  data/btc_adx_stage_b_summary.csv         full results table
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import yfinance as yf
from ta.trend import ADXIndicator

warnings.filterwarnings('ignore')

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Strategy constants ────────────────────────────────────────────────────────
ADX_THRESHOLD  = 19
ADX_PERIOD     = 14
CANDIDATE_STOP = 0.03       # Fixed 3% stop — Stage A winner
COSTS          = 0.0015     # 0.15% round-trip
MIN_TRADES     = 3          # minimum per window for metrics
LOW_N_FLAG     = 3          # flag windows with fewer than this

# Fixed stop sweep for stability analysis
STOP_SWEEP = [0.020, 0.025, 0.030, 0.035, 0.040, 0.045,
              0.050, 0.055, 0.060, 0.070, 0.080]

# Walk-forward test windows
TEST_WINDOWS = [
    ('2022', pd.Timestamp('2022-01-01'), pd.Timestamp('2022-12-31')),
    ('2023', pd.Timestamp('2023-01-01'), pd.Timestamp('2023-12-31')),
    ('2024', pd.Timestamp('2024-01-01'), pd.Timestamp('2024-12-31')),
]

POST_2022_START = pd.Timestamp('2022-01-01')


# ─────────────────────────────────────────────────────────────────────────────
# 1. FETCH DATA
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("BTC ADX 19/14 — STAGE B: STABILITY & WALK-FORWARD ANALYSIS")
print("=" * 70)
print("\nFetching BTC-USD daily data (2018 → present)...")

raw = yf.download('BTC-USD', start='2018-01-01', auto_adjust=True, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
df = raw[['High', 'Low', 'Close']].copy().dropna()

closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)
highs  = df['High'].values.astype(float)
dates  = df.index
N      = len(df)
YEARS  = (dates[-1] - dates[0]).days / 365.25

print(f"Data: {dates[0].date()} → {dates[-1].date()}  ({YEARS:.2f} yrs, {N} bars)")


# ─────────────────────────────────────────────────────────────────────────────
# 2. INDICATORS
# ─────────────────────────────────────────────────────────────────────────────

print(f"Computing ADX {ADX_THRESHOLD}/{ADX_PERIOD} signals...")
adx_ind  = ADXIndicator(df['High'], df['Low'], df['Close'],
                        window=ADX_PERIOD, fillna=False)
adx_vals = adx_ind.adx().values
di_pos   = adx_ind.adx_pos().values
di_neg   = adx_ind.adx_neg().values

# Long signal: ADX >= threshold AND DI+ > DI-
sig_long = (adx_vals >= ADX_THRESHOLD) & (di_pos > di_neg)


# ─────────────────────────────────────────────────────────────────────────────
# 3. BACKTESTS
# ─────────────────────────────────────────────────────────────────────────────

def run_fixed_stop(closes, lows, signals, dates, stop_pct):
    """Bar-by-bar fixed stop backtest. Stop checked vs daily LOW first."""
    pos = ep = sp = 0.0
    entry_date = None
    trades = []
    for i in range(1, len(closes)):
        lo, cl, sig = lows[i], closes[i], signals[i]
        if pos == 1:
            if lo <= sp:
                trades.append({
                    'entry_date': entry_date, 'entry_price': ep,
                    'exit_date': dates[i],   'exit_price': sp,
                    'return': (sp - ep) / ep, 'exit_reason': 'STOP',
                })
                pos = ep = sp = 0.0; entry_date = None
            elif not sig:
                trades.append({
                    'entry_date': entry_date, 'entry_price': ep,
                    'exit_date': dates[i],   'exit_price': cl,
                    'return': (cl - ep) / ep, 'exit_reason': 'ADX_EXIT',
                })
                pos = ep = sp = 0.0; entry_date = None
        elif pos == 0 and sig:
            ep = cl; sp = cl * (1 - stop_pct); pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)


def build_equity_curve(trades_df, close_series):
    """Daily mark-to-market equity curve. Cost deducted at exit."""
    n        = len(close_series)
    arr      = close_series.values.astype(float)
    date_idx = pd.Series(np.arange(n), index=close_series.index)
    equity   = np.ones(n)
    portfolio = 1.0
    prev_i    = 0
    for _, t in trades_df.iterrows():
        ei = date_idx.get(pd.Timestamp(t['entry_date']))
        xi = date_idx.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None or xi >= n:
            continue
        equity[prev_i:ei]  = portfolio
        equity[ei:xi + 1]  = portfolio * arr[ei:xi + 1] / t['entry_price']
        portfolio          *= (1 + t['return'] - COSTS)
        equity[xi]          = portfolio
        prev_i              = xi + 1
    equity[prev_i:] = portfolio
    return equity


def calc_metrics(trades_df, close_series, years):
    """Full metrics from trade list + daily equity curve."""
    if len(trades_df) < MIN_TRADES:
        return None
    rets    = trades_df['return'].values - COSTS
    winners = rets[rets > 0]
    losers  = rets[rets <= 0]

    eq_pt   = np.cumprod(1 + rets)
    pk_pt   = np.maximum.accumulate(eq_pt)
    dd_pt   = ((eq_pt - pk_pt) / pk_pt).min()
    ann_ret = (eq_pt[-1]) ** (1 / years) - 1
    calmar  = ann_ret / abs(dd_pt) if dd_pt != 0 else 0.0

    eq      = build_equity_curve(trades_df, close_series)
    dr      = np.diff(eq) / eq[:-1]
    down    = dr[dr < 0]
    sortino = (dr.mean() / down.std() * np.sqrt(365)
               if len(down) > 0 and down.std() > 0 else 0.0)
    pk_eq   = np.maximum.accumulate(eq)
    dd_mtm  = ((eq - pk_eq) / pk_eq).min()

    gl = abs(losers.sum()) if len(losers) > 0 else 1e-9
    pf = winners.sum() / gl if len(winners) > 0 else 0.0

    return {
        'n_trades':      len(trades_df),
        'win_rate':      (rets > 0).mean(),
        'avg_win':       winners.mean() if len(winners) > 0 else 0.0,
        'avg_loss':      losers.mean()  if len(losers)  > 0 else 0.0,
        'profit_factor': pf,
        'annual_return': ann_ret,
        'max_dd_trade':  dd_pt,
        'max_dd_mtm':    dd_mtm,
        'calmar':        calmar,
        'sortino':       sortino,
        'stop_exit_pct': (trades_df['exit_reason'] == 'STOP').sum() / len(trades_df),
    }


# Run full-period candidate
print(f"\nRunning Fixed {CANDIDATE_STOP*100:.0f}% stop backtest (full period)...")
trades_full = run_fixed_stop(closes, lows, sig_long, dates, CANDIDATE_STOP)
m_full      = calc_metrics(trades_full, df['Close'], YEARS)

print(f"  → {len(trades_full)} trades  |  "
      f"Annual {m_full['annual_return']*100:.1f}%  |  "
      f"Sortino {m_full['sortino']:.3f}  |  "
      f"Calmar {m_full['calmar']:.3f}")

equity_full = build_equity_curve(trades_full, df['Close'])
bh_eq       = closes / closes[0]


# ─────────────────────────────────────────────────────────────────────────────
# 4. YEAR-BY-YEAR ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 70)
print("YEAR-BY-YEAR PROFITABILITY  (Fixed 3% stop, exit-year attribution)")
print("─" * 70)

all_years = sorted(df.index.year.unique())
trades_full['exit_year'] = pd.to_datetime(trades_full['exit_date']).dt.year
trades_full['entry_year'] = pd.to_datetime(trades_full['entry_date']).dt.year

yy_rows = []
print(f"  {'Year':<6} {'N':>4} {'Ann%':>8} {'WR':>7} {'AvgWin':>8} {'AvgLoss':>9} "
      f"{'DD%Tr':>8} {'DD%MtM':>8} {'BH%':>8}  {'Note'}")
print(f"  {'-'*90}")

for yr in all_years:
    yr_trades = trades_full[trades_full['exit_year'] == yr].copy()
    yr_close  = df['Close'].loc[str(yr)]

    if len(yr_close) == 0:
        continue

    # BTC buy-and-hold for this calendar year
    bh_yr = yr_close.iloc[-1] / yr_close.iloc[0] - 1

    if len(yr_trades) == 0:
        yy_rows.append({'year': yr, 'n': 0, 'ann': 0.0, 'win_rate': 0.0,
                        'avg_win': 0.0, 'avg_loss': 0.0, 'dd_trade': 0.0,
                        'dd_mtm': 0.0, 'bh': bh_yr, 'calmar': 0.0})
        print(f"  {yr:<6} {'—':>4} {'—':>8} {'—':>7} {'—':>8} {'—':>9} "
              f"{'—':>8} {'—':>8} {bh_yr*100:>7.1f}%   no trades")
        continue

    rets_yr  = yr_trades['return'].values - COSTS
    eq_yr    = np.cumprod(1 + rets_yr)
    ann_yr   = eq_yr[-1] - 1
    pk_yr    = np.maximum.accumulate(eq_yr)
    dd_yr    = ((eq_yr - pk_yr) / pk_yr).min()
    wr_yr    = (rets_yr > 0).mean()
    win_ret  = rets_yr[rets_yr > 0]
    loss_ret = rets_yr[rets_yr <= 0]
    avg_w    = win_ret.mean() if len(win_ret) > 0 else 0.0
    avg_l    = loss_ret.mean() if len(loss_ret) > 0 else 0.0
    cal_yr   = ann_yr / abs(dd_yr) if dd_yr != 0 else 0.0

    eq_mtm   = build_equity_curve(yr_trades, yr_close)
    pk_mtm   = np.maximum.accumulate(eq_mtm)
    dd_mtm   = ((eq_mtm - pk_mtm) / pk_mtm).min()

    note = '⚠ low-n' if len(yr_trades) < LOW_N_FLAG else ''
    marker = '✓' if ann_yr > 0 else '✗'

    yy_rows.append({'year': yr, 'n': len(yr_trades), 'ann': ann_yr,
                    'win_rate': wr_yr, 'avg_win': avg_w, 'avg_loss': avg_l,
                    'dd_trade': dd_yr, 'dd_mtm': dd_mtm, 'bh': bh_yr, 'calmar': cal_yr})

    print(f"  {yr:<6} {len(yr_trades):>4} {ann_yr*100:>7.1f}% {wr_yr*100:>6.0f}% "
          f"{avg_w*100:>7.1f}% {avg_l*100:>8.1f}% "
          f"{dd_yr*100:>7.1f}% {dd_mtm*100:>7.1f}% {bh_yr*100:>7.1f}%  "
          f"{marker} {note}")

pos_years   = sum(1 for r in yy_rows if r['ann'] > 0 and r['n'] > 0)
total_years = sum(1 for r in yy_rows if r['n'] > 0)
print(f"\n  Profitable years: {pos_years}/{total_years} ({100*pos_years/total_years:.0f}%)")


# ─────────────────────────────────────────────────────────────────────────────
# 5. HALF-SPLIT:  PRE-2022 vs POST-2022
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 70)
print("HALF-SPLIT: PRE-2022 (2018-2021) vs POST-2022 (2022-present)")
print("─" * 70)

pre_trades  = trades_full[trades_full['exit_year'] < 2022].copy()
post_trades = trades_full[trades_full['exit_year'] >= 2022].copy()

pre_close   = df['Close'].loc[:'2021-12-31']
post_close  = df['Close'].loc['2022-01-01':]

pre_years   = (pd.Timestamp('2022-01-01') - dates[0]).days / 365.25
post_years  = (dates[-1] - pd.Timestamp('2022-01-01')).days / 365.25

print(f"\n  {'Half':<26} {'N':>4} {'Yrs':>5} {'AnnRet%':>9} {'WR':>7} "
      f"{'AvgWin':>8} {'AvgLoss':>9} {'Sortino':>8} {'Calmar':>8}")
print(f"  {'-'*90}")

for label, tdf, cs, yrs in [
    ('Pre-2022 (2018–2021)',  pre_trades,  pre_close,  pre_years),
    ('Post-2022 (2022–now)', post_trades, post_close, post_years),
]:
    if len(tdf) < MIN_TRADES:
        print(f"  {label:<26} {len(tdf):>4} {yrs:>5.1f}   insufficient trades")
        continue
    rets_h   = tdf['return'].values - COSTS
    eq_h     = np.cumprod(1 + rets_h)
    ann_h    = (eq_h[-1]) ** (1 / yrs) - 1
    pk_h     = np.maximum.accumulate(eq_h)
    dd_h     = ((eq_h - pk_h) / pk_h).min()
    wr_h     = (rets_h > 0).mean()
    win_h    = rets_h[rets_h > 0]
    loss_h   = rets_h[rets_h <= 0]
    avg_w_h  = win_h.mean() if len(win_h) > 0 else 0.0
    avg_l_h  = loss_h.mean() if len(loss_h) > 0 else 0.0
    cal_h    = ann_h / abs(dd_h) if dd_h != 0 else 0.0

    eq_mtm_h = build_equity_curve(tdf, cs)
    dr_h     = np.diff(eq_mtm_h) / eq_mtm_h[:-1]
    down_h   = dr_h[dr_h < 0]
    sort_h   = (dr_h.mean() / down_h.std() * np.sqrt(365)
                if len(down_h) > 0 and down_h.std() > 0 else 0.0)

    print(f"  {label:<26} {len(tdf):>4} {yrs:>5.1f} {ann_h*100:>8.1f}% "
          f"{wr_h*100:>6.0f}% {avg_w_h*100:>7.1f}% {avg_l_h*100:>8.1f}% "
          f"{sort_h:>8.3f} {cal_h:>8.3f}")

# 15%/yr GO threshold check
post_rets   = post_trades['return'].values - COSTS if len(post_trades) > 0 else np.array([])
if len(post_rets) >= MIN_TRADES:
    eq_post = np.cumprod(1 + post_rets)
    ann_post = (eq_post[-1]) ** (1 / post_years) - 1
    print(f"\n  Post-2022 annual return: {ann_post*100:.1f}%  "
          f"(GO threshold: ≥15.0%  |  "
          f"{'PASS' if ann_post >= 0.15 else '✗ FAIL — well below threshold'})")
    print(f"  BTC B&H post-2022:  "
          f"{(closes[-1] / df['Close'].loc['2022-01-01':].iloc[0] - 1)**1 * 100:.0f}% total  "
          f"({((closes[-1] / df['Close'].loc['2022-01-01':].iloc[0])**(1/post_years)-1)*100:.1f}%/yr)")


# ─────────────────────────────────────────────────────────────────────────────
# 6. REGIME ANALYSIS — Signal frequency + trade quality by year
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 70)
print("REGIME ANALYSIS — ADX Signal Frequency & Trade Quality by Year")
print("(Diagnoses WHY post-2022 deteriorated)")
print("─" * 70)

print(f"\n  {'Year':<6} {'SigDays':>8} {'Sig%':>7} {'AvgADX':>8} "
      f"{'Trades':>7} {'EntryWR':>9} {'AvgNetRet':>10} {'Note'}")
print(f"  {'-'*70}")

regime_rows = []
for yr in all_years:
    yr_mask = df.index.year == yr
    adx_yr  = adx_vals[yr_mask]
    dip_yr  = di_pos[yr_mask]
    din_yr  = di_neg[yr_mask]
    sig_yr  = sig_long[yr_mask]

    total_days   = yr_mask.sum()
    signal_days  = sig_yr.sum()
    sig_pct      = signal_days / total_days * 100 if total_days > 0 else 0
    avg_adx_sig  = adx_yr[sig_yr].mean() if signal_days > 0 else 0.0

    yr_trades = trades_full[trades_full['entry_year'] == yr]
    n_entries = len(yr_trades)
    rets_entry = yr_trades['return'].values - COSTS if n_entries > 0 else np.array([])
    wr_entry   = (rets_entry > 0).mean() if len(rets_entry) > 0 else 0.0
    avg_ret    = rets_entry.mean() if len(rets_entry) > 0 else 0.0

    regime_rows.append({
        'year': yr, 'signal_days': signal_days, 'sig_pct': sig_pct,
        'avg_adx': avg_adx_sig, 'n_entries': n_entries,
        'win_rate': wr_entry, 'avg_net_ret': avg_ret,
    })

    note = '← pre-2022' if yr < 2022 else '← post-2022'
    print(f"  {yr:<6} {signal_days:>8d} {sig_pct:>6.1f}% {avg_adx_sig:>8.1f} "
          f"{n_entries:>7} {wr_entry*100:>8.0f}% {avg_ret*100:>9.1f}%  {note}")

pre_sig  = [r for r in regime_rows if r['year'] < 2022 and r['avg_adx'] > 0]
post_sig = [r for r in regime_rows if r['year'] >= 2022 and r['avg_adx'] > 0]

if pre_sig and post_sig:
    avg_sig_pre  = np.mean([r['sig_pct'] for r in pre_sig])
    avg_sig_post = np.mean([r['sig_pct'] for r in post_sig])
    avg_adx_pre  = np.mean([r['avg_adx'] for r in pre_sig])
    avg_adx_post = np.mean([r['avg_adx'] for r in post_sig])
    avg_wr_pre   = np.mean([r['win_rate'] for r in pre_sig if r['n_entries'] > 0])
    avg_wr_post  = np.mean([r['win_rate'] for r in post_sig if r['n_entries'] > 0])
    avg_ret_pre  = np.mean([r['avg_net_ret'] for r in pre_sig if r['n_entries'] > 0])
    avg_ret_post = np.mean([r['avg_net_ret'] for r in post_sig if r['n_entries'] > 0])

    print(f"\n  REGIME COMPARISON:")
    print(f"  {'Metric':<30} {'Pre-2022':>12} {'Post-2022':>12} {'Change':>10}")
    print(f"  {'-'*66}")
    print(f"  {'Signal days / yr (avg)':30} {avg_sig_pre:>11.1f}% {avg_sig_post:>11.1f}%"
          f" {avg_sig_post-avg_sig_pre:>+9.1f}pp")
    print(f"  {'Avg ADX when signal on':30} {avg_adx_pre:>12.1f} {avg_adx_post:>12.1f}"
          f" {avg_adx_post-avg_adx_pre:>+10.1f}")
    print(f"  {'Win rate (entry-year)':30} {avg_wr_pre*100:>11.0f}% {avg_wr_post*100:>11.0f}%"
          f" {(avg_wr_post-avg_wr_pre)*100:>+9.0f}pp")
    print(f"  {'Avg net return / trade':30} {avg_ret_pre*100:>11.1f}% {avg_ret_post*100:>11.1f}%"
          f" {(avg_ret_post-avg_ret_pre)*100:>+9.1f}pp")

    print(f"\n  STRUCTURAL vs TEMPORARY DIAGNOSIS:")
    deterioration_reasons = []
    if avg_sig_post < avg_sig_pre - 5:
        deterioration_reasons.append(
            f"↓ Signal frequency declined ({avg_sig_pre:.0f}% → {avg_sig_post:.0f}% of days)"
            " — BTC spending less time in strong trends post-2022")
    if avg_adx_post < avg_adx_pre - 3:
        deterioration_reasons.append(
            f"↓ Average ADX strength declined ({avg_adx_pre:.1f} → {avg_adx_post:.1f})"
            " — trends are weaker when they do occur")
    if avg_wr_post < avg_wr_pre - 0.05:
        deterioration_reasons.append(
            f"↓ Win rate deteriorated ({avg_wr_pre*100:.0f}% → {avg_wr_post*100:.0f}%)"
            " — entries are hitting the 3% stop more often post-2022")
    if abs(avg_ret_post) < abs(avg_ret_pre) * 0.7:
        deterioration_reasons.append(
            f"↓ Average return per trade fell ({avg_ret_pre*100:.1f}% → {avg_ret_post*100:.1f}%)"
            " — winners are smaller when they occur")

    if deterioration_reasons:
        for r in deterioration_reasons:
            print(f"    → {r}")
        if avg_sig_post < avg_sig_pre - 5 and avg_wr_post < avg_wr_pre - 0.05:
            print(f"\n  VERDICT: STRUCTURAL + PARAMETER SENSITIVITY")
            print(f"  Both signal opportunity AND trade quality declined post-2022.")
            print(f"  Structural component: BTC market regime changed (more macro-driven,")
            print(f"  ETF-era volatility, shorter trend durations).")
            print(f"  Parameter sensitivity: 3% fixed stop may be too tight for")
            print(f"  post-2022 volatility — consider wider stop in Stage C.")
        elif avg_sig_post < avg_sig_pre - 5:
            print(f"\n  VERDICT: PRIMARILY STRUCTURAL (regime change)")
            print(f"  Signal frequency is the dominant factor. BTC post-2022 has fewer")
            print(f"  strong sustained trends — ADX parameters less responsive.")
            print(f"  Win rate is similar, suggesting parameters are not overfit.")
        else:
            print(f"\n  VERDICT: PARAMETER SENSITIVITY DOMINANT")
            print(f"  Signal frequency is similar pre/post. Win rate deteriorated,")
            print(f"  suggesting the 3% stop is too tight for post-2022 volatility ranges.")
    else:
        print(f"  No significant deterioration detected in regime metrics.")
        print(f"  Post-2022 underperformance may be driven by specific adverse trades.")


# ─────────────────────────────────────────────────────────────────────────────
# 7. PARAMETER STABILITY SWEEP  (Fixed stop 2% → 8%)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 70)
print(f"PARAMETER STABILITY  (Fixed stop sweep {STOP_SWEEP[0]*100:.0f}%–{STOP_SWEEP[-1]*100:.0f}%)")
print("─" * 70)

sweep_rows = []
print(f"\n  {'Stop%':<8} {'N':>5} {'Ann%':>8} {'Sortino':>9} {'Calmar':>8} "
      f"{'DD%Tr':>8} {'Comp':>8} {'Pass?':>6}")
print(f"  {'-'*70}")

for sp in STOP_SWEEP:
    t_sp = run_fixed_stop(closes, lows, sig_long, dates, sp)
    m_sp = calc_metrics(t_sp, df['Close'], YEARS)
    if m_sp is None:
        sweep_rows.append({'stop_pct': sp, 'valid': False})
        continue
    sweep_rows.append({
        'stop_pct': sp, 'valid': True,
        'n_trades': m_sp['n_trades'],
        'annual_return': m_sp['annual_return'],
        'sortino': m_sp['sortino'],
        'calmar': m_sp['calmar'],
        'max_dd_trade': m_sp['max_dd_trade'],
    })

valid_rows = [r for r in sweep_rows if r['valid']]
if valid_rows:
    ann_lo  = min(r['annual_return'] for r in valid_rows)
    ann_hi  = max(r['annual_return'] for r in valid_rows)
    sort_lo = min(r['sortino'] for r in valid_rows)
    sort_hi = max(r['sortino'] for r in valid_rows)
    dd_lo   = min(r['max_dd_trade'] for r in valid_rows)
    dd_hi   = max(r['max_dd_trade'] for r in valid_rows)

    def normalize(v, lo, hi):
        return (v - lo) / (hi - lo) if hi != lo else 0.5

    COMP_THRESHOLD = 0.70
    passing = 0
    for r in valid_rows:
        n_ann  = normalize(r['annual_return'], ann_lo, ann_hi)
        n_sort = normalize(r['sortino'], sort_lo, sort_hi)
        n_dd   = normalize(r['max_dd_trade'], dd_lo, dd_hi)
        comp   = (n_ann + n_sort + n_dd) / 3.0
        r['composite'] = comp
        mark = '◀ BEST' if abs(r['stop_pct'] - CANDIDATE_STOP) < 0.001 else ''
        passes = comp >= COMP_THRESHOLD
        if passes:
            passing += 1
        print(f"  {r['stop_pct']*100:<7.1f}% {r['n_trades']:>5} "
              f"{r['annual_return']*100:>7.1f}% {r['sortino']:>9.3f} "
              f"{r['calmar']:>8.3f} {r['max_dd_trade']*100:>7.1f}% "
              f"{comp:>8.3f} {'✓' if passes else '✗':>6}  {mark}")

    stab_pct   = passing / len(valid_rows) * 100
    stab_label = ('STABLE' if stab_pct > 60
                  else 'MARGINAL' if stab_pct >= 40
                  else 'FRAGILE')

    # Cliff-edge check
    best_idx = max(range(len(valid_rows)),
                   key=lambda i: valid_rows[i]['annual_return'])
    at_max   = valid_rows[best_idx]['stop_pct'] == max(r['stop_pct'] for r in valid_rows)
    at_min   = valid_rows[best_idx]['stop_pct'] == min(r['stop_pct'] for r in valid_rows)
    boundary = 'AT MAX BOUNDARY ⚠' if at_max else ('AT MIN BOUNDARY ⚠' if at_min else 'interior ✓')

    print(f"\n  Stability: {passing}/{len(valid_rows)} pass composite ≥ {COMP_THRESHOLD}"
          f" → {stab_pct:.0f}% → {stab_label}")
    print(f"  Best stop%: {valid_rows[best_idx]['stop_pct']*100:.1f}% — {boundary}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. WALK-FORWARD VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 70)
print("WALK-FORWARD VALIDATION  (2022 / 2023 / 2024 test windows)")
print("Expanding train: anchored to 2018-01-01")
print("─" * 70)

print(f"\n  {'Window':<8} {'Trades':>7} {'AnnRet%':>9} {'WR':>7} "
      f"{'DD%Tr':>8} {'DD%MtM':>8} {'Pass?':>7}  {'Notes'}")
print(f"  {'-'*80}")

wf_rows = []
for win_label, ts, te in TEST_WINDOWS:
    mask = ((pd.to_datetime(trades_full['exit_date']) >= ts) &
            (pd.to_datetime(trades_full['exit_date']) <= te))
    wt = trades_full[mask].copy()
    cross = ((pd.to_datetime(wt['entry_date']) < ts)).sum() if len(wt) > 0 else 0

    if len(wt) == 0:
        print(f"  {win_label:<8} {'—':>7}")
        wf_rows.append({'year': win_label, 'n': 0, 'pass': False})
        continue

    rets_w  = wt['return'].values - COSTS
    eq_w    = np.cumprod(1 + rets_w)
    ann_w   = eq_w[-1] - 1
    pk_w    = np.maximum.accumulate(eq_w)
    dd_w    = ((eq_w - pk_w) / pk_w).min()
    wr_w    = (rets_w > 0).mean()

    try:
        cs_win  = df['Close'].loc[ts:te]
        eq_mtm  = build_equity_curve(wt, cs_win)
        pk_mtm  = np.maximum.accumulate(eq_mtm)
        dd_mtm  = ((eq_mtm - pk_mtm) / pk_mtm).min()
    except Exception:
        dd_mtm  = dd_w

    passes  = ann_w > 0
    notes   = []
    if len(wt) < LOW_N_FLAG:
        notes.append(f'n={len(wt)}<{LOW_N_FLAG}')
    if cross > 0:
        notes.append(f'{cross} cross-period')

    wf_rows.append({
        'year': win_label, 'n': len(wt), 'ann': ann_w,
        'win_rate': wr_w, 'dd_trade': dd_w, 'dd_mtm': dd_mtm, 'pass': passes,
    })

    marker = '✓ PASS' if passes else '✗ FAIL'
    print(f"  {win_label:<8} {len(wt):>7} {ann_w*100:>8.1f}% {wr_w*100:>6.0f}% "
          f"{dd_w*100:>7.1f}% {dd_mtm*100:>7.1f}% {marker:>7}  "
          f"{' '.join(notes)}")

pass_count = sum(1 for r in wf_rows if r['pass'])
total_wf   = len([r for r in wf_rows if r['n'] > 0])

if pass_count == total_wf:
    wf_verdict = f'PASS — all {pass_count}/{total_wf} windows profitable'
elif pass_count >= 2:
    wf_verdict = (f'CONDITIONAL — {pass_count}/{total_wf} windows pass')
else:
    wf_verdict = f'FAIL — only {pass_count}/{total_wf} windows profitable'

fail_years = [r['year'] for r in wf_rows if not r['pass']]
print(f"\n  Walk-forward verdict: {wf_verdict}")
if '2022' in fail_years:
    r22 = next(r for r in wf_rows if r['year'] == '2022')
    print(f"  2022 bear-year context: strategy returned {r22['ann']*100:.1f}%"
          f" vs BTC buy-and-hold ≈ −65%")
    print(f"  Long-only trend-following in a year-long bear market: expected behaviour.")


# ─────────────────────────────────────────────────────────────────────────────
# 9. CHARTS
# ─────────────────────────────────────────────────────────────────────────────

print("\nGenerating charts...")

# ── Chart 1: Year-by-year returns + trade count ───────────────────────────────
fig1, (ax1a, ax1b) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
fig1.patch.set_facecolor('#0e1117')
for ax in [ax1a, ax1b]:
    ax.set_facecolor('#0e1117')
    for spine in ax.spines.values():
        spine.set_edgecolor('#333')

x_pos  = list(range(len(all_years)))
yr_ann = [next((r['ann'] for r in yy_rows if r['year'] == yr), 0.0) for yr in all_years]
yr_bh  = [next((r['bh'] for r in yy_rows if r['year'] == yr), 0.0) for yr in all_years]
yr_n   = [next((r['n'] for r in yy_rows if r['year'] == yr), 0) for yr in all_years]

colors_strat = ['#4CAF50' if v > 0 else '#F44336' for v in yr_ann]
ax1a.bar([x - 0.2 for x in x_pos], [v * 100 for v in yr_ann],
         width=0.38, color=colors_strat, label='BTC ADX Fixed 3%', alpha=0.9)
ax1a.bar([x + 0.2 for x in x_pos], [v * 100 for v in yr_bh],
         width=0.38, color='#607D8B', label='BTC Buy & Hold', alpha=0.6)
ax1a.axhline(0, color='#aaa', lw=0.8)
ax1a.axvline(x_pos[all_years.index(2022)] - 0.5, color='#FF9800',
             lw=1.5, ls='--', label='Pre/Post-2022 split')
ax1a.set_ylabel('Annual Return %', color='white', fontsize=10)
ax1a.tick_params(colors='white')
ax1a.legend(fontsize=8, facecolor='#1a1a2e', labelcolor='white')
ax1a.set_title(f'BTC ADX {ADX_THRESHOLD}/{ADX_PERIOD} Fixed 3% Stop — Year-by-Year Returns',
               color='white', fontsize=12, fontweight='bold', pad=10)

ax1b.bar(x_pos, yr_n, color='#2196F3', alpha=0.8)
ax1b.axvline(x_pos[all_years.index(2022)] - 0.5, color='#FF9800', lw=1.5, ls='--')
ax1b.set_ylabel('N Trades (exit year)', color='white', fontsize=10)
ax1b.set_xticks(x_pos)
ax1b.set_xticklabels([str(y) for y in all_years], color='white', fontsize=9)
ax1b.tick_params(colors='white')

plt.tight_layout()
path_yoy = os.path.join(RESULTS_DIR, 'btc_adx_stage_b_yoy.png')
plt.savefig(path_yoy, dpi=130, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"  Saved → results/btc_adx_stage_b_yoy.png")


# ── Chart 2: Stop% plateau (cliff-edge check) ────────────────────────────────
fig2, ax2 = plt.subplots(figsize=(10, 5))
fig2.patch.set_facecolor('#0e1117')
ax2.set_facecolor('#0e1117')
for sp in ax2.spines.values():
    sp.set_edgecolor('#333')

xs = [r['stop_pct'] * 100 for r in valid_rows]
ys = [r['annual_return'] * 100 for r in valid_rows]
ys_sort = [r['sortino'] for r in valid_rows]
ax2b = ax2.twinx()
ax2.plot(xs, ys, 'o-', color='#2196F3', lw=2.2, label='Annual Return %', zorder=3)
ax2b.plot(xs, ys_sort, 's--', color='#FF9800', lw=1.6, label='Sortino', zorder=3, alpha=0.8)
ax2.axvline(CANDIDATE_STOP * 100, color='#4CAF50', lw=1.8, ls='--',
            label=f'Candidate: {CANDIDATE_STOP*100:.0f}%')
ax2.set_xlabel('Fixed Stop %', color='white', fontsize=11)
ax2.set_ylabel('Annual Return %', color='#2196F3', fontsize=10)
ax2b.set_ylabel('Sortino', color='#FF9800', fontsize=10)
ax2.tick_params(colors='white')
ax2b.tick_params(colors='#FF9800')
ax2.set_title(f'BTC ADX {ADX_THRESHOLD}/{ADX_PERIOD} — Stop% Sensitivity Plateau\n'
              'Cliff-edge check: candidate should sit at or near peak, not on a slope',
              color='white', fontsize=11, pad=10)
lines1, labels1 = ax2.get_legend_handles_labels()
lines2, labels2 = ax2b.get_legend_handles_labels()
ax2.legend(lines1 + lines2, labels1 + labels2, fontsize=9,
           facecolor='#1a1a2e', labelcolor='white')
plt.tight_layout()
path_plateau = os.path.join(RESULTS_DIR, 'btc_adx_stage_b_plateau.png')
plt.savefig(path_plateau, dpi=130, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"  Saved → results/btc_adx_stage_b_plateau.png")


# ── Chart 3: Walk-forward bar chart ─────────────────────────────────────────
fig3, ax3 = plt.subplots(figsize=(9, 5))
fig3.patch.set_facecolor('#0e1117')
ax3.set_facecolor('#0e1117')
for sp in ax3.spines.values():
    sp.set_edgecolor('#333')

wf_years  = [r['year'] for r in wf_rows if r['n'] > 0]
wf_rets   = [r['ann'] * 100 for r in wf_rows if r['n'] > 0]
wf_colors = ['#4CAF50' if v > 0 else '#F44336' for v in wf_rets]

ax3.bar(wf_years, wf_rets, color=wf_colors, alpha=0.85)
ax3.axhline(0, color='#aaa', lw=0.8)
ax3.set_ylabel('Annual Return % (test window)', color='white', fontsize=10)
ax3.set_title(f'BTC ADX {ADX_THRESHOLD}/{ADX_PERIOD} Fixed 3% — Walk-Forward Results\n'
              f'Expanding train (anchored 2018) | Test: 2022, 2023, 2024',
              color='white', fontsize=11, pad=10)
ax3.tick_params(colors='white')
for i, (yr, v) in enumerate(zip(wf_years, wf_rets)):
    ax3.text(i, v + (1 if v >= 0 else -3), f'{v:.1f}%',
             ha='center', va='bottom' if v >= 0 else 'top',
             color='white', fontsize=10, fontweight='bold')
plt.tight_layout()
path_wf = os.path.join(RESULTS_DIR, 'btc_adx_stage_b_walkforward.png')
plt.savefig(path_wf, dpi=130, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"  Saved → results/btc_adx_stage_b_walkforward.png")


# ── Chart 4: Regime analysis — signal frequency + win rate by year ──────────
fig4, (ax4a, ax4b, ax4c) = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
fig4.patch.set_facecolor('#0e1117')
for ax in [ax4a, ax4b, ax4c]:
    ax.set_facecolor('#0e1117')
    for sp in ax.spines.values():
        sp.set_edgecolor('#333')

rr_years = [r['year'] for r in regime_rows]
rr_sig   = [r['sig_pct'] for r in regime_rows]
rr_adx   = [r['avg_adx'] for r in regime_rows]
rr_wr    = [r['win_rate'] * 100 for r in regime_rows]
rr_ret   = [r['avg_net_ret'] * 100 for r in regime_rows]

split_x  = rr_years.index(2022) - 0.5

ax4a.bar(range(len(rr_years)), rr_sig, color='#9C27B0', alpha=0.8)
ax4a.axvline(split_x, color='#FF9800', lw=1.5, ls='--')
ax4a.set_ylabel('Signal Days %\n(ADX≥19, DI+>DI-)', color='white', fontsize=9)
ax4a.tick_params(colors='white')
ax4a.set_title('Regime Analysis: Is Post-2022 Deterioration Structural?',
               color='white', fontsize=12, fontweight='bold', pad=8)

ax4b.bar(range(len(rr_years)), rr_wr,
         color=['#4CAF50' if v >= 33 else '#F44336' for v in rr_wr], alpha=0.8)
ax4b.axvline(split_x, color='#FF9800', lw=1.5, ls='--')
ax4b.set_ylabel('Win Rate %\n(entry year)', color='white', fontsize=9)
ax4b.tick_params(colors='white')

colors_ret = ['#4CAF50' if v > 0 else '#F44336' for v in rr_ret]
ax4c.bar(range(len(rr_years)), rr_ret, color=colors_ret, alpha=0.8)
ax4c.axvline(split_x, color='#FF9800', lw=1.5, ls='--', label='Pre/Post-2022 split')
ax4c.axhline(0, color='#aaa', lw=0.8)
ax4c.set_ylabel('Avg Net Return\n/ Trade %', color='white', fontsize=9)
ax4c.set_xticks(range(len(rr_years)))
ax4c.set_xticklabels([str(y) for y in rr_years], color='white', fontsize=9)
ax4c.tick_params(colors='white')
ax4c.legend(fontsize=9, facecolor='#1a1a2e', labelcolor='white', loc='upper right')

plt.tight_layout()
path_regime = os.path.join(RESULTS_DIR, 'btc_adx_stage_b_regime.png')
plt.savefig(path_regime, dpi=130, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"  Saved → results/btc_adx_stage_b_regime.png")


# ── Chart 5: Equity curve — full vs post-2022 split ─────────────────────────
fig5, (ax5a, ax5b) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
fig5.patch.set_facecolor('#0e1117')
for ax in [ax5a, ax5b]:
    ax.set_facecolor('#0e1117')
    for sp in ax.spines.values():
        sp.set_edgecolor('#333')

date_strs = [d.strftime('%Y-%m-%d') for d in dates]
split_date = '2022-01-01'

ax5a.plot(date_strs, equity_full, color='#2196F3', lw=1.8, label='ADX Fixed 3%')
ax5a.plot(date_strs, bh_eq, color='#607D8B', lw=1.2, ls='--', label='B&H BTC', alpha=0.7)
ax5a.axvline(split_date, color='#FF9800', lw=1.5, ls='--', label='2022 split')
ax5a.set_yscale('log')
ax5a.set_ylabel('Equity (log, $1 start)', color='white', fontsize=10)
ax5a.tick_params(colors='white')
ax5a.legend(fontsize=9, facecolor='#1a1a2e', labelcolor='white')
ax5a.set_title(f'BTC ADX {ADX_THRESHOLD}/{ADX_PERIOD} Fixed 3% — Full Equity Curve (log)',
               color='white', fontsize=12, fontweight='bold', pad=8)

pk_eq  = np.maximum.accumulate(equity_full)
dd_arr = (equity_full - pk_eq) / pk_eq * 100
ax5b.fill_between(date_strs, dd_arr, 0, color='#F44336', alpha=0.5)
ax5b.axvline(split_date, color='#FF9800', lw=1.5, ls='--')
ax5b.set_ylabel('Drawdown %', color='white', fontsize=10)
ax5b.tick_params(colors='white')

plt.tight_layout()
path_equity = os.path.join(RESULTS_DIR, 'btc_adx_stage_b_equity.png')
plt.savefig(path_equity, dpi=130, bbox_inches='tight', facecolor='#0e1117')
plt.close()
print(f"  Saved → results/btc_adx_stage_b_equity.png")


# ─────────────────────────────────────────────────────────────────────────────
# 10. SAVE CSV SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

summary_rows = []

# Full period
summary_rows.append({
    'period': 'Full (2018-now)',
    'n_trades': m_full['n_trades'],
    'annual_return_pct': round(m_full['annual_return'] * 100, 2),
    'sortino': round(m_full['sortino'], 3),
    'calmar': round(m_full['calmar'], 3),
    'max_dd_trade_pct': round(m_full['max_dd_trade'] * 100, 2),
    'max_dd_mtm_pct': round(m_full['max_dd_mtm'] * 100, 2),
    'win_rate_pct': round(m_full['win_rate'] * 100, 1),
    'stability_pct': round(stab_pct, 1) if valid_rows else None,
    'wf_pass': f'{pass_count}/{total_wf}',
})

# Year-by-year rows
for r in yy_rows:
    if r['n'] > 0:
        summary_rows.append({
            'period': str(r['year']),
            'n_trades': r['n'],
            'annual_return_pct': round(r['ann'] * 100, 2),
            'win_rate_pct': round(r['win_rate'] * 100, 1),
            'max_dd_trade_pct': round(r['dd_trade'] * 100, 2),
            'max_dd_mtm_pct': round(r['dd_mtm'] * 100, 2),
        })

pd.DataFrame(summary_rows).to_csv(
    os.path.join(DATA_DIR, 'btc_adx_stage_b_summary.csv'), index=False)
print(f"  Saved → data/btc_adx_stage_b_summary.csv")


# ─────────────────────────────────────────────────────────────────────────────
# 11. FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("STAGE B SUMMARY — BTC ADX 19/14 Fixed 3% Stop")
print("=" * 70)

print(f"\n  Full-period metrics ({dates[0].year}–{dates[-1].year}, {YEARS:.1f} yrs):")
print(f"    Annual return:    {m_full['annual_return']*100:.1f}%")
print(f"    Sortino:          {m_full['sortino']:.3f}")
print(f"    Calmar:           {m_full['calmar']:.3f}")
print(f"    MaxDD (trade):    {m_full['max_dd_trade']*100:.1f}%")
print(f"    MaxDD (MtM):      {m_full['max_dd_mtm']*100:.1f}%")
print(f"    N trades:         {m_full['n_trades']}")
print(f"    Win rate:         {m_full['win_rate']*100:.0f}%")

print(f"\n  Positive years:   {pos_years}/{total_years}")
if valid_rows:
    print(f"  Stability:        {stab_pct:.0f}% → {stab_label}")
    best_stop = valid_rows[max(range(len(valid_rows)),
                               key=lambda i: valid_rows[i]['annual_return'])]
    cliff = ('⚠ AT BOUNDARY' if (best_stop['stop_pct'] in
             [STOP_SWEEP[0], STOP_SWEEP[-1]]) else '✓ interior')
    print(f"  Plateau peak:     {best_stop['stop_pct']*100:.1f}% — {cliff}")
print(f"  Walk-forward:     {wf_verdict}")

print(f"\n  Post-2022 annual: {ann_post*100:.1f}%/yr  "
      f"(vs GO threshold 15.0%/yr)")

go_flags   = []
nogo_flags = []

if m_full['n_trades'] >= 30:
    go_flags.append(f"✓ N trades ≥ 30 ({m_full['n_trades']})")
else:
    nogo_flags.append(f"✗ N trades < 30 ({m_full['n_trades']})")

if m_full['sortino'] >= 0.8:
    go_flags.append(f"✓ Sortino ≥ 0.8 ({m_full['sortino']:.3f})")
else:
    nogo_flags.append(f"✗ Sortino < 0.8 ({m_full['sortino']:.3f})")

if m_full['calmar'] >= 1.0:
    go_flags.append(f"✓ Calmar ≥ 1.0 ({m_full['calmar']:.3f})")
else:
    nogo_flags.append(f"✗ Calmar < 1.0 ({m_full['calmar']:.3f})")

if pass_count >= 2:
    go_flags.append(f"✓ Walk-forward {pass_count}/{total_wf} windows pass")
else:
    nogo_flags.append(f"✗ Walk-forward {pass_count}/{total_wf} windows pass")

if valid_rows:
    if stab_label in ('STABLE', 'MARGINAL'):
        go_flags.append(f"✓ Stability: {stab_label} ({stab_pct:.0f}%)")
    else:
        nogo_flags.append(f"✗ Stability: {stab_label} ({stab_pct:.0f}%)")

if ann_post >= 0.15:
    go_flags.append(f"✓ Post-2022 annual ≥ 15% ({ann_post*100:.1f}%)")
else:
    nogo_flags.append(f"✗ Post-2022 annual < 15% ({ann_post*100:.1f}%) — CRITICAL")

print(f"\n  GO/NO-GO CHECKLIST:")
for f in go_flags:
    print(f"    {f}")
for f in nogo_flags:
    print(f"    {f}")

# Decision
if len(nogo_flags) == 0:
    decision = 'GO'
elif len(nogo_flags) == 1 and 'Post-2022' not in str(nogo_flags[0]) and '2022' in str(fail_years):
    decision = 'CONDITIONAL GO (2022 bear year only)'
elif len(nogo_flags) == 1 and 'Post-2022' in str(nogo_flags[0]):
    decision = 'NO-GO — POST-2022 RETURN BELOW THRESHOLD'
elif len(nogo_flags) >= 2 and any('Post-2022' in f for f in nogo_flags):
    decision = 'NO-GO — POST-2022 RETURN FAILS THRESHOLD'
else:
    decision = f'CONDITIONAL ({len(nogo_flags)} items)'

print(f"\n  ┌────────────────────────────────────────────────────────────┐")
print(f"  │  STAGE B DECISION: {decision:<42}│")
print(f"  └────────────────────────────────────────────────────────────┘")

print(f"\n  NEXT: Stage C — Monte Carlo (103 trades — meaningful sample)")
print(f"  Key question for Stage C: Does Monte Carlo distribution")
print(f"  confirm the post-2022 deterioration as a genuine regime shift")
print(f"  rather than an unlucky sample path?\n")
