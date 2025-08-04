import pandas as pd
from arch import arch_model
from src.models.base_model import BaseModel

class GarchModel(BaseModel):
    """
    A wrapper for the arch GARCH(1,1) model.
    This implementation models the price directly with an ARMA(1,1)-GARCH(1,1) process.
    The forecast is based on the conditional mean.
    """

    def __init__(self, p=1, q=1, **kwargs):
        """
        Initializes the GarchModel.

        Args:
            p (int): The order of the GARCH component.
            q (int): The order of the ARCH component.
        """
        super().__init__()
        self.p = p
        self.q = q
        self.kwargs = kwargs
        self.train_series = None
        self.fitted_model = None

    def fit(self, data: pd.Series):
        """
        Fits the GARCH model to the data. We model the log returns.

        Args:
            data (pd.Series): Time series data of prices to train on.
        """
        print(f"Fitting GarchModel...")
        # GARCH models are best applied to returns, not prices
        self.returns = 100 * data.pct_change().dropna()
        self.train_series = data # Keep original prices for forecasting

        # Define an ARMA(1,1)-GARCH(1,1) model. This is a common choice.
        self.model = arch_model(self.returns, vol='Garch', p=self.p, q=self.q, mean='ARX', lags=1, dist='Normal')
        self.fitted_model = self.model.fit(disp='off')
        print(self.fitted_model.summary())

    def predict(self, n_periods: int) -> pd.Series:
        """
        Makes predictions for n_periods into the future.
        This uses the model's forecast for the conditional mean of returns,
        and then reconstructs the price forecast from that.

        Args:
            n_periods (int): The number of periods to forecast.

        Returns:
            pd.Series: A series of forecasted price values with a DatetimeIndex.
        """
        if self.fitted_model is None:
            raise RuntimeError("The model has not been fitted yet. Call fit() first.")

        # Forecast the conditional mean (returns)
        forecasts = self.fitted_model.forecast(horizon=n_periods, start=None)
        mean_forecast = forecasts.mean.iloc[-1].values

        # Reconstruct the price forecast from the returns forecast
        last_price = self.train_series.iloc[-1]
        price_forecast = [last_price]
        for ret in mean_forecast:
            next_price = price_forecast[-1] * (1 + ret / 100)
            price_forecast.append(next_price)

        price_forecast = price_forecast[1:] # Remove the starting price

        # Create a future date index for the forecast
        last_date = self.train_series.index[-1]
        future_index = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=n_periods, freq='B')

        forecast_series = pd.Series(price_forecast, index=future_index, name='forecast')

        return forecast_series
