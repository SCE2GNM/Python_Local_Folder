"""
PHASE 2b: INSTITUTIONAL DATA
STRATEGY: Funding Rate Mean Reversion
SOURCE: Binance Futures (via CCXT)

HYPOTHESIS:
Extreme positive funding rates (>0.05%) indicate euphoric over-leverage.
These moments often precede a "Long Squeeze" (Crash).
"""

import ccxt
import pandas as pd
import matplotlib.pyplot as plt

# --- SETTINGS ---
SYMBOL = 'BTC/USDT'
LIMIT = 1000  # 1000 periods of 8 hours = ~330 days of data

def fetch_binance_data(symbol, limit):
    """
    Connects to Binance FUTURES API to get funding rates.
    """
    print(f"Connecting to Binance Futures to fetch {symbol} data...")
    
    # CRITICAL FIX: Connect to the Futures Exchange, not Spot
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future' 
        }
    })
    
    try:
        # 1. Fetch Funding Rate History
        # This returns a list of dictionaries: [{'symbol': 'BTC/USDT', 'fundingRate': 0.0001, 'timestamp': 160...}, ...]
        funding_data = exchange.fetch_funding_rate_history(symbol, limit=limit)
        
        # Debug Check: Did we get anything?
        if not funding_data:
            print("ERROR: API returned no funding data. Check Symbol or API status.")
            return pd.DataFrame()
            
        # Convert to DataFrame
        df_fund = pd.DataFrame(funding_data)
        
        # FIX: Ensure we use the raw 'timestamp' (ms integer)
        df_fund['timestamp'] = pd.to_datetime(df_fund['timestamp'], unit='ms')
        df_fund.set_index('timestamp', inplace=True)
        
        # Keep only the funding rate
        df_fund = df_fund[['fundingRate']]
        
        # 2. Fetch OHLCV (Price) Data
        # '8h' timeframe matches the standard funding interval
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='8h', limit=limit)
        
        df_price = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_price['timestamp'] = pd.to_datetime(df_price['timestamp'], unit='ms')
        df_price.set_index('timestamp', inplace=True)
        
        # 3. Merge Datasets
        # We align them on the index (Time)
        merged = pd.merge(df_price, df_fund, left_index=True, right_index=True, how='inner')
        
        return merged
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return pd.DataFrame()

def analyze_funding(df):
    """
    Identify Extreme States.
    """
    # Convert to percentage (0.0001 -> 0.01%)
    df['Funding_Pct'] = df['fundingRate'] * 100
    
    # Calculate Stats
    mean_rate = df['Funding_Pct'].mean()
    std_rate = df['Funding_Pct'].std()
    
    # 2 Standard Deviations (Bollinger Band Logic)
    upper_band = mean_rate + (2 * std_rate)
    lower_band = mean_rate - (2 * std_rate)
    
    print(f"\n--- STATISTICS ---")
    print(f"Average Funding: {mean_rate:.4f}% (per 8h)")
    print(f"Extreme Greed Threshold: > {upper_band:.4f}%")
    print(f"Extreme Fear Threshold:  < {lower_band:.4f}%")
    
    return df, upper_band, lower_band

def plot_funding(df, upper, lower):
    plt.figure(figsize=(12, 10))
    plt.style.use('dark_background')
    
    # Top Chart: Price
    ax1 = plt.subplot(2, 1, 1)
    plt.plot(df.index, df['close'], color='cyan', label='BTC Price')
    plt.title(f'{SYMBOL} Price vs Funding Rate (8h Intervals)')
    plt.ylabel('Price (USDT)')
    plt.grid(True, alpha=0.2)
    
    # Bottom Chart: Funding Rate
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    
    # Color bar based on Positive/Negative
    colors = ['lime' if x > 0 else 'red' for x in df['Funding_Pct']]
    plt.bar(df.index, df['Funding_Pct'], color=colors, width=0.02) # Adjusted width for 8h bars
    
    # Add Threshold Lines
    plt.axhline(upper, color='orange', linestyle='--', label='Extreme Greed')
    plt.axhline(lower, color='magenta', linestyle='--', label='Extreme Fear')
    plt.axhline(0.01, color='white', alpha=0.3, linestyle=':', label='Baseline (0.01%)')
    
    plt.ylabel('Funding Rate (%)')
    plt.legend()
    plt.grid(True, alpha=0.2)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # 1. Run Pipeline
    data = fetch_binance_data(SYMBOL, LIMIT)
    
    # 2. Check Success
    if not data.empty:
        data, high_thresh, low_thresh = analyze_funding(data)
        plot_funding(data, high_thresh, low_thresh)
    else:
        print("Data fetch failed. Please check internet connection or VPN settings.")