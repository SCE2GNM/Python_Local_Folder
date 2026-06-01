"""
keltner_gap_analysis.py — Exit slippage / gap analysis for Keltner ema=22 mult=1.5
Week 8 | 2026-05-19

For every intrabar-stop exit (LOW <= prior EMA): measure gap between the
prior EMA (backtest fill) and the actual open price on that bar.
Then reprice all affected trades at open and measure impact on annual return
and MDD.
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

EMA_P  = 22
MULT   = 1.5
COSTS  = 0.0015


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


def build_equity(trades, closes, N):
    eq = np.ones(N)
    for t in sorted(trades, key=lambda x: x["ei"]):
        ei, xi = t["ei"], t["xi"]
        base = eq[ei]
        for j in range(ei + 1, xi):
            eq[j] = base * (closes[j] / closes[ei])
        eq[xi] = base * (1 + t["ret"]) * (1 - COSTS)
        if xi + 1 < N:
            eq[xi + 1:] = eq[xi]
    return eq


def annual_ret(eq, n_days):
    return eq[-1] ** (365.25 / n_days) - 1


def max_dd(eq):
    run_max = np.maximum.accumulate(eq)
    return ((eq - run_max) / run_max).min()


def main():
    print("Fetching SOLUSDT daily data...")
    df     = fetch_sol()
    closes = df["close"].values
    opens  = df["open"].values
    lows   = df["low"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days

    ema   = pd.Series(closes).ewm(span=EMA_P, adjust=False).mean().values
    atr   = AverageTrueRange(df["high"], df["low"], df["close"],
                             window=EMA_P).average_true_range().values
    upper = ema + MULT * atr

    # ── Replay backtest, record full trade detail ──────────────────────────────
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
            if lows[i] <= ema[i - 1]:             # intrabar stop
                prior_ema  = ema[i - 1]
                exit_open  = opens[i]
                ret_bt     = (prior_ema - epx) / epx
                ret_open   = (exit_open - epx) / epx
                trades.append(dict(
                    ei=ei, xi=i, epx=epx,
                    exit_type="stop",
                    prior_ema=prior_ema,
                    exit_open=exit_open,
                    gap_pct=(exit_open - prior_ema) / prior_ema * 100,
                    ret=ret_bt,
                    ret_open=ret_open,
                ))
                in_pos = False
            elif closes[i] < ema[i]:               # close signal
                trades.append(dict(
                    ei=ei, xi=i, epx=epx,
                    exit_type="close",
                    prior_ema=ema[i],
                    exit_open=opens[i],
                    gap_pct=np.nan,                # gap not applicable for close fills
                    ret=(closes[i] - epx) / epx,
                    ret_open=(closes[i] - epx) / epx,  # same — fill at close either way
                ))
                in_pos = False

    if in_pos:
        trades.append(dict(
            ei=ei, xi=N - 1, epx=epx,
            exit_type="open",
            prior_ema=ema[-1],
            exit_open=opens[-1],
            gap_pct=np.nan,
            ret=(closes[-1] - epx) / epx,
            ret_open=(closes[-1] - epx) / epx,
        ))

    # ── Gap statistics (stop exits only) ──────────────────────────────────────
    stop_trades = [t for t in trades if t["exit_type"] == "stop"]
    gaps        = [t["gap_pct"] for t in stop_trades if not np.isnan(t["gap_pct"])]

    large_gaps  = [t for t in stop_trades if not np.isnan(t["gap_pct"]) and t["gap_pct"] < -3.0]
    worst       = min(stop_trades, key=lambda t: t["gap_pct"] if not np.isnan(t["gap_pct"]) else 0)

    # ── Equity curves ─────────────────────────────────────────────────────────
    # Backtest fill (EMA level for stop exits)
    eq_bt   = build_equity(trades, closes, N)
    ann_bt  = annual_ret(eq_bt, n_days)
    mdd_bt  = max_dd(eq_bt)

    # Open fill (worst case — open price for stop exits)
    trades_open = [dict(t, ret=t["ret_open"]) for t in trades]
    eq_op   = build_equity(trades_open, closes, N)
    ann_op  = annual_ret(eq_op, n_days)
    mdd_op  = max_dd(eq_op)

    # ── Report ────────────────────────────────────────────────────────────────
    SEP = "=" * 70
    print(f"\n{SEP}")
    print(f"Keltner ema={EMA_P} mult={MULT}  —  Exit Gap Analysis")
    print(f"Data: {df.index[0].date()} → {df.index[-1].date()}")
    print(SEP)

    print(f"\nTrade count breakdown:")
    print(f"  Total trades          : {len(trades)}")
    print(f"  Stop exits (LOW≤EMA)  : {len(stop_trades)}")
    print(f"  Close-signal exits    : {len([t for t in trades if t['exit_type']=='close'])}")
    print(f"  Open position (last)  : {len([t for t in trades if t['exit_type']=='open'])}")

    print(f"\nGap statistics (stop exits only — {len(stop_trades)} trades):")
    if gaps:
        print(f"  Mean gap              : {np.mean(gaps):+.2f}%")
        print(f"  Median gap            : {np.median(gaps):+.2f}%")
        print(f"  Gaps > +1% (open above EMA — favourable)   : {sum(1 for g in gaps if g > 1)}")
        print(f"  Gaps between -1% and +1% (neutral)         : {sum(1 for g in gaps if -1 <= g <= 1)}")
        print(f"  Gaps < -1% (open below EMA — adverse)      : {sum(1 for g in gaps if g < -1)}")
        print(f"  Gaps < -3% (significant adverse)           : {len(large_gaps)}")
        print(f"  Largest adverse gap   : {min(gaps):+.2f}%")
        print(f"  Largest favourable gap: {max(gaps):+.2f}%")

    if large_gaps:
        print(f"\n  Trades with gap < -3% (date | EMA | Open | gap% | BT ret | Open ret):")
        large_gaps_sorted = sorted(large_gaps, key=lambda t: t["gap_pct"])
        for t in large_gaps_sorted:
            exit_date = df.index[t["xi"]].date()
            print(f"    {exit_date}  EMA={t['prior_ema']:>8.3f}  "
                  f"Open={t['exit_open']:>8.3f}  gap={t['gap_pct']:>+6.2f}%  "
                  f"BT_ret={t['ret']:>+7.2%}  Open_ret={t['ret_open']:>+7.2%}")

    if worst and not np.isnan(worst["gap_pct"]):
        print(f"\n  Worst single gap:")
        exit_date = df.index[worst["xi"]].date()
        print(f"    {exit_date}  EMA={worst['prior_ema']:.3f}  "
              f"Open={worst['exit_open']:.3f}  gap={worst['gap_pct']:+.2f}%")
        extra_loss = worst["ret_open"] - worst["ret"]
        print(f"    Backtest return: {worst['ret']:+.2%}  →  Open-fill return: {worst['ret_open']:+.2%}")
        print(f"    Additional loss from gap: {extra_loss:+.2%}")

    print(f"\nEquity impact — backtest fill vs open fill:")
    print(f"  {'Metric':<25} {'BT fill (EMA)':>15}  {'Open fill':>12}  {'Delta':>10}")
    print(f"  {'-'*25} {'-'*15}  {'-'*12}  {'-'*10}")
    print(f"  {'Annual return':<25} {ann_bt:>14.1%}  {ann_op:>11.1%}  {ann_op-ann_bt:>+9.1%}")
    print(f"  {'Max drawdown':<25} {mdd_bt:>14.1%}  {mdd_op:>11.1%}  {mdd_op-mdd_bt:>+9.1%}")
    print(f"  {'Final equity':<25} {eq_bt[-1]:>14.4f}  {eq_op[-1]:>11.4f}  {eq_op[-1]-eq_bt[-1]:>+9.4f}")

    print(SEP)


if __name__ == "__main__":
    main()
