# Stage 2 — Interactive Parallel Coordinates (Plotly HTML)
# Saves: Week_6_Notebooks/results/stage2_parallel_coordinates_interactive.html
#
# Each line = one (SMA, trail%) strategy from the extended Stage 2a grid (171 combos)
# Axes: Annual%, Sortino, MaxDD (↑ = less negative = better), Calmar, Trades
# Colour: Annual Return % (green = high, red = low)
# Hover: SMA period, trail%, Annual%, MaxDD%, Sortino, Calmar, Trades, composite
# Click a line to highlight it; click again (or double-click) to reset

import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)

DIV_ID = 'btc-sma-parcoords'

PRIMARY_SMA     = 135;  PRIMARY_TRAIL   = 25.0
SECONDARY_SMA   = 145;  SECONDARY_TRAIL = 20.0

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
csv_path = os.path.join(DATA_DIR, 'stage2a_results_extended.csv')
df = pd.read_csv(csv_path).reset_index(drop=True)
print(f"Loaded {len(df)} rows")

# Keep composite from CSV (normalised within the 171-combo grid)
# annual_return and max_drawdown already stored as % (e.g. 46.9, -15.1)

# ---------------------------------------------------------------------------
# Axes: order, raw column, display label, value format
# ---------------------------------------------------------------------------
AXES = [
    ('annual_return', 'Annual Return %',            '.1f', '%'),
    ('sortino',       'Sortino',                    '.3f', ''),
    ('max_drawdown',  'Max DD %<br>↑ = less negative', '.1f', '%'),
    ('calmar',        'Calmar',                     '.3f', ''),
    ('total_trades',  'Trades',                     '.0f', ''),
]
N_AXES = len(AXES)
X_POS  = list(range(N_AXES))

# Normalise each axis to [0, 1] for display
# MaxDD: all-negative; minmax gives most-negative → 0 (bottom), least-negative → 1 (top)  ✓
col_min = {col: df[col].min() for col, *_ in AXES}
col_max = {col: df[col].max() for col, *_ in AXES}

def norm_col(col):
    lo, hi = col_min[col], col_max[col]
    return (df[col] - lo) / (hi - lo) if hi > lo else pd.Series(0.5, index=df.index)

df_n = pd.DataFrame({col: norm_col(col) for col, *_ in AXES})

# ---------------------------------------------------------------------------
# Line colours: RdYlGn by annual return
# ---------------------------------------------------------------------------
ann_min = col_min['annual_return']
ann_max = col_max['annual_return']
ann_pct_norm = ((df['annual_return'] - ann_min) / (ann_max - ann_min)).tolist()
line_colors = px.colors.sample_colorscale('RdYlGn', ann_pct_norm)

# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
fig = go.Figure()

# -- Invisible dummy trace for the colorbar --------------------------------
fig.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(
        colorscale='RdYlGn',
        showscale=True,
        cmin=ann_min,
        cmax=ann_max,
        color=[ann_min, ann_max],
        colorbar=dict(
            title=dict(text='Annual<br>Return %', side='right', font=dict(size=11)),
            thickness=18,
            len=0.72,
            y=0.52,
            yanchor='middle',
            ticksuffix='%',
            tickfont=dict(size=10),
        ),
    ),
    hoverinfo='skip',
    showlegend=False,
))

# -- One Scatter trace per strategy ----------------------------------------
for idx in df.index:
    row   = df.loc[idx]
    is_pri = bool(row['sma_period'] == PRIMARY_SMA   and abs(row['trail_pct'] - PRIMARY_TRAIL)   < 0.1)
    is_sec = bool(row['sma_period'] == SECONDARY_SMA and abs(row['trail_pct'] - SECONDARY_TRAIL) < 0.1)

    y_vals = [df_n.loc[idx, col] for col, *_ in AXES]

    # Repeat hover data once per axis point so tooltip fires everywhere along the line
    low_n_flag = ' [!low n]' if str(row['low_trades']).strip().lower() == 'true' else ''
    label = (f"SMA {int(row['sma_period'])} / trail {row['trail_pct']:.1f}%"
             + (' ★ PRIMARY'   if is_pri  else '')
             + (' ● SECONDARY' if is_sec  else '')
             + low_n_flag)

    cd_row = [
        int(row['sma_period']),  # 0
        row['trail_pct'],        # 1
        row['annual_return'],    # 2
        row['max_drawdown'],     # 3
        row['sortino'],          # 4
        row['calmar'],           # 5
        int(row['total_trades']),# 6
        row['composite'],        # 7
        label,                   # 8
    ]
    customdata = [cd_row] * N_AXES

    base_lw = 3.5 if is_pri else (2.8 if is_sec else 1.4)
    base_op = 0.95 if (is_pri or is_sec) else 0.60

    fig.add_trace(go.Scatter(
        x=X_POS,
        y=y_vals,
        mode='lines',
        line=dict(color=line_colors[idx], width=base_lw),
        opacity=base_op,
        customdata=customdata,
        hovertemplate=(
            '<b>%{customdata[8]}</b><br>'
            '<br>'
            'Annual Return: <b>%{customdata[2]:.1f}%</b><br>'
            'Max Drawdown: %{customdata[3]:.1f}%<br>'
            'Sortino: %{customdata[4]:.3f}<br>'
            'Calmar: %{customdata[5]:.3f}<br>'
            'Trades: %{customdata[6]}<br>'
            'Composite: %{customdata[7]:.3f}'
            '<extra></extra>'
        ),
        name=label,
        showlegend=(is_pri or is_sec),
        meta={'base_lw': float(base_lw), 'base_op': float(base_op)},
    ))

# ---------------------------------------------------------------------------
# Axis shapes (vertical lines) and annotations
# ---------------------------------------------------------------------------
shapes = []
for j in range(N_AXES):
    shapes.append(dict(
        type='line', layer='above',
        x0=j, x1=j, y0=0.0, y1=1.0,
        line=dict(color='#888888', width=1.6),
    ))

annotations = []
for j, (col, label, fmt, suffix) in enumerate(AXES):
    lo = col_min[col]
    hi = col_max[col]

    # Format bottom (lo) and top (hi) tick labels
    if col in ('annual_return', 'max_drawdown'):
        lo_str = f'{lo:.1f}%'
        hi_str = f'{hi:.1f}%'
    elif col == 'total_trades':
        lo_str = f'{int(lo)}'
        hi_str = f'{int(hi)}'
    else:
        lo_str = f'{lo:.2f}'
        hi_str = f'{hi:.2f}'

    # Axis label (above the chart)
    annotations.append(dict(
        x=j, y=1.13, xref='x', yref='y',
        text=f'<b>{label}</b>',
        showarrow=False,
        font=dict(size=11, color='#222222'),
        xanchor='center', yanchor='bottom',
        align='center',
    ))
    # Min value (bottom)
    annotations.append(dict(
        x=j, y=-0.04, xref='x', yref='y',
        text=lo_str,
        showarrow=False,
        font=dict(size=9, color='#666666'),
        xanchor='center', yanchor='top',
    ))
    # Max value (top)
    annotations.append(dict(
        x=j, y=1.04, xref='x', yref='y',
        text=hi_str,
        showarrow=False,
        font=dict(size=9, color='#666666'),
        xanchor='center', yanchor='bottom',
    ))

fig.update_layout(
    shapes=shapes,
    annotations=annotations,
    title=dict(
        text='BTC SMA Strategy Space — Interactive Parallel Coordinates'
             '<br><sup>Click a line to highlight  ·  Click again to reset  ·  '
             'Hover for full metrics  ·  171 strategies (SMA 80–170 × trail 5–25%)</sup>',
        font=dict(size=15, color='#1a1a1a'),
        x=0.5, xanchor='center', y=0.97,
    ),
    xaxis=dict(
        range=[-0.45, N_AXES - 0.55],
        showgrid=False, zeroline=False,
        showticklabels=False,
        showline=False,
    ),
    yaxis=dict(
        range=[-0.12, 1.22],
        showgrid=False, zeroline=False,
        showticklabels=False,
        showline=False,
    ),
    hovermode='closest',
    plot_bgcolor='#fafafa',
    paper_bgcolor='white',
    height=620,
    width=1150,
    margin=dict(l=40, r=110, t=90, b=50),
    legend=dict(
        title=dict(text='Candidates', font=dict(size=11)),
        x=1.10, y=0.98,
        xanchor='left', yanchor='top',
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#aaaaaa',
        borderwidth=1,
        font=dict(size=10),
    ),
)

# ---------------------------------------------------------------------------
# Click-to-highlight JavaScript
# ---------------------------------------------------------------------------
# Reads each trace's initial opacity and line.width from plotDiv.data
# so the reset correctly restores per-trace base values.
click_js = f"""
(function() {{
    var plotDiv = document.getElementById('{DIV_ID}');
    if (!plotDiv) {{ return; }}

    // Cache base state from trace data on first load
    var baseState = plotDiv.data.map(function(t) {{
        return {{
            op: typeof t.opacity === 'number' ? t.opacity : 0.60,
            lw: (t.line && typeof t.line.width === 'number') ? t.line.width : 1.4
        }};
    }});

    var highlighted = null;

    function resetAll() {{
        var ops = baseState.map(function(s) {{ return s.op; }});
        var lws = baseState.map(function(s) {{ return s.lw; }});
        Plotly.restyle(plotDiv, {{'opacity': ops, 'line.width': lws}});
        highlighted = null;
    }}

    plotDiv.on('plotly_click', function(evt) {{
        if (!evt || !evt.points || evt.points.length === 0) return;
        var clicked = evt.points[0].curveNumber;

        if (highlighted === clicked) {{
            resetAll();
            return;
        }}

        var n   = plotDiv.data.length;
        var ops = [];
        var lws = [];
        for (var i = 0; i < n; i++) {{
            if (i === clicked) {{
                ops.push(1.0);
                lws.push(Math.max(baseState[i].lw, 3.5));
            }} else {{
                ops.push(0.06);
                lws.push(Math.min(baseState[i].lw, 0.6));
            }}
        }}
        Plotly.restyle(plotDiv, {{'opacity': ops, 'line.width': lws}});
        highlighted = clicked;
    }});

    plotDiv.on('plotly_doubleclick', function() {{
        resetAll();
        return false;   // prevent default zoom-reset
    }});
}})();
"""

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
out_path = os.path.join(RESULTS_DIR, 'stage2_parallel_coordinates_interactive.html')
fig.write_html(
    out_path,
    div_id=DIV_ID,
    full_html=True,
    include_plotlyjs='cdn',
    post_script=click_js,
    config={'displayModeBar': True, 'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']},
)
print(f"Saved → {out_path}")
print(f"  {len(df)} strategy lines  |  click-to-highlight enabled")
