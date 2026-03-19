"""
PHASE 3: DEFI MATH (CORRECTED VERSION)
FILENAME: 06.2_uniswap_math_corrected.py

DIFFERENCE FROM PREVIOUS VERSION (06):
1. Asset Initialization: 
   - Old version assumed you deposited 50% ETH and 50% USDC ($5k/$5k).
   - This version calculates the *exact* ratio required by the pool for your specific range.
   - Example: If range is $2500-$3500 and price is $3000, the pool might actually demand 
     46% ETH and 54% USDC.
   
2. HODL Benchmark:
   - This version sets the HODL benchmark to match that *exact* specific basket.
   - Result: Impermanent Loss at entry price ($3000) will now correctly be 0.00%.

MATH CORE:
Uniswap V3 Geometric Ratio:
The ratio of y/x (USDC/ETH) changes as price moves. We must solve for L first, 
then back-calculate the required x and y.
"""

import numpy as np
import matplotlib.pyplot as plt

# --- SETTINGS ---
ENTRY_PRICE = 3000   # ETH Price
MIN_RANGE = 2500     # Lower bound
MAX_RANGE = 3500     # Upper bound
INVESTMENT = 10000   # Total USD to deploy

def calculate_liquidity_and_amounts(price, Pa, Pb, max_usd):
    """
    Step 1: Determine the specific mix of ETH/USDC needed.
    
    The Math:
    We calculate the Liquidity (L) provided by 1 unit of ETH at current price.
    We then find the corresponding amount of USDC needed to match that L.
    Finally, we scale both up until their total value equals our INVESTMENT ($10k).
    """
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    # 1. Calculate a theoretical 'test' liquidity bundle using 1.0 ETH
    L_test = (1.0 * sqrt_P * sqrt_Pb) / (sqrt_Pb - sqrt_P)
    
    # 2. Calculate how much USDC corresponds to that L_test
    usdc_test = L_test * (sqrt_P - sqrt_Pa)
    
    # 3. Calculate the total dollar value of this test bundle
    value_test = (1.0 * price) + usdc_test
    
    # 4. Calculate the Scaling Factor
    scale = max_usd / value_test
    
    # 5. Apply Scale to get final amounts
    final_eth = 1.0 * scale
    final_usdc = usdc_test * scale
    final_L = L_test * scale
    
    return final_L, final_eth, final_usdc

def calculate_lp_value(price, L, Pa, Pb):
    """
    Step 2: Calculate value of the LP position at a future price.
    """
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    if price <= Pa:
        # Case A: Price Crashed below Range -> We hold 100% ETH
        amount_eth = L * (sqrt_Pb - sqrt_Pa) / (sqrt_Pa * sqrt_Pb)
        return amount_eth * price
        
    elif price >= Pb:
        # Case B: Price Mooned above Range -> We hold 100% USDC
        amount_usdc = L * (sqrt_Pb - sqrt_Pa)
        return amount_usdc
        
    else:
        # Case C: In Range -> We hold a mix
        amount_eth = L * (sqrt_Pb - sqrt_P) / (sqrt_P * sqrt_Pb)
        amount_usdc = L * (sqrt_P - sqrt_Pa)
        return (amount_eth * price) + amount_usdc

def simulate_curve():
    print(f"--- UNISWAP V3 SIMULATION (CORRECTED) ---")
    
    # 1. INITIALIZATION
    L, initial_eth, initial_usdc = calculate_liquidity_and_amounts(ENTRY_PRICE, MIN_RANGE, MAX_RANGE, INVESTMENT)
    
    eth_pct = (initial_eth * ENTRY_PRICE) / INVESTMENT * 100
    usdc_pct = initial_usdc / INVESTMENT * 100
    
    print(f"Entry Price: ${ENTRY_PRICE}")
    print(f"Invested:    ${(initial_eth * ENTRY_PRICE) + initial_usdc:.2f}")
    print(f"Basket:      {initial_eth:.4f} ETH + ${initial_usdc:.2f} USDC")
    print(f"Split:       {eth_pct:.1f}% ETH / {usdc_pct:.1f}% USDC")
    
    # 2. SIMULATION LOOP
    prices = np.linspace(ENTRY_PRICE * 0.5, ENTRY_PRICE * 1.5, 200)
    lp_values = []
    hold_values = []
    impermanent_losses = []
    
    for p in prices:
        # A. Value of the LP Position
        val_lp = calculate_lp_value(p, L, MIN_RANGE, MAX_RANGE)
        lp_values.append(val_lp)
        
        # B. Value of the HODL Position
        val_hold = (initial_eth * p) + initial_usdc
        hold_values.append(val_hold)
        
        # C. Impermanent Loss Calculation
        il = (val_lp - val_hold) / val_hold
        impermanent_losses.append(il * 100)
        
    # 3. ENHANCED VISUALIZATION
    fig = plt.figure(figsize=(16, 10))
    fig.patch.set_facecolor('#0a0e27')
    
    # Define color scheme
    bg_color = '#0a0e27'
    grid_color = '#1e2847'
    lp_color = '#00ff88'
    hold_color = '#ff6b6b'
    range_color = '#ffd93d'
    il_color = '#6bcfff'
    
    # Chart 1: Portfolio Value Comparison
    ax1 = plt.subplot(2, 2, (1, 2))
    ax1.set_facecolor('#141b3d')
    
    # Highlight the active range
    ax1.axvspan(MIN_RANGE, MAX_RANGE, alpha=0.15, color=range_color, label='Active Range')
    
    # Plot main lines with enhanced styling
    ax1.plot(prices, lp_values, label='Uniswap V3 Position', 
             color=lp_color, linewidth=3, zorder=3)
    ax1.plot(prices, hold_values, label=f'HODL Baseline ({eth_pct:.1f}% ETH)', 
             color=hold_color, linewidth=2.5, linestyle='--', alpha=0.8, zorder=2)
    
    # Entry price marker
    ax1.axvline(ENTRY_PRICE, color='white', linestyle=':', 
                linewidth=2, alpha=0.6, label=f'Entry: ${ENTRY_PRICE}')
    
    # Range boundaries
    ax1.axvline(MIN_RANGE, color=range_color, linestyle='-', 
                linewidth=2, alpha=0.8, label=f'Range: ${MIN_RANGE}-${MAX_RANGE}')
    ax1.axvline(MAX_RANGE, color=range_color, linestyle='-', 
                linewidth=2, alpha=0.8)
    
    # Add value annotations at key points
    entry_idx = np.argmin(np.abs(prices - ENTRY_PRICE))
    ax1.scatter([ENTRY_PRICE], [lp_values[entry_idx]], 
                s=150, color=lp_color, zorder=4, edgecolor='white', linewidth=2)
    
    ax1.set_title('Portfolio Value: Uniswap V3 LP vs HODL Strategy (CORRECTED)', 
                  fontsize=16, fontweight='bold', color='white', pad=20)
    ax1.set_ylabel('Portfolio Value (USD)', fontsize=13, fontweight='bold', color='white')
    ax1.set_xlabel('ETH Price (USD)', fontsize=13, fontweight='bold', color='white')
    ax1.legend(loc='upper left', fontsize=11, framealpha=0.9)
    ax1.grid(True, alpha=0.15, color=grid_color, linewidth=1.5)
    ax1.tick_params(colors='white', labelsize=11)
    
    # Format y-axis as currency
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # Chart 2: Impermanent Loss
    ax2 = plt.subplot(2, 2, 3)
    ax2.set_facecolor('#141b3d')
    
    # Color IL based on positive/negative
    ax2.fill_between(prices, impermanent_losses, 0, 
                      color=il_color, alpha=0.4)
    ax2.plot(prices, impermanent_losses, color=il_color, linewidth=3)
    
    # Highlight the active range
    ax2.axvspan(MIN_RANGE, MAX_RANGE, alpha=0.15, color=range_color)
    ax2.axvline(ENTRY_PRICE, color='white', linestyle=':', linewidth=2, alpha=0.6)
    ax2.axhline(0, color='white', linestyle='-', linewidth=1.5, alpha=0.5)
    
    # Mark 0% IL at entry
    ax2.scatter([ENTRY_PRICE], [0], s=150, color='white', 
                zorder=4, edgecolor=il_color, linewidth=2)
    ax2.annotate('0.00% IL at Entry', 
                xy=(ENTRY_PRICE, 0), xytext=(ENTRY_PRICE * 1.1, -1),
                fontsize=10, color='white',
                arrowprops=dict(arrowstyle='->', color='white', lw=1.5))
    
    ax2.set_title('Impermanent Loss vs HODL (Corrected Baseline)', 
                  fontsize=14, fontweight='bold', color='white', pad=15)
    ax2.set_ylabel('IL (%)', fontsize=12, fontweight='bold', color='white')
    ax2.set_xlabel('ETH Price (USD)', fontsize=12, fontweight='bold', color='white')
    ax2.grid(True, alpha=0.15, color=grid_color, linewidth=1.5)
    ax2.tick_params(colors='white', labelsize=10)
    ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # Chart 3: Key Metrics Summary
    ax3 = plt.subplot(2, 2, 4)
    ax3.set_facecolor('#141b3d')
    ax3.axis('off')
    
    # Calculate key metrics
    max_il = min(impermanent_losses)
    max_il_price = prices[np.argmin(impermanent_losses)]
    il_at_entry = impermanent_losses[entry_idx]
    
    # Create metrics display
    metrics_text = f"""
    KEY METRICS (CORRECTED MODEL)
    {'='*42}
    
    Initial Investment:     ${INVESTMENT:,.0f}
    Entry Price:           ${ENTRY_PRICE:,.0f}
    Position Range:        ${MIN_RANGE:,.0f} - ${MAX_RANGE:,.0f}
    Liquidity (L):         {int(L):,}
    
    EXACT BASKET DEPLOYED
    {'='*42}
    
    ETH Deposited:         {initial_eth:.4f} ETH
    USDC Deposited:        ${initial_usdc:,.2f}
    
    Split Ratio:           {eth_pct:.1f}% ETH / {usdc_pct:.1f}% USDC
    (Not 50/50 - calculated by pool geometry!)
    
    RISK ANALYSIS
    {'='*42}
    
    IL at Entry:           {il_at_entry:.4f}% ✓ CORRECT
    Max IL in Range:       {max_il:.2f}%
    Occurs at Price:       ${max_il_price:,.0f}
    
    Range Width:           {((MAX_RANGE-MIN_RANGE)/ENTRY_PRICE*100):.1f}% of entry
    Capital Efficiency:    {(100 / ((MAX_RANGE-MIN_RANGE)/ENTRY_PRICE*100)):.1f}x vs full range
    
    ⚠️  Price moves outside range = 0 fees earned
    ✓  Tighter range = higher fee APY when in range
    ✓  HODL baseline matches actual pool deposit
    """
    
    ax3.text(0.05, 0.95, metrics_text, 
             transform=ax3.transAxes,
             fontsize=10.5,
             verticalalignment='top',
             fontfamily='monospace',
             color='white',
             bbox=dict(boxstyle='round', facecolor='#1e2847', alpha=0.8, pad=1))
    
    plt.tight_layout()
    plt.show()
    
    # Print detailed analysis
    print(f"\n--- DETAILED ANALYSIS ---")
    print(f"IL at Entry Price: {il_at_entry:.4f}% (Should be ~0.00%)")
    print(f"Maximum IL: {max_il:.2f}% at ${max_il_price:,.0f}")
    print(f"Range Concentration: {((MAX_RANGE-MIN_RANGE)/ENTRY_PRICE*100):.1f}% of entry price")

if __name__ == "__main__":
    simulate_curve()