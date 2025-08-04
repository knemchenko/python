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

    def update_and_predict(self, full_data: pd.Series, n_periods: int = 30) -> Dict[str, pd.Series]:
        """
        Updates the loaded models with the latest data and generates new forecasts.

        Args:
            full_data (pd.Series): The complete, up-to-date time series data.
            n_periods (int): The number of future periods to forecast.

        Returns:
            Dict[str, pd.Series]: A dictionary where keys are model names and
                                 values are the forecast Series.
        """
        forecasts = {}

        print(f"\n--- Generating forecasts for {self.ticker} for the next {n_periods} days ---")

        for model in self.models:
            model_name = str(model)
            try:
                print(f"Updating and predicting with model: {model_name}...")
                # 1. Retrain the model on the full, most recent dataset
                model.fit(full_data)

                # 2. Generate a new forecast
                forecast = model.predict(n_periods=n_periods)
                forecasts[model_name] = forecast

            except Exception as e:
                print(f"!!! Failed to update and predict with {model_name}. Error: {e}")
                # Store an empty series on failure to be handled by the reporter
                forecasts[model_name] = pd.Series(dtype='float64')

        return forecasts
