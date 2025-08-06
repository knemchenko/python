import os
import pandas as pd
import numpy as np
import yfinance as yf
from functools import lru_cache
from dashboard.config import Config

# --- File Paths ---
METRICS_CSV = os.path.join(Config.DATA_DIR, "metrics.csv")
HISTORY_PARQUET = os.path.join(Config.DATA_DIR, "forecast_history.parquet")

# --- Data Loading & Processing Functions ---

@lru_cache(maxsize=32)
def get_historical_signals():
    """Loads and caches the complete history of signals."""
    if not os.path.exists(HISTORY_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(HISTORY_PARQUET)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def get_latest_metrics():
    """Returns the most recent row of metrics as a dictionary."""
    if not os.path.exists(METRICS_CSV):
        return {}
    metrics_df = pd.read_csv(METRICS_CSV)
    return metrics_df.iloc[-1].to_dict() if not metrics_df.empty else {}

def get_todays_signals():
    """Filters historical signals to get only the most recent ones for each ticker."""
    df = get_historical_signals()
    if df.empty:
        return pd.DataFrame()
    latest_signals = df.loc[df.groupby('ticker')['timestamp'].idxmax()]
    return latest_signals

@lru_cache(maxsize=4)
def get_spy_data(start_date, end_date):
    """Downloads SPY data for benchmark comparison."""
    return yf.download("SPY", start=start_date, end=end_date)

def get_equity_curve():
    """
    Calculates a simulated equity curve based on historical signals.
    """
    signals = get_historical_signals()
    if signals.empty:
        return pd.DataFrame(columns=['date', 'equity', 'spy_equity'])

    signals['pnl'] = signals['expected_return'] * signals['weight'] * np.where(signals['direction'] == 'Long', 1, -1)

    daily_pnl = signals.groupby('timestamp')['pnl'].sum()

    initial_capital = 100.0
    equity_curve = (1 + daily_pnl).cumprod() * initial_capital
    equity_curve.name = "equity"

    start_date = equity_curve.index.min()
    end_date = equity_curve.index.max()
    spy_data = get_spy_data(start_date, end_date)

    if not spy_data.empty:
        spy_returns = spy_data['Close'].pct_change()
        spy_equity = (1 + spy_returns).cumprod() * initial_capital
        spy_equity.name = "spy_equity"

        combined = pd.concat([equity_curve, spy_equity], axis=1).fillna(method='ffill')
        combined.index.name = 'date'
        combined = combined.reset_index()
    else:
        combined = equity_curve.to_frame().reset_index()
        combined.rename(columns={'timestamp': 'date'}, inplace=True)
        combined['spy_equity'] = np.nan

    return combined

def get_sharpe_heatmap_data():
    """Calculates Sharpe ratio for each ticker/horizon combination."""
    signals = get_historical_signals()
    if signals.empty:
        return {}

    signals['pnl'] = signals['expected_return'] * signals['weight'] * np.where(signals['direction'] == 'Long', 1, -1)

    def sharpe(x):
        if x.std() == 0: return 0
        return (x.mean() / x.std()) * np.sqrt(252)

    heatmap_data = signals.groupby(['ticker', 'horizon_days'])['pnl'].apply(sharpe).unstack().fillna(0)

    return {
        'x': heatmap_data.columns.tolist(),
        'y': heatmap_data.index.tolist(),
        'z': heatmap_data.values.tolist()
    }
