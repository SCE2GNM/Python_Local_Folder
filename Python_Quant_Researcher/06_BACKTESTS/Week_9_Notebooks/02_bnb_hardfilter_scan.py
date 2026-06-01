"""
02_bnb_hardfilter_scan.py
Re-runs the discovery grid for BNB-USD only.

Saves ALL combinations that pass the hard filters (n_trades >= 30,
MtM MDD > -50%) WITHOUT applying the B&H benchmark filter.
Sorted by annual_ret descending.

Imports grid functions from 01_altcoin_discovery_grid.py via importlib
(normal import fails because the filename starts with a digit).
"""

import importlib.util
import os
import numpy as np
import pandas as pd

BASE   = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE, "bnb_hardfilter_results.csv")

# ── Load grid module without executing main() ─────────────────────────────────
spec = importlib.util.spec_from_file_location(
    "altcoin_grid",
    os.path.join(BASE, "01_altcoin_discovery_grid.py"),
)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)   # __name__ != "__main__" so main() does not run

TICKER = "BNB-USD"

print("=" * 68)
print(f"BNB-USD HARD-FILTER SCAN  (no B&H benchmark gate)")
print(f"Hard filters : n_trades >= {g.MIN_TRADES}  |  MtM MDD > {g.MAX_MDD:.0%}")
print(f"Combos       : {g.TOTAL_COMBOS}  (same grid as full discovery run)")
print("=" * 68)

print(f"\nFetching {TICKER}...")
df = g.fetch_asset(TICKER)
print(f"  {len(df)} candles | {df.index[0].date()} → {df.index[-1].date()}")

bh     = g.bh_benchmark(df["close"].values, (df.index[-1] - df.index[0]).days)
bh_ann = bh["annual_ret"]
print(f"  B&H: {bh_ann:.1%} annual | {bh['mdd']:.1%} MDD | Sortino {bh['sortino']:.2f}")
print(f"  B&H 1.5× floor (reference only, NOT applied): {bh_ann * g.BH_MULT:.1%}\n")

# ── Run all five grids, collect hard-filter passes ────────────────────────────
print(f"Running ADX ({len(g.ADX_PERIODS)*len(g.ADX_THRESHOLDS)*len(g.ADX_STOPS)} combos)...")
raw = g.run_adx_grid(df)

print(f"Running Supertrend ({len(g.ST_ATR_PERIODS)*len(g.ST_MULTIPLIERS)} combos)...")
raw += g.run_supertrend_grid(df)

print(f"Running Donchian ({len(g.DC_PERIODS)*len(g.DC_STOPS)} combos)...")
raw += g.run_donchian_grid(df)

print(f"Running Keltner ({len(g.KC_EMA_PERIODS)*len(g.KC_MULTIPLIERS)} combos)...")
raw += g.run_keltner_grid(df)

print(f"Running Bollinger ({len(g.BB_PERIODS)*len(g.BB_STDS)} combos)...")
raw += g.run_bollinger_grid(df)

print(f"\n{len(raw)} combinations passed hard filters (of {g.TOTAL_COMBOS} tested)")

# ── Build and save results ────────────────────────────────────────────────────
rows = []
for m in raw:
    rows.append({
        "asset":      TICKER,
        "strategy":   m["strategy"],
        "params":     m["params"],
        "annual_ret": m["annual_ret"],
        "sortino":    m["sortino"],
        "pf":         m["pf"],
        "win_rate":   m["win_rate"],
        "n_trades":   m["n_trades"],
        "mtm_mdd":    m["mtm_mdd"],
        "pt_mdd":     m["pt_mdd"],
    })

df_out = (pd.DataFrame(rows)
          .sort_values("annual_ret", ascending=False)
          .reset_index(drop=True))
df_out.to_csv(OUTPUT, index=False)
print(f"Saved → {OUTPUT}\n")

# ── Display results table ─────────────────────────────────────────────────────
SEP = "=" * 100

print(SEP)
print(f"BNB-USD — All hard-filter passing combinations, sorted by annual return")
print(f"B&H reference: {bh_ann:.1%} annual | Sortino {bh['sortino']:.2f} | MDD {bh['mdd']:.1%}")
print(SEP)

hdr = (f"{'#':<4}  {'Family':<12}  {'Parameters':<26}  "
       f"{'AnnRet':>7}  {'Sortino':>7}  {'Trades':>6}  "
       f"{'MtMMDD':>7}  {'PF':>7}  {'Win%':>5}")
print(hdr)
print("-" * 100)

# B&H reference row
bh_so = f"{bh['sortino']:.2f}" if pd.notna(bh["sortino"]) else "  —"
print(f"{'B&H':<4}  {'buy-hold':<12}  {'—':<26}  "
      f"{bh_ann:>6.1%}  {bh_so:>7}  {'—':>6}  "
      f"{bh['mdd']:>6.1%}  {'—':>7}  {'—':>5}")
print("-" * 100)

for rank, row in df_out.iterrows():
    so = f"{row['sortino']:.2f}" if pd.notna(row["sortino"]) else "  —"
    pf = f"{row['pf']:.3f}"      if pd.notna(row["pf"])      else "  —"
    wr = f"{row['win_rate']:.1%}"
    beats_bh = "✓" if row["annual_ret"] > bh_ann else " "
    print(f"{rank+1:<4}  {row['strategy']:<12}  {row['params']:<26}  "
          f"{row['annual_ret']:>6.1%}{beats_bh} {so:>7}  {int(row['n_trades']):>6}  "
          f"{row['mtm_mdd']:>6.1%}  {pf:>7}  {wr:>5}")

print(SEP)

# ── Breakdown by strategy family ──────────────────────────────────────────────
print("\nBreakdown by strategy family:")
for fam in df_out["strategy"].unique():
    sub  = df_out[df_out["strategy"] == fam]
    best = sub.iloc[0]
    above_bh = sum(sub["annual_ret"] > bh_ann)
    print(f"  {fam:<12}  {len(sub):>2} passing  "
          f"best: {best['annual_ret']:.1%} ann / Sortino {best['sortino']:.2f}  "
          f"({above_bh} beat B&H annual)")

print(f"\nTotal: {len(df_out)} combinations. ✓ = beats B&H annual return ({bh_ann:.1%})")
print("B&H 1.5× deployment floor (104.2%) shown for reference — NOT a gate here.")
