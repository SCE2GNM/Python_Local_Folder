# Stage 2 — Interactive Parallel Coordinates (Plotly HTML)
# Rebuilt using go.Parcoords for native browser drag-to-reorder axes.
# Previous version used go.Scatter with manual axis lines — axes were NOT draggable.
#
# go.Parcoords features:
#   - Drag any axis left/right to reorder
#   - Brush an axis to filter/highlight matching strategies
#   - Shift+click to add multiple range selections
#   - Double-click axis label to clear its selection
#
# Each line = one (SMA, trail%) strategy from the extended Stage 2a grid (171 combos)
# Colour: Annual Return % (RdYlGn — red = low, green = high)
# Saves: Week_6_Notebooks/results/stage2_parallel_coordinates_interactive.html

import os
import pandas as pd
import plotly.graph_objects as go

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)

PRIMARY_SMA   = 135;  PRIMARY_TRAIL   = 25.0
SECONDARY_SMA = 145;  SECONDARY_TRAIL = 20.0

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
csv_path = os.path.join(DATA_DIR, 'stage2a_results_extended.csv')
df = pd.read_csv(csv_path).reset_index(drop=True)
print(f"Loaded {len(df)} strategies from {csv_path}")

# Candidate marker column: 2 = primary, 1 = secondary, 0 = other
def cand_type(row):
    if row['sma_period'] == PRIMARY_SMA and abs(row['trail_pct'] - PRIMARY_TRAIL) < 0.1:
        return 2
    if row['sma_period'] == SECONDARY_SMA and abs(row['trail_pct'] - SECONDARY_TRAIL) < 0.1:
        return 1
    return 0

df['cand'] = df.apply(cand_type, axis=1)

# Sort so primary/secondary are drawn last (on top of other lines)
df = df.sort_values('cand', ascending=True).reset_index(drop=True)

n_primary   = (df['cand'] == 2).sum()
n_secondary = (df['cand'] == 1).sum()
print(f"  Primary candidates: {n_primary}  |  Secondary candidates: {n_secondary}")

# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
fig = go.Figure(go.Parcoords(
    line=dict(
        color=df['annual_return'],
        colorscale='RdYlGn',
        showscale=True,
        cmin=df['annual_return'].min(),
        cmax=df['annual_return'].max(),
        colorbar=dict(
            title=dict(text='Annual<br>Return %', side='right',
                       font=dict(size=11, color='#333')),
            thickness=18,
            len=0.75,
            y=0.5, yanchor='middle',
            ticksuffix='%',
            tickfont=dict(size=10),
        ),
    ),
    dimensions=[
        dict(
            label='SMA Period',
            values=df['sma_period'],
            range=[df['sma_period'].min() - 2, df['sma_period'].max() + 2],
            tickformat='d',
        ),
        dict(
            label='Trail (pct)',
            values=df['trail_pct'],
            range=[df['trail_pct'].min() - 1, df['trail_pct'].max() + 1],
            tickformat='.1f',
        ),
        dict(
            label='Annual Return %',
            values=df['annual_return'].round(1),
            tickformat='.1f',
        ),
        dict(
            label='Sortino',
            values=df['sortino'].round(3),
            tickformat='.2f',
        ),
        dict(
            label='Max DD % (up=better)',
            values=df['max_drawdown'].round(1),
            tickformat='.1f',
        ),
        dict(
            label='Calmar',
            values=df['calmar'].round(3),
            tickformat='.2f',
        ),
        dict(
            label='Trades',
            values=df['total_trades'],
            tickformat='d',
        ),
        dict(
            label='Composite',
            values=df['composite'].round(3),
            tickformat='.3f',
        ),
        dict(
            label='Candidate (2=Primary)',
            values=df['cand'],
            range=[-0.1, 2.1],
            tickvals=[0, 1, 2],
            ticktext=['Other', 'Alt', 'Primary'],
        ),
    ],
    labelangle=0,
    unselected=dict(line=dict(opacity=0.04, color='gray')),
))

fig.update_layout(
    title=dict(
        text=(
            f'BTC SMA Strategy Space — Parallel Coordinates  '
            f'({len(df)} strategies)<br>'
            f'<sup>Drag axes to reorder  ·  Brush an axis to filter  ·  '
            f'Shift+brush for multiple ranges  ·  Double-click axis to clear  |  '
            f'Primary: SMA {PRIMARY_SMA} / trail {PRIMARY_TRAIL}%  ·  '
            f'Alt: SMA {SECONDARY_SMA} / trail {SECONDARY_TRAIL}%</sup>'
        ),
        font=dict(size=13, color='#1a1a1a'),
        x=0.5, xanchor='center', y=0.97,
    ),
    height=660,
    margin=dict(l=80, r=140, t=95, b=40),
    paper_bgcolor='white',
    plot_bgcolor='#fafafa',
)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
out_path = os.path.join(RESULTS_DIR, 'stage2_parallel_coordinates_interactive.html')
fig.write_html(
    out_path,
    include_plotlyjs='cdn',
    config={
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
    },
)
sz = os.path.getsize(out_path) / 1024
print(f"Saved → results/stage2_parallel_coordinates_interactive.html  ({sz:.0f} KB)")
print(f"\nUsage:")
print(f"  - Drag any axis header left/right to reorder axes")
print(f"  - Click and drag on an axis to create a filter range (brush)")
print(f"  - Shift+drag to add a second range on the same axis")
print(f"  - Double-click an axis label to clear its filter")
print(f"  - Use 'Candidate (2=Primary)' axis to isolate primary/alt strategies")
