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

# [VARIABLE - int] How many candles to keep in memory at once
LOOKBACK = 100

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
    
    adx     = adx_indicator.adx().iloc[-1]
    plus_di = adx_indicator.adx_pos().iloc[-1]
    minus_di = adx_indicator.adx_neg().iloc[-1]
    
    return adx, plus_di, minus_di

def determine_signal(adx, plus_di, minus_di):
    """Apply Week 2 strategy rules to live ADX values."""
    
    trending = adx >= ADX_THRESHOLD
    bullish  = plus_di > minus_di
    
    if trending and bullish:
        return "🟢 LONG   ", "BUY ETH"
    elif trending and not bullish:
        return "🔴 BEARISH", "NO POSITION"
    else:
        return "⚪ CHOPPY ", "STAY IN CASH"

# ============================================================
# BOOTSTRAP: Load historical candles via REST
# ============================================================

print("="*70)
print("LIVE ADX REGIME DETECTOR")
print("="*70)
print(f"\nParameters: ADX Threshold {ADX_THRESHOLD} | Period {ADX_PERIOD}")
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
print(f"   From: {candle_buffer[0]['timestamp']}")
print(f"   To:   {candle_buffer[-1]['timestamp']}")

adx, plus_di, minus_di = calculate_adx(candle_buffer)
signal, action = determine_signal(adx, plus_di, minus_di)

print(f"\nInitial ADX Reading:")
print(f"   ADX: {adx:.2f} | +DI: {plus_di:.2f} | -DI: {minus_di:.2f}")
print(f"   Signal: {signal} → {action}")

# ============================================================
# LIVE STREAM: Update ADX on each new completed candle
# ============================================================

async def stream_live_adx():
    """Recalculate ADX every time a new 1-minute candle completes."""
    
    print(f"\nStep 2: Starting live stream...")
    print("="*70)
    print(f"{'Time':<8} {'Close':>10} {'ADX':>8} {'+DI':>8} {'-DI':>8}  {'Signal'}")
    print("-"*70)
    
    async with websockets.connect(URI) as ws:
        
        while True:
            
            raw  = await ws.recv()
            msg  = json.loads(raw)
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
                
                adx, plus_di, minus_di = calculate_adx(candle_buffer)
                signal, action = determine_signal(adx, plus_di, minus_di)
                
                time_str = new_candle['timestamp'].strftime('%H:%M')
                
                # [PRINT] \r clears the building candle line before printing
                print(f"\r{time_str:<8} "
                      f"${new_candle['close']:>9,.2f} "
                      f"{adx:>8.2f} "
                      f"{plus_di:>8.2f} "
                      f"{minus_di:>8.2f}  "
                      f"{signal} → {action}"
                      # Trailing spaces to overwrite any leftover building text
                      f"          ")
            
            else:
                current_price = float(kline['c'])
                current_time  = datetime.fromtimestamp(kline['t'] / 1000).strftime('%H:%M')
                
                # [PRINT] Overwrite same line with extra spaces to clear leftovers
                print(f"\r⏳ [{current_time}] Building candle... "
                      f"Current price: ${current_price:,.2f}          ",
                      end='', flush=True)

# [ENTRY POINT]
try:
    asyncio.run(stream_live_adx())

except KeyboardInterrupt:
    print("\n\n✅ Stream stopped.")