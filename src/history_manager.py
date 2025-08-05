import pandas as pd
import os
from typing import Dict
from src import config
from datetime import datetime

class HistoryManager:
    """
    Handles the saving and loading of historical forecast data.
    """

    def __init__(self, ticker: str):
        """
        Initializes the HistoryManager for a specific ticker.
        """
        self.ticker = ticker
        self.forecasts_path = os.path.join(config.DATA_SETTINGS["data_dir"], config.DATA_SETTINGS["forecasts_path"])
        if not os.path.exists(self.forecasts_path):
            os.makedirs(self.forecasts_path)
        self.history_filepath = os.path.join(self.forecasts_path, f"{self.ticker}_forecast_history.parquet")

    def save_forecasts(self, forecasts: Dict[str, pd.Series]):
        """
        Appends the latest forecasts to the historical record.

        Args:
            forecasts (Dict[str, pd.Series]): A dictionary of forecasts from the models.
        """
        if not forecasts:
            return

        records = []
        forecast_date = datetime.now().strftime('%Y-%m-%d')

        for model_name, forecast_series in forecasts.items():
            if not forecast_series.empty and not forecast_series.isnull().all():
                for target_date, predicted_price in forecast_series.items():
                    records.append({
                        "forecast_date": forecast_date,
                        "target_date": target_date.strftime('%Y-%m-%d'),
                        "model_name": model_name,
                        "predicted_price": predicted_price
                    })

        if not records:
            print("No valid forecasts to save.")
            return

        new_history_df = pd.DataFrame(records)

        if os.path.exists(self.history_filepath):
            # Append to existing file
            history_df = pd.read_parquet(self.history_filepath)
            combined_df = pd.concat([history_df, new_history_df], ignore_index=True)
            # Remove potential duplicates, keeping the latest entry
            combined_df.drop_duplicates(
                subset=['forecast_date', 'target_date', 'model_name'],
                keep='last',
                inplace=True
            )
            combined_df.to_parquet(self.history_filepath, index=False)
            print(f"Appended {len(new_history_df)} new forecasts to {self.history_filepath}")
        else:
            # Create a new file
            new_history_df.to_parquet(self.history_filepath, index=False)
            print(f"Created new forecast history file at {self.history_filepath}")

    def load_forecast_history(self) -> pd.DataFrame:
        """
        Loads the forecast history from the Parquet file.

        Returns:
            pd.DataFrame: A DataFrame containing the historical forecasts,
                          or an empty DataFrame if the file doesn't exist.
        """
        if not os.path.exists(self.history_filepath):
            return pd.DataFrame()

        history_df = pd.read_parquet(self.history_filepath)
        # Dates should be automatically parsed correctly by to_parquet, but we can ensure it
        history_df['forecast_date'] = pd.to_datetime(history_df['forecast_date'])
        history_df['target_date'] = pd.to_datetime(history_df['target_date'])
        return history_df
