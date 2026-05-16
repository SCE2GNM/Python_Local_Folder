# [IMPORT] streamlit - turns this Python script into a web dashboard
import streamlit as st

# [IMPORT] pandas for reading and manipulating our log files
import pandas as pd

# [IMPORT] plotly for interactive charts
import plotly.graph_objects as go

# [IMPORT] json for reading performance and signal logs
import json

# [IMPORT] pathlib for file path handling
from pathlib import Path

# [IMPORT] datetime for timestamps
from datetime import datetime

# [IMPORT] os for file checking
import os

# ============================================================
# PAGE CONFIGURATION
# ============================================================
# This must be the first Streamlit command in the script

# [FUNCTION CALL] Configure the dashboard page
st.set_page_config(
    page_title="ETH Trading Dashboard",
    page_icon="📈",
    layout="wide"  # Use full browser width
)

# ============================================================
# FILE PATHS
# ============================================================

# [OBJECT - Path] Path to logs folder
logs_dir = Path('logs')

# [VARIABLE - Path] Trade log CSV
TRADE_LOG_PATH = logs_dir / 'trade_log.csv'

# [VARIABLE - Path] Performance JSON
PERFORMANCE_LOG_PATH = logs_dir / 'performance.json'

# [VARIABLE - string] Today's date for signal log
today = datetime.now().strftime('%Y-%m-%d')

# [VARIABLE - Path] Today's signal log
SIGNAL_LOG_PATH = logs_dir / f'signals_{today}.json'

# ============================================================
# DATA LOADING FUNCTIONS
# ============================================================

def load_trade_log():
    """
    Load the trade log CSV into a pandas DataFrame.
    Returns empty DataFrame if file doesn't exist yet.
    """
    if not TRADE_LOG_PATH.exists():
        return pd.DataFrame()
    
    df = pd.read_csv(TRADE_LOG_PATH)
    return df

def load_performance():
    """
    Load the performance JSON file.
    Returns default zeros if file doesn't exist yet.
    """
    if not PERFORMANCE_LOG_PATH.exists():
        return {
            'total_trades':    0,
            'winning_trades':  0,
            'losing_trades':   0,
            'total_pnl_usd':   0.0,
            'best_trade_usd':  0.0,
            'worst_trade_usd': 0.0,
            'win_rate_pct':    0.0,
            'last_updated':    'Never'
        }
    
    with open(PERFORMANCE_LOG_PATH, 'r') as f:
        return json.load(f)

def load_signals():
    """
    Load today's signal log JSON.
    Returns empty list if no signals yet today.
    """
    if not SIGNAL_LOG_PATH.exists():
        return []
    
    with open(SIGNAL_LOG_PATH, 'r') as f:
        return json.load(f)

# ============================================================
# DASHBOARD HEADER
# ============================================================

# [FUNCTION CALL] Main title
st.title("📈 ETH/USDT Live Trading Dashboard")
st.caption(f"Strategy: ADX 20/10 | Timeframe: 1-minute (illustration) | "
           f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

# [FUNCTION CALL] Horizontal divider
st.divider()

# ============================================================
# LOAD ALL DATA
# ============================================================

# [VARIABLE] Load all data sources
performance = load_performance()
trades_df   = load_trade_log()
signals     = load_signals()

# ============================================================
# ROW 1: KEY METRICS
# ============================================================
# st.columns splits the page into side-by-side panels
# Think of it like columns in a newspaper

# [FUNCTION CALL] Create 5 equal columns for metric cards
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="Total Trades",
        value=performance['total_trades']
    )

with col2:
    st.metric(
        label="Win Rate",
        value=f"{performance['win_rate_pct']}%"
    )

with col3:
    # [VARIABLE] Format P&L with colour indicator
    total_pnl = performance['total_pnl_usd']
    st.metric(
        label="Total P&L",
        value=f"${total_pnl:+,.2f}",
        # delta shows green arrow if positive, red if negative
        delta=f"${total_pnl:+,.2f}"
    )

with col4:
    st.metric(
        label="Best Trade",
        value=f"${performance['best_trade_usd']:+,.2f}"
    )

with col5:
    st.metric(
        label="Worst Trade",
        value=f"${performance['worst_trade_usd']:+,.2f}"
    )

st.divider()

# ============================================================
# ROW 2: CURRENT SIGNAL + LIVE ADX
# ============================================================

col_signal, col_adx = st.columns([1, 2])

with col_signal:
    st.subheader("Current Signal")
    
    if signals:
        # [VARIABLE] Get the most recent signal
        latest = signals[-1]
        signal = latest['signal']
        
        # [CONDITIONAL] Display signal with appropriate styling
        if signal == 'LONG':
            st.success(f"🟢 LONG — BUY ETH")
        elif signal == 'BEARISH':
            st.error(f"🔴 BEARISH — NO POSITION")
        else:
            st.warning(f"⚪ CHOPPY — STAY IN CASH")
        
        # [PRINT] Show ADX values
        st.write(f"**ADX:** {latest['adx']}")
        st.write(f"**+DI:** {latest['plus_di']}")
        st.write(f"**-DI:** {latest['minus_di']}")
        st.write(f"**Time:** {latest['time']}")
        st.write(f"**Position:** {latest['position_state']}")
    
    else:
        st.info("No signals logged today yet. Run the trading bot first.")

with col_adx:
    st.subheader("ADX History (Today)")
    
    if signals:
        # [DATAFRAME] Convert signal list to DataFrame for charting
        sig_df = pd.DataFrame(signals)
        
        # [OBJECT] Create plotly figure
        fig = go.Figure()
        
        # [METHOD] Add ADX line
        fig.add_trace(go.Scatter(
            x=sig_df['time'],
            y=sig_df['adx'],
            name='ADX',
            line=dict(color='yellow', width=2)
        ))
        
        # [METHOD] Add +DI line
        fig.add_trace(go.Scatter(
            x=sig_df['time'],
            y=sig_df['plus_di'],
            name='+DI',
            line=dict(color='green', width=1)
        ))
        
        # [METHOD] Add -DI line
        fig.add_trace(go.Scatter(
            x=sig_df['time'],
            y=sig_df['minus_di'],
            name='-DI',
            line=dict(color='red', width=1)
        ))
        
        # [METHOD] Add horizontal threshold line at ADX=20
        fig.add_hline(
            y=20,
            line_dash="dash",
            line_color="white",
            annotation_text="ADX Threshold (20)"
        )
        
        # [METHOD] Style the chart
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            height=250,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation='h')
        )
        
        # [FUNCTION CALL] Render chart in dashboard
        st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info("No signal data yet today.")

st.divider()

# ============================================================
# ROW 3: CUMULATIVE P&L CHART
# ============================================================

st.subheader("Cumulative P&L Over Time")

if not trades_df.empty:
    
    # [METHOD] Calculate running cumulative P&L
    # cumsum() = cumulative sum — adds each trade's P&L to the running total
    trades_df['cumulative_pnl'] = trades_df['pnl_usd'].cumsum()
    
    # [VARIABLE] Add a trade number column for x-axis
    trades_df['trade_number'] = range(1, len(trades_df) + 1)
    
    # [OBJECT] Create plotly figure
    fig_pnl = go.Figure()
    
    # [METHOD] Add cumulative P&L line
    fig_pnl.add_trace(go.Scatter(
        x=trades_df['trade_number'],
        y=trades_df['cumulative_pnl'],
        mode='lines+markers',
        name='Cumulative P&L',
        line=dict(color='cyan', width=2),
        marker=dict(size=8),
        # [PARAMETER] Show trade details on hover
        hovertemplate=(
            'Trade %{x}<br>'
            'P&L: $%{y:+,.2f}<br>'
            '<extra></extra>'
        )
    ))
    
    # [METHOD] Add zero line for reference
    fig_pnl.add_hline(y=0, line_dash="dash", line_color="white")
    
    # [METHOD] Colour the area under the line
    # Green if above zero, red if below
    fig_pnl.add_trace(go.Scatter(
        x=trades_df['trade_number'],
        y=trades_df['cumulative_pnl'],
        fill='tozeroy',
        fillcolor='rgba(0,255,0,0.1)' if trades_df['cumulative_pnl'].iloc[-1] >= 0
                  else 'rgba(255,0,0,0.1)',
        line=dict(width=0),
        showlegend=False
    ))
    
    # [METHOD] Style the chart
    fig_pnl.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title='Trade Number',
        yaxis_title='Cumulative P&L ($)'
    )
    
    st.plotly_chart(fig_pnl, use_container_width=True)

else:
    st.info("No trades logged yet. Run the trading bot to generate data.")

st.divider()

# ============================================================
# ROW 4: TRADE HISTORY TABLE
# ============================================================

st.subheader("Trade History")

if not trades_df.empty:
    
    # [METHOD] Format the DataFrame for display
    display_df = trades_df[[
        'session_date', 'entry_time', 'exit_time',
        'entry_price', 'exit_price',
        'pnl_usd', 'pnl_pct', 'duration_minutes', 'exit_reason'
    ]].copy()
    
    # [METHOD] Rename columns for readability
    display_df.columns = [
        'Date', 'Entry Time', 'Exit Time',
        'Entry Price', 'Exit Price',
        'P&L ($)', 'P&L (%)', 'Duration (min)', 'Exit Reason'
    ]
    
    # [FUNCTION CALL] Render the table with colour coding
    # Positive P&L rows highlighted green, negative red
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
    
    # [PRINT] Show summary below table
    st.caption(f"Showing {len(display_df)} trades | "
               f"Last updated: {performance['last_updated']}")

else:
    st.info("No trades to display yet.")

# ============================================================
# AUTO REFRESH
# ============================================================

st.divider()

# [FUNCTION CALL] Add manual refresh button
if st.button("🔄 Refresh Dashboard"):
    st.rerun()

# [PRINT] Footer
st.caption("⚠️ Paper trading only — no real money at risk | "
           "ADX 20/10 optimised for daily candles, "
           "running on 1-minute candles for illustration purposes only")