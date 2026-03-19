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
    
    # Simplified approximation for "Full Range" deposit within bounds
    # We assume 50/50 split value at entry for simplicity in this model
    amount_usd = investment / 2
    amount_eth = (investment / 2) / P
    
    # Calculate L based on the limiting asset
    # These formulas are derived from the Uniswap Whitepaper
    L_eth = amount_eth * (sqrt_P * sqrt_Pb) / (sqrt_Pb - sqrt_P)
    L_usdc = amount_usd / (sqrt_P - sqrt_Pa)
    
    # Actual L is the minimum of what your two assets allow
    L = min(L_eth, L_usdc)
    return L

def calculate_value_at_price(price, L, Pa, Pb):
    """
    Calculates value of your LP position at a future price.
    """
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    # Case 1: Price Below Range (You hold 100% ETH)
    if price <= Pa:
        amount_eth = L * (sqrt_Pb - sqrt_Pa) / (sqrt_Pa * sqrt_Pb)
        return amount_eth * price
        
    # Case 2: Price Above Range (You hold 100% USDC)
    elif price >= Pb:
        amount_usdc = L * (sqrt_Pb - sqrt_Pa)
        return amount_usdc
        
    # Case 3: In Range (You hold Mix)
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
    prices = np.linspace(ENTRY_PRICE * 0.5, ENTRY_PRICE * 1.5, 100)
    
    lp_values = []
    hold_values = []
    impermanent_losses = []
    
    # Initial amount of ETH and USDC if just held (HODL)
    # Simplified: Assuming 50/50 split at entry
    initial_eth = (INVESTMENT / 2) / ENTRY_PRICE
    initial_usdc = INVESTMENT / 2
    
    for p in prices:
        # Value if LP
        val_lp = calculate_value_at_price(p, L, MIN_RANGE, MAX_RANGE)
        lp_values.append(val_lp)
        
        # Value if HODL
        val_hold = (initial_eth * p) + initial_usdc
        hold_values.append(val_hold)
        
        # Impermanent Loss %
        il = (val_lp - val_hold) / val_hold
        impermanent_losses.append(il * 100)
        
    # 3. Visualize
    plt.figure(figsize=(12, 10))
    plt.style.use('dark_background')
    
    # Chart 1: LP Value vs HODL Value
    plt.subplot(2, 1, 1)
    plt.plot(prices, lp_values, label='Uniswap V3 Position', color='lime')
    plt.plot(prices, hold_values, label='HODL 50/50', color='gray', linestyle='--')
    plt.axvline(MIN_RANGE, color='red', linestyle=':', label='Min Range')
    plt.axvline(MAX_RANGE, color='red', linestyle=':', label='Max Range')
    plt.title(f'Liquidity Provision vs Holding (Entry: ${ENTRY_PRICE})')
    plt.ylabel('Portfolio Value ($)')
    plt.legend()
    plt.grid(True, alpha=0.2)
    
    # Chart 2: Impermanent Loss
    plt.subplot(2, 1, 2)
    plt.plot(prices, impermanent_losses, color='orange')
    plt.fill_between(prices, impermanent_losses, 0, color='orange', alpha=0.3)
    plt.title('Impermanent Loss (%)')
    plt.ylabel('Loss vs HODL (%)')
    plt.xlabel('ETH Price ($)')
    plt.grid(True, alpha=0.2)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    simulate_curve()