# [MODULE] Kelly Criterion Sizing Comparison
# Week 5 Extension
#
# WHAT THIS SCRIPT DOES:
#   Runs each strategy under 5 different position sizing approaches
#   and plots equity curves + drawdowns side by side.
#   Shows whether aggressive sizing is worth it given the journey.
#
# KEY QUESTION:
#   If aggressive sizing produces higher absolute returns but deeper
#   drawdowns, is it still worth it if the account value at the
#   bottom of a drawdown is higher than conservative sizing's peak?
#
# STRATEGIES:
#   ETH ADX 20/10 (5% stop)    — from trade_log_with_stoploss.csv
#   BTC ADX 19/14 (3% stop)    — run live in script
#   BTC SMA 125                 — run live in script
#
# SIZING APPROACHES (applied to each strategy):
#   1. 150% — leveraged (requires margin, noted as such)
#   2. 100% — all-in every trade
#   3. Full Kelly
#   4. Half Kelly / Selected Kelly
#   5. Conservative 5%
#
# NOTE ON 150% SIZING:
#   Mathematically modelled as 1.5x position size per trade.
#   In live trading requires margin account with interest costs.
#   Backtest does not model margin costs or forced liquidation.
#
# NOTE ON KELLY VALUES:
#   ETH ADX:  Full 23.54%, Selected 12.41%
#   BTC ADX:  Full 19.30%, Selected  9.65%
#   BTC SMA:  Full capped, Selected 25.00% (25-trade sample too small)

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from ta.trend import ADXIndicator
import os

# ---------------------------------------------------------------------------
# STRATEGY KELLY PARAMETERS
# ---------------------------------------------------------------------------

STRATEGIES = {
    'ETH ADX 20/10': {
        'full_kelly':     0.2354,
        'selected_kelly': 0.1241,
        'color':          'steelblue',
    },
    'BTC ADX 19/14': {
        'full_kelly':     0.1930,
        'selected_kelly': 0.0965,
        'color':          'orange',
    },
    'BTC SMA 125': {
        'full_kelly':     0.25,    # capped — sample too small for reliable estimate
        'selected_kelly': 0.25,    # same — cap applies
        'color':          'green',
    },
}

SIZING_LEVELS = [
    ('150% (leveraged)', 1.50, 'darkred',    '--'),
    ('100% (all-in)',    1.00, 'crimson',     '-'),
    ('Full Kelly',       None, 'darkorange',  '-'),
    ('Selected Kelly',   None, 'steelblue',   '-'),
    ('Conservative 5%',  0.05, 'gray',        ':'),
]

INITIAL_CAPITAL = 1000.0


# ---------------------------------------------------------------------------
# [FUNCTION] simulate_sizing
# ---------------------------------------------------------------------------

def simulate_sizing(
    returns:    np.ndarray,
    fraction:   float,
    initial:    float = INITIAL_CAPITAL,
) -> np.ndarray:
    """
    [FUNCTION] Simulate portfolio growth with a fixed fractional sizing.

    Each trade uses fraction * current_balance as position size.
    PnL = position_size * trade_return
    New balance = old balance + PnL
    Floor at 1.0 (can't go below $1)

    Args:
        returns  : array of per-trade returns
        fraction : position size as fraction of balance (e.g. 0.12)
        initial  : starting capital

    Returns:
        np.ndarray of balance after each trade (length = len(returns) + 1)
    """
    balance  = initial
    history  = [balance]

    for r in returns:
        position_size = balance * fraction
        pnl           = position_size * r
        balance       = max(balance + pnl, 1.0)
        history.append(balance)

    return np.array(history)


# ---------------------------------------------------------------------------
# [FUNCTION] equity_metrics
# ---------------------------------------------------------------------------

def equity_metrics(equity: np.ndarray, years: float) -> dict:
    """
    [FUNCTION] Calculate key metrics from an equity curve.

    Args:
        equity : array of portfolio values
        years  : length of backtest period in years

    Returns:
        dict with total_return, annual_return, max_drawdown, calmar
    """
    total_return  = equity[-1] / equity[0] - 1
    annual_return = (1 + total_return) ** (1 / years) - 1
    peak          = np.maximum.accumulate(equity)
    drawdown      = (equity - peak) / peak
    max_dd        = drawdown.min()
    calmar        = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    return {
        'final':          equity[-1],
        'total_return':   total_return,
        'annual_return':  annual_return,
        'max_drawdown':   max_dd,
        'calmar':         calmar,
        'drawdown':       drawdown,
    }


# ---------------------------------------------------------------------------
# FETCH DATA AND RUN BACKTESTS
# ---------------------------------------------------------------------------

print("\nFetching data...")

# ETH
raw_eth = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw_eth.columns, pd.MultiIndex):
    raw_eth.columns = raw_eth.columns.droplevel(1)
eth_df = raw_eth[['Open','High','Low','Close','Volume']].copy()
eth_df.dropna(inplace=True)
print(f"  ETH: {eth_df.index[0].date()} → {eth_df.index[-1].date()}")

# BTC
raw_btc = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw_btc.columns, pd.MultiIndex):
    raw_btc.columns = raw_btc.columns.droplevel(1)
btc_df = raw_btc[['Open','High','Low','Close','Volume']].copy()
btc_df.dropna(inplace=True)
print(f"  BTC: {btc_df.index[0].date()} → {btc_df.index[-1].date()}")

years = (eth_df.index[-1] - eth_df.index[0]).days / 365.25


# ---------------------------------------------------------------------------
# GET TRADE RETURNS FOR EACH STRATEGY
# ---------------------------------------------------------------------------

print("\nRunning strategy backtests...")

# --- ETH ADX: load from saved trade log ---
eth_adx_trades = pd.read_csv('data/trade_log_with_stoploss.csv')
eth_adx_returns = eth_adx_trades['return'].values
print(f"  ETH ADX: {len(eth_adx_returns)} trades loaded from trade log")


# --- BTC ADX 19/14 3% stop: run backtest ---
def run_adx_trades(df, threshold, period, stop_pct):
    """Run ADX backtest and return array of trade returns."""
    adx_ind = ADXIndicator(df['High'], df['Low'], df['Close'], window=period)
    adx     = adx_ind.adx()
    di_pos  = adx_ind.adx_pos()
    di_neg  = adx_ind.adx_neg()
    signal  = (adx >= threshold) & (di_pos > di_neg)

    position = 0; entry_price = 0.0; stop_price = 0.0; trades = []
    closes = df['Close'].values; lows = df['Low'].values
    signals = signal.values

    for i in range(1, len(df)):
        low = lows[i]; close = closes[i]; sig = signals[i]
        if position == 1:
            if low <= stop_price:
                trades.append((stop_price - entry_price) / entry_price)
                position = 0; entry_price = 0.0; stop_price = 0.0
            elif not sig:
                trades.append((close - entry_price) / entry_price)
                position = 0; entry_price = 0.0; stop_price = 0.0
        elif position == 0 and sig:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    return np.array(trades)


def run_sma_trades(df, sma_period):
    """Run SMA crossover backtest and return array of trade returns."""
    sma = df['Close'].rolling(window=sma_period).mean()
    position = 0; entry_price = 0.0; trades = []
    closes = df['Close'].values; smas = sma.values

    for i in range(sma_period + 1, len(df)):
        close = closes[i]; close_prev = closes[i-1]
        sma_val = smas[i]; sma_prev = smas[i-1]
        if np.isnan(sma_val) or np.isnan(sma_prev): continue

        if position == 1:
            if close < sma_val and close_prev >= sma_prev:
                trades.append((close - entry_price) / entry_price)
                position = 0; entry_price = 0.0
        elif position == 0:
            if close > sma_val and close_prev <= sma_prev:
                entry_price = close; position = 1

    if position == 1:
        trades.append((closes[-1] - entry_price) / entry_price)

    return np.array(trades)


btc_adx_returns = run_adx_trades(btc_df, threshold=19, period=14, stop_pct=0.03)
btc_sma_returns = run_sma_trades(btc_df, sma_period=125)

print(f"  BTC ADX: {len(btc_adx_returns)} trades")
print(f"  BTC SMA: {len(btc_sma_returns)} trades")


# ---------------------------------------------------------------------------
# RUN ALL SIZING SIMULATIONS
# ---------------------------------------------------------------------------

strategy_returns = {
    'ETH ADX 20/10': eth_adx_returns,
    'BTC ADX 19/14': btc_adx_returns,
    'BTC SMA 125':   btc_sma_returns,
}

# Store results: results[strategy_name][sizing_label] = metrics dict
all_results = {}

for strat_name, returns in strategy_returns.items():
    all_results[strat_name] = {}
    kelly_info = STRATEGIES[strat_name]

    for sizing_label, fraction, color, ls in SIZING_LEVELS:
        # Determine actual fraction
        if fraction is None:
            if 'Full' in sizing_label:
                f = kelly_info['full_kelly']
            else:
                f = kelly_info['selected_kelly']
        else:
            f = fraction

        equity  = simulate_sizing(returns, f)
        metrics = equity_metrics(equity, years)
        metrics['equity']   = equity
        metrics['fraction'] = f
        metrics['color']    = color
        metrics['ls']       = ls
        metrics['label']    = sizing_label

        all_results[strat_name][sizing_label] = metrics


# ---------------------------------------------------------------------------
# PRINT SUMMARY TABLE
# ---------------------------------------------------------------------------

print(f"\n{'='*100}")
print(f"KELLY SIZING COMPARISON — FULL RESULTS")
print(f"{'='*100}")

for strat_name in strategy_returns.keys():
    kelly_info = STRATEGIES[strat_name]
    print(f"\n  {strat_name} "
          f"(Full Kelly: {kelly_info['full_kelly']:.1%}, "
          f"Selected: {kelly_info['selected_kelly']:.1%})")
    print(f"  {'Sizing':<22} {'Fraction':>10} {'Final Value':>12} "
          f"{'Total Return':>14} {'Annual':>10} {'Max DD':>10} {'Calmar':>8}")
    print(f"  {'-'*90}")

    for sizing_label, _, _, _ in SIZING_LEVELS:
        m = all_results[strat_name][sizing_label]
        print(f"  {sizing_label:<22} {m['fraction']:>10.1%} "
              f"${m['final']:>11,.0f} {m['total_return']:>14.1%} "
              f"{m['annual_return']:>10.1%} {m['max_drawdown']:>10.1%} "
              f"{m['calmar']:>8.3f}")

print(f"\n  NOTE: 150% sizing requires margin account in live trading.")
print(f"  Backtest does not model margin interest costs (~0.1%/day).")
print(f"  At 150% sizing, margin interest would reduce returns by ~36%/yr.")


# ---------------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------------

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

strat_names  = list(strategy_returns.keys())
n_strategies = len(strat_names)

fig = plt.figure(figsize=(20, 24))
fig.suptitle(
    'Kelly Criterion Sizing Comparison — ETH ADX, BTC ADX, BTC SMA\n'
    'Does aggressive sizing justify the drawdown journey?\n'
    'Starting capital: 1,000 USD each strategy',
    fontsize=13, fontweight='bold', y=0.99
)

# 3 strategies × 2 panels each (equity + drawdown) = 6 rows
gs = gridspec.GridSpec(6, 1, hspace=0.45, figure=fig)

row = 0
for strat_name in strat_names:
    ax_eq = fig.add_subplot(gs[row])
    ax_dd = fig.add_subplot(gs[row + 1])
    row  += 2

    results_for_strat = all_results[strat_name]
    kelly_info        = STRATEGIES[strat_name]

    # --- Equity curve (log scale) ---
    for sizing_label, _, color, ls in SIZING_LEVELS:
        m      = results_for_strat[sizing_label]
        equity = m['equity']
        label  = (f"{sizing_label} ({m['fraction']:.0%}) — "
                  f"Final: {equity[-1]:,.0f} | "
                  f"Ann: {m['annual_return']:+.1%} | "
                  f"DD: {m['max_drawdown']:.1%}")
        ax_eq.plot(equity, color=color, linewidth=2,
                   linestyle=ls, label=label, alpha=0.9)

    ax_eq.axhline(INITIAL_CAPITAL, color='gray',
                  linestyle=':', alpha=0.4, linewidth=1)
    ax_eq.set_title(
        f'{strat_name} — Equity Curves by Sizing Strategy (log scale)',
        fontsize=10, fontweight='bold'
    )
    ax_eq.set_ylabel('Portfolio Value (USD)')
    ax_eq.set_yscale('log')
    ax_eq.legend(fontsize=7, loc='upper left')
    ax_eq.grid(alpha=0.3)

    # --- Drawdown ---
    for sizing_label, _, color, ls in SIZING_LEVELS:
        m = results_for_strat[sizing_label]
        ax_dd.plot(
            m['drawdown'] * 100,
            color=color, linewidth=1.5, linestyle=ls,
            alpha=0.8,
            label=f"{sizing_label} ({m['fraction']:.0%}) "
                  f"max: {m['max_drawdown']:.1%}"
        )

    ax_dd.axhline(0,     color='gray',  linestyle=':', alpha=0.4)
    ax_dd.axhline(-15,   color='red',   linestyle='--', linewidth=1.5,
                  alpha=0.7, label='15% guardrail')
    ax_dd.axhline(-30,   color='orange', linestyle='--', linewidth=1,
                  alpha=0.5, label='30% reference')
    ax_dd.set_title(
        f'{strat_name} — Drawdown by Sizing Strategy',
        fontsize=10, fontweight='bold'
    )
    ax_dd.set_ylabel('Drawdown %')
    ax_dd.legend(fontsize=7, loc='lower left')
    ax_dd.grid(alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.98])
chart_path = 'Week_5_Notebooks/results/kelly_sizing_comparison.png'
plt.savefig(chart_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"\n✅ Chart saved → {chart_path}")

print(f"\n{'='*100}")
print(f"KELLY SIZING COMPARISON COMPLETE")
print(f"{'='*100}\n")