"""
PHASE 3b: UNISWAP BACKTESTER (Fixed for Data Limits)
FILENAME: 07_uniswap_backtester.py

OBJECTIVE: 
Simulate the performance of a Concentrated Liquidity Position (Uniswap V3) 
versus a standard Buy & Hold strategy.

CORE CONCEPTS:
1. Passive Liquidity: We enter a range (e.g., ±20%) on Jan 1st and do not move it.
2. Fee Accrual: We earn fees only when the price is inside our range.
3. Impermanent Loss: Calculated using the specific Geometric Math of V3.
4. The Benchmark: We compare our total value (Assets + Fees) against simply holding 
   the initial deposit amount (HODL).

FIX NOTES:
- Switched to '1d' (Daily) data because Yahoo Finance '1h' data is limited to the last 730 days.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- 1. SIMULATION SETTINGS ---
SYMBOL = "ETH-USD"        # The asset pair
START_DATE = "2023-01-01" # Start of the simulation (The 'Crab' Year)
END_DATE = "2024-01-01"   # End of the simulation
INVESTMENT = 10000        # Initial capital in USD
RANGE_PCT = 0.20          # Range Width: ±20% (e.g., 2000 to 3000)
FEE_TIER = 0.003          # Pool Fee Tier: 0.3% (30 basis points)

# Volume Velocity Assumption:
# "How often does the money in the pool turn over?"
# 0.20 means 20% of the pool's TVL is traded every day.
DAILY_VOL_TO_TVL = 0.20   

# --- 2. UNISWAP MATH ENGINE ---

def calculate_liquidity_and_amounts(price, Pa, Pb, max_usd):
    """
    SOLVER FUNCTION:
    Determines exactly how much ETH and USDC are required to enter a pool
    with $10,000, given specific range boundaries.
    """
    # Convert prices to Square Roots (Uniswap math uses sqrt(Price))
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)  # Lower Bound sqrt
    sqrt_Pb = np.sqrt(Pb)  # Upper Bound sqrt
    
    # Step A: Calculate 'L' for a theoretical test amount (1.0 ETH)
    L_test = (1.0 * sqrt_P * sqrt_Pb) / (sqrt_Pb - sqrt_P)
    
    # Step B: Calculate the matching USDC amount
    usdc_test = L_test * (sqrt_P - sqrt_Pa)
    
    # Step C: Scale up to our Budget ($10,000)
    value_test = (1.0 * price) + usdc_test
    scale = max_usd / value_test
    
    # Return the actual scaled amounts we will deposit
    return L_test * scale, 1.0 * scale, usdc_test * scale

def calculate_lp_value(price, L, Pa, Pb):
    """
    VALUATION FUNCTION (The Robot):
    Calculates the current value of the LP position based on the new price.
    Handles the 3 states of a V3 position: Below Range, Above Range, In Range.
    """
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    if price <= Pa:
        # STATE 1: Price Crashed (Below Range) -> 100% ETH
        return L * (sqrt_Pb - sqrt_Pa) / (sqrt_Pa * sqrt_Pb) * price
        
    elif price >= Pb:
        # STATE 2: Price Mooned (Above Range) -> 100% USDC
        return L * (sqrt_Pb - sqrt_Pa)
        
    else:
        # STATE 3: In Range (Active) -> Mix
        eth = L * (sqrt_Pb - sqrt_P) / (sqrt_P * sqrt_Pb)
        usdc = L * (sqrt_P - sqrt_Pa)
        return (eth * price) + usdc

# --- 3. BACKTEST SIMULATION ---

def fetch_data(symbol, start, end):
    print(f"Fetching {symbol} DAILY data (due to API limits)...")
    # Switched to interval="1d" to access older data
    df = yf.download(symbol, start=start, end=end, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[['Close']]

def run_simulation(df):
    data = df.copy()
    
    # Step 1: Initialize the Strategy (Jan 1st)
    entry_price = data['Close'].iloc[0]
    min_price = entry_price * (1 - RANGE_PCT) 
    max_price = entry_price * (1 + RANGE_PCT) 
    
    print(f"--- SIMULATION START ---")
    print(f"Entry Price: ${entry_price:.2f}")
    print(f"Range:       ${min_price:.2f} - ${max_price:.2f} (±{int(RANGE_PCT*100)}%)")
    
    # Step 2: Deposit Funds
    L, initial_eth, initial_usdc = calculate_liquidity_and_amounts(entry_price, min_price, max_price, INVESTMENT)
    
    # Step 3: Run the Time Loop
    portfolio_values = []
    hodl_values = []
    fees_accumulated = []
    running_fees = 0.0
    
    # --- Fee Estimation Logic (Updated for Daily) ---
    EFFICIENCY_MULTIPLIER = 3.0 
    
    # Daily Yield = Daily Volume % * Fee Tier * Efficiency
    # Removed the "/ 24" because we are now iterating by Day, not Hour
    daily_yield_rate = DAILY_VOL_TO_TVL * FEE_TIER * EFFICIENCY_MULTIPLIER
    
    print(f"Simulating {len(data)} days...")
    
    for price in data['Close']:
        # A. Check if the position is Active
        in_range = min_price <= price <= max_price
        
        # B. Accrue Fees (The Cash Register)
        if in_range:
            fee = INVESTMENT * daily_yield_rate
            running_fees += fee
        
        fees_accumulated.append(running_fees)
        
        # C. Calculate Current LP Value
        val_lp = calculate_lp_value(price, L, min_price, max_price)
        portfolio_values.append(val_lp)
        
        # D. Calculate HODL Value
        val_hodl = (initial_eth * price) + initial_usdc
        hodl_values.append(val_hodl)
        
    # Step 4: Aggregate Results
    data['LP_Value'] = portfolio_values       
    data['HODL_Value'] = hodl_values          
    data['Cumulative_Fees'] = fees_accumulated 
    data['Total_Value'] = data['LP_Value'] + data['Cumulative_Fees'] 
    
    return data, entry_price, min_price, max_price

def plot_results(data, min_p, max_p):
    plt.figure(figsize=(12, 12))
    plt.style.use('dark_background')
    
    # Chart 1: Price Action & Range Status
    ax1 = plt.subplot(3, 1, 1)
    plt.plot(data['Close'], color='gray', alpha=0.5, label='ETH Price')
    plt.axhline(min_p, color='red', linestyle='--', label='Min Range')
    plt.axhline(max_p, color='red', linestyle='--', label='Max Range')
    
    plt.fill_between(data.index, min_p, max_p, 
                     where=(data['Close'] >= min_p) & (data['Close'] <= max_p), 
                     color='lime', alpha=0.1, label='Earning Fees')
    plt.title('1. Range Status (Green Zone = Earning Fees)')
    plt.legend()
    
    # Chart 2: Equity Curve vs HODL
    ax2 = plt.subplot(3, 1, 2, sharex=ax1)
    plt.plot(data['Total_Value'], color='lime', label='LP Strategy (Assets + Fees)')
    plt.plot(data['HODL_Value'], color='white', linestyle='--', label='HODL Benchmark')
    plt.title('2. Portfolio Value Comparison')
    plt.legend()
    
    # Chart 3: Net Profit/Loss vs HODL
    ax3 = plt.subplot(3, 1, 3, sharex=ax1)
    net_pnl = data['Total_Value'] - data['HODL_Value']
    
    plt.plot(net_pnl, color='cyan', label='Net Edge vs HODL ($)')
    plt.plot(data['Cumulative_Fees'], color='yellow', alpha=0.5, label='Total Fees Collected')
    plt.axhline(0, color='white', linestyle=':')
    plt.title('3. The "Net Edge" (Did Fees cover Impermanent Loss?)')
    plt.legend()
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    df = fetch_data(SYMBOL, START_DATE, END_DATE)
    df, entry, min_p, max_p = run_simulation(df)
    
    # Final Statistics Printout
    final_lp = df['Total_Value'].iloc[-1]
    final_hodl = df['HODL_Value'].iloc[-1]
    fees = df['Cumulative_Fees'].iloc[-1]
    net_result = final_lp - final_hodl
    
    print(f"\n--- RESULTS (2023 'Crab' Market) ---")
    print(f"HODL Final Value: ${final_hodl:,.2f}")
    print(f"LP Final Value:   ${final_lp:,.2f} (Assets + Fees)")
    print(f"Fees Earned:      ${fees:,.2f}")
    print(f"Net Edge:         ${net_result:,.2f}")
    
    if net_result > 0:
        print("CONCLUSION: Strategy BEAT HODL (Fees > Impermanent Loss)")
    else:
        print("CONCLUSION: Strategy LOST to HODL (Impermanent Loss > Fees)")
    
    plot_results(df, min_p, max_p)