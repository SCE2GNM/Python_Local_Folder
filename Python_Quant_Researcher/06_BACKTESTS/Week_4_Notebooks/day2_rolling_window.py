# [FILE] day2_rolling_window.py
# PURPOSE: Rolling Window walk-forward validation of ADX 20/10 parameters
#
# WHY DOES THIS MATTER BEFORE DEPLOYING REAL MONEY?
# A backtest can accidentally find parameters that worked historically
# but only because of data snooping — the optimiser saw all the data
# and found settings that fit it perfectly, like memorising exam answers
# rather than understanding the subject.
#
# Walk-forward testing prevents this by enforcing a strict rule:
# parameters are ALWAYS optimised on past data and ALWAYS tested
# on future data the optimiser never saw.
#
# If ADX 20/10 consistently appears as the best parameters across
# multiple independent time windows, that's genuine robustness —
# not curve fitting.
#
# ROLLING vs EXPANDING WINDOW (recap):
#
#   Expanding: Train window grows each year (uses all history)
#   Rolling:   Train window stays fixed size, shifts forward each year
#
#   Rolling is MORE conservative — it only uses recent market conditions
#   for training. If ADX 20/10 passes both, confidence is very high.

# ── Imports ───────────────────────────────────────────────────────────────────

import pandas as pd                      # [LIBRARY] data manipulation
import numpy as np                       # [LIBRARY] numerical calculations
import yfinance as yf                    # [LIBRARY] historical price data
from ta.trend import ADXIndicator        # [LIBRARY] ADX calculation
import json                              # [LIBRARY] save results
import warnings                          # [LIBRARY] suppress minor warnings
warnings.filterwarnings('ignore')

# ── Configuration ─────────────────────────────────────────────────────────────

SYMBOL     = 'ETH-USD'      # [VARIABLE - str] asset to test
START_DATE = '2018-01-01'   # [VARIABLE - str] full dataset start
END_DATE   = '2024-12-31'   # [VARIABLE - str] full dataset end
COSTS      = 0.00175        # [VARIABLE - float] 0.175% transaction cost

# Parameter grid to search
# Same grid as Week 2 so results are directly comparable
THRESHOLDS = [20, 22, 25, 27, 30, 32, 35]   # [VARIABLE - list] ADX thresholds
PERIODS    = [10, 14, 20, 25]                # [VARIABLE - list] ADX periods

# Our target parameters from Week 2
TARGET_THRESHOLD = 20        # [VARIABLE - int] what we want to see confirmed
TARGET_PERIOD    = 10        # [VARIABLE - int] what we want to see confirmed

# ── Step 1: Fetch Data ────────────────────────────────────────────────────────

print("=" * 80)
print("ROLLING WINDOW WALK-FORWARD VALIDATION")
print("=" * 80)
print(f"\nFetching ETH-USD daily data {START_DATE} to {END_DATE}...")

df_full = yf.download(                   # [VARIABLE - DataFrame] full price history
    SYMBOL,
    start    = START_DATE,
    end      = END_DATE,
    interval = '1d',
    auto_adjust = True,
    progress = False
)

# Flatten multi-level columns (yfinance compatibility fix)
df_full.columns = df_full.columns.get_level_values(0)

print(f"✅ Downloaded {len(df_full):,} daily candles")

# ── Step 2: Strategy Functions ────────────────────────────────────────────────

def run_strategy(data, threshold, period):
    """
    [FUNCTION] Run ADX strategy on a dataset and return performance metrics.

    Args:
        data      [DataFrame]: OHLCV price data
        threshold [int]      : ADX threshold (e.g. 20)
        period    [int]      : ADX period (e.g. 10)

    Returns:
        dict: Performance metrics (sharpe, return, trades)
        None: If insufficient data
    """
    df = data.copy()

    # Need enough data to calculate ADX
    if len(df) < period + 30:
        return None

    # Calculate ADX
    adx_ind  = ADXIndicator(
        high   = df['High'].squeeze(),
        low    = df['Low'].squeeze(),
        close  = df['Close'].squeeze(),
        window = period
    )

    df['ADX']    = adx_ind.adx()
    df['+DI']    = adx_ind.adx_pos()
    df['-DI']    = adx_ind.adx_neg()

    # Generate signals
    df['Position'] = (
        (df['ADX'] >= threshold) &
        (df['+DI'] > df['-DI'])
    ).astype(int)                        # [VARIABLE - Series] 1=LONG, 0=FLAT

    # Calculate returns
    df['Market_Return']   = df['Close'].pct_change()
    df['Strategy_Return'] = df['Position'].shift(1) * df['Market_Return']

    # Apply transaction costs
    df['Position_Change'] = df['Position'].diff().abs()
    df['Costs']           = df['Position_Change'] * COSTS
    df['Net_Strategy']    = df['Strategy_Return'] - df['Costs']

    # Drop NaN rows from ADX warmup period
    df = df.dropna()

    if len(df) < 30:
        return None

    # Calculate metrics
    total_return  = (1 + df['Net_Strategy']).prod() - 1
    sharpe        = (df['Net_Strategy'].mean() /
                     df['Net_Strategy'].std() *
                     np.sqrt(365))
    trades        = df['Position_Change'].sum()

    return {                             # [VARIABLE - dict] performance metrics
        'total_return': total_return,
        'sharpe':       sharpe,
        'trades':       trades
    }


def find_best_params(train_data, thresholds, periods):
    """
    [FUNCTION] Grid search to find best ADX parameters on training data.

    Args:
        train_data [DataFrame]: Training period price data
        thresholds [list]     : ADX threshold values to test
        periods    [list]     : ADX period values to test

    Returns:
        tuple: (best_threshold, best_period, best_sharpe)
    """
    best_sharpe    = -999        # [VARIABLE - float] track best Sharpe found
    best_threshold = None        # [VARIABLE - int] best threshold found
    best_period    = None        # [VARIABLE - int] best period found

    for threshold in thresholds:
        for period in periods:
            result = run_strategy(train_data, threshold, period)

            if result and result['sharpe'] > best_sharpe:
                best_sharpe    = result['sharpe']
                best_threshold = threshold
                best_period    = period

    return best_threshold, best_period, best_sharpe

# ── Step 3: Define Rolling Windows ────────────────────────────────────────────
# 5 windows, each with 2-year training and 1-year test
# Stepping forward one year at a time

windows = [                              # [VARIABLE - list] window definitions
    # (train_start, train_end, test_start, test_end, test_year)
    ('2018-01-01', '2019-12-31', '2020-01-01', '2020-12-31', 2020),
    ('2019-01-01', '2020-12-31', '2021-01-01', '2021-12-31', 2021),
    ('2020-01-01', '2021-12-31', '2022-01-01', '2022-12-31', 2022),
    ('2021-01-01', '2022-12-31', '2023-01-01', '2023-12-31', 2023),
    ('2022-01-01', '2023-12-31', '2024-01-01', '2024-12-31', 2024),
]

# ── Step 4: Run Rolling Window Analysis ───────────────────────────────────────

print(f"\nRunning {len(windows)} rolling windows...")
print(f"Each window: 2-year train → 1-year test")
print(f"Parameter grid: {len(THRESHOLDS) * len(PERIODS)} combinations per window\n")

results = []                             # [VARIABLE - list] all window results

for train_start, train_end, test_start, test_end, test_year in windows:

    print(f"Window {test_year}: Train {train_start[:4]}-{train_end[:4]} "
          f"→ Test {test_year}...")

    # Slice training and test data
    train_data = df_full.loc[train_start:train_end].copy()  # [VARIABLE - DataFrame]
    test_data  = df_full.loc[test_start:test_end].copy()    # [VARIABLE - DataFrame]

    # Find best parameters on training data
    best_threshold, best_period, train_sharpe = find_best_params(
        train_data, THRESHOLDS, PERIODS
    )

    # Test those parameters on unseen test data
    test_result = run_strategy(test_data, best_threshold, best_period)

    if test_result is None:
        print(f"  ⚠️  Insufficient test data for {test_year}")
        continue

    test_sharpe = test_result['sharpe']
    test_return = test_result['total_return']

    # Calculate how much performance degraded from train to test
    # Degradation = how far Sharpe dropped as a percentage
    if abs(train_sharpe) > 0:
        degradation = (train_sharpe - test_sharpe) / abs(train_sharpe) * 100
    else:
        degradation = 0

    # Check if our target parameters (ADX 20/10) were selected
    target_selected = (                  # [VARIABLE - bool]
        best_threshold == TARGET_THRESHOLD and
        best_period    == TARGET_PERIOD
    )

    print(f"  Best params:  ADX {best_threshold}/{best_period} "
          f"{'✅ (our params)' if target_selected else '⚠️  (different)'}")
    print(f"  Train Sharpe: {train_sharpe:.3f}")
    print(f"  Test Sharpe:  {test_sharpe:.3f}")
    print(f"  Test Return:  {test_return:.2%}")
    print(f"  Degradation:  {degradation:.1f}%\n")

    results.append({                     # [VARIABLE - dict] window result
        'year':            test_year,
        'best_threshold':  best_threshold,
        'best_period':     best_period,
        'train_sharpe':    round(train_sharpe, 3),
        'test_sharpe':     round(test_sharpe, 3),
        'test_return':     round(test_return, 4),
        'degradation':     round(degradation, 1),
        'target_selected': target_selected
    })

# ── Step 5: Summary Analysis ──────────────────────────────────────────────────

print("=" * 80)
print("ROLLING WINDOW SUMMARY")
print("=" * 80)

results_df = pd.DataFrame(results)      # [VARIABLE - DataFrame] all results

# Print results table
print(f"\n{'Year':<6} {'Params':<12} {'Train Sharpe':<14} "
      f"{'Test Sharpe':<13} {'Test Return':<13} {'Degrad.':<10} {'Target?'}")
print("─" * 80)

for _, row in results_df.iterrows():
    target_str = "✅ YES" if row['target_selected'] else "⚠️  NO"
    print(f"{int(row['year']):<6} "
          f"ADX {int(row['best_threshold'])}/{int(row['best_period']):<7} "
          f"{row['train_sharpe']:<14.3f} "
          f"{row['test_sharpe']:<13.3f} "
          f"{row['test_return']:<13.2%} "
          f"{row['degradation']:<10.1f} "
          f"{target_str}")

# ── Step 6: Parameter Stability ───────────────────────────────────────────────

print(f"\n{'─' * 80}")
print(f"PARAMETER STABILITY")
print(f"{'─' * 80}")

# Count how many times each parameter combination was selected
param_counts = (results_df
    .groupby(['best_threshold', 'best_period'])
    .size()
    .sort_values(ascending=False))      # [VARIABLE - Series] parameter frequency

print(f"\nMost frequently selected parameters:")
for (threshold, period), count in param_counts.items():
    marker = " ← OUR PARAMS" if (threshold == TARGET_THRESHOLD and
                                   period == TARGET_PERIOD) else ""
    print(f"  ADX {int(threshold)}/{int(period)}: selected {count}/5 windows{marker}")

target_count = results_df['target_selected'].sum()  # [VARIABLE - int]

# ── Step 7: Performance Statistics ───────────────────────────────────────────

print(f"\n{'─' * 80}")
print(f"PERFORMANCE STATISTICS")
print(f"{'─' * 80}")

avg_test_sharpe  = results_df['test_sharpe'].mean()   # [VARIABLE - float]
avg_degradation  = results_df['degradation'].mean()   # [VARIABLE - float]
positive_years   = (results_df['test_return'] > 0).sum()  # [VARIABLE - int]
worst_year       = results_df.loc[results_df['test_return'].idxmin()]

print(f"\n  Average out-of-sample Sharpe: {avg_test_sharpe:.3f}")
print(f"  Average degradation:          {avg_degradation:.1f}%")
print(f"  Profitable test years:        {positive_years}/{len(results_df)}")
print(f"  Worst year:                   "
      f"{int(worst_year['year'])} ({worst_year['test_return']:.2%})")

# ── Step 8: Validation Decision ───────────────────────────────────────────────

print(f"\n{'─' * 80}")
print(f"VALIDATION DECISION")
print(f"{'─' * 80}")

# Gate criteria:
# 1. ADX 20/10 selected in at least 3 of 5 windows (60%+ stability)
# 2. Average out-of-sample Sharpe > 0 (strategy adds value out-of-sample)
# 3. Strategy profitable in at least 3 of 5 test years

criteria_1 = target_count >= 3          # [VARIABLE - bool] parameter stability
criteria_2 = avg_test_sharpe > 0        # [VARIABLE - bool] positive out-of-sample
criteria_3 = positive_years >= 3        # [VARIABLE - bool] consistent profitability

print(f"\n  Criteria 1 — ADX 20/10 selected ≥3/5 windows: "
      f"{'✅' if criteria_1 else '❌'} ({target_count}/5)")
print(f"  Criteria 2 — Average out-of-sample Sharpe > 0: "
      f"{'✅' if criteria_2 else '❌'} ({avg_test_sharpe:.3f})")
print(f"  Criteria 3 — Profitable in ≥3/5 test years:   "
      f"{'✅' if criteria_3 else '❌'} ({positive_years}/5)")

all_passed = criteria_1 and criteria_2 and criteria_3  # [VARIABLE - bool]

print(f"\n{'=' * 80}")
if all_passed:
    print(f"✅ ROLLING WINDOW VALIDATION PASSED")
    print(f"   ADX 20/10 confirmed stable across multiple market regimes")
    print(f"   Parameters validated for live deployment")
else:
    print(f"❌ ROLLING WINDOW VALIDATION FAILED")
    print(f"   Investigate parameter stability before deploying real money")
print(f"{'=' * 80}\n")

# ── Save Results ──────────────────────────────────────────────────────────────

rolling_summary = {                      # [VARIABLE - dict] summary for JSON
    'windows_tested':     len(results),
    'target_selected':    int(target_count),
    'avg_test_sharpe':    round(avg_test_sharpe, 3),
    'avg_degradation':    round(avg_degradation, 1),
    'profitable_years':   int(positive_years),
    'validation_passed':  bool(all_passed),
    'window_results':     results
}

with open('Week_4_Notebooks/rolling_window_results.json', 'w') as f:
    json.dump(rolling_summary, f, indent=2)

print(f"✅ Results saved to rolling_window_results.json")