"""
PHASE 4: CAPSTONE STRATEGY (Regime Switching with Hysteresis)
FILENAME: 10_capstone_strategy.py

OBJECTIVE: 
Simulate a dynamic portfolio that rotates capital between 3 states based on market conditions.
NOW INCLUDES: Automated CSV Logging, Advanced Risk Metrics, and Signal Hysteresis.

THE STRATEGY LOGIC:
1. CALCULATE REGIME (The "Weather Report"):
   - We use ADX (Average Directional Index) to measure Trend Strength.
   - HYSTERESIS UPGRADE: We use two thresholds to prevent "whipsaw" switching.
     * ADX > 27: Enter Trend Mode.
     * ADX < 23: Enter Chop Mode.
     * ADX 23-27: Stay in current mode.

2. STATE SELECTION (The "Vehicle"):
   A. IF CHOP (ADX < 23):
      - Deploy Capital into Uniswap V3 (±20% Range).
      - Goal: Farm fees while price goes sideways.
      
   B. IF TREND (ADX > 27):
      - Check Direction using SMA 50.
      - IF Price > SMA 50 (Uptrend): BUY ETH (HODL). Catch the pump.
      - IF Price < SMA 50 (Downtrend): SELL to USDC (CASH). Avoid the crash.

3. FRICTION (The "Real World"):
   - Every time we switch strategies, we pay Swap Fees & Gas Fees.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os # Added for file handling

# --- 1. GLOBAL SETTINGS ---
SYMBOL = "ETH-USD"
START_DATE = "2020-01-01" 
END_DATE = "2024-01-01"
INITIAL_CAPITAL = 10000

# Strategy Parameters
ADX_PERIOD = 14
ADX_UPPER = 27          # Need to break ABOVE this to enter TREND
ADX_LOWER = 23          # Need to fall BELOW this to enter CHOP
SMA_PERIOD = 50         # Direction filter
UNISWAP_RANGE = 0.20    # ±20% Liquidity Range
FEE_TIER = 0.003        # 0.3% Pool
DAILY_VOL_TO_TVL = 0.20 # Estimated Volume Velocity

# Friction Costs (Environment Settings)
LAYER_NAME = "L1 Ethereum" # Label for the log (e.g., "L1 Ethereum" or "L2 Arbitrum")
GAS_FEE = 10.0             # $10 per switch (L1). Set to 0.1 for L2.
SWAP_FEE = 0.001           # 0.1% slippage/fee on rotation

# Logging Config
LOG_FILENAME = "strategy_backtest_log.csv"

# --- 2. MATH HELPERS (Uniswap & Indicators) ---

def calculate_liquidity_and_amounts(price, Pa, Pb, max_usd):
    """
    Solves for Liquidity (L) given a dollar investment amount.
    """
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    # Standard V3 Formulas
    L_test = (1.0 * sqrt_P * sqrt_Pb) / (sqrt_Pb - sqrt_P)
    usdc_test = L_test * (sqrt_P - sqrt_Pa)
    value_test = (1.0 * price) + usdc_test
    
    scale = max_usd / value_test
    return L_test * scale

def calculate_lp_value(price, L, Pa, Pb):
    """
    Returns the current Asset Value of the LP position.
    """
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    if price <= Pa: return L * (sqrt_Pb - sqrt_Pa) / (sqrt_Pa * sqrt_Pb) * price
    elif price >= Pb: return L * (sqrt_Pb - sqrt_Pa)
    else:
        eth = L * (sqrt_Pb - sqrt_P) / (sqrt_P * sqrt_Pb)
        usdc = L * (sqrt_P - sqrt_Pa)
        return (eth * price) + usdc

def wilders_smoothing(series, period):
    return series.ewm(alpha=1/period, adjust=False).mean()

def add_indicators(df):
    data = df.copy()
    
    # 1. Simple Moving Average (Direction)
    data['SMA'] = data['Close'].rolling(window=SMA_PERIOD).mean()
    
    # 2. ADX (Trend Strength) - Calculated manually
    data['H-L'] = data['High'] - data['Low']
    data['H-PC'] = abs(data['High'] - data['Close'].shift(1))
    data['L-PC'] = abs(data['Low'] - data['Close'].shift(1))
    data['TR'] = data[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    data['+DM'] = np.where((data['High']-data['High'].shift(1))>(data['Low'].shift(1)-data['Low']), np.maximum(data['High']-data['High'].shift(1),0), 0)
    data['-DM'] = np.where((data['Low'].shift(1)-data['Low'])>(data['High']-data['High'].shift(1)), np.maximum(data['Low'].shift(1)-data['Low'],0), 0)
    
    data['TR_Smooth'] = wilders_smoothing(data['TR'], ADX_PERIOD)
    data['+DM_Smooth'] = wilders_smoothing(data['+DM'], ADX_PERIOD)
    data['-DM_Smooth'] = wilders_smoothing(data['-DM'], ADX_PERIOD)
    
    data['+DI'] = 100 * (data['+DM_Smooth'] / data['TR_Smooth'])
    data['-DI'] = 100 * (data['-DM_Smooth'] / data['TR_Smooth'])
    data['DX'] = 100 * abs(data['+DI'] - data['-DI']) / (data['+DI'] + data['-DI'])
    data['ADX'] = wilders_smoothing(data['DX'], ADX_PERIOD)
    
    return data.dropna()

# --- 3. THE BACKTEST ENGINE ---

def run_capstone_strategy(df):
    print("--- STARTING CAPSTONE SIMULATION ---")
    
    # Simulation State Variables
    cash = INITIAL_CAPITAL
    current_state = "CASH" # Options: "CASH", "HODL", "UNISWAP"
    
    # Uniswap Specific State
    uni_L = 0
    uni_min = 0
    uni_max = 0
    uni_fees_collected = 0 # Fees in current session
    
    # Performance Tracking
    equity_curve = []
    state_history = []
    total_lifetime_fees = 0.0 # Total fees collected historically
    
    # Loop through every single day
    for i in range(len(df)):
        today = df.iloc[i]
        price = today['Close']
        adx = today['ADX']
        sma = today['SMA']
        
        # -----------------------------
        # 1. DETERMINE DESIRED REGIME (With Hysteresis)
        # -----------------------------
        target_state = current_state # Default to staying in current state
        
        if current_state == "UNISWAP":
            # Already in chop mode - need stronger signal to leave
            if adx > ADX_UPPER:
                target_state = "HODL" if price > sma else "CASH"
            else:
                target_state = "UNISWAP"
        else:
            # In trend mode (HODL or CASH) - need weaker signal to enter chop
            if adx < ADX_LOWER:
                target_state = "UNISWAP"
            else:
                # Still in trend mode, check direction
                target_state = "HODL" if price > sma else "CASH"
                
        # -----------------------------
        # 2. HANDLE SWITCHING (Friction)
        # -----------------------------
        if target_state != current_state:
            # A. LIQUIDATE OLD POSITION
            if current_state == "HODL":
                # Sell ETH -> Cash
                cash = cash * (1 - SWAP_FEE)
            elif current_state == "UNISWAP":
                # Withdraw Liquidity -> Cash
                lp_value = calculate_lp_value(price, uni_L, uni_min, uni_max)
                total_val = lp_value + uni_fees_collected
                cash = total_val - GAS_FEE # Pay Gas to exit
                uni_fees_collected = 0     # Reset session fees bucket
            
            # Pay Gas for the switch logic
            cash -= GAS_FEE
            
            # B. ENTER NEW POSITION
            if target_state == "HODL":
                # Buy ETH (Cash value tracks ETH price changes relatively)
                # In simulation, we just mark the cash as "exposed"
                cash = cash * (1 - SWAP_FEE)
                
            elif target_state == "UNISWAP":
                # Deposit into Pool
                uni_min = price * (1 - UNISWAP_RANGE)
                uni_max = price * (1 + UNISWAP_RANGE)
                uni_L = calculate_liquidity_and_amounts(price, uni_min, uni_max, cash)
                uni_fees_collected = 0
                cash -= GAS_FEE # Pay Gas to deposit
            
            current_state = target_state
            
        # -----------------------------
        # 3. UPDATE PORTFOLIO VALUE
        # -----------------------------
        daily_equity = 0
        
        if current_state == "CASH":
            # Value is just Cash (Stable)
            daily_equity = cash
            
        elif current_state == "HODL":
            # Value fluctuates with ETH % change
            # (Simplified: calculating daily return)
            if i > 0:
                prev_price = df.iloc[i-1]['Close']
                ret = (price - prev_price) / prev_price
                cash = cash * (1 + ret)
            daily_equity = cash
            
        elif current_state == "UNISWAP":
            # 1. Check Range for Fees
            if uni_min <= price <= uni_max:
                # Earn Fees
                efficiency = 3.0 * (0.20 / UNISWAP_RANGE)
                daily_yield = DAILY_VOL_TO_TVL * FEE_TIER * efficiency
                # We earn fees based on the Asset Value
                lp_asset_value = calculate_lp_value(price, uni_L, uni_min, uni_max)
                fees = lp_asset_value * daily_yield 
                
                uni_fees_collected += fees
                total_lifetime_fees += fees # Track specific earning source
            
            # 2. Mark to Market
            asset_value = calculate_lp_value(price, uni_L, uni_min, uni_max)
            daily_equity = asset_value + uni_fees_collected

        equity_curve.append(daily_equity)
        state_history.append(current_state)

    # Attach to DataFrame
    df['Strategy_Equity'] = equity_curve
    df['Regime'] = state_history
    df['Lifetime_Fees'] = total_lifetime_fees 
    return df, total_lifetime_fees

# --- 4. ADVANCED METRICS & LOGGING ---

def calculate_performance_metrics(df):
    """
    Calculates advanced risk metrics for the Strategy Log.
    """
    # 1. Daily Returns
    df['Daily_Ret'] = df['Strategy_Equity'].pct_change()
    
    # 2. Max Drawdown
    running_max = df['Strategy_Equity'].cummax()
    drawdown = (df['Strategy_Equity'] - running_max) / running_max
    max_dd = drawdown.min()
    
    # 3. Total Return
    total_ret = (df['Strategy_Equity'].iloc[-1] / INITIAL_CAPITAL) - 1
    
    # 4. Sharpe Ratio (Risk Adjusted Return)
    # Mean Daily Return / Std Dev of Daily Returns * sqrt(365)
    mean_ret = df['Daily_Ret'].mean()
    std_ret = df['Daily_Ret'].std()
    sharpe = (mean_ret / std_ret) * np.sqrt(365) if std_ret > 0 else 0
    
    # 5. Sortino Ratio (Downside Risk Only)
    # Like Sharpe, but only penalizes negative volatility. Better for crypto.
    negative_rets = df.loc[df['Daily_Ret'] < 0, 'Daily_Ret']
    downside_std = negative_rets.std()
    sortino = (mean_ret / downside_std) * np.sqrt(365) if downside_std > 0 else 0
    
    # 6. Calmar Ratio (Return / Max Drawdown)
    # Measures "Bang for your Buck" relative to the worst crash.
    calmar = abs(total_ret / max_dd) if max_dd != 0 else 0
    
    return {
        "Total_Return": total_ret,
        "Max_Drawdown": max_dd,
        "Sharpe_Ratio": sharpe,
        "Sortino_Ratio": sortino,
        "Calmar_Ratio": calmar
    }

def log_to_csv(metrics, fee_total):
    """
    Appends the results of this specific run to a CSV file.
    Robustly handles schema changes (adding new columns) by reading/merging.
    """
    # Data to save
    log_data = {
        "Timestamp": pd.Timestamp.now(),
        "Strategy_Desc": "Regime Switch (Hysteresis)", 
        "Layer_Type": LAYER_NAME, 
        "Symbol": SYMBOL,
        "Date_Range": f"{START_DATE} to {END_DATE}",
        "ADX_Thresh": f"{ADX_LOWER}-{ADX_UPPER}", 
        "SMA_Period": SMA_PERIOD,
        "Range_Pct": UNISWAP_RANGE,
        "Friction_Gas": GAS_FEE,   
        "Friction_Swap": SWAP_FEE, 
        "Final_Equity": round(INITIAL_CAPITAL * (1 + metrics['Total_Return']), 2),
        "Total_Return_%": round(metrics['Total_Return'] * 100, 2),
        "Max_Drawdown_%": round(metrics['Max_Drawdown'] * 100, 2),
        "Sharpe": round(metrics['Sharpe_Ratio'], 2),
        "Sortino": round(metrics['Sortino_Ratio'], 2),
        "Calmar": round(metrics['Calmar_Ratio'], 2),
        "Total_Fees_USD": round(fee_total, 2)
    }
    
    new_row = pd.DataFrame([log_data])
    
    if os.path.isfile(LOG_FILENAME):
        try:
            # Read existing log to handle column alignment
            existing_df = pd.read_csv(LOG_FILENAME)
            # Combine old and new (aligns columns, fills missing with NaN)
            combined_df = pd.concat([existing_df, new_row], ignore_index=True)
            combined_df.to_csv(LOG_FILENAME, index=False)
        except Exception as e:
            print(f"Error reading existing log: {e}. Creating new log file.")
            new_row.to_csv(LOG_FILENAME, index=False)
    else:
        new_row.to_csv(LOG_FILENAME, index=False)
    
    print(f"\n[+] Results successfully logged to '{LOG_FILENAME}'")

# --- 5. VISUALIZATION ---
def plot_capstone(df):
    plt.figure(figsize=(12, 12))
    plt.style.use('dark_background')
    
    # 1. Equity Curve
    ax1 = plt.subplot(3, 1, 1)
    # Calculate Buy & Hold Benchmark
    initial_price = df['Close'].iloc[0]
    final_price_column = df['Close'] / initial_price * INITIAL_CAPITAL
    
    plt.plot(df['Strategy_Equity'], color='lime', label='Regime Switching Bot')
    plt.plot(final_price_column, color='gray', linestyle='--', label='Buy & Hold ETH')
    plt.title('Capstone Strategy vs Buy & Hold')
    plt.legend()
    plt.yscale('log')
    
    # 2. Regime Map (Background Color)
    ax2 = plt.subplot(3, 1, 2, sharex=ax1)
    plt.plot(df['Close'], color='white', alpha=0.5)
    
    conditions = [df['Regime']=='CASH', df['Regime']=='HODL', df['Regime']=='UNISWAP']
    choices = [0, 1, 2]
    regime_num = np.select(conditions, choices)
    
    plt.fill_between(df.index, df['Close'].min(), df['Close'].max(), where=(df['Regime']=='UNISWAP'), color='cyan', alpha=0.3, label='Uniswap (Chop)')
    plt.fill_between(df.index, df['Close'].min(), df['Close'].max(), where=(df['Regime']=='HODL'), color='green', alpha=0.3, label='HODL (Uptrend)')
    plt.fill_between(df.index, df['Close'].min(), df['Close'].max(), where=(df['Regime']=='CASH'), color='red', alpha=0.3, label='CASH (Downtrend)')
    plt.title('Strategy State (Red=Safety, Green=Ride, Cyan=Farm)')
    plt.legend(loc='upper left')
    
    # 3. Drawdown
    ax3 = plt.subplot(3, 1, 3, sharex=ax1)
    running_max = df['Strategy_Equity'].cummax()
    drawdown = (df['Strategy_Equity'] - running_max) / running_max
    plt.plot(drawdown, color='red', alpha=0.6)
    plt.fill_between(df.index, drawdown, 0, color='red', alpha=0.2)
    plt.title('Strategy Drawdown')
    plt.tight_layout()
    plt.show()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # 1. ETL
    print(f"Fetching Data for {SYMBOL}...")
    raw_data = yf.download(SYMBOL, start=START_DATE, end=END_DATE, interval="1d", progress=False)
    if isinstance(raw_data.columns, pd.MultiIndex):
        raw_data.columns = raw_data.columns.get_level_values(0)
    
    # 2. Indicators
    processed_data = add_indicators(raw_data[['High', 'Low', 'Close']])
    
    # 3. Backtest
    results, fee_total = run_capstone_strategy(processed_data)
    
    # 4. Advanced Metrics & Logging
    metrics = calculate_performance_metrics(results)
    
    final_val = results['Strategy_Equity'].iloc[-1]
    hodl_val = (results['Close'].iloc[-1] / results['Close'].iloc[0]) * INITIAL_CAPITAL
    
    print(f"\n--- CAPSTONE RESULTS ({START_DATE} to {END_DATE}) ---")
    print(f"Layer Model:     {LAYER_NAME}")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Strategy Final:  ${final_val:,.2f}")
    print(f"Buy & Hold Final:${hodl_val:,.2f}")
    print(f"Net Performance: {((final_val - hodl_val)/hodl_val)*100:.2f}% vs Benchmark")
    print(f"--------------------------------")
    print(f"Total Uniswap Fees: ${fee_total:,.2f}")
    print(f"Capital Gains:      ${final_val - INITIAL_CAPITAL - fee_total:,.2f}")
    print(f"--------------------------------")
    print(f"Max Drawdown:       {metrics['Max_Drawdown']*100:.2f}%")
    print(f"Sharpe Ratio:       {metrics['Sharpe_Ratio']:.2f}")
    print(f"Sortino Ratio:      {metrics['Sortino_Ratio']:.2f}")
    print(f"Calmar Ratio:       {metrics['Calmar_Ratio']:.2f}")
    
    # Save to CSV
    log_to_csv(metrics, fee_total)
    
    plot_capstone(results)