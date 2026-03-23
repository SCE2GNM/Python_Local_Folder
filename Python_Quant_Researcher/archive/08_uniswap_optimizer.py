"""
PHASE 3b: UNISWAP RANGE OPTIMIZER
FILENAME: 08_uniswap_optimizer.py

OBJECTIVE: 
Find the "Island of Profitability."
Instead of guessing a range (e.g., 20%), we test every range from 5% to 50%.

METRIC:
Net Edge vs HODL. We want to find the "Sweet Spot" where Fees > IL.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- SETTINGS ---
SYMBOL = "ETH-USD"
START_DATE = "2023-01-01"
END_DATE = "2024-01-01"
INVESTMENT = 10000
FEE_TIER = 0.003
DAILY_VOL_TO_TVL = 0.20

# --- UNISWAP MATH (Standardized) ---
def calculate_liquidity_and_amounts(price, Pa, Pb, max_usd):
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    L_test = (1.0 * sqrt_P * sqrt_Pb) / (sqrt_Pb - sqrt_P)
    usdc_test = L_test * (sqrt_P - sqrt_Pa)
    value_test = (1.0 * price) + usdc_test
    scale = max_usd / value_test
    return L_test * scale, 1.0 * scale, usdc_test * scale

def calculate_lp_value(price, L, Pa, Pb):
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    if price <= Pa:
        return L * (sqrt_Pb - sqrt_Pa) / (sqrt_Pa * sqrt_Pb) * price
    elif price >= Pb:
        return L * (sqrt_Pb - sqrt_Pa)
    else:
        eth = L * (sqrt_Pb - sqrt_P) / (sqrt_P * sqrt_Pb)
        usdc = L * (sqrt_P - sqrt_Pa)
        return (eth * price) + usdc

# --- DATA ---
def fetch_data(symbol, start, end):
    print(f"Fetching {symbol} daily data...")
    df = yf.download(symbol, start=start, end=end, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[['Close']]

# --- SINGLE SIMULATION RUN ---
def run_single_backtest(df, range_pct):
    # 1. Setup
    entry_price = df['Close'].iloc[0]
    min_price = entry_price * (1 - range_pct)
    max_price = entry_price * (1 + range_pct)
    
    # 2. Init LP
    L, initial_eth, initial_usdc = calculate_liquidity_and_amounts(entry_price, min_price, max_price, INVESTMENT)
    
    # 3. Fee Logic (Capital Efficiency approximation)
    # Tighter range = Higher Efficiency = More Fees
    # Efficiency is roughly proportional to 1 / range_pct
    # We calibrate based on standard 20% range = 3.0x multiplier
    # New Multiplier = 3.0 * (0.20 / current_range)
    # Example: 10% range -> 3.0 * (0.20/0.10) = 6.0x efficiency
    efficiency_multiplier = 3.0 * (0.20 / range_pct)
    daily_yield = DAILY_VOL_TO_TVL * FEE_TIER * efficiency_multiplier
    
    # 4. Fast Vectorized Loop
    # Identify days in range
    in_range_mask = (df['Close'] >= min_price) & (df['Close'] <= max_price)
    
    # Calculate Total Fees
    # Sum of days in range * daily_fee_dollars
    days_in_range = in_range_mask.sum()
    total_fees = days_in_range * (INVESTMENT * daily_yield)
    
    # 5. Calculate Final Values (Asset Value + Fees)
    final_price = df['Close'].iloc[-1]
    final_lp_assets = calculate_lp_value(final_price, L, min_price, max_price)
    final_lp_total = final_lp_assets + total_fees
    
    # 6. Calculate HODL
    final_hodl = (initial_eth * final_price) + initial_usdc
    
    # Return Net Edge (Profit vs HODL)
    return final_lp_total - final_hodl

# --- GRID SEARCH ---
def optimize_range(df):
    results = []
    # Test ranges from 5% to 60% in steps of 1%
    test_ranges = np.arange(0.05, 0.61, 0.01)
    
    print(f"Testing {len(test_ranges)} different ranges...")
    
    for r in test_ranges:
        net_edge = run_single_backtest(df, r)
        results.append({
            'Range': r * 100, # Convert to %
            'Net_Edge': net_edge
        })
        
    return pd.DataFrame(results)

def plot_optimization(results):
    plt.figure(figsize=(12, 6))
    plt.style.use('dark_background')
    
    # Plot the curve
    plt.plot(results['Range'], results['Net_Edge'], color='cyan', linewidth=2, marker='o', markersize=3)
    
    # Draw Zero Line (Breakeven vs HODL)
    plt.axhline(0, color='white', linestyle='--', label='HODL Benchmark')
    
    # Color logic
    plt.fill_between(results['Range'], results['Net_Edge'], 0, where=(results['Net_Edge'] > 0), color='lime', alpha=0.3)
    plt.fill_between(results['Range'], results['Net_Edge'], 0, where=(results['Net_Edge'] < 0), color='red', alpha=0.3)
    
    plt.title('Optimization: Which Range Beats HODL?')
    plt.xlabel('Range Width (±%)')
    plt.ylabel('Net Profit vs HODL ($)')
    plt.grid(True, alpha=0.2)
    plt.legend()
    plt.show()

if __name__ == "__main__":
    data = fetch_data(SYMBOL, START_DATE, END_DATE)
    results_df = optimize_range(data)
    
    # Find Best Range
    best_run = results_df.loc[results_df['Net_Edge'].idxmax()]
    print(f"\n--- OPTIMIZATION RESULTS ---")
    print(f"Best Range: ±{best_run['Range']:.1f}%")
    print(f"Max Edge:   ${best_run['Net_Edge']:.2f}")
    
    plot_optimization(results_df)