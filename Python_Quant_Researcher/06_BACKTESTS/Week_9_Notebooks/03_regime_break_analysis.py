"""
03_regime_break_analysis.py — Targeted regime break analysis
Week 9 | 2026-06-01

Combinations tested:
  BNB-USD   ADX         period=14  threshold=25  stop=12%
  BNB-USD   Donchian    period=60  stop=5%
  BNB-USD   Donchian    period=20  stop=5%
  AVAX-USD  Keltner     ema=15     mult=2.0

Split date: January 1 2024 (institutional adoption break, METHODOLOGY_STANDARDS.md)
Decision rules: post-break PF > 2.0 → VIABLE | 1.0–2.0 → EDGE COMPRESSED | <1.0 → REGIME CHANGE

Annual return computed from the full equity curve sliced at the break date.
This correctly accounts for idle cash periods between trades.

PF / win rate split by trade EXIT date (same convention as full discovery grid).
"""

import importlib.util
import os
import numpy as np
import pandas as pd
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange

# ── Load grid module (filename starts with digit — importlib required) ─────────
BASE   = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE, "regime_break_results.csv")

spec = importlib.util.spec_from_file_location(
    "altcoin_grid",
    os.path.join(BASE, "01_altcoin_discovery_grid.py"),
)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

BREAK_TS = pd.Timestamp("2024-01-01")
COSTS    = g.COSTS


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE-COMBO BACKTEST RUNNERS
# ══════════════════════════════════════════════════════════════════════════════

def run_adx_single(df, period, threshold, stop_pct):
    closes = df["close"].values
    lows   = df["low"].values
    N      = len(df)
    ind    = ADXIndicator(df["high"], df["low"], df["close"], window=period, fillna=False)
    adx    = ind.adx().values
    pdi    = ind.adx_pos().values
    mdi    = ind.adx_neg().values

    trades = []
    in_pos = False
    ei = epx = peak = 0

    for i in range(1, N):
        if np.isnan(adx[i]):
            continue
        if not in_pos:
            if adx[i] >= threshold and pdi[i] > mdi[i]:
                in_pos = True
                ei, epx, peak = i, closes[i], closes[i]
        else:
            stop_lvl = peak * (1 - stop_pct)
            if lows[i] <= stop_lvl:
                trades.append({"ei": ei, "xi": i, "ret": (stop_lvl - epx) / epx})
                in_pos = False
            else:
                if closes[i] > peak:
                    peak = closes[i]
                if not (adx[i] >= threshold and pdi[i] > mdi[i]):
                    trades.append({"ei": ei, "xi": i, "ret": (closes[i] - epx) / epx})
                    in_pos = False

    if in_pos:
        trades.append({"ei": ei, "xi": N - 1, "ret": (closes[-1] - epx) / epx})

    return trades, g.build_equity(trades, closes, N)


def run_donchian_single(df, period, stop_pct):
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    N      = len(df)

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


def run_keltner_single(df, ema_period, mult):
    closes = df["close"].values
    lows   = df["low"].values
    N      = len(df)

    ema   = pd.Series(closes).ewm(span=ema_period, adjust=False).mean().values
    atr   = AverageTrueRange(df["high"], df["low"], df["close"],
                             window=ema_period).average_true_range().values
    upper = ema + mult * atr

    trades = []
    in_pos = False
    ei = epx = 0

    for i in range(1, N):
        if np.isnan(upper[i - 1]) or np.isnan(ema[i - 1]):
            continue
        if not in_pos:
            if closes[i] > upper[i - 1]:
                in_pos = True
                ei, epx = i, closes[i]
        else:
            if lows[i] <= ema[i - 1]:
                trades.append({"ei": ei, "xi": i, "ret": (ema[i - 1] - epx) / epx})
                in_pos = False
            elif closes[i] < ema[i]:
                trades.append({"ei": ei, "xi": i, "ret": (closes[i] - epx) / epx})
                in_pos = False

    if in_pos:
        trades.append({"ei": ei, "xi": N - 1, "ret": (closes[-1] - epx) / epx})

    return trades, g.build_equity(trades, closes, N)


# ══════════════════════════════════════════════════════════════════════════════
# REGIME BREAK ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def analyse_regime_break(trades, eq, df, break_ts):
    """
    Split at break_ts and return pre/post metrics.

    Annual return: computed from the equity curve sliced at the break index.
    This correctly reflects idle cash periods and is directly comparable to
    the full-period metrics from the discovery grid.

    PF / win rate: computed from trade lists split by EXIT date.
    Post-break trade count: trades exiting on or after break_ts.
    """
    dates = df.index
    N     = len(df)

    # Break index: first bar on or after break_ts
    break_idx = dates.searchsorted(break_ts)
    break_idx = min(break_idx, N - 1)

    # ── Annual returns from equity curve ──────────────────────────────────────
    pre_days  = max((dates[break_idx - 1] - dates[0]).days, 1) if break_idx > 0 else 1
    post_days = max((dates[-1] - dates[break_idx]).days, 1)

    eq_at_break = float(eq[break_idx])

    pre_ann  = float(eq_at_break ** (365.25 / pre_days) - 1)
    post_ann = float((eq[-1] / eq_at_break) ** (365.25 / post_days) - 1)

    # ── PF / win rate from trade lists ────────────────────────────────────────
    pre_trades  = [t for t in trades if dates[t["xi"]] <  break_ts]
    post_trades = [t for t in trades if dates[t["xi"]] >= break_ts]

    def pf_wr_n(tlist):
        if not tlist:
            return None, None, 0
        wins   = [t["ret"] for t in tlist if t["ret"] > 0]
        losses = [abs(t["ret"]) for t in tlist if t["ret"] <= 0]
        pf     = float(sum(wins) / sum(losses)) if losses else float("inf")
        return pf, float(len(wins) / len(tlist)), len(tlist)

    pre_pf,  pre_wr,  pre_n  = pf_wr_n(pre_trades)
    post_pf, post_wr, post_n = pf_wr_n(post_trades)

    # ── Decision rule ─────────────────────────────────────────────────────────
    if post_n == 0:
        decision = "INSUFFICIENT POST-BREAK DATA"
    elif post_pf is not None and post_pf < 1.0:
        decision = "REGIME CHANGE"
    elif post_pf is not None and post_pf <= 2.0:
        decision = "EDGE COMPRESSED"
    else:
        decision = "VIABLE"

    return dict(
        break_date  = str(break_ts.date()),
        pre_n       = pre_n,
        pre_pf      = pre_pf,
        pre_wr      = pre_wr,
        pre_ann_ret = pre_ann,
        post_n      = post_n,
        post_pf     = post_pf,
        post_wr     = post_wr,
        post_ann_ret= post_ann,
        decision    = decision,
    )


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY HELPER
# ══════════════════════════════════════════════════════════════════════════════

def print_result(asset, strategy, params, rb):
    """Print a single regime break result block."""
    pf_fmt  = lambda v: f"{v:.3f}" if v is not None and not np.isinf(v) else ("inf" if v == float("inf") else "—")
    wr_fmt  = lambda v: f"{v:.1%}" if v is not None else "—"
    ann_fmt = lambda v: f"{v:+.1%}" if v is not None else "—"

    print(f"\n  {asset}  |  {strategy}  |  {params}")
    print(f"  Break date : {rb['break_date']}")
    print(f"  {'Metric':<22}  {'Pre-break':>12}  {'Post-break':>12}")
    print(f"  {'-'*50}")
    print(f"  {'Trade count':<22}  {rb['pre_n']:>12}  {rb['post_n']:>12}")
    print(f"  {'Profit factor':<22}  {pf_fmt(rb['pre_pf']):>12}  {pf_fmt(rb['post_pf']):>12}")
    print(f"  {'Win rate':<22}  {wr_fmt(rb['pre_wr']):>12}  {wr_fmt(rb['post_wr']):>12}")
    print(f"  {'Annual return':<22}  {ann_fmt(rb['pre_ann_ret']):>12}  {ann_fmt(rb['post_ann_ret']):>12}")
    print(f"  {'Decision':<22}  {'':>12}  {rb['decision']}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    SEP = "═" * 70

    print(SEP)
    print("REGIME BREAK ANALYSIS — Jan 2024 split")
    print(f"Decision rules:  PF > 2.0 → VIABLE  |  1.0–2.0 → EDGE COMPRESSED  |  <1.0 → REGIME CHANGE")
    print(SEP)

    combinations = [
        ("BNB-USD",  "ADX",      "p=14 thr=25 stop=12%",  "adx",      {"period": 14, "threshold": 25, "stop_pct": 0.12}),
        ("BNB-USD",  "Donchian", "per=60 stop=5%",         "donchian", {"period": 60, "stop_pct": 0.05}),
        ("BNB-USD",  "Donchian", "per=20 stop=5%",         "donchian", {"period": 20, "stop_pct": 0.05}),
        ("AVAX-USD", "Keltner",  "ema=15 mult=2.0",        "keltner",  {"ema_period": 15, "mult": 2.0}),
    ]

    # Download data for each unique asset once
    data_cache = {}
    for asset in dict.fromkeys(c[0] for c in combinations):
        print(f"\nFetching {asset}...")
        df = g.fetch_asset(asset)
        data_cache[asset] = df
        bh = g.bh_benchmark(df["close"].values, (df.index[-1] - df.index[0]).days)
        print(f"  {len(df)} candles | {df.index[0].date()} → {df.index[-1].date()}")
        print(f"  B&H: {bh['annual_ret']:.1%} annual | Sortino {bh['sortino']:.2f}")

    # Run each combination
    print(f"\n{SEP}")
    print("RESULTS")
    print(SEP)

    rows = []
    current_asset = None

    for asset, strategy, params, kind, kwargs in combinations:
        if asset != current_asset:
            current_asset = asset
            print(f"\n{'─'*70}")
            print(f"  {asset}")
            print(f"{'─'*70}")

        df = data_cache[asset]

        if kind == "adx":
            trades, eq = run_adx_single(df, **kwargs)
        elif kind == "donchian":
            trades, eq = run_donchian_single(df, **kwargs)
        elif kind == "keltner":
            trades, eq = run_keltner_single(df, **kwargs)

        rb = analyse_regime_break(trades, eq, df, BREAK_TS)
        print_result(asset, strategy, params, rb)

        rows.append({
            "asset":        asset,
            "strategy":     strategy,
            "params":       params,
            "break_date":   rb["break_date"],
            "pre_n":        rb["pre_n"],
            "pre_pf":       rb["pre_pf"],
            "pre_wr":       rb["pre_wr"],
            "pre_ann_ret":  rb["pre_ann_ret"],
            "post_n":       rb["post_n"],
            "post_pf":      rb["post_pf"],
            "post_wr":      rb["post_wr"],
            "post_ann_ret": rb["post_ann_ret"],
            "decision":     rb["decision"],
        })

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n\n{SEP}")
    print("SUMMARY")
    print(SEP)
    hdr = (f"  {'Asset':<10}  {'Strategy':<10}  {'Parameters':<22}  "
           f"{'PrePF':>6}  {'PreAnn':>7}  "
           f"{'PostPF':>6}  {'PostWR':>6}  {'PostN':>5}  {'PostAnn':>7}  Decision")
    print(hdr)
    print(f"  {'-'*110}")
    for r in rows:
        pre_pf  = f"{r['pre_pf']:.3f}"  if r["pre_pf"]  is not None else "  —"
        post_pf = f"{r['post_pf']:.3f}" if r["post_pf"] is not None else "  —"
        post_wr = f"{r['post_wr']:.1%}" if r["post_wr"] is not None else "  —"
        print(f"  {r['asset']:<10}  {r['strategy']:<10}  {r['params']:<22}  "
              f"{pre_pf:>6}  {r['pre_ann_ret']:>+7.1%}  "
              f"{post_pf:>6}  {post_wr:>6}  {r['post_n']:>5}  "
              f"{r['post_ann_ret']:>+7.1%}  {r['decision']}")

    # ── Save CSV ──────────────────────────────────────────────────────────────
    df_out = pd.DataFrame(rows)
    df_out.to_csv(OUTPUT, index=False)
    print(f"\nSaved → {OUTPUT}")
    print(f"\n{SEP}")
    print("Review complete. Await instruction before proceeding to walk-forward.")
    print(SEP)


if __name__ == "__main__":
    main()
