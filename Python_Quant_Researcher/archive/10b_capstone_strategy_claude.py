"""
PHASE 4: CAPSTONE STRATEGY (Regime Switching)
FILENAME: 10_capstone_strategy.py

OBJECTIVE: 
Simulate a dynamic portfolio that rotates capital between 3 states based on market conditions.

THE STRATEGY LOGIC:
1. CALCULATE REGIME (The "Weather Report"):
   - We use ADX (Average Directional Index) to measure Trend Strength.
   - If ADX < 25: The market is "Choppy/Calm".
   - If ADX > 25: The market is "Trending/Volatile".

2. STATE SELECTION (The "Vehicle"):
   A. IF CHOP (ADX < 25):
      - Deploy Capital into Uniswap V3 (±20% Range).
      - Goal: Farm fees while price goes sideways.
      
   B. IF TREND (ADX > 25):
      - We need to survive the volatility. Check Direction using SMA 50.
      - IF Price > SMA 50 (Uptrend): BUY ETH (HODL). Catch the pump.
      - IF Price < SMA 50 (Downtrend): SELL to USDC (CASH). Avoid the crash.

3. FRICTION (The "Real World"):
   - Every time we switch strategies, we pay:
     a) Swap Fees (0.1% to convert ETH<->USDC).
     b) Gas Fees ($10 fixed cost).
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- 1. GLOBAL SETTINGS ---
SYMBOL = "ETH-USD"
START_DATE = "2020-01-01" 
END_DATE = "2024-01-01"
INITIAL_CAPITAL = 10000

# Strategy Parameters
ADX_PERIOD = 14
ADX_THRESHOLD = 25      # Below = Chop, Above = Trend
SMA_PERIOD = 50         # Direction filter
UNISWAP_RANGE = 0.20    # ±20% Liquidity Range
FEE_TIER = 0.003        # 0.3% Pool
DAILY_VOL_TO_TVL = 0.20 # Estimated Volume Velocity

# Friction Costs
GAS_FEE = 10.0          # $10 per switch
SWAP_FEE = 0.001        # 0.1% slippage/fee on rotation

# --- 2. MATH HELPERS (Uniswap & Indicators) ---

def calculate_liquidity_and_amounts(price, Pa, Pb, max_usd):
    """
    Solves for Liquidity (L) given a dollar investment amount.
    """
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    # Standard V3 Formulas
    L_test = (1.0 * sqrt_P * sqrt_Pb) / (sqrt_Pb - sqrt_P)
    usdc_test = L_test * (sqrt_P - sqrt_Pa)
    value_test = (1.0 * price) + usdc_test
    
    scale = max_usd / value_test
    return L_test * scale

def calculate_lp_value(price, L, Pa, Pb):
    """
    Returns the current Asset Value of the LP position.
    """
    sqrt_P = np.sqrt(price)
    sqrt_Pa = np.sqrt(Pa)
    sqrt_Pb = np.sqrt(Pb)
    
    if price <= Pa: return L * (sqrt_Pb - sqrt_Pa) / (sqrt_Pa * sqrt_Pb) * price
    elif price >= Pb: return L * (sqrt_Pb - sqrt_Pa)
    else:
        eth = L * (sqrt_Pb - sqrt_P) / (sqrt_P * sqrt_Pb)
        usdc = L * (sqrt_P - sqrt_Pa)
        return (eth * price) + usdc

def wilders_smoothing(series, period):
    return series.ewm(alpha=1/period, adjust=False).mean()

def add_indicators(df):
    data = df.copy()
    
    # 1. Simple Moving Average (Direction)
    data['SMA'] = data['Close'].rolling(window=SMA_PERIOD).mean()
    
    # 2. ADX (Trend Strength) - Calculated manually
    data['H-L'] = data['High'] - data['Low']
    data['H-PC'] = abs(data['High'] - data['Close'].shift(1))
    data['L-PC'] = abs(data['Low'] - data['Close'].shift(1))
    data['TR'] = data[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    data['+DM'] = np.where((data['High']-data['High'].shift(1))>(data['Low'].shift(1)-data['Low']), np.maximum(data['High']-data['High'].shift(1),0), 0)
    data['-DM'] = np.where((data['Low'].shift(1)-data['Low'])>(data['High']-data['High'].shift(1)), np.maximum(data['Low'].shift(1)-data['Low'],0), 0)
    
    data['TR_Smooth'] = wilders_smoothing(data['TR'], ADX_PERIOD)
    data['+DM_Smooth'] = wilders_smoothing(data['+DM'], ADX_PERIOD)
    data['-DM_Smooth'] = wilders_smoothing(data['-DM'], ADX_PERIOD)
    
    data['+DI'] = 100 * (data['+DM_Smooth'] / data['TR_Smooth'])
    data['-DI'] = 100 * (data['-DM_Smooth'] / data['TR_Smooth'])
    data['DX'] = 100 * abs(data['+DI'] - data['-DI']) / (data['+DI'] + data['-DI'])
    data['ADX'] = wilders_smoothing(data['DX'], ADX_PERIOD)
    
    return data.dropna()

# --- 3. THE BACKTEST ENGINE ---

def run_capstone_strategy(df):
    print("--- STARTING CAPSTONE SIMULATION ---")
    
    # Simulation State Variables
    cash = INITIAL_CAPITAL
    current_state = "CASH" # Options: "CASH", "HODL", "UNISWAP"
    
    # Uniswap Specific State
    uni_L = 0
    uni_min = 0
    uni_max = 0
    uni_fees_collected = 0
    
    # Tracking
    equity_curve = []
    state_history = []
    
    # Loop through every single day
    for i in range(len(df)):
        today = df.iloc[i]
        price = today['Close']
        adx = today['ADX']
        sma = today['SMA']
        
        # -----------------------------
        # 1. DETERMINE DESIRED REGIME
        # -----------------------------
        target_state = "CASH"
        
        if adx < ADX_THRESHOLD:
            # Low Volatility -> Market Neutral Strategy
            target_state = "UNISWAP"
        else:
            # High Volatility -> Directional Strategy
            if price > sma:
                target_state = "HODL" # Trend Up
            else:
                target_state = "CASH" # Trend Down (Safety)
                
        # -----------------------------
        # 2. HANDLE SWITCHING (Friction)
        # -----------------------------
        if target_state != current_state:
            # A. LIQUIDATE OLD POSITION
            if current_state == "HODL":
                # Sell ETH -> Cash
                cash = cash * (1 - SWAP_FEE)
            elif current_state == "UNISWAP":
                # Withdraw Liquidity -> Cash
                lp_value = calculate_lp_value(price, uni_L, uni_min, uni_max)
                total_val = lp_value + uni_fees_collected
                cash = total_val - GAS_FEE # Pay Gas to exit
                uni_fees_collected = 0     # Reset fees bucket
            
            # Pay Gas for the switch logic
            cash -= GAS_FEE
            
            # B. ENTER NEW POSITION
            if target_state == "HODL":
                # Buy ETH (Cash value tracks ETH price changes relatively)
                # In simulation, we just mark the cash as "exposed"
                cash = cash * (1 - SWAP_FEE)
                
            elif target_state == "UNISWAP":
                # Deposit into Pool
                uni_min = price * (1 - UNISWAP_RANGE)
                uni_max = price * (1 + UNISWAP_RANGE)
                uni_L = calculate_liquidity_and_amounts(price, uni_min, uni_max, cash)
                uni_fees_collected = 0
                cash -= GAS_FEE # Pay Gas to deposit
            
            current_state = target_state
            
        # -----------------------------
        # 3. UPDATE PORTFOLIO VALUE
        # -----------------------------
        daily_equity = 0
        
        if current_state == "CASH":
            # Value is just Cash (Stable)
            daily_equity = cash
            
        elif current_state == "HODL":
            # Value fluctuates with ETH % change
            # (Simplified: calculating daily return)
            if i > 0:
                prev_price = df.iloc[i-1]['Close']
                ret = (price - prev_price) / prev_price
                cash = cash * (1 + ret)
            daily_equity = cash
            
        elif current_state == "UNISWAP":
            # 1. Check Range for Fees
            if uni_min <= price <= uni_max:
                # Earn Fees
                efficiency = 3.0 * (0.20 / UNISWAP_RANGE)
                daily_yield = DAILY_VOL_TO_TVL * FEE_TIER * efficiency
                # We earn fees based on the Initial Capital deployed
                # (Approximate for simulation speed)
                lp_asset_value = calculate_lp_value(price, uni_L, uni_min, uni_max)
                fees = lp_asset_value * daily_yield 
                uni_fees_collected += fees
            
            # 2. Mark to Market
            asset_value = calculate_lp_value(price, uni_L, uni_min, uni_max)
            daily_equity = asset_value + uni_fees_collected

        equity_curve.append(daily_equity)
        state_history.append(current_state)

    # Attach to DataFrame
    df['Strategy_Equity'] = equity_curve
    df['Regime'] = state_history
    return df

# --- 4. ENHANCED VISUALIZATION ---
def plot_capstone(df):
    fig = plt.figure(figsize=(16, 14))
    plt.style.use('dark_background')
    
    # Calculate metrics for all plots
    initial_price = df['Close'].iloc[0]
    hodl_equity = df['Close'] / initial_price * INITIAL_CAPITAL
    
    # 1. DUAL-AXIS EQUITY CURVE WITH RELATIVE PERFORMANCE
    ax1 = plt.subplot(4, 2, (1, 2))
    
    line1 = ax1.plot(df.index, df['Strategy_Equity'], color='#00ff41', linewidth=2, label='Regime Switching Strategy', zorder=3)
    line2 = ax1.plot(df.index, hodl_equity, color='#ff6b35', linestyle='--', linewidth=1.5, label='Buy & Hold ETH', alpha=0.8, zorder=2)
    
    ax1.set_ylabel('Portfolio Value ($)', fontsize=11, color='white')
    ax1.set_title('Capstone Strategy Performance vs Buy & Hold', fontsize=14, fontweight='bold', pad=15)
    ax1.set_yscale('log')
    ax1.grid(True, alpha=0.2, linestyle='--')
    
    # Add relative performance on secondary axis
    ax1b = ax1.twinx()
    relative_perf = ((df['Strategy_Equity'] - hodl_equity) / hodl_equity) * 100
    line3 = ax1b.plot(df.index, relative_perf, color='#ffd700', linewidth=1, alpha=0.6, label='Relative Performance (%)', zorder=1)
    ax1b.axhline(y=0, color='white', linestyle=':', linewidth=0.8, alpha=0.5)
    ax1b.set_ylabel('Outperformance (%)', fontsize=11, color='#ffd700')
    ax1b.tick_params(axis='y', labelcolor='#ffd700')
    
    # Combine legends
    lines = line1 + line2 + line3
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', framealpha=0.9)
    
    # 2. PRICE WITH REGIME OVERLAYS AND INDICATORS
    ax2 = plt.subplot(4, 2, (3, 4), sharex=ax1)
    
    # Plot price with SMA
    ax2.plot(df.index, df['Close'], color='white', linewidth=1.5, label='ETH Price', zorder=2)
    ax2.plot(df.index, df['SMA'], color='orange', linewidth=1, linestyle='--', alpha=0.7, label=f'SMA {SMA_PERIOD}', zorder=1)
    
    # Regime backgrounds
    for regime, color, alpha, label in [
        ('CASH', '#ff4444', 0.15, 'Cash (Downtrend)'),
        ('HODL', '#44ff44', 0.15, 'HODL (Uptrend)'),
        ('UNISWAP', '#44ddff', 0.15, 'Uniswap LP (Chop)')
    ]:
        mask = df['Regime'] == regime
        if mask.any():
            ax2.fill_between(df.index, df['Close'].min() * 0.95, df['Close'].max() * 1.05, 
                            where=mask, color=color, alpha=alpha, label=label, zorder=0)
    
    ax2.set_ylabel('ETH Price ($)', fontsize=11)
    ax2.set_title('Price Action with Regime Indicators', fontsize=13, fontweight='bold', pad=10)
    ax2.legend(loc='upper left', fontsize=9, framealpha=0.9, ncol=2)
    ax2.grid(True, alpha=0.2, linestyle='--')
    ax2.set_yscale('log')
    
    # 3. ADX TREND STRENGTH INDICATOR
    ax3 = plt.subplot(4, 2, 5, sharex=ax1)
    
    ax3.plot(df.index, df['ADX'], color='#9d4edd', linewidth=1.5, label='ADX (Trend Strength)')
    ax3.axhline(y=ADX_THRESHOLD, color='yellow', linestyle='--', linewidth=1.5, alpha=0.8, label=f'Threshold ({ADX_THRESHOLD})')
    ax3.fill_between(df.index, 0, ADX_THRESHOLD, color='cyan', alpha=0.1, label='Chop Zone')
    ax3.fill_between(df.index, ADX_THRESHOLD, df['ADX'].max(), color='red', alpha=0.1, label='Trend Zone')
    
    ax3.set_ylabel('ADX Value', fontsize=10)
    ax3.set_title('ADX Trend Strength Monitor', fontsize=12, fontweight='bold')
    ax3.legend(loc='upper right', fontsize=8, framealpha=0.9)
    ax3.grid(True, alpha=0.2, linestyle='--')
    ax3.set_ylim(0, df['ADX'].max() * 1.1)
    
    # 4. REGIME ALLOCATION PIE CHART
    ax4 = plt.subplot(4, 2, 6)
    
    regime_counts = df['Regime'].value_counts()
    colors_pie = {'CASH': '#ff4444', 'HODL': '#44ff44', 'UNISWAP': '#44ddff'}
    pie_colors = [colors_pie.get(regime, 'gray') for regime in regime_counts.index]
    
    wedges, texts, autotexts = ax4.pie(regime_counts.values, labels=regime_counts.index, autopct='%1.1f%%',
                                         colors=pie_colors, startangle=90, textprops={'fontsize': 10, 'weight': 'bold'})
    
    for autotext in autotexts:
        autotext.set_color('black')
        autotext.set_fontsize(11)
    
    ax4.set_title('Time Allocation by Regime', fontsize=12, fontweight='bold')
    
    # 5. DRAWDOWN ANALYSIS
    ax5 = plt.subplot(4, 2, 7, sharex=ax1)
    
    running_max = df['Strategy_Equity'].cummax()
    drawdown = (df['Strategy_Equity'] - running_max) / running_max * 100
    
    ax5.plot(df.index, drawdown, color='#ff6b6b', linewidth=1.5, alpha=0.8)
    ax5.fill_between(df.index, drawdown, 0, color='#ff6b6b', alpha=0.3)
    
    max_dd = drawdown.min()
    max_dd_date = drawdown.idxmin()
    ax5.scatter([max_dd_date], [max_dd], color='red', s=100, zorder=5, label=f'Max DD: {max_dd:.2f}%')
    ax5.annotate(f'{max_dd:.1f}%', xy=(max_dd_date, max_dd), xytext=(10, 10), 
                textcoords='offset points', fontsize=9, color='red', weight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='black', alpha=0.7))
    
    ax5.set_ylabel('Drawdown (%)', fontsize=10)
    ax5.set_xlabel('Date', fontsize=10)
    ax5.set_title('Strategy Drawdown Profile', fontsize=12, fontweight='bold')
    ax5.legend(loc='lower right', fontsize=9)
    ax5.grid(True, alpha=0.2, linestyle='--')
    ax5.axhline(y=0, color='white', linestyle='-', linewidth=0.8, alpha=0.3)
    
    # 6. PERFORMANCE METRICS TABLE
    ax6 = plt.subplot(4, 2, 8)
    ax6.axis('off')
    
    # Calculate comprehensive metrics
    final_strategy = df['Strategy_Equity'].iloc[-1]
    final_hodl = hodl_equity.iloc[-1]
    total_return_strat = ((final_strategy - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    total_return_hodl = ((final_hodl - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    
    # Annualized returns
    years = (df.index[-1] - df.index[0]).days / 365.25
    cagr_strat = ((final_strategy / INITIAL_CAPITAL) ** (1/years) - 1) * 100
    cagr_hodl = ((final_hodl / INITIAL_CAPITAL) ** (1/years) - 1) * 100
    
    # Sharpe-like metric (simplified)
    daily_returns = df['Strategy_Equity'].pct_change().dropna()
    sharpe_approx = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0
    
    # Win rate (days with positive returns)
    win_rate = (daily_returns > 0).sum() / len(daily_returns) * 100
    
    max_drawdown = drawdown.min()
    
    metrics_data = [
        ['Metric', 'Strategy', 'Buy & Hold'],
        ['─' * 20, '─' * 12, '─' * 12],
        ['Final Value', f'${final_strategy:,.0f}', f'${final_hodl:,.0f}'],
        ['Total Return', f'{total_return_strat:.1f}%', f'{total_return_hodl:.1f}%'],
        ['CAGR', f'{cagr_strat:.1f}%', f'{cagr_hodl:.1f}%'],
        ['Max Drawdown', f'{max_drawdown:.1f}%', '─'],
        ['Sharpe Ratio', f'{sharpe_approx:.2f}', '─'],
        ['Win Rate', f'{win_rate:.1f}%', '─'],
        ['Total Switches', f'{(df["Regime"] != df["Regime"].shift()).sum()}', '0'],
    ]
    
    table = ax6.table(cellText=metrics_data, cellLoc='left', loc='center',
                     colWidths=[0.45, 0.275, 0.275],
                     bbox=[0, 0, 1, 1])
    
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    
    # Style the table
    for i in range(len(metrics_data)):
        for j in range(3):
            cell = table[(i, j)]
            if i == 0:  # Header
                cell.set_facecolor('#2d2d2d')
                cell.set_text_props(weight='bold', color='#00ff41', fontsize=10)
            elif i == 1:  # Separator
                cell.set_facecolor('#1a1a1a')
                cell.set_text_props(color='gray')
            else:
                cell.set_facecolor('#1a1a1a' if i % 2 == 0 else '#242424')
                if j == 1 and i > 1:  # Strategy column - highlight if better
                    cell.set_text_props(color='#00ff41', weight='bold')
                elif j == 2 and i > 1:  # HODL column
                    cell.set_text_props(color='#ff6b35')
            cell.set_edgecolor('#444444')
            cell.set_linewidth(0.5)
    
    ax6.set_title('Performance Metrics Summary', fontsize=12, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.3, wspace=0.3)
    plt.show()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # 1. ETL
    print(f"Fetching Data for {SYMBOL}...")
    raw_data = yf.download(SYMBOL, start=START_DATE, end=END_DATE, interval="1d", progress=False)
    if isinstance(raw_data.columns, pd.MultiIndex):
        raw_data.columns = raw_data.columns.get_level_values(0)
    
    # 2. Indicators
    processed_data = add_indicators(raw_data[['High', 'Low', 'Close']])
    
    # 3. Backtest
    results = run_capstone_strategy(processed_data)
    
    # 4. Metrics
    final_val = results['Strategy_Equity'].iloc[-1]
    hodl_val = (results['Close'].iloc[-1] / results['Close'].iloc[0]) * INITIAL_CAPITAL
    
    print(f"\n--- CAPSTONE RESULTS ({START_DATE} to {END_DATE}) ---")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Strategy Final:  ${final_val:,.2f}")
    print(f"Buy & Hold Final:${hodl_val:,.2f}")
    print(f"Net Performance: {((final_val - hodl_val)/hodl_val)*100:.2f}% vs Benchmark")
    
    plot_capstone(results)