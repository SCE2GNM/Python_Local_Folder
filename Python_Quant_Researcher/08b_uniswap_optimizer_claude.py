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
    entry_price = df['Close'].iloc[0]
    min_price = entry_price * (1 - range_pct)
    max_price = entry_price * (1 + range_pct)
    
    L, initial_eth, initial_usdc = calculate_liquidity_and_amounts(entry_price, min_price, max_price, INVESTMENT)
    
    efficiency_multiplier = 3.0 * (0.20 / range_pct)
    daily_yield = DAILY_VOL_TO_TVL * FEE_TIER * efficiency_multiplier
    
    in_range_mask = (df['Close'] >= min_price) & (df['Close'] <= max_price)
    days_in_range = in_range_mask.sum()
    total_fees = days_in_range * (INVESTMENT * daily_yield)
    
    final_price = df['Close'].iloc[-1]
    final_lp_assets = calculate_lp_value(final_price, L, min_price, max_price)
    final_lp_total = final_lp_assets + total_fees
    
    final_hodl = (initial_eth * final_price) + initial_usdc
    
    # Return additional metrics
    return {
        'net_edge': final_lp_total - final_hodl,
        'days_in_range': days_in_range,
        'total_fees': total_fees,
        'final_lp_total': final_lp_total,
        'final_hodl': final_hodl,
        'uptime_pct': (days_in_range / len(df)) * 100
    }

# --- GRID SEARCH ---
def optimize_range(df):
    results = []
    test_ranges = np.arange(0.05, 0.61, 0.01)
    
    print(f"Testing {len(test_ranges)} different ranges...")
    
    for r in test_ranges:
        metrics = run_single_backtest(df, r)
        results.append({
            'Range': r * 100,
            'Net_Edge': metrics['net_edge'],
            'Days_In_Range': metrics['days_in_range'],
            'Total_Fees': metrics['total_fees'],
            'Uptime_Pct': metrics['uptime_pct']
        })
        
    return pd.DataFrame(results)

def plot_optimization(results, df):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    plt.style.use('dark_background')
    
    # === PLOT 1: Net Edge vs HODL ===
    ax1.plot(results['Range'], results['Net_Edge'], color='cyan', linewidth=2.5, 
             marker='o', markersize=4, label='Net P&L vs HODL')
    
    # Zero line
    ax1.axhline(0, color='white', linestyle='--', linewidth=1.5, label='HODL Breakeven', alpha=0.8)
    
    # Color fills
    ax1.fill_between(results['Range'], results['Net_Edge'], 0, 
                      where=(results['Net_Edge'] > 0), color='lime', alpha=0.3, label='Profitable Zone')
    ax1.fill_between(results['Range'], results['Net_Edge'], 0, 
                      where=(results['Net_Edge'] < 0), color='red', alpha=0.3, label='Loss Zone')
    
    # Mark optimal point
    best_idx = results['Net_Edge'].idxmax()
    best_range = results.loc[best_idx, 'Range']
    best_edge = results.loc[best_idx, 'Net_Edge']
    ax1.scatter([best_range], [best_edge], color='yellow', s=200, marker='*', 
                zorder=5, label=f'Optimal: ±{best_range:.1f}%', edgecolors='black', linewidths=1.5)
    
    # Formatting
    ax1.set_title(f'Uniswap V3 Range Optimization: {SYMBOL} ({START_DATE} to {END_DATE})', 
                  fontsize=16, fontweight='bold', pad=20)
    ax1.set_xlabel('Range Width (±%)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Net Profit vs HODL ($)', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle=':', linewidth=0.8)
    ax1.legend(loc='best', fontsize=10, framealpha=0.9)
    
    # Format y-axis with dollar signs
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # Add annotations
    ax1.annotate(f'Max Profit: ${best_edge:,.2f}', 
                xy=(best_range, best_edge), 
                xytext=(best_range + 5, best_edge + abs(best_edge) * 0.2),
                fontsize=10, color='yellow', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='yellow', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.5', facecolor='black', alpha=0.8))
    
    # === PLOT 2: Uptime Percentage ===
    ax2.plot(results['Range'], results['Uptime_Pct'], color='orange', linewidth=2.5, 
             marker='s', markersize=3, label='Position Uptime %')
    ax2.fill_between(results['Range'], results['Uptime_Pct'], 0, color='orange', alpha=0.2)
    
    # Mark optimal point uptime
    best_uptime = results.loc[best_idx, 'Uptime_Pct']
    ax2.scatter([best_range], [best_uptime], color='yellow', s=200, marker='*', 
                zorder=5, edgecolors='black', linewidths=1.5)
    
    # Formatting
    ax2.set_title('Position Uptime: Days In Range', fontsize=14, fontweight='bold', pad=15)
    ax2.set_xlabel('Range Width (±%)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Uptime (%)', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, linestyle=':', linewidth=0.8)
    ax2.legend(loc='best', fontsize=10, framealpha=0.9)
    ax2.set_ylim(0, 105)
    
    # Format y-axis with percentage
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.0f}%'))
    
    # Add info box
    info_text = f"""
    Investment: ${INVESTMENT:,}
    Fee Tier: {FEE_TIER*100:.2f}%
    Period: {len(df)} days
    Entry: ${df['Close'].iloc[0]:,.2f}
    Exit: ${df['Close'].iloc[-1]:,.2f}
    """
    ax2.text(0.02, 0.98, info_text.strip(), transform=ax2.transAxes,
             fontsize=9, verticalalignment='top', 
             bbox=dict(boxstyle='round', facecolor='black', alpha=0.8),
             family='monospace', color='white')
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    data = fetch_data(SYMBOL, START_DATE, END_DATE)
    results_df = optimize_range(data)
    
    # Find Best Range
    best_run = results_df.loc[results_df['Net_Edge'].idxmax()]
    
    print(f"\n{'='*50}")
    print(f"OPTIMIZATION RESULTS")
    print(f"{'='*50}")
    print(f"Best Range:        ±{best_run['Range']:.1f}%")
    print(f"Max Edge vs HODL:  ${best_run['Net_Edge']:,.2f}")
    print(f"Total Fees Earned: ${best_run['Total_Fees']:,.2f}")
    print(f"Position Uptime:   {best_run['Uptime_Pct']:.1f}%")
    print(f"Days In Range:     {best_run['Days_In_Range']:.0f}/{len(data)} days")
    print(f"{'='*50}\n")
    
    plot_optimization(results_df, data)