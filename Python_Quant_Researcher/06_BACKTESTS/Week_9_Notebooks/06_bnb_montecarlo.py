"""
06_bnb_montecarlo.py — Phase 3 Monte Carlo Stress Test
Week 9 | 2026-06-01

Strategy: BNB Donchian period=20, stop=5%, SMA-120 regime filter
(post-break PF 2.961, MtM MDD -29.7%, 74 trades — MANDATORY Monte Carlo: n < 100)

Method: Bootstrap resampling, 1,000 simulations per win-rate scenario.

Win rate adjustment:
  At the backtest win rate, resample all trades with replacement (pure bootstrap).
  At lower win rate scenarios, sample wins and losses SEPARATELY in the required
  proportion, then shuffle. This preserves the actual win/loss size distributions
  while changing only the win/loss frequency.

Trade returns: net of 0.15% round-trip costs (applied before simulation).
  Raw trade ret values from backtest do not include costs; build_equity applies
  them at exit. We apply them here so simulated annual returns match the
  equity-curve methodology.

Annual return annualisation: compound(sim_returns) ^ (365.25/n_calendar_days) - 1
  Uses the actual backtest calendar span (n_days) as the annualisation base.
  Note: this slightly overstates annual return vs daily-equity-curve method
  because it does not model idle cash periods. It is the standard Monte Carlo
  methodology and is appropriate for comparing scenarios. All scenarios use
  the same n_days denominator, so relative comparisons are valid.

Kelly formula: f* = p - (1-p)/b  where b = avg_win / |avg_loss|
  b is calculated from ACTUAL backtest trade returns (same for all scenarios).
  Only p (win rate) changes across scenarios.
  Half-Kelly position sizing: position = (f*/2 × capital) / stop_pct

Capital: $150 (initial deployment capital for validation phase).
Stop:    5% (fixed stop from entry price).

Flags:
  ★ Kelly < 0  → NEGATIVE EXPECTANCY — DO NOT DEPLOY at this win rate
  ★ P(neg yr) > 30% → HIGH NEGATIVE YEAR RISK — flag for explicit acceptance
"""

import importlib.util
import os
import warnings
import numpy as np
import pandas as pd
from ta.volatility import AverageTrueRange

warnings.filterwarnings("ignore")
np.random.seed(42)

BASE   = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE, "bnb_montecarlo_results.csv")

spec = importlib.util.spec_from_file_location(
    "altcoin_grid", os.path.join(BASE, "01_altcoin_discovery_grid.py")
)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

TICKER     = "BNB-USD"
PERIOD     = 20
STOP_PCT   = 0.05
SMA_PERIOD = 120
COSTS      = g.COSTS          # 0.0015 (0.15% round-trip)
CAPITAL    = 150.0
N_SIMS     = 1000
BREAK_TS   = pd.Timestamp("2024-01-01")


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY RUNNER  (replicates Analysis 4 SMA-120 result)
# ══════════════════════════════════════════════════════════════════════════════

def run_strategy(df):
    """
    BNB Donchian period=20, stop=5%, SMA-120 filter, Exit A.
    Returns (trades, eq, n_days) where trades carry raw (pre-cost) returns.
    """
    closes    = df["close"].values
    highs     = df["high"].values
    lows      = df["low"].values
    N         = len(df)
    n_days    = (df.index[-1] - df.index[0]).days

    h_ser     = pd.Series(highs)
    l_ser     = pd.Series(lows)
    entry_max = h_ser.shift(1).rolling(PERIOD).max().values
    exit_min  = l_ser.shift(1).rolling(PERIOD).min().values
    sma_vals  = pd.Series(closes).rolling(SMA_PERIOD).mean().values

    trades = []
    in_pos = False
    ei = epx = peak = 0

    for i in range(1, N):
        if np.isnan(entry_max[i]) or np.isnan(exit_min[i]) or np.isnan(sma_vals[i]):
            continue
        if not in_pos:
            if closes[i] > entry_max[i] and closes[i] > sma_vals[i]:
                in_pos = True
                ei, epx, peak = i, closes[i], closes[i]
        else:
            stop_lvl = peak * (1 - STOP_PCT)
            if lows[i] <= stop_lvl:
                trades.append({"ei": ei, "xi": i, "ret": (stop_lvl - epx) / epx})
                in_pos = False
            elif lows[i] <= exit_min[i]:
                trades.append({"ei": ei, "xi": i, "ret": (exit_min[i] - epx) / epx})
                in_pos = False
            else:
                if closes[i] > peak:
                    peak = closes[i]

    if in_pos:
        trades.append({"ei": ei, "xi": N - 1, "ret": (closes[-1] - epx) / epx})

    eq = g.build_equity(trades, closes, N)
    return trades, eq, n_days


# ══════════════════════════════════════════════════════════════════════════════
# KELLY FRACTION
# ══════════════════════════════════════════════════════════════════════════════

def kelly_fraction(p, b):
    """f* = p - (1-p)/b.  Returns negative value if no positive expectancy."""
    if b <= 0:
        return -1.0
    return p - (1 - p) / b


# ══════════════════════════════════════════════════════════════════════════════
# MONTE CARLO ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_monte_carlo(net_wins, net_losses, n_trades, n_days, avg_win_raw, avg_loss_raw,
                    p_target, b, n_sims=N_SIMS):
    """
    Bootstrap 1,000 simulations for a given win-rate scenario.

    net_wins / net_losses: actual trade returns after 0.15% cost.
    p_target:  target win rate for this scenario.
    b:         avg_win / avg_loss from RAW backtest returns (fixed across scenarios).
    """
    n_wins_target   = int(round(p_target * n_trades))
    n_losses_target = n_trades - n_wins_target

    # Edge case: if wins or losses pool is empty, scenario is not computable
    if n_wins_target > 0 and len(net_wins) == 0:
        return None
    if n_losses_target > 0 and len(net_losses) == 0:
        return None

    annual_rets = np.empty(n_sims)
    for k in range(n_sims):
        sim = np.empty(n_trades)
        if n_wins_target > 0:
            sim[:n_wins_target] = np.random.choice(net_wins, n_wins_target, replace=True)
        if n_losses_target > 0:
            sim[n_wins_target:] = np.random.choice(net_losses, n_losses_target, replace=True)
        np.random.shuffle(sim)
        compound = float(np.prod(1.0 + sim))
        annual_rets[k] = compound ** (365.25 / n_days) - 1.0

    f_star    = kelly_fraction(p_target, b)
    half_k    = f_star / 2.0
    pos_size  = (half_k * CAPITAL) / STOP_PCT if half_k > 0 else 0.0

    return dict(
        p_target     = p_target,
        median_ann   = float(np.median(annual_rets)),
        p10_ann      = float(np.percentile(annual_rets, 10)),
        p90_ann      = float(np.percentile(annual_rets, 90)),
        prob_neg     = float(np.mean(annual_rets < 0)),
        kelly        = f_star,
        half_kelly   = half_k,
        pos_size_usd = pos_size,
        avg_win_raw  = avg_win_raw,
        avg_loss_raw = avg_loss_raw,
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    SEP = "═" * 78

    print(SEP)
    print("PHASE 3 MONTE CARLO STRESS TEST")
    print("BNB Donchian period=20, stop=5%, SMA-120 filter")
    print(f"Simulations: {N_SIMS} per scenario  |  Capital: ${CAPITAL:.0f}  |  Stop: {STOP_PCT:.0%}")
    print(SEP)

    # ── Fetch data and run strategy ───────────────────────────────────────────
    print(f"\nFetching {TICKER} and running strategy...")
    df     = g.fetch_asset(TICKER)
    trades, eq, n_days = run_strategy(df)
    n_years = n_days / 365.25

    print(f"  {len(df)} candles | {df.index[0].date()} → {df.index[-1].date()}")
    print(f"  {len(trades)} trades over {n_years:.1f} years "
          f"({len(trades)/n_years:.1f} trades/year)")

    # ── Extract raw returns ───────────────────────────────────────────────────
    raw_rets = np.array([t["ret"] for t in trades])
    raw_wins  = raw_rets[raw_rets > 0]
    raw_losses = raw_rets[raw_rets <= 0]

    actual_wr  = float(len(raw_wins) / len(raw_rets))
    avg_win    = float(np.mean(raw_wins))   if len(raw_wins)   > 0 else 0.0
    avg_loss   = float(abs(np.mean(raw_losses))) if len(raw_losses) > 0 else 0.0
    b          = avg_win / avg_loss if avg_loss > 0 else 0.0

    print(f"\n  Backtest statistics:")
    print(f"    Trade count   : {len(raw_rets)}")
    print(f"    Win rate      : {actual_wr:.1%}  ({len(raw_wins)} wins, {len(raw_losses)} losses)")
    print(f"    Avg win       : {avg_win:+.2%}")
    print(f"    Avg loss      : {avg_loss:.2%}  (absolute)")
    print(f"    Win/loss ratio (b): {b:.3f}×")
    print(f"    Backtest Kelly f* : {kelly_fraction(actual_wr, b):.1%}")

    # ── Net-of-costs returns for simulation ───────────────────────────────────
    # Apply 0.15% cost to each trade return before simulation.
    # Raw rets are pre-cost (costs applied in build_equity, not per-trade).
    net_rets   = (1 + raw_rets) * (1 - COSTS) - 1
    net_wins   = net_rets[net_rets > 0]
    net_losses = net_rets[net_rets <= 0]

    n_trades   = len(raw_rets)

    # ── Run Monte Carlo at five scenarios ─────────────────────────────────────
    scenarios = [actual_wr, 0.80, 0.75, 0.70, 0.65]
    scenario_labels = [
        f"Backtest ({actual_wr:.1%})", "80%", "75%", "70%", "65%"
    ]

    results = []
    print(f"\nRunning {N_SIMS} simulations × {len(scenarios)} scenarios...")
    for p, label in zip(scenarios, scenario_labels):
        r = run_monte_carlo(net_wins, net_losses, n_trades, n_days,
                            avg_win, avg_loss, p, b)
        if r:
            r["scenario_label"] = label
            results.append(r)
            print(f"  {label:<20} done — median ann: {r['median_ann']:+.1%}, "
                  f"P(neg): {r['prob_neg']:.0%}, Kelly: {r['kelly']:.1%}")

    # ── Display results table ─────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("MONTE CARLO RESULTS — BNB Donchian period=20, stop=5%, SMA-120")
    print(f"b (win/loss ratio) = {b:.3f}×  |  avg win = {avg_win:+.2%}  "
          f"|  avg loss = {avg_loss:.2%}")
    print(SEP)

    hdr = (f"  {'Scenario':<22}  {'Median':>7}  {'P10':>7}  {'P90':>7}  "
           f"{'P(neg)':>7}  {'Kelly':>6}  {'½-Kelly':>7}  "
           f"{'PosSize':>8}  Flags")
    print(hdr)
    print(f"  {'-'*100}")

    flags_list = []
    for r in results:
        flags = []
        if r["kelly"] < 0:
            flags.append("★ NEGATIVE EXPECTANCY — DO NOT TRADE")
        if r["prob_neg"] > 0.30:
            flags.append("★ HIGH NEG-YEAR RISK (>30%)")

        kelly_str    = f"{r['kelly']:+.1%}"  if not np.isnan(r["kelly"]) else "  —"
        half_k_str   = f"{r['half_kelly']:+.1%}" if r["half_kelly"] > 0 else "  N/A"
        pos_str      = f"${r['pos_size_usd']:.0f}"  if r["pos_size_usd"] > 0 else "  $0"
        flag_str     = "  ".join(flags) if flags else ""

        print(f"  {r['scenario_label']:<22}  "
              f"{r['median_ann']:>+6.1%}  "
              f"{r['p10_ann']:>+6.1%}  "
              f"{r['p90_ann']:>+6.1%}  "
              f"{r['prob_neg']:>6.0%}  "
              f"{kelly_str:>6}  "
              f"{half_k_str:>7}  "
              f"{pos_str:>8}  {flag_str}")
        flags_list.append(flag_str)

    # ── Deployment recommendation ─────────────────────────────────────────────
    print(f"\n{SEP}")
    print("DEPLOYMENT SIZING RECOMMENDATION")
    print(SEP)

    # Find the lowest win rate scenario where Kelly is still positive
    viable = [r for r in results if r["kelly"] > 0]
    failed = [r for r in results if r["kelly"] <= 0]

    if not viable:
        print("  ★ ALL SCENARIOS SHOW NEGATIVE KELLY — strategy not deployable.")
    else:
        # Conservative sizing: use the lowest viable Kelly (most pessimistic)
        conservative_r = min(viable, key=lambda r: r["kelly"])
        print(f"  Conservative sizing (worst viable scenario: {conservative_r['scenario_label']}):")
        print(f"    Kelly f*   : {conservative_r['kelly']:+.1%}")
        print(f"    Half-Kelly : {conservative_r['half_kelly']:+.1%}")
        print(f"    Dollar risk: ${conservative_r['half_kelly'] * CAPITAL:.2f} "
              f"(= Half-Kelly × ${CAPITAL:.0f})")
        print(f"    Position   : ${conservative_r['pos_size_usd']:.0f} "
              f"(= dollar risk / {STOP_PCT:.0%} stop)")
        print(f"    → At ${CAPITAL:.0f} total capital, risk ${conservative_r['half_kelly']*CAPITAL:.2f} "
              f"per trade with a ${conservative_r['pos_size_usd']:.0f} position.")

        # Backtest sizing for reference
        bt_r = results[0]
        print(f"\n  Backtest scenario sizing ({bt_r['scenario_label']}):")
        print(f"    Kelly f*   : {bt_r['kelly']:+.1%}")
        print(f"    Half-Kelly : {bt_r['half_kelly']:+.1%}")
        print(f"    Position   : ${bt_r['pos_size_usd']:.0f}")

    if failed:
        print(f"\n  Scenarios where Kelly turns NEGATIVE (no positive expectancy):")
        for r in failed:
            print(f"    {r['scenario_label']:<22} Kelly {r['kelly']:+.1%} — "
                  f"★ DO NOT DEPLOY at this win rate")

    # ── Kelly breakeven win rate ───────────────────────────────────────────────
    # p_breakeven: solve p - (1-p)/b = 0 → p = 1/(1+b)
    p_breakeven = 1.0 / (1.0 + b) if b > 0 else 1.0
    print(f"\n  Kelly breakeven win rate: {p_breakeven:.1%} "
          f"(b={b:.3f}×, from f*=0 → p=1/(1+b))")
    print(f"  Backtest win rate: {actual_wr:.1%}  |  "
          f"Margin above breakeven: {actual_wr - p_breakeven:+.1%}")

    # ── Save CSV ──────────────────────────────────────────────────────────────
    df_out = pd.DataFrame(results)
    cols   = ["scenario_label", "p_target", "median_ann", "p10_ann", "p90_ann",
              "prob_neg", "kelly", "half_kelly", "pos_size_usd",
              "avg_win_raw", "avg_loss_raw"]
    df_out = df_out[[c for c in cols if c in df_out.columns]]
    df_out.to_csv(OUTPUT, index=False)
    print(f"\n  Saved → {OUTPUT}")

    print(f"\n{SEP}")
    print("Monte Carlo complete. Review results before any deployment documentation.")
    print(SEP)


if __name__ == "__main__":
    main()
