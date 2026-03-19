"""
Strategy Performance Logger
Automatically logs backtest results to CSV and Excel
"""

import pandas as pd
import os
from datetime import datetime
import json

class StrategyLogger:
    def __init__(self, log_file='strategy_log.csv'):
        self.log_file = log_file
        self.excel_file = log_file.replace('.csv', '.xlsx')
        
        # Define all columns (including future ones)
        self.columns = [
            # Identification
            'timestamp',
            'strategy_id',
            'strategy_name',
            'description',
            'script_path',
            'notebook_path',
            
            # Parameters
            'ticker',
            'start_date',
            'end_date',
            'duration_days',
            'parameters',  # JSON string of all params
            
            # Return Metrics
            'total_return_pct',
            'annual_return_pct',
            'daily_avg_return_pct',
            
            # Risk Metrics
            'daily_volatility_pct',
            'downside_volatility_pct',
            'max_drawdown_pct',
            
            # Risk-Adjusted Metrics
            'sharpe_daily',
            'sharpe_annual',
            'sortino_daily',
            'sortino_annual',
            'calmar_ratio',
            
            # Win/Loss Stats
            'win_rate_pct',
            'winning_days',
            'losing_days',
            'avg_win_pct',
            'avg_loss_pct',
            'profit_factor',
            
            # Distribution Metrics
            'sortino_sharpe_ratio',
            'downside_total_vol_ratio',
            'skewness',
            'kurtosis',
            
            # Advanced Metrics (future use)
            'omega_ratio',
            'var_95',
            'cvar_95',
            'ulcer_index',
            'recovery_factor',
            'payoff_ratio',
            
            # ML Metrics (future use)
            'information_ratio',
            'treynor_ratio',
            'jensens_alpha',
            
            # Execution Metrics (future use)
            'num_trades',
            'avg_trade_duration_days',
            'turnover_rate',
            'transaction_costs_pct',
            
            # Notes
            'verdict',
            'notes',
            'tags'
        ]
        
        # Create log file if doesn't exist
        if not os.path.exists(self.log_file):
            df = pd.DataFrame(columns=self.columns)
            df.to_csv(self.log_file, index=False)
            print(f"✅ Created new strategy log: {self.log_file}")
    
    def log_strategy(self, strategy_data):
        """
        Add a strategy to the log
        
        Args:
            strategy_data: dict with strategy metrics
            
        Returns:
            strategy_id: The assigned strategy ID
        """
        # Read existing log
        df = pd.read_csv(self.log_file)
        
        # Add timestamp and strategy ID
        strategy_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if 'strategy_id' not in strategy_data:
            strategy_data['strategy_id'] = f"S{len(df) + 1:03d}"
        
        # Fill missing columns with None
        for col in self.columns:
            if col not in strategy_data:
                strategy_data[col] = None
        
        # Ensure parameters is JSON string
        if 'parameters' in strategy_data and isinstance(strategy_data['parameters'], dict):
            strategy_data['parameters'] = json.dumps(strategy_data['parameters'])
        
        # Append to dataframe
        new_row = pd.DataFrame([strategy_data])
        df = pd.concat([df, new_row], ignore_index=True)
        
        # Save to CSV
        df.to_csv(self.log_file, index=False)
        
        # Save to Excel with formatting
        self._save_to_excel(df)
        
        print(f"✅ Logged strategy: {strategy_data['strategy_name']} (ID: {strategy_data['strategy_id']})")
        print(f"   CSV: {self.log_file}")
        print(f"   Excel: {self.excel_file}")
        
        return strategy_data['strategy_id']
    
    def _save_to_excel(self, df):
        """Save to Excel with nice formatting"""
        try:
            with pd.ExcelWriter(self.excel_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Strategies', index=False)
                
                # Get workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Strategies']
                
                # Auto-adjust column widths
                for column in df:
                    column_length = max(df[column].astype(str).map(len).max(), len(column))
                    col_idx = df.columns.get_loc(column)
                    worksheet.column_dimensions[chr(65 + col_idx)].width = min(column_length + 2, 50)
                
                print(f"   ✅ Excel formatted and saved")
        except Exception as e:
            print(f"   ⚠️  Excel save failed (install openpyxl): {e}")
    
    def get_log(self):
        """Return the full log as DataFrame"""
        return pd.read_csv(self.log_file)
    
    def search(self, **kwargs):
        """
        Search strategies by criteria
        
        Example:
            logger.search(ticker='BTC-USD', sharpe_annual__gt=1.0)
        """
        df = self.get_log()
        
        for key, value in kwargs.items():
            if '__gt' in key:
                col = key.replace('__gt', '')
                df = df[pd.to_numeric(df[col], errors='coerce') > value]
            elif '__lt' in key:
                col = key.replace('__lt', '')
                df = df[pd.to_numeric(df[col], errors='coerce') < value]
            elif '__contains' in key:
                col = key.replace('__contains', '')
                df = df[df[col].str.contains(value, case=False, na=False)]
            else:
                df = df[df[key] == value]
        
        return df
    
    def get_best_strategies(self, metric='sharpe_annual', top_n=5):
        """Get top N strategies by metric"""
        df = self.get_log()
        df_clean = df.dropna(subset=[metric])
        return df_clean.nlargest(top_n, metric)[
            ['strategy_id', 'strategy_name', metric, 'max_drawdown_pct', 'verdict']
        ]
    
    def compare_strategies(self, strategy_ids):
        """Compare multiple strategies side-by-side"""
        df = self.get_log()
        df = df[df['strategy_id'].isin(strategy_ids)]
        
        key_metrics = [
            'strategy_id', 'strategy_name', 'annual_return_pct', 'max_drawdown_pct',
            'sharpe_annual', 'sortino_annual', 'calmar_ratio', 'win_rate_pct', 'verdict'
        ]
        
        available_metrics = [col for col in key_metrics if col in df.columns]
        return df[available_metrics]
    
    def summary_stats(self):
        """Get summary statistics across all strategies"""
        df = self.get_log()
        
        numeric_cols = [
            'annual_return_pct', 'sharpe_annual', 'sortino_annual',
            'calmar_ratio', 'max_drawdown_pct', 'win_rate_pct'
        ]
        
        stats = {}
        for col in numeric_cols:
            if col in df.columns:
                stats[col] = {
                    'mean': df[col].mean(),
                    'median': df[col].median(),
                    'min': df[col].min(),
                    'max': df[col].max(),
                    'std': df[col].std()
                }
        
        return pd.DataFrame(stats).T
    
    def export_summary(self, output_file='strategy_summary.xlsx'):
        """Export comprehensive summary to Excel"""
        df = self.get_log()
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Full log
            df.to_excel(writer, sheet_name='All Strategies', index=False)
            
            # Summary stats
            summary = self.summary_stats()
            summary.to_excel(writer, sheet_name='Summary Statistics')
            
            # Top performers
            if 'sharpe_annual' in df.columns:
                top_sharpe = self.get_best_strategies('sharpe_annual', 10)
                top_sharpe.to_excel(writer, sheet_name='Top Sharpe', index=False)
            
            if 'sortino_annual' in df.columns:
                top_sortino = self.get_best_strategies('sortino_annual', 10)
                top_sortino.to_excel(writer, sheet_name='Top Sortino', index=False)
            
            if 'calmar_ratio' in df.columns:
                top_calmar = self.get_best_strategies('calmar_ratio', 10)
                top_calmar.to_excel(writer, sheet_name='Top Calmar', index=False)
        
        print(f"✅ Summary exported to {output_file}")