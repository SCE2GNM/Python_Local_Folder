"""
PHASE 4: REGIME DETECTION
FILENAME: 09_regime_detector.py

OBJECTIVE: 
Mathematically distinguish between 'Trending' and 'Mean Reverting' (Chop) markets.

THEORY:
- ADX (Average Directional Index) measures Trend Strength (0-100).
- It does NOT tell you direction (Up/Down), only strength.
- Low ADX (< 25) = Chop -> Ideal for Uniswap.
- High ADX (> 25) = Trend -> Ideal for HODL/Trend Following.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- SETTINGS ---
SYMBOL = "ETH-USD"
START_DATE = "2023-01-01"
END_DATE = "2024-01-01"
ADX_PERIOD = 14
ADX_THRESHOLD = 25  # Below 25 is "Chop", Above 25 is "Trend"

# --- HELPER: WILDER'S SMOOTHING ---
def wilders_smoothing(series, period):
    """
    Standard ADX uses 'Wilder's Smoothing', which is similar to EMA 
    but with a slower decay (alpha = 1/n).
    """
    return series.ewm(alpha=1/period, adjust=False).mean()

# --- MATH ENGINE ---
def calculate_adx(df, period=14):
    """
    Calculates ADX from scratch using High, Low, Close data.
    """
    data = df.copy()
    
    # 1. Calculate True Range (TR)
    # TR is the greatest of:
    #   a) Current High - Current Low
    #   b) Abs(Current High - Previous Close)
    #   c) Abs(Current Low - Previous Close)
    
    data['H-L'] = data['High'] - data['Low']
    data['H-PC'] = abs(data['High'] - data['Close'].shift(1))
    data['L-PC'] = abs(data['Low'] - data['Close'].shift(1))
    data['TR'] = data[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    # 2. Calculate Directional Movement (+DM, -DM)
    # +DM: How much higher is today's high than yesterday's?
    # -DM: How much lower is today's low than yesterday's?
    data['+DM'] = np.where(
        (data['High'] - data['High'].shift(1)) > (data['Low'].shift(1) - data['Low']), 
        np.maximum(data['High'] - data['High'].shift(1), 0), 
        0
    )
    
    data['-DM'] = np.where(
        (data['Low'].shift(1) - data['Low']) > (data['High'] - data['High'].shift(1)), 
        np.maximum(data['Low'].shift(1) - data['Low'], 0), 
        0
    )
    
    # 3. Smooth the TR and DMs (Wilder's Smoothing)
    data['TR_Smooth'] = wilders_smoothing(data['TR'], period)
    data['+DM_Smooth'] = wilders_smoothing(data['+DM'], period)
    data['-DM_Smooth'] = wilders_smoothing(data['-DM'], period)
    
    # 4. Calculate Directional Indicators (+DI, -DI)
    data['+DI'] = 100 * (data['+DM_Smooth'] / data['TR_Smooth'])
    data['-DI'] = 100 * (data['-DM_Smooth'] / data['TR_Smooth'])
    
    # 5. Calculate DX (Directional Index)
    # DX = 100 * Abs(+DI - -DI) / (+DI + -DI)
    data['DX'] = 100 * abs(data['+DI'] - data['-DI']) / (data['+DI'] + data['-DI'])
    
    # 6. Calculate ADX (Smoothed DX)
    data['ADX'] = wilders_smoothing(data['DX'], period)
    
    return data

def fetch_data(symbol, start, end):
    print(f"Fetching {symbol} daily data...")
    df = yf.download(symbol, start=start, end=end, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def plot_regimes(df):
    plt.figure(figsize=(12, 10))
    plt.style.use('dark_background')
    
    # Top Chart: Price with Regime Shading
    ax1 = plt.subplot(2, 1, 1)
    plt.plot(df['Close'], color='white', label='ETH Price', linewidth=1)
    
    # Shade Green where ADX < Threshold (CHOP -> Uniswap)
    # Shade Red where ADX > Threshold (TREND -> HODL)
    plt.fill_between(df.index, df['Close'].min(), df['Close'].max(), 
                     where=(df['ADX'] < ADX_THRESHOLD), 
                     color='lime', alpha=0.1, label='Regime: CHOP (Uniswap)')
    
    plt.fill_between(df.index, df['Close'].min(), df['Close'].max(), 
                     where=(df['ADX'] >= ADX_THRESHOLD), 
                     color='red', alpha=0.1, label='Regime: TREND (HODL)')
    
    plt.title(f'{SYMBOL} Regime Detection (ADX Period {ADX_PERIOD})')
    plt.legend(loc='upper left')
    
    # Bottom Chart: ADX Value
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    plt.plot(df['ADX'], color='yellow', label='ADX Strength')
    plt.axhline(ADX_THRESHOLD, color='white', linestyle='--', label=f'Threshold ({ADX_THRESHOLD})')
    plt.axhline(50, color='gray', linestyle=':', alpha=0.5)
    plt.title('ADX Indicator')
    plt.ylabel('Trend Strength (0-100)')
    plt.legend()
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    df = fetch_data(SYMBOL, START_DATE, END_DATE)
    
    # Calculate Indicators
    df = calculate_adx(df, ADX_PERIOD)
    
    # Drop initial NaN values caused by smoothing lag
    df.dropna(inplace=True)
    
    # Analyze Regimes
    chop_days = len(df[df['ADX'] < ADX_THRESHOLD])
    trend_days = len(df[df['ADX'] >= ADX_THRESHOLD])
    total_days = len(df)
    
    print(f"\n--- REGIME ANALYSIS (2023) ---")
    print(f"Total Trading Days: {total_days}")
    print(f"Chop Days (Uniswap ON):  {chop_days} ({chop_days/total_days:.1%})")
    print(f"Trend Days (Uniswap OFF): {trend_days} ({trend_days/total_days:.1%})")
    
    plot_regimes(df)