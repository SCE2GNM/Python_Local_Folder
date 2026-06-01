"""
05_bnb_validation_pipeline.py — BNB Donchian Full Validation Pipeline
Week 9 | 2026-06-01

Strategy under validation: BNB Donchian period=20, stop=5%
(post-break PF 2.199, regime break VIABLE, walk-forward 9/13 windows profitable)

Four analyses in order:

Analysis 1 — Grid boundary extension
  Stop range: 3%–15% (9 values), period=20 fixed.
  Confirms whether stop=5% sits on a plateau or a cliff edge.

Analysis 2 — Stability grid + heatmaps
  Joint grid: period [15,17,19,20,21,23,25] × stop [3%,4%,5%,6%,7%,8%]
  Metric: post-break PF (Jan 2024 split) — the correct forward-looking measure.
  Classification: STABLE ≥50% combos with post-break PF>2.0 | MARGINAL 25–49% | FRAGILE <25%
  Outputs: three PNG heatmaps (post-break PF, full-period Sortino, full-period annual return)
           bnb_stability_results.csv

Analysis 3 — Exit method comparison (period=20 fixed)
  Exit A (current): 5% trailing stop + 20-day channel low exit
  Exit B: ATR14 trailing stop (peak − 2.0×ATR14, ratchet up only, LOW exit)
  Exit C: EMA-20 two-tier stop (LOW ≤ prior EMA = intrabar; close < current EMA = EOD)
  Metrics: full-period PF, post-break PF, WR, n_trades, ann_ret, Sortino, MtM MDD, PT MDD

Analysis 4 — Regime filter test on best exit from Analysis 3
  Entry gate: only enter when close > SMA on signal bar
  Filters: None (baseline) | SMA-50 | SMA-100 | SMA-120
  Metrics: full-period and post-break for each

Outputs: bnb_exit_regime_results.csv, bnb_heatmap_postbreak_pf.png,
         bnb_heatmap_sortino.png, bnb_heatmap_annual_return.png
"""

import importlib.util
import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import seaborn as sns
from ta.volatility import AverageTrueRange

warnings.filterwarnings("ignore")

# ── Load grid module (digit-prefixed filename) ────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "altcoin_grid", os.path.join(BASE, "01_altcoin_discovery_grid.py")
)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

TICKER   = "BNB-USD"
BREAK_TS = pd.Timestamp("2024-01-01")
COSTS    = g.COSTS

# Deployed parameters
D_PERIOD   = 20
D_STOP_PCT = 0.05

# Analysis 1
A1_STOPS = [0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.15]

# Analysis 2
A2_PERIODS = [15, 17, 19, 20, 21, 23, 25]
A2_STOPS   = [0.03, 0.04, 0.05, 0.06, 0.07, 0.08]

OUTPUT_STABILITY  = os.path.join(BASE, "bnb_stability_results.csv")
OUTPUT_EXIT_SMA   = os.path.join(BASE, "bnb_exit_regime_results.csv")
PNG_POSTBREAK_PF  = os.path.join(BASE, "bnb_heatmap_postbreak_pf.png")
PNG_SORTINO       = os.path.join(BASE, "bnb_heatmap_sortino.png")
PNG_ANNUAL_RET    = os.path.join(BASE, "bnb_heatmap_annual_return.png")


# ══════════════════════════════════════════════════════════════════════════════
# METRICS HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def full_metrics(trades, eq, n_days):
    """Full-period metrics dict. Returns None if hard filters fail."""
    m = g.calc_metrics(trades, eq, n_days)
    return m


def post_break_pf_wr_n(trades, dates):
    """Post-Jan-2024 PF, win rate, and trade count."""
    post = [t for t in trades if dates[t["xi"]] >= BREAK_TS]
    if not post:
        return None, None, 0
    wins   = [t["ret"] for t in post if t["ret"] > 0]
    losses = [abs(t["ret"]) for t in post if t["ret"] <= 0]
    pf     = float(sum(wins) / sum(losses)) if losses else float("inf")
    wr     = float(len(wins) / len(post))
    return pf, wr, len(post)


def post_break_ann_ret(eq, df):
    """Annual return for the post-break period from equity curve slice."""
    dates     = df.index
    N         = len(df)
    break_idx = min(int(dates.searchsorted(BREAK_TS, side="left")), N - 1)
    post_days = max((dates[-1] - dates[break_idx]).days, 1)
    return float((eq[-1] / eq[break_idx]) ** (365.25 / post_days) - 1)


# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED DONCHIAN RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_donchian(df, period, stop_pct=0.05, exit_method="A",
                 sma_period=None, atr_mult=2.0, atr_period=14, ema_exit_period=20):
    """
    Unified Donchian runner.

    Entry: close > prior N-day rolling high (+ optional close > SMA filter)

    Exit A (current): trailing stop (stop_pct from peak) checked first;
                      then LOW ≤ prior N-day rolling low of lows.
    Exit B: ATR trailing stop. stop_level = peak − atr_mult×ATR[atr_period].
            Ratchets upward only. Exit when LOW ≤ stop_level.
    Exit C: EMA two-tier stop. Tier 1: LOW ≤ prior bar EMA (intrabar, fill at EMA).
            Tier 2: close < current EMA (EOD, fill at close). Check tier 1 first.
    """
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    N      = len(df)
    n_days = (df.index[-1] - df.index[0]).days

    h_ser     = pd.Series(highs)
    l_ser     = pd.Series(lows)
    entry_max = h_ser.shift(1).rolling(period).max().values
    exit_min  = l_ser.shift(1).rolling(period).min().values if exit_method == "A" else None

    sma_vals = (pd.Series(closes).rolling(sma_period).mean().values
                if sma_period else None)

    if exit_method == "B":
        atr_vals = AverageTrueRange(df["high"], df["low"], df["close"],
                                    window=atr_period).average_true_range().values
    elif exit_method == "C":
        ema_vals = pd.Series(closes).ewm(span=ema_exit_period, adjust=False).mean().values

    trades    = []
    in_pos    = False
    ei        = 0
    epx       = 0.0
    peak      = 0.0
    stop_lvl  = 0.0

    for i in range(1, N):
        if np.isnan(entry_max[i]):
            continue

        # ── Entry ────────────────────────────────────────────────────────────
        if not in_pos:
            sma_ok = (sma_vals is None or
                      (not np.isnan(sma_vals[i]) and closes[i] > sma_vals[i]))
            if closes[i] > entry_max[i] and sma_ok:
                if exit_method == "B" and np.isnan(atr_vals[i]):
                    continue
                if exit_method == "C" and np.isnan(ema_vals[i - 1]):
                    continue
                in_pos = True
                ei, epx, peak = i, closes[i], closes[i]
                if exit_method == "A":
                    stop_lvl = peak * (1 - stop_pct)
                elif exit_method == "B":
                    stop_lvl = peak - atr_mult * atr_vals[i]

        # ── Exit ─────────────────────────────────────────────────────────────
        else:
            exited = False

            if exit_method == "A":
                stop_lvl = peak * (1 - stop_pct)          # trailing: recompute from peak
                if lows[i] <= stop_lvl:
                    trades.append({"ei": ei, "xi": i, "ret": (stop_lvl - epx) / epx})
                    exited = True
                elif exit_min is not None and not np.isnan(exit_min[i]) and lows[i] <= exit_min[i]:
                    trades.append({"ei": ei, "xi": i, "ret": (exit_min[i] - epx) / epx})
                    exited = True
                else:
                    if closes[i] > peak:
                        peak = closes[i]

            elif exit_method == "B":
                if lows[i] <= stop_lvl:
                    trades.append({"ei": ei, "xi": i, "ret": (stop_lvl - epx) / epx})
                    exited = True
                else:
                    if closes[i] > peak:
                        peak = closes[i]
                    if not np.isnan(atr_vals[i]):
                        new_stop = peak - atr_mult * atr_vals[i]
                        stop_lvl = max(stop_lvl, new_stop)   # ratchet up only

            elif exit_method == "C":
                if np.isnan(ema_vals[i - 1]) or np.isnan(ema_vals[i]):
                    continue
                if lows[i] <= ema_vals[i - 1]:              # tier 1: intrabar
                    trades.append({"ei": ei, "xi": i, "ret": (ema_vals[i - 1] - epx) / epx})
                    exited = True
                elif closes[i] < ema_vals[i]:               # tier 2: EOD close
                    trades.append({"ei": ei, "xi": i, "ret": (closes[i] - epx) / epx})
                    exited = True

            if exited:
                in_pos = False

    if in_pos:
        trades.append({"ei": ei, "xi": N - 1, "ret": (closes[-1] - epx) / epx})

    eq = g.build_equity(trades, closes, N)
    return trades, eq, n_days


def metrics_row(label, trades, eq, df, n_days):
    """Build a complete metrics dict for display and CSV output."""
    m      = full_metrics(trades, eq, n_days) or {}
    pb_pf, pb_wr, pb_n = post_break_pf_wr_n(trades, df.index)
    pb_ann = post_break_ann_ret(eq, df)
    return dict(
        label      = label,
        full_pf    = m.get("pf"),
        full_wr    = m.get("win_rate"),
        n_trades   = m.get("n_trades", len(trades)),
        ann_ret    = m.get("annual_ret"),
        sortino    = m.get("sortino"),
        mtm_mdd    = m.get("mtm_mdd"),
        pt_mdd     = m.get("pt_mdd"),
        post_pf    = pb_pf,
        post_wr    = pb_wr,
        post_n     = pb_n,
        post_ann   = pb_ann,
    )


# ══════════════════════════════════════════════════════════════════════════════
# HEATMAP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def save_heatmap(pivot, title, filepath, center, vmin, vmax,
                 fmt=".2f", deployed_period=20, deployed_stop=0.05):
    """Save a diverging heatmap with a marker on the deployed combination."""
    fig, ax = plt.subplots(figsize=(10, 7))

    # Replace inf with a large finite number for colour scaling
    display = pivot.copy().replace([np.inf, -np.inf], np.nan)

    # Clamp vmin/vmax to data range if needed
    data_min = float(np.nanmin(display.values))
    data_max = float(np.nanmax(display.values))
    vmin = min(vmin, data_min)
    vmax = max(vmax, data_max)
    center = min(max(center, vmin), vmax)

    norm = mcolors.TwoSlopeNorm(vmin=vmin, vcenter=center, vmax=vmax)
    cmap = plt.cm.RdYlGn

    sns.heatmap(
        display,
        annot=True,
        fmt=fmt,
        cmap=cmap,
        norm=norm,
        ax=ax,
        linewidths=0.5,
        linecolor="white",
        cbar_kws={"shrink": 0.8},
    )

    # Mark deployed combination with a blue rectangle
    try:
        row_idx = list(pivot.index).index(deployed_period)
        col_idx = list(pivot.columns).index(deployed_stop)
        rect = mpatches.FancyBboxPatch(
            (col_idx, row_idx), 1, 1,
            boxstyle="square,pad=0",
            linewidth=3, edgecolor="blue", facecolor="none",
            transform=ax.transData,
        )
        ax.add_patch(rect)
        ax.text(col_idx + 0.5, row_idx + 0.92, "★",
                ha="center", va="center", fontsize=10, color="blue",
                transform=ax.transData)
    except ValueError:
        pass   # deployed params not in this grid — skip marker

    # Format axis tick labels
    ax.set_xticklabels([f"{v:.0%}" for v in pivot.columns], rotation=0)
    ax.set_yticklabels(pivot.index, rotation=0)
    ax.set_xlabel("Stop %", fontsize=11)
    ax.set_ylabel("Donchian Period", fontsize=11)
    ax.set_title(title + "\n(★ = deployed: period=20, stop=5%)", fontsize=12)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {os.path.basename(filepath)}")


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def f_pf(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "    —"
    if np.isinf(v):                                         return "  ∞"
    return f"{v:.3f}"

def f_pct(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "   —"
    return f"{v:+.1%}"

def f_so(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "   —"
    return f"{v:.2f}"


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 1 — GRID BOUNDARY EXTENSION
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis_1(df):
    SEP = "═" * 80
    print(f"\n{SEP}")
    print("ANALYSIS 1 — GRID BOUNDARY EXTENSION")
    print(f"Period=20 fixed | Stop range: {[int(s*100) for s in A1_STOPS]}%")
    print(f"Checking whether stop=5% is a plateau or a cliff edge")
    print(SEP)

    n_days = (df.index[-1] - df.index[0]).days
    rows   = []

    hdr = (f"  {'Stop':>6}  {'Trades':>6}  {'AnnRet':>7}  {'Sortino':>7}  "
           f"{'PF':>7}  {'MtMMDD':>7}  {'Note'}")
    print(hdr)
    print(f"  {'-'*72}")

    for stop_pct in A1_STOPS:
        trades, eq, _ = run_donchian(df, D_PERIOD, stop_pct=stop_pct, exit_method="A")
        m = full_metrics(trades, eq, n_days)
        if m:
            flag = "  ← DEPLOYED" if stop_pct == D_STOP_PCT else ""
            print(f"  {int(stop_pct*100):>5}%  {m['n_trades']:>6}  "
                  f"{f_pct(m['annual_ret']):>7}  {f_so(m['sortino']):>7}  "
                  f"{f_pf(m['pf']):>7}  {f_pct(m['mtm_mdd']):>7}  {flag}")
        else:
            print(f"  {int(stop_pct*100):>5}%  — insufficient trades")

        rows.append({"stop_pct": stop_pct,
                     "n_trades": m["n_trades"] if m else None,
                     "ann_ret":  m["annual_ret"] if m else None,
                     "sortino":  m["sortino"]    if m else None,
                     "pf":       m["pf"]         if m else None,
                     "mtm_mdd":  m["mtm_mdd"]    if m else None})

    # Cliff-edge assessment
    valid = [(r["stop_pct"], r["pf"]) for r in rows if r["pf"] is not None and not np.isinf(r["pf"])]
    if len(valid) >= 3:
        pf_vals = [v[1] for v in valid]
        pf_min  = min(pf_vals)
        pf_max  = max(pf_vals)
        pf_range_pct = (pf_max - pf_min) / pf_max if pf_max > 0 else 0

        print(f"\n  Cliff-edge assessment (PF range: {pf_min:.3f} – {pf_max:.3f}):")
        if pf_range_pct < 0.30:
            assessment = "PLATEAU — PF varies less than 30% across range. stop=5% is not cherry-picked."
        elif pf_range_pct < 0.60:
            assessment = "MODERATE SENSITIVITY — some variation. Review whether 5% is near a local peak."
        else:
            assessment = "HIGH SENSITIVITY — large PF variation across stops. Overfitting risk. Investigate."
        print(f"  → {assessment}")

    return rows


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 2 — STABILITY GRID + HEATMAPS
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis_2(df, bh_ann):
    SEP = "═" * 80
    print(f"\n{SEP}")
    print("ANALYSIS 2 — STABILITY GRID (POST-BREAK PF AS QUALITY MEASURE)")
    print(f"Grid: period {A2_PERIODS} × stop {[int(s*100) for s in A2_STOPS]}% = "
          f"{len(A2_PERIODS)*len(A2_STOPS)} combinations")
    print(f"Post-break split: {BREAK_TS.date()}")
    print(SEP)

    n_days = (df.index[-1] - df.index[0]).days
    dates  = df.index
    grid   = []

    total  = len(A2_PERIODS) * len(A2_STOPS)
    done   = 0
    for period in A2_PERIODS:
        for stop_pct in A2_STOPS:
            trades, eq, _ = run_donchian(df, period, stop_pct=stop_pct, exit_method="A")
            m = full_metrics(trades, eq, n_days)
            pb_pf, pb_wr, pb_n = post_break_pf_wr_n(trades, dates)
            grid.append({
                "period":    period,
                "stop_pct":  stop_pct,
                "full_ann":  m["annual_ret"]  if m else np.nan,
                "full_sort": m["sortino"]     if m else np.nan,
                "full_pf":   m["pf"]          if m else np.nan,
                "full_n":    m["n_trades"]    if m else 0,
                "full_mdd":  m["mtm_mdd"]     if m else np.nan,
                "post_pf":   pb_pf if pb_pf is not None else np.nan,
                "post_wr":   pb_wr if pb_wr is not None else np.nan,
                "post_n":    pb_n,
            })
            done += 1
        print(f"  Period {period} done ({done}/{total})")

    df_grid = pd.DataFrame(grid)

    # ── Stability classification ──────────────────────────────────────────────
    n_total   = len(df_grid)
    n_viable  = int((df_grid["post_pf"] > 2.0).sum())
    viable_pct = n_viable / n_total

    if viable_pct >= 0.50:
        stability = "STABLE"
    elif viable_pct >= 0.25:
        stability = "MARGINAL"
    else:
        stability = "FRAGILE"

    print(f"\n  Stability: {n_viable}/{n_total} combos post-break PF > 2.0 "
          f"({viable_pct:.0%}) → {stability}")
    print(f"  Deployed (period=20, stop=5%) post-break PF: "
          f"{df_grid.loc[(df_grid.period==20)&(df_grid.stop_pct==0.05), 'post_pf'].values[0]:.3f}")

    # ── Post-break PF table ───────────────────────────────────────────────────
    print(f"\n  Post-break PF grid (>2.0 = VIABLE):")
    pivot_pb = df_grid.pivot(index="period", columns="stop_pct", values="post_pf")
    hdr_stops = "  " + "  ".join(f"{int(s*100):>5}%" for s in A2_STOPS)
    print(hdr_stops)
    for p in A2_PERIODS:
        row_vals = [pivot_pb.loc[p, s] for s in A2_STOPS]
        row_str  = "  ".join(
            f"{v:>6.2f}" if (pd.notna(v) and not np.isinf(v)) else "     —"
            for v in row_vals
        )
        marker = " ← DEPLOYED" if p == D_PERIOD else ""
        print(f"  p={p:<3}  {row_str}{marker}")

    # ── Save CSV ──────────────────────────────────────────────────────────────
    df_grid.to_csv(OUTPUT_STABILITY, index=False)
    print(f"\n  Saved → {OUTPUT_STABILITY}")

    # ── Heatmap 1: Post-break PF ──────────────────────────────────────────────
    pb_max   = float(df_grid["post_pf"].replace([np.inf], np.nan).quantile(0.95))
    pb_max   = max(pb_max, 4.0)
    save_heatmap(
        pivot_pb.replace([np.inf], pb_max + 0.5),
        "BNB Donchian — Post-Break Profit Factor (Jan 2024 split)\nDivergence at PF=2.0 (VIABLE threshold)",
        PNG_POSTBREAK_PF,
        center=2.0, vmin=0.0, vmax=pb_max,
    )

    # ── Heatmap 2: Full-period Sortino ────────────────────────────────────────
    pivot_so = df_grid.pivot(index="period", columns="stop_pct", values="full_sort")
    so_max   = max(float(df_grid["full_sort"].quantile(0.95)), 2.0)
    so_min   = min(float(df_grid["full_sort"].min()), -0.5)
    save_heatmap(
        pivot_so,
        "BNB Donchian — Full-Period Sortino Ratio\nDivergence at Sortino=0.8 (deployment threshold)",
        PNG_SORTINO,
        center=0.8, vmin=so_min, vmax=so_max, fmt=".2f",
    )

    # ── Heatmap 3: Full-period annual return ──────────────────────────────────
    pivot_ann = df_grid.pivot(index="period", columns="stop_pct", values="full_ann")
    ann_max   = max(float(df_grid["full_ann"].quantile(0.95)), bh_ann * 1.5)
    ann_min   = min(float(df_grid["full_ann"].min()), -0.1)
    save_heatmap(
        pivot_ann,
        f"BNB Donchian — Full-Period Annual Return\nDivergence at B&H annual return ({bh_ann:.1%})",
        PNG_ANNUAL_RET,
        center=bh_ann, vmin=ann_min, vmax=ann_max, fmt=".0%",
    )

    return df_grid, stability, n_viable, n_total


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 3 — EXIT METHOD COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis_3(df):
    SEP = "═" * 80
    print(f"\n{SEP}")
    print("ANALYSIS 3 — EXIT METHOD COMPARISON (period=20 fixed)")
    print("A: 5% trailing stop + channel low  |  B: ATR14 stop  |  C: EMA-20 two-tier")
    print(SEP)

    n_days = (df.index[-1] - df.index[0]).days

    exits = [
        ("A — channel+trail5%", "A", {}),
        ("B — ATR14×2.0 stop",  "B", {"atr_mult": 2.0, "atr_period": 14}),
        ("C — EMA-20 two-tier", "C", {"ema_exit_period": 20}),
    ]

    results = []
    for label, method, kwargs in exits:
        trades, eq, _ = run_donchian(df, D_PERIOD, stop_pct=D_STOP_PCT,
                                     exit_method=method, **kwargs)
        r = metrics_row(label, trades, eq, df, n_days)
        results.append(r)

    # ── Display ───────────────────────────────────────────────────────────────
    hdr = (f"  {'Exit':<22}  {'FPF':>6}  {'FAnn':>7}  {'FSrt':>6}  "
           f"{'WR':>6}  {'N':>4}  {'MtMMDD':>7}  {'PtMDD':>7}  "
           f"{'PBkPF':>7}  {'PBkAnn':>7}  {'PBkN':>5}")
    print(hdr)
    print(f"  {'-'*100}")

    for r in results:
        print(f"  {r['label']:<22}  "
              f"{f_pf(r['full_pf']):>6}  {f_pct(r['ann_ret']):>7}  "
              f"{f_so(r['sortino']):>6}  "
              f"{f_pct(r['full_wr']):>6}  {r['n_trades']:>4}  "
              f"{f_pct(r['mtm_mdd']):>7}  {f_pct(r['pt_mdd']):>7}  "
              f"{f_pf(r['post_pf']):>7}  {f_pct(r['post_ann']):>7}  "
              f"{r['post_n']:>5}")

    # Determine best exit by post-break PF (primary), then full-period Sortino
    def sort_key(r):
        pb = r["post_pf"] if r["post_pf"] is not None and not np.isinf(r["post_pf"]) else -999
        so = r["sortino"] if r["sortino"] is not None and not np.isnan(r["sortino"]) else -999
        return (pb, so)

    best = max(results, key=sort_key)
    best_method = best["label"][0]   # "A", "B", or "C"
    print(f"\n  Best exit by post-break PF: {best['label']}  "
          f"(post-break PF {f_pf(best['post_pf'])}, Sortino {f_so(best['sortino'])})")
    print(f"  This exit method will be used for Analysis 4 regime filter test.")

    return results, best_method


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 4 — REGIME FILTER TEST
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis_4(df, best_exit_method):
    SEP = "═" * 80
    print(f"\n{SEP}")
    print(f"ANALYSIS 4 — REGIME FILTER TEST (exit method: {best_exit_method})")
    print("SMA filter: only enter when close > SMA on signal bar")
    print(SEP)

    n_days  = (df.index[-1] - df.index[0]).days

    filters = [
        ("No filter (baseline)", None),
        ("SMA-50 filter",         50),
        ("SMA-100 filter",       100),
        ("SMA-120 filter",       120),
    ]

    results = []
    for label, sma_p in filters:
        trades, eq, _ = run_donchian(df, D_PERIOD, stop_pct=D_STOP_PCT,
                                     exit_method=best_exit_method,
                                     sma_period=sma_p)
        r = metrics_row(label, trades, eq, df, n_days)
        results.append(r)

    hdr = (f"  {'Filter':<22}  {'FPF':>6}  {'FAnn':>7}  {'FSrt':>6}  "
           f"{'WR':>6}  {'N':>4}  {'MtMMDD':>7}  "
           f"{'PBkPF':>7}  {'PBkAnn':>7}  {'PBkN':>5}")
    print(hdr)
    print(f"  {'-'*90}")

    for r in results:
        baseline = " ← baseline" if r["label"] == "No filter (baseline)" else ""
        print(f"  {r['label']:<22}  "
              f"{f_pf(r['full_pf']):>6}  {f_pct(r['ann_ret']):>7}  "
              f"{f_so(r['sortino']):>6}  "
              f"{f_pct(r['full_wr']):>6}  {r['n_trades']:>4}  "
              f"{f_pct(r['mtm_mdd']):>7}  "
              f"{f_pf(r['post_pf']):>7}  {f_pct(r['post_ann']):>7}  "
              f"{r['post_n']:>5}{baseline}")

    # Interpretation
    no_filter = results[0]
    print(f"\n  Regime filter effect on post-break performance:")
    for r in results[1:]:
        pb_delta = (r["post_pf"] or 0) - (no_filter["post_pf"] or 0)
        n_delta  = r["n_trades"] - no_filter["n_trades"]
        direction = "↑ improves" if pb_delta > 0.1 else ("↓ hurts" if pb_delta < -0.1 else "≈ neutral")
        print(f"    {r['label']}: post-break PF {f_pf(r['post_pf'])} "
              f"({pb_delta:+.3f} vs baseline), "
              f"{r['n_trades']} trades ({n_delta:+d}), {direction}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# SAVE CSV OUTPUTS
# ══════════════════════════════════════════════════════════════════════════════

def save_exit_regime_csv(a3_results, a4_results, best_exit_method):
    rows = []
    for r in a3_results:
        rows.append({"analysis": "3_exit_comparison",
                     "exit_method": r["label"], "sma_filter": None, **r})
    for r in a4_results:
        rows.append({"analysis": "4_regime_filter",
                     "exit_method": best_exit_method, "sma_filter": r["label"], **r})
    df_out = pd.DataFrame(rows)
    df_out.to_csv(OUTPUT_EXIT_SMA, index=False)
    print(f"\n  Saved → {OUTPUT_EXIT_SMA}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    SEP = "═" * 80
    print(SEP)
    print("BNB DONCHIAN FULL VALIDATION PIPELINE — ANALYSES 1–4")
    print(f"Strategy: BNB Donchian period={D_PERIOD}, stop={int(D_STOP_PCT*100)}%")
    print(f"Regime break split: {BREAK_TS.date()}")
    print(SEP)

    print(f"\nFetching {TICKER}...")
    df  = g.fetch_asset(TICKER)
    bh  = g.bh_benchmark(df["close"].values, (df.index[-1] - df.index[0]).days)
    print(f"  {len(df)} candles | {df.index[0].date()} → {df.index[-1].date()}")
    print(f"  B&H: {bh['annual_ret']:+.1%} annual | Sortino {bh['sortino']:.2f}")

    # ── Analysis 1 ────────────────────────────────────────────────────────────
    run_analysis_1(df)

    # ── Analysis 2 ────────────────────────────────────────────────────────────
    df_grid, stability, n_viable, n_total = run_analysis_2(df, bh["annual_ret"])

    # ── Analysis 3 ────────────────────────────────────────────────────────────
    a3_results, best_exit = run_analysis_3(df)

    # ── Analysis 4 ────────────────────────────────────────────────────────────
    a4_results = run_analysis_4(df, best_exit)

    # ── Save CSV ──────────────────────────────────────────────────────────────
    save_exit_regime_csv(a3_results, a4_results, best_exit)

    # ── Final summary ─────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("PIPELINE SUMMARY")
    print(SEP)
    print(f"  Analysis 1 (boundary): stop range 3–15%, period=20 fixed")
    print(f"  Analysis 2 (stability): {n_viable}/{n_total} combos post-break PF>2.0 "
          f"→ {stability}")
    print(f"  Analysis 3 (exits): best exit by post-break PF = Exit {best_exit}")
    print(f"  Analysis 4 (regime): SMA filters tested with Exit {best_exit}")
    print(f"\n  Outputs:")
    print(f"    {OUTPUT_STABILITY}")
    print(f"    {OUTPUT_EXIT_SMA}")
    print(f"    {PNG_POSTBREAK_PF}")
    print(f"    {PNG_SORTINO}")
    print(f"    {PNG_ANNUAL_RET}")
    print(f"\n{SEP}")
    print("All four analyses complete. Do not proceed to deployment docs until reviewed.")
    print(SEP)


if __name__ == "__main__":
    main()
