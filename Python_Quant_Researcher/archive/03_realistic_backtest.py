"""
STRATEGY: Optimized Trend Following with REALISTIC Constraints
PARAMETERS: Fast=5, Slow=120 (Derived from Step 2 Optimization)

OBJECTIVE:
Compare the "Paper Returns" (No Fees) vs "Net Returns" (With Fees/Slippage).

ASSUMPTIONS:
1. Capital: $10,000
2. Fee Tier: 0.10% per trade (Standard Taker Fee)
3. Slippage: 0.10% per trade (Assumed execution drag)
4. Total Cost per Turn: 0.40% (Entry + Exit) effectively reduces edge.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- SETTINGS ---
SYMBOL = "BTC-USD"
START_DATE = "2020-01-01"
END_DATE = "2024-01-01"

# Optimized Parameters (From your Grid Search)
FAST_WINDOW = 5
SLOW_WINDOW = 120

# Costs
INITIAL_CAPITAL = 10000
TRADING_FEE = 0.0010  # 0.10%
SLIPPAGE = 0.0010     # 0.10%
TOTAL_COST = TRADING_FEE + SLIPPAGE

def fetch_data(symbol, start, end):
    print(f"Fetching {symbol}...")
    df = yf.download(symbol, start=start, end=end, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[['Close']]

def calculate_strategy(df):
    data = df.copy()
    
    # 1. Indicators
    data['Fast_SMA'] = data['Close'].rolling(window=FAST_WINDOW).mean()
    data['Slow_SMA'] = data['Close'].rolling(window=SLOW_WINDOW).mean()
    
    # 2. Raw Signal
    data['Signal'] = np.where(data['Fast_SMA'] > data['Slow_SMA'], 1, 0)
    
    # 3. Position (Shifted for Look-Ahead Bias)
    data['Position'] = data['Signal'].shift(1)
    
    # 4. Identify Trade Executions
    # We take the difference between today's position and yesterday's.
    # If Position goes 0 -> 1 (Buy), diff is 1.
    # If Position goes 1 -> 0 (Sell), diff is -1.
    # If Position goes 1 -> 1 (Hold), diff is 0.
    # abs() makes both Buy and Sell = 1, so we just count "events".
    data['Trade_Executed'] = data['Position'].diff().abs().fillna(0)
    
    return data

def run_realistic_backtest(data):
    # 1. Market Returns
    data['Asset_Returns'] = data['Close'].pct_change()
    
    # 2. Raw Strategy Returns (Paper Money)
    data['Strategy_Returns_Raw'] = data['Position'] * data['Asset_Returns']
    
    # 3. Cost Adjustment
    # Every time 'Trade_Executed' is 1, we subtract the TOTAL_COST from that day's return.
    cost_drag = data['Trade_Executed'] * TOTAL_COST
    data['Strategy_Returns_Net'] = data['Strategy_Returns_Raw'] - cost_drag
    
    # 4. Equity Curves
    data['Equity_Raw'] = (1 + data['Strategy_Returns_Raw']).cumprod() * INITIAL_CAPITAL
    data['Equity_Net'] = (1 + data['Strategy_Returns_Net']).cumprod() * INITIAL_CAPITAL
    data['Equity_Hold'] = (1 + data['Asset_Returns']).cumprod() * INITIAL_CAPITAL
    
    return data

def show_results(data):
    # Calculate Final Stats
    final_raw = data['Equity_Raw'].iloc[-1]
    final_net = data['Equity_Net'].iloc[-1]
    
    total_trades = data['Trade_Executed'].sum()
    total_fees_paid = final_raw - final_net # Approximation of lost value
    
    print("\n--- REALITY CHECK ---")
    print(f"Total Trades:      {int(total_trades)}")
    print(f"Final Equity (Raw): ${final_raw:,.2f}")
    print(f"Final Equity (Net): ${final_net:,.2f}")
    print(f"Cost of Business:   ${total_fees_paid:,.2f} (Lost to Fees/Slippage)")
    
    # Visualize
    plt.figure(figsize=(12, 6))
    plt.style.use('dark_background')
    
    plt.plot(data['Equity_Raw'], label='Paper Returns (No Fees)', color='lime', alpha=0.5, linestyle='--')
    plt.plot(data['Equity_Net'], label='Real Returns (With Fees)', color='cyan', linewidth=1.5)
    plt.plot(data['Equity_Hold'], label='Buy & Hold', color='gray', alpha=0.5)
    
    plt.title(f'The Cost of Trading: {FAST_WINDOW}/{SLOW_WINDOW} Strategy')
    plt.legend()
    plt.yscale('log') # Log scale helps see long-term compounding better
    plt.grid(True, alpha=0.2)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    df = fetch_data(SYMBOL, START_DATE, END_DATE)
    df = calculate_strategy(df)
    df = run_realistic_backtest(df)
    show_results(df)