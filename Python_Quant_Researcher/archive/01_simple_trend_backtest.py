"""
STRATEGY: Dual Moving Average Crossover (Long Only)
ASSET:    BTC-USD (Spot)
TIMEFRAME: Daily (1D)

HYPOTHESIS:
Bitcoin exhibits strong serial correlation (momentum). When a short-term trend (Fast SMA)
overtakes a long-term average (Slow SMA), it indicates positive price momentum.
We capture this by going LONG. When momentum fades, we go CASH (Flat).

CORE LOGIC:
1. Signal: Close > SMA_20 > SMA_50
2. Execution: Enter on the OPEN of the NEXT candle after the signal is confirmed.
3. Position: 100% Long or 100% Cash (No leverage, no shorting).

RISKS:
1. Whipsaw: In sideways markets, moving averages lag, causing us to buy tops and sell bottoms.
2. Latency: We assume we can execute perfectly at the 'Close' price (theoretical) or next 'Open'.
"""

import yfinance as yf          # The Data Source (Yahoo Finance API)
import pandas as pd            # The DataFrame library (Data manipulation)
import numpy as np             # The Math library (Vectorized logic)
import matplotlib.pyplot as plt # The Visualization library

# --- 1. GLOBAL SETTINGS ---
# We define constants at the top so we can easily "parameter tune" later.
SYMBOL = "BTC-USD"
START_DATE = "2020-01-01"      # Start of the bull run
END_DATE = "2024-01-01"        # Post-bear market clarity
FAST_WINDOW = 20               # Sensitivity: Lower = more signals, more noise
SLOW_WINDOW = 50               # Trend Confirmation: Higher = smoother, more lag
INITIAL_CAPITAL = 10000        # Starting portfolio size in USD

def fetch_data(symbol, start, end):
    """
    ETL (Extract, Transform, Load) Pipeline.
    Responsible for getting clean data into the system.
    """
    print(f"--- 1. ETL STARTED: Fetching {symbol} ---")
    
    # Download data. 'progress=False' keeps the console clean.
    df = yf.download(symbol, start=start, end=end, progress=False)
    
    # CLEANING: Yahoo Finance sometimes returns a "MultiIndex" (complex column headers).
    # We flatten it to keep things simple: Just 'Close', 'Open', etc.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # We only need the 'Close' price for this specific strategy.
    # In more complex strategies, we would need Open, High, Low, and Volume.
    return df[['Close']]

def calculate_strategy(df):
    """
    ALPHA GENERATION MODULE.
    Here we apply statistical logic to price data to generate a 'Signal'.
    """
    data = df.copy() # Create a copy to avoid modifying the original data source accidentally
    
    # 1. Calculate Technical Indicators (Vectorized)
    # .rolling(w).mean() calculates the average of the last 'w' prices.
    # NaN (Not a Number) will appear for the first 20 or 50 rows because there isn't enough data yet.
    data['Fast_SMA'] = data['Close'].rolling(window=FAST_WINDOW).mean()
    data['Slow_SMA'] = data['Close'].rolling(window=SLOW_WINDOW).mean()
    
    # 2. Generate Raw Signal (The Logic)
    # np.where(condition, value_if_true, value_if_false)
    # Logic: If Fast Trend > Slow Trend, we want to be LONG (1). Else, CASH (0).
    data['Signal'] = np.where(data['Fast_SMA'] > data['Slow_SMA'], 1, 0)
    
    # 3. Handle Look-Ahead Bias (CRITICAL STEP)
    # PROBLEM: The 'Signal' is calculated using the Close price of Day T.
    # We cannot buy at the Close of Day T because we don't know the Close until the day ends.
    # SOLUTION: We shift the signal forward by 1 day.
    # We calculate on Day T, but we execute/hold the position on Day T+1.
    data['Position'] = data['Signal'].shift(1)
    
    return data

def run_backtest(data):
    """
    PERFORMANCE ENGINE.
    Simulates the PnL (Profit and Loss) of the strategy vs the Market.
    """
    # 1. Calculate Market Returns
    # pct_change() = (Price_Today - Price_Yesterday) / Price_Yesterday
    data['Asset_Returns'] = data['Close'].pct_change()
    
    # 2. Calculate Strategy Returns
    # Logic: If we held the asset (Position=1), we get the Asset_Return.
    # If we were in Cash (Position=0), we get 0% return.
    data['Strategy_Returns'] = data['Position'] * data['Asset_Returns']
    
    # 3. Calculate Equity Curves (The "Bank Account" View)
    # (1 + r).cumprod() is the standard formula for compound returns.
    # It links the series of daily % returns into a continuous line chart of value.
    data['Cumulative_Market_Returns'] = (1 + data['Asset_Returns']).cumprod() * INITIAL_CAPITAL
    data['Cumulative_Strategy_Returns'] = (1 + data['Strategy_Returns']).cumprod() * INITIAL_CAPITAL
    
    return data

def calculate_metrics(data):
    """
    RISK REPORTING.
    Quantifies how "good" the strategy is.
    """
    # Metric 1: Total Return (Absolute Performance)
    # (Final Value / Initial Value) - 1
    total_return = (data['Cumulative_Strategy_Returns'].iloc[-1] / INITIAL_CAPITAL) - 1
    
    # Metric 2: Sharpe Ratio (Risk-Adjusted Performance)
    # A Sharpe of 1.0 means you get 1 unit of return for 1 unit of risk.
    # We multiply by sqrt(365) to "Annualize" the daily Sharpe (Crypto trades 365 days).
    daily_mean = data['Strategy_Returns'].mean()
    daily_std = data['Strategy_Returns'].std()
    
    # Guard clause: If std is 0 (strategy never traded), Sharpe is 0.
    if daily_std == 0:
        sharpe = 0
    else:
        sharpe = (daily_mean / daily_std) * np.sqrt(365)
    
    # Metric 3: Maximum Drawdown (Pain Tolerance)
    # running_max tracks the "High Water Mark" (highest value portfolio has ever reached).
    running_max = data['Cumulative_Strategy_Returns'].cummax()
    # drawdown is the % distance from that High Water Mark.
    drawdown = (data['Cumulative_Strategy_Returns'] - running_max) / running_max
    # Max Drawdown is the deepest valley in that chart.
    max_drawdown = drawdown.min()
    
    return total_return, sharpe, max_drawdown

def plot_performance(data, symbol):
    """
    VISUALIZATION.
    Generates the chart to visually inspect "When did we buy?" and "Did we survive the crash?"
    """
    plt.figure(figsize=(12, 8))
    plt.style.use('dark_background') # Professional dark mode
    
    # Top Panel: Price Action & Indicators
    ax1 = plt.subplot(2, 1, 1)
    plt.plot(data['Close'], label='Price', alpha=0.5, color='gray')
    plt.plot(data['Fast_SMA'], label=f'Fast SMA ({FAST_WINDOW})', color='cyan', linewidth=1.5)
    plt.plot(data['Slow_SMA'], label=f'Slow SMA ({SLOW_WINDOW})', color='magenta', linewidth=1.5)
    
    # Optional: Plot Buy/Sell Markers (Advanced visualization)
    # We find days where the signal changed from 0 to 1 (Buy) or 1 to 0 (Sell)
    # (This is just for visual confirmation)
    
    plt.title(f'{symbol} Strategy Indicators')
    plt.legend()
    plt.grid(True, alpha=0.2)
    
    # Bottom Panel: Equity Curve
    ax2 = plt.subplot(2, 1, 2, sharex=ax1) # sharex aligns the dates
    plt.plot(data['Cumulative_Strategy_Returns'], label='Active Strategy', color='lime')
    plt.plot(data['Cumulative_Market_Returns'], label='Buy & Hold (Benchmark)', color='white', alpha=0.3, linestyle='--')
    
    plt.title('Equity Curve (Wallet Balance)')
    plt.legend()
    plt.grid(True, alpha=0.2)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # --- EXECUTION FLOW ---
    
    # 1. Get the Raw Material
    df = fetch_data(SYMBOL, START_DATE, END_DATE)
    
    # 2. Apply the Logic
    df = calculate_strategy(df)
    
    # 3. Simulate the Past
    df = run_backtest(df)
    
    # 4. Grade the Exam
    ret, sharpe, mdd = calculate_metrics(df)
    
    print(f"\n--- BACKTEST RESULTS: {SYMBOL} ---")
    print(f"Time Period: {START_DATE} to {END_DATE}")
    print(f"Initial Capital: ${INITIAL_CAPITAL}")
    print(f"Final Value:     ${df['Cumulative_Strategy_Returns'].iloc[-1]:.2f}")
    print(f"Total Return:    {ret*100:.2f}%")
    print(f"Sharpe Ratio:    {sharpe:.2f} (Target > 1.0)")
    print(f"Max Drawdown:    {mdd*100:.2f}% (Target > -30%)")
    
    # 5. Show the Proof
    plot_performance(df, SYMBOL)