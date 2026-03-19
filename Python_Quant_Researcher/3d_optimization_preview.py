"""
3D Optimization Heatmap - Preview of Week 2/3
Shows how different SMA parameters perform across 3 dimensions
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from datetime import datetime

print("🚀 Running 3D Optimization Preview...")
print("This will take 1-2 minutes...\n")

# Download data to PRESENT DAY
ticker = 'BTC-USD'
start_date = '2020-01-01'
end_date = datetime.today().strftime('%Y-%m-%d')  # TODAY!

print(f"Downloading {ticker} from {start_date} to {end_date}...")
df = yf.download(ticker, start=start_date, end=end_date, progress=False)
print(f"✅ Downloaded {len(df)} days of data\n")

# Function to backtest SMA strategy
def backtest_sma(df, short_window, long_window):
    """Quick backtest returning Sharpe ratio"""
    df = df.copy()
    
    # Calculate SMAs
    df['SMA_Short'] = df['Close'].rolling(short_window).mean()
    df['SMA_Long'] = df['Close'].rolling(long_window).mean()
    
    # Generate signals
    df['Signal'] = np.where(df['SMA_Short'] > df['SMA_Long'], 1, 0)
    df['Position'] = df['Signal'].shift(1)
    
    # Calculate returns
    df['Market_Returns'] = df['Close'].pct_change()
    df['Strategy_Returns'] = df['Position'] * df['Market_Returns']
    
    # Drop NaN
    df = df.dropna()
    
    # Calculate Sharpe Ratio
    if len(df) == 0 or df['Strategy_Returns'].std() == 0:
        return 0
    
    mean_return = df['Strategy_Returns'].mean()
    std_return = df['Strategy_Returns'].std()
    sharpe = (mean_return / std_return) * np.sqrt(252)
    
    # Calculate total return
    total_return = (1 + df['Strategy_Returns']).prod() - 1
    
    # Calculate max drawdown
    cumulative = (1 + df['Strategy_Returns']).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_dd = abs(drawdown.min())
    
    return sharpe, total_return, max_dd

# Parameter ranges for optimization
short_range = range(20, 100, 10)   # Short SMA: 20 to 90, step 10
long_range = range(100, 300, 20)   # Long SMA: 100 to 280, step 20

print(f"Testing {len(short_range)} × {len(long_range)} = {len(short_range) * len(long_range)} combinations...")
print("This creates the 3D landscape...\n")

# Store results
results = []
counter = 0
total = len(short_range) * len(long_range)

for short in short_range:
    for long in long_range:
        if short >= long:  # Skip invalid combinations
            continue
        
        counter += 1
        if counter % 10 == 0:
            print(f"Progress: {counter}/{total} ({counter/total*100:.1f}%)")
        
        sharpe, total_return, max_dd = backtest_sma(df, short, long)
        
        results.append({
            'short': short,
            'long': long,
            'sharpe': sharpe,
            'return': total_return * 100,  # Convert to percentage
            'max_dd': max_dd * 100
        })

# Convert to DataFrame
results_df = pd.DataFrame(results)

print(f"\n✅ Tested {len(results_df)} valid combinations!")
print(f"\nBest Result:")
best = results_df.loc[results_df['sharpe'].idxmax()]
print(f"  Short SMA: {best['short']:.0f}")
print(f"  Long SMA: {best['long']:.0f}")
print(f"  Sharpe Ratio: {best['sharpe']:.2f}")
print(f"  Total Return: {best['return']:.2f}%")
print(f"  Max Drawdown: {best['max_dd']:.2f}%")

# Create 3D visualization
fig = plt.figure(figsize=(16, 12))

# Plot 1: 3D Surface - Sharpe Ratio
ax1 = fig.add_subplot(2, 2, 1, projection='3d')

# Create meshgrid for surface plot
short_unique = sorted(results_df['short'].unique())
long_unique = sorted(results_df['long'].unique())
X, Y = np.meshgrid(short_unique, long_unique)
Z = np.zeros_like(X, dtype=float)

for i, short in enumerate(short_unique):
    for j, long in enumerate(long_unique):
        match = results_df[(results_df['short'] == short) & (results_df['long'] == long)]
        if len(match) > 0:
            Z[j, i] = match['sharpe'].values[0]

surf1 = ax1.plot_surface(X, Y, Z, cmap='viridis', alpha=0.8, edgecolor='none')
ax1.set_xlabel('Short SMA Window', fontsize=10, labelpad=10)
ax1.set_ylabel('Long SMA Window', fontsize=10, labelpad=10)
ax1.set_zlabel('Sharpe Ratio', fontsize=10, labelpad=10)
ax1.set_title('3D Optimization: Sharpe Ratio', fontsize=12, fontweight='bold', pad=20)
ax1.view_init(elev=25, azim=45)
fig.colorbar(surf1, ax=ax1, shrink=0.5, aspect=5)

# Plot 2: 3D Scatter - Total Return (colored by Sharpe)
ax2 = fig.add_subplot(2, 2, 2, projection='3d')

scatter = ax2.scatter(
    results_df['short'], 
    results_df['long'], 
    results_df['return'],
    c=results_df['sharpe'],
    cmap='RdYlGn',
    s=100,
    alpha=0.6,
    edgecolors='black',
    linewidth=0.5
)

ax2.set_xlabel('Short SMA Window', fontsize=10, labelpad=10)
ax2.set_ylabel('Long SMA Window', fontsize=10, labelpad=10)
ax2.set_zlabel('Total Return (%)', fontsize=10, labelpad=10)
ax2.set_title('3D Scatter: Return vs Parameters\n(Color = Sharpe)', fontsize=12, fontweight='bold', pad=20)
ax2.view_init(elev=25, azim=135)
fig.colorbar(scatter, ax=ax2, shrink=0.5, aspect=5, label='Sharpe Ratio')

# Plot 3: 3D Scatter - Max Drawdown
ax3 = fig.add_subplot(2, 2, 3, projection='3d')

scatter2 = ax3.scatter(
    results_df['short'], 
    results_df['long'], 
    results_df['max_dd'],
    c=results_df['sharpe'],
    cmap='RdYlGn',
    s=100,
    alpha=0.6,
    edgecolors='black',
    linewidth=0.5
)

ax3.set_xlabel('Short SMA Window', fontsize=10, labelpad=10)
ax3.set_ylabel('Long SMA Window', fontsize=10, labelpad=10)
ax3.set_zlabel('Max Drawdown (%)', fontsize=10, labelpad=10)
ax3.set_title('3D Scatter: Risk vs Parameters\n(Color = Sharpe)', fontsize=12, fontweight='bold', pad=20)
ax3.view_init(elev=25, azim=225)
ax3.invert_zaxis()  # Invert so lower drawdown is "higher" (better)
fig.colorbar(scatter2, ax=ax3, shrink=0.5, aspect=5, label='Sharpe Ratio')

# Plot 4: 2D Heatmap - Sharpe Ratio
ax4 = fig.add_subplot(2, 2, 4)

heatmap_data = results_df.pivot(index='long', columns='short', values='sharpe')

im = ax4.imshow(heatmap_data, cmap='RdYlGn', aspect='auto', origin='lower')
ax4.set_xlabel('Short SMA Window', fontsize=10)
ax4.set_ylabel('Long SMA Window', fontsize=10)
ax4.set_title('2D Heatmap: Sharpe Ratio', fontsize=12, fontweight='bold')

# Set tick labels
ax4.set_xticks(range(len(short_unique)))
ax4.set_xticklabels([int(x) for x in short_unique], rotation=45)
ax4.set_yticks(range(len(long_unique)))
ax4.set_yticklabels([int(x) for x in long_unique])

# Add colorbar
fig.colorbar(im, ax=ax4, label='Sharpe Ratio')

# Mark the best point
best_short_idx = list(short_unique).index(best['short'])
best_long_idx = list(long_unique).index(best['long'])
ax4.plot(best_short_idx, best_long_idx, 'r*', markersize=20, 
         markeredgecolor='white', markeredgewidth=2, label='Best')
ax4.legend()

plt.suptitle(f'SMA Strategy Optimization - {ticker} ({start_date} to {end_date})', 
             fontsize=16, fontweight='bold', y=0.98)

plt.tight_layout()
plt.savefig('3d_optimization_preview.png', dpi=300, bbox_inches='tight')
print(f"\n✅ Visualization saved as '3d_optimization_preview.png'")
plt.show()

print("\n🎉 Preview complete! This is what you'll master in Week 2-3!")