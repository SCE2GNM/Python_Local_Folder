"""
PHASE 3b: UNISWAP BACKTESTER (Enhanced Visualization - Fixed)
FILENAME: 07_uniswap_backtester_enhanced.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# --- 1. SIMULATION SETTINGS ---
SYMBOL = "ETH-USD"
START_DATE = "2023-01-01"
END_DATE = "2024-01-01"
INVESTMENT = 10000
RANGE_PCT = 0.20
FEE_TIER = 0.003
DAILY_VOL_TO_TVL = 0.20

# --- 2. UNISWAP MATH ENGINE ---

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

# --- 3. BACKTEST SIMULATION ---

def fetch_data(symbol, start, end):
    print(f"Fetching {symbol} DAILY data (due to API limits)...")
    df = yf.download(symbol, start=start, end=end, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[['Close']]

def run_simulation(df):
    data = df.copy()
    
    entry_price = data['Close'].iloc[0]
    min_price = entry_price * (1 - RANGE_PCT)
    max_price = entry_price * (1 + RANGE_PCT)
    
    print(f"--- SIMULATION START ---")
    print(f"Entry Price: ${entry_price:.2f}")
    print(f"Range:       ${min_price:.2f} - ${max_price:.2f} (±{int(RANGE_PCT*100)}%)")
    
    L, initial_eth, initial_usdc = calculate_liquidity_and_amounts(entry_price, min_price, max_price, INVESTMENT)
    
    portfolio_values = []
    hodl_values = []
    fees_accumulated = []
    running_fees = 0.0
    
    EFFICIENCY_MULTIPLIER = 3.0
    daily_yield_rate = DAILY_VOL_TO_TVL * FEE_TIER * EFFICIENCY_MULTIPLIER
    
    print(f"Simulating {len(data)} days...")
    
    for price in data['Close']:
        in_range = min_price <= price <= max_price
        
        if in_range:
            fee = INVESTMENT * daily_yield_rate
            running_fees += fee
        
        fees_accumulated.append(running_fees)
        val_lp = calculate_lp_value(price, L, min_price, max_price)
        portfolio_values.append(val_lp)
        val_hodl = (initial_eth * price) + initial_usdc
        hodl_values.append(val_hodl)
    
    data['LP_Value'] = portfolio_values
    data['HODL_Value'] = hodl_values
    data['Cumulative_Fees'] = fees_accumulated
    data['Total_Value'] = data['LP_Value'] + data['Cumulative_Fees']
    
    return data, entry_price, min_price, max_price, initial_eth, initial_usdc

def plot_results(data, min_p, max_p, entry_p, init_eth, init_usdc):
    # Use white background for better readability
    plt.style.use('seaborn-v0_8-darkgrid')
    fig = plt.figure(figsize=(20, 14))
    fig.patch.set_facecolor('white')
    
    gs = GridSpec(4, 2, figure=fig, hspace=0.4, wspace=0.3, 
                  height_ratios=[2.5, 1.2, 1.5, 1], top=0.95, bottom=0.05)
    
    # Calculate key metrics
    final_lp = data['Total_Value'].iloc[-1]
    final_hodl = data['HODL_Value'].iloc[-1]
    fees = data['Cumulative_Fees'].iloc[-1]
    net_result = final_lp - final_hodl
    il_amount = data['HODL_Value'].iloc[-1] - data['LP_Value'].iloc[-1]
    days_in_range = ((data['Close'] >= min_p) & (data['Close'] <= max_p)).sum()
    pct_in_range = (days_in_range / len(data)) * 100
    roi_lp = ((final_lp - INVESTMENT) / INVESTMENT) * 100
    roi_hodl = ((final_hodl - INVESTMENT) / INVESTMENT) * 100
    
    # Color scheme
    COLOR_PRICE = '#0066CC'
    COLOR_LP = '#00AA44'
    COLOR_HODL = '#666666'
    COLOR_FEES = '#FFB800'
    COLOR_IL = '#CC3333'
    COLOR_RANGE = '#FF4444'
    COLOR_ENTRY = '#FF8C00'
    
    # --- Chart 1: Price Action & Range ---
    ax1 = fig.add_subplot(gs[0:2, 0])
    ax1.plot(data.index, data['Close'], color=COLOR_PRICE, linewidth=3, label='ETH Price', zorder=3)
    ax1.axhline(min_p, color=COLOR_RANGE, linestyle='--', linewidth=2.5, 
                label=f'Range Bounds (±{int(RANGE_PCT*100)}%)', alpha=0.9)
    ax1.axhline(max_p, color=COLOR_RANGE, linestyle='--', linewidth=2.5, alpha=0.9)
    ax1.axhline(entry_p, color=COLOR_ENTRY, linestyle=':', linewidth=2, 
                label=f'Entry: ${entry_p:.2f}', alpha=0.8)
    
    ax1.fill_between(data.index, min_p, max_p,
                     where=(data['Close'] >= min_p) & (data['Close'] <= max_p),
                     color='#90EE90', alpha=0.3, label='Active Range (Earning Fees)')
    
    ax1.set_title('ETH Price Movement & Liquidity Range', fontsize=16, fontweight='bold', pad=20)
    ax1.set_ylabel('Price (USD)', fontsize=13, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=11, framealpha=0.95)
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax1.tick_params(labelsize=11)
    
    # Price labels on right axis
    ax1_right = ax1.twinx()
    ax1_right.set_ylim(ax1.get_ylim())
    ax1_right.set_yticks([min_p, entry_p, max_p])
    ax1_right.set_yticklabels([f'${min_p:.0f}', f'${entry_p:.0f}', f'${max_p:.0f}'], fontsize=11)
    ax1_right.tick_params(labelsize=11)
    
    # --- Chart 2: Portfolio Value Comparison ---
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(data.index, data['Total_Value'], color=COLOR_LP, linewidth=3.5, 
             label='LP Strategy (Assets + Fees)', zorder=3)
    ax2.plot(data.index, data['HODL_Value'], color=COLOR_HODL, linewidth=3, 
             linestyle='--', label='HODL Benchmark', zorder=2)
    
    ax2.fill_between(data.index, data['Total_Value'], data['HODL_Value'],
                     where=(data['Total_Value'] >= data['HODL_Value']),
                     color=COLOR_LP, alpha=0.2, interpolate=True)
    ax2.fill_between(data.index, data['Total_Value'], data['HODL_Value'],
                     where=(data['Total_Value'] < data['HODL_Value']),
                     color=COLOR_IL, alpha=0.2, interpolate=True)
    
    ax2.set_title('Portfolio Value Over Time', fontsize=14, fontweight='bold', pad=15)
    ax2.set_ylabel('Value (USD)', fontsize=12, fontweight='bold')
    ax2.legend(loc='best', fontsize=10, framealpha=0.95)
    ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax2.tick_params(labelsize=10)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # --- Chart 3: Returns Percentage ---
    ax3 = fig.add_subplot(gs[1, 1])
    lp_returns = ((data['Total_Value'] - INVESTMENT) / INVESTMENT) * 100
    hodl_returns = ((data['HODL_Value'] - INVESTMENT) / INVESTMENT) * 100
    
    ax3.plot(data.index, lp_returns, color=COLOR_LP, linewidth=3, label='LP Returns %', zorder=3)
    ax3.plot(data.index, hodl_returns, color=COLOR_HODL, linewidth=3, 
             linestyle='--', label='HODL Returns %', zorder=2)
    ax3.axhline(0, color='black', linestyle='-', linewidth=1.5, alpha=0.5)
    ax3.fill_between(data.index, 0, lp_returns, where=(lp_returns >= 0), 
                     color=COLOR_LP, alpha=0.2)
    ax3.fill_between(data.index, 0, lp_returns, where=(lp_returns < 0), 
                     color=COLOR_IL, alpha=0.2)
    
    ax3.set_title('Returns Percentage', fontsize=14, fontweight='bold', pad=15)
    ax3.set_ylabel('Return (%)', fontsize=12, fontweight='bold')
    ax3.legend(loc='best', fontsize=10, framealpha=0.95)
    ax3.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax3.tick_params(labelsize=10)
    
    # --- Chart 4: Fee Accumulation & IL ---
    ax4 = fig.add_subplot(gs[2, 0])
    ax4_twin = ax4.twinx()
    
    # Fees on left axis
    line1 = ax4.plot(data.index, data['Cumulative_Fees'], color=COLOR_FEES, 
                     linewidth=4, label='Cumulative Fees', zorder=3)
    ax4.fill_between(data.index, 0, data['Cumulative_Fees'], 
                     color=COLOR_FEES, alpha=0.25)
    
    # IL on right axis
    il_series = data['HODL_Value'] - data['LP_Value']
    line2 = ax4_twin.plot(data.index, il_series, color=COLOR_IL, linewidth=4, 
                          linestyle='--', label='Impermanent Loss', alpha=0.9, zorder=2)
    
    ax4.set_title('Fee Accumulation vs Impermanent Loss', fontsize=14, fontweight='bold', pad=15)
    ax4.set_ylabel('Fees Earned (USD)', fontsize=12, fontweight='bold', color=COLOR_FEES)
    ax4_twin.set_ylabel('IL Amount (USD)', fontsize=12, fontweight='bold', color=COLOR_IL)
    ax4.tick_params(axis='y', labelcolor=COLOR_FEES, labelsize=11)
    ax4_twin.tick_params(axis='y', labelcolor=COLOR_IL, labelsize=11)
    ax4.tick_params(axis='x', labelsize=10)
    ax4.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    ax4_twin.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # Combined legend
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax4.legend(lines, labels, loc='upper left', fontsize=10, framealpha=0.95)
    
    # --- Chart 5: Net Profit/Loss ---
    ax5 = fig.add_subplot(gs[2, 1])
    net_pnl = data['Total_Value'] - data['HODL_Value']
    
    ax5.fill_between(data.index, 0, net_pnl, color=COLOR_LP, 
                     where=(net_pnl >= 0), alpha=0.3, label='LP Winning')
    ax5.fill_between(data.index, 0, net_pnl, color=COLOR_IL, 
                     where=(net_pnl < 0), alpha=0.3, label='HODL Winning')
    ax5.plot(data.index, net_pnl, color=COLOR_PRICE, linewidth=3, zorder=3, label='Net Edge')
    ax5.axhline(0, color='black', linestyle='-', linewidth=1.5, alpha=0.5)
    
    ax5.set_title('Net Edge vs HODL (LP minus HODL)', fontsize=14, fontweight='bold', pad=15)
    ax5.set_ylabel('Difference (USD)', fontsize=12, fontweight='bold')
    ax5.legend(loc='best', fontsize=10, framealpha=0.95)
    ax5.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax5.tick_params(labelsize=10)
    ax5.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # --- Chart 6: Summary Statistics ---
    ax6 = fig.add_subplot(gs[3, :])
    ax6.axis('off')
    
    verdict_symbol = "✓" if net_result > 0 else "✗"
    verdict_text = "LP STRATEGY WINS" if net_result > 0 else "HODL WINS"
    verdict_color = COLOR_LP if net_result > 0 else COLOR_IL
    
    summary_lines = [
        f"PERFORMANCE SUMMARY  │  {data.index[0].strftime('%b %d, %Y')} to {data.index[-1].strftime('%b %d, %Y')}  │  Initial: ${INVESTMENT:,.0f}",
        "─" * 150,
        "",
        f"FINAL VALUES:                          PERFORMANCE:                           RANGE ACTIVITY:",
        f"  LP Strategy:  ${final_lp:>13,.2f}      LP ROI:       {roi_lp:>8.2f}%            In Range:    {days_in_range:>3}/{len(data)} days ({pct_in_range:>5.1f}%)",
        f"  HODL:         ${final_hodl:>13,.2f}      HODL ROI:     {roi_hodl:>8.2f}%            Range:       ${min_p:>8,.0f} - ${max_p:>8,.0f}",
        f"  Net Edge:     ${net_result:>13,.2f}      Difference:   {roi_lp - roi_hodl:>8.2f}%            Fee Tier:    {FEE_TIER*100:>8.2f}%",
        "",
        f"BREAKDOWN:                             VERDICT:",
        f"  Fees:         ${fees:>13,.2f}      {verdict_symbol} {verdict_text}",
        f"  IL Loss:      ${il_amount:>13,.2f}      Net Advantage: ${abs(net_result):>10,.2f} ({abs(net_result/INVESTMENT*100):>5.2f}%)",
    ]
    
    summary_text = '\n'.join(summary_lines)
    
    ax6.text(0.5, 0.5, summary_text, 
             fontsize=12, 
             family='monospace',
             verticalalignment='center', 
             horizontalalignment='center',
             bbox=dict(boxstyle='round,pad=1.5', 
                      facecolor='#f8f8f8', 
                      edgecolor=verdict_color, 
                      linewidth=3))
    
    plt.suptitle('Uniswap V3 Concentrated Liquidity Backtesting Results', 
                 fontsize=18, fontweight='bold', y=0.98)
    
    plt.show()

if __name__ == "__main__":
    df = fetch_data(SYMBOL, START_DATE, END_DATE)
    df, entry, min_p, max_p, init_eth, init_usdc = run_simulation(df)
    
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
    
    plot_results(df, min_p, max_p, entry, init_eth, init_usdc)