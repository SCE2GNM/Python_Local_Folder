# [MODULE] Final Strategy Visualisation
# Week 5
#
# WHAT THIS SCRIPT DOES:
#   Runs full backtests for both ADX and RSI strategies with ALL
#   three risk guardrails applied simultaneously:
#     1. Per-trade stop-loss (ADX: 5%, RSI: 15%)
#     2. Daily loss limit (2% of account)
#     3. Maximum drawdown limit (15% from peak)
#
#   Produces 6-panel visualisation showing:
#     1. ETH price with ADX trade entry/exit markers
#     2. ADX indicator
#     3. ETH price with RSI trade entry/exit markers
#     4. RSI indicator
#     5. Combined equity curves (log scale)
#     6. Drawdown comparison
#
# EXIT COLOUR CODING:
#   Green  triangle up   = entry
#   Blue   triangle down = signal exit (ADX or RSI)
#   Red    triangle down = per-trade stop-loss
#   Orange triangle down = daily loss limit
#   Purple triangle down = max drawdown limit
#
# POSITION SIZING:
#   ADX: 12.41% Kelly  ($1,000 capital)
#   RSI: 15.00%        ($500 capital)

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from ta.trend import ADXIndicator
import os

# ---------------------------------------------------------------------------
# RISK GUARDRAIL CONSTANTS
# ---------------------------------------------------------------------------

DAILY_LOSS_LIMIT:    float = 999.0   # 2% of account value
MAX_DRAWDOWN_LIMIT:  float = 0.15   # 15% from peak

# ADX parameters
ADX_THRESHOLD:  int   = 20
ADX_PERIOD:     int   = 10
ADX_STOP_PCT:   float = 0.05
ADX_KELLY:      float = 0.1241
ADX_CAPITAL:    float = 1000.0

# RSI parameters
RSI_PERIOD:     int   = 14
RSI_OVERSOLD:   float = 43.0
RSI_EXIT:       float = 48.0
RSI_MA_FILTER:  int   = 120
RSI_STOP_PCT:   float = 0.15
RSI_KELLY:      float = 0.15
RSI_CAPITAL:    float = 500.0


# ---------------------------------------------------------------------------
# [FUNCTION] calculate_rsi
# ---------------------------------------------------------------------------

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """[FUNCTION] Calculate RSI using Wilder's smoothing."""
    delta    = close.diff()
    gains    = delta.clip(lower=0)
    losses   = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


# ---------------------------------------------------------------------------
# [FUNCTION] run_adx_with_guardrails
# ---------------------------------------------------------------------------

def run_adx_with_guardrails(
    df:          pd.DataFrame,
    threshold:   int   = ADX_THRESHOLD,
    period:      int   = ADX_PERIOD,
    stop_pct:    float = ADX_STOP_PCT,
    kelly:       float = ADX_KELLY,
    capital:     float = ADX_CAPITAL,
    daily_limit: float = DAILY_LOSS_LIMIT,
    max_dd:      float = MAX_DRAWDOWN_LIMIT,
) -> dict:
    """
    [FUNCTION] ADX backtest with all three risk guardrails.

    Guardrails applied in priority order each bar:
      1. Max drawdown check — halt all trading if breached
      2. Daily loss check   — block new entries if breached today
      3. Per-trade stop     — exit open position if breached

    Args:
        df          : OHLCV DataFrame
        threshold   : ADX trending threshold
        period      : ADX lookback window
        stop_pct    : per-trade stop-loss distance
        kelly       : position size as fraction of account
        capital     : starting capital in USD
        daily_limit : max daily loss as fraction of account
        max_dd      : max drawdown from peak before halting

    Returns:
        dict with trades list, equity curve, and marker arrays
    """

    # Calculate indicators
    adx_ind = ADXIndicator(df['High'], df['Low'], df['Close'], window=period)
    df      = df.copy()
    df['ADX']    = adx_ind.adx()
    df['+DI']    = adx_ind.adx_pos()
    df['-DI']    = adx_ind.adx_neg()
    df['Signal'] = (df['ADX'] >= threshold) & (df['+DI'] > df['-DI'])

    # State variables
    position:         int   = 0       # 0=FLAT, 1=LONG
    entry_price:      float = 0.0
    stop_price:       float = 0.0
    account:          float = capital
    peak_account:     float = capital
    session_start:    float = capital  # account value at start of each day
    trading_halted:   bool  = False    # max drawdown breach
    daily_loss_block: bool  = False    # daily loss breach

    trades:       list = []
    # Arrays for chart markers
    entry_dates:      list = []
    entry_prices:     list = []
    signal_exit_dates:  list = []
    signal_exit_prices: list = []
    stop_exit_dates:    list = []
    stop_exit_prices:   list = []
    daily_exit_dates:   list = []
    daily_exit_prices:  list = []
    maxdd_exit_dates:   list = []
    maxdd_exit_prices:  list = []

    # Daily equity curve
    daily_equity: list = [capital]

    closes  = df['Close'].values
    highs   = df['High'].values
    lows    = df['Low'].values
    signals = df['Signal'].values
    dates   = df.index

    for i in range(1, len(df)):
        close:  float = closes[i]
        low:    float = lows[i]
        signal: bool  = signals[i]

        # Reset daily tracking at start of each new day
        session_start    = account
        daily_loss_block = False

        # --- GUARDRAIL 1: Max drawdown check ---
        peak_account = max(peak_account, account)
        dd_from_peak = (account - peak_account) / peak_account

        if dd_from_peak <= -max_dd:
            if position == 1:
                # Exit open position
                trade_return = (close - entry_price) / entry_price
                pnl          = (account * kelly) * trade_return
                account     += pnl
                trades.append({
                    'entry_date':  dates[i-1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                    'exit_reason': 'MAX_DRAWDOWN',
                })
                maxdd_exit_dates.append(dates[i])
                maxdd_exit_prices.append(close)
                position = 0; entry_price = 0.0; stop_price = 0.0

            trading_halted = True

        if trading_halted:
            daily_equity.append(account)
            continue

        # --- GUARDRAIL 2: Daily loss check ---
        current_value = account
        if position == 1:
            mtm_return    = (close - entry_price) / entry_price
            current_value = account + (account * kelly) * mtm_return

        daily_loss = (current_value - session_start) / session_start
        if daily_loss <= -daily_limit:
            if position == 1:
                trade_return = (close - entry_price) / entry_price
                pnl          = (account * kelly) * trade_return
                account     += pnl
                trades.append({
                    'entry_date':  dates[i-1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                    'exit_reason': 'DAILY_LOSS',
                })
                daily_exit_dates.append(dates[i])
                daily_exit_prices.append(close)
                position = 0; entry_price = 0.0; stop_price = 0.0

            daily_loss_block = True

        if position == 1:
            # --- GUARDRAIL 3: Per-trade stop-loss ---
            if low <= stop_price:
                trade_return = (stop_price - entry_price) / entry_price
                pnl          = (account * kelly) * trade_return
                account     += pnl
                trades.append({
                    'entry_date':  dates[i-1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      trade_return,
                    'exit_reason': 'STOP_LOSS',
                })
                stop_exit_dates.append(dates[i])
                stop_exit_prices.append(stop_price)
                position = 0; entry_price = 0.0; stop_price = 0.0

            # --- Signal exit ---
            elif not signal:
                trade_return = (close - entry_price) / entry_price
                pnl          = (account * kelly) * trade_return
                account     += pnl
                trades.append({
                    'entry_date':  dates[i-1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                    'exit_reason': 'ADX_EXIT',
                })
                signal_exit_dates.append(dates[i])
                signal_exit_prices.append(close)
                position = 0; entry_price = 0.0; stop_price = 0.0

        # --- Entry (only if not blocked) ---
        elif position == 0 and signal and not daily_loss_block:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1
            entry_dates.append(dates[i])
            entry_prices.append(close)

        daily_equity.append(account)

    return {
        'trades':              pd.DataFrame(trades),
        'daily_equity':        np.array(daily_equity),
        'df':                  df,
        'entry_dates':         entry_dates,
        'entry_prices':        entry_prices,
        'signal_exit_dates':   signal_exit_dates,
        'signal_exit_prices':  signal_exit_prices,
        'stop_exit_dates':     stop_exit_dates,
        'stop_exit_prices':    stop_exit_prices,
        'daily_exit_dates':    daily_exit_dates,
        'daily_exit_prices':   daily_exit_prices,
        'maxdd_exit_dates':    maxdd_exit_dates,
        'maxdd_exit_prices':   maxdd_exit_prices,
    }


# ---------------------------------------------------------------------------
# [FUNCTION] run_rsi_with_guardrails
# ---------------------------------------------------------------------------

def run_rsi_with_guardrails(
    df:          pd.DataFrame,
    rsi_period:  int   = RSI_PERIOD,
    oversold:    float = RSI_OVERSOLD,
    exit_level:  float = RSI_EXIT,
    ma_filter:   int   = RSI_MA_FILTER,
    stop_pct:    float = RSI_STOP_PCT,
    kelly:       float = RSI_KELLY,
    capital:     float = RSI_CAPITAL,
    daily_limit: float = DAILY_LOSS_LIMIT,
    max_dd:      float = MAX_DRAWDOWN_LIMIT,
) -> dict:
    """
    [FUNCTION] RSI backtest with all three risk guardrails.

    Same guardrail logic as ADX but with RSI-specific
    entry/exit signals and parameters.
    """

    df = df.copy()
    df['RSI']       = calculate_rsi(df['Close'], period=rsi_period)
    df['MA_filter'] = df['Close'].rolling(window=ma_filter).mean()
    df.dropna(inplace=True)

    df['Entry_Signal'] = (
        (df['RSI'] < oversold) &
        (df['Close'] > df['MA_filter'])
    )
    df['Exit_Signal'] = df['RSI'] > exit_level

    position:         int   = 0
    entry_price:      float = 0.0
    stop_price:       float = 0.0
    account:          float = capital
    peak_account:     float = capital
    session_start:    float = capital
    trading_halted:   bool  = False
    daily_loss_block: bool  = False

    trades:             list = []
    entry_dates:        list = []
    entry_prices:       list = []
    signal_exit_dates:  list = []
    signal_exit_prices: list = []
    stop_exit_dates:    list = []
    stop_exit_prices:   list = []
    daily_exit_dates:   list = []
    daily_exit_prices:  list = []
    maxdd_exit_dates:   list = []
    maxdd_exit_prices:  list = []
    daily_equity:       list = [capital]

    closes        = df['Close'].values
    lows          = df['Low'].values
    entry_signals = df['Entry_Signal'].values
    exit_signals  = df['Exit_Signal'].values
    dates         = df.index

    for i in range(1, len(df)):
        close:     float = closes[i]
        low:       float = lows[i]
        entry_sig: bool  = entry_signals[i]
        exit_sig:  bool  = exit_signals[i]

        session_start    = account
        daily_loss_block = False

        # Guardrail 1: Max drawdown
        peak_account = max(peak_account, account)
        dd_from_peak = (account - peak_account) / peak_account

        if dd_from_peak <= -max_dd:
            if position == 1:
                trade_return = (close - entry_price) / entry_price
                pnl          = (account * kelly) * trade_return
                account     += pnl
                trades.append({
                    'entry_date':  dates[i-1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                    'exit_reason': 'MAX_DRAWDOWN',
                })
                maxdd_exit_dates.append(dates[i])
                maxdd_exit_prices.append(close)
                position = 0; entry_price = 0.0; stop_price = 0.0

            trading_halted = True

        if trading_halted:
            daily_equity.append(account)
            continue

        # Guardrail 2: Daily loss
        current_value = account
        if position == 1:
            mtm_return    = (close - entry_price) / entry_price
            current_value = account + (account * kelly) * mtm_return

        daily_loss = (current_value - session_start) / session_start
        if daily_loss <= -daily_limit:
            if position == 1:
                trade_return = (close - entry_price) / entry_price
                pnl          = (account * kelly) * trade_return
                account     += pnl
                trades.append({
                    'entry_date':  dates[i-1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                    'exit_reason': 'DAILY_LOSS',
                })
                daily_exit_dates.append(dates[i])
                daily_exit_prices.append(close)
                position = 0; entry_price = 0.0; stop_price = 0.0

            daily_loss_block = True

        if position == 1:
            # Guardrail 3: Per-trade stop
            if low <= stop_price:
                trade_return = (stop_price - entry_price) / entry_price
                pnl          = (account * kelly) * trade_return
                account     += pnl
                trades.append({
                    'entry_date':  dates[i-1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  stop_price,
                    'return':      trade_return,
                    'exit_reason': 'STOP_LOSS',
                })
                stop_exit_dates.append(dates[i])
                stop_exit_prices.append(stop_price)
                position = 0; entry_price = 0.0; stop_price = 0.0

            # RSI exit
            elif exit_sig:
                trade_return = (close - entry_price) / entry_price
                pnl          = (account * kelly) * trade_return
                account     += pnl
                trades.append({
                    'entry_date':  dates[i-1],
                    'entry_price': entry_price,
                    'exit_date':   dates[i],
                    'exit_price':  close,
                    'return':      trade_return,
                    'exit_reason': 'RSI_EXIT',
                })
                signal_exit_dates.append(dates[i])
                signal_exit_prices.append(close)
                position = 0; entry_price = 0.0; stop_price = 0.0

        elif position == 0 and entry_sig and not daily_loss_block:
            entry_price = close
            stop_price  = entry_price * (1 - stop_pct)
            position    = 1
            entry_dates.append(dates[i])
            entry_prices.append(close)

        daily_equity.append(account)

    return {
        'trades':              pd.DataFrame(trades) if trades else pd.DataFrame(),
        'daily_equity':        np.array(daily_equity),
        'df':                  df,
        'entry_dates':         entry_dates,
        'entry_prices':        entry_prices,
        'signal_exit_dates':   signal_exit_dates,
        'signal_exit_prices':  signal_exit_prices,
        'stop_exit_dates':     stop_exit_dates,
        'stop_exit_prices':    stop_exit_prices,
        'daily_exit_dates':    daily_exit_dates,
        'daily_exit_prices':   daily_exit_prices,
        'maxdd_exit_dates':    maxdd_exit_dates,
        'maxdd_exit_prices':   maxdd_exit_prices,
    }


# ---------------------------------------------------------------------------
# FETCH DATA AND RUN BACKTESTS
# ---------------------------------------------------------------------------

print("\nFetching ETH-USD data...")
raw = yf.download('ETH-USD', start='2018-01-01', interval='1d', progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.droplevel(1)
df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.dropna(inplace=True)
print(f"Data: {df.index[0].date()} → {df.index[-1].date()} ({len(df):,} days)")

years = (df.index[-1] - df.index[0]).days / 365.25

print("\nRunning ADX backtest with guardrails...")
adx_result = run_adx_with_guardrails(df)

print("Running RSI backtest with guardrails...")
rsi_result = run_rsi_with_guardrails(df)


# ---------------------------------------------------------------------------
# PRINT SUMMARY STATS
# ---------------------------------------------------------------------------

def print_summary(result: dict, label: str, kelly: float, capital: float) -> None:
    """Print strategy summary statistics."""
    trades = result['trades']
    equity = result['daily_equity']

    if len(trades) == 0:
        print(f"\n  {label}: No trades generated")
        return

    # Exit breakdown
    exit_counts = trades['exit_reason'].value_counts()

    # Daily equity metrics
    daily_returns = np.diff(equity) / equity[:-1]
    total_return  = equity[-1] / equity[0] - 1
    annual_return = (1 + total_return) ** (1 / years) - 1
    sharpe        = (daily_returns.mean() / daily_returns.std() * np.sqrt(365)
                     if daily_returns.std() > 0 else 0.0)
    downside      = daily_returns[daily_returns < 0]
    sortino       = (daily_returns.mean() / downside.std() * np.sqrt(365)
                     if len(downside) > 0 and downside.std() > 0 else 0.0)
    peak          = np.maximum.accumulate(equity)
    drawdown      = (equity - peak) / peak
    max_dd        = drawdown.min()
    calmar        = annual_return / abs(max_dd) if max_dd != 0 else 0.0

    winners = trades[trades['return'] > 0]
    losers  = trades[trades['return'] <= 0]
    win_rate      = len(winners) / len(trades)
    gross_profit  = winners['return'].sum() if len(winners) > 0 else 0.0
    gross_loss    = abs(losers['return'].sum()) if len(losers) > 0 else 1e-9
    profit_factor = gross_profit / gross_loss

    print(f"\n  {'='*65}")
    print(f"  {label}")
    print(f"  {'='*65}")
    print(f"  Capital:        ${capital:,.0f} | Kelly: {kelly:.1%}")
    print(f"  Total Trades:   {len(trades)}")
    print(f"  Win Rate:       {win_rate:.1%}")
    print(f"  Profit Factor:  {profit_factor:.3f}")
    print(f"  Final Account:  ${equity[-1]:,.2f} "
          f"({total_return:+.1%} total, {annual_return:+.1%}/yr)")
    print(f"  Max Drawdown:   {max_dd:.1%}")
    print(f"  Calmar:         {calmar:.3f}")
    print(f"  Sharpe:         {sharpe:.3f}")
    print(f"  Sortino:        {sortino:.3f}")
    print(f"\n  EXIT BREAKDOWN:")
    for reason, count in exit_counts.items():
        pct = count / len(trades) * 100
        print(f"    {reason:<20} {count:>4} trades ({pct:.1f}%)")


print(f"\n{'='*70}")
print(f"BACKTEST RESULTS WITH ALL THREE GUARDRAILS")
print(f"{'='*70}")

print_summary(adx_result, 'ADX 20/10 ETH', ADX_KELLY, ADX_CAPITAL)
print_summary(rsi_result, 'RSI Final ETH', RSI_KELLY, RSI_CAPITAL)


# ---------------------------------------------------------------------------
# PLOTS — 6 panel visualisation
# ---------------------------------------------------------------------------

print("\nGenerating visualisation...")
os.makedirs('Week_5_Notebooks/results', exist_ok=True)

fig = plt.figure(figsize=(20, 24))
fig.suptitle(
    'ETH Trading Strategies — Full Backtest Visualisation with Guardrails\n'
    'ADX 20/10 (1000 USD, 12.41% Kelly) | RSI 14/43/48 (500 USD, 15% Kelly)\n'
    'Guardrails: 5%/15% stop-loss | 15% max drawdown (daily loss limit removed)',
    fontsize=13, fontweight='bold', y=0.98
)

# Layout: 6 rows, 1 column with different heights
gs = fig.add_gridspec(
    6, 1,
    height_ratios=[3, 1.2, 3, 1.2, 2, 1.5],
    hspace=0.4
)

ax1 = fig.add_subplot(gs[0])  # ADX price chart
ax2 = fig.add_subplot(gs[1])  # ADX indicator
ax3 = fig.add_subplot(gs[2])  # RSI price chart
ax4 = fig.add_subplot(gs[3])  # RSI indicator
ax5 = fig.add_subplot(gs[4])  # Equity curves
ax6 = fig.add_subplot(gs[5])  # Drawdown

# Colour scheme
ENTRY_COLOR     = 'limegreen'
SIGNAL_COLOR    = 'dodgerblue'
STOP_COLOR      = 'red'
DAILY_COLOR     = 'orange'
MAXDD_COLOR     = 'purple'
MARKER_SIZE     = 80

# Legend patches
entry_patch  = mpatches.Patch(color=ENTRY_COLOR,  label='Entry')
signal_patch = mpatches.Patch(color=SIGNAL_COLOR, label='Signal exit (ADX/RSI)')
stop_patch   = mpatches.Patch(color=STOP_COLOR,   label='Stop-loss exit')
daily_patch  = mpatches.Patch(color=DAILY_COLOR,  label='Daily loss limit exit')
maxdd_patch  = mpatches.Patch(color=MAXDD_COLOR,  label='Max drawdown exit')


# ---------------------------------------------------------------------------
# PANEL 1: ADX Price Chart
# ---------------------------------------------------------------------------

adx_df = adx_result['df']

# Last 4 years for clarity
cutoff    = adx_df.index[-1] - pd.DateOffset(years=4)
plot_adx  = adx_df[adx_df.index >= cutoff]

ax1.plot(plot_adx.index, plot_adx['Close'],
         color='black', linewidth=1, label='ETH Close', zorder=2)

# Shade LONG periods
in_pos   = False
pos_start = None
for i in range(1, len(plot_adx)):
    date   = plot_adx.index[i]
    signal = plot_adx['Signal'].iloc[i]
    if signal and not in_pos:
        pos_start = date
        in_pos    = True
    elif not signal and in_pos:
        ax1.axvspan(pos_start, date, alpha=0.08,
                    color='steelblue', zorder=1)
        in_pos = False

# Plot markers — filter to plot range
def filter_markers(dates, prices, start):
    filtered_d, filtered_p = [], []
    for d, p in zip(dates, prices):
        if d >= start:
            filtered_d.append(d)
            filtered_p.append(p)
    return filtered_d, filtered_p

fd, fp = filter_markers(adx_result['entry_dates'],
                         adx_result['entry_prices'], cutoff)
if fd:
    ax1.scatter(fd, fp, color=ENTRY_COLOR, marker='^',
                s=MARKER_SIZE, zorder=5, label='Entry')

fd, fp = filter_markers(adx_result['signal_exit_dates'],
                         adx_result['signal_exit_prices'], cutoff)
if fd:
    ax1.scatter(fd, fp, color=SIGNAL_COLOR, marker='v',
                s=MARKER_SIZE, zorder=5, label='ADX exit')

fd, fp = filter_markers(adx_result['stop_exit_dates'],
                         adx_result['stop_exit_prices'], cutoff)
if fd:
    ax1.scatter(fd, fp, color=STOP_COLOR, marker='v',
                s=MARKER_SIZE, zorder=5, label='Stop-loss')

fd, fp = filter_markers(adx_result['daily_exit_dates'],
                         adx_result['daily_exit_prices'], cutoff)
if fd:
    ax1.scatter(fd, fp, color=DAILY_COLOR, marker='v',
                s=MARKER_SIZE, zorder=5, label='Daily limit')

fd, fp = filter_markers(adx_result['maxdd_exit_dates'],
                         adx_result['maxdd_exit_prices'], cutoff)
if fd:
    ax1.scatter(fd, fp, color=MAXDD_COLOR, marker='v',
                s=MARKER_SIZE, zorder=5, label='Max DD')

ax1.set_title('ADX Strategy — ETH Price with Trade Markers (last 4 years)\n'
              'Blue shading = periods in LONG position',
              fontsize=10)
ax1.set_ylabel('Price (USD)')
ax1.legend(handles=[entry_patch, signal_patch, stop_patch,
                    daily_patch, maxdd_patch],
           fontsize=8, loc='upper left')
ax1.grid(alpha=0.3)


# ---------------------------------------------------------------------------
# PANEL 2: ADX Indicator
# ---------------------------------------------------------------------------

ax2.plot(plot_adx.index, plot_adx['ADX'],
         color='steelblue', linewidth=1.5, label='ADX')
ax2.plot(plot_adx.index, plot_adx['+DI'],
         color='green', linewidth=1, alpha=0.7, label='+DI')
ax2.plot(plot_adx.index, plot_adx['-DI'],
         color='red', linewidth=1, alpha=0.7, label='-DI')
ax2.axhline(ADX_THRESHOLD, color='orange', linestyle='--',
            linewidth=1.5, label=f'Threshold ({ADX_THRESHOLD})')
ax2.fill_between(plot_adx.index, plot_adx['ADX'], ADX_THRESHOLD,
                 where=plot_adx['ADX'] >= ADX_THRESHOLD,
                 alpha=0.2, color='steelblue')
ax2.set_title('ADX Indicator', fontsize=9)
ax2.set_ylabel('ADX / DI')
ax2.set_ylim(0, 80)
ax2.legend(fontsize=7, loc='upper right')
ax2.grid(alpha=0.3)


# ---------------------------------------------------------------------------
# PANEL 3: RSI Price Chart
# ---------------------------------------------------------------------------

rsi_df   = rsi_result['df']
plot_rsi = rsi_df[rsi_df.index >= cutoff]

ax3.plot(plot_rsi.index, plot_rsi['Close'],
         color='black', linewidth=1, label='ETH Close', zorder=2)
ax3.plot(plot_rsi.index, plot_rsi['MA_filter'],
         color='orange', linewidth=1.5, linestyle='--',
         alpha=0.8, label=f'{RSI_MA_FILTER}MA (regime filter)')

fd, fp = filter_markers(rsi_result['entry_dates'],
                         rsi_result['entry_prices'], cutoff)
if fd:
    ax3.scatter(fd, fp, color=ENTRY_COLOR, marker='^',
                s=MARKER_SIZE, zorder=5)

fd, fp = filter_markers(rsi_result['signal_exit_dates'],
                         rsi_result['signal_exit_prices'], cutoff)
if fd:
    ax3.scatter(fd, fp, color=SIGNAL_COLOR, marker='v',
                s=MARKER_SIZE, zorder=5)

fd, fp = filter_markers(rsi_result['stop_exit_dates'],
                         rsi_result['stop_exit_prices'], cutoff)
if fd:
    ax3.scatter(fd, fp, color=STOP_COLOR, marker='v',
                s=MARKER_SIZE, zorder=5)

fd, fp = filter_markers(rsi_result['daily_exit_dates'],
                         rsi_result['daily_exit_prices'], cutoff)
if fd:
    ax3.scatter(fd, fp, color=DAILY_COLOR, marker='v',
                s=MARKER_SIZE, zorder=5)

fd, fp = filter_markers(rsi_result['maxdd_exit_dates'],
                         rsi_result['maxdd_exit_prices'], cutoff)
if fd:
    ax3.scatter(fd, fp, color=MAXDD_COLOR, marker='v',
                s=MARKER_SIZE, zorder=5)

ax3.set_title('RSI Strategy — ETH Price with Trade Markers (last 4 years)',
              fontsize=10)
ax3.set_ylabel('Price (USD)')
ax3.legend(handles=[entry_patch, signal_patch, stop_patch,
                    daily_patch, maxdd_patch,
                    plt.Line2D([0], [0], color='orange',
                               linestyle='--', label=f'{RSI_MA_FILTER}MA')],
           fontsize=8, loc='upper left')
ax3.grid(alpha=0.3)


# ---------------------------------------------------------------------------
# PANEL 4: RSI Indicator
# ---------------------------------------------------------------------------

ax4.plot(plot_rsi.index, plot_rsi['RSI'],
         color='purple', linewidth=1.5, label='RSI (14)')
ax4.axhline(RSI_OVERSOLD, color='green', linestyle='--',
            linewidth=1.5, label=f'Oversold (<{RSI_OVERSOLD})')
ax4.axhline(RSI_EXIT, color='dodgerblue', linestyle='--',
            linewidth=1.5, label=f'Exit (>{RSI_EXIT})')
ax4.axhline(30, color='gray', linestyle=':', alpha=0.5,
            label='Traditional oversold (30)')
ax4.fill_between(plot_rsi.index, plot_rsi['RSI'], RSI_OVERSOLD,
                 where=plot_rsi['RSI'] < RSI_OVERSOLD,
                 alpha=0.3, color='green')
ax4.set_ylim(0, 100)
ax4.set_title('RSI Indicator', fontsize=9)
ax4.set_ylabel('RSI')
ax4.legend(fontsize=7, loc='upper right')
ax4.grid(alpha=0.3)


# ---------------------------------------------------------------------------
# PANEL 5: Combined Equity Curves
# ---------------------------------------------------------------------------

adx_equity = adx_result['daily_equity']
rsi_equity = rsi_result['daily_equity']

# Align RSI equity to ADX date range (RSI starts later due to MA warmup)
# Pad RSI equity curve from front with its starting capital
rsi_df_len = len(rsi_result['df'])
adx_df_len = len(adx_result['df'])
pad_len    = adx_df_len - rsi_df_len

if pad_len > 0:
    rsi_equity_padded = np.concatenate([
        np.full(pad_len, rsi_equity[0]), rsi_equity
    ])
else:
    rsi_equity_padded = rsi_equity

# Normalise to starting capital for combined chart
adx_norm = adx_equity / ADX_CAPITAL
rsi_norm = rsi_equity_padded / RSI_CAPITAL

# Buy and hold ETH
bh_eth = df['Close'].values / df['Close'].values[0]

ax5.plot(adx_norm, color='steelblue', linewidth=2,
         label=f"ADX ETH (${adx_equity[-1]:,.0f} "
               f"from ${ADX_CAPITAL:,.0f})")
ax5.plot(rsi_norm, color='purple', linewidth=2,
         label=f"RSI ETH (${rsi_equity[-1]:,.0f} "
               f"from ${RSI_CAPITAL:,.0f})")
ax5.plot(bh_eth, color='gray', linewidth=1.5, linestyle='--',
         alpha=0.6, label='Buy & Hold ETH')
ax5.axhline(1.0, color='gray', linestyle=':', alpha=0.4)
ax5.set_title('Equity Curves — Both Strategies (log scale, normalised to 1.0)',
              fontsize=10)
ax5.set_ylabel('Portfolio multiplier')
ax5.set_yscale('log')
ax5.legend(fontsize=9)
ax5.grid(alpha=0.3)


# ---------------------------------------------------------------------------
# PANEL 6: Drawdown Comparison
# ---------------------------------------------------------------------------

def calc_drawdown(equity):
    peak = np.maximum.accumulate(equity)
    return (equity - peak) / peak * 100

adx_dd = calc_drawdown(adx_equity)
rsi_dd = calc_drawdown(rsi_equity_padded)
bh_dd  = calc_drawdown(bh_eth)

ax6.fill_between(range(len(adx_dd)), adx_dd, 0,
                 alpha=0.4, color='steelblue', label='ADX ETH')
ax6.fill_between(range(len(rsi_dd)), rsi_dd, 0,
                 alpha=0.4, color='purple', label='RSI ETH')
ax6.plot(bh_dd, color='gray', linewidth=1, linestyle='--',
         alpha=0.6, label='Buy & Hold ETH')
ax6.axhline(0, color='gray', linestyle=':', alpha=0.4)
ax6.axhline(-MAX_DRAWDOWN_LIMIT * 100, color='red', linestyle='--',
            linewidth=1.5, alpha=0.7,
            label=f'Max DD guardrail ({MAX_DRAWDOWN_LIMIT*100:.0f}%)')
ax6.set_title('Drawdown Comparison (%)', fontsize=10)
ax6.set_ylabel('Drawdown %')
ax6.legend(fontsize=9)
ax6.grid(alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.97])
chart_path = 'Week_5_Notebooks/results/final_strategy_visualisation.png'
plt.savefig(chart_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"\n✅ Chart saved → {chart_path}")

print(f"\n{'='*70}")
print(f"VISUALISATION COMPLETE")
print(f"{'='*70}\n")
