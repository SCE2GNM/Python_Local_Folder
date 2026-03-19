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
    # Formula derived from Uniswap Whitepaper for L given amount0 (ETH)
    # L = amount0 * (sqrt(P) * sqrt(Pb)) / (sqrt(Pb) - sqrt(P))
    L_test = (1.0 * sqrt_P * sqrt_Pb) / (sqrt_Pb - sqrt_P)
    
    # 2. Calculate how much USDC corresponds to that L_test
    # Formula for amount1 (USDC) given L
    # amount1 = L * (sqrt(P) - sqrt(Pa))
    usdc_test = L_test * (sqrt_P - sqrt_Pa)
    
    # 3. Calculate the total dollar value of this test bundle
    # (1 ETH * Price) + USDC
    value_test = (1.0 * price) + usdc_test
    
    # 4. Calculate the Scaling Factor
    # How many times does our test bundle fit into our $10,000 investment?
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
        # Formula: amount_eth = L * (sqrt(Pb) - sqrt(Pa)) / (sqrt(Pa) * sqrt(Pb))
        amount_eth = L * (sqrt_Pb - sqrt_Pa) / (sqrt_Pa * sqrt_Pb)
        return amount_eth * price
        
    elif price >= Pb:
        # Case B: Price Mooned above Range -> We hold 100% USDC
        # Formula: amount_usdc = L * (sqrt(Pb) - sqrt(Pa))
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
    
    print(f"Entry Price: ${ENTRY_PRICE}")
    print(f"Invested:    ${(initial_eth * ENTRY_PRICE) + initial_usdc:.2f}")
    print(f"Basket:      {initial_eth:.4f} ETH + ${initial_usdc:.2f} USDC")
    
    # 2. SIMULATION LOOP
    prices = np.linspace(ENTRY_PRICE * 0.5, ENTRY_PRICE * 1.5, 100)
    lp_values = []
    hold_values = []
    impermanent_losses = []
    
    for p in prices:
        # A. Value of the LP Position (The Robot)
        val_lp = calculate_lp_value(p, L, MIN_RANGE, MAX_RANGE)
        lp_values.append(val_lp)
        
        # B. Value of the HODL Position (The Benchmark)
        # We assume we simply held the EXACT basket calculated in Step 1
        val_hold = (initial_eth * p) + initial_usdc
        hold_values.append(val_hold)
        
        # C. Impermanent Loss Calculation
        # (LP_Value - HODL_Value) / HODL_Value
        il = (val_lp - val_hold) / val_hold
        impermanent_losses.append(il * 100)
        
    # 3. VISUALIZATION
    plt.figure(figsize=(12, 10))
    plt.style.use('dark_background')
    
    # Chart 1: Value Comparison
    plt.subplot(2, 1, 1)
    plt.plot(prices, lp_values, label='Uniswap V3 LP', color='lime')
    plt.plot(prices, hold_values, label='HODL Benchmark', color='gray', linestyle='--')
    plt.axvline(ENTRY_PRICE, color='white', linestyle=':', label='Entry Price')
    plt.title(f'LP vs HODL (Corrected Baseline)')
    plt.ylabel('Portfolio Value ($)')
    plt.legend()
    plt.grid(True, alpha=0.2)
    
    # Chart 2: Impermanent Loss
    plt.subplot(2, 1, 2)
    plt.plot(prices, impermanent_losses, color='orange')
    plt.fill_between(prices, impermanent_losses, 0, color='orange', alpha=0.3)
    plt.axvline(ENTRY_PRICE, color='white', linestyle=':')
    plt.title('Impermanent Loss (%)')
    plt.xlabel('ETH Price')
    plt.ylabel('Loss vs HODL (%)')
    plt.grid(True, alpha=0.2)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    simulate_curve()