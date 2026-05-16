#!/usr/bin/env python3
"""
BTC SMA Stage C — Monte Carlo: Return Magnitude Scaling (Option A)
Candidates: SMA110/T30% (primary), SMA125/T30% (secondary), SMA110/T20% (alt)
10,000 simulations | 5 magnitude scenarios (100%, 80%, 60%, 40%, 20%)
Winners scaled by magnitude factor; losers unchanged (structurally determined by stop).
Plain text output only — no charts, no HTML, no PNG.
"""

import os, warnings
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

COSTS            = 0.0015
N_SIM            = 10_000
MAGNITUDE_SCALES = [1.00, 0.80, 0.60, 0.40, 0.20]
FAN_YEAR_RANGE   = list(range(2018, 2027))   # 2018 → 2026 (2026 is partial)

CANDIDATES = [
    {'sma': 110, 'trail': 0.30, 'label': 'SMA110/T30%', 'role': 'Primary'},
    {'sma': 125, 'trail': 0.30, 'label': 'SMA125/T30%', 'role': 'Secondary'},
    {'sma': 110, 'trail': 0.20, 'label': 'SMA110/T20%', 'role': 'Trade-frequency alt'},
]

OUT_DIR  = '/Users/Greg/Documents/Python_Local_Folder/Python_Quant_Researcher/Week_7_Notebooks/results'
OUT_CSV  = os.path.join(OUT_DIR, 'btc_sma_stage_c_results.csv')
os.makedirs(OUT_DIR, exist_ok=True)

# ── Data ──────────────────────────────────────────────────────────────────────

raw = yf.download('BTC-USD', start='2018-01-01', progress=False, auto_adjust=True)
raw.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in raw.columns]
closes = raw['close'].values.astype(float)
lows   = raw['low'].values.astype(float)
dates  = [pd.Timestamp(d) for d in raw.index]
years  = (dates[-1] - dates[0]).days / 365.25

# ── Backtest ──────────────────────────────────────────────────────────────────

def run_pct_trail(closes, lows, sma_vals, dates, trail_pct):
    pos = 0; ep = peak = stop = 0.0; entry_date = None; trades = []
    for i in range(1, len(closes)):
        lo, cl, sm = lows[i], closes[i], sma_vals[i]
        if np.isnan(sm):
            continue
        if pos == 1:
            if cl > peak:
                peak = cl; stop = peak * (1 - trail_pct)
            if lo <= stop:
                trades.append({'entry_date': entry_date, 'exit_date': dates[i],
                               'return': (stop - ep) / ep})
                pos = 0; ep = peak = stop = 0.0; entry_date = None
            elif cl < sm:
                trades.append({'entry_date': entry_date, 'exit_date': dates[i],
                               'return': (cl - ep) / ep})
                pos = 0; ep = peak = stop = 0.0; entry_date = None
        elif cl > sm:
            ep = cl; peak = cl; stop = cl * (1 - trail_pct); pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)

# ── Monte Carlo core ──────────────────────────────────────────────────────────

def run_magnitude_mc(net_rets, exit_years_arr, scale, n_sim=N_SIM, seed_extra=0):
    """
    Resample N trades with replacement.
    Winners: actual return × scale.
    Losers:  actual return (unchanged — structurally determined by stop distance).
    Returns metrics dict + eq_full array (n_sim, n_trades+1).
    """
    winner_pos   = np.where(net_rets > 0)[0]
    loser_pos    = np.where(net_rets <= 0)[0]
    n_trades     = len(net_rets)
    n_win        = len(winner_pos)
    n_los        = len(loser_pos)
    winners_pool = net_rets[winner_pos]
    losers_pool  = net_rets[loser_pos]

    rng = np.random.default_rng(42 + seed_extra + int(scale * 1000))

    # Draw returns (all simulations at once — vectorised)
    sim_rets = np.zeros((n_sim, n_trades))
    if n_win > 0:
        sim_rets[:, winner_pos] = (
            rng.choice(winners_pool, size=(n_sim, n_win), replace=True) * scale
        )
    if n_los > 0:
        sim_rets[:, loser_pos] = rng.choice(losers_pool, size=(n_sim, n_los), replace=True)

    # Cumulative equity paths
    eq_paths = np.cumprod(1 + sim_rets, axis=1)            # (n_sim, n_trades)
    eq_full  = np.hstack([np.ones((n_sim, 1)), eq_paths])   # (n_sim, n_trades+1)

    # Full-period annualised returns
    ann_rets = eq_paths[:, -1] ** (1.0 / years) - 1

    # P(negative year) — actual calendar year structure from backtest
    unique_yrs = np.unique(exit_years_arr)
    neg_yr = 0; tot_yr = 0
    for yr in unique_yrs:
        yr_idx    = np.where(exit_years_arr == yr)[0]
        yr_comp   = np.prod(1 + sim_rets[:, yr_idx], axis=1)
        neg_yr   += (yr_comp < 1.0).sum()
        tot_yr   += n_sim
    p_neg_year = neg_yr / tot_yr if tot_yr > 0 else np.nan

    # Kelly fraction (binary formula on scaled distribution)
    avg_win_sc  = winners_pool.mean() * scale if n_win > 0 else 1e-9
    avg_los_abs = abs(losers_pool.mean())     if n_los > 0 else 1e-9
    wr          = n_win / n_trades
    kelly       = max(wr / avg_los_abs - (1.0 - wr) / avg_win_sc, 0.0)
    q_kelly     = kelly / 4.0

    return {
        'median_ann': np.median(ann_rets),
        'p10_ann':    np.percentile(ann_rets, 10),
        'p90_ann':    np.percentile(ann_rets, 90),
        'p_neg_year': p_neg_year,
        'kelly':      kelly,
        'q_kelly':    q_kelly,
        'eq_full':    eq_full,
    }


def year_end_fan(eq_full, exit_years_arr, year_range):
    """
    Portfolio value at end of each calendar year across all simulations.
    For a year with no trades, carry forward the last known equity value.
    """
    out = {}
    for yr in year_range:
        before = np.where(exit_years_arr <= yr)[0]
        if len(before) == 0:
            yr_eq = np.ones(eq_full.shape[0])
        else:
            yr_eq = eq_full[:, before[-1] + 1]   # +1: eq_full has leading 1.0
        out[yr] = {
            'p5':  np.percentile(yr_eq, 5),
            'p50': np.percentile(yr_eq, 50),
            'p95': np.percentile(yr_eq, 95),
        }
    return out

# ── CSV accumulator ───────────────────────────────────────────────────────────

csv_lines = [
    'BTC SMA Stage C — Monte Carlo: Return Magnitude Scaling (Option A)',
    f'Generated: {pd.Timestamp.now().date()}',
    'Candidates: SMA110/T30% (primary), SMA125/T30% (secondary), SMA110/T20% (alt)',
    'Methodology: winners scaled by magnitude factor; losers unchanged',
    '',
    'SECTION: CANDIDATE SUMMARY',
    'candidate,win_rate_pct,avg_win_pct,avg_loss_pct,n_trades',
]

results_lines = [
    '',
    'SECTION: MAGNITUDE SCALING RESULTS',
    'candidate,scale_pct,median_ann_pct,p10_ann_pct,p90_ann_pct,'
    'p_neg_year_pct,kelly_pct,q_kelly_pct,breakeven',
]

fan_lines = [
    '',
    'SECTION: EQUITY FAN (SMA110/T30% primary candidate at 100% magnitude scale)',
    'year,p5,p50,p95',
]

# ── MAIN LOOP ─────────────────────────────────────────────────────────────────

primary_fan_printed = False

for c_idx, cand in enumerate(CANDIDATES):
    sma_n = cand['sma']; trail = cand['trail']
    label = cand['label']; role  = cand['role']

    sma_vals = pd.Series(closes).rolling(sma_n).mean().values
    tr = run_pct_trail(closes, lows, sma_vals, dates, trail)

    net_rets     = tr['return'].values - COSTS
    exit_yrs_arr = pd.to_datetime(tr['exit_date']).dt.year.values
    n_trades     = len(tr)
    wr           = (net_rets > 0).mean()
    avg_win      = net_rets[net_rets > 0].mean()
    avg_loss     = net_rets[net_rets <= 0].mean()

    # CSV candidate summary
    csv_lines.append(
        f'{label},{wr*100:.0f},{avg_win*100:.1f},{avg_loss*100:.1f},{n_trades}'
    )

    # ── Print candidate header ────────────────────────────────────────────────
    print()
    print('=' * 72)
    print(f'CANDIDATE: {label}')
    print(f'Backtest win rate: {wr*100:.0f}%')
    print(f'Backtest avg win: +{avg_win*100:.1f}%')
    print(f'Backtest avg loss: {avg_loss*100:.1f}%')
    print(f'N trades: {n_trades}')
    print()

    # Table header
    col_w = [22, 24, 22, 22, 22, 30, 22]
    headers = ['Win magnitude scale', 'Median annual return %',
               'P10 annual return %', 'P90 annual return %',
               'P(negative year) %', 'Quarter-Kelly position size %',
               'Break-even magnitude?']
    print('  ' + ' | '.join(h.ljust(w) for h, w in zip(headers, col_w)))
    print('  ' + '-' * (sum(col_w) + 3 * (len(col_w) - 1)))

    scenario_results = []
    first_neg_scale  = None

    for scale in MAGNITUDE_SCALES:
        res = run_magnitude_mc(net_rets, exit_yrs_arr, scale, seed_extra=c_idx * 100)
        breakeven = 'Yes' if res['median_ann'] > 0 else 'No'
        if res['median_ann'] <= 0 and first_neg_scale is None:
            first_neg_scale = scale

        scale_label    = f"{int(scale*100)}%"
        median_s       = f"+{res['median_ann']*100:.1f}%" if res['median_ann'] >= 0 \
                         else f"{res['median_ann']*100:.1f}%"
        p10_s          = f"+{res['p10_ann']*100:.1f}%" if res['p10_ann'] >= 0 \
                         else f"{res['p10_ann']*100:.1f}%"
        p90_s          = f"+{res['p90_ann']*100:.1f}%"
        p_neg_s        = f"{res['p_neg_year']*100:.1f}%"
        qk_s           = f"{res['q_kelly']*100:.1f}%"

        row = [scale_label, median_s, p10_s, p90_s, p_neg_s, qk_s, breakeven]
        print('  ' + ' | '.join(v.ljust(w) for v, w in zip(row, col_w)))

        scenario_results.append(res)

        # CSV results row
        results_lines.append(
            f"{label},{int(scale*100)},{res['median_ann']*100:.1f},"
            f"{res['p10_ann']*100:.1f},{res['p90_ann']*100:.1f},"
            f"{res['p_neg_year']*100:.1f},{res['kelly']*100:.1f},"
            f"{res['q_kelly']*100:.1f},{breakeven}"
        )

        # Equity fan for primary candidate at 100% scale
        if label == 'SMA110/T30%' and scale == 1.0 and not primary_fan_printed:
            fan_data = year_end_fan(res['eq_full'], exit_yrs_arr, FAN_YEAR_RANGE)
            primary_fan_printed = True

    # Break-even answer
    print()
    if first_neg_scale is None:
        print(f'  At what win magnitude does median annual return first turn negative?')
        print(f'  -> Not reached within 20% magnitude scale.')
    else:
        print(f'  At what win magnitude does median annual return first turn negative?')
        print(f'  -> {int(first_neg_scale*100)}% magnitude scale.')

# ── Equity fan output ─────────────────────────────────────────────────────────

print()
print('=' * 72)
print('EQUITY FAN DATA — SMA110/T30% at 100% win magnitude (backtest)')
print('Portfolio value relative to start=1.0 at end of each calendar year')
print('2,000 simulations, returns resampled at backtest win rate and magnitude')
print()
print(f'  {"Year":<8} {"P5":>10} {"Median (P50)":>14} {"P95":>10}')
print('  ' + '-' * 46)

for yr in FAN_YEAR_RANGE:
    d = fan_data[yr]
    note = ' (partial)' if yr == 2026 else ''
    print(f'  {yr:<8} {d["p5"]:>10.3f} {d["p50"]:>14.3f} {d["p95"]:>10.3f}{note}')
    fan_lines.append(f'{yr},{d["p5"]:.3f},{d["p50"]:.3f},{d["p95"]:.3f}')

# ── Save CSV ──────────────────────────────────────────────────────────────────

all_lines = csv_lines + results_lines + fan_lines
with open(OUT_CSV, 'w') as f:
    f.write('\n'.join(all_lines) + '\n')

print()
print('=' * 72)
print(f'Results saved → {OUT_CSV}')
print('Stage C complete.')
