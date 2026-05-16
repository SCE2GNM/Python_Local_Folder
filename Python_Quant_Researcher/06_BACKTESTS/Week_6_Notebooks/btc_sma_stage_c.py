#!/usr/bin/env python3
"""
BTC SMA Stage C — Monte Carlo Stress Test
Candidates: SMA110/T30% (primary), SMA125/T30% (secondary), SMA110/T20% (alt)
10,000 simulations | 5 win rate scenarios | Quarter-Kelly sizing
Actual trade return distribution used — no normality assumption.
"""

import os, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf

warnings.filterwarnings('ignore')

COSTS     = 0.0015
N_SIM     = 10_000
N_FAN     = 2_000    # simulations for fan chart (2k is sufficient for smooth P5/P95)

WIN_RATE_SCENARIOS = ['backtest', 0.80, 0.75, 0.70, 0.65]

CANDIDATES = [
    {'sma': 110, 'trail': 0.30, 'label': 'SMA110/T30%', 'role': 'Primary'},
    {'sma': 125, 'trail': 0.30, 'label': 'SMA125/T30%', 'role': 'Secondary'},
    {'sma': 110, 'trail': 0.20, 'label': 'SMA110/T20%', 'role': 'Trade-frequency alt'},
]

OUT_DIR = '/Users/Greg/Documents/Python_Local_Folder/Python_Quant_Researcher/Week_7_Notebooks/results'
os.makedirs(OUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 78)
print("BTC SMA STAGE C — MONTE CARLO STRESS TEST")
print("=" * 78)
print("\nFetching BTC-USD 2018-start ...")

raw = yf.download('BTC-USD', start='2018-01-01', progress=False, auto_adjust=True)
raw.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in raw.columns]
closes = raw['close'].values.astype(float)
lows   = raw['low'].values.astype(float)
dates  = [pd.Timestamp(d) for d in raw.index]
years  = (dates[-1] - dates[0]).days / 365.25

print(f"  {dates[0].date()} → {dates[-1].date()}  ({years:.2f} yrs)\n")

# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST — PCT TRAIL
# ─────────────────────────────────────────────────────────────────────────────

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
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                               'exit_date': dates[i], 'exit_price': stop,
                               'return': (stop - ep) / ep})
                pos = 0; ep = peak = stop = 0.0; entry_date = None
            elif cl < sm:
                trades.append({'entry_date': entry_date, 'entry_price': ep,
                               'exit_date': dates[i], 'exit_price': cl,
                               'return': (cl - ep) / ep})
                pos = 0; ep = peak = stop = 0.0; entry_date = None
        elif cl > sm:
            ep = cl; peak = cl; stop = cl * (1 - trail_pct)
            pos = 1; entry_date = dates[i]
    return pd.DataFrame(trades)

# ─────────────────────────────────────────────────────────────────────────────
# MONTE CARLO CORE
# ─────────────────────────────────────────────────────────────────────────────

def run_mc(net_rets, yr_map, win_rate_target, n_trades, n_sim, seed_offset=0):
    """
    Resample N trades at a target win rate from the actual winner/loser pools.
    Returns dict of metrics, or (n_sim, n_trades+1) equity array if fan=True.

    Kelly formula: f* = p / |avg_loss| - (1-p) / avg_win
    Derivation: binary Kelly maximising E[log(1+fR)] with binary payoff.
    """
    winners = net_rets[net_rets > 0]
    losers  = net_rets[net_rets <= 0]
    if len(winners) == 0 or len(losers) == 0:
        return None

    rng = np.random.default_rng(42 + seed_offset)
    wr  = win_rate_target

    # Vectorised resample: (n_sim, n_trades)
    is_win = rng.random((n_sim, n_trades)) < wr
    w_idx  = rng.integers(0, len(winners), (n_sim, n_trades))
    l_idx  = rng.integers(0, len(losers),  (n_sim, n_trades))
    sim_rets = np.where(is_win, winners[w_idx], losers[l_idx])

    # Equity paths (n_sim, n_trades+1)
    eq_paths = np.cumprod(1 + sim_rets, axis=1)
    eq_full  = np.hstack([np.ones((n_sim, 1)), eq_paths])

    # Annual returns
    ann_rets = eq_paths[:, -1] ** (1.0 / years) - 1

    # P(negative year) — computed across all calendar year × simulation pairs
    neg_yr = 0; total_yr = 0
    for indices in yr_map.values():
        if len(indices) == 0:
            continue
        yr_compound = np.prod(1 + sim_rets[:, indices], axis=1)
        neg_yr   += (yr_compound < 1.0).sum()
        total_yr += n_sim
    p_neg_year = neg_yr / total_yr if total_yr > 0 else np.nan

    # Kelly fraction
    avg_win = winners.mean()
    avg_los = abs(losers.mean())
    kelly   = max(wr / avg_los - (1.0 - wr) / avg_win, 0.0)
    q_kelly = kelly / 4.0

    return {
        'median_ann': np.median(ann_rets),
        'p10_ann':    np.percentile(ann_rets, 10),
        'p_neg_year': p_neg_year,
        'kelly':      kelly,
        'q_kelly':    q_kelly,
        'eq_full':    eq_full,   # kept for fan chart
    }

# ─────────────────────────────────────────────────────────────────────────────
# CHART — EQUITY FAN
# ─────────────────────────────────────────────────────────────────────────────

def make_fan_chart(candidates_data, out_path):
    """
    candidates_data: list of dicts:
      {label, role, trade_dates (list of Timestamps), actual_eq (array),
       fan_eq (n_fan x n_trades+1 array), backtest_wr}
    """
    fig, axes = plt.subplots(3, 1, figsize=(13, 16), constrained_layout=True)
    fig.suptitle(
        'BTC SMA Stage C — Monte Carlo Equity Fan\n'
        '(Backtest win rate | Returns resampled from actual winner/loser pools | '
        '2,000 simulations)',
        fontsize=11, fontweight='bold'
    )

    for ax, cd in zip(axes, candidates_data):
        fan    = cd['fan_eq']            # (N_FAN, n_trades+1)
        actual = cd['actual_eq']         # (n_trades+1,)
        xdates = cd['trade_dates']       # list of Timestamps

        x = [d.to_pydatetime() for d in xdates]

        p5  = np.percentile(fan, 5,  axis=0)
        p50 = np.percentile(fan, 50, axis=0)
        p95 = np.percentile(fan, 95, axis=0)

        ax.fill_between(x, p5, p95, alpha=0.18, color='steelblue',
                        label='P5–P95 simulation range')
        ax.plot(x, p50,    color='steelblue',   linewidth=1.8, label='P50 (median sim)')
        ax.plot(x, actual, color='limegreen',    linewidth=2.2,
                linestyle='--', label='Actual backtest equity')
        ax.axhline(1.0, color='tomato', linewidth=0.8, linestyle=':', alpha=0.7)

        ax.set_yscale('log')
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax.set_ylabel('Portfolio value (log scale, start = 1.0)')
        ax.set_title(
            f"{cd['label']} — {cd['role']}  |  "
            f"Backtest win rate: {cd['backtest_wr']*100:.0f}%  |  "
            f"{len(actual)-1} trades",
            fontsize=10
        )
        ax.legend(fontsize=8, loc='upper left')
        ax.grid(True, alpha=0.25)
        ax.set_xlim(x[0], x[-1])

    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────────────

all_fan_data = []

for cand in CANDIDATES:
    sma_n = cand['sma']; trail = cand['trail']
    label = cand['label']; role  = cand['role']

    # Backtest
    sma_vals = pd.Series(closes).rolling(sma_n).mean().values
    tr = run_pct_trail(closes, lows, sma_vals, dates, trail)
    if len(tr) < 5:
        print(f"  {label}: insufficient trades — skipped\n")
        continue

    net_rets   = tr['return'].values - COSTS
    actual_wr  = (net_rets > 0).mean()
    n_trades   = len(tr)
    avg_win    = net_rets[net_rets > 0].mean()
    avg_loss   = net_rets[net_rets <= 0].mean()
    avg_loss_abs = abs(avg_loss)

    # Calendar-year → 0-based trade index map
    exit_yrs = pd.to_datetime(tr['exit_date']).dt.year.values
    yr_map   = {}
    for yr in np.unique(exit_yrs):
        yr_map[yr] = list(np.where(exit_yrs == yr)[0])

    # Actual trade-level equity and plot dates
    actual_eq_trd  = np.concatenate([[1.0], np.cumprod(1 + net_rets)])
    trade_dates    = ([pd.Timestamp(tr['entry_date'].iloc[0])] +
                      [pd.Timestamp(d) for d in tr['exit_date'].values])

    # ── print header ─────────────────────────────────────────────────────────
    print()
    print(f"  {'═' * 72}")
    print(f"  CANDIDATE: {label}  —  {role}")
    print(f"  {'═' * 72}")
    print(f"  Backtest: N={n_trades} trades | Win rate {actual_wr*100:.0f}% | "
          f"Avg win {avg_win*100:+.1f}% | Avg loss {avg_loss*100:+.1f}%")
    print(f"  Unique winner pool: {(net_rets > 0).sum()} trades | "
          f"Unique loser pool: {(net_rets <= 0).sum()} trades")
    print()
    print(f"  {'Win Rate':<16} {'Med Ann%':>9} {'P10 Ann%':>9} "
          f"{'P(neg yr)':>10} {'Kelly%':>8} {'★ QKelly%':>10}")
    print(f"  {'─' * 66}")

    best_scen_mc = None  # store backtest-rate MC for fan chart

    for s_idx, scen in enumerate(WIN_RATE_SCENARIOS):
        wr = actual_wr if scen == 'backtest' else float(scen)

        res = run_mc(net_rets, yr_map, wr, n_trades,
                     n_sim=N_SIM, seed_offset=s_idx * 17)
        if res is None:
            continue

        if scen == 'backtest':
            best_scen_mc = res

        wr_label = f"Backtest ({actual_wr*100:.0f}%)" if scen == 'backtest' \
                   else f"{int(wr * 100)}%"

        kelly_str  = f"{res['kelly']*100:>7.1f}%" if res['kelly'] > 0 else "  neg edge"
        qkelly_str = f"{res['q_kelly']*100:>8.1f}%" if res['q_kelly'] > 0 else " neg edge"

        print(f"  {wr_label:<16} "
              f"{res['median_ann']*100:>+8.1f}%  "
              f"{res['p10_ann']*100:>+8.1f}%  "
              f"{res['p_neg_year']*100:>9.1f}%  "
              f"{kelly_str}  {qkelly_str}")

    # ── fan chart data (at backtest win rate, N_FAN sims) ────────────────────
    fan_res = run_mc(net_rets, yr_map, actual_wr, n_trades,
                     n_sim=N_FAN, seed_offset=999)
    if fan_res is not None:
        all_fan_data.append({
            'label':       label,
            'role':        role,
            'trade_dates': trade_dates,
            'actual_eq':   actual_eq_trd,
            'fan_eq':      fan_res['eq_full'],
            'backtest_wr': actual_wr,
        })

# ─────────────────────────────────────────────────────────────────────────────
# NOTES
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 78)
print("SIZING NOTE — QUARTER-KELLY (★ QKelly%)")
print("=" * 78)
print("  Kelly fraction = p/|avg_loss| − (1−p)/avg_win")
print("  Represents the optimal capital fraction per trade (binary Kelly).")
print()
print("  Quarter-Kelly (★) is recommended per Methodology Standards because:")
print("  BTC SMA is a momentum strategy not yet confirmed through a full bear")
print("  cycle with integrated stop-loss in live conditions. Kelly fractions")
print("  assume stationary return distributions; fat tails and regime shifts")
print("  create ruin risk at full Kelly. Quarter-Kelly provides a 4× safety margin.")
print()
print("  Interpretation: if QKelly% = 25%, allocate 25% of BTC capital per")
print("  trade signal (or equivalently, cap total strategy allocation at 25%")
print("  of available capital and deploy fully on each signal).")
print("=" * 78)

# ─────────────────────────────────────────────────────────────────────────────
# GENERATE AND SAVE FAN CHART
# ─────────────────────────────────────────────────────────────────────────────

fan_path = os.path.join(OUT_DIR, 'btc_sma_stage_c_fan.png')
if all_fan_data:
    print("\nGenerating equity fan chart ...")
    make_fan_chart(all_fan_data, fan_path)
    print(f"Fan chart saved → {fan_path}")

print()
print("=" * 78)
print("STAGE C COMPLETE — Review results before Stage D")
print("=" * 78)
