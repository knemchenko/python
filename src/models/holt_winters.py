import pandas as pd
from statsmodels.tsa.api import ExponentialSmoothing
from src.models.base_model import BaseModel

class HoltWintersModel(BaseModel):
    """
    A wrapper for the statsmodels Holt-Winters Exponential Smoothing model.
    """

    def __init__(self, trend='add', seasonal='add', seasonal_periods=5, **kwargs):
        """
        Initializes the HoltWintersModel.

        Args:
            trend (str): The type of trend component.
            seasonal (str): The type of seasonal component.
            seasonal_periods (int): The number of periods in a season.
        """
        super().__init__()
        self.trend = trend
        self.seasonal = seasonal
        self.seasonal_periods = seasonal_periods
        self.kwargs = kwargs
        self.train_series = None

    def fit(self, data: pd.Series):
        """
        Fits the Holt-Winters model to the data.

        Args:
            data (pd.Series): Time series data to train on.
        """
        print(f"Fitting HoltWintersModel...")
        self.train_series = data
        self.model = ExponentialSmoothing(
            data,
            trend=self.trend,
            seasonal=self.seasonal,
            seasonal_periods=self.seasonal_periods,
            **self.kwargs
        ).fit()
        print(self.model.summary())

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

        # The forecast method in statsmodels handles the future index automatically
        forecast = self.model.forecast(n_periods)

        forecast_series = pd.Series(forecast, name='forecast')

        # Ensure the index has the correct name
        forecast_series.index.name = 'Date'

        return forecast_series
