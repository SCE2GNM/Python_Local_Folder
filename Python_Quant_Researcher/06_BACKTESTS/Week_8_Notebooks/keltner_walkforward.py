"""
keltner_walkforward.py — Walk-forward analysis for top 3 Keltner candidates
Week 8 | 2026-05-19

Candidates : ema=22/mult=1.5, ema=22/mult=2.0, ema=19/mult=1.5
Windows    : 7 expanding + 7 rolling (fixed 2yr IS, 6-month step)
Methodology: fixed parameters throughout (no re-optimisation per window)
             0.15% costs, LOW-bar stop, daily MtM equity
"""

import os
import numpy as np
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv
from ta.volatility import AverageTrueRange

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
WEEK_DIR     = os.path.dirname(BASE_DIR)
PROJECT_ROOT = os.path.dirname(WEEK_DIR)
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

COSTS = 0.0015

CANDIDATES = [
    dict(ema_p=22, mult=1.5, label="ema=22 mult=1.5"),
    dict(ema_p=22, mult=2.0, label="ema=22 mult=2.0"),
    dict(ema_p=19, mult=1.5, label="ema=19 mult=1.5"),
]

# ── Data ────────────────────────────────────────────────────────────────────────
def fetch_sol():
    client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_SECRET_KEY"))
    raw = client.get_historical_klines(
        "SOLUSDT", Client.KLINE_INTERVAL_1DAY, "1 Jan, 2020"
    )
    cols = ["open_time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "taker_base", "taker_quote", "ignore"]
    df = pd.DataFrame(raw, columns=cols)
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    df["dt"] = pd.to_datetime(df["open_time"], unit="ms")
    return df.set_index("dt").sort_index()


# ── Indicators ───────────────────────────────────────────────────────────────────
def add_indicators(df, ema_p, mult):
    ema   = pd.Series(df["close"].values).ewm(span=ema_p, adjust=False).mean().values
    atr   = AverageTrueRange(df["high"], df["low"], df["close"],
                             window=ema_p).average_true_range().values
    upper = ema + mult * atr
    return ema, upper


# ── Single-period backtest ───────────────────────────────────────────────────────
def run_period(df_slice, ema_full, upper_full, full_index):
    """
    Run Keltner strategy on df_slice, using pre-computed indicators aligned
    to the full dataset index.
    Returns dict of metrics, or None if < 5 trades.
    """
    closes = df_slice["close"].values
    lows   = df_slice["low"].values
    N      = len(df_slice)
    if N < 30:
        return None

    # Map slice positions to full-dataset indicator arrays
    start_loc = full_index.get_loc(df_slice.index[0])

    trades = []
    in_pos = False
    ei = epx = 0

    for j in range(1, N):
        gi = start_loc + j   # global index into full indicator arrays
        if gi < 1 or np.isnan(upper_full[gi - 1]) or np.isnan(ema_full[gi - 1]):
            continue
        if not in_pos:
            if closes[j] > upper_full[gi - 1]:
                in_pos = True
                ei, epx = j, closes[j]
        else:
            if lows[j] <= ema_full[gi - 1]:
                trades.append(dict(ei=ei, xi=j, ret=(ema_full[gi - 1] - epx) / epx))
                in_pos = False
            elif closes[j] < ema_full[gi]:
                trades.append(dict(ei=ei, xi=j, ret=(closes[j] - epx) / epx))
                in_pos = False

    if in_pos:
        trades.append(dict(ei=ei, xi=N - 1, ret=(closes[-1] - epx) / epx))

    n_trades = len(trades)
    if n_trades < 1:
        return dict(annual_ret=np.nan, mdd=np.nan, trades=0, profitable=False)

    # Equity curve
    n_days = (df_slice.index[-1] - df_slice.index[0]).days
    if n_days < 30:
        return None

    eq = np.ones(N)
    for t in sorted(trades, key=lambda x: x["ei"]):
        ei_, xi_ = t["ei"], t["xi"]
        base = eq[ei_]
        for jj in range(ei_ + 1, xi_):
            eq[jj] = base * (closes[jj] / closes[ei_])
        eq[xi_] = base * (1 + t["ret"]) * (1 - COSTS)
        if xi_ + 1 < N:
            eq[xi_ + 1:] = eq[xi_]

    ann  = eq[-1] ** (365.25 / n_days) - 1
    rm   = np.maximum.accumulate(eq)
    mdd  = ((eq - rm) / rm).min()

    return dict(annual_ret=ann, mdd=mdd, trades=n_trades, profitable=(ann > 0))


# ── Window definitions ───────────────────────────────────────────────────────────
def make_windows(start, end):
    """
    Returns list of (is_start, is_end, oos_start, oos_end) as Timestamps.
    Expanding: IS anchored at start, 2yr initial IS, 6-month OOS steps.
    Rolling  : 2yr IS, 6-month step.
    """
    from dateutil.relativedelta import relativedelta

    expanding = []
    is_start  = pd.Timestamp(start)
    is_end    = is_start + relativedelta(years=2)
    while True:
        oos_start = is_end
        oos_end   = oos_start + relativedelta(months=6)
        if oos_end > pd.Timestamp(end):
            break
        expanding.append((is_start, is_end, oos_start, oos_end))
        is_end = oos_end

    rolling = []
    is_end = is_start + relativedelta(years=2)
    while True:
        oos_start = is_end
        oos_end   = oos_start + relativedelta(months=6)
        if oos_end > pd.Timestamp(end):
            break
        rolling.append((is_start, is_end, oos_start, oos_end))
        is_start = is_start + relativedelta(months=6)
        is_end   = is_end   + relativedelta(months=6)

    return expanding, rolling


# ── Report helpers ───────────────────────────────────────────────────────────────
def fmt_pct(v):
    return f"{v:>+7.1%}" if not np.isnan(v) else "     —"

def fmt_ratio(v):
    return f"{v:>+6.2f}" if not np.isnan(v) else "    —"


def print_wf_table(windows, results, wf_type, candidate_label):
    print(f"\n  {wf_type} windows — {candidate_label}")
    hdr = (f"  {'Win':<4} {'IS Period':<24} {'OOS Period':<24} "
           f"{'IS Ann':>7} {'IS MDD':>7} {'IS T':>5} "
           f"{'OOS Ann':>8} {'OOS MDD':>7} {'OOS T':>5} {'Degrad':>7} {'OOS+':>5}")
    print(hdr)
    print("  " + "-" * 105)

    oos_profitable = 0
    for i, ((is0, is1, oos0, oos1), (is_m, oos_m)) in enumerate(zip(windows, results)):
        is_ann  = is_m["annual_ret"]  if is_m  else np.nan
        is_mdd  = is_m["mdd"]         if is_m  else np.nan
        is_t    = is_m["trades"]      if is_m  else 0
        oos_ann = oos_m["annual_ret"] if oos_m else np.nan
        oos_mdd = oos_m["mdd"]        if oos_m else np.nan
        oos_t   = oos_m["trades"]     if oos_m else 0
        degrad  = oos_ann / is_ann if (is_m and oos_m and not np.isnan(is_ann)
                                       and not np.isnan(oos_ann) and is_ann != 0) else np.nan
        profitable = oos_m["profitable"] if oos_m else False
        if profitable:
            oos_profitable += 1

        is_str  = f"{is0.date()} → {is1.date()}"
        oos_str = f"{oos0.date()} → {oos1.date()}"
        plus    = "YES" if profitable else "no"
        print(f"  {i+1:<4} {is_str:<24} {oos_str:<24} "
              f"{fmt_pct(is_ann)} {fmt_pct(is_mdd)} {is_t:>5} "
              f"{fmt_pct(oos_ann)} {fmt_pct(oos_mdd)} {oos_t:>5} "
              f"{fmt_ratio(degrad)} {plus:>5}")

    total = len(windows)
    print(f"  {'':4} {'OOS profitable':>52}: {oos_profitable}/{total}")


# ── Main ─────────────────────────────────────────────────────────────────────────
def main():
    print("Fetching SOLUSDT daily data...")
    df = fetch_sol()
    full_index = df.index
    data_start = df.index[0]
    data_end   = df.index[-1]
    print(f"  {len(df)} candles | {data_start.date()} → {data_end.date()}\n")

    expanding_wins, rolling_wins = make_windows(data_start, data_end)
    print(f"Window structure: {len(expanding_wins)} expanding, {len(rolling_wins)} rolling")

    SEP = "=" * 109

    for cand in CANDIDATES:
        ema_p = cand["ema_p"]
        mult  = cand["mult"]
        label = cand["label"]

        ema_full, upper_full = add_indicators(df, ema_p, mult)

        # Run all windows
        def run_windows(wins):
            out = []
            for (is0, is1, oos0, oos1) in wins:
                is_slice  = df[(df.index >= is0)  & (df.index < is1)]
                oos_slice = df[(df.index >= oos0) & (df.index < oos1)]
                is_m  = run_period(is_slice,  ema_full, upper_full, full_index)
                oos_m = run_period(oos_slice, ema_full, upper_full, full_index)
                out.append((is_m, oos_m))
            return out

        exp_results  = run_windows(expanding_wins)
        roll_results = run_windows(rolling_wins)

        print(f"\n{SEP}")
        print(f"Walk-Forward Analysis — {label}")
        print(SEP)

        print_wf_table(expanding_wins, exp_results, "EXPANDING", label)
        print_wf_table(rolling_wins,   roll_results, "ROLLING",   label)

        # ── Summary ──────────────────────────────────────────────────────────
        print(f"\n  Summary — {label}")
        for wf_type, wins, results in [
            ("Expanding", expanding_wins, exp_results),
            ("Rolling",   rolling_wins,  roll_results),
        ]:
            oos_anns = [r[1]["annual_ret"] for r in results
                        if r[1] and not np.isnan(r[1]["annual_ret"])]
            oos_mdds = [r[1]["mdd"]        for r in results
                        if r[1] and not np.isnan(r[1]["mdd"])]
            n_prof   = sum(1 for r in results if r[1] and r[1]["profitable"])
            n_total  = len(results)
            mean_oos = np.mean(oos_anns) if oos_anns else np.nan
            worst_dd = min(oos_mdds)     if oos_mdds else np.nan
            print(f"  {wf_type:<12} OOS profitable: {n_prof}/{n_total}  "
                  f"mean OOS ann: {fmt_pct(mean_oos).strip()}  "
                  f"worst OOS MDD: {fmt_pct(worst_dd).strip()}")

    print(f"\n{SEP}")
    print("Note: OOS windows of 6 months yield ~2-4 trades each at this trade rate.")
    print("Interpret direction (consistently profitable?) not statistical significance.")
    print(SEP)


if __name__ == "__main__":
    main()
