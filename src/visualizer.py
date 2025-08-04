import pandas as pd
import matplotlib.pyplot as plt
import os
from typing import Dict
from src import config

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

    def create_plot(self, ticker: str, historical_data: pd.Series, forecasts: Dict[str, pd.Series]) -> str:
        """
        Creates a plot showing the last 30 days of actual prices and the next
        30 days of forecasted prices.

        Args:
            ticker (str): The ticker symbol.
            historical_data (pd.Series): The full series of historical prices.
            forecasts (Dict[str, pd.Series]): A dictionary of forecasts from the models.

        Returns:
            str: The file path of the saved plot image.
        """
        if historical_data.empty:
            print("Historical data is empty, cannot create plot.")
            return ""

        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(15, 8))

        # 1. Plot historical data (last 30 days)
        # Use boolean indexing for robustness instead of .last()
        last_date = historical_data.index[-1]
        start_date = last_date - pd.Timedelta(days=30)
        last_30_days_actual = historical_data[historical_data.index > start_date]
        ax.plot(last_30_days_actual.index, last_30_days_actual.values, color='gray', marker='o', linestyle='-', label='Actual (Last 30 days)')

        # 2. Plot forecast data
        for model_name, forecast in forecasts.items():
            if not forecast.empty:
                ax.plot(forecast.index, forecast.values, marker='.', linestyle='--', label=f'{model_name} Forecast')

        # 3. Add vertical line separator
        ax.axvline(historical_data.index[-1], color='black', linestyle='--', lw=2, label='Forecast Horizon')

        # 4. Formatting
        ax.set_title(f"{ticker} - Actual (Last 30 days) & Forecast (Next 30 days)", fontsize=16)
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Price", fontsize=12)
        ax.legend()
        ax.grid(True)
        plt.xticks(rotation=45)

        # Set explicit limits to ensure the view is correct
        if not forecast.empty:
            ax.set_xlim(last_30_days_actual.index[0], forecast.index[-1])

        plt.tight_layout()

        # 5. Save the plot
        plot_path = os.path.join(self.data_dir, f"{ticker}_forecast.jpg")
        plt.savefig(plot_path, dpi=150)
        plt.close(fig) # Close the figure to free up memory

        print(f"Forecast plot saved to {plot_path}")
        return plot_path
