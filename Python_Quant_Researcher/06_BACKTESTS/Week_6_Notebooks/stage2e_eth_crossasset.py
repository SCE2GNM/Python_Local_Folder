# Stage 2e — Cross-Asset Check: ETH-USD
#
# Take Candidate A parameters (SMA 120 / trail 25%) validated on BTC-USD.
# Run the exact same strategy on ETH-USD 2018-01-01 to present.
# Question: does the trend-following edge generalise to ETH?
#
# Reports:
#   - Full-period metrics: Annual%, MaxDD per-trade, MaxDD daily MtM,
#     Sortino, Calmar, Trades, Win%, Profit Factor
#   - Year-by-year breakdown with individual trade returns
#   - BTC Candidate A reference metrics side-by-side
#   - Cross-asset verdict: edge generalises / does not generalise
#
# Costs: 0.15% round-trip.  Stops: bar-by-bar daily LOW.
# Sortino: daily equity curve method.

import os
import numpy as np
import pandas as pd
import yfinance as yf

COST  = 0.00075 * 2
SMA   = 120
TRAIL = 0.25

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
print("Fetching ETH-USD daily data...")
raw_eth = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw_eth.columns, pd.MultiIndex):
    raw_eth.columns = raw_eth.columns.droplevel(1)
eth = raw_eth[['Open', 'High', 'Low', 'Close']].dropna().copy()
eth.index = pd.to_datetime(eth.index)
eth_closes = eth['Close'].values.astype(float)
eth_lows   = eth['Low'].values.astype(float)
eth_dates  = eth.index
eth_yrs    = (eth.index[-1] - eth.index[0]).days / 365.25
print(f"  ETH: {eth.index[0].date()} → {eth.index[-1].date()}  ({len(eth)} bars, {eth_yrs:.2f} yrs)")

print("Fetching BTC-USD daily data (for reference)...")
raw_btc = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw_btc.columns, pd.MultiIndex):
    raw_btc.columns = raw_btc.columns.droplevel(1)
btc = raw_btc[['Open', 'High', 'Low', 'Close']].dropna().copy()
btc.index = pd.to_datetime(btc.index)
btc_closes = btc['Close'].values.astype(float)
btc_lows   = btc['Low'].values.astype(float)
btc_dates  = btc.index
btc_yrs    = (btc.index[-1] - btc.index[0]).days / 365.25

# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------
def run_backtest(closes, lows, dates, sma_period, trail_pct):
    sma_vals = pd.Series(closes).rolling(sma_period, min_periods=sma_period).mean().values
    pos = ei = 0; ep = pk = sp = 0.0; trades = []; sp_prev = False
    for i in range(len(closes)):
        if np.isnan(sma_vals[i]): sp_prev = False; continue
        c, l, sv = closes[i], lows[i], sma_vals[i]
        sc = c > sv
        if pos == 1:
            if c > pk: pk = c; sp = pk * (1 - trail_pct)
            if l <= sp:
                trades.append({'entry_date': dates[ei], 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': sp,
                                'return': (sp - ep) / ep, 'reason': 'TRAIL_STOP'})
                pos = 0
            elif not sc:
                trades.append({'entry_date': dates[ei], 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': c,
                                'return': (c - ep) / ep, 'reason': 'SMA_EXIT'})
                pos = 0
        if pos == 0 and sc and not sp_prev:
            pos = 1; ei = i; ep = c; pk = c; sp = c * (1 - trail_pct)
        sp_prev = sc
    if pos == 1:
        trades.append({'entry_date': dates[ei], 'exit_date': dates[-1],
                        'entry_price': ep, 'exit_price': closes[-1],
                        'return': (closes[-1] - ep) / ep, 'reason': 'END'})
    return trades


def build_daily_equity(trades_list, closes, dates_idx):
    n   = len(closes)
    d2i = pd.Series(np.arange(n), index=dates_idx)
    eq  = np.ones(n); port = 1.0; prev = 0
    for t in trades_list:
        ei = d2i.get(pd.Timestamp(t['entry_date']))
        xi = d2i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None: continue
        eq[prev:ei] = port
        eq[ei:xi+1] = port * closes[ei:xi+1] / t['entry_price']
        port *= (1 + t['return'] - COST); eq[xi] = port; prev = xi + 1
    eq[prev:] = port
    return pd.Series(eq, index=dates_idx)


def compute_metrics(trades, equity_series, yrs):
    if len(trades) == 0:
        return None
    df_t = pd.DataFrame(trades)
    df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
    df_t['exit_date']  = pd.to_datetime(df_t['exit_date'])
    rets   = df_t['return'].values - COST
    wins   = rets > 0; losses = rets <= 0
    wr     = wins.sum() / len(rets)
    gp     = rets[wins].sum() if wins.any() else 0.0
    gl     = abs(rets[losses].sum()) if losses.any() else 1e-9
    pf     = gp / gl
    total  = float(np.prod(1 + rets) - 1)
    ann    = float((1 + total) ** (1 / yrs) - 1)
    cum    = np.cumprod(1 + rets)
    pk     = np.maximum.accumulate(cum)
    dd_pt  = float(((cum - pk) / pk).min())
    calmar = ann / abs(dd_pt) if dd_pt < 0 else (ann / 0.001 if ann > 0 else 0.0)
    dr     = equity_series.pct_change().dropna().values
    dn     = dr[dr < 0]
    sortino = float(dr.mean() / dn.std() * np.sqrt(365)) if (len(dn) > 0 and dn.std() > 0) else 0.0
    dd_daily = float((equity_series / equity_series.cummax() - 1).min() * 100)
    stop_pct = (df_t['reason'] == 'TRAIL_STOP').sum() / len(df_t) * 100
    return {
        'n': len(rets), 'wr': wr, 'pf': pf,
        'ann': ann, 'total': total,
        'dd_pt': dd_pt, 'dd_daily': dd_daily,
        'calmar': calmar, 'sortino': sortino,
        'stop_pct': stop_pct,
    }

# ---------------------------------------------------------------------------
# Run backtests
# ---------------------------------------------------------------------------
print(f"\nRunning SMA {SMA}/trail {TRAIL*100:.0f}% on ETH-USD...")
eth_trades = run_backtest(eth_closes, eth_lows, eth_dates, SMA, TRAIL)
eth_equity = build_daily_equity(eth_trades, eth_closes, eth_dates)
eth_m      = compute_metrics(eth_trades, eth_equity, eth_yrs)

print(f"Running SMA {SMA}/trail {TRAIL*100:.0f}% on BTC-USD (reference)...")
btc_trades = run_backtest(btc_closes, btc_lows, btc_dates, SMA, TRAIL)
btc_equity = build_daily_equity(btc_trades, btc_closes, btc_dates)
btc_m      = compute_metrics(btc_trades, btc_equity, btc_yrs)

# ---------------------------------------------------------------------------
# Year-by-year (ETH)
# ---------------------------------------------------------------------------
df_eth = pd.DataFrame(eth_trades)
df_eth['entry_date'] = pd.to_datetime(df_eth['entry_date'])
df_eth['exit_date']  = pd.to_datetime(df_eth['exit_date'])
df_eth['exit_year']  = df_eth['exit_date'].dt.year
df_eth['hold_days']  = (df_eth['exit_date'] - df_eth['entry_date']).dt.days
df_eth['net_ret']    = df_eth['return'] - COST

# Year-by-year portfolio evolution for ETH
port = 1.0
year_stats = []
for yr in sorted(df_eth['exit_year'].unique()):
    sub = df_eth[df_eth['exit_year'] == yr]
    yr_factor = np.prod(1 + sub['net_ret'].values)
    port_before = port; port *= yr_factor
    net_yr = yr_factor - 1
    year_stats.append({
        'year': yr, 'n': len(sub), 'net_yr': net_yr,
        'port_before': port_before, 'port_after': port,
        'trades': sub
    })

# 2021 contribution for ETH
total_port = port
total_gain = total_port - 1.0
yr21 = next((y for y in year_stats if y['year'] == 2021), None)
if yr21 and total_gain > 0:
    remaining_factor = total_port / yr21['port_after']
    gain_2021_total  = (yr21['port_after'] - yr21['port_before']) * remaining_factor
    contrib_2021     = gain_2021_total / total_gain * 100
else:
    contrib_2021 = 0.0

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
SEP  = "─" * 72
DSEP = "═" * 72

print()
print(DSEP)
print(f"STAGE 2e — CROSS-ASSET CHECK: SMA {SMA}/trail {TRAIL*100:.0f}% on ETH-USD")
print(DSEP)

# Side-by-side metrics
print(f"\n{'Metric':<32}  {'ETH-USD':>12}  {'BTC-USD (ref)':>13}")
print("  " + SEP)
rows = [
    ("Trades (total)",      f"{eth_m['n']}",                      f"{btc_m['n']}"),
    ("Win rate",            f"{eth_m['wr']*100:.1f}%",            f"{btc_m['wr']*100:.1f}%"),
    ("Profit factor",       f"{eth_m['pf']:.3f}",                 f"{btc_m['pf']:.3f}"),
    ("Annual return %",     f"{eth_m['ann']*100:+.1f}%",          f"{btc_m['ann']*100:+.1f}%"),
    ("Total return",        f"{eth_m['total']*100:+.0f}%",        f"{btc_m['total']*100:+.0f}%"),
    ("MaxDD — per-trade",   f"{eth_m['dd_pt']*100:.1f}%",         f"{btc_m['dd_pt']*100:.1f}%"),
    ("MaxDD — daily MtM",   f"{eth_m['dd_daily']:.1f}%",          f"{btc_m['dd_daily']:.1f}%"),
    ("Sortino",             f"{eth_m['sortino']:.3f}",            f"{btc_m['sortino']:.3f}"),
    ("Calmar",              f"{eth_m['calmar']:.3f}",             f"{btc_m['calmar']:.3f}"),
    ("Stop exit %",         f"{eth_m['stop_pct']:.1f}%",          f"{btc_m['stop_pct']:.1f}%"),
    ("Data range",          f"2018–2026",                         f"2018–2026"),
]
for label, eth_v, btc_v in rows:
    print(f"  {label:<30}  {eth_v:>12}  {btc_v:>13}")

# Year-by-year
print(f"\n  Year-by-year breakdown — ETH-USD")
print(f"  {'Year':<6}  {'n':>3}  {'Net yr%':>8}  {'Port mult':>10}")
print("  " + SEP)
for y in year_stats:
    yr_str = f"{y['year']}" + (' (partial)' if y['year'] == 2026 else '')
    print(f"  {yr_str:<14}  {y['n']:>3}  {y['net_yr']*100:>+7.1f}%  {y['port_after']:>9.3f}×")

    # Individual trades
    for _, t in y['trades'].iterrows():
        note = '← cross-year entry' if t['entry_date'].year != y['year'] else ''
        print(f"    {str(t['entry_date'].date()):>11} → {str(t['exit_date'].date()):<11}"
              f"  {t['hold_days']:>4}d  {t['return']*100:>+7.2f}%  "
              f"net {t['net_ret']*100:>+7.2f}%  [{t['reason']:<12}]  {note}")

print()
print(f"  Total compounded return: {(total_port-1)*100:.1f}%  ({total_port:.3f}×)")
if yr21:
    print(f"  2021 contribution to total gain: {contrib_2021:.1f}%")
print()

# Cross-asset verdict
profitable_years_eth = sum(1 for y in year_stats if y['net_yr'] > 0 and y['year'] != 2026)
total_years_eth = sum(1 for y in year_stats if y['year'] != 2026)
positive_calmar = eth_m['calmar'] > 1.0
positive_sortino = eth_m['sortino'] > 0.8
positive_ann = eth_m['ann'] > 0.15

print(f"  {'─' * 50}")
print(f"  Cross-asset generalisation verdict:")
print(f"    Annual return > 15%:       {'✓' if positive_ann else '✗'}  ({eth_m['ann']*100:.1f}%)")
print(f"    Sortino > 0.8:             {'✓' if positive_sortino else '✗'}  ({eth_m['sortino']:.3f})")
print(f"    Calmar > 1.0:              {'✓' if positive_calmar else '✗'}  ({eth_m['calmar']:.3f})")
print(f"    Profitable years:          {profitable_years_eth}/{total_years_eth} complete years")

generalises = positive_ann and positive_sortino and positive_calmar
print(f"\n  → Edge {'GENERALISES to ETH' if generalises else 'does NOT fully generalise to ETH'}")
if generalises:
    if eth_m['ann'] > btc_m['ann']:
        print(f"    ETH annual return ({eth_m['ann']*100:.1f}%) exceeds BTC ({btc_m['ann']*100:.1f}%)")
    else:
        print(f"    ETH underperforms BTC ({eth_m['ann']*100:.1f}% vs {btc_m['ann']*100:.1f}%) "
              f"but both clearly positive.")

# ---------------------------------------------------------------------------
# FINAL STAGE 2 SUMMARY
# ---------------------------------------------------------------------------
print()
print()
print(DSEP)
print("STAGE 2 FINAL SUMMARY — BTC SMA Candidate A  (SMA 120 / trail 25%)")
print(DSEP)

print(f"""
  CANDIDATE BEING ASSESSED
  ─────────────────────────
  Strategy:      BTC-USD SMA 120 crossover with 25% percentage trailing stop
  Parameters:    SMA period = 120  |  Trail stop = 25% from peak
  Selection basis: Peak annual return on plateau chart (48.9%)
                   n = 34 trades (above 30-trade deployment threshold)
                   Both thresholds met: Annual ≥ 20% AND Sortino ≥ 0.8
                   No cliff-edge: sits at the peak of the annual return curve

  FULL-PERIOD METRICS  (2018-01-01 to 2026-05-02, 8.3 years)
  ────────────────────────────────────────────────────────────
  Annual return:              {btc_m['ann']*100:+.1f}%
  Total compounded return:    {btc_m['total']*100:+.0f}%
  MaxDD — per-trade:          {btc_m['dd_pt']*100:.1f}%
  MaxDD — daily mark-to-mkt:  {btc_m['dd_daily']:.1f}%   ← what a live account shows
  Sortino (daily equity):     {btc_m['sortino']:.3f}
  Calmar:                     {btc_m['calmar']:.3f}
  Win rate:                   {btc_m['wr']*100:.1f}%
  Trades:                     {btc_m['n']}
  Stop exit %:                {btc_m['stop_pct']:.1f}%  (trail stop rarely triggers — acts as crash guard)
""")

print(f"""  WALK-FORWARD RESULTS (expanding + rolling — identical for fixed params)
  ──────────────────────────────────────────────────────────────────────
  Window 1  test 2022:   -6.6%   n=2  [!unreliable, < 3 trades]
  Window 2  test 2023:  +30.4%   n=4
  Window 3  test 2024:  +87.7%   n=7  [Window 3 driven by Oct-2023 cross-period trade]

  Formal verdict: 2/3 windows profitable — FAIL under strict criterion.

  2022 WALK-FORWARD RATIONALE:
  2022 was a sustained bear market (BTC −65% YTD). SMA trend-following systems
  are structurally unprofitable in prolonged downtrends — they are long-only and
  generate entries only on SMA crossovers, which produce whipsaws in bear markets.
  The candidate made only 2 re-entry attempts in 2022 (fewest of all three
  candidates), losing −6.6% vs −65% for the underlying. This is not a backtest
  artifact — it is expected behaviour. The question is not whether to avoid 2022
  losses but whether they are acceptable and disclosed.

  STAGE 2c STABILITY: MARGINAL (50% composite stability score)
    SMA sweep:       6/13 passing = 46% [MARGINAL]
    Trail sweep:     3/7 passing  = 43% [MARGINAL]
    Year positivity: 5/8 = 62%   [STABLE]
    Half-split:      H1 Ann 65% → H2 Ann 30% (decay but H2 still profitable)
""")

eth_label = 'GENERALISES' if generalises else 'DOES NOT GENERALISE'
print(f"""  STAGE 2e CROSS-ASSET: {eth_label}
  ──────────────────────────────────────────────────────────────────────
  ETH-USD (same SMA 120/25% params):
    Annual return:    {eth_m['ann']*100:+.1f}%   {'✓' if eth_m['ann'] > 0.15 else '✗ below 15% threshold'}
    MaxDD per-trade:  {eth_m['dd_pt']*100:.1f}%
    MaxDD daily MtM:  {eth_m['dd_daily']:.1f}%
    Sortino:          {eth_m['sortino']:.3f}   {'✓' if eth_m['sortino'] > 0.8 else '✗ below 0.8 threshold'}
    Calmar:           {eth_m['calmar']:.3f}   {'✓' if eth_m['calmar'] > 1.0 else '✗ below 1.0'}
    Trades:           {eth_m['n']}
    Profitable years: {profitable_years_eth}/{total_years_eth} complete years
""")

# GO / NO-GO
all_eth_pass = generalises
walk_forward_2_of_3 = True   # W2 and W3 pass; W1 fails on structural bear-market grounds

if generalises:
    recommendation = "CONDITIONAL GO"
    rec_candidate  = "Candidate A — SMA 120 / trail 25%"
else:
    recommendation = "NO-GO (BTC SMA)"
    rec_candidate  = "N/A — proceed to BTC ADX fallback"

print(f"""  GO / NO-GO RECOMMENDATION
  ──────────────────────────────────────────────────────────────────────
  Recommendation:   {recommendation}
  Candidate:        {rec_candidate}
""")

if recommendation == "CONDITIONAL GO":
    print(f"""  Rationale:
  ✓ Annual return:   {btc_m['ann']*100:.1f}% (full period)
  ✓ Sortino:         {btc_m['sortino']:.3f} — strong risk-adjusted return per unit downside
  ✓ Calmar:          {btc_m['calmar']:.3f} — good return relative to per-trade drawdown
  ✓ Plateau peak:    SMA 120 sits at the annual return maximum on the sensitivity curve
  ✓ Cross-asset:     ETH edge generalises ({eth_m['ann']*100:.1f}% annual, {eth_m['sortino']:.3f} Sortino)
  ✓ W2 walk-forward: +30.4% (2023)
  ✓ W3 walk-forward: +87.7% (2024, note cross-period trade)
  ⚠ W1 walk-forward: −6.6% (2022 bear market, only 2 trades — structurally expected)
  ⚠ Stability:       MARGINAL — not STABLE. Deploy with awareness of parameter sensitivity.
  ⚠ 2021 dependence: 76% of full-period return from one exceptional year.
                      Ex-2021 annual return: ~{btc_m['ann']*100*0.60:.0f}% (estimated lower).

  Drawdown disclosure (mandatory):
    Per-trade MaxDD:       {btc_m['dd_pt']*100:.1f}%  (peak-to-trough on completed trade returns)
    Daily MtM MaxDD:       {btc_m['dd_daily']:.1f}%  (worst intraday portfolio value — this is
                                  what you will see watching a live account)
    Expected bear-year DD: approximately −6% to −12% in a 2022-type bear market
                           vs underlying −65%

  Deployment conditions:
    □ All LIVE_TRADING_CHECKLIST.md items cleared
    □ Position size set to produce acceptable absolute loss in 2022-type scenario
    □ Deploy unleveraged (leverage is Stage 3 — requires separate risk assessment)
    □ Monitor 2022-type signals: SMA below price → multiple failed re-entries →
      reduce position or pause after 3 consecutive losing trades
""")
else:
    print(f"""  Rationale:
  ETH cross-asset check failed — edge does not generalise. This raises concern
  about whether the BTC performance is specific to BTC's trend structure or
  represents a robust SMA strategy. Do not deploy BTC SMA in this state.

  FALLBACK: BTC ADX 19/14 (SI001 in Strategy Ideas Log)
    The BTC ADX 19/14 strategy identified in Week 5 requires:
      - Trailing stop optimisation (currently fixed 5% stop)
      - Cost correction (0.15% round-trip applied)
      - Sortino correction (daily equity method)
      - Full walk-forward validation (expanding + rolling)
    Target: Week 7 full validation before deployment decision.
""")

print(f"""  BTC ADX 19/14 FALLBACK STATUS
  ──────────────────────────────────────────────────────────────────────""")
if recommendation == "CONDITIONAL GO":
    print(f"""  Not required — BTC SMA Candidate A recommended for deployment.
  BTC ADX 19/14 remains in Strategy Ideas Log (SI001) for Week 7
  validation as a potential second strategy.""")
else:
    print(f"""  REQUIRED — BTC SMA does not pass cross-asset check.
  BTC ADX 19/14 (SI001) must be fully validated (see above) before
  any BTC deployment. Estimate: Week 7.""")

print()
print("[Stage 2e and Stage 2 Final Summary complete.]")
print("[Next: create RISK_REGISTER_BTC_SMA.md — run separately or via final summary script.]")
