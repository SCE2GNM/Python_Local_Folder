"""
PHASE 3: DEFI MATH
STRATEGY: Uniswap V3 Liquidity Provisioning
OBJECTIVE: Calculate PnL (Fees - Impermanent Loss) for a concentrated position.
MATH CORE:
Uniswap V3 uses the curve: (x + L/sqrt(Pb))(y + L*sqrt(Pa)) = L^2
Where L = Liquidity, P = Price.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# --- SETTINGS ---
ENTRY_PRICE = 3000   # ETH Price when you deposit
MIN_RANGE = 2500     # Lower bound of your range
MAX_RANGE = 3500     # Upper bound of your range
INVESTMENT = 10000   # Total USD Value to deposit

def calculate_liquidity(P, Pa, Pb, investment):
    """
    Calculates 'Liquidity Units' (L).
    Simplified estimation assuming optimal asset split.
    """
    sqrt_P = np.sqrt(P)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    amount_usd = investment / 2
    amount_eth = (investment / 2) / P
    
    L_eth = amount_eth * (sqrt_P * sqrt_Pb) / (sqrt_Pb - sqrt_P)
    L_usdc = amount_usd / (sqrt_P - sqrt_Pa)
    
    L = min(L_eth, L_usdc)
    return L

def calculate_value_at_price(price, L, Pa, Pb):
    """
    Calculates value of your LP position at a future price.
    """
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    if price <= Pa:
        amount_eth = L * (sqrt_Pb - sqrt_Pa) / (sqrt_Pa * sqrt_Pb)
        return amount_eth * price
    elif price >= Pb:
        amount_usdc = L * (sqrt_Pb - sqrt_Pa)
        return amount_usdc
    else:
        amount_eth = L * (sqrt_Pb - sqrt_P) / (sqrt_P * sqrt_Pb)
        amount_usdc = L * (sqrt_P - sqrt_Pa)
        return (amount_eth * price) + amount_usdc

def simulate_curve():
    # 1. Calculate Initial State
    L = calculate_liquidity(ENTRY_PRICE, MIN_RANGE, MAX_RANGE, INVESTMENT)
    print(f"--- UNISWAP V3 SIMULATION ---")
    print(f"Entry Price: ${ENTRY_PRICE}")
    print(f"Range:       ${MIN_RANGE} - ${MAX_RANGE}")
    print(f"Liquidity (L): {int(L)}")
    
    # 2. Simulate Price Moves (-50% to +50%)
    prices = np.linspace(ENTRY_PRICE * 0.5, ENTRY_PRICE * 1.5, 200)
    lp_values = []
    hold_values = []
    impermanent_losses = []
    
    initial_eth = (INVESTMENT / 2) / ENTRY_PRICE
    initial_usdc = INVESTMENT / 2
    
    for p in prices:
        val_lp = calculate_value_at_price(p, L, MIN_RANGE, MAX_RANGE)
        lp_values.append(val_lp)
        
        val_hold = (initial_eth * p) + initial_usdc
        hold_values.append(val_hold)
        
        il = (val_lp - val_hold) / val_hold
        impermanent_losses.append(il * 100)
    
    # 3. Enhanced Visualization
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
    ax1.plot(prices, hold_values, label='HODL 50/50', 
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
    
    ax1.set_title('Portfolio Value: Uniswap V3 LP vs HODL Strategy', 
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
    colors = [il_color if il < 0 else '#ff4757' for il in impermanent_losses]
    ax2.fill_between(prices, impermanent_losses, 0, 
                      color=il_color, alpha=0.4)
    ax2.plot(prices, impermanent_losses, color=il_color, linewidth=3)
    
    # Highlight the active range
    ax2.axvspan(MIN_RANGE, MAX_RANGE, alpha=0.15, color=range_color)
    ax2.axvline(ENTRY_PRICE, color='white', linestyle=':', linewidth=2, alpha=0.6)
    ax2.axhline(0, color='white', linestyle='-', linewidth=1.5, alpha=0.5)
    
    ax2.set_title('Impermanent Loss vs HODL', 
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
    current_il = impermanent_losses[entry_idx]
    
    # Create metrics display
    metrics_text = f"""
    KEY METRICS
    {'='*40}
    
    Initial Investment:     ${INVESTMENT:,.0f}
    Entry Price:           ${ENTRY_PRICE:,.0f}
    Position Range:        ${MIN_RANGE:,.0f} - ${MAX_RANGE:,.0f}
    Liquidity (L):         {int(L):,}
    
    RISK ANALYSIS
    {'='*40}
    
    Max IL in Range:       {max_il:.2f}%
    Occurs at Price:       ${max_il_price:,.0f}
    
    Range Width:           {((MAX_RANGE-MIN_RANGE)/ENTRY_PRICE*100):.1f}% of entry
    Capital Efficiency:    {(100 / ((MAX_RANGE-MIN_RANGE)/ENTRY_PRICE*100)):.1f}x vs full range
    
    ⚠️  Price moves outside range = 0 fees earned
    ✓  Tighter range = higher fee APY when in range
    """
    
    ax3.text(0.05, 0.95, metrics_text, 
             transform=ax3.transAxes,
             fontsize=11,
             verticalalignment='top',
             fontfamily='monospace',
             color='white',
             bbox=dict(boxstyle='round', facecolor='#1e2847', alpha=0.8, pad=1))
    
    plt.tight_layout()
    plt.show()
    
    # Print detailed analysis
    print(f"\n--- DETAILED ANALYSIS ---")
    print(f"Maximum IL: {max_il:.2f}% at ${max_il_price:,.0f}")
    print(f"IL at Entry: {current_il:.2f}%")
    print(f"Range Concentration: {((MAX_RANGE-MIN_RANGE)/ENTRY_PRICE*100):.1f}% of entry price")

if __name__ == "__main__":
    simulate_curve()