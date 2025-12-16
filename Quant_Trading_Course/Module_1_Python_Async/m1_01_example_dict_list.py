# --- 1. THE LIST (Sequences) ---
# A list of closing prices for the last 5 hours
price_history = [59000, 59200, 58900, 60000, 60500]

# Accessing data:
print(f"First price recorded: {price_history[0]}") # Lists start at index 0
print(f"Most recent price: {price_history[-1]}")   # -1 gets the last item

# --- 2. THE DICTIONARY (Labels/Attributes) ---
# Information about the asset
bitcoin_data = {
    "symbol": "BTC/USDT",
    "exchange": "Binance",
    "current_price": 60500,
    "is_active": True
}

# Accessing data:
print(f"Trading Pair: {bitcoin_data['symbol']}")
print(f"Price: {bitcoin_data['current_price']}")