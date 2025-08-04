import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from src.models.base_model import BaseModel

class ArimaModel(BaseModel):
    """
    A wrapper for the statsmodels ARIMA model.
    """

    def __init__(self, order=(5, 1, 0), **kwargs):
        """
        Initializes the ArimaModel.

        Args:
            order (tuple): The (p,d,q) order of the model.
        """
        super().__init__()
        self.order = order
        self.kwargs = kwargs
        self.train_series = None

    def fit(self, data: pd.Series):
        """
        Fits the ARIMA model to the data.

        Args:
            data (pd.Series): Time series data to train on.
        """
        print(f"Fitting ArimaModel with order {self.order}...")
        self.train_series = data
        try:
            fitted_model = ARIMA(data, order=self.order, **self.kwargs).fit()
            # Check if the model fit is valid and doesn't contain NaNs
            if np.isnan(fitted_model.params).any():
                print(f"!!! ArimaModel fitted with NaN parameters. Discarding model.")
                self.model = None
            else:
                self.model = fitted_model
                print(self.model.summary())
        except Exception as e:
            print(f"!!! ArimaModel failed to fit. Error: {e}")
            self.model = None

    def predict(self, n_periods: int) -> pd.Series:
        """
        Makes predictions for n_periods into the future.

        Args:
            n_periods (int): The number of periods to forecast.

        Returns:
            pd.Series: A series of forecasted values with a DatetimeIndex.
        """
        if self.model is None:
            raise RuntimeError("The model has not been fitted yet. Call fit() first.")

        # The forecast method can return integer indices if the frequency is not found
        forecast_values = self.model.forecast(steps=n_periods)

        # Create a proper DatetimeIndex to avoid issues
        last_date = self.train_series.index[-1]
        future_index = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=n_periods, freq='B')

        forecast_series = pd.Series(forecast_values, index=future_index, name='forecast')

        return forecast_series
