import pandas as pd
import pandas_ta as ta
import numpy as np

class FeatureEngineer:
    """
    Calculates and adds technical features to the price data.
    """

    def _calculate_atr(self, df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
        """Calculates the Average True Range (ATR)."""
        df.ta.atr(length=length, append=True)
        return df

    def _calculate_realized_vol(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """Calculates the realized volatility."""
        log_returns = np.log(df['Close'] / df['Close'].shift(1))
        df[f'realized_vol_{window}d'] = log_returns.rolling(window=window).std() * np.sqrt(252)
        return df

    def _calculate_beta(self, asset_df: pd.DataFrame, benchmark_df: pd.DataFrame, window: int = 60) -> pd.DataFrame:
        """Calculates the rolling beta against a benchmark."""
        # Calculate returns
        asset_returns = asset_df['Close'].pct_change()
        benchmark_returns = benchmark_df['Close'].pct_change()

        # Combine returns for rolling calculation
        returns_df = pd.concat([asset_returns, benchmark_returns], axis=1)
        returns_df.columns = ['asset', 'benchmark']

        # Calculate rolling covariance and variance
        rolling_cov = returns_df['asset'].rolling(window=window).cov(returns_df['benchmark'])
        rolling_var = returns_df['benchmark'].rolling(window=window).var()

        # Calculate beta and add to the original asset dataframe
        asset_df[f'beta_{window}d'] = rolling_cov / rolling_var
        return asset_df

    def add_features(self, asset_df: pd.DataFrame, benchmark_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        Main method to add all features to the asset's price dataframe.

        Args:
            asset_df (pd.DataFrame): The price data for the main asset.
            benchmark_df (pd.DataFrame, optional): The price data for the benchmark asset,
                                                   required for beta calculation.

        Returns:
            pd.DataFrame: The asset DataFrame enriched with new feature columns.
        """
        print("Adding technical features...")

        # Ensure columns are lowercase for pandas_ta compatibility if needed
        asset_df.columns = [col.lower() for col in asset_df.columns]

        # Calculate features that don't require a benchmark
        asset_df = self._calculate_atr(asset_df)
        asset_df = self._calculate_realized_vol(asset_df)

        # Calculate features that require a benchmark
        if benchmark_df is not None and not benchmark_df.empty:
            asset_df = self._calculate_beta(asset_df, benchmark_df)

        # Restore original column casing if desired, or just keep it lowercase
        asset_df.columns = [col.capitalize() for col in asset_df.columns]

        print("Features added successfully.")
        return asset_df.dropna()
