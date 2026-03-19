# [FILE] week4_daily_validation.py
# PURPOSE: Re-validate ADX 20/10 strategy on DAILY candles
# CRITICAL: Week 3 used 1-minute candles for infrastructure testing only.
#           Your ADX 20/10 parameters were optimised on DAILY candles in Week 2.
#           Before deploying real money, we must confirm those parameters still
#           hold on the correct timeframe.

# ── Imports ───────────────────────────────────────────────────────────────────

import yfinance as yf                    # [LIBRARY] fetches historical price data
import pandas as pd                      # [LIBRARY] data manipulation
import numpy as np                       # [LIBRARY] numerical calculations
from ta.trend import ADXIndicator        # [LIBRARY] calculates ADX indicator
import json                              # [LIBRARY] saves results to file

# ── Configuration ─────────────────────────────────────────────────────────────

SYMBOL     = 'ETH-USD'    # [VARIABLE - str] asset to test
START_DATE = '2018-01-01' # [VARIABLE - str] backtest start date
THRESHOLD  = 20           # [VARIABLE - int] ADX threshold from Week 2 optimisation
PERIOD     = 10           # [VARIABLE - int] ADX period from Week 2 optimisation
COSTS      = 0.00175      # [VARIABLE - float] 0.175% transaction cost per trade

# ── Week 2 Benchmark ──────────────────────────────────────────────────────────
# These are the results we expect to reproduce.
# If today's results differ significantly, something is wrong.

WEEK2_SHARPE  = 0.906   # [VARIABLE - float] expected Sharpe ratio
WEEK2_RETURN  = 0.442   # [VARIABLE - float] expected annual return (44.2%)
WEEK2_TRADES  = 23.4    # [VARIABLE - float] expected trades per year

# ── Step 1: Fetch Daily Data ───────────────────────────────────────────────────
# This is the critical difference from Week 3.
# interval='1d' = one candle per DAY (correct for our strategy)
# interval='1m' = one candle per MINUTE (what Week 3 used for infrastructure testing)

print("=" * 70)
print("WEEK 4 - DAILY TIMEFRAME VALIDATION")
print("=" * 70)
print(f"\nFetching ETH-USD daily candles from {START_DATE}...")

df = yf.download(            # [FUNCTION] downloads historical OHLCV data
    SYMBOL,                  # which asset
    start=START_DATE,        # how far back
    interval='1d',           # ← DAILY candles (not 1m!)
    auto_adjust=True,        # adjusts for splits/dividends
    progress=False           # suppresses download progress bar
)

print(f"✅ Downloaded {len(df):,} daily candles")
print(f"   From: {df.index[0].date()}")
print(f"   To:   {df.index[-1].date()}")

# ── Step 2: Calculate ADX Indicator ───────────────────────────────────────────
# ADXIndicator needs High, Low, Close prices and a lookback window (period).
# It returns three values:
#   ADX    = trend STRENGTH (0-100). Above threshold = strong trend
#   +DI    = positive directional index (bulls in control when this is higher)
#   -DI    = negative directional index (bears in control when this is higher)
#
# .squeeze() fixes a yfinance compatibility issue — newer versions return
# 2D arrays instead of 1D Series. squeeze() flattens them to 1D.

print(f"\nCalculating ADX (threshold={THRESHOLD}, period={PERIOD})...")

# Fix for yfinance multi-level column format
high  = df['High'].squeeze()   # [VARIABLE - Series] 1D daily high prices
low   = df['Low'].squeeze()    # [VARIABLE - Series] 1D daily low prices
close = df['Close'].squeeze()  # [VARIABLE - Series] 1D daily close prices

adx_indicator = ADXIndicator(   # [OBJECT] ADX calculator
    high   = high,
    low    = low,
    close  = close,
    window = PERIOD             # lookback period (10 days)
)

df['ADX']     = adx_indicator.adx()       # [VARIABLE - Series] trend strength
df['+DI']     = adx_indicator.adx_pos()  # [VARIABLE - Series] bullish pressure
df['-DI']     = adx_indicator.adx_neg()  # [VARIABLE - Series] bearish pressure

# ── Step 3: Generate Signals ───────────────────────────────────────────────────
# Our strategy has two conditions that must BOTH be true to go LONG:
#   1. Trending: ADX >= 20 (market is trending strongly enough)
#   2. Bullish:  +DI > -DI (trend direction is upward)
# Position = 1 means LONG (holding ETH)
# Position = 0 means FLAT (holding cash)

df['Trending']  = df['ADX'] >= THRESHOLD          # [VARIABLE - Series bool] is market trending?
df['Bullish']   = df['+DI'] > df['-DI']           # [VARIABLE - Series bool] is trend bullish?
df['Position']  = (df['Trending'] & df['Bullish']).astype(int)  # [VARIABLE - Series int] 1=LONG, 0=FLAT

# ── Step 4: Calculate Returns ──────────────────────────────────────────────────
# Market_Return = what ETH did each day (buy and hold)
# Strategy_Return = what OUR strategy did each day
# The .shift(1) is critical — it means we act on YESTERDAY's signal TODAY.
# Without shift(1) we'd be looking into the future (cheating).

df['Market_Return']   = df['Close'].pct_change()                          # [VARIABLE - Series] daily ETH return
df['Strategy_Return'] = df['Position'].shift(1) * df['Market_Return']    # [VARIABLE - Series] our daily return

# ── Step 5: Apply Transaction Costs ───────────────────────────────────────────
# Every time we change position (enter or exit), we pay 0.175% in fees.
# Position_Change detects those transitions (0→1 = buy, 1→0 = sell).

df['Position_Change'] = df['Position'].diff().abs()           # [VARIABLE - Series] 1 on trade days, 0 otherwise
df['Costs']           = df['Position_Change'] * COSTS         # [VARIABLE - Series] cost on trade days
df['Net_Strategy']    = df['Strategy_Return'] - df['Costs']   # [VARIABLE - Series] return after costs

# ── Step 6: Calculate Performance Metrics ─────────────────────────────────────

# Total return over entire backtest period
total_return = (1 + df['Net_Strategy']).prod() - 1    # [VARIABLE - float] e.g. 9.03 = 903%

# Number of years in backtest (for annualising)
years = (df.index[-1] - df.index[0]).days / 365       # [VARIABLE - float] e.g. 7.2 years

# Annual return (geometric)
annual_return = (1 + total_return) ** (1 / years) - 1 # [VARIABLE - float] e.g. 0.442 = 44.2%/year

# Sharpe Ratio = return per unit of risk
# sqrt(365) annualises daily Sharpe to yearly
sharpe = (
    df['Net_Strategy'].mean() /
    df['Net_Strategy'].std() *
    np.sqrt(365)
)                                                      # [VARIABLE - float] e.g. 0.906

# Maximum Drawdown = worst peak-to-trough loss
cumulative   = (1 + df['Net_Strategy']).cumprod()     # [VARIABLE - Series] portfolio growth curve
running_max  = cumulative.expanding().max()            # [VARIABLE - Series] highest point so far
drawdown     = (cumulative - running_max) / running_max # [VARIABLE - Series] drawdown at each point
max_drawdown = drawdown.min()                          # [VARIABLE - float] worst drawdown e.g. -0.468

# Trade frequency
total_trades     = df['Position_Change'].sum()         # [VARIABLE - float] total number of trades
trades_per_year  = total_trades / years                # [VARIABLE - float] trades per year

# ── Step 7: Print Results ──────────────────────────────────────────────────────

print(f"\n{'=' * 70}")
print(f"VALIDATION RESULTS - ADX {THRESHOLD}/{PERIOD} ON DAILY CANDLES")
print(f"{'=' * 70}")
print(f"  Date Range:       {df.index[0].date()} → {df.index[-1].date()}")
print(f"  Total Candles:    {len(df):,} daily bars")
print(f"  Total Return:     {total_return:.2%}")
print(f"  Annual Return:    {annual_return:.2%}")
print(f"  Sharpe Ratio:     {sharpe:.3f}")
print(f"  Max Drawdown:     {max_drawdown:.2%}")
print(f"  Total Trades:     {total_trades:.0f}")
print(f"  Trades/Year:      {trades_per_year:.1f}")

print(f"\n{'=' * 70}")
print(f"COMPARISON TO WEEK 2 BENCHMARK")
print(f"{'=' * 70}")
print(f"  Metric          Week 2      Today       Status")
print(f"  {'─' * 55}")
print(f"  Annual Return   {WEEK2_RETURN:.1%}       {annual_return:.1%}        {'✅' if annual_return >= WEEK2_RETURN * 0.8 else '❌'}")
print(f"  Sharpe Ratio    {WEEK2_SHARPE:.3f}       {sharpe:.3f}        {'✅' if sharpe >= 0.85 else '❌'}")
print(f"  Trades/Year     {WEEK2_TRADES:.1f}        {trades_per_year:.1f}         {'✅' if abs(trades_per_year - WEEK2_TRADES) < 5 else '❌'}")

# ── Step 8: Validation Decision ───────────────────────────────────────────────
# Gate: Sharpe must be >= 0.85 to proceed to live deployment.
# A Sharpe below 0.85 means the strategy has degraded significantly
# since Week 2 and should be investigated before risking real money.

print(f"\n{'=' * 70}")

if sharpe >= 0.85:
    print(f"✅ VALIDATION PASSED")
    print(f"   Sharpe {sharpe:.3f} >= 0.85 threshold")
    print(f"   ADX {THRESHOLD}/{PERIOD} confirmed on daily timeframe")
    print(f"   SAFE TO PROCEED to order execution (Task 1)")
else:
    print(f"❌ VALIDATION FAILED")
    print(f"   Sharpe {sharpe:.3f} is below 0.85 threshold")
    print(f"   DO NOT proceed to live deployment")
    print(f"   Investigate discrepancy before risking real money")

print(f"{'=' * 70}\n")

# ── Step 9: Save Results ───────────────────────────────────────────────────────
# Save to JSON so we can reference these numbers later in the week

results = {                              # [VARIABLE - dict] all metrics
    'symbol':          SYMBOL,
    'start_date':      START_DATE,
    'end_date':        str(df.index[-1].date()),
    'threshold':       THRESHOLD,
    'period':          PERIOD,
    'total_return':    round(total_return, 4),
    'annual_return':   round(annual_return, 4),
    'sharpe':          round(sharpe, 4),
    'max_drawdown':    round(max_drawdown, 4),
    'total_trades':    int(total_trades),
    'trades_per_year': round(trades_per_year, 1),
    'validated':       bool(sharpe >= 0.85)
}

output_path = 'Week_4_Notebooks/daily_validation_results.json'

with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"✅ Results saved to {output_path}")
print(f"   This file will be referenced throughout Week 4")