# [MODULE] Day 7b - Bitcoin Cross-Asset Validation
# Week 5
#
# WHAT THIS SCRIPT DOES:
#   Runs all three strategies on BTC-USD using parameters
#   optimised on ETH-USD. This is out-of-asset validation —
#   the strictest test of whether an edge is genuine.
#
# WHY THIS MATTERS:
#   If strategies only work on ETH, the edge may be specific
#   to ETH's price history rather than a genuine statistical
#   phenomenon. If they also work on BTC with the SAME parameters,
#   that's much stronger evidence of a real edge.
#
# PARAMETERS: FROZEN at ETH-optimised values
#   ADX: threshold=20, period=10, stop=5%
#   BB:  window=15, std=2.0, stop=10%, MA=150
#   RSI: period=14, oversold=43, exit=48, stop=15%, MA=120
#
# NOTE ON PROFIT FACTOR:
#   When all trades are winners, profit factor = infinite.
#   We report this as 'INF' rather than a nonsensical large number.

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from ta.trend import ADXIndicator
import os

# ---------------------------------------------------------------------------
# [FUNCTION] safe_profit_factor
# ---------------------------------------------------------------------------

def safe_profit_factor(winners: pd.DataFrame, losers: pd.DataFrame) -> float:
    """
    [FUNCTION] Calculate profit factor safely.

    Returns float('inf') when there are no losing trades,
    rather than dividing by near-zero which produces nonsensical numbers.

    Args:
        winners : DataFrame of winning trades
        losers  : DataFrame of losing trades

    Returns:
        float profit factor, or float('inf') if no losers
    """
    gross_profit: float = winners['return'].sum() if len(winners) > 0 else 0.0
    gross_loss:   float = abs(losers['return'].sum()) if len(losers) > 0 else 0.0

    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def fmt_pf(pf: float) -> str:
    """Format profit factor for display."""
    if pf == float('inf'):
        return 'INF (no losses)'
    return f"{pf:.3f}"


# ---------------------------------------------------------------------------
# [FUNCTION] run_adx_backtest
# ---------------------------------------------------------------------------

def run_adx_backtest(
    df:        pd.DataFrame,
    threshold: int   = 20,
    period:    int   = 10,
    stop_pct:  float = 0.05,
    label:     str   = 'ADX',
) -> dict:
    """
    [FUNCTION] Run ADX trend-following backtest.

    Entry:  ADX >= threshold AND +DI > -DI
    Exit:   ADX < threshold OR -DI > +DI
    Stop:   stop_pct below entry price

    Args:
        df        : OHLCV DataFrame
        threshold : ADX level to define trending regime
        period    : ADX lookback window
        stop_pct  : hard stop-loss
        label     : strategy label for reporting
    """
    adx_ind = ADXIndicator(df['High'], df['Low'], df['Close'], window=period)
    adx     = adx_ind.adx()
    di_pos  = adx_ind.adx_pos()
    di_neg  = adx_ind.adx_neg()

    entry_signal = (adx >= threshold) & (di_pos > di_neg)

    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    closes  = df['Close'].values
    lows    = df['Low'].values
    signals = entry_signal.values

    for i in range(1, len(df)):
        low:    float = lows[i]
        close:  float = closes[i]
        signal: bool  = signals[i]

        if position == 1:
            if low <= stop_price:
                trades.append({
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            elif not signal:
                trades.append({
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'ADX_EXIT',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and signal:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    if len(trades) == 0:
        return {'label': label, 'trades': 0}

    trades_df = pd.DataFrame(trades)
    returns   = trades_df['return'].values
    winners   = trades_df[trades_df['return'] > 0]
    losers    = trades_df[trades_df['return'] <= 0]

    equity   = np.cumprod(1 + returns)
    peak     = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak

    years = (df.index[-1] - df.index[0]).days / 365.25

    return {
        'label':           label,
        'trades':          len(trades_df),
        'trades_per_year': len(trades_df) / years,
        'win_rate':        len(winners) / len(trades_df),
        'avg_win':         winners['return'].mean() if len(winners) > 0 else 0.0,
        'avg_loss':        losers['return'].mean()  if len(losers)  > 0 else 0.0,
        'profit_factor':   safe_profit_factor(winners, losers),
        'max_drawdown':    drawdown.min(),
        'total_return':    (1 + returns).prod() - 1,
        'equity':          equity,
        'years':           years,
    }


# ---------------------------------------------------------------------------
# [FUNCTION] run_bb_backtest
# ---------------------------------------------------------------------------

def run_bb_backtest(
    df:        pd.DataFrame,
    window:    int   = 15,
    num_std:   float = 2.0,
    stop_pct:  float = 0.10,
    ma_filter: int   = 150,
    label:     str   = 'BB',
) -> dict:
    """
    [FUNCTION] Run Bollinger Bands mean reversion backtest.

    Entry:  Close < lower band AND Close > MA filter
    Exit:   Close > middle band
    Stop:   stop_pct below entry

    Args:
        df        : OHLCV DataFrame
        window    : BB lookback period
        num_std   : band width in standard deviations
        stop_pct  : hard stop-loss
        ma_filter : regime filter MA period
        label     : strategy label
    """
    middle    = df['Close'].rolling(window=window).mean()
    std       = df['Close'].rolling(window=window).std()
    bb_upper  = middle + (num_std * std)
    bb_lower  = middle - (num_std * std)
    ma        = df['Close'].rolling(window=ma_filter).mean()

    entry_signal = (df['Close'] < bb_lower) & (df['Close'] > ma)
    exit_signal  = df['Close'] > middle

    valid_from = max(window, ma_filter)

    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    closes  = df['Close'].values
    lows    = df['Low'].values
    entries = entry_signal.values
    exits   = exit_signal.values

    for i in range(valid_from, len(df)):
        low:   float = lows[i]
        close: float = closes[i]

        if position == 1:
            if low <= stop_price:
                trades.append({
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            elif exits[i]:
                trades.append({
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'BB_EXIT',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and entries[i]:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    if len(trades) == 0:
        return {'label': label, 'trades': 0}

    trades_df = pd.DataFrame(trades)
    returns   = trades_df['return'].values
    winners   = trades_df[trades_df['return'] > 0]
    losers    = trades_df[trades_df['return'] <= 0]

    equity   = np.cumprod(1 + returns)
    peak     = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak

    years = (df.index[-1] - df.index[0]).days / 365.25

    return {
        'label':           label,
        'trades':          len(trades_df),
        'trades_per_year': len(trades_df) / years,
        'win_rate':        len(winners) / len(trades_df),
        'avg_win':         winners['return'].mean() if len(winners) > 0 else 0.0,
        'avg_loss':        losers['return'].mean()  if len(losers)  > 0 else 0.0,
        'profit_factor':   safe_profit_factor(winners, losers),
        'max_drawdown':    drawdown.min(),
        'total_return':    (1 + returns).prod() - 1,
        'equity':          equity,
        'years':           years,
    }


# ---------------------------------------------------------------------------
# [FUNCTION] run_rsi_backtest
# ---------------------------------------------------------------------------

def run_rsi_backtest(
    df:         pd.DataFrame,
    rsi_period: int   = 14,
    oversold:   float = 43.0,
    exit_level: float = 48.0,
    stop_pct:   float = 0.15,
    ma_filter:  int   = 120,
    label:      str   = 'RSI',
) -> dict:
    """
    [FUNCTION] Run RSI mean reversion backtest.

    Entry:  RSI < oversold AND Close > MA filter
    Exit:   RSI > exit_level
    Stop:   stop_pct below entry

    Args:
        df         : OHLCV DataFrame
        rsi_period : RSI calculation window
        oversold   : RSI buy threshold
        exit_level : RSI exit threshold
        stop_pct   : hard stop-loss
        ma_filter  : regime filter MA period
        label      : strategy label
    """
    delta    = df['Close'].diff()
    gains    = delta.clip(lower=0)
    losses   = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1/rsi_period, min_periods=rsi_period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1/rsi_period, min_periods=rsi_period, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, 1e-9)
    rsi      = 100 - (100 / (1 + rs))
    ma       = df['Close'].rolling(window=ma_filter).mean()

    entry_signal = (rsi < oversold) & (df['Close'] > ma)
    exit_signal  = rsi > exit_level

    valid_from = max(rsi_period * 3, ma_filter)

    position:    int   = 0
    entry_price: float = 0.0
    stop_price:  float = 0.0
    trades:      list  = []

    closes  = df['Close'].values
    lows    = df['Low'].values
    entries = entry_signal.values
    exits   = exit_signal.values

    for i in range(valid_from, len(df)):
        low:   float = lows[i]
        close: float = closes[i]

        if position == 1:
            if low <= stop_price:
                trades.append({
                    'return':      (stop_price - entry_price) / entry_price,
                    'exit_reason': 'STOP_LOSS',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

            elif exits[i]:
                trades.append({
                    'return':      (close - entry_price) / entry_price,
                    'exit_reason': 'RSI_EXIT',
                })
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and entries[i]:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1

    if len(trades) == 0:
        return {'label': label, 'trades': 0}

    trades_df = pd.DataFrame(trades)
    returns   = trades_df['return'].values
    winners   = trades_df[trades_df['return'] > 0]
    losers    = trades_df[trades_df['return'] <= 0]

    equity   = np.cumprod(1 + returns)
    peak     = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak

    years = (df.index[-1] - df.index[0]).days / 365.25

    return {
        'label':           label,
        'trades':          len(trades_df),
        'trades_per_year': len(trades_df) / years,
        'win_rate':        len(winners) / len(trades_df),
        'avg_win':         winners['return'].mean() if len(winners) > 0 else 0.0,
        'avg_loss':        losers['return'].mean()  if len(losers)  > 0 else 0.0,
        'profit_factor':   safe_profit_factor(winners, losers),
        'max_drawdown':    drawdown.min(),
        'total_return':    (1 + returns).prod() - 1,
        'equity':          equity,
        'years':           years,
    }


# ---------------------------------------------------------------------------
# FETCH BTC DATA
# ---------------------------------------------------------------------------

print("\nFetching BTC-USD daily data...")
raw = yf.download('BTC-USD', start='2018-01-01', interval='1d', progress=False)

if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)

btc = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
btc.dropna(inplace=True)
print(f"BTC data: {btc.index[0].date()} → {btc.index[-1].date()} ({len(btc):,} days)")

# Also fetch ETH for direct comparison
print("\nFetching ETH-USD daily data...")
raw_eth = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)

if isinstance(raw_eth.columns, pd.MultiIndex):
    raw_eth.columns = raw_eth.columns.droplevel(1)

eth = raw_eth[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
eth.dropna(inplace=True)
print(f"ETH data: {eth.index[0].date()} → {eth.index[-1].date()} ({len(eth):,} days)")


# ---------------------------------------------------------------------------
# RUN ALL STRATEGIES ON BOTH ASSETS
# ---------------------------------------------------------------------------

print(f"\n{'='*80}")
print(f"RUNNING ALL STRATEGIES — ETH vs BTC")
print(f"Parameters frozen at ETH-optimised values")
print(f"{'='*80}")

# ETH results
eth_adx = run_adx_backtest(eth, threshold=20, period=10,  stop_pct=0.05,  label='ADX ETH')
eth_bb  = run_bb_backtest( eth, window=15,   num_std=2.0, stop_pct=0.10, ma_filter=150, label='BB ETH')
eth_rsi = run_rsi_backtest(eth, rsi_period=14, oversold=43.0, exit_level=48.0, stop_pct=0.15, ma_filter=120, label='RSI ETH')

# BTC results — same parameters
btc_adx = run_adx_backtest(btc, threshold=20, period=10,  stop_pct=0.05,  label='ADX BTC')
btc_bb  = run_bb_backtest( btc, window=15,   num_std=2.0, stop_pct=0.10, ma_filter=150, label='BB BTC')
btc_rsi = run_rsi_backtest(btc, rsi_period=14, oversold=43.0, exit_level=48.0, stop_pct=0.15, ma_filter=120, label='RSI BTC')


# ---------------------------------------------------------------------------
# PRINT COMPARISON TABLE
# ---------------------------------------------------------------------------

def print_result(r: dict) -> None:
    """Print a single strategy result row."""
    if r['trades'] == 0:
        print(f"  {r['label']:<12} {'No trades':>8}")
        return

    pf_str = fmt_pf(r['profit_factor'])
    print(f"  {r['label']:<12} "
          f"Trades:{r['trades']:>4} ({r['trades_per_year']:.1f}/yr)  "
          f"WR:{r['win_rate']:>6.1%}  "
          f"PF:{pf_str:>18}  "
          f"DD:{r['max_drawdown']:>7.1%}  "
          f"Return:{r['total_return']:>+8.1%}")


print(f"\n{'ADX TREND FOLLOWING':}")
print(f"  {'Strategy':<12} {'Trades':>10}  {'Win Rate':>8}  {'Profit Factor':>20}  {'Max DD':>8}  {'Return':>8}")
print(f"  {'-'*78}")
print_result(eth_adx)
print_result(btc_adx)

print(f"\n{'BOLLINGER BANDS MEAN REVERSION':}")
print(f"  {'Strategy':<12} {'Trades':>10}  {'Win Rate':>8}  {'Profit Factor':>20}  {'Max DD':>8}  {'Return':>8}")
print(f"  {'-'*78}")
print_result(eth_bb)
print_result(btc_bb)

print(f"\n{'RSI MEAN REVERSION':}")
print(f"  {'Strategy':<12} {'Trades':>10}  {'Win Rate':>8}  {'Profit Factor':>20}  {'Max DD':>8}  {'Return':>8}")
print(f"  {'-'*78}")
print_result(eth_rsi)
print_result(btc_rsi)


# ---------------------------------------------------------------------------
# OVERALL CROSS-ASSET VERDICT
# ---------------------------------------------------------------------------

print(f"\n{'='*80}")
print(f"CROSS-ASSET VALIDATION VERDICT")
print(f"{'='*80}")

strategies = [
    ('ADX', eth_adx, btc_adx),
    ('BB',  eth_bb,  btc_bb),
    ('RSI', eth_rsi, btc_rsi),
]

for name, eth_r, btc_r in strategies:
    print(f"\n  {name} Strategy:")

    if eth_r['trades'] == 0 or btc_r['trades'] == 0:
        print(f"    ⚠️  Insufficient trades on one or both assets")
        continue

    eth_pf = eth_r['profit_factor']
    btc_pf = btc_r['profit_factor']

    eth_profitable = eth_pf > 1.0 or eth_pf == float('inf')
    btc_profitable = btc_pf > 1.0 or btc_pf == float('inf')

    if eth_profitable and btc_profitable:
        print(f"    ✅ GENERALISES — profitable on both ETH and BTC")
        print(f"       ETH: WR {eth_r['win_rate']:.1%} | "
              f"Return {eth_r['total_return']:+.1%}")
        print(f"       BTC: WR {btc_r['win_rate']:.1%} | "
              f"Return {btc_r['total_return']:+.1%}")
    elif eth_profitable:
        print(f"    ⚠️  ETH ONLY — does not generalise to BTC")
        print(f"       Consider ETH-specific factors in the edge")
    else:
        print(f"    ❌ FAILS on both assets")


# ---------------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------------

os.makedirs('Week_5_Notebooks/results', exist_ok=True)

fig, axes = plt.subplots(3, 2, figsize=(16, 14))
fig.suptitle(
    'Cross-Asset Validation — ETH vs BTC\n'
    'Same parameters on both assets (ETH-optimised values)',
    fontsize=13, fontweight='bold'
)

strategy_pairs = [
    (eth_adx, btc_adx, 'ADX Trend Following', 'steelblue', 'navy'),
    (eth_bb,  btc_bb,  'BB Mean Reversion',   'green',     'darkgreen'),
    (eth_rsi, btc_rsi, 'RSI Mean Reversion',  'purple',    'indigo'),
]

for row, (eth_r, btc_r, title, eth_color, btc_color) in enumerate(strategy_pairs):
    # ETH equity curve
    ax_eth = axes[row][0]
    if eth_r['trades'] > 0 and 'equity' in eth_r:
        eq = np.concatenate([[1.0], eth_r['equity']])
        ax_eth.plot(eq, color=eth_color, linewidth=2, label='ETH')
        ax_eth.axhline(1.0, color='gray', linestyle='--', alpha=0.5)
        pf_str = fmt_pf(eth_r['profit_factor'])
        ax_eth.set_title(
            f'{title} — ETH\n'
            f"Trades: {eth_r['trades']} | WR: {eth_r['win_rate']:.1%} | "
            f"PF: {pf_str}\nReturn: {eth_r['total_return']:+.1%} | "
            f"DD: {eth_r['max_drawdown']:.1%}",
            fontsize=8
        )
    else:
        ax_eth.text(0.5, 0.5, 'No trades', ha='center', va='center',
                    transform=ax_eth.transAxes)
        ax_eth.set_title(f'{title} — ETH\nNo trades generated', fontsize=8)

    ax_eth.set_ylabel('Equity multiplier')
    ax_eth.grid(alpha=0.3)

    # BTC equity curve
    ax_btc = axes[row][1]
    if btc_r['trades'] > 0 and 'equity' in btc_r:
        eq = np.concatenate([[1.0], btc_r['equity']])
        ax_btc.plot(eq, color=btc_color, linewidth=2, label='BTC')
        ax_btc.axhline(1.0, color='gray', linestyle='--', alpha=0.5)
        pf_str = fmt_pf(btc_r['profit_factor'])
        ax_btc.set_title(
            f'{title} — BTC\n'
            f"Trades: {btc_r['trades']} | WR: {btc_r['win_rate']:.1%} | "
            f"PF: {pf_str}\nReturn: {btc_r['total_return']:+.1%} | "
            f"DD: {btc_r['max_drawdown']:.1%}",
            fontsize=8
        )
    else:
        ax_btc.text(0.5, 0.5, 'No trades', ha='center', va='center',
                    transform=ax_btc.transAxes)
        ax_btc.set_title(f'{title} — BTC\nNo trades generated', fontsize=8)

    ax_btc.set_ylabel('Equity multiplier')
    ax_btc.grid(alpha=0.3)

plt.tight_layout()
chart_path = 'Week_5_Notebooks/results/day7b_bitcoin_validation.png'
plt.savefig(chart_path, dpi=150)
plt.close()
print(f"\n✅ Chart saved → {chart_path}")

print(f"\n{'='*80}")
print(f"BITCOIN VALIDATION COMPLETE")
print(f"{'='*80}\n")