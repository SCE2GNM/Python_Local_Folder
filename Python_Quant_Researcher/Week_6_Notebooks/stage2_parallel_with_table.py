#!/usr/bin/env python3
"""
Stage 2 — Parallel Coordinates with Linked Interactive Table
Self-contained HTML. No server. Opens directly in browser.

Interactions:
  Brush any axis        → table filters to matching strategies
  Click table row       → highlights that line in the chart (others dimmed)
  Click row again       → clears highlight
  Click column header   → sorts table
  Reset All Filters     → clears all brushes and highlights
"""

import os, json
import pandas as pd
import plotly.graph_objects as go

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, 'results')
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
os.makedirs(RESULTS_DIR, exist_ok=True)

PRIMARY_SMA   = 135;  PRIMARY_TRAIL   = 25.0
SECONDARY_SMA = 145;  SECONDARY_TRAIL = 20.0

# ── Load data ─────────────────────────────────────────────────────────────────
csv_path = os.path.join(DATA_DIR, 'stage2a_results_extended.csv')
df = pd.read_csv(csv_path).reset_index(drop=True)
print(f"Loaded {len(df)} strategies")

def cand_type(row):
    if row['sma_period'] == PRIMARY_SMA and abs(row['trail_pct'] - PRIMARY_TRAIL) < 0.1:
        return 2
    if row['sma_period'] == SECONDARY_SMA and abs(row['trail_pct'] - SECONDARY_TRAIL) < 0.1:
        return 1
    return 0

df['cand'] = df.apply(cand_type, axis=1)
df = df.sort_values('cand', ascending=True).reset_index(drop=True)
df['rank'] = df['composite'].rank(ascending=False, method='min').astype(int)
n = len(df)
print(f"  Primary: {(df['cand']==2).sum()}  |  Alt: {(df['cand']==1).sum()}")

# ── Parcoords figure ──────────────────────────────────────────────────────────
# Dimension index 9 is a hidden _pidx axis used for programmatic row highlighting
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
            thickness=18, len=0.75, y=0.5, yanchor='middle',
            tickfont=dict(size=10),
        ),
    ),
    dimensions=[
        dict(label='SMA Period', values=df['sma_period'].tolist(),
             range=[int(df['sma_period'].min())-2, int(df['sma_period'].max())+2],
             tickformat='d'),
        dict(label='Trail (pct)', values=df['trail_pct'].tolist(),
             range=[float(df['trail_pct'].min())-1, float(df['trail_pct'].max())+1],
             tickformat='.1f'),
        dict(label='Annual Return %', values=df['annual_return'].round(1).tolist(),
             tickformat='.1f'),
        dict(label='Sortino', values=df['sortino'].round(3).tolist(),
             tickformat='.2f'),
        dict(label='Max DD % (up=better)', values=df['max_drawdown'].round(1).tolist(),
             tickformat='.1f'),
        dict(label='Calmar', values=df['calmar'].round(3).tolist(),
             tickformat='.2f'),
        dict(label='Trades', values=df['total_trades'].tolist(),
             tickformat='d'),
        dict(label='Composite', values=df['composite'].round(3).tolist(),
             tickformat='.3f'),
        dict(label='Candidate', values=df['cand'].tolist(),
             range=[-0.1, 2.1], tickvals=[0, 1, 2],
             ticktext=['Other', 'Alt', 'Primary']),
        dict(label='_pidx', values=list(range(n)),
             range=[-1, n], visible=False),
    ],
    labelangle=0,
    unselected=dict(line=dict(opacity=0.04, color='gray')),
))

fig.update_layout(
    title=dict(
        text=(
            f'BTC SMA Strategy Space — Parallel Coordinates  ({n} strategies)<br>'
            f'<sup>Drag axes to reorder  ·  Brush axis to filter  ·  '
            f'Shift+brush for multiple ranges  ·  Double-click axis to clear  |  '
            f'Primary: SMA {PRIMARY_SMA} / trail {PRIMARY_TRAIL}%  ·  '
            f'Alt: SMA {SECONDARY_SMA} / trail {SECONDARY_TRAIL}%</sup>'
        ),
        font=dict(size=13, color='#1a1a1a'),
        x=0.5, xanchor='center', y=0.97,
    ),
    height=620,
    margin=dict(l=80, r=140, t=95, b=40),
    paper_bgcolor='white',
    plot_bgcolor='#fafafa',
)

# ── Data records for JS table ─────────────────────────────────────────────────
records = sorted([
    {
        'pidx':      int(i),
        'rank':      int(row['rank']),
        'sma':       int(row['sma_period']),
        'trail':     float(row['trail_pct']),
        'annual':    round(float(row['annual_return']), 1),
        'maxdd':     round(float(row['max_drawdown']), 1),
        'sortino':   round(float(row['sortino']), 3),
        'calmar':    round(float(row['calmar']), 3),
        'trades':    int(row['total_trades']),
        'composite': round(float(row['composite']), 3),
        'cand':      int(row['cand']),
    }
    for i, row in df.iterrows()
], key=lambda x: x['rank'])

fig_json_str = fig.to_json()

# ── HTML template ─────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>BTC SMA Strategy Space — {n} Strategies</title>
<script src="https://cdn.plot.ly/plotly-2.34.0.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #f0f2f5; color: #222; }}
#parcoords-wrap {{ background: white; border-bottom: 1px solid #ddd; }}
#controls {{
  display: flex; align-items: center; gap: 14px;
  padding: 8px 20px; background: #fff; border-bottom: 2px solid #e8e8e8;
}}
#sel-count {{ font-size: 13px; color: #555; }}
.btn {{
  font-size: 12px; padding: 4px 12px; border: 1px solid #b0b0b0;
  background: #f4f4f4; cursor: pointer; border-radius: 4px; color: #333;
}}
.btn:hover {{ background: #e8e8e8; }}
#hint {{ font-size: 12px; color: #aaa; margin-left: auto; font-style: italic; }}
#table-wrap {{ padding: 14px 20px 40px; overflow-x: auto; }}
table {{
  width: 100%; border-collapse: collapse; font-size: 13px;
  background: white; box-shadow: 0 1px 6px rgba(0,0,0,0.10);
  border-radius: 6px; overflow: hidden;
}}
thead {{ position: sticky; top: 0; z-index: 10; }}
th {{
  background: #2c3e50; color: #ecf0f1; padding: 9px 12px;
  text-align: right; cursor: pointer; user-select: none;
  white-space: nowrap; font-size: 12px; font-weight: 600;
}}
th:first-child {{ text-align: center; min-width: 48px; }}
th:hover {{ background: #3d5570; }}
th.s-asc::after  {{ content: ' ↑'; opacity: 0.9; }}
th.s-desc::after {{ content: ' ↓'; opacity: 0.9; }}
td {{
  padding: 6px 12px; text-align: right;
  border-bottom: 1px solid #efefef;
}}
td:first-child {{ text-align: center; font-weight: 700; color: #777; font-size: 12px; }}
tbody tr {{ cursor: pointer; }}
tbody tr:hover td {{ filter: brightness(0.95); }}
tbody tr.hl td {{ outline: 2px solid #e67e22; outline-offset: -2px; }}
tbody tr.hl td {{ background: rgba(230,126,34,0.10) !important; }}
tbody tr.hide {{ display: none; }}
.g {{ background: #eafaf1; }}
.a {{ background: #fef9e7; }}
.r {{ background: #fdf2f0; }}
.badge {{
  display: inline-block; padding: 2px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 700;
}}
.bp {{ background: #27ae60; color: #fff; }}
.ba {{ background: #e67e22; color: #fff; }}
</style>
</head>
<body>

<div id="parcoords-wrap">
  <div id="pc"></div>
</div>

<div id="controls">
  <span id="sel-count">{n} of {n} strategies</span>
  <button class="btn" id="reset-btn">Reset All Filters</button>
  <button class="btn" id="clr-btn" style="display:none">Clear Row Highlight</button>
  <span id="hint">Click a table row to isolate that strategy in the chart</span>
</div>

<div id="table-wrap">
  <table id="tbl">
    <thead>
      <tr>
        <th data-col="rank" class="s-asc">Rank</th>
        <th data-col="sma">SMA</th>
        <th data-col="trail">Trail%</th>
        <th data-col="annual">Annual%</th>
        <th data-col="maxdd">MaxDD%</th>
        <th data-col="sortino">Sortino</th>
        <th data-col="calmar">Calmar</th>
        <th data-col="trades">Trades</th>
        <th data-col="composite">Composite</th>
        <th data-col="cand">Type</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
</div>

<script>
var DATA = {json.dumps(records)};
var FIG  = {fig_json_str};
var N    = {n};
var PIDX = 9;  // hidden _pidx dimension index

var gd, hlPidx = null, sCol = 'rank', sDir = 1;

window.addEventListener('DOMContentLoaded', function() {{
  gd = document.getElementById('pc');
  Plotly.newPlot(gd, FIG.data, FIG.layout, {{
    displayModeBar: true, displaylogo: false, responsive: true,
    modeBarButtonsToRemove: ['lasso2d','select2d']
  }});
  gd.on('plotly_restyle', renderTable);
  renderTable();
  document.getElementById('reset-btn').addEventListener('click', resetAll);
  document.getElementById('clr-btn').addEventListener('click', clearHL);
  document.querySelectorAll('th[data-col]').forEach(function(th) {{
    th.addEventListener('click', function() {{
      var c = this.getAttribute('data-col');
      if (sCol === c) {{ sDir *= -1; }}
      else {{ sCol = c; sDir = (c==='rank'||c==='maxdd') ? 1 : -1; }}
      document.querySelectorAll('th[data-col]').forEach(function(h) {{
        h.className = '';
      }});
      this.className = sDir === 1 ? 's-asc' : 's-desc';
      renderTable();
    }});
  }});
}});

function checkCR(val, cr) {{
  if (!cr) return true;
  if (typeof cr[0] === 'number') return val >= cr[0] && val <= cr[1];
  for (var i = 0; i < cr.length; i++) {{
    if (val >= cr[i][0] && val <= cr[i][1]) return true;
  }}
  return false;
}}

function passes(row) {{
  if (!gd || !gd.data || !gd.data[0]) return true;
  var dims = gd.data[0].dimensions;
  for (var d = 0; d < dims.length; d++) {{
    if (d === PIDX) continue;
    var cr = dims[d].constraintrange;
    if (!cr) continue;
    if (!checkCR(dims[d].values[row.pidx], cr)) return false;
  }}
  return true;
}}

function compCls(c) {{ return c >= 0.85 ? 'g' : c >= 0.70 ? 'a' : 'r'; }}

function badge(cand) {{
  if (cand === 2) return '<span class="badge bp">Primary</span>';
  if (cand === 1) return '<span class="badge ba">Alt</span>';
  return '<span style="color:#bbb">—</span>';
}}

function renderTable() {{
  var rows = DATA.slice().sort(function(a, b) {{
    var va = a[sCol], vb = b[sCol];
    return sDir * (va < vb ? -1 : va > vb ? 1 : 0);
  }});
  var tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  var vis = 0;
  rows.forEach(function(r) {{
    var ok = passes(r);
    if (ok) vis++;
    var cls = compCls(r.composite);
    if (!ok)           cls += ' hide';
    if (hlPidx === r.pidx) cls += ' hl';
    var tr = document.createElement('tr');
    tr.className = cls;
    tr.setAttribute('data-pidx', r.pidx);
    tr.innerHTML =
      '<td>' + r.rank + '</td>' +
      '<td>' + r.sma + '</td>' +
      '<td>' + r.trail.toFixed(1) + '%</td>' +
      '<td>' + r.annual.toFixed(1) + '%</td>' +
      '<td>' + r.maxdd.toFixed(1) + '%</td>' +
      '<td>' + r.sortino.toFixed(3) + '</td>' +
      '<td>' + r.calmar.toFixed(3) + '</td>' +
      '<td>' + r.trades + '</td>' +
      '<td>' + r.composite.toFixed(3) + '</td>' +
      '<td>' + badge(r.cand) + '</td>';
    tr.addEventListener('click', function() {{
      toggleHL(parseInt(this.getAttribute('data-pidx')));
    }});
    tbody.appendChild(tr);
  }});
  document.getElementById('sel-count').textContent = vis + ' of ' + N + ' strategies';
}}

function toggleHL(pidx) {{
  if (hlPidx === pidx) {{ clearHL(); return; }}
  hlPidx = pidx;
  document.getElementById('clr-btn').style.display = '';
  var upd = {{}};
  upd['dimensions[' + PIDX + '].constraintrange'] = [[pidx - 0.1, pidx + 0.1]];
  Plotly.restyle(gd, upd, [0]);
}}

function clearHL() {{
  hlPidx = null;
  document.getElementById('clr-btn').style.display = 'none';
  var upd = {{}};
  upd['dimensions[' + PIDX + '].constraintrange'] = null;
  Plotly.restyle(gd, upd, [0]);
}}

function resetAll() {{
  hlPidx = null;
  document.getElementById('clr-btn').style.display = 'none';
  if (!gd || !gd.data || !gd.data[0]) return;
  var dims = gd.data[0].dimensions;
  var upd = {{}};
  for (var d = 0; d < dims.length; d++) {{
    upd['dimensions[' + d + '].constraintrange'] = null;
  }}
  Plotly.restyle(gd, upd, [0]);
}}
</script>
</body>
</html>"""

out_path = os.path.join(RESULTS_DIR, 'stage2_parallel_with_table.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

sz = os.path.getsize(out_path) / 1024
print(f"\nSaved → results/stage2_parallel_with_table.html  ({sz:.0f} KB)")
print(f"\nInteractions:")
print(f"  Brush axis           → table filters to matching strategies")
print(f"  Click table row      → isolates that line in chart (others dimmed)")
print(f"  Click row again      → clears row highlight")
print(f"  Click column header  → sorts table by that column")
print(f"  Reset All Filters    → clears all brushes and highlights")
print(f"\nComposite colour bands: green ≥ 0.85 · amber ≥ 0.70 · red < 0.70")
