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
import matplotlib
matplotlib.use('TkAgg')  # Ensures graph displays properly
import matplotlib.pyplot as plt
import numpy as np

# --- SETTINGS ---
SYMBOL = 'BTC/USDT'
LIMIT = 1000  # 1000 periods of 8 hours = ~330 days of data

def fetch_binance_data(symbol, limit):
    """
    Connects to Binance FUTURES API to get funding rates.
    """
    print(f"Connecting to Binance Futures to fetch {symbol} data...")
    
    # Connect to the Futures Exchange, not Spot
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future' 
        }
    })
    
    try:
        # 1. Fetch Funding Rate History
        funding_data = exchange.fetch_funding_rate_history(symbol, limit=limit)
        
        if not funding_data:
            print("ERROR: API returned no funding data. Check Symbol or API status.")
            return pd.DataFrame()
            
        # Convert to DataFrame
        df_fund = pd.DataFrame(funding_data)
        
        # Ensure we use the raw 'timestamp' (ms integer)
        df_fund['timestamp'] = pd.to_datetime(df_fund['timestamp'], unit='ms')
        df_fund.set_index('timestamp', inplace=True)
        
        # Keep only the funding rate
        df_fund = df_fund[['fundingRate']]
        
        print(f"✓ Funding data points fetched: {len(df_fund)}")
        
        # 2. Fetch OHLCV (Price) Data
        # '8h' timeframe matches the standard funding interval
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='8h', limit=limit)
        
        df_price = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_price['timestamp'] = pd.to_datetime(df_price['timestamp'], unit='ms')
        df_price.set_index('timestamp', inplace=True)
        
        print(f"✓ Price data points fetched: {len(df_price)}")
        
        # 3. Merge Datasets
        # We align them on the index (Time)
        merged = pd.merge(df_price, df_fund, left_index=True, right_index=True, how='inner')
        
        print(f"✓ Merged data points: {len(merged)}")
        
        if len(merged) == 0:
            print("WARNING: Merge resulted in 0 rows. Check timestamp alignment.")
        
        return merged
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
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
    
    # Count extreme events
    extreme_greed = (df['Funding_Pct'] > upper_band).sum()
    extreme_fear = (df['Funding_Pct'] < lower_band).sum()
    
    print(f"\n--- FUNDING RATE STATISTICS ---")
    print(f"Average Funding: {mean_rate:.4f}% (per 8h)")
    print(f"Std Deviation:   {std_rate:.4f}%")
    print(f"Extreme Greed Threshold: > {upper_band:.4f}%")
    print(f"Extreme Fear Threshold:  < {lower_band:.4f}%")
    print(f"\nExtreme Events:")
    print(f"  Greed (High Funding): {extreme_greed} occurrences")
    print(f"  Fear (Low Funding):   {extreme_fear} occurrences")
    
    return df, upper_band, lower_band

def plot_funding(df, upper, lower):
    """
    Create improved visualization with better formatting.
    """
    fig = plt.figure(figsize=(14, 10))
    plt.style.use('dark_background')
    
    # Ensure tick labels are visible
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10
    plt.rcParams['xtick.color'] = 'white'
    plt.rcParams['ytick.color'] = 'white'
    
    # Top Chart: Price with marked extreme funding events
    ax1 = plt.subplot(2, 1, 1)
    plt.plot(df.index, df['close'], color='cyan', linewidth=1.5, label='BTC Price')
    
    # Mark extreme funding periods on price chart
    extreme_high = df[df['Funding_Pct'] > upper]
    extreme_low = df[df['Funding_Pct'] < lower]
    
    plt.scatter(extreme_high.index, extreme_high['close'], 
                color='orange', s=50, alpha=0.7, label='Extreme Greed', zorder=5)
    plt.scatter(extreme_low.index, extreme_low['close'], 
                color='magenta', s=50, alpha=0.7, label='Extreme Fear', zorder=5)
    
    plt.title(f'{SYMBOL} Price vs Funding Rate Analysis (8h Intervals)', 
              fontsize=14, fontweight='bold')
    plt.ylabel('Price (USDT)', fontsize=12)
    plt.legend(loc='upper right', framealpha=0.9)
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Bottom Chart: Funding Rate with improved visualization
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    
    # Use fill_between for better visibility
    plt.fill_between(df.index, 0, df['Funding_Pct'], 
                     where=(df['Funding_Pct'] > 0), 
                     color='lime', alpha=0.4, label='Positive Funding (Longs Pay)')
    plt.fill_between(df.index, 0, df['Funding_Pct'], 
                     where=(df['Funding_Pct'] <= 0), 
                     color='red', alpha=0.4, label='Negative Funding (Shorts Pay)')
    
    # Add line for clarity
    plt.plot(df.index, df['Funding_Pct'], color='white', linewidth=0.8, alpha=0.8)
    
    # Add Threshold Lines
    plt.axhline(upper, color='orange', linestyle='--', linewidth=2, 
                label=f'Extreme Greed ({upper:.3f}%)')
    plt.axhline(lower, color='magenta', linestyle='--', linewidth=2, 
                label=f'Extreme Fear ({lower:.3f}%)')
    plt.axhline(0.01, color='white', alpha=0.3, linestyle=':', 
                label='Typical Rate (0.01%)')
    plt.axhline(0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)
    
    plt.ylabel('Funding Rate (%)', fontsize=12)
    plt.xlabel('Date', fontsize=12)
    plt.legend(loc='upper right', fontsize=9, framealpha=0.9)
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Format x-axis dates and ensure labels are visible
    import matplotlib.dates as mdates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.gcf().autofmt_xdate()
    
    plt.tight_layout()
    print("\n✓ Displaying chart...")
    plt.show()

def export_extreme_events(df, upper, lower):
    """
    Export extreme funding events to CSV for further analysis.
    """
    extreme_events = df[
        (df['Funding_Pct'] > upper) | (df['Funding_Pct'] < lower)
    ].copy()
    
    extreme_events['Event_Type'] = extreme_events['Funding_Pct'].apply(
        lambda x: 'EXTREME_GREED' if x > upper else 'EXTREME_FEAR'
    )
    
    if not extreme_events.empty:
        filename = f'{SYMBOL.replace("/", "_")}_extreme_funding_events.csv'
        extreme_events.to_csv(filename)
        print(f"\n✓ Extreme events exported to: {filename}")
    
    return extreme_events

if __name__ == "__main__":
    print("=" * 60)
    print("BINANCE FUNDING RATE ANALYZER")
    print("=" * 60)
    
    # 1. Fetch Data
    data = fetch_binance_data(SYMBOL, LIMIT)
    
    # 2. Check Success
    if not data.empty:
        # 3. Analyze
        data, high_thresh, low_thresh = analyze_funding(data)
        
        # 4. Export extreme events
        extreme_events = export_extreme_events(data, high_thresh, low_thresh)
        
        # 5. Visualize
        plot_funding(data, high_thresh, low_thresh)
        
        print("\n" + "=" * 60)
        print("Analysis Complete!")
        print("=" * 60)
    else:
        print("\n❌ Data fetch failed. Please check:")
        print("  - Internet connection")
        print("  - VPN settings (some regions block Binance)")
        print("  - API status at https://www.binance.com/en/support/announcement")