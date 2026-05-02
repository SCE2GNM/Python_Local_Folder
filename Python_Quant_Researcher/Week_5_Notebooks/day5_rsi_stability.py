# [MODULE] Day 5c - RSI Parameter Stability Analysis
# Week 5 Part B
#
# WHAT THIS SCRIPT DOES:
#   Analyses whether the best RSI parameters sit on a broad stable
#   plateau (genuine edge) or an isolated spike (overfitting).
#
# TWO VISUALISATIONS:
#
#   1. SENSITIVITY CHART
#      Varies each parameter one at a time while holding others fixed
#      at best values. If profit factor collapses when you move one
#      step away from the optimum — that's a spike. If it stays high
#      across a range — that's a plateau.
#
#   2. 2D HEATMAP GRID
#      Shows profit factor across pairs of parameters simultaneously.
#      Stable regions appear as broad green areas. Spikes appear as
#      single green cells surrounded by red/yellow.
#
# BEST PARAMETERS FROM GRID SEARCH (rank 2 — most statistically reliable):
#   RSI period: 14 | Oversold: 45 | Exit: 45 | Stop: 15% | MA: 100

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ---------------------------------------------------------------------------
# Load grid search results
# ---------------------------------------------------------------------------

print("\nLoading RSI optimisation results...")
results_df = pd.read_csv('data/rsi_optimisation_results.csv')
print(f"Loaded {len(results_df)} valid combinations.")

# Best parameters (rank 2 — most statistically reliable)
BEST = {
    'rsi_period': 14,
    'oversold':   43.0,
    'exit_level': 48.0,
    'stop_pct':   0.15,
    'ma_filter':  120,
}

print(f"\nReference parameters (rank 2):")
for k, v in BEST.items():
    print(f"  {k}: {v}")


# ---------------------------------------------------------------------------
# PART 1: SENSITIVITY ANALYSIS
# ---------------------------------------------------------------------------
# For each parameter, vary it across all tested values while holding
# the other 4 parameters fixed at BEST values.
# Plot median profit factor at each value — median is more robust
# than mean because it ignores extreme outliers.

print("\nCalculating parameter sensitivity...")

fig1, axes = plt.subplots(1, 5, figsize=(20, 5))
fig1.suptitle(
    'RSI Parameter Sensitivity Analysis\n'
    'Each parameter varied independently — others fixed at best values\n'
    'Wide flat curve = stable plateau. Sharp peak = fragile spike.',
    fontsize=11, fontweight='bold'
)

params = ['rsi_period', 'oversold', 'exit_level', 'stop_pct', 'ma_filter']
labels = ['RSI Period', 'Oversold Level', 'Exit Level', 'Stop %', 'MA Filter']
colors = ['steelblue', 'green', 'purple', 'crimson', 'orange']

for idx, (param, label, color) in enumerate(zip(params, labels, colors)):
    ax = axes[idx]

    # Filter to rows where all OTHER params match BEST values
    mask = pd.Series([True] * len(results_df))
    for other_param, other_val in BEST.items():
        if other_param != param:
            mask = mask & (results_df[other_param] == other_val)

    filtered = results_df[mask]

    if len(filtered) == 0:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                transform=ax.transAxes)
        ax.set_title(label)
        continue

    # Group by this parameter and calculate median profit factor
    grouped = filtered.groupby(param)['profit_factor'].agg(['median', 'mean', 'count'])
    grouped = grouped.reset_index()

    # Plot median profit factor
    ax.plot(grouped[param], grouped['median'],
            color=color, linewidth=2.5, marker='o', markersize=6,
            label='Median PF')

    # Shade the range between min and max to show spread
    pf_min = filtered.groupby(param)['profit_factor'].min()
    pf_max = filtered.groupby(param)['profit_factor'].max()
    ax.fill_between(grouped[param], pf_min.values, pf_max.values,
                    alpha=0.2, color=color, label='Min-Max range')

    # Mark the best value
    best_val = BEST[param]
    best_pf  = grouped[grouped[param] == best_val]['median'].values
    if len(best_pf) > 0:
        ax.axvline(best_val, color='gold', linewidth=2,
                   linestyle='--', label=f'Best={best_val}')
        ax.scatter([best_val], [best_pf[0]], color='gold',
                   s=100, zorder=5)

    # Reference line at profit factor = 1.0 (break-even)
    ax.axhline(1.0, color='red', linestyle=':', alpha=0.5, label='Break-even')

    # Format x-axis for stop_pct
    if param == 'stop_pct':
        ax.set_xticklabels([f"{int(v*100)}%" for v in grouped[param]], fontsize=7)

    ax.set_title(label, fontweight='bold')
    ax.set_xlabel(label, fontsize=8)
    ax.set_ylabel('Profit Factor' if idx == 0 else '')
    ax.legend(fontsize=6)
    ax.grid(alpha=0.3)

plt.tight_layout()
os.makedirs('Week_5_Notebooks/results', exist_ok=True)
sensitivity_path = 'Week_5_Notebooks/results/day5c_rsi_sensitivity.png'
plt.savefig(sensitivity_path, dpi=150)
plt.close()
print(f"✅ Sensitivity chart saved → {sensitivity_path}")


# ---------------------------------------------------------------------------
# PART 2: 2D HEATMAP GRID
# ---------------------------------------------------------------------------
# Show all pairs of parameters as heatmaps.
# Fix the remaining 3 parameters at BEST values for each panel.
# This shows whether good performance is concentrated or spread out.

print("Generating 2D heatmap grid...")

# All pairs of parameters
param_pairs = [
    ('rsi_period', 'oversold'),
    ('rsi_period', 'exit_level'),
    ('oversold',   'exit_level'),
    ('oversold',   'ma_filter'),
    ('exit_level', 'stop_pct'),
    ('stop_pct',   'ma_filter'),
]

fig2, axes2 = plt.subplots(2, 3, figsize=(18, 12))
fig2.suptitle(
    'RSI 2D Parameter Heatmaps — Profit Factor\n'
    'Broad green regions = stable edge. Isolated green cells = fragile spike.\n'
    f'Fixed params at best values: Period={BEST["rsi_period"]}, '
    f'OS={int(BEST["oversold"])}, Exit={int(BEST["exit_level"])}, '
    f'Stop={int(BEST["stop_pct"]*100)}%, MA={BEST["ma_filter"]}',
    fontsize=10, fontweight='bold'
)

# Colour scale fixed across all panels for fair comparison
vmin = results_df['profit_factor'].quantile(0.1)
vmax = results_df['profit_factor'].quantile(0.9)

for idx, (p1, p2) in enumerate(param_pairs):
    ax = axes2[idx // 3][idx % 3]

    # Fix all params EXCEPT p1 and p2 at BEST values
    mask = pd.Series([True] * len(results_df))
    for param, val in BEST.items():
        if param not in [p1, p2]:
            mask = mask & (results_df[param] == val)

    filtered = results_df[mask]

    if len(filtered) == 0:
        ax.text(0.5, 0.5, 'No data\nfor this\ncombination',
                ha='center', va='center', transform=ax.transAxes, fontsize=10)
        ax.set_title(f'{p1} vs {p2}')
        continue

    # Pivot table: median profit factor at each (p1, p2) combination
    pivot = filtered.pivot_table(
        index=p1,
        columns=p2,
        values='profit_factor',
        aggfunc='median'
    )

    im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto',
                   vmin=vmin, vmax=vmax)

    # Format axis labels
    def fmt(param, val):
        if param == 'stop_pct':
            return f"{int(val*100)}%"
        elif param in ['oversold', 'exit_level']:
            return f"{int(val)}"
        else:
            return str(int(val))

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([fmt(p2, v) for v in pivot.columns], fontsize=7)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([fmt(p1, v) for v in pivot.index], fontsize=7)
    ax.set_xlabel(p2.replace('_', ' ').title(), fontsize=9)
    ax.set_ylabel(p1.replace('_', ' ').title(), fontsize=9)
    ax.set_title(f'{p1.replace("_"," ").title()} vs '
                 f'{p2.replace("_"," ").title()}',
                 fontweight='bold', fontsize=10)

    # Annotate cells with profit factor values
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.2f}',
                        ha='center', va='center',
                        fontsize=6, fontweight='bold')

    # Mark best parameter values on this panel
    p1_vals = list(pivot.index)
    p2_vals = list(pivot.columns)
    if BEST[p1] in p1_vals and BEST[p2] in p2_vals:
        p1_idx = p1_vals.index(BEST[p1])
        p2_idx = p2_vals.index(BEST[p2])
        ax.add_patch(plt.Rectangle(
            (p2_idx - 0.5, p1_idx - 0.5), 1, 1,
            fill=False, edgecolor='blue', linewidth=3
        ))

fig2.colorbar(im, ax=axes2.ravel().tolist(),
              label='Profit Factor (median)', shrink=0.6)
plt.tight_layout()
heatmap_path = 'Week_5_Notebooks/results/day5c_rsi_heatmap_grid.png'
plt.savefig(heatmap_path, dpi=150)
plt.close()
print(f"✅ 2D heatmap grid saved → {heatmap_path}")


# ---------------------------------------------------------------------------
# PART 3: STABILITY SCORE
# ---------------------------------------------------------------------------
# For each parameter, calculate what fraction of values produce a
# profit factor above 2.0 (a reasonable minimum threshold).
# High fraction = stable. Low fraction = fragile.

print(f"\n{'='*70}")
print(f"PARAMETER STABILITY SCORES")
print(f"(% of values that keep profit factor above 2.0,")
print(f" when all other params fixed at best values)")
print(f"{'='*70}")

threshold = 2.0

for param, label in zip(params, labels):
    mask = pd.Series([True] * len(results_df))
    for other_param, other_val in BEST.items():
        if other_param != param:
            mask = mask & (results_df[other_param] == other_val)

    filtered = results_df[mask]
    if len(filtered) == 0:
        continue

    grouped = filtered.groupby(param)['profit_factor'].median()
    above_threshold = (grouped >= threshold).sum()
    total_values    = len(grouped)
    stability_pct   = above_threshold / total_values * 100

    bar = '█' * int(stability_pct / 5) + '░' * (20 - int(stability_pct / 5))
    print(f"  {label:<20} {bar} {stability_pct:.0f}% "
          f"({above_threshold}/{total_values} values)")

print(f"\n  Interpretation:")
print(f"  80-100% = very stable — broad plateau")
print(f"  50-79%  = moderately stable — some sensitivity")
print(f"  0-49%   = fragile — likely overfitting to specific values")

print(f"\n{'='*70}")
print(f"STABILITY ANALYSIS COMPLETE")
print(f"{'='*70}\n")
