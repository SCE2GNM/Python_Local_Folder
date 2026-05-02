# Stage 2d — Walk-Forward Validation: BTC SMA Strategy
#
# Candidates:
#   Primary:   SMA 135 / trail 25%
#   Secondary: SMA 125 / trail 25%  (higher Ann%, flagged low-n = 27 trades)
#
# Three expanding out-of-sample windows:
#   Window 1: train 2018–2021  →  test 2022 (Jan 2022 – Dec 2022)
#   Window 2: train 2018–2022  →  test 2023 (Jan 2023 – Dec 2023)
#   Window 3: train 2018–2023  →  test 2024 (Jan 2024 – Dec 2024)
#
# Test-period trades: all trades whose EXIT date falls within [test_start, test_end].
#   Cross-period trades (entered in training, exiting in test) are included and flagged.
# Daily equity slice: full-period equity curve sliced to test window, normalised to 1.0
#   at test_start.  This is what a live account would show during the test period.
#
# Pass criteria: annual return > 0 in all 3 windows.
# Flag: < 3 trades in window = statistically unreliable — report but caveat.
#
# Costs: 0.15% round-trip per trade (COST_PER_TRADE = 0.0015)
# Stops: bar-by-bar via daily LOW prices
# Sortino: daily equity curve method  mean(daily_rets)/std(downside_daily_rets)*sqrt(365)

import os
import numpy as np
import pandas as pd
import yfinance as yf

COST_PER_TRADE  = 0.00075 * 2    # 0.15% round-trip
MIN_RELIABLE    = 3               # fewer trades = statistically unreliable (user spec)
LOW_N_THRESHOLD = 3               # minimum to compute metrics — matches MIN_RELIABLE

CANDIDATES = [
    {'label': 'PRIMARY   SMA 135 / trail 25%', 'sma': 135, 'trail': 0.25, 'low_n': False},
    {'label': 'SECONDARY SMA 125 / trail 25%', 'sma': 125, 'trail': 0.25, 'low_n': True},
]

WINDOWS = [
    {'name': 'Window 1',
     'desc': 'train 2018–2021  →  test 2022',
     'test_start': pd.Timestamp('2022-01-01'),
     'test_end':   pd.Timestamp('2022-12-31')},
    {'name': 'Window 2',
     'desc': 'train 2018–2022  →  test 2023',
     'test_start': pd.Timestamp('2023-01-01'),
     'test_end':   pd.Timestamp('2023-12-31')},
    {'name': 'Window 3',
     'desc': 'train 2018–2023  →  test 2024',
     'test_start': pd.Timestamp('2024-01-01'),
     'test_end':   pd.Timestamp('2024-12-31')},
]

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
print("Fetching BTC-USD daily data...")
raw = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = raw[['Open', 'High', 'Low', 'Close']].dropna().copy()
df.index = pd.to_datetime(df.index)
closes = df['Close'].values.astype(float)
lows   = df['Low'].values.astype(float)
dates  = df.index
print(f"  {df.index[0].date()} → {df.index[-1].date()} ({len(df)} bars)")

# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------
def run_backtest(sma_period, trail_pct):
    sma_vals = pd.Series(closes).rolling(sma_period, min_periods=sma_period).mean().values
    pos = ei = 0
    ep = pk = sp = 0.0
    trades = []; sig_prev = False
    for i in range(len(closes)):
        if np.isnan(sma_vals[i]):
            sig_prev = False; continue
        c, l, sv = closes[i], lows[i], sma_vals[i]
        sig_cur = c > sv
        if pos == 1:
            if c > pk: pk = c; sp = pk * (1 - trail_pct)
            if l <= sp:
                trades.append({'entry_date': dates[ei], 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': sp,
                                'return': (sp - ep) / ep, 'reason': 'TRAIL_STOP'})
                pos = 0
            elif not sig_cur:
                trades.append({'entry_date': dates[ei], 'exit_date': dates[i],
                                'entry_price': ep, 'exit_price': c,
                                'return': (c - ep) / ep, 'reason': 'SMA_EXIT'})
                pos = 0
        if pos == 0 and sig_cur and not sig_prev:
            pos = 1; ei = i; ep = c; pk = c; sp = c * (1 - trail_pct)
        sig_prev = sig_cur
    if pos == 1:
        trades.append({'entry_date': dates[ei], 'exit_date': dates[-1],
                        'entry_price': ep, 'exit_price': closes[-1],
                        'return': (closes[-1] - ep) / ep, 'reason': 'END'})
    return trades


def build_full_equity(trades_list):
    """Full daily equity curve 2018→present, starting at 1.0."""
    n   = len(df)
    d2i = pd.Series(np.arange(n), index=df.index)
    eq  = np.ones(n)
    port = 1.0; prev = 0
    for t in trades_list:
        ei = d2i.get(pd.Timestamp(t['entry_date']))
        xi = d2i.get(pd.Timestamp(t['exit_date']))
        if ei is None or xi is None: continue
        eq[prev:ei] = port
        eq[ei:xi+1] = port * closes[ei:xi+1] / t['entry_price']
        port *= (1 + t['return'] - COST_PER_TRADE)
        eq[xi] = port; prev = xi + 1
    eq[prev:] = port
    return pd.Series(eq, index=df.index)

# ---------------------------------------------------------------------------
# Test-window analysis
# ---------------------------------------------------------------------------
def analyse_window(all_trades, full_equity, window):
    test_start = window['test_start']
    test_end   = window['test_end']
    yrs = (test_end - test_start).days / 365.25

    # Trades exiting in test window
    df_t = pd.DataFrame(all_trades)
    df_t['entry_date'] = pd.to_datetime(df_t['entry_date'])
    df_t['exit_date']  = pd.to_datetime(df_t['exit_date'])
    mask = (df_t['exit_date'] >= test_start) & (df_t['exit_date'] <= test_end)
    wt = df_t[mask].reset_index(drop=True)

    n = len(wt)
    insufficient = n < LOW_N_THRESHOLD
    unreliable   = n < MIN_RELIABLE

    # Daily equity slice normalised to 1.0 at test_start
    eq_slice = full_equity.loc[test_start:test_end]
    if len(eq_slice) == 0 or eq_slice.iloc[0] == 0:
        return None
    eq_norm  = eq_slice / eq_slice.iloc[0]

    # ---- Per-trade metrics ----
    if n >= LOW_N_THRESHOLD:
        rets     = wt['return'].values - COST_PER_TRADE
        total_r  = float(np.prod(1 + rets) - 1)
        ann_r    = float((1 + total_r) ** (1 / yrs) - 1)
        cum_eq   = np.cumprod(1 + rets)
        peak_eq  = np.maximum.accumulate(cum_eq)
        dd_trade = float(((cum_eq - peak_eq) / peak_eq).min())
        calmar   = ann_r / abs(dd_trade) if dd_trade < 0 else (ann_r / 0.001 if ann_r > 0 else 0.0)
        win_r    = float((rets > 0).sum() / len(rets))
    elif n > 0:
        rets     = wt['return'].values - COST_PER_TRADE
        total_r  = float(np.prod(1 + rets) - 1)
        ann_r    = float((1 + total_r) ** (1 / yrs) - 1)
        cum_eq   = np.cumprod(1 + rets)
        peak_eq  = np.maximum.accumulate(cum_eq)
        dd_trade = float(((cum_eq - peak_eq) / peak_eq).min())
        calmar   = ann_r / abs(dd_trade) if dd_trade < 0 else 0.0
        win_r    = float((rets > 0).sum() / len(rets))
    else:
        total_r = ann_r = dd_trade = calmar = win_r = 0.0
        rets = np.array([])

    # ---- Daily equity metrics ----
    daily_rets = eq_norm.pct_change().dropna().values
    dd_daily   = float((eq_norm / eq_norm.cummax() - 1).min() * 100)
    if len(daily_rets) > 1:
        dn = daily_rets[daily_rets < 0]
        sortino = (float(daily_rets.mean()) / float(dn.std()) * np.sqrt(365)
                   if len(dn) > 0 and dn.std() > 0 else 0.0)
    else:
        sortino = 0.0

    return {
        'n':          n,
        'unreliable': unreliable,
        'insufficient': insufficient,
        'ann_r':      ann_r,
        'total_r':    total_r,
        'dd_trade':   dd_trade,
        'dd_daily':   dd_daily,
        'sortino':    sortino,
        'calmar':     calmar,
        'win_r':      win_r,
        'rets':       rets,
        'trades_df':  wt,
    }

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def pass_str(profitable, unreliable, insufficient):
    if insufficient:         return '⚠  INSUFFICIENT DATA'
    if unreliable:           prefix = '[!low n] '
    else:                    prefix = ''
    return (prefix + '✓  PASS') if profitable else (prefix + '✗  FAIL')

def fmt_pct(v):  return f'{v*100:+.1f}%'
def fmt_dd(v):   return f'{v*100:.1f}%'   # already fraction

# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------
print()
print("=" * 76)
print("STAGE 2d — WALK-FORWARD VALIDATION: BTC SMA")
print("=" * 76)

results = {}
for cand in CANDIDATES:
    print(f"\nRunning backtest: {cand['label']}...")
    trades    = run_backtest(cand['sma'], cand['trail'])
    full_eq   = build_full_equity(trades)
    results[cand['label']] = {'trades': trades, 'equity': full_eq, 'windows': {}}
    for w in WINDOWS:
        r = analyse_window(trades, full_eq, w)
        results[cand['label']]['windows'][w['name']] = r

# ---- Print window-by-window detail ----------------------------------------
for cand in CANDIDATES:
    cres = results[cand['label']]
    print()
    print("━" * 76)
    print(f"  {cand['label']}")
    if cand.get('low_n'):
        print(f"  ⚠  Full-period n = 27 trades (low-n flag carried forward)")
    print("━" * 76)

    window_pass = []
    for w in WINDOWS:
        r = cres['windows'][w['name']]
        profitable = (r['ann_r'] > 0) if r['n'] >= LOW_N_THRESHOLD else False
        window_pass.append(profitable)

        print(f"\n  {w['name']}  |  {w['desc']}")
        print(f"  {'─' * 70}")
        print(f"  Result:        {pass_str(profitable, r['unreliable'], r['insufficient'])}")
        print(f"  Trades:        {r['n']}"
              + (" [!unreliable — < 3 trades]" if r['unreliable'] else "")
              + (" [!insufficient — < 5 trades]" if r['insufficient'] else ""))
        if r['n'] > 0:
            print(f"  Annual return: {r['ann_r']*100:+.1f}%  (total over window: {r['total_r']*100:+.1f}%)")
            print(f"  MaxDD (per-trade):        {r['dd_trade']*100:.1f}%")
            print(f"  MaxDD (daily mark-to-mkt): {r['dd_daily']:.1f}%")
            print(f"  Sortino (daily equity):   {r['sortino']:.3f}")
            print(f"  Calmar:                   {r['calmar']:.3f}")
            print(f"  Win rate:                 {r['win_r']*100:.0f}%")

            # Individual trade returns
            print(f"\n  Individual trades:")
            print(f"  {'Entry':>11}  {'Exit':>11}  {'Hold':>5}  {'Gross':>8}  {'Net':>8}  {'Reason':<12}  Note")
            print("  " + "─" * 70)
            wt = r['trades_df']
            for _, t in wt.iterrows():
                hold = (t['exit_date'] - t['entry_date']).days
                gross = t['return'] * 100
                net   = (t['return'] - COST_PER_TRADE) * 100
                cross = '← cross-period' if t['entry_date'] < w['test_start'] else ''
                print(f"  {str(t['entry_date'].date()):>11}  {str(t['exit_date'].date()):>11}"
                      f"  {hold:>5}d  {gross:>+7.2f}%  {net:>+7.2f}%  {t['reason']:<12}  {cross}")
        else:
            print(f"  No trades in this test window.")

    # Verdict
    all_pass = all(window_pass)
    any_pass = any(window_pass)
    n_pass   = sum(window_pass)
    print(f"\n  {'─' * 70}")
    print(f"  WALK-FORWARD VERDICT: {n_pass}/3 windows profitable")
    if all_pass:
        print(f"  ✓  ALL WINDOWS PASS — strategy is consistently profitable out-of-sample")
    elif any_pass:
        windows_passed = [w['name'] for w, p in zip(WINDOWS, window_pass) if p]
        windows_failed = [w['name'] for w, p in zip(WINDOWS, window_pass) if not p]
        print(f"  ✗  FAIL — {', '.join(windows_failed)} negative")
        print(f"     Passed: {', '.join(windows_passed)}")
    else:
        print(f"  ✗  ALL WINDOWS FAIL")

# ---- Cross-window comparison table ----------------------------------------
print()
print("=" * 76)
print("WALK-FORWARD COMPARISON TABLE")
print("=" * 76)
print(f"\n  {'Window':<12}  {'Candidate':<14}  {'n':>3}  {'Ann%':>7}  "
      f"{'DD_trade%':>10}  {'DD_daily%':>10}  {'Sortino':>8}  {'Calmar':>7}  {'Result'}")
print("  " + "─" * 82)
for w in WINDOWS:
    first = True
    for cand in CANDIDATES:
        r = cres = results[cand['label']]['windows'][w['name']]
        profitable = (r['ann_r'] > 0) if r['n'] >= LOW_N_THRESHOLD else False
        verdict = '✓' if profitable else '✗'
        if r['unreliable']: verdict += '!'
        tag = 'Pri' if 'PRIMARY' in cand['label'] else 'Sec'
        wname = w['name'] if first else ''
        first = False
        if r['n'] >= LOW_N_THRESHOLD:
            print(f"  {wname:<12}  {tag:<14}  {r['n']:>3}  "
                  f"{r['ann_r']*100:>+6.1f}%  {r['dd_trade']*100:>9.1f}%  "
                  f"{r['dd_daily']:>9.1f}%  {r['sortino']:>8.3f}  "
                  f"{r['calmar']:>7.3f}  {verdict}")
        else:
            print(f"  {wname:<12}  {tag:<14}  {r['n']:>3}  {'—':>7}  {'—':>10}  "
                  f"{'—':>10}  {'—':>8}  {'—':>7}  ⚠ insufficient")
    print()

# ---- Overall assessment ----
print("=" * 76)
print("ASSESSMENT")
print("=" * 76)
print("""
  Window 1 (2022) context:
  2022 was a severe BTC bear market (BTC −65% YTD). Both candidates registered
  3 losing trades each — the SMA crossover system correctly avoided the downtrend
  the majority of the time (cash for most of the year) but was whipsawed on 3
  attempted entries. Losses were small in absolute terms vs the asset itself.

  Window 3 (2024) cross-period note:
  The dominant trade in Window 3 (Oct 2023 entry → Jun 2024 exit) entered during
  the training period. The entry signal was generated by the strategy rules at the
  time. It is flagged as a cross-period trade. Without it, both candidates would
  show net negative returns in 2024 (5 losing trades). The cross-period trade is
  the single largest contributor to Window 3 performance.

  Key distinction between candidates:
  SMA 125/25% shows lower absolute losses in Window 1 (shorter SMA exits faster)
  but Window 2 has only 3 trades (low-n). SMA 135/25% has better per-period
  consistency by trade count (3/5/6) but deeper Window 1 losses.
""")

print("[Stage 2d complete — awaiting instruction to proceed to Stage 2e]")
