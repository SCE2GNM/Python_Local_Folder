# [FILE] day2_window_comparison.py
# PURPOSE: Side-by-side comparison of Expanding vs Rolling Window results
#          with Sharpe AND Sortino ratios for each test year
#
# WHY COMPARE BOTH METHODS?
# Expanding Window (Week 2): Optimises on ALL available history each year
#   - More data = more stable parameter estimates
#   - But: recent market conditions get diluted by old data
#
# Rolling Window (Day 2): Optimises on most recent 2 years only
#   - Captures recent market regime changes
#   - But: less training data per window
#
# If BOTH methods agree on ADX 20/10 and show similar out-of-sample
# performance, we have very high confidence in the strategy.
#
# WHY ADD SORTINO?
# Sharpe penalises ALL volatility including upside.
# Sortino only penalises DOWNSIDE volatility (actual losses).
# For trend-following strategies that capture large upward moves,
# Sortino gives a fairer picture of risk-adjusted performance.

# ── Imports ───────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np
import yfinance as yf
from ta.trend import ADXIndicator
import json
import warnings
warnings.filterwarnings('ignore')

# ── Configuration ─────────────────────────────────────────────────────────────

SYMBOL     = 'ETH-USD'
START_DATE = '2018-01-01'
END_DATE   = '2024-12-31'
COSTS      = 0.00175
THRESHOLDS = [20, 22, 25, 27, 30, 32, 35]
PERIODS    = [10, 14, 20, 25]

# ── Fetch Data ────────────────────────────────────────────────────────────────

print("=" * 90)
print("EXPANDING vs ROLLING WINDOW — SIDE BY SIDE COMPARISON")
print("=" * 90)
print(f"\nFetching ETH-USD daily data...")

df_full = yf.download(
    SYMBOL,
    start       = START_DATE,
    end         = END_DATE,
    interval    = '1d',
    auto_adjust = True,
    progress    = False
)
df_full.columns = df_full.columns.get_level_values(0)
print(f"✅ {len(df_full):,} daily candles loaded\n")

# ── Strategy + Metrics Function ───────────────────────────────────────────────

def run_strategy(data, threshold, period):
    """
    [FUNCTION] Run ADX strategy and return Sharpe AND Sortino.

    Sortino formula:
        downside_returns = only the negative daily returns
        downside_std     = standard deviation of downside returns only
        sortino          = mean_return / downside_std * sqrt(365)

    Args:
        data      [DataFrame]: OHLCV price data
        threshold [int]      : ADX threshold
        period    [int]      : ADX period

    Returns:
        dict: sharpe, sortino, total_return, trades
    """
    df = data.copy()

    if len(df) < period + 30:
        return None

    # Calculate ADX
    adx_ind = ADXIndicator(
        high   = df['High'].squeeze(),
        low    = df['Low'].squeeze(),
        close  = df['Close'].squeeze(),
        window = period
    )

    df['ADX'] = adx_ind.adx()
    df['+DI'] = adx_ind.adx_pos()
    df['-DI'] = adx_ind.adx_neg()

    # Generate signals
    df['Position'] = (
        (df['ADX'] >= threshold) &
        (df['+DI'] > df['-DI'])
    ).astype(int)

    # Calculate returns
    df['Market_Return']   = df['Close'].pct_change()
    df['Strategy_Return'] = df['Position'].shift(1) * df['Market_Return']
    df['Position_Change'] = df['Position'].diff().abs()
    df['Costs']           = df['Position_Change'] * COSTS
    df['Net_Strategy']    = df['Strategy_Return'] - df['Costs']
    df = df.dropna()

    if len(df) < 30:
        return None

    mean_return  = df['Net_Strategy'].mean()   # [VARIABLE - float] avg daily return
    std_return   = df['Net_Strategy'].std()    # [VARIABLE - float] all volatility
    total_return = (1 + df['Net_Strategy']).prod() - 1
    trades       = df['Position_Change'].sum()

    # Sharpe — penalises all volatility
    sharpe = mean_return / std_return * np.sqrt(365) if std_return > 0 else 0

    # Sortino — only penalises downside volatility
    downside_returns = df['Net_Strategy'][df['Net_Strategy'] < 0]  # [VARIABLE - Series]
    downside_std     = downside_returns.std()                       # [VARIABLE - float]
    sortino = mean_return / downside_std * np.sqrt(365) if downside_std > 0 else 0

    return {
        'sharpe':        round(sharpe, 3),
        'sortino':       round(sortino, 3),
        'total_return':  round(total_return, 4),
        'trades':        int(trades)
    }


def find_best_params(train_data):
    """[FUNCTION] Grid search for best ADX parameters on training data."""
    best_sharpe    = -999
    best_threshold = None
    best_period    = None

    for threshold in THRESHOLDS:
        for period in PERIODS:
            result = run_strategy(train_data, threshold, period)
            if result and result['sharpe'] > best_sharpe:
                best_sharpe    = result['sharpe']
                best_threshold = threshold
                best_period    = period

    return best_threshold, best_period, best_sharpe

# ── Define Test Years ─────────────────────────────────────────────────────────

test_years = [2020, 2021, 2022, 2023, 2024]  # [VARIABLE - list] years to test

# ── Run Expanding Window ──────────────────────────────────────────────────────
# Expanding: training data starts at 2018 and grows each year
# e.g. for test year 2022, train on ALL data from 2018-2021

print("Running Expanding Window analysis...")
expanding_results = []                   # [VARIABLE - list] expanding window results

for test_year in test_years:
    train_start = '2018-01-01'
    train_end   = f'{test_year - 1}-12-31'
    test_start  = f'{test_year}-01-01'
    test_end    = f'{test_year}-12-31'

    train_data = df_full.loc[train_start:train_end].copy()
    test_data  = df_full.loc[test_start:test_end].copy()
    print(f"  Expanding {test_year}: train={train_start} to {train_end} "
          f"({len(train_data)} candles)")
    best_threshold, best_period, train_sharpe = find_best_params(train_data)
    test_result = run_strategy(test_data, best_threshold, best_period)

    if test_result:
        expanding_results.append({
            'year':           test_year,
            'params':         f"ADX {best_threshold}/{best_period}",
            'train_sharpe':   round(train_sharpe, 3),
            'test_sharpe':    test_result['sharpe'],
            'test_sortino':   test_result['sortino'],
            'test_return':    test_result['total_return'],
            'target':         best_threshold == 20 and best_period == 10
        })
        print(f"  {test_year}: ADX {best_threshold}/{best_period} | "
              f"Test Sharpe {test_result['sharpe']:.3f} | "
              f"Sortino {test_result['sortino']:.3f}")

# ── Run Rolling Window ────────────────────────────────────────────────────────
# Rolling: training data always covers exactly the 2 years before test year

print("\nRunning Rolling Window analysis...")
rolling_results = []                     # [VARIABLE - list] rolling window results

rolling_windows = {
    2020: ('2018-01-01', '2019-12-31'),
    2021: ('2019-01-01', '2020-12-31'),
    2022: ('2020-01-01', '2021-12-31'),
    2023: ('2021-01-01', '2022-12-31'),
    2024: ('2022-01-01', '2023-12-31'),
}

for test_year in test_years:
    train_start, train_end = rolling_windows[test_year]
    test_start  = f'{test_year}-01-01'
    test_end    = f'{test_year}-12-31'

    train_data = df_full.loc[train_start:train_end].copy()
    test_data  = df_full.loc[test_start:test_end].copy()
    # ADD THIS LINE
    print(f"  Rolling   {test_year}: train={train_start} to {train_end} "
          f"({len(train_data)} candles)")
    best_threshold, best_period, train_sharpe = find_best_params(train_data)
    test_result = run_strategy(test_data, best_threshold, best_period)

    if test_result:
        rolling_results.append({
            'year':         test_year,
            'params':       f"ADX {best_threshold}/{best_period}",
            'train_sharpe': round(train_sharpe, 3),
            'test_sharpe':  test_result['sharpe'],
            'test_sortino': test_result['sortino'],
            'test_return':  test_result['total_return'],
            'target':       best_threshold == 20 and best_period == 10
        })
        print(f"  {test_year}: ADX {best_threshold}/{best_period} | "
              f"Test Sharpe {test_result['sharpe']:.3f} | "
              f"Sortino {test_result['sortino']:.3f}")

# ── Side by Side Comparison ───────────────────────────────────────────────────

print(f"\n{'=' * 90}")
print(f"SIDE BY SIDE COMPARISON")
print(f"{'=' * 90}")

print(f"\n{'Year':<6} "
      f"{'── EXPANDING WINDOW ──':^40} "
      f"{'── ROLLING WINDOW ──':^40}")
print(f"{'':6} "
      f"{'Params':<12} {'Sharpe':<8} {'Sortino':<10} {'Return':<12} "
      f"{'Params':<12} {'Sharpe':<8} {'Sortino':<10} {'Return'}")
print("─" * 90)

exp_df  = pd.DataFrame(expanding_results)   # [VARIABLE - DataFrame]
roll_df = pd.DataFrame(rolling_results)     # [VARIABLE - DataFrame]

for year in test_years:
    exp  = exp_df[exp_df['year'] == year].iloc[0]
    roll = roll_df[roll_df['year'] == year].iloc[0]

    exp_target  = "✅" if exp['target']  else "  "
    roll_target = "✅" if roll['target'] else "  "

    print(f"{year:<6} "
          f"{exp['params']:<10}{exp_target} "
          f"{exp['test_sharpe']:<8.3f} "
          f"{exp['test_sortino']:<10.3f} "
          f"{exp['test_return']:<12.2%} "
          f"{roll['params']:<10}{roll_target} "
          f"{roll['test_sharpe']:<8.3f} "
          f"{roll['test_sortino']:<10.3f} "
          f"{roll['test_return']:.2%}")

# ── Agreement Analysis ────────────────────────────────────────────────────────

print(f"\n{'─' * 90}")
print(f"AGREEMENT BETWEEN METHODS")
print(f"{'─' * 90}")

agreements = 0                           # [VARIABLE - int] years both agree
for year in test_years:
    exp  = exp_df[exp_df['year'] == year].iloc[0]
    roll = roll_df[roll_df['year'] == year].iloc[0]
    if exp['params'] == roll['params']:
        agreements += 1
        print(f"  {year}: ✅ Both methods selected {exp['params']}")
    else:
        print(f"  {year}: ⚠️  Expanding={exp['params']}, "
              f"Rolling={roll['params']}")

print(f"\n  Methods agree: {agreements}/{len(test_years)} years")

# ── Summary Statistics ────────────────────────────────────────────────────────

print(f"\n{'─' * 90}")
print(f"SUMMARY STATISTICS")
print(f"{'─' * 90}")

print(f"\n{'Metric':<35} {'Expanding':>12} {'Rolling':>12}")
print(f"{'─' * 60}")

metrics = [
    ('Avg out-of-sample Sharpe',
     exp_df['test_sharpe'].mean(),
     roll_df['test_sharpe'].mean()),
    ('Avg out-of-sample Sortino',
     exp_df['test_sortino'].mean(),
     roll_df['test_sortino'].mean()),
    ('Avg annual return',
     exp_df['test_return'].mean(),
     roll_df['test_return'].mean()),
    ('ADX 20/10 selected (of 5)',
     exp_df['target'].sum(),
     roll_df['target'].sum()),
    ('Profitable years (of 5)',
     (exp_df['test_return'] > 0).sum(),
     (roll_df['test_return'] > 0).sum()),
]

for label, exp_val, roll_val in metrics:
    if isinstance(exp_val, float) and exp_val < 10:
        print(f"  {label:<33} {exp_val:>12.3f} {roll_val:>12.3f}")
    else:
        print(f"  {label:<33} {exp_val:>12.0f} {roll_val:>12.0f}")

# ── Final Verdict ─────────────────────────────────────────────────────────────

print(f"\n{'=' * 90}")
print(f"FINAL VERDICT")
print(f"{'=' * 90}")

exp_sortino_avg  = exp_df['test_sortino'].mean()
roll_sortino_avg = roll_df['test_sortino'].mean()
exp_profitable   = (exp_df['test_return'] > 0).sum()
roll_profitable  = (roll_df['test_return'] > 0).sum()

all_good = (
    exp_df['test_sharpe'].mean()  > 0.5 and
    roll_df['test_sharpe'].mean() > 0.5 and
    exp_sortino_avg               > 0.5 and
    roll_sortino_avg              > 0.5 and
    exp_profitable                >= 4  and
    roll_profitable               >= 4
)

print(f"\n  Both methods — avg Sharpe > 0.5:   "
      f"{'✅' if exp_df['test_sharpe'].mean() > 0.5 and roll_df['test_sharpe'].mean() > 0.5 else '❌'}")
print(f"  Both methods — avg Sortino > 0.5:  "
      f"{'✅' if exp_sortino_avg > 0.5 and roll_sortino_avg > 0.5 else '❌'}")
print(f"  Both methods — profitable ≥4/5 yrs:"
      f"{'✅' if exp_profitable >= 4 and roll_profitable >= 4 else '❌'}")

print(f"\n{'=' * 90}")
if all_good:
    print(f"✅ STRATEGY CONFIRMED ROBUST ACROSS BOTH VALIDATION METHODS")
    print(f"   ADX 20/10 is validated for live deployment on daily candles")
else:
    print(f"⚠️  FURTHER INVESTIGATION REQUIRED BEFORE LIVE DEPLOYMENT")
print(f"{'=' * 90}\n")

# ── Save Combined Results ─────────────────────────────────────────────────────

combined = {
    'expanding': expanding_results,
    'rolling':   rolling_results,
    'summary': {
        'exp_avg_sharpe':   round(exp_df['test_sharpe'].mean(), 3),
        'roll_avg_sharpe':  round(roll_df['test_sharpe'].mean(), 3),
        'exp_avg_sortino':  round(exp_sortino_avg, 3),
        'roll_avg_sortino': round(roll_sortino_avg, 3),
        'methods_agree':    agreements,
        'all_passed':       bool(all_good)
    }
}

with open('Week_4_Notebooks/window_comparison_results.json', 'w') as f:
    json.dump(combined, f, indent=2)

print(f"✅ Combined results saved to window_comparison_results.json")