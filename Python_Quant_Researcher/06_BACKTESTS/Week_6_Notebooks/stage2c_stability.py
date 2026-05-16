# Stage 2c — Stability Analysis
# Primary candidate:   SMA 135 / trail 25%
# Secondary candidate: SMA 145 / trail 20%
#
# Part A: Detailed year-by-year breakdown of SMA 135/25%
#         — individual trade returns, 2021 contribution, ex-2021 metrics
# Part B: Stability sweeps
#   1. SMA period sweep (110–170, step 5) — trail fixed at 25%
#   2. Trail% sweep (15–30%, step 2.5%) — SMA fixed at 135
#   3. Year-by-year profitability count
#   4. Half-split test
#   5. 2D heatmap: SMA 110-170 × trail 15-30%
#
# Composite = equal-weight mean of min-max normalised (Calmar, Sortino, Ann%, MaxDD%)
# MaxDD: all-negative — less negative = better = higher value, NO invert in minmax.
# Stability threshold: composite ≥ 0.7 within each sweep's own normalisation.
# Verdict: STABLE >60%  |  MARGINAL 40–60%  |  FRAGILE <40%

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import yfinance as yf

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)

COST_PER_TRADE    = 0.00075 * 2
MIN_TRADES        = 5
LOW_TRADES_FLAG   = 30
COMP_THRESHOLD    = 0.7          # stability pass threshold (within-sweep normalised)
STAB_PASS_PCT     = 60.0         # STABLE if % passing ≥ this
STAB_MARGINAL_PCT = 40.0         # MARGINAL if ≥ this; else FRAGILE

PRIMARY_SMA   = 135;  PRIMARY_TRAIL   = 0.25
SECONDARY_SMA = 145;  SECONDARY_TRAIL = 0.20

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

print("Fetching BTC-USD daily data...")
raw = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = raw[['Open', 'High', 'Low', 'Close']].dropna().copy()
df.index = pd.to_datetime(df.index)
closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index
years_full = (df.index[-1] - df.index[0]).days / 365.25
print(f"  {df.index[0].date()} → {df.index[-1].date()} ({len(df)} bars, {years_full:.2f} yrs)")

# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def run_sma_pct_trail(sma_period, trail_pct):
    sma_vals = pd.Series(closes).rolling(sma_period, min_periods=sma_period).mean().values
    fv = int(np.argmax(~np.isnan(sma_vals)))
    position = entry_i = 0
    entry_price = peak_price = stop_price = 0.0
    trades = []; sig_prev = False
    for i in range(fv, len(closes)):
        close, low, sv = closes[i], lows[i], sma_vals[i]
        if np.isnan(sv): continue
        sig_cur = close > sv
        if position == 1:
            if close > peak_price:
                peak_price = close; stop_price = peak_price * (1 - trail_pct)
            if low <= stop_price:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': stop_price,
                               'return': (stop_price - entry_price) / entry_price,
                               'exit_reason': 'TRAIL_STOP'}); position = 0
            elif not sig_cur:
                trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                               'exit_date': dates[i], 'exit_price': close,
                               'return': (close - entry_price) / entry_price,
                               'exit_reason': 'SMA_EXIT'}); position = 0
        if position == 0 and sig_cur and not sig_prev:
            position = 1; entry_i = i; entry_price = close
            peak_price = close; stop_price = close * (1 - trail_pct)
        sig_prev = sig_cur
    if position == 1:
        trades.append({'entry_date': dates[entry_i], 'entry_price': entry_price,
                       'exit_date': dates[-1], 'exit_price': closes[-1],
                       'return': (closes[-1] - entry_price) / entry_price,
                       'exit_reason': 'END'})
    return trades


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def build_daily_equity(trades_df, close_series):
    n = len(close_series); ca = close_series.values
    d2i = pd.Series(np.arange(n), index=close_series.index)
    eq = np.ones(n); port = 1.0; prev = 0
    for _, t in trades_df.iterrows():
        ei = d2i.get(pd.Timestamp(t['entry_date']))
        xi = d2i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None: continue
        eq[prev:ei] = port
        eq[ei:xi+1] = port * ca[ei:xi+1] / t['entry_price']
        port *= (1 + t['return'] - COST_PER_TRADE); eq[xi] = port; prev = xi + 1
    eq[prev:] = port
    return eq


def metrics_from_trades(trades, yrs, close_series, exclude_year=None):
    df_t = pd.DataFrame(trades)
    if len(df_t) == 0: return None
    df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
    df_t['exit_date']  = pd.to_datetime(df_t['exit_date'])
    if exclude_year is not None:
        df_t = df_t[df_t['exit_date'].dt.year != exclude_year].reset_index(drop=True)
    if len(df_t) < MIN_TRADES: return None
    df_t = df_t.sort_values('entry_date').reset_index(drop=True)
    rets = df_t['return'].values - COST_PER_TRADE
    wm = rets > 0; lm = rets <= 0
    win_rate      = wm.sum() / len(rets)
    gross_p       = rets[wm].sum() if wm.any() else 0.0
    gross_l       = abs(rets[lm].sum()) if lm.any() else 1e-9
    profit_factor = gross_p / gross_l
    total_ret     = np.prod(1 + rets) - 1
    ann_ret       = (1 + total_ret) ** (1 / yrs) - 1
    cum_eq        = np.cumprod(1 + rets)
    peak          = np.maximum.accumulate(cum_eq)
    max_dd        = ((cum_eq - peak) / peak).min()
    calmar        = ann_ret / abs(max_dd) if max_dd != 0 else 0.0
    cs = close_series.loc[df_t['entry_date'].min() : df_t['exit_date'].max()]
    eq = build_daily_equity(df_t, cs)
    dr = np.diff(eq) / eq[:-1]; dn = dr[dr < 0]
    sharpe  = dr.mean() / dr.std()  * np.sqrt(365) if dr.std() > 0 else 0.0
    sortino = dr.mean() / dn.std()  * np.sqrt(365) if (len(dn) > 0 and dn.std() > 0) else 0.0
    stop_pct = (df_t['exit_reason'] == 'TRAIL_STOP').sum() / len(df_t) * 100 \
               if 'exit_reason' in df_t.columns else 0.0
    return {'total_trades': len(df_t), 'win_rate': win_rate,
            'profit_factor': profit_factor, 'annual_return': ann_ret,
            'max_drawdown': max_dd, 'calmar': calmar,
            'sharpe': sharpe, 'sortino': sortino,
            'stop_exit_pct': stop_pct, 'low_trades': len(df_t) < LOW_TRADES_FLAG}


def composite_score_list(rows):
    """Given list of metric dicts, add composite score. Returns DataFrame."""
    df_r = pd.DataFrame(rows)
    def mm(s):
        lo, hi = s.min(), s.max()
        return pd.Series(0.5, index=s.index) if hi == lo else (s - lo) / (hi - lo)
    df_r['norm_calmar']  = mm(df_r['calmar'])
    df_r['norm_sortino'] = mm(df_r['sortino'])
    df_r['norm_annual']  = mm(df_r['annual_return'])
    df_r['norm_maxdd']   = mm(df_r['max_drawdown'])   # less negative = higher = better, no invert
    df_r['composite']    = (df_r['norm_calmar'] + df_r['norm_sortino'] +
                             df_r['norm_annual'] + df_r['norm_maxdd']) / 4.0
    return df_r


def stability_verdict(pct_passing):
    if pct_passing >= STAB_PASS_PCT:     return "STABLE"
    if pct_passing >= STAB_MARGINAL_PCT: return "MARGINAL"
    return "FRAGILE"

# ---------------------------------------------------------------------------
# Pre-compute SMA caches for sweep ranges
# ---------------------------------------------------------------------------

SMA_SWEEP   = list(range(110, 171, 5))   # 13 values
TRAIL_SWEEP = [round(x, 4) for x in np.arange(0.15, 0.305, 0.025)]  # 7: 15-30%

print("Pre-computing SMA cache for sweep range...")
sma_cache = {p: pd.Series(closes).rolling(p, min_periods=p).mean().values
             for p in range(80, 171, 5)}

# ===========================================================================
# PART A — Detailed year-by-year breakdown: SMA 135/25%
# ===========================================================================

print("\n" + "=" * 76)
print(f"PART A — Detailed breakdown: SMA {PRIMARY_SMA} / trail {PRIMARY_TRAIL*100:.1f}%")
print("=" * 76)

trades_primary = run_sma_pct_trail(PRIMARY_SMA, PRIMARY_TRAIL)
df_p = pd.DataFrame(trades_primary)
df_p['entry_date'] = pd.to_datetime(df_p['entry_date'])
df_p['exit_date']  = pd.to_datetime(df_p['exit_date'])
df_p['return_net'] = df_p['return'] - COST_PER_TRADE
df_p['exit_year']  = df_p['exit_date'].dt.year
df_p['hold_days']  = (df_p['exit_date'] - df_p['entry_date']).dt.days

print(f"\n  Total trades: {len(df_p)}  |  "
      f"Win rate: {(df_p['return_net']>0).mean()*100:.1f}%  |  "
      f"Avg hold: {df_p['hold_days'].mean():.1f} days")

# Individual trade returns by year
print("\n  Year-by-year with individual trade returns")
print("  " + "─" * 72)

# Build running portfolio to compute 2021 contribution properly
rets_all  = df_p['return_net'].values
portvals   = np.cumprod(1 + rets_all)   # ending portfolio values per trade
port_start = np.concatenate([[1.0], portvals[:-1]])  # portfolio at start of each trade

yr_stats = {}
for yr in sorted(df_p['exit_year'].unique()):
    mask   = df_p['exit_year'].values == yr
    yr_idx = np.where(mask)[0]
    yr_trades_df = df_p[mask].reset_index(drop=True)
    yr_rets = yr_trades_df['return_net'].values
    yr_port_before = port_start[yr_idx[0]]      # portfolio value entering 2021
    yr_port_after  = portvals[yr_idx[-1]]       # portfolio value after last 2021 trade
    yr_net         = yr_port_after / yr_port_before - 1

    note = "(partial)" if yr == df_p['exit_year'].max() else ""
    print(f"\n  {yr}  [{len(yr_trades_df)} trades, net {yr_net*100:+.1f}%]  {note}")
    for j, (_, row) in enumerate(yr_trades_df.iterrows(), 1):
        prefix = "   " if row['return_net'] >= 0 else "  "
        print(f"    Trade {j:>2}: entry {row['entry_date'].date()} → "
              f"exit {row['exit_date'].date()}  "
              f"({row['hold_days']:>3}d)  "
              f"return {row['return_net']*100:>+7.2f}%  [{row['exit_reason']}]")
    yr_stats[yr] = {
        'n': len(yr_trades_df), 'net': yr_net,
        'port_before': yr_port_before, 'port_after': yr_port_after,
    }

# 2021 contribution
total_port = portvals[-1]
port_before_2021 = yr_stats[2021]['port_before']
port_after_2021  = yr_stats[2021]['port_after']
# Absolute gain from 2021 (portfolio terms): P_after_2021 × remaining_factor - P_before_2021 × remaining_factor
# Simplify: contribution = (P_after_2021 - P_before_2021) × (total_port / P_after_2021)
remaining_factor = total_port / port_after_2021
gain_2021_in_total_terms = (port_after_2021 - port_before_2021) * remaining_factor
total_absolute_gain = total_port - 1.0
contribution_2021 = gain_2021_in_total_terms / total_absolute_gain * 100

print(f"\n  " + "─" * 72)
print(f"\n  Total compounded return (all years): {(total_port - 1)*100:.1f}%  "
      f"({total_port:.3f}× starting capital)")
print(f"\n  2021 breakdown:")
print(f"    Portfolio entering 2021:     {port_before_2021:.3f}×")
print(f"    Portfolio after 2021 trades: {port_after_2021:.3f}×  "
      f"(2021 year factor: {yr_stats[2021]['net']*100:+.1f}%)")
print(f"    Remaining factor (2022-on):  {remaining_factor:.3f}×")
print(f"    2021 contribution to total absolute gain: "
      f"{contribution_2021:.1f}% of the {(total_port-1)*100:.1f}% total return")

# Ex-2021 metrics
print(f"\n  Metrics with 2021 trades excluded entirely:")
yr_2021_days = 365
ex21_yrs = years_full - yr_2021_days / 365.25
m_ex21 = metrics_from_trades(trades_primary, ex21_yrs, df['Close'], exclude_year=2021)
if m_ex21:
    flag = " [!low n]" if m_ex21['low_trades'] else ""
    print(f"    Trades:        {m_ex21['total_trades']}{flag}")
    print(f"    Annual return: {m_ex21['annual_return']*100:.1f}%")
    print(f"    Max drawdown:  {m_ex21['max_drawdown']*100:.1f}%")
    print(f"    Calmar:        {m_ex21['calmar']:.3f}")
    print(f"    Sortino:       {m_ex21['sortino']:.3f}")
    print(f"    Sharpe:        {m_ex21['sharpe']:.3f}")
    print(f"    Win rate:      {m_ex21['win_rate']*100:.1f}%")
else:
    print(f"    Insufficient trades after excluding 2021.")

# Full-period reference
m_full = metrics_from_trades(trades_primary, years_full, df['Close'])
print(f"\n  Full-period reference (incl. 2021):")
print(f"    Annual return: {m_full['annual_return']*100:.1f}%  |  "
      f"Calmar: {m_full['calmar']:.3f}  |  Sortino: {m_full['sortino']:.3f}  |  "
      f"MaxDD: {m_full['max_drawdown']*100:.1f}%")

# ===========================================================================
# PART B — Stage 2c Stability Analysis
# ===========================================================================

print("\n" + "=" * 76)
print("PART B — Stage 2c Stability Analysis")
print(f"  Primary:   SMA {PRIMARY_SMA} / trail {PRIMARY_TRAIL*100:.1f}%")
print(f"  Secondary: SMA {SECONDARY_SMA} / trail {SECONDARY_TRAIL*100:.1f}%")
print(f"  Composite threshold: ≥ {COMP_THRESHOLD} (normalised within each sweep)")
print("=" * 76)


def run_sweep(sweep_label, param_values, param_name, run_fn,
              fixed_desc, threshold=COMP_THRESHOLD):
    """Run a 1D parameter sweep, compute composite scores, return verdict."""
    rows = []
    for v in param_values:
        trades = run_fn(v)
        m = metrics_from_trades(trades, years_full, df['Close'])
        if m is None:
            rows.append({'param': v, 'calmar': -99, 'sortino': -99,
                         'annual_return': -99, 'max_drawdown': -99,
                         'total_trades': 0, 'valid': False})
        else:
            rows.append({'param': v, **{k: m[k] for k in
                         ('calmar','sortino','annual_return','max_drawdown',
                          'total_trades','low_trades','win_rate','stop_exit_pct')},
                         'valid': True})
    df_sw = pd.DataFrame(rows)
    valid = df_sw[df_sw['valid']].copy()
    if len(valid) < 2:
        print(f"\n  {sweep_label}: insufficient valid results")
        return 0.0

    df_scored = composite_score_list(valid.to_dict('records'))
    df_sw.loc[df_sw['valid'], 'composite'] = df_scored['composite'].values
    df_sw['composite'] = df_sw['composite'].fillna(0)

    n_pass = (df_scored['composite'] >= threshold).sum()
    n_tot  = len(df_scored)
    pct    = n_pass / n_tot * 100

    print(f"\n  {sweep_label}  ({fixed_desc})")
    print(f"  {'─'*66}")
    H = (f"  {'Param':>8}  {'Comp':>5}  {'Calmar':>7}  {'Sortino':>7}  "
         f"{'Ann%':>6}  {'MaxDD%':>7}  {'n':>3}  {'Pass'}")
    print(H); print("  " + "─" * (len(H) - 2))
    for _, row in df_sw.iterrows():
        if not row['valid']:
            print(f"  {row['param']:>8}  [no valid result]"); continue
        score_row = df_scored[df_scored['param'] == row['param']]
        comp = score_row['composite'].values[0] if len(score_row) else 0
        flag = " !" if row.get('low_trades', False) else ""
        tick = "✓" if comp >= threshold else "✗"
        ann  = score_row['annual_return'].values[0] if len(score_row) else 0
        dd   = score_row['max_drawdown'].values[0] if len(score_row) else 0
        cal  = score_row['calmar'].values[0] if len(score_row) else 0
        sor  = score_row['sortino'].values[0] if len(score_row) else 0
        print(f"  {row['param']:>8}  {comp:>5.3f}  {cal:>7.3f}  {sor:>7.3f}  "
              f"{ann:>6.1f}  {dd:>7.1f}  {int(row['total_trades']):>3}  {tick}{flag}")
    verdict = stability_verdict(pct)
    print(f"\n  → {n_pass}/{n_tot} values ≥ {threshold} composite = {pct:.0f}%  "
          f"[{verdict}]")
    return pct, verdict, df_scored


# ----- Loop over both candidates -----
all_verdicts = {}

for cand_name, cand_sma, cand_trail in [
    (f"PRIMARY — SMA {PRIMARY_SMA}/trail {PRIMARY_TRAIL*100:.1f}%",
     PRIMARY_SMA, PRIMARY_TRAIL),
    (f"SECONDARY — SMA {SECONDARY_SMA}/trail {SECONDARY_TRAIL*100:.1f}%",
     SECONDARY_SMA, SECONDARY_TRAIL),
]:
    key = 'primary' if 'PRIMARY' in cand_name else 'secondary'
    all_verdicts[key] = {}

    print(f"\n{'━'*76}")
    print(f"  CANDIDATE: {cand_name}")
    print(f"{'━'*76}")

    # ------------------------------------------------------------------
    # Test 1: SMA period sweep (110–170, step 5) — trail fixed
    # ------------------------------------------------------------------
    result1 = run_sweep(
        "Test 1 — SMA period sweep (trail fixed)",
        SMA_SWEEP,
        "sma_period",
        lambda p, t=cand_trail: run_sma_pct_trail(p, t),
        f"trail = {cand_trail*100:.1f}%",
    )
    all_verdicts[key]['sma_sweep'] = result1[0] if isinstance(result1, tuple) else result1

    # ------------------------------------------------------------------
    # Test 2: Trail% sweep (15–30%, step 2.5%) — SMA fixed
    # ------------------------------------------------------------------
    result2 = run_sweep(
        "Test 2 — Trail% sweep (SMA fixed)",
        TRAIL_SWEEP,
        "trail_pct",
        lambda t, s=cand_sma: run_sma_pct_trail(s, t),
        f"SMA = {cand_sma}",
    )
    all_verdicts[key]['trail_sweep'] = result2[0] if isinstance(result2, tuple) else result2

    # ------------------------------------------------------------------
    # Test 3: Year-by-year profitability
    # ------------------------------------------------------------------
    print(f"\n  Test 3 — Year-by-year profitability")
    print(f"  {'─'*66}")
    trades_c = run_sma_pct_trail(cand_sma, cand_trail)
    df_c = pd.DataFrame(trades_c)
    df_c['entry_date'] = pd.to_datetime(df_c['entry_date'])
    df_c['exit_date']  = pd.to_datetime(df_c['exit_date'])
    df_c['return_net'] = df_c['return'] - COST_PER_TRADE
    df_c['exit_year']  = df_c['exit_date'].dt.year

    H3 = (f"  {'Year':>4}  {'n':>3}  {'Win%':>5}  {'Net ret':>8}  "
          f"{'Avg hold':>9}  {'Positive?'}")
    print(H3); print("  " + "─" * (len(H3) - 2))
    n_pos_years = 0; n_years = 0
    for yr in sorted(df_c['exit_year'].unique()):
        grp = df_c[df_c['exit_year'] == yr]
        rets = grp['return_net'].values
        net = (1 + rets).prod() - 1
        hold = (pd.to_datetime(grp['exit_date']) - pd.to_datetime(grp['entry_date'])).dt.days.mean()
        note = "(partial)" if yr == df_c['exit_year'].max() else ""
        is_pos = net > 0; n_years += 1; n_pos_years += is_pos
        tick = "✓" if is_pos else "✗"
        print(f"  {yr:>4}  {len(grp):>3}  {(rets>0).mean()*100:>5.1f}  "
              f"{net*100:>+7.1f}%  {hold:>9.1f}d  {tick} {note}")

    n_partial = 1  # 2026 is partial; exclude from profitability count
    n_complete = n_years - n_partial
    n_pos_complete = sum(
        1 for yr in list(df_c['exit_year'].unique())[:-1]
        for _ in [1]
        if (df_c[df_c['exit_year'] == yr]['return_net'].values.size > 0 and
            ((1 + df_c[df_c['exit_year'] == yr]['return_net'].values).prod() - 1) > 0)
    )
    yby_pct = n_pos_complete / n_complete * 100
    yby_verdict = stability_verdict(yby_pct)
    print(f"\n  → {n_pos_complete}/{n_complete} complete years positive = {yby_pct:.0f}%  "
          f"[{yby_verdict}]")
    all_verdicts[key]['year_by_year'] = yby_pct

    # ------------------------------------------------------------------
    # Test 4: Half-split
    # ------------------------------------------------------------------
    print(f"\n  Test 4 — Half-split test")
    print(f"  {'─'*66}")
    split_date = df.index[len(df) // 2]
    print(f"  Split at: {split_date.date()}")
    df_c2 = df_c.copy()

    for hlabel, ymask in [('H1 (earlier)', df_c2['entry_date'] < split_date),
                           ('H2 (later)',  df_c2['entry_date'] >= split_date)]:
        h_trades = df_c2[ymask].to_dict('records')
        m_h = metrics_from_trades(h_trades, years_full / 2, df['Close'])
        if m_h:
            flag = " [!low n]" if m_h['low_trades'] else ""
            print(f"  {hlabel}: n={m_h['total_trades']}{flag}  "
                  f"Calmar {m_h['calmar']:.3f}  Sortino {m_h['sortino']:.3f}  "
                  f"Ann {m_h['annual_return']*100:.1f}%  MaxDD {m_h['max_drawdown']*100:.1f}%")
        else:
            print(f"  {hlabel}: insufficient trades")


# ===========================================================================
# Test 5: 2D heatmap — SMA 110-170 × trail 15-30%  (both candidates)
# ===========================================================================

print("\n" + "=" * 76)
print("Test 5 — 2D Stability Heatmap: SMA period × Trail%")
print(f"  SMA sweep: {SMA_SWEEP[0]}–{SMA_SWEEP[-1]} (step 5)  ×  "
      f"Trail sweep: 15–30% (step 2.5%)")
print("=" * 76)

trail_vals = TRAIL_SWEEP   # 15% to 30%
sma_vals_2d = SMA_SWEEP    # 110 to 170

print("  Running 2D grid...")
rows_2d = []
n_2d = len(sma_vals_2d) * len(trail_vals)
done = 0
for sma_p, trail_p in [(s, t) for s in sma_vals_2d for t in trail_vals]:
    trades = run_sma_pct_trail(sma_p, trail_p)
    m = metrics_from_trades(trades, years_full, df['Close'])
    done += 1
    if done % 20 == 0:
        print(f"    {done}/{n_2d}...")
    if m is None:
        rows_2d.append({'sma_period': sma_p, 'trail_pct': round(trail_p*100,2),
                        'calmar': -99, 'sortino': -99, 'annual_return': -99,
                        'max_drawdown': -99, 'total_trades': 0, 'valid': False})
    else:
        rows_2d.append({'sma_period': sma_p, 'trail_pct': round(trail_p*100,2),
                        **{k: m[k] for k in ('calmar','sortino','annual_return',
                           'max_drawdown','total_trades','low_trades')},
                        'valid': True})

df_2d_all = pd.DataFrame(rows_2d)
valid_2d  = df_2d_all[df_2d_all['valid']].copy()

# Compute composite across all 91 valid combos
scored_2d = composite_score_list(valid_2d.to_dict('records'))
df_2d_all.loc[df_2d_all['valid'], 'composite'] = scored_2d['composite'].values
df_2d_all['composite'] = df_2d_all['composite'].fillna(0)

# Build matrix
sma_u   = sorted(df_2d_all['sma_period'].unique())
trail_u = sorted(df_2d_all['trail_pct'].unique())
mat_comp = np.full((len(trail_u), len(sma_u)), np.nan)
mat_cal  = np.full((len(trail_u), len(sma_u)), np.nan)

for _, row in df_2d_all.iterrows():
    if not row['valid']: continue
    ri = trail_u.index(row['trail_pct'])
    ci = sma_u.index(row['sma_period'])
    mat_comp[ri, ci] = row['composite']
    mat_cal[ri, ci]  = row['calmar']

# Mark primary and secondary candidates
prim_ri  = trail_u.index(round(PRIMARY_TRAIL  * 100, 2))
prim_ci  = sma_u.index(PRIMARY_SMA)
sec_ri   = trail_u.index(round(SECONDARY_TRAIL * 100, 2))
sec_ci   = sma_u.index(SECONDARY_SMA)

fig, axes = plt.subplots(1, 2, figsize=(18, 7))

for ax, mat, title, fmt in [
    (axes[0], mat_comp, 'Composite Score (Calmar+Sortino+Ann%+MaxDD)', '{:.2f}'),
    (axes[1], mat_cal,  'Calmar Ratio', '{:.2f}'),
]:
    vmax = np.nanmax(mat)
    im = ax.imshow(mat, aspect='auto', cmap='RdYlGn', origin='lower', vmin=0, vmax=vmax)
    ax.set_xticks(range(len(sma_u)))
    ax.set_xticklabels([str(s) for s in sma_u], rotation=45, ha='right', fontsize=8)
    ax.set_yticks(range(len(trail_u)))
    ax.set_yticklabels([f'{t:.1f}%' for t in trail_u], fontsize=8)
    ax.set_xlabel('SMA Period', fontsize=10)
    ax.set_ylabel('Trail %', fontsize=10)
    ax.set_title(title, fontweight='bold', fontsize=9)
    for ri in range(mat.shape[0]):
        for ci in range(mat.shape[1]):
            v = mat[ri, ci]
            if not np.isnan(v):
                ax.text(ci, ri, fmt.format(v), ha='center', va='center', fontsize=6,
                        color='black' if v > vmax * 0.45 else 'white')
    # Mark primary and secondary
    ax.add_patch(plt.Rectangle((prim_ci-0.5, prim_ri-0.5), 1, 1,
                                fill=False, edgecolor='blue', linewidth=2.5,
                                label=f'Primary (SMA {PRIMARY_SMA}/{PRIMARY_TRAIL*100:.0f}%)'))
    ax.add_patch(plt.Rectangle((sec_ci-0.5, sec_ri-0.5), 1, 1,
                                fill=False, edgecolor='purple', linewidth=2.5,
                                label=f'Secondary (SMA {SECONDARY_SMA}/{SECONDARY_TRAIL*100:.0f}%)'))
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
    plt.colorbar(im, ax=ax)

plt.suptitle(
    f'Stage 2c — Stability Heatmap: SMA 110–170 × Trail 15–30%\n'
    f'Composite normalised across all {len(valid_2d)} combos in this grid',
    fontweight='bold', fontsize=11,
)
plt.tight_layout()
hm_path = os.path.join(RESULTS_DIR, 'stage2c_stability_heatmap.png')
plt.savefig(hm_path, dpi=150, bbox_inches='tight'); plt.close()
print(f"\n  Saved → {hm_path}")

# Stats from 2D grid around candidates
print(f"\n  2D grid coverage (all 91 combos, SMA 110-170 × trail 15-30%):")
n_valid = (df_2d_all['valid']).sum()
for thresh in [0.5, 0.6, 0.7, 0.8]:
    n_p = (df_2d_all['composite'] >= thresh).sum()
    print(f"    Composite ≥ {thresh:.1f}:  {n_p:>3}/{n_valid}  ({n_p/n_valid*100:.1f}%)")

# ===========================================================================
# SUMMARY — Stability verdicts
# ===========================================================================

print("\n" + "=" * 76)
print("STAGE 2c STABILITY SUMMARY")
print("=" * 76)

for cand_label, cand_sma, cand_trail, key in [
    (f"SMA {PRIMARY_SMA} / trail {PRIMARY_TRAIL*100:.1f}%  (PRIMARY)",
     PRIMARY_SMA, PRIMARY_TRAIL, 'primary'),
    (f"SMA {SECONDARY_SMA} / trail {SECONDARY_TRAIL*100:.1f}%  (SECONDARY)",
     SECONDARY_SMA, SECONDARY_TRAIL, 'secondary'),
]:
    v = all_verdicts.get(key, {})
    sma_pct   = v.get('sma_sweep', 0)
    trail_pct = v.get('trail_sweep', 0)
    ybypct    = v.get('year_by_year', 0)
    overall   = (sma_pct + trail_pct + ybypct) / 3

    print(f"\n  {cand_label}")
    print(f"    Test 1 — SMA sweep:        {sma_pct:>5.1f}%  [{stability_verdict(sma_pct)}]")
    print(f"    Test 2 — Trail% sweep:     {trail_pct:>5.1f}%  [{stability_verdict(trail_pct)}]")
    print(f"    Test 3 — Year positivity:  {ybypct:>5.1f}%  [{stability_verdict(ybypct)}]")
    print(f"    Test 4 — Half-split:       (see details above)")
    print(f"    ─────────────────────────────────────────────")
    print(f"    Composite stability score: {overall:.1f}%  [{stability_verdict(overall)}]")

m_prim = metrics_from_trades(trades_primary, years_full, df['Close'])
trades_sec = run_sma_pct_trail(SECONDARY_SMA, SECONDARY_TRAIL)
m_sec  = metrics_from_trades(trades_sec, years_full, df['Close'])

print(f"\n  Raw metric comparison (full period):")
print(f"  {'Metric':<16}  {'Primary':>10}  {'Secondary':>10}")
print(f"  {'─'*40}")
for met_lbl, mp_val, ms_val in [
    ('Calmar',      m_prim['calmar'],            m_sec['calmar']),
    ('Sortino',     m_prim['sortino'],            m_sec['sortino']),
    ('Annual%',     m_prim['annual_return']*100,  m_sec['annual_return']*100),
    ('MaxDD%',      m_prim['max_drawdown']*100,   m_sec['max_drawdown']*100),
    ('Trades',      m_prim['total_trades'],        m_sec['total_trades']),
    ('Win%',        m_prim['win_rate']*100,        m_sec['win_rate']*100),
]:
    is_pct = met_lbl in ('Annual%', 'MaxDD%', 'Win%')
    fmt = "{:.1f}%" if is_pct else ("{:.0f}" if met_lbl == 'Trades' else "{:.3f}")
    pref_p = "►" if mp_val > ms_val else " "
    pref_s = "►" if ms_val > mp_val else " "
    if met_lbl == 'MaxDD%':  # lower magnitude is better
        pref_p = "►" if mp_val > ms_val else " "
        pref_s = "►" if ms_val > mp_val else " "
    print(f"  {met_lbl:<16}  {pref_p}{fmt.format(mp_val):>9}  {pref_s}{fmt.format(ms_val):>9}")

low_n_warn = ""
if m_prim['total_trades'] < LOW_TRADES_FLAG:
    low_n_warn = f"\n  WARNING: Primary candidate n={m_prim['total_trades']} < 30 trades."

print(f"\n{low_n_warn}")
print("\n[Stage 2c complete — awaiting instruction to continue to Stage 2d.]")
