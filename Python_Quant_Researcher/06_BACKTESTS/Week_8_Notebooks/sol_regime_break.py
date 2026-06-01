"""
sol_regime_break.py — SOL Keltner ema=19 mult=1.5 regime break analysis
Week 8 | 2026-05-19
Splits: Jan 2024 (BTC ETF approval), Aug 2025 (SOL ATH / subsequent decline)
"""

import os
import numpy as np
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv
from ta.volatility import AverageTrueRange

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

EMA_P  = 19
MULT   = 1.5
COSTS  = 0.0015

BREAK1 = pd.Timestamp("2024-01-11")   # BTC spot ETF approval date
BREAK2 = pd.Timestamp("2025-08-01")   # SOL ATH region / subsequent decline


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


def run_full_backtest(df):
    """Returns list of trade dicts with entry/exit dates, returns, and period tags."""
    closes = df["close"].values
    lows   = df["low"].values
    dates  = df.index
    N      = len(df)

    ema   = pd.Series(closes).ewm(span=EMA_P, adjust=False).mean().values
    atr   = AverageTrueRange(df["high"], df["low"], df["close"],
                             window=EMA_P).average_true_range().values
    upper = ema + MULT * atr

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
                ret = (ema[i - 1] - epx) / epx
                trades.append(dict(entry_date=dates[ei], exit_date=dates[i],
                                   ei=ei, xi=i, ret=ret))
                in_pos = False
            elif closes[i] < ema[i]:
                ret = (closes[i] - epx) / epx
                trades.append(dict(entry_date=dates[ei], exit_date=dates[i],
                                   ei=ei, xi=i, ret=ret))
                in_pos = False

    if in_pos:
        trades.append(dict(entry_date=dates[ei], exit_date=dates[-1],
                           ei=ei, xi=N - 1, ret=(closes[-1] - epx) / epx))

    return trades, closes, N, (df.index[-1] - df.index[0]).days


def period_stats(trades, closes, N, n_days, label):
    """Compute full stats for a subset of trades."""
    if not trades:
        return dict(label=label, n=0, win_rate=np.nan, avg_win=np.nan,
                    avg_loss=np.nan, pf=np.nan, annual_ret=np.nan, mdd=np.nan)

    rets  = [t["ret"] for t in trades]
    wins  = [r for r in rets if r > 0]
    losses= [r for r in rets if r <= 0]
    pf    = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else np.nan

    # Equity curve over the sub-period bars only
    sub_closes = closes[trades[0]["ei"]: trades[-1]["xi"] + 1]
    sub_N      = len(sub_closes)
    sub_n_days = n_days  # passed in as the sub-period span

    eq = np.ones(sub_N)
    offset = trades[0]["ei"]
    for t in trades:
        ei_ = t["ei"] - offset
        xi_ = t["xi"] - offset
        if ei_ < 0 or xi_ >= sub_N:
            continue
        base = eq[ei_]
        for j in range(ei_ + 1, xi_):
            if j < sub_N:
                eq[j] = base * (sub_closes[j] / sub_closes[ei_])
        if xi_ < sub_N:
            eq[xi_] = base * (1 + t["ret"]) * (1 - COSTS)
            if xi_ + 1 < sub_N:
                eq[xi_ + 1:] = eq[xi_]

    ann  = eq[-1] ** (365.25 / n_days) - 1 if n_days > 0 else np.nan
    rm   = np.maximum.accumulate(eq)
    mdd  = ((eq - rm) / rm).min()

    return dict(
        label     = label,
        n         = len(trades),
        win_rate  = len(wins) / len(trades),
        avg_win   = np.mean(wins)   if wins   else np.nan,
        avg_loss  = np.mean(losses) if losses else np.nan,
        pf        = pf,
        annual_ret= ann,
        mdd       = mdd,
    )


def print_table(stats_list):
    SEP = "=" * 82
    print(SEP)
    hdr = (f"{'Period':<28} {'Trades':>6} {'Win%':>6} {'Avg Win':>8} "
           f"{'Avg Loss':>9} {'PF':>6} {'Ann Ret':>8} {'MDD':>7}")
    print(hdr)
    print("-" * 82)
    for s in stats_list:
        n       = s["n"]
        wr      = f"{s['win_rate']:.1%}"    if not np.isnan(s.get("win_rate", np.nan))   else "—"
        aw      = f"{s['avg_win']:+.2%}"    if not np.isnan(s.get("avg_win", np.nan))    else "—"
        al      = f"{s['avg_loss']:+.2%}"   if not np.isnan(s.get("avg_loss", np.nan))   else "—"
        pf      = f"{s['pf']:.3f}"          if not np.isnan(s.get("pf", np.nan))         else "—"
        ann     = f"{s['annual_ret']:+.1%}" if not np.isnan(s.get("annual_ret", np.nan)) else "—"
        mdd     = f"{s['mdd']:.1%}"         if not np.isnan(s.get("mdd", np.nan))        else "—"
        print(f"  {s['label']:<26} {n:>6} {wr:>6} {aw:>8} {al:>9} {pf:>6} {ann:>8} {mdd:>7}")
    print(SEP)


def main():
    print("Fetching SOLUSDT data...")
    df = fetch_sol()
    print(f"  {len(df)} candles | {df.index[0].date()} → {df.index[-1].date()}\n")

    trades, closes, N, _ = run_full_backtest(df)
    print(f"Full backtest: {len(trades)} trades\n")

    # ── Split 1: Jan 2024 (BTC ETF) ───────────────────────────────────────────
    pre_etf  = [t for t in trades if t["exit_date"] < BREAK1]
    post_etf = [t for t in trades if t["entry_date"] >= BREAK1]
    mid_etf  = [t for t in trades
                if not (t["exit_date"] < BREAK1 or t["entry_date"] >= BREAK1)]

    d_pre_etf  = (BREAK1 - df.index[0]).days
    d_post_etf = (df.index[-1] - BREAK1).days

    s_full     = period_stats(trades,   closes, N, (df.index[-1]-df.index[0]).days, "FULL PERIOD")
    s_pre_etf  = period_stats(pre_etf,  closes, N, d_pre_etf,  f"Pre-BTC ETF  (< Jan 2024)")
    s_post_etf = period_stats(post_etf, closes, N, d_post_etf, f"Post-BTC ETF (≥ Jan 2024)")

    # ── Split 2: Aug 2025 (SOL ATH) ───────────────────────────────────────────
    pre_ath  = [t for t in trades if t["exit_date"] < BREAK2]
    post_ath = [t for t in trades if t["entry_date"] >= BREAK2]

    d_pre_ath  = (BREAK2 - df.index[0]).days
    d_post_ath = (df.index[-1] - BREAK2).days

    s_pre_ath  = period_stats(pre_ath,  closes, N, d_pre_ath,  f"Pre-Aug 2025 (< Aug 2025)")
    s_post_ath = period_stats(post_ath, closes, N, d_post_ath, f"Post-Aug 2025 (≥ Aug 2025)")

    SEP2 = "=" * 82
    print(f"{SEP2}")
    print(f"SOL Keltner ema={EMA_P} mult={MULT}  —  Regime Break Analysis")
    print(f"Data: {df.index[0].date()} → {df.index[-1].date()}")
    print(f"{SEP2}\n")

    print("SPLIT 1 — BTC Spot ETF approval (11 Jan 2024)")
    print_table([s_full, s_pre_etf, s_post_etf])

    print("\nSPLIT 2 — SOL ATH / subsequent decline (Aug 2025)")
    print_table([s_full, s_pre_ath, s_post_ath])

    # ── Three-period table ─────────────────────────────────────────────────────
    pre_etf_only = [t for t in trades
                    if t["exit_date"] < BREAK1]
    mid_period   = [t for t in trades
                    if t["entry_date"] >= BREAK1 and t["exit_date"] < BREAK2]
    post_period  = [t for t in trades
                    if t["entry_date"] >= BREAK2]

    d_mid = (BREAK2 - BREAK1).days

    s_p1 = period_stats(pre_etf_only, closes, N, d_pre_etf, "Pre-ETF  (< Jan 2024)")
    s_p2 = period_stats(mid_period,   closes, N, d_mid,     "ETF→ATH  (Jan24–Aug25)")
    s_p3 = period_stats(post_period,  closes, N, d_post_ath,"Post-ATH (≥ Aug 2025)")

    print("\nTHREE-PERIOD VIEW")
    print_table([s_p1, s_p2, s_p3])

    # ── Dominant question: regime change or drawdown? ──────────────────────────
    print(f"\nPost-Aug 2025  —  {s_post_ath['n']} trades:")
    if not np.isnan(s_post_ath["pf"]):
        print(f"  Profit factor : {s_post_ath['pf']:.3f}")
    else:
        print(f"  Profit factor : insufficient data (no losses or no trades)")
    print(f"  Win rate      : {s_post_ath['win_rate']:.1%}" if not np.isnan(s_post_ath.get("win_rate",np.nan)) else "  Win rate      : —")
    print(f"  Annual return : {s_post_ath['annual_ret']:+.1%}" if not np.isnan(s_post_ath.get("annual_ret",np.nan)) else "  Annual return : —")

    print(f"\nPost-Jan 2024  —  {s_post_etf['n']} trades:")
    if not np.isnan(s_post_etf["pf"]):
        print(f"  Profit factor : {s_post_etf['pf']:.3f}")
    else:
        print(f"  Profit factor : insufficient data")
    print(f"{SEP2}")


if __name__ == "__main__":
    main()
