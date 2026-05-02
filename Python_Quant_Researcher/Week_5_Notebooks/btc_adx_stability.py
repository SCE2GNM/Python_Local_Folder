# [MODULE] BTC ADX Parameter Stability Analysis
# Week 5 Extension
#
# Analyses whether the best BTC ADX parameters sit on a broad
# stable plateau (genuine edge) or an isolated spike (overfitting).
#
# BEST PARAMETERS FROM BTC GRID SEARCH:
#   Threshold: 19 | Period: 14 | Stop: 3.0%
#
# REFERENCE: ETH live parameters for comparison
#   Threshold: 20 | Period: 10 | Stop: 5.0%

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ---------------------------------------------------------------------------
# Load BTC grid search results
# ---------------------------------------------------------------------------

print("\nLoading BTC ADX optimisation results...")
results_df = pd.read_csv('data/btc_adx_optimisation_results.csv')
print(f"Loaded {len(results_df)} combinations.")

# Best BTC parameters from grid search
BEST = {
    'threshold': 19,
    'period':    14,
    'stop_pct':  0.030,
}

# ETH live parameters for reference
ETH = {
    'threshold': 20,
    'period':    10,
    'stop_pct':  0.050,
}

print(f"\nBTC best parameters: ADX {BEST['threshold']}/{BEST['period']} "
      f"stop={BEST['stop_pct']*100:.1f}%")
print(f"ETH live parameters: ADX {ETH['threshold']}/{ETH['period']} "
      f"stop={ETH['stop_pct']*100:.1f}%")


# ---------------------------------------------------------------------------
# PART 1: SENSITIVITY ANALYSIS
# ---------------------------------------------------------------------------

print("\nCalculating parameter sensitivity...")

fig1, axes = plt.subplots(1, 3, figsize=(15, 5))
fig1.suptitle(
    'BTC ADX Parameter Sensitivity Analysis\n'
    'Each parameter varied independently — others fixed at best values\n'
    'Wide flat curve = stable plateau. Sharp peak = fragile spike.',
    fontsize=11, fontweight='bold'
)

params = ['threshold', 'period', 'stop_pct']
labels = ['ADX Threshold', 'ADX Period', 'Stop %']
colors = ['steelblue', 'green', 'crimson']

for idx, (param, label, color) in enumerate(zip(params, labels, colors)):
    ax = axes[idx]

    # Filter to rows where all OTHER params match BEST
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

    grouped = filtered.groupby(param)['profit_factor'].agg(
        ['median', 'min', 'max']
    ).reset_index()

    # Plot median
    ax.plot(grouped[param], grouped['median'],
            color=color, linewidth=2.5, marker='o', markersize=6,
            label='Median PF')

    # Shade min-max range
    ax.fill_between(grouped[param], grouped['min'], grouped['max'],
                    alpha=0.2, color=color, label='Min-Max range')

    # Mark best value
    best_val = BEST[param]
    best_pf  = grouped[grouped[param] == best_val]['median'].values
    if len(best_pf) > 0:
        ax.axvline(best_val, color='gold', linewidth=2,
                   linestyle='--', label=f'BTC best={best_val}')
        ax.scatter([best_val], [best_pf[0]], color='gold', s=100, zorder=5)

    # Mark ETH value for comparison
    eth_val = ETH[param]
    eth_pf  = grouped[grouped[param] == eth_val]['median'].values
    if len(eth_pf) > 0:
        ax.axvline(eth_val, color='orange', linewidth=1.5,
                   linestyle=':', label=f'ETH live={eth_val}')
        ax.scatter([eth_val], [eth_pf[0]], color='orange', s=80, zorder=5)

    # Break-even line
    ax.axhline(1.0, color='red', linestyle=':', alpha=0.5, label='Break-even')

    # Format stop_pct x-axis
    if param == 'stop_pct':
        tick_vals = grouped[param].values
        ax.set_xticks(tick_vals)
        ax.set_xticklabels([f"{int(v*100)}%" for v in tick_vals], fontsize=8)

    ax.set_title(label, fontweight='bold')
    ax.set_xlabel(label, fontsize=9)
    ax.set_ylabel('Profit Factor' if idx == 0 else '')
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

plt.tight_layout()
os.makedirs('Week_5_Notebooks/results', exist_ok=True)
sensitivity_path = 'Week_5_Notebooks/results/btc_adx_sensitivity.png'
plt.savefig(sensitivity_path, dpi=150)
plt.close()
print(f"✅ Sensitivity chart saved → {sensitivity_path}")


# ---------------------------------------------------------------------------
# PART 2: 2D HEATMAPS
# ---------------------------------------------------------------------------

print("Generating 2D heatmaps...")

param_pairs = [
    ('threshold', 'period'),
    ('threshold', 'stop_pct'),
    ('period',    'stop_pct'),
]

fig2, axes2 = plt.subplots(1, 3, figsize=(18, 6))
fig2.suptitle(
    'BTC ADX 2D Parameter Heatmaps — Profit Factor\n'
    f'Blue box = BTC best (ADX {BEST["threshold"]}/{BEST["period"]} '
    f'stop {BEST["stop_pct"]*100:.0f}%) | '
    f'Orange box = ETH live (ADX {ETH["threshold"]}/{ETH["period"]} '
    f'stop {ETH["stop_pct"]*100:.0f}%)',
    fontsize=10, fontweight='bold'
)

vmin = results_df['profit_factor'].quantile(0.1)
vmax = results_df['profit_factor'].quantile(0.9)

for idx, (p1, p2) in enumerate(param_pairs):
    ax = axes2[idx]

    # Fix the third parameter at BEST value
    third_param = [p for p in BEST.keys() if p not in [p1, p2]][0]
    mask = results_df[third_param] == BEST[third_param]
    filtered = results_df[mask]

    if len(filtered) == 0:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                transform=ax.transAxes)
        continue

    pivot = filtered.pivot_table(
        index=p1,
        columns=p2,
        values='profit_factor',
        aggfunc='median'
    )

    im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto',
                   vmin=vmin, vmax=vmax)

    def fmt(param, val):
        if param == 'stop_pct':
            return f"{int(val*100)}%"
        return str(int(val))

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([fmt(p2, v) for v in pivot.columns], fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([fmt(p1, v) for v in pivot.index], fontsize=8)
    ax.set_xlabel(p2.replace('_', ' ').title(), fontsize=9)
    ax.set_ylabel(p1.replace('_', ' ').title(), fontsize=9)
    ax.set_title(
        f'{p1.replace("_"," ").title()} vs '
        f'{p2.replace("_"," ").title()}\n'
        f'(fixed: {third_param.replace("_"," ")}='
        f'{fmt(third_param, BEST[third_param])})',
        fontsize=9, fontweight='bold'
    )

    # Annotate cells
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.2f}',
                        ha='center', va='center',
                        fontsize=7, fontweight='bold')

    # Mark BTC best parameters
    p1_vals = list(pivot.index)
    p2_vals = list(pivot.columns)
    if BEST[p1] in p1_vals and BEST[p2] in p2_vals:
        p1_idx = p1_vals.index(BEST[p1])
        p2_idx = p2_vals.index(BEST[p2])
        ax.add_patch(plt.Rectangle(
            (p2_idx - 0.5, p1_idx - 0.5), 1, 1,
            fill=False, edgecolor='blue', linewidth=3, label='BTC best'
        ))

    # Mark ETH parameters
    if ETH[p1] in p1_vals and ETH[p2] in p2_vals:
        p1_idx = p1_vals.index(ETH[p1])
        p2_idx = p2_vals.index(ETH[p2])
        ax.add_patch(plt.Rectangle(
            (p2_idx - 0.5, p1_idx - 0.5), 1, 1,
            fill=False, edgecolor='orange', linewidth=2,
            linestyle='--', label='ETH live'
        ))

fig2.colorbar(im, ax=axes2.ravel().tolist(),
              label='Profit Factor (median)', shrink=0.8)
plt.tight_layout()
heatmap_path = 'Week_5_Notebooks/results/btc_adx_heatmaps.png'
plt.savefig(heatmap_path, dpi=150)
plt.close()
print(f"✅ Heatmaps saved → {heatmap_path}")


# ---------------------------------------------------------------------------
# PART 3: STABILITY SCORES
# ---------------------------------------------------------------------------

threshold = 2.0  # minimum acceptable profit factor

print(f"\n{'='*70}")
print(f"BTC ADX PARAMETER STABILITY SCORES")
print(f"(% of values keeping profit factor above {threshold:.1f})")
print(f"{'='*70}")

for param, label in zip(params, labels):
    mask = pd.Series([True] * len(results_df))
    for other_param, other_val in BEST.items():
        if other_param != param:
            mask = mask & (results_df[other_param] == other_val)

    filtered = results_df[mask]
    if len(filtered) == 0:
        continue

    grouped = filtered.groupby(param)['profit_factor'].median()
    above   = (grouped >= threshold).sum()
    total   = len(grouped)
    pct     = above / total * 100

    bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
    print(f"  {label:<20} {bar} {pct:.0f}% ({above}/{total} values)")

print(f"\n  Interpretation:")
print(f"  80-100% = very stable — broad plateau")
print(f"  50-79%  = moderately stable — some sensitivity")
print(f"  0-49%   = fragile — likely overfitting")

# Also show ETH parameter performance on each BTC sensitivity curve
print(f"\n{'='*70}")
print(f"ETH PARAMETERS PERFORMANCE ON BTC SENSITIVITY CURVES")
print(f"{'='*70}")
print(f"  (What profit factor do ETH values produce on BTC?)")

for param, label in zip(params, labels):
    mask = pd.Series([True] * len(results_df))
    for other_param, other_val in BEST.items():
        if other_param != param:
            mask = mask & (results_df[other_param] == other_val)

    filtered = results_df[mask]
    if len(filtered) == 0:
        continue

    eth_val = ETH[param]
    eth_row = filtered[filtered[param] == eth_val]
    if len(eth_row) > 0:
        eth_pf = eth_row['profit_factor'].median()
        print(f"  {label:<20} ETH value={fmt(param, eth_val):<8} "
              f"→ PF on BTC: {eth_pf:.3f} "
              f"({'✅ above 2.0' if eth_pf >= 2.0 else '❌ below 2.0'})")

print(f"\n{'='*70}")
print(f"BTC ADX STABILITY ANALYSIS COMPLETE")
print(f"{'='*70}\n")