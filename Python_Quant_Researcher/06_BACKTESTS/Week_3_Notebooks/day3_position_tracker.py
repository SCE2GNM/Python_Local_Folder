# [IMPORT] asyncio for running asynchronous WebSocket connection
import asyncio

# [IMPORT] websockets for stable WebSocket connection to Binance
import websockets

# [IMPORT] json to decode Binance messages
import json

# [IMPORT] pandas for storing candles and calculating ADX
import pandas as pd

# [IMPORT] ADXIndicator from the ta library (same as Week 2)
from ta.trend import ADXIndicator

# [IMPORT] deque - rolling buffer with automatic size limit
from collections import deque

# [IMPORT] Binance REST client for fetching initial historical data
from binance.client import Client

# [IMPORT] Load API keys from .env file
from dotenv import load_dotenv

# [IMPORT] os to read environment variables
import os

# [IMPORT] datetime for readable timestamps
from datetime import datetime

# [FUNCTION CALL] Load keys from .env
load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

# [VARIABLE - string] Trading pair to monitor
SYMBOL = 'ETHUSDT'

# [VARIABLE - int] Your optimised ADX period from Week 2
ADX_PERIOD = 10

# [VARIABLE - int] Your optimised ADX threshold from Week 2
ADX_THRESHOLD = 20

# [VARIABLE - int] Rolling candle buffer size
LOOKBACK = 100

# [VARIABLE - float] Simulated position size in ETH
# This is paper trading — no real money moves
POSITION_SIZE_ETH = 1.0

# ============================================================
# SETUP
# ============================================================

# [OBJECT] Binance REST client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'))

# [VARIABLE - string] WebSocket URL for 1-minute ETH/USDT klines
URI = "wss://stream.binance.com:9443/ws/ethusdt@kline_1m"

# [OBJECT - deque] Rolling buffer of the last 100 candles
candle_buffer = deque(maxlen=LOOKBACK)

# ============================================================
# POSITION TRACKER STATE
# ============================================================
# These variables track the current state of our simulated position.
# Think of this as the trading journal — it remembers where we are.

# [VARIABLE - string] Current position state
# 'FLAT'  = no position, holding cash
# 'LONG'  = holding ETH, waiting to sell
position_state = 'FLAT'

# [VARIABLE - float] Price we entered the position at (None if flat)
entry_price = None

# [VARIABLE - string] Time we entered the position (None if flat)
entry_time = None

# [VARIABLE - string] What the previous signal was
# Used to detect when signal CHANGES (e.g. CHOPPY → LONG)
previous_signal = None

# [LIST] Log of all completed trades this session
trade_log = []

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calculate_adx(buffer):
    """Calculate ADX on the current candle buffer."""
    df = pd.DataFrame(list(buffer))
    
    adx_indicator = ADXIndicator(
        high=df['high'],
        low=df['low'],
        close=df['close'],
        window=ADX_PERIOD
    )
    
    adx      = adx_indicator.adx().iloc[-1]
    plus_di  = adx_indicator.adx_pos().iloc[-1]
    minus_di = adx_indicator.adx_neg().iloc[-1]
    
    return adx, plus_di, minus_di

def determine_signal(adx, plus_di, minus_di):
    """Apply Week 2 strategy rules to live ADX values."""
    trending = adx >= ADX_THRESHOLD
    bullish  = plus_di > minus_di
    
    if trending and bullish:
        return "LONG"
    elif trending and not bullish:
        return "BEARISH"
    else:
        return "CHOPPY"

def open_position(price, time):
    """
    Record opening a new LONG position.
    
    Think of this like pressing 'BUY' on a trading platform —
    we record the price and time so we can calculate P&L later.
    """
    global position_state, entry_price, entry_time
    
    # [VARIABLE] Update position state to LONG
    position_state = 'LONG'
    
    # [VARIABLE] Store entry price for P&L calculation
    entry_price = price
    
    # [VARIABLE] Store entry time for trade duration tracking
    entry_time = time
    
    print(f"\n{'='*70}")
    print(f"🟢 POSITION OPENED")
    print(f"   Time:          {time}")
    print(f"   Entry Price:   ${price:,.2f}")
    print(f"   Position Size: {POSITION_SIZE_ETH} ETH")
    print(f"   Value:         ${price * POSITION_SIZE_ETH:,.2f}")
    print(f"{'='*70}\n")

def close_position(price, time, reason):
    """
    Record closing an existing LONG position.
    
    Calculates P&L and logs the completed trade.
    'reason' explains why we're closing (signal changed to BEARISH or CHOPPY)
    """
    global position_state, entry_price, entry_time
    
    # [VARIABLE - float] Calculate profit/loss in USD
    # Positive = profitable trade, Negative = losing trade
    pnl_usd = (price - entry_price) * POSITION_SIZE_ETH
    
    # [VARIABLE - float] Calculate return as a percentage
    pnl_pct = ((price - entry_price) / entry_price) * 100
    
    # [VARIABLE - string] Emoji based on profit or loss
    pnl_emoji = "💰" if pnl_usd >= 0 else "📉"
    
    print(f"\n{'='*70}")
    print(f"🔴 POSITION CLOSED")
    print(f"   Reason:        {reason}")
    print(f"   Entry:         ${entry_price:,.2f} at {entry_time}")
    print(f"   Exit:          ${price:,.2f} at {time}")
    print(f"   P&L:           {pnl_emoji} ${pnl_usd:+,.2f} ({pnl_pct:+.2f}%)")
    print(f"{'='*70}\n")
    
    # [DICT] Build a record of this completed trade
    trade_record = {
        'entry_time':  entry_time,
        'exit_time':   time,
        'entry_price': entry_price,
        'exit_price':  price,
        'pnl_usd':     round(pnl_usd, 2),
        'pnl_pct':     round(pnl_pct, 4),
        'reason':      reason
    }
    
    # [METHOD] Add trade to the session log
    trade_log.append(trade_record)
    
    # [VARIABLE] Reset position state back to flat
    position_state = 'FLAT'
    entry_price    = None
    entry_time     = None

def update_position(signal, current_price, current_time):
    """
    Core position management logic.
    
    Called every time a new candle completes.
    Decides whether to open, hold, or close a position
    based on the current signal and position state.
    
    Think of this like a rulebook:
    - If FLAT and signal is LONG → open position
    - If LONG and signal is still LONG → hold, show unrealised P&L
    - If LONG and signal changed → close position
    - If FLAT and signal is not LONG → do nothing
    """
    global previous_signal
    
    if position_state == 'FLAT':
        
        if signal == 'LONG':
            # [FUNCTION CALL] Signal just turned bullish — enter position
            open_position(current_price, current_time)
        
        else:
            # [PRINT] No position, no signal — just waiting
            print(f"   💤 Waiting for LONG signal... "
                  f"(Current: {signal})")
    
    elif position_state == 'LONG':
        
        if signal == 'LONG':
            # [VARIABLE - float] Calculate unrealised P&L
            unrealised_pnl = (current_price - entry_price) * POSITION_SIZE_ETH
            unrealised_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_emoji = "💰" if unrealised_pnl >= 0 else "📉"
            
            # [PRINT] Still long — show current P&L
            print(f"   📊 Holding LONG | Entry: ${entry_price:,.2f} | "
                  f"Current: ${current_price:,.2f} | "
                  f"Unrealised P&L: {pnl_emoji} ${unrealised_pnl:+,.2f} "
                  f"({unrealised_pct:+.2f}%)")
        
        else:
            # [FUNCTION CALL] Signal changed — exit position
            close_position(current_price, current_time, 
                         reason=f"Signal changed to {signal}")
    
    # [VARIABLE] Remember this signal for next candle
    previous_signal = signal

def print_session_summary():
    """Print a summary of all trades completed this session."""
    
    print(f"\n{'='*70}")
    print(f"SESSION SUMMARY")
    print(f"{'='*70}")
    
    if not trade_log:
        print("No completed trades this session.")
        return
    
    # [VARIABLE - float] Total P&L across all trades
    total_pnl = sum(t['pnl_usd'] for t in trade_log)
    
    # [VARIABLE - int] Count winning trades
    winners = sum(1 for t in trade_log if t['pnl_usd'] > 0)
    
    print(f"Total Trades:  {len(trade_log)}")
    print(f"Winners:       {winners}/{len(trade_log)}")
    print(f"Total P&L:     ${total_pnl:+,.2f}")
    print(f"\nTrade Details:")
    print(f"{'-'*70}")
    
    for i, trade in enumerate(trade_log, 1):
        pnl_emoji = "💰" if trade['pnl_usd'] >= 0 else "📉"
        print(f"Trade {i}: {trade['entry_time']} → {trade['exit_time']} | "
              f"${trade['entry_price']:,.2f} → ${trade['exit_price']:,.2f} | "
              f"{pnl_emoji} ${trade['pnl_usd']:+,.2f} ({trade['pnl_pct']:+.2f}%)")

# ============================================================
# BOOTSTRAP: Load historical candles via REST
# ============================================================

print("="*70)
print("LIVE ADX POSITION TRACKER")
print("="*70)
print(f"\nParameters: ADX Threshold {ADX_THRESHOLD} | Period {ADX_PERIOD}")
print(f"Position Size: {POSITION_SIZE_ETH} ETH (paper trading)")
print(f"\nStep 1: Loading {LOOKBACK} historical candles via REST API...")

klines = client.get_historical_klines(
    symbol=SYMBOL,
    interval=Client.KLINE_INTERVAL_1MINUTE,
    limit=LOOKBACK
)

for k in klines:
    candle_buffer.append({
        'timestamp': pd.to_datetime(k[0], unit='ms'),
        'open':      float(k[1]),
        'high':      float(k[2]),
        'low':       float(k[3]),
        'close':     float(k[4]),
        'volume':    float(k[5])
    })

print(f"✅ Loaded {len(candle_buffer)} historical candles")

# [FUNCTION CALL] Get initial signal from historical data
adx, plus_di, minus_di = calculate_adx(candle_buffer)
initial_signal = determine_signal(adx, plus_di, minus_di)

print(f"\nInitial ADX Reading:")
print(f"   ADX: {adx:.2f} | +DI: {plus_di:.2f} | -DI: {minus_di:.2f}")
print(f"   Signal: {initial_signal}")

# ============================================================
# LIVE STREAM
# ============================================================

async def stream_with_position_tracking():
    """
    Stream live candles, calculate ADX, and track positions.
    This combines everything from Day 2 with the new position logic.
    """
    
    print(f"\nStep 2: Starting live stream with position tracking...")
    print("="*70)
    print(f"{'Time':<8} {'Close':>10} {'ADX':>7} {'+DI':>7} {'-DI':>7}  {'Signal':<10}")
    print("-"*70)
    
    async with websockets.connect(URI) as ws:
        
        while True:
            
            raw   = await ws.recv()
            msg   = json.loads(raw)
            kline = msg['k']
            is_closed = kline['x']
            
            if is_closed:
                
                new_candle = {
                    'timestamp': pd.to_datetime(kline['t'], unit='ms'),
                    'open':      float(kline['o']),
                    'high':      float(kline['h']),
                    'low':       float(kline['l']),
                    'close':     float(kline['c']),
                    'volume':    float(kline['v'])
                }
                
                candle_buffer.append(new_candle)
                
                # [FUNCTION CALL] Recalculate ADX
                adx, plus_di, minus_di = calculate_adx(candle_buffer)
                
                # [FUNCTION CALL] Determine signal
                signal = determine_signal(adx, plus_di, minus_di)
                
                # [VARIABLE] Format signal for display
                if signal == 'LONG':
                    signal_display = "🟢 LONG"
                elif signal == 'BEARISH':
                    signal_display = "🔴 BEARISH"
                else:
                    signal_display = "⚪ CHOPPY"
                
                time_str = new_candle['timestamp'].strftime('%H:%M')
                
                # [PRINT] Candle summary row
                print(f"\r{time_str:<8} "
                      f"${new_candle['close']:>9,.2f} "
                      f"{adx:>7.2f} "
                      f"{plus_di:>7.2f} "
                      f"{minus_di:>7.2f}  "
                      f"{signal_display:<10}          ")
                
                # [FUNCTION CALL] Update position based on signal
                update_position(signal, new_candle['close'], time_str)
            
            else:
                current_price = float(kline['c'])
                current_time  = datetime.fromtimestamp(
                    kline['t'] / 1000).strftime('%H:%M')
                print(f"\r⏳ [{current_time}] Building candle... "
                      f"Current price: ${current_price:,.2f}          ",
                      end='', flush=True)

# [ENTRY POINT]
try:
    asyncio.run(stream_with_position_tracking())

except KeyboardInterrupt:
    print("\n")
    print_session_summary()
    print("\n✅ Stream stopped.")