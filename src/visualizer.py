import pandas as pd
import matplotlib.pyplot as plt
import os
from typing import Dict
from src import config
from src.history_manager import HistoryManager
from datetime import datetime, timedelta

class Visualizer:
    """
    Handles the creation of plots for the forecast reports.
    """

    def __init__(self):
        """
        Initializes the Visualizer. Ensures the data directory exists.
        """
        self.data_dir = config.DATA_DIR
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def create_plot(self, ticker: str, historical_data: pd.Series, forecasts: Dict[str, pd.Series], forecast_history: pd.DataFrame) -> str:
        """
        Creates a plot showing the last 30 days of actual prices, the next
        30 days of forecasted prices, and historical "spaghetti" forecasts.

        Args:
            ticker (str): The ticker symbol.
            historical_data (pd.Series): The full series of historical prices.
            forecasts (Dict[str, pd.Series]): A dictionary of new forecasts from the models.
            forecast_history (pd.DataFrame): A DataFrame of historical forecasts.

        Returns:
            str: The file path of the saved plot image.
        """
        if historical_data.empty:
            print("Historical data is empty, cannot create plot.")
            return ""

        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(15, 8))

        # 1. Select the relevant historical data window
        last_date = historical_data.index[-1]
        start_date_hist = last_date - pd.Timedelta(days=30)
        last_30_days_actual = historical_data[historical_data.index >= start_date_hist]

        # Plot the historical data
        ax.plot(last_30_days_actual.index, last_30_days_actual.values, color='gray', marker='o', linestyle='-', label='Actual (Last 30 days)')

        # 2. Plot historical "spaghetti" forecasts
        if not forecast_history.empty:
            today = datetime.now().date()
            for days_ago in [1, 7, 14, 30]:
                past_forecast_date = today - timedelta(days=days_ago)
                hist_forecast = forecast_history[forecast_history['forecast_date'].dt.date == past_forecast_date]
                if not hist_forecast.empty:
                    # Plot each model's historical forecast
                    for model_name, group in hist_forecast.groupby('model_name'):
                        group = group.sort_values('target_date')
                        ax.plot(group['target_date'], group['predicted_price'], color='grey', linestyle=':', lw=1,
                                label=f'Forecast from {past_forecast_date.strftime("%Y-%m-%d")} ({model_name})' if 'historical_legend_added' not in locals() else "")
                        locals()['historical_legend_added'] = True # Add legend only once

        # 3. Plot future forecast data, ensuring continuity
        end_date_forecast = last_date # Initialize with last historical date
        for model_name, forecast in forecasts.items():
            if not forecast.empty:
                # Create a continuous series from the last actual point to the forecast
                last_actual_point = historical_data.tail(1)
                continuous_forecast = pd.concat([last_actual_point, forecast])

                ax.plot(continuous_forecast.index, continuous_forecast.values, marker='.', linestyle='--', label=f'{model_name} Forecast')

                # Keep track of the furthest forecast date for setting plot limits
                if continuous_forecast.index[-1] > end_date_forecast:
                    end_date_forecast = continuous_forecast.index[-1]

        # 4. Add vertical line separator
        ax.axvline(last_date, color='black', linestyle='--', lw=2, label='Forecast Horizon')

        # 4. Formatting and setting explicit limits
        ax.set_title(f"{ticker} - Actual (Last 30 days) & Forecast (Next 30 days)", fontsize=16)
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Price", fontsize=12)
        ax.legend()
        ax.grid(True)

        # Set explicit X-axis limits
        ax.set_xlim(start_date_hist, end_date_forecast + pd.Timedelta(days=1))

        plt.xticks(rotation=45)
        plt.tight_layout()

        # 5. Save the plot
        plot_path = os.path.join(self.data_dir, f"{ticker}_forecast.jpg")
        if config.SAVE_PLOTS_TO_DISK:
            plt.savefig(plot_path, dpi=150)
            print(f"Forecast plot saved to {plot_path}")

        plt.close(fig) # Close the figure to free up memory

        return plot_path
