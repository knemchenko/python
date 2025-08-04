import pandas as pd
import numpy as np
from datetime import timedelta, datetime
from src.history_manager import HistoryManager

class Evaluator:
    """
    Calculates the accuracy of historical forecasts against actual prices.
    """

    def __init__(self, ticker: str, actual_data: pd.Series):
        """
        Initializes the Evaluator.

        Args:
            ticker (str): The ticker symbol to evaluate.
            actual_data (pd.Series): A Series of actual historical prices, indexed by date.
        """
        self.ticker = ticker
        self.actual_data = actual_data
        self.history_manager = HistoryManager(ticker)
        self.forecast_history = self.history_manager.load_forecast_history()

    def _calculate_metrics(self, pairs: pd.DataFrame):
        """
        Calculates RMSE and MAPE for a dataframe of (prediction, actual) pairs.
        """
        if pairs.empty:
            return np.nan, np.nan

        rmse = np.sqrt(np.mean((pairs['predicted_price'] - pairs['actual_price'])**2))
        mape = np.mean(np.abs((pairs['predicted_price'] - pairs['actual_price']) / pairs['actual_price'])) * 100

        return rmse, mape

    def calculate_accuracy(self, horizons=[1, 7, 14, 30]):
        """
        Calculates accuracy metrics for different time horizons.

        Args:
            horizons (list): A list of forecast horizons in days to evaluate.

        Returns:
            Dict[str, Dict[str, float]]: A dictionary where keys are horizons
                                         and values are dicts of metrics.
        """
        if self.forecast_history.empty:
            print("Forecast history is empty. Cannot calculate accuracy.")
            return {}

        results = {}
        today = datetime.now().date()

        for h in horizons:
            # Find the date `h` days ago
            forecast_date_to_check = today - timedelta(days=h)

            # Get all forecasts made on that specific date
            relevant_forecasts = self.forecast_history[
                self.forecast_history['forecast_date'].dt.date == forecast_date_to_check
            ].copy()

            if relevant_forecasts.empty:
                continue

            # Match forecasts with actual prices on their target dates
            # We merge the forecasts with the actual price series
            relevant_forecasts.rename(columns={'target_date': 'Date'}, inplace=True)
            actuals_df = self.actual_data.rename('actual_price').to_frame()

            # Ensure the index of actuals_df is what we need for merging
            actuals_df.index.name = 'Date'

            # Convert relevant_forecasts['Date'] to the same type as actuals_df.index
            # This is crucial if one is timezone-aware and the other is not.
            relevant_forecasts['Date'] = pd.to_datetime(relevant_forecasts['Date']).dt.tz_localize(None)
            actuals_df.index = pd.to_datetime(actuals_df.index).tz_localize(None)

            comparison_df = pd.merge(
                relevant_forecasts,
                actuals_df,
                on='Date',
                how='inner'
            )

            if not comparison_df.empty:
                rmse, mape = self._calculate_metrics(comparison_df)
                results[f'{h}d'] = {'RMSE': rmse, 'MAPE': mape}

        return results
