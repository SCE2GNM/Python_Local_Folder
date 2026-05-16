# [FILE] day3_trade_logger.py
# PURPOSE: Enhanced backtest with per-trade logging
#          Resolves A001 (real win rate) and A005 (Kelly re-calculation)
#
# WHY PER-TRADE LOGGING MATTERS:
# Our Day 2 Kelly calculation used an ESTIMATED 50% win rate.
# This script extracts the REAL win rate from 193 historical trades.
# The difference matters — if real win rate is 40% instead of 50%,
# our Kelly sizing changes significantly.
#
# WHAT IS A "TRADE" IN THIS CONTEXT?
# A trade is a complete round-trip: entry (buy) + exit (sell)
# Entry: day when Position changes from 0 (FLAT) to 1 (LONG)
# Exit:  day when Position changes from 1 (LONG) to 0 (FLAT)
#
# The backtest produces a daily series of positions (0s and 1s).
# We scan this series for transitions to identify individual trades.
#
# EXAMPLE:
# Day 1:  Position = 0 (FLAT)
# Day 2:  Position = 0 (FLAT)
# Day 3:  Position = 1 (LONG)  ← ENTRY recorded here
# Day 4:  Position = 1 (LONG)
# Day 5:  Position = 1 (LONG)
# Day 6:  Position = 0 (FLAT)  ← EXIT recorded here
# Trade: Entry Day 3, Exit Day 6, held 3 days

# ── Imports ───────────────────────────────────────────────────────────────────

import pandas as pd                      # [LIBRARY] data manipulation
import numpy as np                       # [LIBRARY] numerical calculations
import yfinance as yf                    # [LIBRARY] historical price data
from ta.trend import ADXIndicator        # [LIBRARY] ADX calculation
import json                              # [LIBRARY] save/load results
import os                                # [LIBRARY] file paths
from datetime import datetime            # [LIBRARY] timestamps
import warnings
warnings.filterwarnings('ignore')

# ── Configuration ─────────────────────────────────────────────────────────────

STRATEGY_ID      = 'ADX_20_10_v1'       # [VARIABLE - str] unique strategy identifier
SYMBOL           = 'ETH-USD'            # [VARIABLE - str] asset
START_DATE       = '2018-01-01'         # [VARIABLE - str] backtest start
THRESHOLD        = 20                   # [VARIABLE - int] ADX threshold
PERIOD           = 10                   # [VARIABLE - int] ADX period
COSTS            = 0.00175              # [VARIABLE - float] transaction cost
STARTING_CAPITAL = 1000.0              # [VARIABLE - float] hypothetical starting $

# File paths — using the new data/ folder structure
TRADE_LOG_PATH    = 'data/trade_log.csv'         # [VARIABLE - str] per-trade log
REGISTRY_PATH     = 'data/strategy_registry.csv' # [VARIABLE - str] strategy registry
KELLY_PATH        = 'Week_4_Notebooks/results/kelly_results.json'  # [VARIABLE - str]

# ── Step 1: Fetch Data ────────────────────────────────────────────────────────

print("=" * 70)
print("DAY 3 — PER-TRADE BACKTEST LOGGING")
print("=" * 70)
print(f"\nStrategy: {STRATEGY_ID}")
print(f"Symbol:   {SYMBOL}")
print(f"Period:   {START_DATE} to present")
print(f"\nFetching daily data...")

df = yf.download(                        # [VARIABLE - DataFrame] price data
    SYMBOL,
    start       = START_DATE,
    interval    = '1d',
    auto_adjust = True,
    progress    = False
)
df.columns = df.columns.get_level_values(0)
print(f"✅ {len(df):,} daily candles loaded")

# ── Step 2: Run ADX Strategy ──────────────────────────────────────────────────

print(f"\nRunning ADX {THRESHOLD}/{PERIOD} strategy...")

adx_ind = ADXIndicator(
    high   = df['High'].squeeze(),
    low    = df['Low'].squeeze(),
    close  = df['Close'].squeeze(),
    window = PERIOD
)

df['ADX']    = adx_ind.adx()
df['+DI']    = adx_ind.adx_pos()
df['-DI']    = adx_ind.adx_neg()

# Generate position signals
df['Position'] = (
    (df['ADX'] >= THRESHOLD) &
    (df['+DI'] > df['-DI'])
).astype(int)                            # [VARIABLE - Series] 1=LONG, 0=FLAT

# Calculate returns
df['Market_Return']   = df['Close'].pct_change()
df['Strategy_Return'] = df['Position'].shift(1) * df['Market_Return']
df['Position_Change'] = df['Position'].diff().abs()
df['Costs']           = df['Position_Change'] * COSTS
df['Net_Strategy']    = df['Strategy_Return'] - df['Costs']
df = df.dropna()

print(f"✅ Strategy signals calculated")

# ── Step 3: Extract Individual Trades ─────────────────────────────────────────
# This is the core new piece — scanning position transitions
# to identify discrete entry and exit events.

print(f"\nExtracting individual trades...")

trades    = []                           # [VARIABLE - list] all trade records
in_trade  = False                        # [VARIABLE - bool] currently in position?
entry_date  = None                       # [VARIABLE - Timestamp] when we entered
entry_price = None                       # [VARIABLE - float] price at entry

for i in range(1, len(df)):
    prev_pos = df['Position'].iloc[i-1]  # [VARIABLE - float] yesterday's position
    curr_pos = df['Position'].iloc[i]    # [VARIABLE - float] today's position
    curr_price = float(df['Close'].iloc[i])  # [VARIABLE - float] today's price
    curr_date  = df.index[i]             # [VARIABLE - Timestamp] today's date

    # Detect ENTRY: position changed from 0 to 1
    if prev_pos == 0 and curr_pos == 1:
        in_trade    = True
        entry_date  = curr_date
        entry_price = curr_price

    # Detect EXIT: position changed from 1 to 0
    elif prev_pos == 1 and curr_pos == 0 and in_trade:
        exit_date  = curr_date           # [VARIABLE - Timestamp] exit date
        exit_price = curr_price          # [VARIABLE - float] exit price

        # Calculate trade metrics
        hold_days   = (exit_date - entry_date).days  # [VARIABLE - int]
        pnl_pct     = (exit_price - entry_price) / entry_price  # [VARIABLE - float]
        pnl_pct_net = pnl_pct - (2 * COSTS)          # [VARIABLE - float] after costs
        pnl_dollars = STARTING_CAPITAL * pnl_pct_net  # [VARIABLE - float] dollar P&L
        win_loss    = 'WIN' if pnl_pct_net > 0 else 'LOSS'  # [VARIABLE - str]

        trades.append({                  # [VARIABLE - dict] single trade record
            'strategy_id':   STRATEGY_ID,
            'symbol':        SYMBOL,
            'entry_date':    entry_date.strftime('%Y-%m-%d'),
            'entry_price':   round(entry_price, 2),
            'exit_date':     exit_date.strftime('%Y-%m-%d'),
            'exit_price':    round(exit_price, 2),
            'hold_days':     hold_days,
            'pnl_pct':       round(pnl_pct_net * 100, 3),
            'pnl_dollars':   round(pnl_dollars, 2),
            'win_loss':      win_loss,
            'exit_reason':   'ADX_SIGNAL',  # stop-loss not yet modelled (A002)
            'logged_at':     datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        in_trade = False

# Handle open position at end of data
if in_trade:
    print(f"  ⚠️  Open position at end of data — not counted as completed trade")

trades_df = pd.DataFrame(trades)         # [VARIABLE - DataFrame] all trades
print(f"✅ {len(trades_df)} completed trades extracted")

# ── Step 4: Calculate Real Win Rate and Kelly Inputs ─────────────────────────

print(f"\n{'─' * 70}")
print(f"REAL TRADE STATISTICS (replaces Day 2 estimates)")
print(f"{'─' * 70}")

total_trades  = len(trades_df)           # [VARIABLE - int]
winners       = trades_df[trades_df['win_loss'] == 'WIN']   # [VARIABLE - DataFrame]
losers        = trades_df[trades_df['win_loss'] == 'LOSS']  # [VARIABLE - DataFrame]

real_win_rate = len(winners) / total_trades  # [VARIABLE - float] measured win rate
avg_win_pct   = winners['pnl_pct'].mean() / 100  # [VARIABLE - float] avg win size
avg_loss_pct  = abs(losers['pnl_pct'].mean()) / 100  # [VARIABLE - float] avg loss size
avg_hold_days = trades_df['hold_days'].mean()  # [VARIABLE - float] avg hold duration

print(f"\n  Total trades:     {total_trades}")
print(f"  Winners:          {len(winners)} ({real_win_rate:.1%})")
print(f"  Losers:           {len(losers)} ({1-real_win_rate:.1%})")
print(f"  Avg win:          {avg_win_pct:.2%}")
print(f"  Avg loss:         {avg_loss_pct:.2%}")
print(f"  Win/loss ratio:   {avg_win_pct/avg_loss_pct:.2f}x")
print(f"  Avg hold:         {avg_hold_days:.1f} days")

# Compare to Day 2 estimates
print(f"\n  COMPARISON TO DAY 2 ESTIMATES:")
print(f"  {'Metric':<20} {'Day 2 Estimate':>16} {'Real Measured':>16} {'Difference':>12}")
print(f"  {'─'*65}")

wr_str  = f"{real_win_rate:.1%}"
aw_str  = f"{avg_win_pct:.2%}"
al_str  = f"{avg_loss_pct:.2%}"
print(f"  {'Win rate':<20} {'50.0%':>16} {wr_str:>16} {(real_win_rate - 0.50)*100:>+11.1f}%")
print(f"  {'Avg win':<20} {'9.93%':>16} {aw_str:>16} {(avg_win_pct - 0.0993)*100:>+11.2f}%")
print(f"  {'Avg loss':<20} {'5.00%':>16} {al_str:>16} {(avg_loss_pct - 0.05)*100:>+11.2f}%")


# ── Step 5: Re-run Kelly with Real Inputs ─────────────────────────────────────

print(f"\n{'─' * 70}")
print(f"KELLY CRITERION — REAL INPUTS")
print(f"{'─' * 70}")

# Kelly formula: f* = (p*b - q) / b
p = real_win_rate                        # [VARIABLE - float] real win probability
q = 1 - p                                # [VARIABLE - float] real loss probability
b = avg_win_pct / avg_loss_pct           # [VARIABLE - float] real reward:risk ratio

full_kelly_real = (p * b - q) / b        # [VARIABLE - float] full Kelly
half_kelly_real = full_kelly_real * 0.5  # [VARIABLE - float] half Kelly
safe_kelly_real = min(half_kelly_real, 0.25)  # [VARIABLE - float] capped at 25%

print(f"\n  Real inputs:")
print(f"  p (win rate):      {p:.1%}")
print(f"  b (reward:risk):   {b:.2f}x")
print(f"\n  Full Kelly:        {full_kelly_real:.2%}")
print(f"  Half Kelly:        {half_kelly_real:.2%}")
print(f"  Recommended:       {safe_kelly_real:.2%}")

# Compare to Day 2 Kelly
old_kelly = 0.1241                       # [VARIABLE - float] Day 2 estimate
difference = safe_kelly_real - old_kelly # [VARIABLE - float] change

print(f"\n  COMPARISON TO DAY 2 KELLY:")
print(f"  Day 2 (estimated):  {old_kelly:.2%}")
print(f"  Day 3 (real):       {safe_kelly_real:.2%}")
print(f"  Difference:         {difference:+.2%}")

if abs(difference) > 0.02:
    print(f"\n  ⚠️  Material difference — update RiskManager position_pct")
    print(f"     Change core/execution/risk_manager.py:")
    print(f"     'position_pct': {safe_kelly_real:.4f}")
else:
    print(f"\n  ✅ Immaterial difference — Day 2 Kelly sizing remains valid")
    print(f"     No change needed to RiskManager")

# ── Step 6: Aggregate Strategy Metrics ───────────────────────────────────────

print(f"\n{'─' * 70}")
print(f"AGGREGATE STRATEGY METRICS")
print(f"{'─' * 70}")

total_return  = (1 + df['Net_Strategy']).prod() - 1
years         = (df.index[-1] - df.index[0]).days / 365
annual_return = (1 + total_return) ** (1/years) - 1
sharpe        = (df['Net_Strategy'].mean() /
                 df['Net_Strategy'].std() * np.sqrt(365))

downside      = df['Net_Strategy'][df['Net_Strategy'] < 0]
sortino       = (df['Net_Strategy'].mean() /
                 downside.std() * np.sqrt(365))

cumulative    = (1 + df['Net_Strategy']).cumprod()
running_max   = cumulative.expanding().max()
drawdown      = (cumulative - running_max) / running_max
max_drawdown  = drawdown.min()

calmar        = annual_return / abs(max_drawdown)  # [VARIABLE - float]
profit_factor = (winners['pnl_dollars'].sum() /    # [VARIABLE - float]
                 abs(losers['pnl_dollars'].sum()))

print(f"\n  Annual return:    {annual_return:.2%}")
print(f"  Sharpe ratio:     {sharpe:.3f}")
print(f"  Sortino ratio:    {sortino:.3f}")
print(f"  Calmar ratio:     {calmar:.3f}")
print(f"  Max drawdown:     {max_drawdown:.2%}")
print(f"  Profit factor:    {profit_factor:.2f}x")
print(f"  Win rate:         {real_win_rate:.1%}")
print(f"  Avg hold:         {avg_hold_days:.1f} days")

# ── Step 7: Save Trade Log ────────────────────────────────────────────────────

print(f"\n{'─' * 70}")
print(f"SAVING RESULTS")
print(f"{'─' * 70}")

# Load existing trade log or create new one
if os.path.exists(TRADE_LOG_PATH):
    existing_trades = pd.read_csv(TRADE_LOG_PATH)  # [VARIABLE - DataFrame]

    # Remove any existing entries for this strategy (avoid duplicates on re-run)
    existing_trades = existing_trades[
        existing_trades['strategy_id'] != STRATEGY_ID
    ]
    combined_trades = pd.concat(         # [VARIABLE - DataFrame]
        [existing_trades, trades_df],
        ignore_index=True
    )
else:
    combined_trades = trades_df

combined_trades.to_csv(TRADE_LOG_PATH, index=False)
print(f"\n✅ Trade log saved: {TRADE_LOG_PATH}")
print(f"   {len(trades_df)} trades for {STRATEGY_ID}")
print(f"   {len(combined_trades)} total trades across all strategies")

# ── Step 8: Save Strategy Registry ───────────────────────────────────────────

registry_entry = {                       # [VARIABLE - dict] strategy summary
    'logged_at':      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'strategy_id':    STRATEGY_ID,
    'symbol':         SYMBOL,
    'start_date':     START_DATE,
    'end_date':       df.index[-1].strftime('%Y-%m-%d'),
    'threshold':      THRESHOLD,
    'period':         PERIOD,
    'annual_return':  round(annual_return, 4),
    'sharpe':         round(sharpe, 4),
    'sortino':        round(sortino, 4),
    'calmar':         round(calmar, 4),
    'max_drawdown':   round(max_drawdown, 4),
    'total_trades':   total_trades,
    'win_rate':       round(real_win_rate, 4),
    'avg_win_pct':    round(avg_win_pct, 4),
    'avg_loss_pct':   round(avg_loss_pct, 4),
    'profit_factor':  round(profit_factor, 4),
    'avg_hold_days':  round(avg_hold_days, 1),
    'kelly_full':     round(full_kelly_real, 4),
    'kelly_half':     round(half_kelly_real, 4),
    'kelly_recommended': round(safe_kelly_real, 4),
    'validated':      True,
    'notes':          'ADX 20/10 validated Week 4. Stop-loss not yet modelled (A002).'
}

if os.path.exists(REGISTRY_PATH):
    registry = pd.read_csv(REGISTRY_PATH)  # [VARIABLE - DataFrame]
    registry = registry[registry['strategy_id'] != STRATEGY_ID]
    registry = pd.concat(
        [registry, pd.DataFrame([registry_entry])],
        ignore_index=True
    )
else:
    registry = pd.DataFrame([registry_entry])

registry.to_csv(REGISTRY_PATH, index=False)
print(f"✅ Strategy registry saved: {REGISTRY_PATH}")

# ── Step 9: Update Kelly Results JSON ────────────────────────────────────────

kelly_updated = {                        # [VARIABLE - dict] updated Kelly results
    'version':          'v2_real_inputs',
    'updated_at':       datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'inputs': {
        'win_rate':     round(real_win_rate, 4),
        'avg_win_pct':  round(avg_win_pct, 4),
        'avg_loss_pct': round(avg_loss_pct, 4),
        'source':       'measured_from_193_trades'
    },
    'outputs': {
        'full_kelly':   round(full_kelly_real, 4),
        'half_kelly':   round(half_kelly_real, 4),
        'recommended':  round(safe_kelly_real, 4),
        'position_for_1k': round(1000 * safe_kelly_real, 2)
    },
    'vs_day2': {
        'day2_kelly':   old_kelly,
        'day3_kelly':   round(safe_kelly_real, 4),
        'difference':   round(difference, 4),
        'material':     bool(abs(difference) > 0.02)
    }
}

with open(KELLY_PATH, 'w') as f:
    json.dump(kelly_updated, f, indent=2)

print(f"✅ Kelly results updated: {KELLY_PATH}")

# ── Step 10: Print Top 10 Trades ──────────────────────────────────────────────

print(f"\n{'─' * 70}")
print(f"TOP 10 WINNING TRADES")
print(f"{'─' * 70}")

top_wins = (winners
    .nlargest(10, 'pnl_pct')
    [['entry_date', 'exit_date', 'hold_days', 'pnl_pct', 'pnl_dollars']]
)

print(f"\n  {'Entry':<12} {'Exit':<12} {'Days':>6} {'P&L %':>8} {'P&L $':>10}")
print(f"  {'─'*52}")
for _, row in top_wins.iterrows():
    print(f"  {row['entry_date']:<12} {row['exit_date']:<12} "
          f"{int(row['hold_days']):>6} {row['pnl_pct']:>7.1f}% "
          f"${row['pnl_dollars']:>9.2f}")

print(f"\n{'─' * 70}")
print(f"TOP 10 LOSING TRADES")
print(f"{'─' * 70}")

top_losses = (losers
    .nsmallest(10, 'pnl_pct')
    [['entry_date', 'exit_date', 'hold_days', 'pnl_pct', 'pnl_dollars']]
)

print(f"\n  {'Entry':<12} {'Exit':<12} {'Days':>6} {'P&L %':>8} {'P&L $':>10}")
print(f"  {'─'*52}")
for _, row in top_losses.iterrows():
    print(f"  {row['entry_date']:<12} {row['exit_date']:<12} "
          f"{int(row['hold_days']):>6} {row['pnl_pct']:>7.1f}% "
          f"${row['pnl_dollars']:>9.2f}")

print(f"\n{'=' * 70}")
print(f"✅ DAY 3 TRADE LOGGING COMPLETE")
print(f"   A001 RESOLVED — Real win rate measured: {real_win_rate:.1%}")
print(f"   A005 RESOLVED — Kelly re-run with real inputs: {safe_kelly_real:.2%}")
print(f"{'=' * 70}\n")