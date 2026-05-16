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

# [IMPORT] deque - a special list with a maximum size
# When it's full and you add a new item, the oldest item is automatically removed
# Think of it like a conveyor belt with limited space
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
# These are your optimised parameters from Week 2

# [VARIABLE - string] Trading pair to monitor
SYMBOL = 'ETHUSDT'

# [VARIABLE - int] Your optimised ADX period from Week 2
ADX_PERIOD = 10

# [VARIABLE - int] Your optimised ADX threshold from Week 2
ADX_THRESHOLD = 20

# [VARIABLE - int] How many candles to keep in memory at once
# We need at least ADX_PERIOD + 20 for accurate calculation
# 100 gives us plenty of buffer
LOOKBACK = 100

# ============================================================
# SETUP
# ============================================================

# [OBJECT] Binance REST client — used only to fetch initial history
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'))

# [VARIABLE - string] WebSocket URL for 1-minute ETH/USDT klines
URI = "wss://stream.binance.com:9443/ws/ethusdt@kline_1m"

# [OBJECT - deque] Rolling buffer of the last 100 candles
# maxlen=LOOKBACK means it automatically drops old candles as new ones arrive
candle_buffer = deque(maxlen=LOOKBACK)

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calculate_adx(buffer):
    """
    Calculate ADX on the current candle buffer.
    
    Takes the deque of candles, converts to DataFrame,
    runs ADX calculation, returns the latest values.
    
    This is identical to your Week 2 ADX calculation —
    the only difference is the data comes from live candles
    instead of a historical CSV.
    """
    
    # [DATAFRAME] Convert deque of candle dicts into a DataFrame
    df = pd.DataFrame(list(buffer))
    
    # [OBJECT] Create ADX indicator using your Week 2 parameters
    adx_indicator = ADXIndicator(
        high=df['high'],
        low=df['low'],
        close=df['close'],
        window=ADX_PERIOD
    )
    
    # [VARIABLE - float] Latest ADX value (trend strength)
    adx = adx_indicator.adx().iloc[-1]
    
    # [VARIABLE - float] Latest +DI (bullish directional pressure)
    plus_di = adx_indicator.adx_pos().iloc[-1]
    
    # [VARIABLE - float] Latest -DI (bearish directional pressure)
    minus_di = adx_indicator.adx_neg().iloc[-1]
    
    return adx, plus_di, minus_di

def determine_signal(adx, plus_di, minus_di):
    """
    Apply your Week 2 strategy rules to the live ADX values.
    
    Rules (same as your backtested strategy):
    - ADX >= 20 AND +DI > -DI → LONG (trending bullish)
    - ADX >= 20 AND +DI < -DI → BEARISH TREND (no position)
    - ADX < 20               → CHOPPY (stay in cash)
    """
    
    # [VARIABLE - bool] Is the market trending strongly enough?
    trending = adx >= ADX_THRESHOLD
    
    # [VARIABLE - bool] Is the trend bullish?
    bullish = plus_di > minus_di
    
    # [CONDITIONAL] Generate signal based on rules
    if trending and bullish:
        return "🟢 LONG  ", "BUY ETH"
    elif trending and not bullish:
        return "🔴 BEARISH", "NO POSITION"
    else:
        return "⚪ CHOPPY ", "STAY IN CASH"

# ============================================================
# BOOTSTRAP: Load historical candles via REST
# ============================================================
# Before starting the live stream, we need enough historical
# candles to calculate ADX accurately.
#
# Think of it like this: ADX needs a runway to calculate.
# You can't calculate a 10-period ADX with only 3 candles.
# So we pre-load 100 historical candles first, then stream
# new ones on top as they complete.

print("="*70)
print("LIVE ADX REGIME DETECTOR")
print("="*70)
print(f"\nParameters: ADX Threshold {ADX_THRESHOLD} | Period {ADX_PERIOD}")
print(f"\nStep 1: Loading {LOOKBACK} historical candles via REST API...")

# [API CALL] Fetch last 100 completed 1-minute candles from Binance
klines = client.get_historical_klines(
    symbol=SYMBOL,
    interval=Client.KLINE_INTERVAL_1MINUTE,
    limit=LOOKBACK
)

# [LOOP] Convert each raw kline into a candle dict and add to buffer
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
print(f"   From: {candle_buffer[0]['timestamp']}")
print(f"   To:   {candle_buffer[-1]['timestamp']}")

# [FUNCTION CALL] Calculate initial ADX on historical data
adx, plus_di, minus_di = calculate_adx(candle_buffer)
signal, action = determine_signal(adx, plus_di, minus_di)

print(f"\nInitial ADX Reading:")
print(f"   ADX: {adx:.2f} | +DI: {plus_di:.2f} | -DI: {minus_di:.2f}")
print(f"   Signal: {signal} → {action}")

# ============================================================
# LIVE STREAM: Update ADX on each new completed candle
# ============================================================

async def stream_live_adx():
    """
    Connect to Binance WebSocket and recalculate ADX
    every time a new 1-minute candle completes.
    """
    
    print(f"\nStep 2: Starting live stream...")
    print(f"{'='*70}")
    print(f"{'Time':<8} {'Close':>10} {'ADX':>8} {'+DI':>8} {'-DI':>8}  Signal")
    print(f"{'-'*70}")
    
    async with websockets.connect(URI) as ws:
        
        while True:
            
            # [VARIABLE] Receive next message from Binance
            raw = await ws.recv()
            msg = json.loads(raw)
            kline = msg['k']
            
            # [VARIABLE - bool] Only process completed candles
            is_closed = kline['x']
            
            if is_closed:
                
                # [VARIABLE - dict] Build completed candle
                new_candle = {
                    'timestamp': pd.to_datetime(kline['t'], unit='ms'),
                    'open':      float(kline['o']),
                    'high':      float(kline['h']),
                    'low':       float(kline['l']),
                    'close':     float(kline['c']),
                    'volume':    float(kline['v'])
                }
                
                # [METHOD] Add new candle to buffer
                # The oldest candle is automatically removed (deque maxlen)
                candle_buffer.append(new_candle)
                
                # [FUNCTION CALL] Recalculate ADX with updated buffer
                adx, plus_di, minus_di = calculate_adx(candle_buffer)
                
                # [FUNCTION CALL] Determine trading signal
                signal, action = determine_signal(adx, plus_di, minus_di)
                
                # [VARIABLE - string] Readable timestamp
                time_str = new_candle['timestamp'].strftime('%H:%M')
                
                # [PRINT] One row per completed candle
                print(f"{time_str:<8} "
                      f"${new_candle['close']:>9,.2f} "
                      f"{adx:>8.2f} "
                      f"{plus_di:>8.2f} "
                      f"{minus_di:>8.2f}  "
                      f"{signal} → {action}")
            
            else:
                # [PRINT] Live price while candle is building
                current_price = float(kline['c'])
                current_time  = datetime.fromtimestamp(kline['t'] / 1000).strftime('%H:%M')
                print(f"\r⏳ [{current_time}] Building candle... "
                      f"Current price: ${current_price:,.2f}", end='', flush=True)

# [ENTRY POINT] Run the live ADX stream
try:
    asyncio.run(stream_live_adx())

except KeyboardInterrupt:
    print("\n\n✅ Stream stopped.")