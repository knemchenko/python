import pandas as pd
import joblib
import os
from typing import List, Dict
from src.models.base_model import BaseModel
from src import config

class Predictor:
    """
    Handles loading saved models, updating them with new data, and generating forecasts.
    """

    def __init__(self, ticker: str):
        """
        Initializes the Predictor by loading the best models for the given ticker.

        Args:
            ticker (str): The ticker symbol for which to make predictions.

        Raises:
            FileNotFoundError: If the model file for the ticker does not exist.
        """
        self.ticker = ticker
        self.model_filepath = os.path.join(config.DATA_DIR, f"best_models_{self.ticker}.pkl")

        if not os.path.exists(self.model_filepath):
            raise FileNotFoundError(f"Model file not found at {self.model_filepath}. Please run the initial training first.")

        self.models: List[BaseModel] = joblib.load(self.model_filepath)
        print(f"Successfully loaded {len(self.models)} models for ticker {self.ticker} from {self.model_filepath}")

    def predict_returns(self, forecast: pd.Series, current_price: float) -> pd.Series:
        """
        Calculates the predicted returns for each forecast horizon.

        Args:
            forecast (pd.Series): The time series of price forecasts.
            current_price (float): The current price (P0).

        Returns:
            pd.Series: A series of predicted returns (r_hat) for each horizon.
        """
        if forecast.empty or current_price == 0:
            return pd.Series(dtype='float64')

        r_hat = (forecast - current_price) / current_price
        return r_hat

    def update_and_predict(self, full_data: pd.Series, n_periods: int = 30) -> Dict[str, Dict]:
        """
        Updates models, generates forecasts, and calculates predicted returns.

        Args:
            full_data (pd.Series): The complete, up-to-date time series data.
            n_periods (int): The number of future periods to forecast.

        Returns:
            Dict[str, Dict]: A dictionary where keys are model names and values are
                             another dictionary containing 'forecast' and 'r_hat'.
                             e.g., {'Arima': {'forecast': pd.Series, 'r_hat': pd.Series}}
        """
        results = {}
        current_price = full_data.iloc[-1]

        print(f"\n--- Generating forecasts for {self.ticker} for the next {n_periods} days ---")

        for model in self.models:
            model_name = str(model)
            try:
                print(f"Updating and predicting with model: {model_name}...")
                # 1. Retrain the model on the full, most recent dataset
                model.fit(full_data)

                # 2. Generate a new forecast
                forecast = model.predict(n_periods=n_periods)

                # 3. Calculate predicted returns
                r_hat = self.predict_returns(forecast, current_price)

                results[model_name] = {
                    'forecast': forecast,
                    'r_hat': r_hat
                }

            except Exception as e:
                print(f"!!! Failed to update and predict with {model_name}. Error: {e}")
                results[model_name] = {
                    'forecast': pd.Series(dtype='float64'),
                    'r_hat': pd.Series(dtype='float64')
                }

        return results
