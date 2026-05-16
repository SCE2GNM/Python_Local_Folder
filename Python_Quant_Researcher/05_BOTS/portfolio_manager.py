"""
Portfolio Manager — shared state across all strategies.

Tracks reserved_capital, position, and deployed value for each strategy.
Used by all production bots for:
  - Kelly position sizing (get_my_capital → stable capital base)
  - Post-trade state sync (update_position)
  - Health check reporting (get_portfolio_summary)
  - Weekly rebalance (rebalance_portfolio, every Monday 01:00 UTC)

State file: data/portfolio_state.json
"""

import json
import os
from datetime import datetime

PORTFOLIO_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'data', 'portfolio_state.json'
)

STRATEGY_SYMBOLS = {
    'eth_adx': 'ETHUSDT',
    'eth_rsi': 'ETHUSDT',
    'btc_sma': 'BTCUSDT',
}


def _load():
    with open(PORTFOLIO_STATE_FILE, 'r') as f:
        return json.load(f)


def _save(state):
    state['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(PORTFOLIO_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_my_capital(strategy_name):
    """
    Return reserved_capital for a strategy. This is the stable, pre-allocated
    capital base used for Kelly position sizing. Does not fluctuate with live
    balance as other strategies open/close positions.
    """
    state = _load()
    return float(state['strategies'][strategy_name]['reserved_capital'])


def update_position(strategy_name, position, entry_price, quantity, deployed_value):
    """
    Sync strategy position state after a trade entry or exit.
    Call after every BUY (position='LONG') and every SELL or stop trigger (position='FLAT').

    Args:
        strategy_name  [str]        : 'eth_adx', 'eth_rsi', or 'btc_sma'
        position       [str]        : 'LONG' or 'FLAT'
        entry_price    [float|None] : fill price at entry; None on exit
        quantity       [float]      : ETH/BTC held; 0 on exit
        deployed_value [float]      : USDT deployed; 0 on exit
    """
    state = _load()
    strat = state['strategies'][strategy_name]
    strat['position']       = position
    strat['entry_price']    = entry_price
    strat['quantity']       = quantity
    strat['deployed_value'] = deployed_value
    strat['cash_held']      = round(strat['reserved_capital'] - deployed_value, 2)
    _save(state)


def get_total_portfolio_value(binance_client):
    """
    Calculate total portfolio value across all strategies using live prices.
    LONG positions: quantity × current_price.
    FLAT positions: cash_held.
    Returns float (total USD value).
    """
    state = _load()
    total = 0.0
    for name, strat in state['strategies'].items():
        if strat['position'] == 'LONG' and strat.get('quantity', 0) > 0:
            symbol = STRATEGY_SYMBOLS.get(name)
            if symbol:
                ticker = binance_client.get_symbol_ticker(symbol=symbol)
                price  = float(ticker['price'])
                total += strat['quantity'] * price
            else:
                total += strat.get('deployed_value', 0)
        else:
            total += strat.get('cash_held', strat['reserved_capital'])
    return round(total, 2)


def rebalance_portfolio(binance_client):
    """
    Recalculate reserved_capital for each strategy based on current total
    portfolio value and allocation_pcts. Called weekly (Monday 01:00 UTC).

    Rules:
    - fixed_allocation=true: reserved_capital is never changed by rebalance.
      Use for validation strategies with manually set capital (e.g. ETH RSI $150).
    - Otherwise: reserved_capital is only updated UPWARD. If the percentage-based
      allocation is lower than the current reserved_capital, keep the current value.
      This prevents a portfolio drawdown from silently reducing strategy capital.

    FLAT strategies: cash_held updated to match new reserved_capital.
    LONG strategies: reserved_capital updated; deployed_value and cash_held
    are NOT changed mid-trade.

    Returns dict with total_val and per-strategy before/after details.
    """
    state     = _load()
    total_val = get_total_portfolio_value(binance_client)
    allocs    = state['allocation_pcts']
    results   = {'total_val': total_val, 'strategies': {}}

    for name, strat in state['strategies'].items():
        old_capital = strat['reserved_capital']
        is_fixed    = strat.get('fixed_allocation', False)

        proposed = round(total_val * allocs.get(name, 0), 2)

        if is_fixed:
            new_capital = old_capital
            action      = 'fixed'
        elif proposed > old_capital:
            new_capital = proposed
            action      = 'increased'
        else:
            new_capital = old_capital
            action      = 'protected'

        strat['reserved_capital'] = new_capital
        if strat['position'] == 'FLAT':
            strat['cash_held'] = new_capital

        results['strategies'][name] = {
            'before':   old_capital,
            'after':    new_capital,
            'proposed': proposed,
            'action':   action,
        }

    state['last_rebalance_date'] = datetime.now().strftime('%Y-%m-%d')
    _save(state)
    return results


def record_trade_result(strategy_name, entry_date, exit_date, return_pct, exit_reason):
    """
    Record a closed trade to the strategy's live performance CSV.
    Appends one row. Returns running stats for monitoring and scale-up decisions.

    Log file: data/{strategy_name}_live_performance_log.csv
    Fields: entry_date, exit_date, return_pct, exit_reason, win

    Returns dict: n_trades, win_rate, consecutive_losses
    """
    import csv

    log_file = os.path.join(
        os.path.dirname(PORTFOLIO_STATE_FILE),
        f'{strategy_name}_live_performance_log.csv'
    )
    fieldnames = ['entry_date', 'exit_date', 'return_pct', 'exit_reason', 'win']
    win = 1 if return_pct > 0 else 0
    row = {
        'entry_date':  str(entry_date),
        'exit_date':   str(exit_date),
        'return_pct':  round(float(return_pct), 6),
        'exit_reason': exit_reason,
        'win':         win,
    }
    file_exists = os.path.exists(log_file)
    with open(log_file, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    with open(log_file, 'r') as f:
        rows = list(csv.DictReader(f))

    n_trades  = len(rows)
    wins      = sum(int(r['win']) for r in rows)
    win_rate  = wins / n_trades if n_trades else 0.0

    consecutive_losses = 0
    for r in reversed(rows):
        if int(r['win']) == 0:
            consecutive_losses += 1
        else:
            break

    return {
        'n_trades':           n_trades,
        'win_rate':           win_rate,
        'consecutive_losses': consecutive_losses,
    }


def get_portfolio_summary(binance_client):
    """
    Return a formatted multi-line string for inclusion in Telegram health checks.
    Shows each strategy: position, live value, P&L if LONG, reserved capital.
    """
    state = _load()
    lines = ["─── Portfolio ───"]
    total = 0.0

    for name, strat in state['strategies'].items():
        reserved = strat['reserved_capital']
        if strat['position'] == 'LONG' and strat.get('quantity', 0) > 0:
            symbol   = STRATEGY_SYMBOLS.get(name)
            price    = float(binance_client.get_symbol_ticker(symbol=symbol)['price']) if symbol else 0.0
            live_val = strat['quantity'] * price
            total   += live_val
            ep       = strat.get('entry_price') or price
            pnl_pct  = (price - ep) / ep if ep else 0.0
            lines.append(
                f"{name}: LONG {strat['quantity']:.3f} | "
                f"${live_val:,.0f} ({pnl_pct:+.1%}) | cap ${reserved:,.0f}"
            )
        else:
            cash   = strat.get('cash_held', reserved)
            total += cash
            lines.append(f"{name}: FLAT | cash ${cash:,.0f} | cap ${reserved:,.0f}")

    lines.append(f"Total: ${total:,.0f}")
    return "\n".join(lines)
