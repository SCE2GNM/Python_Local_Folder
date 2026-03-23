    """
    STRATEGY: Dual Moving Average Crossover (Parameter Optimization)
    GOAL: Find the optimal Fast/Slow window combination via Grid Search.

    METHODOLOGY:
    1. Iterate through a range of FAST_WINDOWS (e.g., 10 to 50).
    2. Iterate through a range of SLOW_WINDOWS (e.g., 50 to 200).
    3. Calculate Sharpe Ratio for every combination.
    4. Visualize results in a Heatmap to identify 'Stability Clusters'.

    ASSUMPTIONS:
    - Transaction Costs: 0% (Raw Signal Strength).
    - Risk Free Rate: 0% (For relative comparison between parameters).
    """

    import yfinance as yf
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt

    # --- SETTINGS ---
    SYMBOL = "BTC-USD"
    START_DATE = "2020-01-01"
    END_DATE = "2024-01-01"

    # Parameter Ranges
    FAST_RANGE = range(5, 60, 5)   # 5, 10, 15 ... 55
    SLOW_RANGE = range(40, 220, 10) # 40, 50, 60 ... 210

    def fetch_data(symbol, start, end):
        """Simple ETL"""
        print(f"Fetching {symbol}...")
        df = yf.download(symbol, start=start, end=end, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df[['Close']]

    def backtest_single_run(df, fast_w, slow_w):
        """
        Runs a lightweight backtest for a specific parameter set.
        Returns: Sharpe Ratio (float)
        """
        # Vectorized Calculation (Speed is crucial here)
        fast_sma = df['Close'].rolling(window=fast_w).mean()
        slow_sma = df['Close'].rolling(window=slow_w).mean()
        
        # Signal (1 = Long, 0 = Cash)
        signal = np.where(fast_sma > slow_sma, 1, 0)
        
        # Position (Shifted to avoid look-ahead bias)
        position = pd.Series(signal, index=df.index).shift(1)
        
        # Returns
        asset_returns = df['Close'].pct_change()
        strategy_returns = position * asset_returns
        
        # Quick Metrics
        daily_mean = strategy_returns.mean()
        daily_std = strategy_returns.std()
        
        # Handle division by zero if strategy never trades
        if daily_std == 0 or np.isnan(daily_std):
            return 0.0
            
        sharpe = (daily_mean / daily_std) * np.sqrt(365)
        return sharpe

    def run_grid_search(df):
        """
        Loops through all combinations of Fast/Slow windows.
        """
        results = []
        print(f"Starting Grid Search: {len(FAST_RANGE) * len(SLOW_RANGE)} iterations...")
        
        for fast in FAST_RANGE:
            for slow in SLOW_RANGE:
                if fast >= slow:
                    # Logic check: Fast window must be shorter than Slow window
                    continue
                    
                sharpe = backtest_single_run(df, fast, slow)
                results.append({
                    'Fast': fast,
                    'Slow': slow,
                    'Sharpe': sharpe
                })
        
        return pd.DataFrame(results)

    def plot_heatmap(results):
        """
        Visualizes the optimization landscape.
        We pivot the data so:
        X-axis = Slow Window
        Y-axis = Fast Window
        Color  = Sharpe Ratio
        """
        # Pivot table: Rows=Fast, Cols=Slow, Values=Sharpe
        heatmap_data = results.pivot(index='Fast', columns='Slow', values='Sharpe')
        
        plt.figure(figsize=(12, 8))
        plt.title(f'Sharpe Ratio Heatmap: {SYMBOL}')
        
        # Create the heatmap using Matplotlib's imshow
        plt.imshow(heatmap_data, cmap='viridis', aspect='auto', origin='lower')
        
        # Add colorbar
        cbar = plt.colorbar()
        cbar.set_label('Sharpe Ratio')
        
        # Set ticks (A bit technical to align labels with grid)
        plt.xlabel('Slow Window')
        plt.ylabel('Fast Window')
        
        # Set X-axis ticks
        plt.xticks(
            ticks=np.arange(len(heatmap_data.columns)),
            labels=heatmap_data.columns,
            rotation=45
        )
        
        # Set Y-axis ticks
        plt.yticks(
            ticks=np.arange(len(heatmap_data.index)),
            labels=heatmap_data.index
        )
        
        plt.tight_layout()
        
        # SAVE THE FILE INSTEAD OF JUST SHOWING IT
        print("Saving Heatmap to 'heatmap.png'...")
        plt.savefig('heatmap.png')
        print("Done.")

    if __name__ == "__main__":
        # 1. Fetch
        data = fetch_data(SYMBOL, START_DATE, END_DATE)
        
        # 2. Optimize
        results_df = run_grid_search(data)
        
        # 3. Analyze Best Result
        best_run = results_df.loc[results_df['Sharpe'].idxmax()]
        print("\n--- OPTIMIZATION RESULTS ---")
        print(f"Best Combination: Fast={int(best_run['Fast'])}, Slow={int(best_run['Slow'])}")
        print(f"Best Sharpe:      {best_run['Sharpe']:.2f}")

        # SAVE RESULTS TO CSV
        results_df.to_csv('optimization_results.csv', index=False)
        print("Saved full results to 'optimization_results.csv'")
        
        # 4. Visualize
        plot_heatmap(results_df)