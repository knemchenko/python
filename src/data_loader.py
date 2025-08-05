import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from src import config

class DataLoader:
    """
    Handles fetching and caching of financial data from yfinance.
    """

    def __init__(self):
        """
        Initializes the DataLoader, creating the data directory if it doesn't exist.
        """
        self.start_date = config.START_DATE
        self.data_dir = config.DATA_DIR
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def _get_cache_filepath(self, ticker: str) -> str:
        """
        Gets the file path for the cached data of a given ticker.
        """
        return os.path.join(self.data_dir, f"{ticker}.csv")

    def _fetch_history(self, tickers: list, start: str, end: str) -> pd.DataFrame:
        """
        Fetches historical data for a list of tickers.
        """
        # yf.download is better for multiple tickers
        df = yf.download(tickers, start=start, end=end, auto_adjust=True)
        return df

    def load_data(self, ticker: str) -> pd.DataFrame:
        """
        Loads data for a given ticker. It uses a local cache to avoid
        downloading all data every time. If cached data is found, it only
        fetches the newer data since the last record.

        Args:
            ticker (str): The ticker symbol to load data for (e.g., "AAPL").

        Returns:
            pd.DataFrame: A DataFrame containing the historical data with
                          'Date' as the index.
        """
        filepath = self._get_cache_filepath(ticker)
        today = datetime.now().strftime('%Y-%m-%d')

        df = None

        if os.path.exists(filepath):
            print(f"Loading cached data for {ticker} from {filepath}")
            main_df = pd.read_csv(filepath, index_col='Date', parse_dates=True)
            last_date = main_df.index.max()
            start_fetch_date = last_date + timedelta(days=1)

            if start_fetch_date.strftime('%Y-%m-%d') < today:
                print(f"Fetching new data for {ticker} and ^VIX from {start_fetch_date.strftime('%Y-%m-%d')} to {today}")
                new_data_raw = self._fetch_history([ticker, '^VIX'], start=start_fetch_date.strftime('%Y-%m-%d'), end=today)
                if not new_data_raw.empty:
                    # Process and append new data
                    new_data_processed = self._process_raw_data(new_data_raw, ticker)
                    main_df = pd.concat([main_df, new_data_processed])
                    main_df = main_df[~main_df.index.duplicated(keep='last')]
            else:
                print(f"Data for {ticker} is already up to date.")
        else:
            print(f"No cached data found for {ticker}. Fetching all data from {self.start_date}.")
            raw_df = self._fetch_history([ticker, '^VIX'], start=self.start_date, end=today)
            main_df = self._process_raw_data(raw_df, ticker)

        if main_df is not None and not main_df.empty:
            main_df.sort_index(inplace=True)
            main_df.to_csv(filepath, index_label='Date')
            print(f"Data for {ticker} saved to {filepath}")
        else:
            print(f"Could not download any data for {ticker}.")
            return pd.DataFrame()

        return main_df

    def _process_raw_data(self, raw_df: pd.DataFrame, main_ticker: str) -> pd.DataFrame:
        """
        Processes the raw DataFrame from yfinance, combines asset and VIX data,
        and calculates the volume moving average.
        """
        if raw_df.empty:
            return pd.DataFrame()

        # Extract data for the main ticker
        df = raw_df['Close'][[main_ticker]].rename(columns={main_ticker: 'Close'})
        df['Open'] = raw_df['Open'][main_ticker]
        df['High'] = raw_df['High'][main_ticker]
        df['Low'] = raw_df['Low'][main_ticker]
        df['Volume'] = raw_df['Volume'][main_ticker]

        # Extract VIX data
        df['VIX_Close'] = raw_df['Close']['^VIX']

        # Forward-fill VIX data for non-trading days
        df['VIX_Close'].fillna(method='ffill', inplace=True)

        # Calculate 30-day moving average of volume
        df['ma30_volume'] = df['Volume'].rolling(window=30, min_periods=1).mean()

        # Drop rows with NaN values that might have been introduced
        df.dropna(inplace=True)

        return df
