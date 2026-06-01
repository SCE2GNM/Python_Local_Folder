"""
sol_grid_search.py  —  SOL/USDT multi-strategy discovery grid
Week 8 | 2026-05-19
Strategies : ADX, Supertrend, Donchian, Keltner, Bollinger
Combos     : ~1,478  (ADX 1232 + ST 70 + DC 77 + KC 44 + BB 55)
Methodology: 0.15% round-trip costs, bar-by-bar LOW stop, min 30 trades, MDD > -50%
"""

import os
import numpy as np
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange

# ── Path / env ──────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))   # Week_8_Notebooks/
WEEK_DIR     = os.path.dirname(BASE_DIR)                    # 06_BACKTESTS/
PROJECT_ROOT = os.path.dirname(WEEK_DIR)                    # project root
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

COSTS      = 0.0015   # 0.15% round-trip, applied once at exit bar
MIN_TRADES = 30
MAX_MDD    = -0.50


# ── Data ────────────────────────────────────────────────────────────────────────
def fetch_sol():
    client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_SECRET_KEY"))
    raw = client.get_historical_klines(
        "SOLUSDT", Client.KLINE_INTERVAL_1DAY, "1 Jan, 2020"
    )
    cols = ["open_time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "taker_base", "taker_quote", "ignore"]
    df = pd.DataFrame(raw, columns=cols)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df["dt"] = pd.to_datetime(df["open_time"], unit="ms")
    return df.set_index("dt").sort_index()


# ── Core helpers ─────────────────────────────────────────────────────────────────
def build_equity(trades, closes, N):
    """Daily MtM equity curve. Costs applied once at exit bar only."""
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


def calc_metrics(trades, eq, n_days):
    if len(trades) < MIN_TRADES:
        return None
    ann = eq[-1] ** (365.25 / n_days) - 1
    run_max = np.maximum.accumulate(eq)
    mdd = ((eq - run_max) / run_max).min()
    if mdd < MAX_MDD:
        return None
    daily_r = np.diff(eq) / eq[:-1]
    neg = daily_r[daily_r < 0]
    down_std = np.std(neg) * np.sqrt(365.25) if len(neg) > 1 else np.nan
    sortino = ann / down_std if down_std and down_std > 0 else np.nan
    gains  = [t["ret"] for t in trades if t["ret"] > 0]
    losses = [abs(t["ret"]) for t in trades if t["ret"] <= 0]
    pf = sum(gains) / sum(losses) if losses else np.nan
    return dict(
        annual_ret=ann, mdd=mdd, sortino=sortino,
        pf=pf, win_rate=len(gains) / len(trades), trades=len(trades)
    )


def bh_benchmark(closes, n_days):
    eq = closes / closes[0]
    ann = eq[-1] ** (365.25 / n_days) - 1
    run_max = np.maximum.accumulate(eq)
    mdd = ((eq - run_max) / run_max).min()
    daily_r = np.diff(eq) / eq[:-1]
    neg = daily_r[daily_r < 0]
    down_std = np.std(neg) * np.sqrt(365.25) if len(neg) > 1 else np.nan
    sortino = ann / down_std if down_std and down_std > 0 else np.nan
    return dict(strategy="BUY_HOLD", params="SOLUSDT spot",
                annual_ret=ann, mdd=mdd, sortino=sortino,
                pf=np.nan, win_rate=np.nan, trades=1)


# ── ADX (1,232 combos: periods 7-20 × thresholds 15-25 × stops 5-12%) ──────────
def run_adx_grid(df):
    results = []
    closes = df["close"].values
    lows   = df["low"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days

    # Pre-cache ADX by period (avoids 1,232 recomputations → 14 only)
    cache = {}
    for p in range(7, 21):
        ind = ADXIndicator(df["high"], df["low"], df["close"], window=p)
        cache[p] = (ind.adx().values, ind.adx_pos().values, ind.adx_neg().values)

    total = 14 * 11 * 8
    done  = 0
    for p in range(7, 21):
        adx, pdi, mdi = cache[p]
        for thr in range(15, 26):
            for sp in range(5, 13):
                stop_pct = sp / 100.0
                trades = []
                in_pos = False
                ei = epx = peak = 0

                for i in range(1, N):
                    if np.isnan(adx[i]):
                        continue
                    if not in_pos:
                        if adx[i] >= thr and pdi[i] > mdi[i]:
                            in_pos = True
                            ei, epx, peak = i, closes[i], closes[i]
                    else:
                        stop_lvl = peak * (1 - stop_pct)
                        if lows[i] <= stop_lvl:
                            trades.append(dict(ei=ei, xi=i,
                                               ret=(stop_lvl - epx) / epx))
                            in_pos = False
                        else:
                            if closes[i] > peak:
                                peak = closes[i]
                            if not (adx[i] >= thr and pdi[i] > mdi[i]):
                                trades.append(dict(ei=ei, xi=i,
                                                   ret=(closes[i] - epx) / epx))
                                in_pos = False

                if in_pos:
                    trades.append(dict(ei=ei, xi=N - 1,
                                       ret=(closes[-1] - epx) / epx))

                if trades:
                    eq = build_equity(trades, closes, N)
                    m  = calc_metrics(trades, eq, n_days)
                    if m:
                        m["strategy"] = "ADX"
                        m["params"]   = f"p={p} thr={thr} stop={sp}%"
                        results.append(m)

                done += 1
                if done % 300 == 0:
                    print(f"  ADX {done}/{total} ({done/total:.0%})")

    print(f"  ADX complete — {len(results)} passing")
    return results


# ── Supertrend (70 combos: ATR 7-20 × mult 2.0-4.0 step 0.5) ───────────────────
def _compute_supertrend(highs, lows, closes, atr_p, mult):
    N    = len(closes)
    prev = np.concatenate([[closes[0]], closes[:-1]])
    tr   = np.maximum(highs - lows,
           np.maximum(np.abs(highs - prev), np.abs(lows - prev)))

    atr = np.full(N, np.nan)
    atr[atr_p - 1] = np.mean(tr[:atr_p])
    for i in range(atr_p, N):
        atr[i] = (atr[i - 1] * (atr_p - 1) + tr[i]) / atr_p

    st  = np.full(N, np.nan)
    ub  = np.full(N, np.nan)   # support line (bullish)
    lb  = np.full(N, np.nan)   # resistance line (bearish)
    dir = np.zeros(N, dtype=int)

    for i in range(atr_p - 1, N):
        hl2      = (highs[i] + lows[i]) / 2
        basic_ub = hl2 - mult * atr[i]
        basic_lb = hl2 + mult * atr[i]

        if i == atr_p - 1:
            ub[i], lb[i] = basic_ub, basic_lb
            dir[i] = 1 if closes[i] > basic_lb else -1
        else:
            ub[i] = basic_ub if basic_ub > ub[i-1] or closes[i-1] < ub[i-1] else ub[i-1]
            lb[i] = basic_lb if basic_lb < lb[i-1] or closes[i-1] > lb[i-1] else lb[i-1]
            if   dir[i-1] == -1 and closes[i] > lb[i]: dir[i] =  1
            elif dir[i-1] ==  1 and closes[i] < ub[i]: dir[i] = -1
            else:                                        dir[i] = dir[i-1]

        st[i] = ub[i] if dir[i] == 1 else lb[i]

    return st, dir


def run_supertrend_grid(df):
    results = []
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days

    total = 14 * 5
    done  = 0
    for atr_p in range(7, 21):
        for mult in [2.0, 2.5, 3.0, 3.5, 4.0]:
            st, dir = _compute_supertrend(highs, lows, closes, atr_p, mult)
            trades  = []
            in_pos  = False
            ei = epx = 0

            for i in range(1, N):
                if np.isnan(st[i]) or np.isnan(st[i - 1]):
                    continue
                if not in_pos:
                    if dir[i - 1] == -1 and dir[i] == 1:   # trend flips bullish
                        in_pos = True
                        ei, epx = i, closes[i]
                else:
                    if lows[i] <= st[i - 1]:                # LOW breaches prior ST stop
                        exit_px = min(closes[i], st[i - 1])
                        trades.append(dict(ei=ei, xi=i, ret=(exit_px - epx) / epx))
                        in_pos = False
                    elif dir[i] == -1:                       # trend flips bearish at close
                        trades.append(dict(ei=ei, xi=i, ret=(closes[i] - epx) / epx))
                        in_pos = False

            if in_pos:
                trades.append(dict(ei=ei, xi=N - 1, ret=(closes[-1] - epx) / epx))

            if trades:
                eq = build_equity(trades, closes, N)
                m  = calc_metrics(trades, eq, n_days)
                if m:
                    m["strategy"] = "Supertrend"
                    m["params"]   = f"atr={atr_p} mult={mult:.1f}"
                    results.append(m)

            done += 1

    print(f"  Supertrend complete ({total} combos) — {len(results)} passing")
    return results


# ── Donchian (77 combos: entry 10-40 step 5 × exit 10-60 step 5) ───────────────
def run_donchian_grid(df):
    results = []
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days

    entry_ps = list(range(10, 45, 5))   # 7 values: 10,15,20,25,30,35,40
    exit_ps  = list(range(10, 65, 5))   # 11 values: 10,15,...,60

    h_ser = pd.Series(highs)
    l_ser = pd.Series(lows)
    entry_maxes = {ep: h_ser.shift(1).rolling(ep).max().values for ep in entry_ps}
    exit_mins   = {xp: l_ser.shift(1).rolling(xp).min().values for xp in exit_ps}

    total = len(entry_ps) * len(exit_ps)
    done  = 0
    for ep in entry_ps:
        entry_max = entry_maxes[ep]
        for xp in exit_ps:
            exit_min = exit_mins[xp]
            trades   = []
            in_pos   = False
            ei = epx = 0

            for i in range(1, N):
                if np.isnan(entry_max[i]) or np.isnan(exit_min[i]):
                    continue
                if not in_pos:
                    if closes[i] > entry_max[i]:
                        in_pos = True
                        ei, epx = i, closes[i]
                else:
                    if lows[i] <= exit_min[i]:
                        trades.append(dict(ei=ei, xi=i,
                                           ret=(exit_min[i] - epx) / epx))
                        in_pos = False

            if in_pos:
                trades.append(dict(ei=ei, xi=N - 1, ret=(closes[-1] - epx) / epx))

            if trades:
                eq = build_equity(trades, closes, N)
                m  = calc_metrics(trades, eq, n_days)
                if m:
                    m["strategy"] = "Donchian"
                    m["params"]   = f"en={ep} ex={xp}"
                    results.append(m)

            done += 1

    print(f"  Donchian complete ({total} combos) — {len(results)} passing")
    return results


# ── Keltner (44 combos: EMA 15-25 × mult 1.5-3.0 step 0.5) ─────────────────────
def run_keltner_grid(df):
    results = []
    closes = df["close"].values
    lows   = df["low"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days

    ema_ps = range(15, 26)         # 11 values
    mults  = [1.5, 2.0, 2.5, 3.0] # 4 values  → 44 total
    total  = 11 * 4
    done   = 0

    for ema_p in ema_ps:
        ema = pd.Series(closes).ewm(span=ema_p, adjust=False).mean().values
        atr = AverageTrueRange(df["high"], df["low"], df["close"],
                               window=ema_p).average_true_range().values

        for mult in mults:
            upper  = ema + mult * atr
            trades = []
            in_pos = False
            ei = epx = 0

            for i in range(1, N):
                if np.isnan(upper[i - 1]) or np.isnan(ema[i - 1]):
                    continue
                if not in_pos:
                    if closes[i] > upper[i - 1]:   # breakout above prior upper band
                        in_pos = True
                        ei, epx = i, closes[i]
                else:
                    if lows[i] <= ema[i - 1]:       # LOW breaches prior EMA (stop)
                        trades.append(dict(ei=ei, xi=i,
                                           ret=(ema[i - 1] - epx) / epx))
                        in_pos = False
                    elif closes[i] < ema[i]:         # close falls below current EMA
                        trades.append(dict(ei=ei, xi=i,
                                           ret=(closes[i] - epx) / epx))
                        in_pos = False

            if in_pos:
                trades.append(dict(ei=ei, xi=N - 1, ret=(closes[-1] - epx) / epx))

            if trades:
                eq = build_equity(trades, closes, N)
                m  = calc_metrics(trades, eq, n_days)
                if m:
                    m["strategy"] = "Keltner"
                    m["params"]   = f"ema={ema_p} mult={mult:.1f}"
                    results.append(m)

            done += 1

    print(f"  Keltner complete ({total} combos) — {len(results)} passing")
    return results


# ── Bollinger (55 combos: period 15-25 × std 1.5-2.5 step 0.25, fixed 15% stop) ─
def run_bollinger_grid(df):
    results = []
    closes = df["close"].values
    lows   = df["low"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days
    STOP   = 0.15   # fixed 15% stop from entry

    bb_ps  = range(15, 26)                     # 11 values
    bb_std = [1.5, 1.75, 2.0, 2.25, 2.5]       # 5 values  → 55 total
    total  = 11 * 5
    done   = 0

    cl = pd.Series(closes)
    for period in bb_ps:
        sma = cl.rolling(period).mean().values
        std = cl.rolling(period).std().values

        for nstd in bb_std:
            upper  = sma + nstd * std
            trades = []
            in_pos = False
            ei = epx = stop_lvl = 0

            for i in range(1, N):
                if np.isnan(upper[i - 1]) or np.isnan(sma[i]):
                    continue
                if not in_pos:
                    if closes[i] > upper[i - 1]:   # breakout above prior upper band
                        in_pos   = True
                        ei, epx  = i, closes[i]
                        stop_lvl = epx * (1 - STOP)
                else:
                    if lows[i] <= stop_lvl:         # fixed stop hit (bar-by-bar LOW)
                        trades.append(dict(ei=ei, xi=i,
                                           ret=(stop_lvl - epx) / epx))
                        in_pos = False
                    elif closes[i] < sma[i]:         # mean reversion exit at SMA
                        trades.append(dict(ei=ei, xi=i,
                                           ret=(closes[i] - epx) / epx))
                        in_pos = False

            if in_pos:
                trades.append(dict(ei=ei, xi=N - 1, ret=(closes[-1] - epx) / epx))

            if trades:
                eq = build_equity(trades, closes, N)
                m  = calc_metrics(trades, eq, n_days)
                if m:
                    m["strategy"] = "Bollinger"
                    m["params"]   = f"p={period} std={nstd:.2f}"
                    results.append(m)

            done += 1

    print(f"  Bollinger complete ({total} combos) — {len(results)} passing")
    return results


# ── Main ─────────────────────────────────────────────────────────────────────────
def main():
    print("Fetching SOLUSDT daily data from Binance...")
    df     = fetch_sol()
    closes = df["close"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days
    print(f"  {N} candles | {df.index[0].date()} → {df.index[-1].date()} | {n_days} days\n")

    bh = bh_benchmark(closes, n_days)

    print("Running ADX grid (1,232 combos)...")
    res  = run_adx_grid(df)

    print("\nRunning Supertrend grid (70 combos)...")
    res += run_supertrend_grid(df)

    print("\nRunning Donchian grid (77 combos)...")
    res += run_donchian_grid(df)

    print("\nRunning Keltner grid (44 combos)...")
    res += run_keltner_grid(df)

    print("\nRunning Bollinger grid (55 combos)...")
    res += run_bollinger_grid(df)

    df_r = pd.DataFrame(res).sort_values("annual_ret", ascending=False).reset_index(drop=True)
    out  = os.path.join(BASE_DIR, "sol_grid_results.csv")
    df_r.to_csv(out, index=False)

    SEP = "=" * 90
    print(f"\n{SEP}")
    print("SOL/USDT  Multi-Strategy Grid Search  —  Discovery Results")
    print(f"Data  : {df.index[0].date()} → {df.index[-1].date()}  |  {N} candles  |  {n_days} days")
    print(f"Filter: ≥{MIN_TRADES} trades, MDD > {MAX_MDD:.0%}  |  Total passing: {len(df_r)} / ~1,478")
    print(SEP)

    hdr = (f"{'#':<4}  {'Type':<12}  {'Parameters':<28}  "
           f"{'AnnRet':>7}  {'MDD':>7}  {'Sortino':>7}  {'PF':>6}  {'Win%':>5}  {'Trades':>6}")
    print(f"\n{hdr}")
    print("-" * 90)

    def fmtrow(row, rank):
        so = f"{row['sortino']:.2f}"  if pd.notna(row.get("sortino"))  else "    —"
        pf = f"{row['pf']:.3f}"       if pd.notna(row.get("pf"))       else "    —"
        wr = f"{row['win_rate']:.1%}" if pd.notna(row.get("win_rate")) else "   —"
        return (f"{rank:<4}  {row['strategy']:<12}  {row['params']:<28}  "
                f"{row['annual_ret']:>6.1%}  {row['mdd']:>6.1%}  {so:>7}  {pf:>6}  {wr:>5}  {int(row['trades']):>6}")

    so_bh = f"{bh['sortino']:.2f}" if pd.notna(bh["sortino"]) else "—"
    print(f"B&H   {'BUY_HOLD':<12}  {'SOLUSDT spot':<28}  "
          f"{bh['annual_ret']:>6.1%}  {bh['mdd']:>6.1%}  {so_bh:>7}  {'—':>6}  {'—':>5}  {'—':>6}")
    print("-" * 90)

    for rank, row in df_r.head(20).iterrows():
        print(fmtrow(row, rank + 1))

    # ── Breakdown by type ──────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("Breakdown by strategy type")
    print(SEP)
    type_order = df_r["strategy"].unique()
    for stype in type_order:
        sub  = df_r[df_r["strategy"] == stype]
        beat = sub[(sub["annual_ret"] > bh["annual_ret"]) & (sub["mdd"] > bh["mdd"])]
        best = sub.iloc[0]
        print(f"  {stype:<12}  passing={len(sub):>4}  beat_BH(ann+MDD)={len(beat):>4}  "
              f"best_ann={best['annual_ret']:>6.1%}  best_mdd={best['mdd']:>6.1%}  [{best['params']}]")

    # ── Q1: which type dominates top 20 ───────────────────────────────────────
    top20 = df_r.head(20)["strategy"].value_counts()
    print(f"\nQ1 — Which strategy type dominates the top 20?")
    for t, c in top20.items():
        print(f"  {t:<12}: {c:>2} entries")

    # ── Q2: beat B&H on both metrics ──────────────────────────────────────────
    beat_both = df_r[(df_r["annual_ret"] > bh["annual_ret"]) & (df_r["mdd"] > bh["mdd"])]
    print(f"\nQ2 — Strategies beating B&H on BOTH annual return AND MDD: "
          f"{len(beat_both)} / {len(df_r)} passing")
    if len(beat_both) > 0:
        for t, c in beat_both["strategy"].value_counts().items():
            print(f"  {t:<12}: {c}")

    print(f"\nCSV saved → {out}")
    print(SEP)


if __name__ == "__main__":
    main()
