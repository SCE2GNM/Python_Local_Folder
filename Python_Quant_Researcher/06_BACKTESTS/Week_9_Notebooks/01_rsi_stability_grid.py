"""
01_rsi_stability_grid.py — ETH RSI mean reversion stability analysis
Week 9  |  RR-RSI-006

Grid  : RSI period 10–18  ×  threshold 41–45  ×  SMA period 90–150 step 10
        315 combinations total
Deployed: RSI=14  threshold=43  SMA=120  (marked *** DEPLOYED *** in output)

Strategy:
  Entry : RSI < threshold  AND  close > SMA  (signal evaluated at bar close)
  Exit  : RSI > EXIT_RSI at close  OR  stop hit (bar LOW ≤ stop price)
  Stop  : 15% fixed below entry price, checked bar-by-bar against daily LOW
  Costs : 0.15% round-trip per trade, applied at exit

DOCUMENTATION GAP (log for RISK_REGISTER_ETH_RSI.md):
  The RR-RSI-006 stability analysis spec said EXIT_RSI=60.
  The deployed bot (rsi_production_bot.py line 77) uses EXIT_RSI=48.
  These are different strategies. This script uses EXIT_RSI=48 to test
  the actual live parameters. The spec discrepancy should be resolved —
  either update the spec to 48 or document why 60 was intended.
"""

import os
import itertools
import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Config ────────────────────────────────────────────────────────────────────
COSTS      = 0.0015           # 0.15% round-trip per trade
STOP_PCT   = 0.15             # 15% fixed stop below entry price
EXIT_RSI   = 48               # matches deployed bot (rsi_production_bot.py:77)
                              # NOTE: RR-RSI-006 spec said 60 — see DOCUMENTATION GAP above
START_DATE = "2018-01-01"
DEPLOYED   = (14, 43, 120)    # (rsi_period, threshold, sma_period)

RSI_PERIODS  = list(range(10, 19))       # 9 values: 10 11 12 13 14 15 16 17 18
THRESHOLDS   = list(range(41, 46))       # 5 values: 41 42 43 44 45
SMA_PERIODS  = list(range(90, 151, 10))  # 7 values: 90 100 110 120 130 140 150

OUTPUT_CSV = os.path.join(BASE_DIR, "rsi_stability_results.csv")


# ── Data ──────────────────────────────────────────────────────────────────────
def fetch_eth():
    """
    Fetch ETH-USD daily via yfinance — same source as day5_rsi_final.py
    and rsi_production_bot.py. Confirmed: 2022-06-01 close = $1,823.57.
    auto_adjust has no effect on ETH (no dividends/splits).
    """
    import warnings
    warnings.filterwarnings('ignore')
    raw = yf.download('ETH-USD', start=START_DATE, interval='1d',
                      auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)
    df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df.dropna(inplace=True)
    df.columns = [c.lower() for c in df.columns]
    return df


# ── Indicators ────────────────────────────────────────────────────────────────
def precompute_indicators(df):
    """
    Compute all RSI and SMA series once. Returns dicts {period: np.array}.
    Uses ta.momentum.RSIIndicator — same implementation as deployed bot.
    """
    closes    = df["close"]
    rsi_cache = {p: RSIIndicator(close=closes, window=p).rsi().values
                 for p in RSI_PERIODS}
    sma_cache = {p: closes.rolling(p).mean().values
                 for p in SMA_PERIODS}
    return rsi_cache, sma_cache


# ── Single backtest ───────────────────────────────────────────────────────────
def run_backtest(closes, lows, rsi_vals, sma_vals, threshold, n_days):
    """
    RSI mean reversion backtest on pre-computed indicator arrays.

    Entry: signal fires on bar i close when RSI[i] < threshold AND
           close[i] > sma[i]. Entry price = close[i].

    Exit priority:
      1. Stop: if low[i] <= stop_price, exit at stop_price (intraday fill).
      2. RSI:  if rsi[i] > EXIT_RSI at close, exit at close[i].

    Returns metrics dict, or None if fewer than 5 trades.
    """
    N          = len(closes)
    equity     = np.ones(N)   # daily equity curve, starts at 1.0
    trade_rets = []
    in_pos     = False
    entry_bar  = 0
    entry_px   = 0.0
    stop_px    = 0.0

    for i in range(1, N):
        if np.isnan(rsi_vals[i]) or np.isnan(sma_vals[i]):
            equity[i] = equity[i - 1]
            continue

        if not in_pos:
            equity[i] = equity[i - 1]               # carry forward when flat
            if rsi_vals[i] < threshold and closes[i] > sma_vals[i]:
                in_pos    = True
                entry_bar = i
                entry_px  = closes[i]
                stop_px   = entry_px * (1.0 - STOP_PCT)

        else:
            # 1. Stop — bar-by-bar using daily LOW
            if lows[i] <= stop_px:
                ret       = (stop_px / entry_px - 1.0) - COSTS
                equity[i] = equity[entry_bar] * (1.0 + ret)
                trade_rets.append(ret)
                in_pos    = False

            # 2. RSI exit at close
            elif rsi_vals[i] > EXIT_RSI:
                ret       = (closes[i] / entry_px - 1.0) - COSTS
                equity[i] = equity[entry_bar] * (1.0 + ret)
                trade_rets.append(ret)
                in_pos    = False

            else:
                # MtM while in position
                equity[i] = equity[entry_bar] * (closes[i] / entry_px)

    # Close any open position at the final bar
    if in_pos:
        ret        = (closes[-1] / entry_px - 1.0) - COSTS
        equity[-1] = equity[entry_bar] * (1.0 + ret)
        trade_rets.append(ret)

    if len(trade_rets) < 5:
        return None

    rets   = np.array(trade_rets)
    wins   = rets[rets > 0]
    losses = rets[rets <= 0]

    pf = (float(wins.sum() / abs(losses.sum()))
          if len(losses) > 0 and losses.sum() != 0 else np.nan)
    wr = float(len(wins) / len(rets))
    n  = len(rets)

    ann_ret = float(equity[-1] ** (365.25 / n_days) - 1) if n_days > 0 else np.nan

    # MtM MaxDD — daily equity curve
    peak    = np.maximum.accumulate(equity)
    mtm_mdd = float(((equity - peak) / peak).min())

    # Per-trade MaxDD — worst single trade loss
    per_trade_mdd = float(rets.min())

    # Sortino — daily equity curve method (not per-trade annualisation)
    daily_rets = np.diff(equity) / equity[:-1]
    daily_rets = daily_rets[~np.isnan(daily_rets)]
    ann_mean   = float(daily_rets.mean()) * 252
    downside   = daily_rets[daily_rets < 0]
    if len(downside) > 1:
        ds_std  = float(np.std(downside, ddof=1)) * np.sqrt(252)
        sortino = ann_mean / ds_std if ds_std > 0 else np.nan
    else:
        sortino = np.nan

    return dict(
        pf            = round(pf, 3)             if not np.isnan(pf)      else np.nan,
        win_rate      = round(wr, 4),
        n_trades      = n,
        ann_ret       = round(ann_ret, 4)        if not np.isnan(ann_ret) else np.nan,
        sortino       = round(float(sortino), 3) if not np.isnan(sortino) else np.nan,
        per_trade_mdd = round(per_trade_mdd, 4),
        mtm_mdd       = round(mtm_mdd, 4),
    )


# ── Output helpers ────────────────────────────────────────────────────────────
def _fp(v):
    """Format value as percentage with sign, or — for NaN."""
    return "—" if (v != v) else f"{v:+.1%}"

def _ff(v, d=3):
    """Format value as float, or — for NaN."""
    return "—" if (v != v) else f"{v:.{d}f}"

HDR = (f"  {'RSI':>4} {'Thr':>4} {'SMA':>4}  "
       f"{'PF':>6}  {'WR%':>6}  {'N':>4}  "
       f"{'Ann%':>7}  {'Sortino':>7}  {'PT-MDD':>8}  {'MtM-MDD':>8}")

def _print_row(r):
    print(
        f"  {int(r['rsi_period']):>4} {int(r['threshold']):>4} {int(r['sma_period']):>4}  "
        f"{_ff(r['pf']):>6}  {_fp(r['win_rate']):>6}  {int(r['n_trades']):>4}  "
        f"{_fp(r['ann_ret']):>7}  {_ff(r['sortino']):>7}  "
        f"{_fp(r['per_trade_mdd']):>8}  {_fp(r['mtm_mdd']):>8}  "
        f"{r['deployed']}"
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Fetching ETHUSDT daily data...")
    df     = fetch_eth()
    n_days = (df.index[-1] - df.index[0]).days
    closes = df["close"].values
    lows   = df["low"].values
    print(f"  {len(df)} candles | {df.index[0].date()} → {df.index[-1].date()}\n")

    print("Pre-computing indicators...")
    rsi_cache, sma_cache = precompute_indicators(df)

    combos = list(itertools.product(RSI_PERIODS, THRESHOLDS, SMA_PERIODS))
    assert len(combos) == 315, f"Expected 315 combos, got {len(combos)}"
    print(f"Running {len(combos)} combinations...\n")

    rows = []
    for idx, (rsi_p, thresh, sma_p) in enumerate(combos, 1):
        if idx % 100 == 0 or idx == len(combos):
            print(f"  {idx}/{len(combos)}")

        m = run_backtest(
            closes, lows,
            rsi_cache[rsi_p], sma_cache[sma_p],
            threshold=thresh,
            n_days=n_days,
        )

        if m is None:
            m = dict(pf=np.nan, win_rate=np.nan, n_trades=0,
                     ann_ret=np.nan, sortino=np.nan,
                     per_trade_mdd=np.nan, mtm_mdd=np.nan)

        rows.append(dict(
            rsi_period    = rsi_p,
            threshold     = thresh,
            sma_period    = sma_p,
            deployed      = "*** DEPLOYED ***" if (rsi_p, thresh, sma_p) == DEPLOYED else "",
            **m,
        ))

    df_res = (pd.DataFrame(rows)
              .sort_values("pf", ascending=False, na_position="last")
              .reset_index(drop=True))
    df_res.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved → {OUTPUT_CSV}\n")

    # ── Console report ────────────────────────────────────────────────────────
    SEP  = "=" * 98
    SEP2 = "─" * 98

    print(SEP)
    print(f"ETH RSI Mean Reversion — Stability Analysis  (RR-RSI-006)")
    print(f"Data  : ETHUSDT daily  {df.index[0].date()} → {df.index[-1].date()}")
    print(f"Config: EXIT_RSI={EXIT_RSI}  stop={STOP_PCT:.0%}  costs={COSTS*100:.2f}%"
          f"  |  matches deployed bot (spec said 60 — see doc gap)")
    print(f"Grid  : {len(combos)} combinations  "
          f"(RSI 10–18 × threshold 41–45 × SMA 90–150 step 10)")
    print(SEP)

    # ── Deployed params ───────────────────────────────────────────────────────
    dep_rows = df_res[df_res["deployed"] == "*** DEPLOYED ***"]
    valid_n  = int(df_res["pf"].notna().sum())
    dep_rank = int(dep_rows.index[0]) + 1 if not dep_rows.empty else None

    print(f"\n{'*' * 60}")
    print(f"  DEPLOYED PARAMETERS: RSI={DEPLOYED[0]}  threshold={DEPLOYED[1]}  SMA={DEPLOYED[2]}")
    print(f"{'*' * 60}")
    if not dep_rows.empty:
        r = dep_rows.iloc[0]
        print(f"  Rank         : {dep_rank} / {valid_n}")
        print(f"  Profit Factor: {_ff(r['pf'])}")
        print(f"  Win Rate     : {_fp(r['win_rate'])}")
        print(f"  Trades       : {int(r['n_trades'])}")
        print(f"  Annual Return: {_fp(r['ann_ret'])}")
        print(f"  Sortino      : {_ff(r['sortino'])}")
        print(f"  Per-trade MDD: {_fp(r['per_trade_mdd'])}")
        print(f"  MtM MaxDD    : {_fp(r['mtm_mdd'])}")

    # ── Neighbourhood: ±1 step on each axis around deployed ──────────────────
    d_rsi, d_thr, d_sma = DEPLOYED
    nbr = df_res[
        df_res["rsi_period"].between(d_rsi - 1, d_rsi + 1) &
        df_res["threshold"].between(d_thr - 1, d_thr + 1) &
        df_res["sma_period"].between(d_sma - 10, d_sma + 10)
    ]
    nbr_valid = int(nbr["pf"].notna().sum())
    nbr_pos   = int((nbr["pf"] > 1.0).sum())

    print(f"\n{SEP2}")
    print(f"Neighbourhood  (±1 RSI period, ±1 threshold, ±10 SMA  —  "
          f"{len(nbr)} combos, deployed at centre)")
    print(HDR)
    print(f"  {'-' * 93}")
    for _, r in nbr.sort_values("pf", ascending=False).iterrows():
        _print_row(r)

    # ── Top 20 by profit factor ───────────────────────────────────────────────
    print(f"\n{SEP2}")
    print("Top 20 by Profit Factor")
    print(HDR)
    print(f"  {'-' * 93}")
    for _, r in df_res.head(20).iterrows():
        _print_row(r)

    # ── Stability classification ──────────────────────────────────────────────
    n_pos   = int((df_res["pf"] > 1.0).sum())
    n_15    = int((df_res["pf"] >= 1.5).sum())
    n_20    = int((df_res["pf"] >= 2.0).sum())
    pct_pos = n_pos / valid_n if valid_n > 0 else 0.0

    if pct_pos >= 0.50:
        classification = "STABLE"
    elif pct_pos >= 0.25:
        classification = "MARGINAL"
    else:
        classification = "FRAGILE"

    print(f"\n{SEP2}")
    print(f"Stability Classification: {classification}")
    print(f"  Valid combinations  : {valid_n} / {len(combos)}")
    print(f"  PF > 1.0 (profitable): {n_pos:>4}  ({pct_pos:.1%} of valid)")
    print(f"  PF >= 1.5            : {n_15:>4}  ({n_15/valid_n:.1%} of valid)")
    print(f"  PF >= 2.0            : {n_20:>4}  ({n_20/valid_n:.1%} of valid)")
    print(f"  Neighbourhood PF>1.0 : {nbr_pos:>4} / {nbr_valid}  "
          f"({nbr_pos/nbr_valid:.1%} of neighbourhood)" if nbr_valid > 0 else "")
    print(f"  Deployed rank        : {dep_rank} / {valid_n}")
    print(SEP)


if __name__ == "__main__":
    main()
