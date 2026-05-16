# [IMPORT] Binance client to connect to the exchange
from binance.client import Client

# [IMPORT] Load our API keys from the .env file
from dotenv import load_dotenv

# [IMPORT] os module to read environment variables
import os

# [IMPORT] pandas for storing and displaying data in a table format
import pandas as pd

# [FUNCTION CALL] Load the .env file so our keys are available
load_dotenv()

# [OBJECT] Create authenticated Binance connection using our keys
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'))

def fetch_ohlcv(symbol='ETHUSDT', interval='1h', lookback='30 days ago UTC'):
    """
    Fetch OHLCV candlestick data from Binance.
    
    Think of this like asking Binance: "Give me ETH's price history,
    broken into 1-hour chunks, going back 30 days."
    
    Args:
        symbol:   Which trading pair (ETH priced in USDT)
        interval: Size of each candle (1h = one candle per hour)
        lookback: How far back to fetch data from
    """
    
    # [API CALL] Fetch raw candlestick data from Binance
    # 'klines' is Binance's term for candlestick/OHLCV data
    klines = client.get_historical_klines(
        symbol=symbol,
        interval=interval,
        start_str=lookback
    )
    
    # [DATAFRAME] Convert the raw list into a structured table
    # Binance returns 12 columns per candle - we name them all here
    df = pd.DataFrame(klines, columns=[
        'timestamp',       # When the candle opened (Unix ms)
        'open',            # Price at start of candle
        'high',            # Highest price during candle
        'low',             # Lowest price during candle
        'close',           # Price at end of candle
        'volume',          # Amount of ETH traded
        'close_time',      # When the candle closed (Unix ms)
        'quote_volume',    # Volume in USDT terms
        'trades',          # Number of individual trades
        'taker_buy_base',  # Aggressive buy volume in ETH
        'taker_buy_quote', # Aggressive buy volume in USDT
        'ignore'           # Unused field from Binance
    ])
    
    # [METHOD] Convert Unix millisecond timestamps to readable dates
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # [METHOD] Set timestamp as the index (row label) of our table
    df.set_index('timestamp', inplace=True)
    
    # [LOOP] Convert price and volume columns from strings to floats
    # Binance returns all values as strings - we need numbers to do maths
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    
    # [METHOD] Keep only the 5 columns we actually need
    df = df[['open', 'high', 'low', 'close', 'volume']]
    
    return df

# [FUNCTION CALL] Fetch 30 days of hourly ETH/USDT data
print("Fetching 30 days of ETH/USDT hourly data from Binance...")
df = fetch_ohlcv(symbol='ETHUSDT', interval='1h', lookback='30 days ago UTC')

# [PRINT] Summary statistics
print(f"\n📊 Data Summary:")
print(f"   Rows: {len(df):,}")
print(f"   Date Range: {df.index[0]} to {df.index[-1]}")
print(f"   Current Price:  ${df['close'].iloc[-1]:,.2f}")
print(f"   30-day High:    ${df['high'].max():,.2f}")
print(f"   30-day Low:     ${df['low'].min():,.2f}")

print(f"\n📈 First 5 rows:")
print(df.head())

print(f"\n📉 Last 5 rows:")
print(df.tail())

# [METHOD] Save the data to a CSV file for reference
df.to_csv('binance_eth_30d.csv')
print("\n✅ Data saved to 'binance_eth_30d.csv'")