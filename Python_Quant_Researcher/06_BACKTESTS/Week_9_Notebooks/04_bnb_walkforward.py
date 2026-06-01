"""
04_bnb_walkforward.py — BNB Donchian Walk-Forward Validation
Week 9 | 2026-06-01

Combinations:
  Donchian per=60 stop=5%  (post-break PF 2.659 — VIABLE)
  Donchian per=20 stop=5%  (post-break PF 2.199 — VIABLE)

Method: Expanding IS window, 6-month OOS windows, step 6 months.
  IS always starts at data start (expanding).
  IS minimum: 2 years. First OOS: 2020-01-01.
  OOS windows are sequential half-years until data ends.

Note (per LEARNING_LOG Week 6):
  With FIXED parameters, expanding and rolling IS windows produce identical OOS
  results — the IS window definition only matters when parameters are re-optimised
  per window. Parameters here are fixed from the discovery grid. The expanding
  structure is preserved for curriculum documentation consistency.
  Validation value: are OOS windows consistently profitable across different
  market regimes (2020 bull, 2022 bear, 2024-26 post-ETF)?
"""

import importlib.util
import os
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

BASE   = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE, "bnb_walkforward_results.csv")

spec = importlib.util.spec_from_file_location(
    "altcoin_grid", os.path.join(BASE, "01_altcoin_discovery_grid.py")
)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

TICKER       = "BNB-USD"
IS_MIN_YEARS = 2
OOS_MONTHS   = 6
COSTS        = g.COSTS


# ══════════════════════════════════════════════════════════════════════════════
# DONCHIAN SINGLE-COMBO RUNNER  (same logic as 03_regime_break_analysis.py)
# ══════════════════════════════════════════════════════════════════════════════

def run_donchian_single(df, period, stop_pct):
    closes    = df["close"].values
    highs     = df["high"].values
    lows      = df["low"].values
    N         = len(df)
    h_ser     = pd.Series(highs)
    l_ser     = pd.Series(lows)
    entry_max = h_ser.shift(1).rolling(period).max().values
    exit_min  = l_ser.shift(1).rolling(period).min().values

    trades = []
    in_pos = False
    ei = epx = peak = 0

    for i in range(1, N):
        if np.isnan(entry_max[i]) or np.isnan(exit_min[i]):
            continue
        if not in_pos:
            if closes[i] > entry_max[i]:
                in_pos = True
                ei, epx, peak = i, closes[i], closes[i]
        else:
            stop_lvl = peak * (1 - stop_pct)
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

    return trades, g.build_equity(trades, closes, N)


# ══════════════════════════════════════════════════════════════════════════════
# OOS WINDOW METRICS
# ══════════════════════════════════════════════════════════════════════════════

def oos_window_metrics(trades, eq, df, oos_start_ts, oos_end_ts, window_num):
    """
    Compute OOS metrics for a single window [oos_start_ts, oos_end_ts).

    Annual return: equity curve slice between OOS start and last bar before end.
    Sortino: daily equity curve slice, annualised downside std.
    PF / WR: trades whose EXIT date falls within [oos_start_ts, oos_end_ts).
    """
    dates = df.index
    N     = len(df)

    # Index of first bar on or after OOS start
    oos_si = int(dates.searchsorted(oos_start_ts, side="left"))
    # Index of last bar BEFORE OOS end (exclusive end)
    oos_ei = int(dates.searchsorted(oos_end_ts, side="left")) - 1
    oos_ei = min(oos_ei, N - 1)

    if oos_si >= oos_ei or oos_si >= N:
        return None

    oos_days = max((dates[oos_ei] - dates[oos_si]).days, 1)
    is_partial = (oos_end_ts > dates[-1] + pd.Timedelta(days=1))

    # ── Annual return from equity curve ───────────────────────────────────────
    ann_ret = float((eq[oos_ei] / eq[oos_si]) ** (365.25 / oos_days) - 1)

    # ── Sortino from daily equity curve slice ─────────────────────────────────
    eq_slice = eq[oos_si: oos_ei + 1]
    daily_r  = np.diff(eq_slice) / eq_slice[:-1]
    neg      = daily_r[daily_r < 0]
    down_std = float(np.std(neg) * np.sqrt(365.25)) if len(neg) > 1 else np.nan
    sortino  = float(ann_ret / down_std) if (down_std and down_std > 0) else np.nan

    # ── PF / WR from trades exiting in OOS window ─────────────────────────────
    oos_trades = [t for t in trades
                  if oos_start_ts <= dates[t["xi"]] < oos_end_ts]

    if not oos_trades:
        pf, wr, n_trades = np.nan, np.nan, 0
    else:
        wins   = [t["ret"] for t in oos_trades if t["ret"] > 0]
        losses = [abs(t["ret"]) for t in oos_trades if t["ret"] <= 0]
        pf     = float(sum(wins) / sum(losses)) if losses else float("inf")
        wr     = float(len(wins) / len(oos_trades))
        n_trades = len(oos_trades)

    return dict(
        window     = window_num,
        is_end     = str((oos_start_ts - pd.Timedelta(days=1)).date()),
        oos_start  = str(dates[oos_si].date()),
        oos_end    = str(dates[oos_ei].date()),
        oos_days   = oos_days,
        partial    = is_partial,
        n_trades   = n_trades,
        pf         = pf,
        wr         = wr,
        ann_ret    = ann_ret,
        sortino    = sortino,
    )


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def fmt_pf(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):  return "  —"
    if np.isinf(v):                                           return "  ∞"
    return f"{v:.3f}"

def fmt_wr(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):  return "   —"
    return f"{v:.1%}"

def fmt_ann(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):  return "    —"
    return f"{v:+.1%}"

def fmt_so(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):  return "   —"
    return f"{v:.2f}"

def print_windows(windows, combo_label):
    SEP = "=" * 88
    print(f"\n{SEP}")
    print(f"  {combo_label}")
    print(SEP)

    hdr = (f"  {'W':<3}  {'IS end':<12}  {'OOS window':<25}  "
           f"{'Trades':>6}  {'PF':>6}  {'WR':>6}  {'AnnRet':>7}  {'Sortino':>7}  {'Status'}")
    print(hdr)
    print(f"  {'-'*85}")

    for w in windows:
        if w is None:
            continue
        oos_range = f"{w['oos_start']} → {w['oos_end']}"
        if w["partial"]:
            oos_range += " *"

        if w["n_trades"] == 0:
            status = "NO TRADES"
        elif np.isnan(w["pf"]):
            status = "NO LOSSES"
        elif w["pf"] >= 1.0:
            status = "PROFITABLE"
        else:
            status = "LOSS"

        print(f"  {w['window']:<3}  {w['is_end']:<12}  {oos_range:<25}  "
              f"{w['n_trades']:>6}  {fmt_pf(w['pf']):>6}  {fmt_wr(w['wr']):>6}  "
              f"{fmt_ann(w['ann_ret']):>7}  {fmt_so(w['sortino']):>7}  {status}")

    print(f"  * partial window (data ends before OOS period completes)")


def print_summary(windows, combo_label, bh_ann):
    with_trades = [w for w in windows if w and w["n_trades"] > 0]
    no_trades   = [w for w in windows if w and w["n_trades"] == 0]
    profitable  = [w for w in with_trades if not np.isnan(w["pf"]) and w["pf"] >= 1.0]
    pfs         = [w["pf"] for w in with_trades if not np.isnan(w["pf"]) and not np.isinf(w["pf"])]
    anns        = [w["ann_ret"] for w in windows if w and not np.isnan(w["ann_ret"])]

    SEP = "-" * 70
    print(f"\n  OOS CONSISTENCY SUMMARY — {combo_label}")
    print(f"  {SEP}")
    print(f"    Total OOS windows      : {len([w for w in windows if w])}")
    print(f"    Windows with trades    : {len(with_trades)}")
    print(f"    Windows without trades : {len(no_trades)}")
    print(f"    Profitable (PF ≥ 1.0)  : {len(profitable)} / {len(with_trades)}")
    if pfs:
        print(f"    OOS PF range           : {min(pfs):.3f} – {max(pfs):.3f}  "
              f"(median {float(np.median(pfs)):.3f})")
    if anns:
        print(f"    OOS Ann Ret range      : {min(anns):+.1%} – {max(anns):+.1%}  "
              f"(mean {float(np.mean(anns)):+.1%})")
    print(f"    B&H annual return      : {bh_ann:+.1%}  (reference)")

    n_win = len(with_trades)
    if n_win == 0:
        verdict = "NO DATA"
    elif len(profitable) / n_win >= 0.75:
        verdict = "CONSISTENT — majority of windows profitable"
    elif len(profitable) / n_win >= 0.50:
        verdict = "MIXED — roughly half of windows profitable"
    else:
        verdict = "INCONSISTENT — fewer than half of windows profitable"

    print(f"    Verdict                : {verdict}")
    print(f"  {SEP}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    SEP = "═" * 88

    print(SEP)
    print("BNB DONCHIAN WALK-FORWARD VALIDATION")
    print(f"Method  : Expanding IS (min {IS_MIN_YEARS}yr), {OOS_MONTHS}-month OOS, step {OOS_MONTHS} months")
    print(f"Combos  : Donchian per=60/stop=5%  |  Donchian per=20/stop=5%")
    print(f"Note    : Fixed parameters — IS window defines sample context only.")
    print(f"          OOS results are independent of IS window size with fixed params.")
    print(SEP)

    print(f"\nFetching {TICKER}...")
    df   = g.fetch_asset(TICKER)
    bh   = g.bh_benchmark(df["close"].values, (df.index[-1] - df.index[0]).days)
    bh_ann = bh["annual_ret"]
    print(f"  {len(df)} candles | {df.index[0].date()} → {df.index[-1].date()}")
    print(f"  B&H: {bh_ann:+.1%} annual | Sortino {bh['sortino']:.2f}\n")

    # ── Generate OOS window timestamps ────────────────────────────────────────
    data_start = df.index[0]
    data_end   = df.index[-1]
    first_oos  = data_start + relativedelta(years=IS_MIN_YEARS)

    oos_starts = []
    ts = first_oos
    while ts < data_end:
        oos_starts.append(ts)
        ts = ts + relativedelta(months=OOS_MONTHS)

    print(f"  {len(oos_starts)} OOS windows generated "
          f"({first_oos.date()} → {data_end.date()})")

    # ── Run both combinations ─────────────────────────────────────────────────
    combinations = [
        {"label": "BNB Donchian per=60 stop=5%", "period": 60, "stop_pct": 0.05},
        {"label": "BNB Donchian per=20 stop=5%", "period": 20, "stop_pct": 0.05},
    ]

    all_rows = []

    for combo in combinations:
        print(f"\nRunning {combo['label']}...")
        trades, eq = run_donchian_single(df, combo["period"], combo["stop_pct"])
        n_days = (df.index[-1] - df.index[0]).days
        m_full = g.calc_metrics(trades, eq, n_days)
        if m_full:
            print(f"  Full-period: {m_full['annual_ret']:+.1%} ann | "
                  f"PF {m_full['pf']:.3f} | "
                  f"Sortino {m_full['sortino']:.2f} | "
                  f"{m_full['n_trades']} trades")

        windows = []
        for w_num, oos_st in enumerate(oos_starts, 1):
            oos_en = oos_st + relativedelta(months=OOS_MONTHS)
            w = oos_window_metrics(trades, eq, df, oos_st, oos_en, w_num)
            windows.append(w)

        print_windows(windows, combo["label"])
        print_summary(windows, combo["label"], bh_ann)

        # Collect rows for CSV
        for w in windows:
            if w:
                row = {
                    "asset":    TICKER,
                    "strategy": "Donchian",
                    "params":   combo["label"].split("BNB Donchian ")[1],
                    **w,
                }
                all_rows.append(row)

    # ── Save CSV ──────────────────────────────────────────────────────────────
    df_out = pd.DataFrame(all_rows)
    df_out.to_csv(OUTPUT, index=False)
    print(f"\n\nSaved → {OUTPUT}")
    print(SEP)
    print("Walk-forward complete. Await instruction before proceeding.")
    print(SEP)


if __name__ == "__main__":
    main()
