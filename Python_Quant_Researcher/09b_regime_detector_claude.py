"""
PHASE 4: REGIME DETECTION (ENHANCED)
FILENAME: 09_regime_detector_enhanced.py

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
from matplotlib.patches import Rectangle

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
    data['H-L'] = data['High'] - data['Low']
    data['H-PC'] = abs(data['High'] - data['Close'].shift(1))
    data['L-PC'] = abs(data['Low'] - data['Close'].shift(1))
    data['TR'] = data[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    # 2. Calculate Directional Movement (+DM, -DM)
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

def identify_regime_periods(df):
    """Identify continuous periods of each regime"""
    df['Regime'] = np.where(df['ADX'] < ADX_THRESHOLD, 'CHOP', 'TREND')
    df['Regime_Change'] = df['Regime'] != df['Regime'].shift(1)
    df['Regime_Group'] = df['Regime_Change'].cumsum()
    
    periods = []
    for group_id in df['Regime_Group'].unique():
        group = df[df['Regime_Group'] == group_id]
        periods.append({
            'regime': group['Regime'].iloc[0],
            'start': group.index[0],
            'end': group.index[-1],
            'days': len(group),
            'start_price': group['Close'].iloc[0],
            'end_price': group['Close'].iloc[-1],
            'return': (group['Close'].iloc[-1] / group['Close'].iloc[0] - 1) * 100
        })
    return periods

def plot_regimes(df):
    fig = plt.figure(figsize=(16, 12))
    plt.style.use('dark_background')
    
    # Define colors
    chop_color = '#00ff88'  # Bright green
    trend_color = '#ff4444'  # Bright red
    price_color = '#00d4ff'  # Cyan
    adx_color = '#ffd700'    # Gold
    
    # TOP PANEL: Price with Regime Shading
    ax1 = plt.subplot(3, 1, 1)
    
    # Plot price line
    ax1.plot(df.index, df['Close'], color=price_color, linewidth=2, 
             label='ETH Price', zorder=3)
    
    # Shade regime backgrounds
    ax1.fill_between(df.index, df['Close'].min() * 0.95, df['Close'].max() * 1.05, 
                     where=(df['ADX'] < ADX_THRESHOLD), 
                     color=chop_color, alpha=0.15, label='CHOP Regime (Uniswap Friendly)')
    
    ax1.fill_between(df.index, df['Close'].min() * 0.95, df['Close'].max() * 1.05, 
                     where=(df['ADX'] >= ADX_THRESHOLD), 
                     color=trend_color, alpha=0.15, label='TREND Regime (HODL Zone)')
    
    ax1.set_title(f'{SYMBOL} Market Regime Detection | ADX Period: {ADX_PERIOD}', 
                  fontsize=16, fontweight='bold', pad=20)
    ax1.set_ylabel('Price (USD)', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=10, framealpha=0.9)
    ax1.grid(True, alpha=0.2, linestyle='--')
    ax1.set_ylim(df['Close'].min() * 0.95, df['Close'].max() * 1.05)
    
    # MIDDLE PANEL: ADX with Directional Indicators
    ax2 = plt.subplot(3, 1, 2, sharex=ax1)
    
    # Plot ADX
    ax2.plot(df.index, df['ADX'], color=adx_color, linewidth=2.5, 
             label='ADX (Trend Strength)', zorder=3)
    
    # Plot +DI and -DI for additional context
    ax2.plot(df.index, df['+DI'], color='#00ff00', linewidth=1, 
             alpha=0.6, label='+DI (Upward Pressure)', linestyle='--')
    ax2.plot(df.index, df['-DI'], color='#ff6666', linewidth=1, 
             alpha=0.6, label='-DI (Downward Pressure)', linestyle='--')
    
    # Add threshold line
    ax2.axhline(ADX_THRESHOLD, color='white', linestyle='--', linewidth=2, 
                label=f'Regime Threshold ({ADX_THRESHOLD})', zorder=2)
    
    # Add reference lines
    ax2.axhline(50, color='gray', linestyle=':', alpha=0.4, linewidth=1)
    ax2.axhline(75, color='gray', linestyle=':', alpha=0.3, linewidth=1)
    
    # Shade regime zones
    ax2.fill_between(df.index, 0, 100, where=(df['ADX'] < ADX_THRESHOLD), 
                     color=chop_color, alpha=0.1)
    ax2.fill_between(df.index, 0, 100, where=(df['ADX'] >= ADX_THRESHOLD), 
                     color=trend_color, alpha=0.1)
    
    # Add zone labels
    ax2.text(df.index[len(df)//2], 12, 'CHOP ZONE', 
             fontsize=11, fontweight='bold', color=chop_color, alpha=0.5, ha='center')
    ax2.text(df.index[len(df)//2], 62, 'TREND ZONE', 
             fontsize=11, fontweight='bold', color=trend_color, alpha=0.5, ha='center')
    
    ax2.set_ylabel('Indicator Value', fontsize=12, fontweight='bold')
    ax2.set_ylim(0, 100)
    ax2.legend(loc='upper left', fontsize=9, framealpha=0.9)
    ax2.grid(True, alpha=0.2, linestyle='--')
    
    # BOTTOM PANEL: Regime Statistics
    ax3 = plt.subplot(3, 1, 3, sharex=ax1)
    
    # Create regime change markers
    df['Regime_Marker'] = np.where(df['ADX'] < ADX_THRESHOLD, 0, 1)
    ax3.fill_between(df.index, 0, 1, where=(df['Regime_Marker'] == 0), 
                     color=chop_color, alpha=0.6, label='CHOP', step='mid')
    ax3.fill_between(df.index, 0, 1, where=(df['Regime_Marker'] == 1), 
                     color=trend_color, alpha=0.6, label='TREND', step='mid')
    
    ax3.set_ylabel('Active Regime', fontsize=12, fontweight='bold')
    ax3.set_yticks([0.25, 0.75])
    ax3.set_yticklabels(['CHOP', 'TREND'], fontweight='bold')
    ax3.set_ylim(0, 1)
    ax3.grid(True, alpha=0.2, linestyle='--', axis='x')
    ax3.set_xlabel('Date', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    plt.show()

def print_regime_analysis(df, periods):
    """Enhanced regime statistics"""
    chop_days = len(df[df['ADX'] < ADX_THRESHOLD])
    trend_days = len(df[df['ADX'] >= ADX_THRESHOLD])
    total_days = len(df)
    
    print("\n" + "="*70)
    print(f"{'REGIME ANALYSIS REPORT':^70}")
    print(f"{SYMBOL} | Period: {START_DATE} to {END_DATE}")
    print("="*70)
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   Total Trading Days:     {total_days}")
    print(f"   CHOP Days (Uniswap):    {chop_days:>4} ({chop_days/total_days:>6.1%})")
    print(f"   TREND Days (HODL):      {trend_days:>4} ({trend_days/total_days:>6.1%})")
    
    print(f"\n📈 ADX STATISTICS:")
    print(f"   Mean ADX:               {df['ADX'].mean():.2f}")
    print(f"   Median ADX:             {df['ADX'].median():.2f}")
    print(f"   Max ADX:                {df['ADX'].max():.2f}")
    print(f"   Min ADX:                {df['ADX'].min():.2f}")
    
    # Regime period analysis
    chop_periods = [p for p in periods if p['regime'] == 'CHOP']
    trend_periods = [p for p in periods if p['regime'] == 'TREND']
    
    print(f"\n🔄 REGIME TRANSITIONS:")
    print(f"   Number of Regime Changes: {len(periods)}")
    print(f"   CHOP Periods:             {len(chop_periods)}")
    print(f"   TREND Periods:            {len(trend_periods)}")
    
    if chop_periods:
        avg_chop_duration = np.mean([p['days'] for p in chop_periods])
        print(f"   Avg CHOP Duration:        {avg_chop_duration:.1f} days")
    
    if trend_periods:
        avg_trend_duration = np.mean([p['days'] for p in trend_periods])
        print(f"   Avg TREND Duration:       {avg_trend_duration:.1f} days")
    
    print(f"\n💡 LONGEST PERIODS:")
    longest_chop = max(chop_periods, key=lambda x: x['days']) if chop_periods else None
    longest_trend = max(trend_periods, key=lambda x: x['days']) if trend_periods else None
    
    if longest_chop:
        print(f"   Longest CHOP: {longest_chop['days']} days "
              f"({longest_chop['start'].strftime('%Y-%m-%d')} to {longest_chop['end'].strftime('%Y-%m-%d')})")
    
    if longest_trend:
        print(f"   Longest TREND: {longest_trend['days']} days "
              f"({longest_trend['start'].strftime('%Y-%m-%d')} to {longest_trend['end'].strftime('%Y-%m-%d')})")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    df = fetch_data(SYMBOL, START_DATE, END_DATE)
    
    # Calculate Indicators
    df = calculate_adx(df, ADX_PERIOD)
    
    # Drop initial NaN values caused by smoothing lag
    df.dropna(inplace=True)
    
    # Identify regime periods
    periods = identify_regime_periods(df)
    
    # Print analysis
    print_regime_analysis(df, periods)
    
    # Plot enhanced visualization
    plot_regimes(df)