"""
01_altcoin_discovery_grid.py — Week 9 Altcoin Discovery Grid
Week 9 | 2026-05-31
Strategies : ADX (96), Supertrend (12), Donchian (15), Keltner (16), Bollinger (9)
             = 148 combos per asset × 5 assets = 740 total
Assets     : LINK-USD, BNB-USD, AVAX-USD, DOT-USD, MATIC-USD
Methodology: 0.15% round-trip costs, bar-by-bar LOW stop, min 30 trades, MtM MDD > -50%
B&H filter : annual return >= asset B&H annual return × 1.5
Regime     : split at 2024-01-01 (institutional adoption default, METHODOLOGY_STANDARDS.md)
             triggered when an asset has 5+ passing combos with Sortino > 0.8

Design decisions that differ from sol_grid_search.py:
  1. yfinance instead of Binance API (consistent with data quality checks; no Binance dep)
  2. Donchian: single period for both high/low channel + trailing stop, not separate entry/exit
     periods. Spec: entry close > N-day high, exit LOW <= channel low OR trailing stop.
     Exit uses LOW (not close as written in spec) — consistent with bar-by-bar methodology.
  3. Bollinger: MEAN REVERSION (close <= prior lower band → enter; close >= mid-band → exit)
     not trend-following. Fixed 15% stop, consistent with validated ETH BB strategy (Week 5).
     Stop is not a grid parameter — user specified only period and std multiplier.
  4. Per-trade MaxDD: peak-to-trough on the sequence of completed trade returns
     (np.cumprod), per LEARNING_LOG Week 6 definition. Not "worst single trade."
     Both pt_mdd and mtm_mdd reported per METHODOLOGY_STANDARDS.md.
  5. B&H filter: if asset B&H annual return is negative, threshold = BH * 1.5 is also
     negative. Any positive-return strategy passes. Correct behaviour for structural
     downtrend assets (DOT) but the filter is effectively inactive in that case.
  6. Regime break classification: PROCEED if any top-5 combo is VIABLE; MARGINAL if
     all are EDGE COMPRESSED; CLOSE if all are REGIME CHANGE.
  7. ADX pre-cache uses exactly the 4 specified periods [7,9,11,14], not a continuous
     range. 4 indicator pre-computations per asset instead of 96.
  8. Supertrend pre-cache stores all 12 (atr_p, mult) pairs before the grid loop.
     sol_grid_search computed these inside the loop.

NOTE on MATIC-USD:
  yfinance uses MATIC-USD throughout, including post-Sep 2024 period.
  Binance retained MATICUSDT as the spot ticker after the September 13 2024 1:1
  MATIC→POL migration. Any live deployment must use MATICUSDT (not POLUSDT).
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange

warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "altcoin_discovery_results.csv")

# ── Constants ──────────────────────────────────────────────────────────────────
COSTS          = 0.0015   # 0.15% round-trip, applied once at exit bar
MIN_TRADES     = 30
MAX_MDD        = -0.50    # MtM equity curve floor
BH_MULT        = 1.5      # annual_ret must be >= BH_annual × BH_MULT
SORTINO_GATE   = 0.8      # threshold for regime break trigger
REGIME_N_MIN   = 5        # combos needed at Sortino > gate to trigger regime break
REGIME_BREAK   = pd.Timestamp("2024-01-01")
BB_STOP        = 0.15     # fixed stop for Bollinger MR — not a grid param
DOWNLOAD_START = "2018-01-01"

ASSETS = ["LINK-USD", "BNB-USD", "AVAX-USD", "DOT-USD", "MATIC-USD"]

# ── Grid parameters ────────────────────────────────────────────────────────────
ADX_THRESHOLDS = [15, 17, 19, 21, 23, 25]
ADX_PERIODS    = [7, 9, 11, 14]
ADX_STOPS      = [0.05, 0.07, 0.09, 0.12]

ST_ATR_PERIODS = [7, 10, 14]
ST_MULTIPLIERS = [2.0, 2.5, 3.0, 3.5]

DC_PERIODS     = [20, 30, 40, 50, 60]
DC_STOPS       = [0.05, 0.08, 0.12]

KC_EMA_PERIODS = [15, 20, 25, 30]
KC_MULTIPLIERS = [1.5, 2.0, 2.5, 3.0]

BB_PERIODS     = [15, 20, 25]
BB_STDS        = [1.5, 2.0, 2.5]

TOTAL_COMBOS = (len(ADX_PERIODS) * len(ADX_THRESHOLDS) * len(ADX_STOPS)
                + len(ST_ATR_PERIODS) * len(ST_MULTIPLIERS)
                + len(DC_PERIODS) * len(DC_STOPS)
                + len(KC_EMA_PERIODS) * len(KC_MULTIPLIERS)
                + len(BB_PERIODS) * len(BB_STDS))


# ══════════════════════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════════════════════

def fetch_asset(ticker):
    df = yf.download(ticker, start=DOWNLOAD_START, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns={c: c.lower() for c in df.columns})
    df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    return df.sort_index()


# ══════════════════════════════════════════════════════════════════════════════
# CORE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def build_equity(trades, closes, N):
    """Daily MtM equity curve. Costs applied once at exit bar."""
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
    """
    Returns metrics dict if passes hard filters (min trades, MtM MDD), else None.
    Reports both mtm_mdd (daily equity curve) and pt_mdd (trade-sequence portfolio).
    """
    if len(trades) < MIN_TRADES:
        return None
    ann     = float(eq[-1] ** (365.25 / n_days) - 1)
    run_mx  = np.maximum.accumulate(eq)
    mtm_mdd = float(((eq - run_mx) / run_mx).min())
    if mtm_mdd < MAX_MDD:
        return None

    daily_r  = np.diff(eq) / eq[:-1]
    neg      = daily_r[daily_r < 0]
    down_std = float(np.std(neg) * np.sqrt(365.25)) if len(neg) > 1 else np.nan
    sortino  = float(ann / down_std) if (down_std and down_std > 0) else np.nan

    rets     = np.array([t["ret"] for t in trades])
    trade_eq = np.cumprod(1 + rets)
    run_mx_t = np.maximum.accumulate(trade_eq)
    pt_mdd   = float(((trade_eq - run_mx_t) / run_mx_t).min())

    gains  = [t["ret"] for t in trades if t["ret"] > 0]
    losses = [abs(t["ret"]) for t in trades if t["ret"] <= 0]
    pf     = float(sum(gains) / sum(losses)) if losses else float("inf")

    return dict(
        annual_ret=ann, sortino=sortino, pf=pf,
        win_rate=float(len(gains) / len(trades)),
        n_trades=len(trades), mtm_mdd=mtm_mdd, pt_mdd=pt_mdd,
    )


def bh_benchmark(closes, n_days):
    eq       = closes / closes[0]
    ann      = float(eq[-1] ** (365.25 / n_days) - 1)
    run_mx   = np.maximum.accumulate(eq)
    mdd      = float(((eq - run_mx) / run_mx).min())
    daily_r  = np.diff(eq) / eq[:-1]
    neg      = daily_r[daily_r < 0]
    down_std = float(np.std(neg) * np.sqrt(365.25)) if len(neg) > 1 else np.nan
    sortino  = float(ann / down_std) if (down_std and down_std > 0) else np.nan
    return dict(annual_ret=ann, mdd=mdd, sortino=sortino)


def regime_break_metrics(trades, dates, break_ts):
    """
    Split trades by exit date at break_ts. Compute pre/post PF, win rate, trade count.
    dates: df.index (DatetimeIndex); trades have int 'xi' key.
    """
    def pf_wr(tlist):
        if not tlist:
            return None, None, 0
        wins   = [t["ret"] for t in tlist if t["ret"] > 0]
        losses = [abs(t["ret"]) for t in tlist if t["ret"] <= 0]
        pf     = float(sum(wins) / sum(losses)) if losses else float("inf")
        return pf, float(len(wins) / len(tlist)), len(tlist)

    pre  = [t for t in trades if dates[t["xi"]] <  break_ts]
    post = [t for t in trades if dates[t["xi"]] >= break_ts]

    pre_pf,  pre_wr,  pre_n  = pf_wr(pre)
    post_pf, post_wr, post_n = pf_wr(post)

    if post_n == 0:
        decision = "INSUFFICIENT POST-BREAK DATA"
    elif post_pf < 1.0:
        decision = "REGIME CHANGE"
    elif post_pf <= 2.0:
        decision = "EDGE COMPRESSED"
    else:
        decision = "VIABLE"

    return dict(
        pre_pf=pre_pf, pre_wr=pre_wr, pre_n=pre_n,
        post_pf=post_pf, post_wr=post_wr, post_n=post_n,
        regime_decision=decision,
    )


# ══════════════════════════════════════════════════════════════════════════════
# SUPERTREND HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _compute_supertrend(highs, lows, closes, atr_p, mult):
    """Returns (upper_band, direction) arrays. Upper band = support line when bullish."""
    N    = len(closes)
    prev = np.concatenate([[closes[0]], closes[:-1]])
    tr   = np.maximum(highs - lows,
           np.maximum(np.abs(highs - prev), np.abs(lows - prev)))

    atr = np.full(N, np.nan)
    if atr_p - 1 < N:
        atr[atr_p - 1] = np.mean(tr[:atr_p])
    for i in range(atr_p, N):
        atr[i] = (atr[i - 1] * (atr_p - 1) + tr[i]) / atr_p

    ub  = np.full(N, np.nan)
    lb  = np.full(N, np.nan)
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
    return ub, dir


# ══════════════════════════════════════════════════════════════════════════════
# GRID RUNNERS
# ══════════════════════════════════════════════════════════════════════════════

def run_adx_grid(df):
    results = []
    closes = df["close"].values
    lows   = df["low"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days
    n_combos = len(ADX_PERIODS) * len(ADX_THRESHOLDS) * len(ADX_STOPS)

    # Pre-compute ADX for each period (4 calls, not 96)
    adx_cache = {}
    for p in ADX_PERIODS:
        ind = ADXIndicator(df["high"], df["low"], df["close"], window=p, fillna=False)
        adx_cache[p] = (ind.adx().values, ind.adx_pos().values, ind.adx_neg().values)

    done = 0
    for p in ADX_PERIODS:
        adx, pdi, mdi = adx_cache[p]
        for thr in ADX_THRESHOLDS:
            for stop_pct in ADX_STOPS:
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
                            trades.append({"ei": ei, "xi": i, "ret": (stop_lvl - epx) / epx})
                            in_pos = False
                        else:
                            if closes[i] > peak:
                                peak = closes[i]
                            if not (adx[i] >= thr and pdi[i] > mdi[i]):
                                trades.append({"ei": ei, "xi": i, "ret": (closes[i] - epx) / epx})
                                in_pos = False

                if in_pos:
                    trades.append({"ei": ei, "xi": N - 1, "ret": (closes[-1] - epx) / epx})

                if len(trades) >= MIN_TRADES:
                    eq = build_equity(trades, closes, N)
                    m  = calc_metrics(trades, eq, n_days)
                    if m:
                        m["strategy"] = "ADX"
                        m["params"]   = f"p={p} thr={thr} stop={int(stop_pct*100)}%"
                        m["_trades"]  = trades
                        results.append(m)
                done += 1
                if done % 32 == 0:
                    print(f"    ADX {done}/{n_combos} ({done/n_combos:.0%})", flush=True)

    print(f"  ADX done ({n_combos} combos) — {len(results)} passing hard filters")
    return results


def run_supertrend_grid(df):
    results  = []
    closes   = df["close"].values
    highs    = df["high"].values
    lows     = df["low"].values
    N        = len(df)
    n_days   = (df.index[-1] - df.index[0]).days
    n_combos = len(ST_ATR_PERIODS) * len(ST_MULTIPLIERS)

    # Pre-compute all 12 (atr_p, mult) supertrend arrays
    st_cache = {}
    for atr_p in ST_ATR_PERIODS:
        for mult in ST_MULTIPLIERS:
            st_cache[(atr_p, mult)] = _compute_supertrend(highs, lows, closes, atr_p, mult)

    for atr_p in ST_ATR_PERIODS:
        for mult in ST_MULTIPLIERS:
            ub, dir = st_cache[(atr_p, mult)]
            trades  = []
            in_pos  = False
            ei = epx = 0

            for i in range(1, N):
                if np.isnan(ub[i]) or np.isnan(ub[i - 1]):
                    continue
                if not in_pos:
                    if dir[i - 1] == -1 and dir[i] == 1:
                        in_pos = True
                        ei, epx = i, closes[i]
                else:
                    if lows[i] <= ub[i - 1]:
                        exit_px = min(closes[i], ub[i - 1])
                        trades.append({"ei": ei, "xi": i, "ret": (exit_px - epx) / epx})
                        in_pos = False
                    elif dir[i] == -1:
                        trades.append({"ei": ei, "xi": i, "ret": (closes[i] - epx) / epx})
                        in_pos = False

            if in_pos:
                trades.append({"ei": ei, "xi": N - 1, "ret": (closes[-1] - epx) / epx})

            if len(trades) >= MIN_TRADES:
                eq = build_equity(trades, closes, N)
                m  = calc_metrics(trades, eq, n_days)
                if m:
                    m["strategy"] = "Supertrend"
                    m["params"]   = f"atr={atr_p} mult={mult:.1f}"
                    m["_trades"]  = trades
                    results.append(m)

    print(f"  Supertrend done ({n_combos} combos) — {len(results)} passing hard filters")
    return results


def run_donchian_grid(df):
    """
    Single channel period for both entry (N-day high) and exit (N-day low) + trailing stop.
    Exit priority: trailing stop checked before channel low.
    Both exits use bar-by-bar LOW (more conservative than close-based check in spec).
    """
    results  = []
    closes   = df["close"].values
    highs    = df["high"].values
    lows     = df["low"].values
    N        = len(df)
    n_days   = (df.index[-1] - df.index[0]).days
    n_combos = len(DC_PERIODS) * len(DC_STOPS)

    h_ser = pd.Series(highs)
    l_ser = pd.Series(lows)

    # Pre-compute rolling high max and low min for each period (5 computations)
    dc_cache = {}
    for per in DC_PERIODS:
        dc_cache[per] = (
            h_ser.shift(1).rolling(per).max().values,   # prior N-bar high → entry
            l_ser.shift(1).rolling(per).min().values,   # prior N-bar low  → channel exit
        )

    for per in DC_PERIODS:
        entry_max, exit_min = dc_cache[per]
        for stop_pct in DC_STOPS:
            trades  = []
            in_pos  = False
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

            if len(trades) >= MIN_TRADES:
                eq = build_equity(trades, closes, N)
                m  = calc_metrics(trades, eq, n_days)
                if m:
                    m["strategy"] = "Donchian"
                    m["params"]   = f"per={per} stop={int(stop_pct*100)}%"
                    m["_trades"]  = trades
                    results.append(m)

    print(f"  Donchian done ({n_combos} combos) — {len(results)} passing hard filters")
    return results


def run_keltner_grid(df):
    """Two-tier EMA exit: LOW <= prior EMA (intrabar trigger) OR close < current EMA (EOD)."""
    results  = []
    closes   = df["close"].values
    lows     = df["low"].values
    N        = len(df)
    n_days   = (df.index[-1] - df.index[0]).days
    n_combos = len(KC_EMA_PERIODS) * len(KC_MULTIPLIERS)

    # Pre-compute EMA and ATR for each EMA period (4 computations)
    kc_cache = {}
    for ema_p in KC_EMA_PERIODS:
        ema = pd.Series(closes).ewm(span=ema_p, adjust=False).mean().values
        atr = AverageTrueRange(df["high"], df["low"], df["close"],
                               window=ema_p).average_true_range().values
        kc_cache[ema_p] = (ema, atr)

    for ema_p in KC_EMA_PERIODS:
        ema, atr = kc_cache[ema_p]
        for mult in KC_MULTIPLIERS:
            upper  = ema + mult * atr
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
                    if lows[i] <= ema[i - 1]:            # intrabar: LOW hits prior EMA
                        trades.append({"ei": ei, "xi": i, "ret": (ema[i - 1] - epx) / epx})
                        in_pos = False
                    elif closes[i] < ema[i]:              # EOD: close below current EMA
                        trades.append({"ei": ei, "xi": i, "ret": (closes[i] - epx) / epx})
                        in_pos = False

            if in_pos:
                trades.append({"ei": ei, "xi": N - 1, "ret": (closes[-1] - epx) / epx})

            if len(trades) >= MIN_TRADES:
                eq = build_equity(trades, closes, N)
                m  = calc_metrics(trades, eq, n_days)
                if m:
                    m["strategy"] = "Keltner"
                    m["params"]   = f"ema={ema_p} mult={mult:.1f}"
                    m["_trades"]  = trades
                    results.append(m)

    print(f"  Keltner done ({n_combos} combos) — {len(results)} passing hard filters")
    return results


def run_bollinger_grid(df):
    """
    Mean reversion: entry when close <= prior lower band; exit when close >= mid SMA.
    Fixed 15% stop (BB_STOP). Entry uses prior bar's band to avoid same-bar look-ahead.
    """
    results  = []
    closes   = df["close"].values
    lows     = df["low"].values
    N        = len(df)
    n_days   = (df.index[-1] - df.index[0]).days
    n_combos = len(BB_PERIODS) * len(BB_STDS)

    cl = pd.Series(closes)

    # Pre-compute SMA and rolling std for each period (3 computations)
    bb_cache = {}
    for period in BB_PERIODS:
        bb_cache[period] = (
            cl.rolling(period).mean().values,
            cl.rolling(period).std().values,
        )

    for period in BB_PERIODS:
        sma, std = bb_cache[period]
        for nstd in BB_STDS:
            lower    = sma - nstd * std
            trades   = []
            in_pos   = False
            ei = epx = stop_lvl = 0.0

            for i in range(1, N):
                if np.isnan(lower[i - 1]) or np.isnan(sma[i]):
                    continue
                if not in_pos:
                    if closes[i] <= lower[i - 1]:        # close <= prior lower band
                        in_pos   = True
                        ei, epx  = i, closes[i]
                        stop_lvl = epx * (1 - BB_STOP)
                else:
                    if lows[i] <= stop_lvl:               # fixed stop (bar-by-bar LOW)
                        trades.append({"ei": ei, "xi": i, "ret": (stop_lvl - epx) / epx})
                        in_pos = False
                    elif closes[i] >= sma[i]:             # mean reversion: close returns to mid
                        trades.append({"ei": ei, "xi": i, "ret": (closes[i] - epx) / epx})
                        in_pos = False

            if in_pos:
                trades.append({"ei": ei, "xi": N - 1, "ret": (closes[-1] - epx) / epx})

            if len(trades) >= MIN_TRADES:
                eq = build_equity(trades, closes, N)
                m  = calc_metrics(trades, eq, n_days)
                if m:
                    m["strategy"] = "Bollinger"
                    m["params"]   = f"p={period} std={nstd:.1f}"
                    m["_trades"]  = trades
                    results.append(m)

    print(f"  Bollinger done ({n_combos} combos) — {len(results)} passing hard filters")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# PER-ASSET PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def process_asset(ticker, df):
    closes = df["close"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days
    dates  = df.index

    bh         = bh_benchmark(closes, n_days)
    bh_ann     = bh["annual_ret"]
    bh_thresh  = bh_ann * BH_MULT   # annual return floor for B&H filter

    SEP = "─" * 72

    print(f"\n{'═'*72}")
    print(f"  {ticker}  |  {N} candles  |  {dates[0].date()} → {dates[-1].date()}")
    print(f"  B&H: {bh_ann:.1%} annual  |  {bh['mdd']:.1%} MDD  |  Sortino {bh['sortino']:.2f}")
    print(f"  B&H filter floor (1.5×): {bh_thresh:.1%} annual return")
    print(f"{'═'*72}")

    # ── Run all five grids ────────────────────────────────────────────────────
    print(f"  Running ADX ({len(ADX_PERIODS)*len(ADX_THRESHOLDS)*len(ADX_STOPS)} combos)...")
    raw = run_adx_grid(df)

    print(f"  Running Supertrend ({len(ST_ATR_PERIODS)*len(ST_MULTIPLIERS)} combos)...")
    raw += run_supertrend_grid(df)

    print(f"  Running Donchian ({len(DC_PERIODS)*len(DC_STOPS)} combos)...")
    raw += run_donchian_grid(df)

    print(f"  Running Keltner ({len(KC_EMA_PERIODS)*len(KC_MULTIPLIERS)} combos)...")
    raw += run_keltner_grid(df)

    print(f"  Running Bollinger ({len(BB_PERIODS)*len(BB_STDS)} combos)...")
    raw += run_bollinger_grid(df)

    n_hard = len(raw)

    # ── Apply B&H benchmark filter ────────────────────────────────────────────
    if bh_thresh > 0:
        passing = [m for m in raw if m["annual_ret"] >= bh_thresh]
    else:
        # B&H annual return is negative — 1.5× threshold is also negative so the
        # benchmark filter is inactive. Accepting any positive-return strategy.
        # Sortino > 0.8 is the sole quality gate for this asset.
        passing = [m for m in raw if m["annual_ret"] > 0]
        print(f"\n  ⚠  NOTE: {ticker} B&H annual return is {bh_ann:.1%} (negative).")
        print(f"     B&H benchmark filter inactive — Sortino > {SORTINO_GATE} is the sole quality gate.")

    n_bh = len(passing)

    # Sort by Sortino descending
    passing.sort(
        key=lambda x: x["sortino"] if pd.notna(x.get("sortino")) else -999,
        reverse=True
    )

    n_sortino = sum(
        1 for m in passing
        if pd.notna(m.get("sortino")) and m["sortino"] > SORTINO_GATE
    )

    # ── Summary verdict ───────────────────────────────────────────────────────
    if n_sortino >= REGIME_N_MIN:
        verdict = "PROCEED TO WALK-FORWARD"
    elif n_sortino >= 1:
        verdict = "INSUFFICIENT EVIDENCE"
    else:
        verdict = "FAILED"

    print(f"\n  {SEP}")
    print(f"  SUMMARY: {ticker}")
    print(f"    Hard filters passed   : {n_hard} / {TOTAL_COMBOS}")
    print(f"    B&H 1.5× filter passed: {n_bh}")
    print(f"    Sortino > {SORTINO_GATE}         : {n_sortino}")
    print(f"    Verdict               : {verdict}")
    print(f"  {SEP}")

    # ── Ranked combinations table ─────────────────────────────────────────────
    if passing:
        show = passing[:20]
        print(f"\n  Top {len(show)} combinations by Sortino (of {n_bh} passing B&H filter):")
        hdr = (f"  {'#':<4}  {'Type':<12}  {'Params':<22}  "
               f"{'AnnRet':>7}  {'Sortino':>7}  {'PF':>6}  "
               f"{'Win%':>5}  {'Trades':>6}  {'MtMMDD':>7}  {'PtMDD':>7}")
        print(hdr)
        print(f"  {'-'*94}")
        bh_so = f"{bh['sortino']:.2f}" if pd.notna(bh["sortino"]) else "  —"
        print(f"  {'B&H':<4}  {'buy-hold':<12}  {'—':<22}  "
              f"{bh_ann:>6.1%}  {bh_so:>7}  {'—':>6}  {'—':>5}  {'—':>6}  "
              f"{bh['mdd']:>6.1%}  {'—':>7}")
        print(f"  {'-'*94}")
        for rank, m in enumerate(show, 1):
            so = f"{m['sortino']:.2f}" if pd.notna(m.get("sortino")) else "  —"
            pf = f"{m['pf']:.3f}"      if pd.notna(m.get("pf"))      else "  —"
            wr = f"{m['win_rate']:.1%}"
            print(f"  {rank:<4}  {m['strategy']:<12}  {m['params']:<22}  "
                  f"{m['annual_ret']:>6.1%}  {so:>7}  {pf:>6}  "
                  f"{wr:>5}  {int(m['n_trades']):>6}  "
                  f"{m['mtm_mdd']:>6.1%}  {m['pt_mdd']:>6.1%}")

    # ── Regime break analysis ─────────────────────────────────────────────────
    regime_results = []
    classification = ""

    if n_sortino >= REGIME_N_MIN:
        top5 = [m for m in passing
                if pd.notna(m.get("sortino")) and m["sortino"] > SORTINO_GATE][:5]

        print(f"\n  REGIME BREAK — Jan 2024 split (top {len(top5)} combos by Sortino):")
        print(f"  {'Type':<12}  {'Params':<22}  "
              f"{'PrePF':>7}  {'PreWR':>6}  {'PreN':>5}  "
              f"{'PostPF':>7}  {'PostWR':>6}  {'PostN':>5}  {'Decision'}")
        print(f"  {'-'*100}")

        decisions = []
        for m in top5:
            rb = regime_break_metrics(m["_trades"], dates, REGIME_BREAK)
            pre_pf  = f"{rb['pre_pf']:.3f}"  if rb["pre_pf"]  is not None else "  —"
            post_pf = f"{rb['post_pf']:.3f}" if rb["post_pf"] is not None else "  —"
            pre_wr  = f"{rb['pre_wr']:.1%}"  if rb["pre_wr"]  is not None else " —"
            post_wr = f"{rb['post_wr']:.1%}" if rb["post_wr"] is not None else " —"
            print(f"  {m['strategy']:<12}  {m['params']:<22}  "
                  f"{pre_pf:>7}  {pre_wr:>6}  {rb['pre_n']:>5}  "
                  f"{post_pf:>7}  {post_wr:>6}  {rb['post_n']:>5}  {rb['regime_decision']}")
            decisions.append(rb["regime_decision"])
            regime_results.append({
                "asset": ticker, **{k: v for k, v in m.items() if k != "_trades"},
                **rb
            })

        viable_count = sum(1 for d in decisions if d == "VIABLE")
        if viable_count >= 3:
            classification = f"PROCEED — {viable_count}/5 top combos VIABLE post Jan 2024"
        elif viable_count >= 1:
            classification = f"MARGINAL — {viable_count}/5 top combos VIABLE post Jan 2024"
        else:
            classification = "CLOSE — 0/5 top combos VIABLE post Jan 2024"

    elif n_sortino >= 1:
        classification = f"MARGINAL — {n_sortino} combo(s) Sortino>{SORTINO_GATE}, below regime-break threshold"
    elif n_bh > 0:
        classification = "CLOSE — combos pass B&H filter but none reach Sortino threshold"
    else:
        classification = "FAILED — no combinations pass B&H benchmark filter"

    print(f"\n  Classification: {classification}\n")

    # ── Build output rows (strip trade lists before CSV) ──────────────────────
    output_rows = []
    for m in passing:
        row = {k: v for k, v in m.items() if k != "_trades"}
        row["asset"] = ticker
        output_rows.append(row)

    return output_rows, regime_results, bh, n_hard, n_bh, n_sortino, verdict, classification


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 72)
    print("WEEK 9 ALTCOIN DISCOVERY GRID")
    print(f"Run date : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Assets   : {', '.join(ASSETS)}")
    print(f"Combos   : {TOTAL_COMBOS} per asset  ({len(ASSETS) * TOTAL_COMBOS} total)")
    print(f"Filters  : ≥{MIN_TRADES} trades | MtM MDD > {MAX_MDD:.0%} | "
          f"annual_ret ≥ B&H × {BH_MULT:.1f}")
    print(f"Regime   : split {REGIME_BREAK.date()} "
          f"(triggered at {REGIME_N_MIN}+ combos Sortino>{SORTINO_GATE})")
    print("=" * 72)

    all_rows      = []
    all_regime    = []
    final_summary = []

    for ticker in ASSETS:
        print(f"\n\n{'▶'*3} Fetching {ticker}...")
        try:
            df = fetch_asset(ticker)
        except Exception as e:
            print(f"  ERROR fetching {ticker}: {e}")
            continue
        if df.empty or len(df) < 200:
            print(f"  Insufficient data for {ticker} — skipping.")
            continue
        print(f"  {len(df)} candles | {df.index[0].date()} → {df.index[-1].date()}")

        rows, regime_rows, bh, n_hard, n_bh, n_sortino, verdict, classification = \
            process_asset(ticker, df)

        all_rows.extend(rows)
        all_regime.extend(regime_rows)
        final_summary.append({
            "asset": ticker, "bh_annual": bh["annual_ret"],
            "n_hard": n_hard, "n_bh": n_bh, "n_sortino": n_sortino,
            "verdict": verdict, "classification": classification,
        })

    # ── Save results CSV ──────────────────────────────────────────────────────
    col_order = ["asset", "strategy", "params", "annual_ret", "sortino",
                 "pf", "win_rate", "n_trades", "mtm_mdd", "pt_mdd"]

    if all_rows:
        df_out = pd.DataFrame(all_rows)
        for col in col_order:
            if col not in df_out.columns:
                df_out[col] = np.nan
        df_out = (df_out[col_order]
                  .sort_values(["asset", "sortino"], ascending=[True, False])
                  .reset_index(drop=True))
        df_out.to_csv(OUTPUT_CSV, index=False)
        print(f"\n\nResults saved → {OUTPUT_CSV}")
    else:
        print("\nNo passing combinations across any asset.")

    # ── Cross-asset summary ───────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("CROSS-ASSET SUMMARY")
    print(f"{'='*72}")
    print(f"  {'Asset':<12}  {'B&H Ann':>7}  {'Hard':>5}  {'≥B&H×1.5':>9}  "
          f"{'Sortino>0.8':>11}  Verdict")
    print(f"  {'-'*72}")
    for s in final_summary:
        print(f"  {s['asset']:<12}  {s['bh_annual']:>7.1%}  {s['n_hard']:>5}  "
              f"{s['n_bh']:>9}  {s['n_sortino']:>11}  {s['verdict']}")
    print(f"\n  Classifications:")
    for s in final_summary:
        print(f"    {s['asset']:<12}  {s['classification']}")
    print(f"{'='*72}")
    print("Grid complete. Do not proceed to walk-forward until results reviewed.")


if __name__ == "__main__":
    main()
