import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import numpy as np

# --- SETTINGS ---
SYMBOL = "BTC-USD"
CSV_FILE = "trends.csv" 
START_DATE = "2020-01-01"
END_DATE = "2026-01-01"

def fetch_market_data(symbol, start, end):
    print(f"Fetching Market Data for {symbol}...")
    df = yf.download(symbol, start=start, end=end, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[['Close', 'Volume']]

def load_sentiment_data(filepath):
    print(f"Loading Sentiment Data from {filepath}...")
    try:
        df = pd.read_csv(filepath, header=1) 
        df.columns = ['Date', 'Search_Score']
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df['Search_Score'] = pd.to_numeric(df['Search_Score'], errors='coerce').fillna(0)
        return df
    except FileNotFoundError:
        print("CRITICAL ERROR: 'trends.csv' not found. Using DUMMY data.")
        dates = pd.date_range(start=START_DATE, end=END_DATE, freq='W')
        fake_data = pd.DataFrame(index=dates)
        fake_data['Search_Score'] = np.random.randint(10, 100, size=len(dates))
        return fake_data

def align_datasets(price_df, sentiment_df):
    print("Aligning Datasets...")
    price_weekly = price_df.resample('W').agg({'Close': 'last', 'Volume': 'sum'})
    merged = pd.merge(price_weekly, sentiment_df, left_index=True, right_index=True, how='inner')
    return merged

def analyze_correlation(df):
    df['Price_Change'] = df['Close'].pct_change()
    df['Sentiment_Change'] = df['Search_Score'].pct_change()
    df['Rolling_Corr'] = df['Price_Change'].rolling(window=24).corr(df['Sentiment_Change'])
    return df

def plot_analysis(df):
    plt.figure(figsize=(12, 10))
    plt.style.use('dark_background')
    
    # Plot 1: Levels
    ax1 = plt.subplot(3, 1, 1)
    color = 'tab:green'
    ax1.set_ylabel('BTC Price', color=color)
    ax1.plot(df.index, df['Close'], color=color)
    ax1.tick_params(axis='y', labelcolor=color)
    
    ax2 = ax1.twinx()
    color = 'tab:blue'
    ax2.set_ylabel('Search Score', color=color)
    ax2.plot(df.index, df['Search_Score'], color=color, alpha=0.6)
    ax2.tick_params(axis='y', labelcolor=color)
    plt.title('Bitcoin Price vs. Retail Interest')
    
    # Plot 2: Scatter
    plt.subplot(3, 1, 2)
    plt.scatter(df['Sentiment_Change'], df['Price_Change'], alpha=0.5, color='cyan')
    plt.title('Scatter: Search Change vs Price Change')
    plt.axhline(0, color='gray', linestyle='--')
    plt.axvline(0, color='gray', linestyle='--')
    
    # Plot 3: Correlation
    plt.subplot(3, 1, 3)
    plt.plot(df.index, df['Rolling_Corr'], color='yellow')
    plt.axhline(0, color='white', linestyle='--')
    plt.title('Rolling Correlation (6-Month)')
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    price_data = fetch_market_data(SYMBOL, START_DATE, END_DATE)
    sentiment_data = load_sentiment_data(CSV_FILE)
    merged_data = align_datasets(price_data, sentiment_data)
    merged_data = analyze_correlation(merged_data)
    plot_analysis(merged_data)
    
    print(f"\n--- RESULTS ---")
    print(f"Overall Correlation: {merged_data['Price_Change'].corr(merged_data['Sentiment_Change']):.4f}")