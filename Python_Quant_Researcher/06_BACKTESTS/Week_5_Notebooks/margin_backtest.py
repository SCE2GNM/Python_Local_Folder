# [MODULE] Margin Trading Backtest
# Week 5 Extension
#
# WHAT THIS SCRIPT DOES:
#   Tests ETH ADX and BTC SMA strategies across leverage levels
#   1.0x to 2.0x (0.05x steps) with realistic margin costs modelled.
#
# MARGIN MODEL:
#   - Isolated margin (each position has its own collateral pool)
#   - Interest: 0.015%/day on borrowed capital (sensitivity: 0.01%, 0.02%)
#   - Stop-loss slippage: 2% below intended stop price
#   - Liquidation: when equity/position falls below 5% maintenance margin
#   - Liquidation fill: liquidation_price × 0.97 (3% slippage)
#   - Safety buffer: flag leverage levels where margin ratio < 25% historically
#
# LEVERAGE DEFINITION:
#   1.0x = no borrowing (normal spot trading, 100% own capital)
#   1.5x = borrow 50% of position value (own 67%, borrow 33%)
#   2.0x = borrow 100% of position value (own 50%, borrow 50%)
#
#   Position size = own_capital × leverage
#   Borrowed amount = position_size - own_capital
#   own_capital = account × position_fraction (Kelly or fixed)
#
# UK RETAIL NOTE:
#   Futures/perpetuals unavailable to UK retail (FCA ban Jan 2021)
#   This backtest models spot margin only

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from ta.trend import ADXIndicator
import os

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

# Interest rate on borrowed capital
DAILY_INTEREST_RATE:    float = 0.00015   # 0.015%/day = ~5.5%/yr
DAILY_INTEREST_LOW:     float = 0.00010   # 0.010%/day sensitivity
DAILY_INTEREST_HIGH:    float = 0.00020   # 0.020%/day sensitivity

# Margin parameters
MAINTENANCE_MARGIN:     float = 0.05      # 5% — Binance minimum
SAFETY_BUFFER_MARGIN:   float = 0.25      # 25% — our operational minimum
STOP_SLIPPAGE:          float = 0.02      # 2% below stop price
LIQ_SLIPPAGE:           float = 0.03      # 3% below liquidation price

# Strategy parameters
ETH_ADX_STOP:           float = 0.05      # 5% per-trade stop
BTC_SMA_PERIOD:         int   = 125

# Own-capital fraction per trade (Kelly/selected — not leverage)
# Leverage multiplies this position
ETH_OWN_FRACTION:       float = 0.1241    # 12.41% of account per trade
BTC_OWN_FRACTION:       float = 0.25      # 25% of account per trade

INITIAL_CAPITAL:        float = 1000.0

# Leverage grid
LEVERAGE_MIN:           float = 1.0
LEVERAGE_MAX:           float = 2.0
LEVERAGE_STEP:          float = 0.05


# ---------------------------------------------------------------------------
# [FUNCTION] calculate_liquidation_price
# ---------------------------------------------------------------------------

def calculate_liquidation_price(
    entry_price:    float,
    leverage:       float,
    maintenance:    float = MAINTENANCE_MARGIN,
) -> float:
    """
    [FUNCTION] Calculate liquidation price for an isolated margin position.

    For a long position with isolated margin:
      Liquidation when: equity / position_value = maintenance_margin
      equity = initial_margin - unrealised_loss
      initial_margin = position_value / leverage
      unrealised_loss = position_value × (entry_price - current_price) / entry_price

    Solving for current_price:
      liq_price = entry_price × (1 - (1/leverage) + maintenance/leverage)
      Simplified: liq_price = entry_price × (1 - (1 - maintenance) / leverage)

    Args:
        entry_price : trade entry price
        leverage    : leverage multiplier (e.g. 1.5)
        maintenance : maintenance margin ratio (default 5%)

    Returns:
        float liquidation price
    """
    liq_price = entry_price * (1 - (1 - maintenance) / leverage)
    return liq_price


# ---------------------------------------------------------------------------
# [FUNCTION] calculate_margin_ratio
# ---------------------------------------------------------------------------

def calculate_margin_ratio(
    entry_price:    float,
    current_price:  float,
    leverage:       float,
) -> float:
    """
    [FUNCTION] Calculate current margin ratio for an open position.

    margin_ratio = equity / position_value
    equity = initial_margin + unrealised_pnl
    initial_margin = position_value / leverage
    unrealised_pnl = (current_price - entry_price) / entry_price × position_value

    Args:
        entry_price   : price when trade was entered
        current_price : current market price
        leverage      : leverage multiplier

    Returns:
        float margin ratio (1.0 = 100%, 0.05 = 5% = liquidation threshold)
    """
    price_change    = (current_price - entry_price) / entry_price
    initial_margin  = 1.0 / leverage
    equity_ratio    = initial_margin + price_change
    return equity_ratio


# ---------------------------------------------------------------------------
# [FUNCTION] run_margin_backtest
# ---------------------------------------------------------------------------

def run_margin_backtest(
    df:            pd.DataFrame,
    trade_returns: list,          # list of (return, hold_days, entry_price, low_prices)
    leverage:      float,
    own_fraction:  float,
    stop_pct:      float,
    daily_rate:    float = DAILY_INTEREST_RATE,
    label:         str   = '',
) -> dict:
    """
    [FUNCTION] Simulate one strategy at one leverage level with full margin model.

    For each trade:
      1. Calculate position size = account × own_fraction × leverage
      2. Calculate borrowed amount = position_size - (account × own_fraction)
      3. Calculate interest = borrowed × daily_rate × hold_days
      4. Check if liquidation occurred during trade (using daily lows)
      5. Apply stop-loss slippage if stop triggered
      6. Calculate net PnL = gross_pnl - interest_cost

    Args:
        df            : OHLCV DataFrame (for price data)
        trade_returns : list of trade dicts with entry/exit data
        leverage      : leverage multiplier (1.0 = no borrowing)
        own_fraction  : fraction of account used as own capital per trade
        stop_pct      : stop-loss distance from entry
        daily_rate    : daily interest rate on borrowed capital
        label         : display label

    Returns:
        dict with equity curve, metrics, margin ratio history
    """

    account          = INITIAL_CAPITAL
    equity_history   = [account]
    margin_ratios    = []      # minimum margin ratio per trade
    interest_paid    = 0.0     # cumulative interest
    liquidations     = 0       # number of liquidation events
    effective_returns = []     # actual returns after all costs

    for trade in trade_returns:
        gross_return = trade['return']
        hold_days    = trade['hold_days']
        entry_price  = trade['entry_price']
        daily_lows   = trade['daily_lows']   # list of daily lows during hold

        # --- Position sizing ---
        own_capital     = account * own_fraction
        position_size   = own_capital * leverage
        borrowed        = position_size - own_capital   # 0 if leverage=1.0

        # --- Interest cost ---
        interest        = borrowed * daily_rate * hold_days
        interest_paid  += interest

        # --- Liquidation price ---
        liq_price       = calculate_liquidation_price(
            entry_price, leverage
        ) if leverage > 1.0 else 0.0

        # --- Stop price (with slippage) ---
        intended_stop   = entry_price * (1 - stop_pct)
        actual_stop     = intended_stop * (1 - STOP_SLIPPAGE)

        # --- Check if liquidation occurred during trade ---
        liquidated      = False
        worst_margin    = 1.0

        if leverage > 1.0:
            for daily_low in daily_lows:
                margin_r = calculate_margin_ratio(
                    entry_price, daily_low, leverage
                )
                worst_margin = min(worst_margin, margin_r)

                if daily_low <= liq_price:
                    # Liquidation triggered
                    liq_fill_price = liq_price * (1 - LIQ_SLIPPAGE)
                    gross_return   = (liq_fill_price - entry_price) / entry_price
                    liquidated     = True
                    liquidations  += 1
                    break

        margin_ratios.append(worst_margin)

        # --- Apply stop slippage to stop-loss exits ---
        if not liquidated and gross_return <= -stop_pct:
            # Stop was triggered — apply slippage
            # Adjust return to reflect actual_stop fill instead of intended_stop
            slippage_adjustment = -STOP_SLIPPAGE * stop_pct
            gross_return        = gross_return + slippage_adjustment

        # --- Calculate net PnL ---
        gross_pnl    = own_capital * leverage * gross_return
        net_pnl      = gross_pnl - interest
        account      = max(account + net_pnl, 1.0)

        effective_return = net_pnl / (own_capital * leverage) if own_capital > 0 else 0
        effective_returns.append(effective_return)
        equity_history.append(account)

    equity     = np.array(equity_history)
    years      = sum(t['hold_days'] for t in trade_returns) / 365.25
    # Use actual backtest years not just hold days
    total_years = 8.3  # fixed backtest period

    # Metrics from equity curve
    daily_like_returns = np.diff(equity) / equity[:-1]
    total_return       = equity[-1] / equity[0] - 1
    annual_return      = (1 + total_return) ** (1 / total_years) - 1

    peak        = np.maximum.accumulate(equity)
    drawdown    = (equity - peak) / peak
    max_dd      = drawdown.min()
    calmar      = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    min_margin  = min(margin_ratios) if margin_ratios else 1.0
    safe        = min_margin >= SAFETY_BUFFER_MARGIN

    return {
        'label':           label,
        'leverage':        leverage,
        'equity':          equity,
        'drawdown':        drawdown,
        'total_return':    total_return,
        'annual_return':   annual_return,
        'max_drawdown':    max_dd,
        'calmar':          calmar,
        'interest_paid':   interest_paid,
        'liquidations':    liquidations,
        'min_margin':      min_margin,
        'safe':            safe,         # True if min_margin >= 25%
        'own_fraction':    own_fraction,
    }


# ---------------------------------------------------------------------------
# [FUNCTION] build_trade_objects
# ---------------------------------------------------------------------------

def build_trade_objects(
    df:        pd.DataFrame,
    trades_df: pd.DataFrame,
    stop_pct:  float,
) -> list:
    """
    [FUNCTION] Build enriched trade objects with daily low prices during hold.

    Each trade gets a list of daily low prices for every day it was open,
    used to check if liquidation or stop would have triggered intraday.

    Args:
        df        : full OHLCV DataFrame
        trades_df : trade log with entry_date, exit_date, return columns
        stop_pct  : stop-loss percentage (used to identify stop exits)

    Returns:
        list of trade dicts with entry_price, exit_price, return,
        hold_days, daily_lows
    """
    trades_df = trades_df.copy()
    trades_df['entry_date'] = pd.to_datetime(trades_df['entry_date'])
    trades_df['exit_date']  = pd.to_datetime(trades_df['exit_date'])

    enriched = []

    for _, trade in trades_df.iterrows():
        entry_date  = trade['entry_date']
        exit_date   = trade['exit_date']
        entry_price = trade['entry_price']

        # Get daily lows during the trade hold period
        mask       = (df.index > entry_date) & (df.index <= exit_date)
        hold_data  = df[mask]
        daily_lows = hold_data['Low'].values.tolist()
        hold_days  = max(len(hold_data), 1)

        enriched.append({
            'entry_price': entry_price,
            'exit_price':  trade['exit_price'],
            'return':      trade['return'],
            'hold_days':   hold_days,
            'daily_lows':  daily_lows,
        })

    return enriched


# ---------------------------------------------------------------------------
# FETCH DATA
# ---------------------------------------------------------------------------

print("\nFetching data...")

raw_eth = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw_eth.columns, pd.MultiIndex):
    raw_eth.columns = raw_eth.columns.droplevel(1)
eth_df = raw_eth[['Open','High','Low','Close','Volume']].copy()
eth_df.dropna(inplace=True)
print(f"  ETH: {eth_df.index[0].date()} → {eth_df.index[-1].date()}")

raw_btc = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw_btc.columns, pd.MultiIndex):
    raw_btc.columns = raw_btc.columns.droplevel(1)
btc_df = raw_btc[['Open','High','Low','Close','Volume']].copy()
btc_df.dropna(inplace=True)
print(f"  BTC: {btc_df.index[0].date()} → {btc_df.index[-1].date()}")


# ---------------------------------------------------------------------------
# BUILD TRADE OBJECTS
# ---------------------------------------------------------------------------

print("\nBuilding trade objects...")

# ETH ADX — load from saved log
eth_adx_log = pd.read_csv('data/trade_log_with_stoploss.csv')
eth_trades  = build_trade_objects(eth_df, eth_adx_log, ETH_ADX_STOP)
print(f"  ETH ADX: {len(eth_trades)} trades")

# BTC SMA 125 — run backtest to get trade log
def run_sma_to_log(df, period):
    """Run SMA crossover and return enriched trade log."""
    sma      = df['Close'].rolling(window=period).mean()
    position = 0; entry_price = 0.0; trades = []
    closes   = df['Close'].values; smas = sma.values; dates = df.index

    for i in range(period + 1, len(df)):
        close = closes[i]; close_prev = closes[i-1]
        sv    = smas[i];   sp         = smas[i-1]
        if np.isnan(sv) or np.isnan(sp): continue

        if position == 1:
            if close < sv and close_prev >= sp:
                trades.append({
                    'entry_date':  entry_date,
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      (close - entry_price) / entry_price,
                })
                position = 0; entry_price = 0.0
        elif position == 0:
            if close > sv and close_prev <= sp:
                entry_price = close
                entry_date  = dates[i]
                position    = 1

    if position == 1:
        trades.append({
            'entry_date':  entry_date,
            'entry_price': entry_price,
            'exit_date':   dates[-1],
            'exit_price':  closes[-1],
            'return':      (closes[-1] - entry_price) / entry_price,
        })

    return pd.DataFrame(trades)

btc_sma_log    = run_sma_to_log(btc_df, BTC_SMA_PERIOD)
# SMA has no hard stop — set stop_pct=1.0 (effectively no stop for slippage calc)
btc_trades     = build_trade_objects(btc_df, btc_sma_log, stop_pct=1.0)
print(f"  BTC SMA: {len(btc_trades)} trades")


# ---------------------------------------------------------------------------
# RUN LEVERAGE GRID SEARCH
# ---------------------------------------------------------------------------

leverage_levels = np.arange(LEVERAGE_MIN, LEVERAGE_MAX + 0.001, LEVERAGE_STEP)
leverage_levels = np.round(leverage_levels, 2)

print(f"\nRunning leverage grid ({len(leverage_levels)} levels: "
      f"{LEVERAGE_MIN:.2f}x to {LEVERAGE_MAX:.2f}x, step {LEVERAGE_STEP:.2f}x)...")

strategies = {
    'ETH ADX 20/10': {
        'trades':       eth_trades,
        'own_fraction': ETH_OWN_FRACTION,
        'stop_pct':     ETH_ADX_STOP,
        'color':        'steelblue',
    },
    'BTC SMA 125': {
        'trades':       btc_trades,
        'own_fraction': BTC_OWN_FRACTION,
        'stop_pct':     1.0,   # SMA uses price crossover as stop, not % stop
        'color':        'orange',
    },
}

# Store grid results: grid_results[strategy][leverage] = result dict
grid_results = {name: {} for name in strategies}

for strat_name, strat_info in strategies.items():
    for lev in leverage_levels:
        result = run_margin_backtest(
            df            = eth_df if 'ETH' in strat_name else btc_df,
            trade_returns = strat_info['trades'],
            leverage      = lev,
            own_fraction  = strat_info['own_fraction'],
            stop_pct      = strat_info['stop_pct'],
            daily_rate    = DAILY_INTEREST_RATE,
            label         = f"{strat_name} {lev:.2f}x",
        )
        grid_results[strat_name][lev] = result

print("  Grid search complete.")


# ---------------------------------------------------------------------------
# PRINT RESULTS TABLE
# ---------------------------------------------------------------------------

print(f"\n{'='*105}")
print(f"MARGIN LEVERAGE OPTIMISATION RESULTS")
print("(safe = margin ratio >= 25% historically, unsafe = margin ratio < 25%)")
print(f"Interest rate: {DAILY_INTEREST_RATE*100:.3f}%/day | "
      f"Stop slippage: {STOP_SLIPPAGE*100:.0f}% | "
      f"Liq slippage: {LIQ_SLIPPAGE*100:.0f}%")
print(f"{'='*105}")

for strat_name in strategies:
    results = grid_results[strat_name]
    print(f"\n  {strat_name}")
    print(f"  {'Lev':>6} {'Annual':>8} {'Max DD':>8} {'Calmar':>8} "
          f"{'Final':>10} {'Interest':>10} {'Liqs':>6} "
          f"{'Min Margin':>12} {'Safe':>6}")
    print(f"  {'-'*85}")

    best_calmar = max(r['calmar'] for r in results.values())

    for lev in leverage_levels:
        r      = results[lev]
        safe   = '✅' if r['safe'] else '❌'
        best   = ' ← BEST' if abs(r['calmar'] - best_calmar) < 0.001 else ''
        marker = '⭐' if r['safe'] and abs(r['calmar'] - max(
            rr['calmar'] for rr in results.values() if rr['safe']
        )) < 0.001 else ''

        print(f"  {lev:>5.2f}x {r['annual_return']:>8.1%} "
              f"{r['max_drawdown']:>8.1%} {r['calmar']:>8.3f} "
              f"${r['equity'][-1]:>9,.0f} "
              f"${r['interest_paid']:>9,.0f} "
              f"{r['liquidations']:>6} "
              f"{r['min_margin']:>12.1%} "
              f"{safe}{marker}{best}")

    # Find best safe leverage
    safe_results = {lev: r for lev, r in results.items() if r['safe']}
    if safe_results:
        best_safe_lev = max(safe_results, key=lambda l: safe_results[l]['calmar'])
        best_safe_r   = safe_results[best_safe_lev]
        print(f"\n  RECOMMENDATION: {best_safe_lev:.2f}x leverage")
        print(f"    Annual return: {best_safe_r['annual_return']:+.1%}")
        print(f"    Max drawdown:  {best_safe_r['max_drawdown']:.1%}")
        print(f"    Calmar:        {best_safe_r['calmar']:.3f}")
        print(f"    Final value:   ${best_safe_r['equity'][-1]:,.0f}")
        print(f"    Interest paid: ${best_safe_r['interest_paid']:,.0f}")
        print(f"    Min margin:    {best_safe_r['min_margin']:.1%} "
              f"(>{SAFETY_BUFFER_MARGIN*100:.0f}% safety buffer ✅)")
    else:
        print(f"\n  ⚠️  No leverage level maintains >{SAFETY_BUFFER_MARGIN*100:.0f}% margin ratio.")
        print(f"       Consider reducing own_fraction or using max leverage of 1.0x.")


# ---------------------------------------------------------------------------
# INTEREST RATE SENSITIVITY
# ---------------------------------------------------------------------------

print(f"\n{'='*105}")
print(f"INTEREST RATE SENSITIVITY — at recommended leverage levels")
print(f"{'='*105}")

for strat_name in strategies:
    strat_info   = strategies[strat_name]
    results      = grid_results[strat_name]
    safe_results = {lev: r for lev, r in results.items() if r['safe']}

    if not safe_results:
        continue

    best_safe_lev = max(safe_results, key=lambda l: safe_results[l]['calmar'])

    print(f"\n  {strat_name} at {best_safe_lev:.2f}x leverage:")
    print(f"  {'Rate':>10} {'Annual':>10} {'Max DD':>10} "
          f"{'Calmar':>10} {'Interest':>12} {'Final':>12}")
    print(f"  {'-'*68}")

    for rate, rate_label in [
        (DAILY_INTEREST_LOW,  f"{DAILY_INTEREST_LOW*100:.3f}%/day (low)"),
        (DAILY_INTEREST_RATE, f"{DAILY_INTEREST_RATE*100:.3f}%/day (mid)"),
        (DAILY_INTEREST_HIGH, f"{DAILY_INTEREST_HIGH*100:.3f}%/day (high)"),
    ]:
        r = run_margin_backtest(
            df            = eth_df if 'ETH' in strat_name else btc_df,
            trade_returns = strat_info['trades'],
            leverage      = best_safe_lev,
            own_fraction  = strat_info['own_fraction'],
            stop_pct      = strat_info['stop_pct'],
            daily_rate    = rate,
            label         = rate_label,
        )
        print(f"  {rate_label:>30} {r['annual_return']:>10.1%} "
              f"{r['max_drawdown']:>10.1%} {r['calmar']:>10.3f} "
              f"${r['interest_paid']:>11,.0f} ${r['equity'][-1]:>11,.0f}")


# ---------------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------------

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

fig = plt.figure(figsize=(20, 20))
fig.suptitle(
    'Margin Trading Optimisation — ETH ADX and BTC SMA\n'
    f'Interest: {DAILY_INTEREST_RATE*100:.3f}%/day | '
    f'Stop slippage: {STOP_SLIPPAGE*100:.0f}% | '
    f'Safety buffer: min margin >{SAFETY_BUFFER_MARGIN*100:.0f}%\n'
    f'Green = safe (margin ratio >{SAFETY_BUFFER_MARGIN*100:.0f}%) | '
    f'Red = unsafe (margin ratio <{SAFETY_BUFFER_MARGIN*100:.0f}%)',
    fontsize=12, fontweight='bold', y=0.99
)

gs  = gridspec.GridSpec(4, 2, hspace=0.45, wspace=0.3, figure=fig)
row = 0

for strat_name in strategies:
    results      = grid_results[strat_name]
    safe_results = {lev: r for lev, r in results.items() if r['safe']}

    ax_calmar  = fig.add_subplot(gs[row, 0])
    ax_equity  = fig.add_subplot(gs[row, 1])
    ax_metrics = fig.add_subplot(gs[row+1, 0])
    ax_margin  = fig.add_subplot(gs[row+1, 1])
    row       += 2

    levs      = list(results.keys())
    calmars   = [results[l]['calmar']        for l in levs]
    annuals   = [results[l]['annual_return'] * 100 for l in levs]
    max_dds   = [results[l]['max_drawdown']  * 100 for l in levs]
    min_margs = [results[l]['min_margin']    * 100 for l in levs]
    safe_mask = [results[l]['safe']          for l in levs]

    colors    = ['green' if s else 'red' for s in safe_mask]

    # --- Calmar vs leverage ---
    ax_calmar.bar(levs, calmars, width=0.04,
                  color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
    ax_calmar.axvline(1.0, color='gray', linestyle=':', alpha=0.5)
    ax_calmar.axhline(results[1.0]['calmar'], color='gray',
                      linestyle='--', alpha=0.5, label='No leverage baseline')
    ax_calmar.set_title(f'{strat_name} — Calmar Ratio by Leverage\n'
                        f'Green = safe margin | Red = unsafe',
                        fontsize=9, fontweight='bold')
    ax_calmar.set_xlabel('Leverage')
    ax_calmar.set_ylabel('Calmar Ratio')
    ax_calmar.legend(fontsize=8)
    ax_calmar.grid(alpha=0.3, axis='y')

    # Best safe leverage marker
    if safe_results:
        best_safe = max(safe_results, key=lambda l: safe_results[l]['calmar'])
        ax_calmar.axvline(best_safe, color='gold', linewidth=2,
                          linestyle='--', label=f'Best safe: {best_safe:.2f}x')
        ax_calmar.legend(fontsize=8)

    # --- Equity curves — selected leverage levels ---
    selected_levs = [1.0, 1.25, 1.5, 1.75, 2.0]
    eq_colors     = ['gray', 'steelblue', 'green', 'orange', 'crimson']

    for lev, col in zip(selected_levs, eq_colors):
        if lev in results:
            r      = results[lev]
            safe_s = '✅' if r['safe'] else '❌'
            ax_equity.plot(
                r['equity'],
                color=col, linewidth=2,
                label=f"{lev:.2f}x {safe_s} "
                      f"({r['annual_return']:+.1%}/yr, "
                      f"DD:{r['max_drawdown']:.1%})"
            )

    ax_equity.axhline(INITIAL_CAPITAL, color='gray',
                      linestyle=':', alpha=0.4)
    ax_equity.set_title(f'{strat_name} — Equity Curves by Leverage (log scale)',
                        fontsize=9, fontweight='bold')
    ax_equity.set_ylabel('Portfolio Value (USD)')
    ax_equity.set_yscale('log')
    ax_equity.legend(fontsize=7, loc='upper left')
    ax_equity.grid(alpha=0.3)

    # --- Annual return and max DD vs leverage ---
    ax_metrics.plot(levs, annuals, color='steelblue', linewidth=2,
                    marker='o', markersize=3, label='Annual Return %')
    ax_metrics2 = ax_metrics.twinx()
    ax_metrics2.plot(levs, max_dds, color='crimson', linewidth=2,
                     marker='s', markersize=3, label='Max Drawdown %')
    ax_metrics2.set_ylabel('Max Drawdown (%)', color='crimson')

    ax_metrics.axvline(1.0, color='gray', linestyle=':', alpha=0.5)
    ax_metrics.set_title(f'{strat_name} — Return and Drawdown vs Leverage',
                         fontsize=9, fontweight='bold')
    ax_metrics.set_xlabel('Leverage')
    ax_metrics.set_ylabel('Annual Return (%)', color='steelblue')
    ax_metrics.grid(alpha=0.3)

    lines1, labels1 = ax_metrics.get_legend_handles_labels()
    lines2, labels2 = ax_metrics2.get_legend_handles_labels()
    ax_metrics.legend(lines1 + lines2, labels1 + labels2, fontsize=7)

    # --- Minimum margin ratio vs leverage ---
    ax_margin.plot(levs, min_margs, color='purple', linewidth=2,
                   marker='o', markersize=4)
    ax_margin.axhline(SAFETY_BUFFER_MARGIN * 100, color='orange',
                      linestyle='--', linewidth=2,
                      label=f'Safety buffer ({SAFETY_BUFFER_MARGIN*100:.0f}%)')
    ax_margin.axhline(MAINTENANCE_MARGIN * 100, color='red',
                      linestyle='--', linewidth=2,
                      label=f'Liquidation threshold ({MAINTENANCE_MARGIN*100:.0f}%)')
    ax_margin.fill_between(levs, min_margs, SAFETY_BUFFER_MARGIN * 100,
                            where=np.array(min_margs) < SAFETY_BUFFER_MARGIN * 100,
                            alpha=0.2, color='red', label='Unsafe zone')
    ax_margin.fill_between(levs, min_margs, SAFETY_BUFFER_MARGIN * 100,
                            where=np.array(min_margs) >= SAFETY_BUFFER_MARGIN * 100,
                            alpha=0.2, color='green', label='Safe zone')
    ax_margin.set_title(f'{strat_name} — Minimum Margin Ratio vs Leverage\n'
                        f'(lowest margin ratio reached across all trades)',
                        fontsize=9, fontweight='bold')
    ax_margin.set_xlabel('Leverage')
    ax_margin.set_ylabel('Minimum Margin Ratio (%)')
    ax_margin.legend(fontsize=7)
    ax_margin.grid(alpha=0.3)

plt.savefig(
    'Week_5_Notebooks/results/margin_backtest.png',
    dpi=150, bbox_inches='tight'
)
plt.close()
print(f"\n✅ Chart saved → Week_5_Notebooks/results/margin_backtest.png")

print(f"\n{'='*105}")
print(f"MARGIN BACKTEST COMPLETE")
print(f"{'='*105}\n")