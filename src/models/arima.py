import pandas as pd
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
        self.model = ARIMA(data, order=self.order, **self.kwargs).fit()
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

        # The forecast method handles the future index automatically if no start/end is given
        forecast = self.model.forecast(steps=n_periods)

        forecast_series = pd.Series(forecast, name='forecast')
        forecast_series.index.name = 'Date'

        return forecast_series
