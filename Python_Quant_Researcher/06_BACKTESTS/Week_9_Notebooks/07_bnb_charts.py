"""
07_bnb_charts.py — Phase 6 Visualisation Package
BNB Donchian period=20, stop=5%, SMA-120 regime filter
Week 9 | 2026-06-01

Produces seven interactive Plotly HTML charts:
  Chart 1: Interactive equity curve (strategy vs B&H, log scale, entry/exit markers)
  Chart 2: Year-by-year equity panels (normalised to 1.0 per year)
  Chart 3: Trade return distribution histogram
  Chart 4: Underwater curve (drawdown from equity peak)
  Chart 5: Walk-forward OOS bar chart
  Chart 6: Annual returns comparison vs B&H
  Chart 7: Stability heatmap (post-break PF, interactive)

All files saved to 06_BACKTESTS/Week_9_Notebooks/charts/
"""

import importlib.util
import os
import warnings
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")

BASE       = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(BASE, "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

spec = importlib.util.spec_from_file_location(
    "ag", os.path.join(BASE, "01_altcoin_discovery_grid.py")
)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

TICKER     = "BNB-USD"
PERIOD     = 20
STOP_PCT   = 0.05
SMA_PERIOD = 120
COSTS      = g.COSTS
BREAK_TS   = pd.Timestamp("2024-01-01")

BLUE   = "#1f77b4"
GREY   = "#7f7f7f"
GREEN  = "#2ca02c"
RED    = "#d62728"
ORANGE = "#ff7f0e"


# ══════════════════════════════════════════════════════════════════════════════
# DATA — STRATEGY + EQUITY CURVE
# ══════════════════════════════════════════════════════════════════════════════

def run_strategy(df):
    """
    BNB Donchian period=20, stop=5%, SMA-120, Exit A.
    Returns (trades, eq, n_days) with enriched trade dicts including
    entry_price, exit_price, exit_type.
    """
    closes    = df["close"].values
    highs     = df["high"].values
    lows      = df["low"].values
    N         = len(df)
    n_days    = (df.index[-1] - df.index[0]).days

    h_ser     = pd.Series(highs)
    l_ser     = pd.Series(lows)
    entry_max = h_ser.shift(1).rolling(PERIOD).max().values
    exit_min  = l_ser.shift(1).rolling(PERIOD).min().values
    sma_vals  = pd.Series(closes).rolling(SMA_PERIOD).mean().values

    trades = []
    in_pos = False
    ei = epx = peak = 0

    for i in range(1, N):
        if np.isnan(entry_max[i]) or np.isnan(exit_min[i]) or np.isnan(sma_vals[i]):
            continue
        if not in_pos:
            if closes[i] > entry_max[i] and closes[i] > sma_vals[i]:
                in_pos = True
                ei, epx, peak = i, closes[i], closes[i]
        else:
            stop_lvl = peak * (1 - STOP_PCT)
            if lows[i] <= stop_lvl:
                trades.append({"ei": ei, "xi": i,
                               "ret": (stop_lvl - epx) / epx,
                               "entry_price": epx, "exit_price": stop_lvl,
                               "exit_type": "stop"})
                in_pos = False
            elif lows[i] <= exit_min[i]:
                trades.append({"ei": ei, "xi": i,
                               "ret": (exit_min[i] - epx) / epx,
                               "entry_price": epx, "exit_price": exit_min[i],
                               "exit_type": "channel"})
                in_pos = False
            else:
                if closes[i] > peak:
                    peak = closes[i]

    if in_pos:
        trades.append({"ei": ei, "xi": N - 1,
                       "ret": (closes[-1] - epx) / epx,
                       "entry_price": epx, "exit_price": closes[-1],
                       "exit_type": "end"})

    eq = g.build_equity(trades, closes, N)
    return trades, eq, n_days


def build_daily_data(df, trades, eq):
    """Build daily arrays for hover data and coloring."""
    N          = len(df)
    position   = np.full(N, "FLAT", dtype=object)
    days_held  = np.zeros(N, dtype=int)
    eq_bh      = df["close"].values / df["close"].values[0]

    for t in trades:
        for i in range(t["ei"], t["xi"] + 1):
            position[i]  = "LONG"
            days_held[i] = i - t["ei"]

    run_max_s  = np.maximum.accumulate(eq)
    dd_strat   = (eq - run_max_s) / run_max_s
    run_max_bh = np.maximum.accumulate(eq_bh)
    dd_bh      = (eq_bh - run_max_bh) / run_max_bh

    return eq_bh, dd_strat, dd_bh, position, days_held


def year_returns(df, eq, eq_bh):
    """Per-calendar-year returns for strategy and B&H."""
    years = sorted(df.index.year.unique())
    results = []
    for yr in years:
        mask = df.index.year == yr
        idx  = np.where(mask)[0]
        if len(idx) < 2:
            continue
        s, e = idx[0], idx[-1]
        strat_yr  = float(eq[e]  / eq[s]  - 1)
        bh_yr     = float(eq_bh[e] / eq_bh[s] - 1)
        results.append({"year": yr, "strat": strat_yr, "bh": bh_yr})
    return results


def find_worst_drawdowns(dates, dd, n=3):
    """Find the n deepest unique drawdown troughs."""
    troughs = []
    seen    = set()
    idx_sorted = np.argsort(dd)   # most negative first
    for idx in idx_sorted:
        if dd[idx] >= -0.05:
            break
        # Ensure at least 30 days from existing trough
        if all(abs(idx - s) > 30 for s in seen):
            troughs.append((dates[idx], float(dd[idx])))
            seen.add(idx)
        if len(troughs) == n:
            break
    return troughs


# ══════════════════════════════════════════════════════════════════════════════
# CHART 1 — INTERACTIVE EQUITY CURVE
# ══════════════════════════════════════════════════════════════════════════════

def chart_equity_curve(df, trades, eq, eq_bh, dd_strat, dd_bh, position, days_held):
    dates = df.index
    N     = len(dates)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.68, 0.32],
        vertical_spacing=0.04,
        subplot_titles=("Portfolio Value (log scale — normalised to 1.0 at start)",
                        "Drawdown from Equity Peak"),
    )

    # ── Row 1: equity curves ──────────────────────────────────────────────────
    hov_strat = [
        f"<b>{d.strftime('%Y-%m-%d')}</b><br>"
        f"Portfolio: {v:.3f}×<br>"
        f"Drawdown: {dd:.1%}<br>"
        f"Status: {pos}<br>"
        f"{'Days held: ' + str(dh) if pos == 'LONG' else ''}"
        for d, v, dd, pos, dh in zip(dates, eq, dd_strat, position, days_held)
    ]

    fig.add_trace(go.Scatter(
        x=dates, y=eq,
        name="BNB Donchian (SMA-120)",
        line=dict(color=BLUE, width=2),
        hovertext=hov_strat, hoverinfo="text",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=dates, y=eq_bh,
        name="BNB Buy-and-Hold",
        line=dict(color=GREY, width=1.5, dash="dash"),
        hovertemplate="%{x|%Y-%m-%d}<br>B&H: %{y:.3f}×<extra></extra>",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[dates[0], dates[-1]], y=[1.0, 1.0],
        name="Cash (flat)",
        line=dict(color="lightgrey", width=1, dash="dot"),
        hoverinfo="skip",
    ), row=1, col=1)

    # Entry markers
    entry_x = [dates[t["ei"]] for t in trades]
    entry_y = [eq[t["ei"]]    for t in trades]
    entry_p = [t["entry_price"] for t in trades]
    fig.add_trace(go.Scatter(
        x=entry_x, y=entry_y, mode="markers",
        name="Entry",
        marker=dict(symbol="triangle-up", size=10, color=GREEN),
        hovertemplate="Entry<br>%{x|%Y-%m-%d}<br>Price: $%{customdata:.2f}<extra></extra>",
        customdata=entry_p,
    ), row=1, col=1)

    # Exit markers
    exit_x = [dates[t["xi"]] for t in trades]
    exit_y = [eq[t["xi"]]    for t in trades]
    exit_p = [t["exit_price"] for t in trades]
    exit_l = [f"{t['exit_type']} ({t['ret']:+.1%})" for t in trades]
    fig.add_trace(go.Scatter(
        x=exit_x, y=exit_y, mode="markers",
        name="Exit",
        marker=dict(symbol="triangle-down", size=10, color=RED),
        hovertemplate="Exit (%{customdata})<br>%{x|%Y-%m-%d}<br>Price: $%{text:.2f}<extra></extra>",
        customdata=exit_l, text=exit_p,
    ), row=1, col=1)

    # ── Row 2: drawdown ───────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=dates, y=dd_strat * 100,
        name="Strategy DD",
        line=dict(color=BLUE, width=1.5),
        hovertemplate="%{x|%Y-%m-%d}<br>Strategy DD: %{y:.1f}%<extra></extra>",
        fill="tozeroy", fillcolor="rgba(31,119,180,0.12)",
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=dates, y=dd_bh * 100,
        name="B&H DD",
        line=dict(color=GREY, width=1, dash="dash"),
        hovertemplate="%{x|%Y-%m-%d}<br>B&H DD: %{y:.1f}%<extra></extra>",
    ), row=2, col=1)

    # ── Regime break line ─────────────────────────────────────────────────────
    for row in [1, 2]:
        fig.add_vline(x=BREAK_TS, line_width=1.5, line_dash="dash",
                      line_color="black", row=row, col=1)
    fig.add_annotation(
        x=BREAK_TS, y=1.02, xref="x", yref="paper",
        text="Jan 2024<br>Regime break", showarrow=False,
        font=dict(size=10, color="black"), xanchor="left",
    )

    fig.update_yaxes(type="log", title_text="Portfolio value (×, log)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_layout(
        title=dict(text="BNB Donchian period=20, stop=5%, SMA-120 — Full Backtest 2018–2026",
                   font=dict(size=16)),
        height=700, hovermode="x unified",
        legend=dict(orientation="h", y=-0.12),
        template="plotly_white",
    )

    path = os.path.join(CHARTS_DIR, "bnb_donchian_equity_curve.html")
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# CHART 2 — YEAR-BY-YEAR EQUITY PANELS
# ══════════════════════════════════════════════════════════════════════════════

def chart_yearly_panels(df, eq, eq_bh, yr_returns):
    years = [r["year"] for r in yr_returns]
    ncols = 3
    nrows = int(np.ceil(len(years) / ncols))

    titles = []
    for r in yr_returns:
        pct = r["strat"]
        titles.append(f"{r['year']}  |  Strategy {pct:+.1%}")

    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=titles,
                        vertical_spacing=0.10, horizontal_spacing=0.06)

    dates = df.index
    for panel_idx, r in enumerate(yr_returns):
        yr   = r["year"]
        row  = panel_idx // ncols + 1
        col  = panel_idx %  ncols + 1
        mask = dates.year == yr
        idx  = np.where(mask)[0]
        if len(idx) < 2:
            continue
        s, e    = idx[0], idx[-1]
        d_yr    = dates[s:e+1]
        eq_s_yr = eq[s:e+1]   / eq[s]
        eq_b_yr = eq_bh[s:e+1] / eq_bh[s]

        fig.add_trace(go.Scatter(
            x=d_yr, y=eq_s_yr,
            name="Strategy" if panel_idx == 0 else None,
            showlegend=(panel_idx == 0),
            line=dict(color=BLUE, width=2),
        ), row=row, col=col)
        fig.add_trace(go.Scatter(
            x=d_yr, y=eq_b_yr,
            name="B&H" if panel_idx == 0 else None,
            showlegend=(panel_idx == 0),
            line=dict(color=GREY, width=1.5, dash="dash"),
        ), row=row, col=col)
        # Unity reference line
        fig.add_hline(y=1.0, line_width=0.8, line_dash="dot",
                      line_color="lightgrey", row=row, col=col)

    fig.update_layout(
        title="BNB Donchian — Year-by-Year Performance (normalised to 1.0 at Jan 1 each year)",
        height=nrows * 220, template="plotly_white",
        legend=dict(orientation="h", y=-0.06),
    )

    path = os.path.join(CHARTS_DIR, "bnb_donchian_yearly_panels.html")
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# CHART 3 — TRADE RETURN DISTRIBUTION
# ══════════════════════════════════════════════════════════════════════════════

def chart_trade_distribution(trades):
    rets   = [t["ret"] * 100 for t in trades]
    wins   = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]

    avg_win  = float(np.mean(wins))   if wins   else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    pf       = (sum(wins) / abs(sum(losses))) if losses else float("inf")
    wr       = len(wins) / len(rets) if rets else 0.0

    nbins = 25
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=wins, name="Wins", nbinsx=nbins // 2,
        marker_color=GREEN, opacity=0.8,
        hovertemplate="Return bin: %{x:.1f}%<br>Count: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Histogram(
        x=losses, name="Losses", nbinsx=nbins // 2,
        marker_color=RED, opacity=0.8,
        hovertemplate="Return bin: %{x:.1f}%<br>Count: %{y}<extra></extra>",
    ))
    fig.add_vline(x=avg_win,  line_dash="dash", line_color=GREEN, line_width=1.5,
                  annotation_text=f"Avg win: +{avg_win:.1f}%",
                  annotation_position="top right")
    fig.add_vline(x=avg_loss, line_dash="dash", line_color=RED, line_width=1.5,
                  annotation_text=f"Avg loss: {avg_loss:.1f}%",
                  annotation_position="top left")

    stats_text = (f"Trades: {len(rets)}  |  Win rate: {wr:.1%}  |  "
                  f"Avg win: +{avg_win:.1f}%  |  Avg loss: {avg_loss:.1f}%  |  "
                  f"PF: {pf:.2f}")
    fig.update_layout(
        title=f"BNB Donchian — Trade Return Distribution<br><sup>{stats_text}</sup>",
        xaxis_title="Trade return (%)",
        yaxis_title="Count",
        barmode="overlay",
        template="plotly_white",
        height=450,
        legend=dict(orientation="h", y=-0.15),
    )

    path = os.path.join(CHARTS_DIR, "bnb_donchian_trade_distribution.html")
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# CHART 4 — UNDERWATER CURVE
# ══════════════════════════════════════════════════════════════════════════════

def chart_underwater(df, dd_strat):
    dates  = df.index
    dd_pct = dd_strat * 100

    worst3 = find_worst_drawdowns(dates, dd_strat, n=3)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=dd_pct,
        name="Drawdown",
        line=dict(color=RED, width=1.5),
        fill="tozeroy",
        fillcolor="rgba(214,39,40,0.25)",
        hovertemplate="%{x|%Y-%m-%d}<br>Drawdown: %{y:.1f}%<extra></extra>",
    ))

    # Reference lines
    for lvl, color, label in [(-10, ORANGE, "−10%"), (-20, RED, "−20%")]:
        fig.add_hline(y=lvl, line_dash="dot", line_color=color, line_width=1,
                      annotation_text=label, annotation_position="right")

    # Worst drawdown annotations
    for d, depth in worst3:
        fig.add_annotation(
            x=d, y=depth * 100, xref="x", yref="y",
            text=f"{depth:.1%}<br>{d.strftime('%b %Y')}",
            showarrow=True, arrowhead=2, arrowcolor=RED,
            font=dict(size=10, color=RED), bgcolor="white", opacity=0.85,
            ax=0, ay=30,
        )

    # Regime break line
    fig.add_vline(x=BREAK_TS, line_width=1.5, line_dash="dash", line_color="black")
    fig.add_annotation(
        x=BREAK_TS, y=-2, xref="x", yref="y",
        text="Jan 2024", showarrow=False, font=dict(size=10), xanchor="left",
    )

    fig.update_layout(
        title="BNB Donchian — Drawdown from Equity Peak (Underwater Curve)",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        template="plotly_white",
        height=420,
        showlegend=False,
    )

    path = os.path.join(CHARTS_DIR, "bnb_donchian_underwater.html")
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# CHART 5 — WALK-FORWARD BAR CHART
# ══════════════════════════════════════════════════════════════════════════════

def chart_walkforward():
    wf_csv = os.path.join(BASE, "bnb_walkforward_results.csv")
    if not os.path.exists(wf_csv):
        print(f"  Walk-forward CSV not found: {wf_csv}")
        return None

    df_wf = pd.read_csv(wf_csv)
    # Filter for per=20 stop=5%
    df_wf = df_wf[df_wf["params"].str.contains("per=20", na=False)].copy()
    df_wf = df_wf.sort_values("window").reset_index(drop=True)

    # Separate pre and post Jan 2024
    df_wf["oos_start_dt"] = pd.to_datetime(df_wf["oos_start"])
    df_pre  = df_wf[df_wf["oos_start_dt"] <  BREAK_TS]
    df_post = df_wf[df_wf["oos_start_dt"] >= BREAK_TS]

    def make_bars(df_sub, show_legend_base):
        traces = []
        for _, row in df_sub.iterrows():
            pf    = row["pf"]
            label = f"W{int(row['window'])}<br>{row['oos_start']}→{row['oos_end']}"
            if pd.isna(pf):
                color, pf_str = "lightgrey", "No trades"
            elif pf >= 1.0:
                color, pf_str = GREEN, f"PF {pf:.2f}"
            else:
                color, pf_str = RED, f"PF {pf:.2f}"

            partial_note = " (partial)" if row.get("partial", False) else ""
            traces.append(dict(
                x=[label],
                y=[pf if pd.notna(pf) else 0],
                color=color,
                hover=f"<b>Window {int(row['window'])}</b>{partial_note}<br>"
                      f"OOS: {row['oos_start']} → {row['oos_end']}<br>"
                      f"Trades: {int(row['n_trades'])}<br>"
                      f"Ann ret: {row['ann_ret']:+.1%}<br>"
                      f"{pf_str}",
            ))
        return traces

    pre_bars  = make_bars(df_pre,  True)
    post_bars = make_bars(df_post, False)

    fig = go.Figure()
    for d in pre_bars:
        fig.add_trace(go.Bar(x=d["x"], y=d["y"],
                             marker_color=d["color"],
                             hovertext=d["hover"], hoverinfo="text",
                             showlegend=False))
    for d in post_bars:
        fig.add_trace(go.Bar(x=d["x"], y=d["y"],
                             marker_color=d["color"],
                             hovertext=d["hover"], hoverinfo="text",
                             showlegend=False))

    fig.add_hline(y=1.0, line_dash="dash", line_color="black", line_width=1.5,
                  annotation_text="PF=1.0 (breakeven)", annotation_position="right")
    fig.add_hline(y=2.0, line_dash="dot",  line_color=GREEN,  line_width=1,
                  annotation_text="PF=2.0 (viable)",   annotation_position="right")

    # Mark pre/post split
    n_pre = len(pre_bars)
    if n_pre > 0 and len(post_bars) > 0:
        fig.add_vline(x=n_pre - 0.5, line_dash="dash", line_color="black",
                      line_width=2)
        fig.add_annotation(x=n_pre - 0.5, y=0.02, xref="x", yref="paper",
                           text="← Pre-2024 | Post-2024 →",
                           showarrow=False, font=dict(size=10), xanchor="center")

    n_profitable = sum(1 for d in pre_bars + post_bars
                       if d["color"] == GREEN)
    n_total      = len(pre_bars) + len(post_bars)

    fig.update_layout(
        title=(f"BNB Donchian (per=20/stop=5%) — Walk-Forward OOS Results<br>"
               f"<sup>{n_profitable}/{n_total} windows profitable (PF≥1.0)</sup>"),
        xaxis_title="OOS Window",
        yaxis_title="OOS Profit Factor",
        template="plotly_white",
        height=450,
        bargap=0.15,
    )

    path = os.path.join(CHARTS_DIR, "bnb_donchian_walkforward.html")
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# CHART 6 — ANNUAL RETURNS COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

def chart_annual_returns(yr_returns):
    years    = [r["year"] for r in yr_returns]
    strat_r  = [r["strat"] * 100 for r in yr_returns]
    bh_r     = [r["bh"]   * 100 for r in yr_returns]

    strat_colors = [GREEN if v >= 0 else "#c44e52" for v in strat_r]
    bh_colors    = ["#aec7e8" if v >= 0 else "#c7c7c7" for v in bh_r]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=strat_r, name="Strategy",
        marker_color=strat_colors, opacity=0.85,
        hovertemplate="%{x}<br>Strategy: %{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=years, y=bh_r, name="B&H",
        marker_color=bh_colors, opacity=0.7,
        hovertemplate="%{x}<br>B&H: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_width=1, line_color="black")

    # Flag W3 / 2021 outlier
    if 2021 in years:
        idx_2021 = years.index(2021)
        fig.add_annotation(
            x=2021, y=max(strat_r[idx_2021], bh_r[idx_2021]) + 5,
            text="2021 outlier<br>(W3 bull run)",
            showarrow=True, arrowhead=2,
            font=dict(size=10), bgcolor="white", opacity=0.85,
        )

    ex_2021_strat = [v for i, v in enumerate(strat_r) if years[i] != 2021]
    avg_ex21 = float(np.mean(ex_2021_strat)) if ex_2021_strat else 0.0
    avg_all  = float(np.mean(strat_r))

    fig.update_layout(
        title=(f"BNB Donchian vs B&H — Annual Returns by Calendar Year<br>"
               f"<sup>Strategy: avg all years {avg_all:+.1f}% / ex-2021 {avg_ex21:+.1f}%</sup>"),
        xaxis_title="Year",
        yaxis_title="Annual Return (%)",
        barmode="group",
        template="plotly_white",
        height=480,
        legend=dict(orientation="h", y=-0.14),
    )

    path = os.path.join(CHARTS_DIR, "bnb_donchian_annual_returns.html")
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# CHART 7 — STABILITY HEATMAP (INTERACTIVE)
# ══════════════════════════════════════════════════════════════════════════════

def chart_stability_heatmap():
    stab_csv = os.path.join(BASE, "bnb_stability_results.csv")
    if not os.path.exists(stab_csv):
        print(f"  Stability CSV not found: {stab_csv}")
        return None

    df_s    = pd.read_csv(stab_csv)
    periods = sorted(df_s["period"].unique())
    stops   = sorted(df_s["stop_pct"].unique())

    # Build z-matrix: rows=periods, cols=stops
    z = []
    text = []
    for per in periods:
        row_z = []
        row_t = []
        for sp in stops:
            val = df_s.loc[(df_s["period"] == per) & (df_s["stop_pct"] == sp), "post_pf"]
            if len(val) > 0 and pd.notna(val.iloc[0]) and not np.isinf(val.iloc[0]):
                v = float(val.iloc[0])
            else:
                v = None
            row_z.append(v)
            row_t.append(f"{v:.2f}" if v is not None else "—")
        z.append(row_z)
        text.append(row_t)

    stop_labels = [f"{int(s*100)}%" for s in stops]

    # Compute colour range
    flat_z = [v for row in z for v in row if v is not None]
    vmax   = min(float(np.quantile(flat_z, 0.95)), 4.0) if flat_z else 4.0

    fig = go.Figure(go.Heatmap(
        z=z,
        x=stop_labels,
        y=[str(p) for p in periods],
        text=text,
        texttemplate="%{text}",
        colorscale=[
            [0.0,  "rgb(215,48,39)"],
            [0.5,  "rgb(255,255,191)"],
            [1.0,  "rgb(26,152,80)"],
        ],
        zmid=2.0,
        zmin=0.0,
        zmax=vmax,
        colorbar=dict(title="Post-break PF", tickformat=".1f"),
        hovertemplate=(
            "Period: %{y}<br>Stop: %{x}<br>"
            "Post-break PF: %{text}<extra></extra>"
        ),
    ))

    # Mark deployed combination (period=20, stop=5%) with annotations
    dep_col = stop_labels.index("5%")  if "5%"  in stop_labels else None
    dep_row = [str(p) for p in periods].index("20") if "20" in [str(p) for p in periods] else None
    if dep_col is not None and dep_row is not None:
        fig.add_shape(
            type="rect",
            x0=dep_col - 0.5, x1=dep_col + 0.5,
            y0=dep_row - 0.5, y1=dep_row + 0.5,
            line=dict(color="white", width=3),
            xref="x", yref="y",
        )
        fig.add_annotation(
            x=dep_col, y=dep_row, xref="x", yref="y",
            text="★", font=dict(size=14, color="white"),
            showarrow=False,
        )

    n_viable = sum(1 for row in z for v in row if v is not None and v > 2.0)
    n_total  = sum(1 for row in z for v in row if v is not None)

    fig.update_layout(
        title=(f"BNB Donchian — Post-Break PF Stability Grid (Jan 2024 split)<br>"
               f"<sup>{n_viable}/{n_total} combinations VIABLE (PF>2.0) | "
               f"★ = deployed (period=20, stop=5%)</sup>"),
        xaxis_title="Stop %",
        yaxis_title="Donchian Period",
        template="plotly_white",
        height=520,
        width=750,
    )

    path = os.path.join(CHARTS_DIR, "bnb_donchian_stability_heatmap.html")
    fig.write_html(path, include_plotlyjs=True, full_html=True)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 66)
    print("PHASE 6 VISUALISATION PACKAGE — BNB Donchian SMA-120")
    print("=" * 66)

    print(f"\nFetching {TICKER} and running strategy...")
    df = g.fetch_asset(TICKER)
    trades, eq, n_days = run_strategy(df)
    eq_bh, dd_strat, dd_bh, position, days_held = build_daily_data(df, trades, eq)
    yr_rets = year_returns(df, eq, eq_bh)

    print(f"  {len(df)} candles | {len(trades)} trades")
    print(f"  Strategy final eq: {eq[-1]:.3f}× | B&H final eq: {eq_bh[-1]:.3f}×")
    print(f"\nProducing charts → {CHARTS_DIR}")
    print()

    outputs = {}

    print("  [1/7] Equity curve...")
    outputs["1_equity_curve"] = chart_equity_curve(
        df, trades, eq, eq_bh, dd_strat, dd_bh, position, days_held
    )

    print("  [2/7] Year-by-year panels...")
    outputs["2_yearly_panels"] = chart_yearly_panels(df, eq, eq_bh, yr_rets)

    print("  [3/7] Trade distribution...")
    outputs["3_trade_dist"] = chart_trade_distribution(trades)

    print("  [4/7] Underwater curve...")
    outputs["4_underwater"] = chart_underwater(df, dd_strat)

    print("  [5/7] Walk-forward bars...")
    outputs["5_walkforward"] = chart_walkforward()

    print("  [6/7] Annual returns comparison...")
    outputs["6_annual_returns"] = chart_annual_returns(yr_rets)

    print("  [7/7] Stability heatmap...")
    outputs["7_stability"] = chart_stability_heatmap()

    print("\n" + "=" * 66)
    print("CHART PACKAGE COMPLETE — FILE SIZES")
    print("=" * 66)
    total_bytes = 0
    for label, path in sorted(outputs.items()):
        if path and os.path.exists(path):
            sz = os.path.getsize(path)
            total_bytes += sz
            print(f"  {label:<22}  {os.path.basename(path):<46}  {sz/1024:>6.0f} KB")
        else:
            print(f"  {label:<22}  MISSING or SKIPPED")
    print(f"  {'TOTAL':<22}  {'':46}  {total_bytes/1024:>6.0f} KB")
    print("=" * 66)
    print(f"\nAll charts saved to: {CHARTS_DIR}")
    print("Confirm chart package before writing deployment card.")


if __name__ == "__main__":
    main()
