# [IMPORT] Load the Binance client class from the python-binance library
from binance.client import Client

# [IMPORT] Load the dotenv function that reads your .env file
from dotenv import load_dotenv

# [IMPORT] Load Python's built-in os module for reading environment variables
import os

# [FUNCTION CALL] Read the .env file and load the keys into memory
# Think of this like opening a safe and taking out the keys before you need them
load_dotenv()

# [VARIABLE] Read your API key from the environment (not hardcoded in the script)
api_key = os.getenv('BINANCE_API_KEY')

# [VARIABLE] Read your secret key the same way
api_secret = os.getenv('BINANCE_SECRET_KEY')

# [OBJECT] Create a Binance client using your keys
# Think of this like logging into Binance — after this line, you're "connected"
client = Client(api_key, api_secret)

# [PRINT] Visual separator for readability
print("="*70)
print("BINANCE API CONNECTION TEST")
print("="*70)

# [API CALL] Ask Binance for your account status
# REST call: you ask → Binance answers → result stored in 'status'
status = client.get_account_status()
print(f"\n✅ Account Status: {status}")

# [API CALL] Ask Binance for its server time (good basic connection test)
server_time = client.get_server_time()
print(f"✅ Server Time: {server_time['serverTime']}")

# [API CALL] Ask Binance for the current ETH/USDT price
ticker = client.get_symbol_ticker(symbol="ETHUSDT")
print(f"\n💰 Current ETH Price: ${float(ticker['price']):,.2f}")

# [API CALL] Ask Binance for 24-hour statistics on ETH/USDT
stats = client.get_ticker(symbol="ETHUSDT")
print(f"\n📊 24hr Statistics:")
print(f"   High: ${float(stats['highPrice']):,.2f}")
print(f"   Low: ${float(stats['lowPrice']):,.2f}")
print(f"   Volume: {float(stats['volume']):,.2f} ETH")
print(f"   Price Change: {float(stats['priceChangePercent']):.2f}%")

print("\n✅ Binance API connection successful!")