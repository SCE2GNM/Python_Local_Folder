# [IMPORT] asyncio for running asynchronous WebSocket connection
import asyncio

# [IMPORT] websockets for direct, stable WebSocket connection to Binance
import websockets

# [IMPORT] json to decode messages from Binance
import json

# [IMPORT] pandas for storing and displaying candle data
import pandas as pd

# [IMPORT] datetime for readable timestamps_
from datetime import datetime

# ============================================================
# WHAT IS A KLINE STREAM?
# ============================================================
# Instead of receiving every individual trade (like day2_websocket_stream.py),
# a kline stream receives pre-aggregated candles directly from Binance.
# Binance builds the candle for us — we just receive the updates.
#
# Think of it like this:
# - Trade stream = every individual sale at a shop (item by item)
# - Kline stream = the shop's hourly sales summary (total per hour)
#
# Each message contains the CURRENT state of the candle being built.
# The candle updates every time a new trade happens within that minute.
# When the minute ends, Binance marks the candle as 'closed' (x = True)

# [VARIABLE - string] Binance WebSocket URL for 1-minute ETH/USDT klines
# '@kline_1m' tells Binance we want 1-minute candle updates
URI = "wss://stream.binance.com:9443/ws/ethusdt@kline_1m"

# [LIST] Store completed candles here
completed_candles = []

async def stream_candles():
    """
    Connect to Binance and receive 1-minute candle updates.
    Print candle details when each minute completes.
    """
    
    print("="*70)
    print("LIVE 1-MINUTE ETH/USDT CANDLE STREAM")
    print("="*70)
    print("\nWaiting for candles to complete (one per minute)...")
    print("Each row = one completed 1-minute candle")
    print("Press Ctrl+C to stop\n")
    
    # [PRINT] Column headers for our table
    print(f"{'Time':<10} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
    print("-"*70)
    
    # [CONTEXT MANAGER] Open persistent WebSocket connection
    async with websockets.connect(URI) as ws:
        
        # [LOOP] Keep receiving messages until Ctrl+C
        while True:
            
            # [VARIABLE - string] Wait for next message from Binance
            raw = await ws.recv()
            
            # [VARIABLE - dict] Decode JSON message into Python dictionary
            msg = json.loads(raw)
            
            # [VARIABLE - dict] Extract the kline data from the message
            # Every kline message has an 'k' key containing candle data
            kline = msg['k']
            
            # [VARIABLE - bool] Has this candle finished?
            # 'x' = True means the minute is over and candle is sealed
            # 'x' = False means the candle is still being built
            is_closed = kline['x']
            
            if is_closed:
                # [VARIABLE - dict] Build a clean candle dictionary
                candle = {
                    'time':   datetime.fromtimestamp(kline['t'] / 1000).strftime('%H:%M'),
                    'open':   float(kline['o']),
                    'high':   float(kline['h']),
                    'low':    float(kline['l']),
                    'close':  float(kline['c']),
                    'volume': float(kline['v'])
                }
                
                # [METHOD] Store the completed candle
                completed_candles.append(candle)
                
                # [VARIABLE - float] Calculate candle direction
                # Positive = price went up during this minute
                # Negative = price went down during this minute
                change = candle['close'] - candle['open']
                
                # [CONDITIONAL] Choose emoji based on price direction
                direction = "🟢" if change >= 0 else "🔴"
                
                # [PRINT] One row per completed candle
                print(f"{direction} {candle['time']:<8} "
                      f"${candle['open']:>9,.2f} "
                      f"${candle['high']:>9,.2f} "
                      f"${candle['low']:>9,.2f} "
                      f"${candle['close']:>9,.2f} "
                      f"{candle['volume']:>11,.2f} ETH")
            
            else:
                # [PRINT] Show live price while candle is still building
                # \r returns cursor to start of line (overwrites previous update)
                current_price = float(kline['c'])
                current_time  = datetime.fromtimestamp(kline['t'] / 1000).strftime('%H:%M')
                print(f"\r⏳ Building candle [{current_time}] | "
                      f"Current price: ${current_price:,.2f}", end='', flush=True)

# [ENTRY POINT] Run the async function
try:
    asyncio.run(stream_candles())

except KeyboardInterrupt:
    print("\n\nStopping stream...")
    
    # [CONDITIONAL] Save candles to CSV if we captured any
    if completed_candles:
        df = pd.DataFrame(completed_candles)
        df.to_csv('live_candles.csv', index=False)
        print(f"✅ Saved {len(completed_candles)} completed candles to 'live_candles.csv'")
    else:
        print("No completed candles to save (stream ran for less than 1 minute)")
    
    print("✅ Done!")