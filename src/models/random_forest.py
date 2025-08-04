import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from src.models.base_model import BaseModel
import numpy as np

class RandomForestModel(BaseModel):
    """
    A wrapper for the scikit-learn RandomForestRegressor model, adapted for time series forecasting.
    """

    def __init__(self, n_estimators=100, max_depth=10, n_lags=5, **kwargs):
        """
        Initializes the RandomForestModel.

        Args:
            n_estimators (int): The number of trees in the forest.
            max_depth (int): The maximum depth of the tree.
            n_lags (int): The number of past values (lags) to use as features.
        """
        super().__init__()
        self.n_lags = n_lags
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42,
            n_jobs=-1,
            **kwargs
        )
        self.train_series = None

    def _create_features(self, data: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
        """
        Creates a feature matrix (X) and target vector (y) from time series data.
        """
        X, y = [], []
        for i in range(len(data) - self.n_lags):
            X.append(data.iloc[i:i + self.n_lags].values)
            y.append(data.iloc[i + self.n_lags])
        return pd.DataFrame(X), pd.Series(y)

    def fit(self, data: pd.Series):
        """
        Fits the RandomForest model to the data.

        Args:
            data (pd.Series): Time series data to train on.
        """
        print(f"Fitting RandomForestModel with {self.n_lags} lags...")
        self.train_series = data
        X, y = self._create_features(data)
        self.model.fit(X, y)

    def predict(self, n_periods: int) -> pd.Series:
        """
        Makes predictions for n_periods into the future using an iterative approach.

        Args:
            n_periods (int): The number of periods to forecast.

        Returns:
            pd.Series: A series of forecasted values with a DatetimeIndex.
        """
        if self.train_series is None:
            raise RuntimeError("The model has not been fitted yet. Call fit() first.")

        # Get the last n_lags from the training data to start the prediction
        history = self.train_series.values[-self.n_lags:].tolist()
        predictions = []

        for _ in range(n_periods):
            # Prepare the input for the next prediction
            input_vector = np.array(history[-self.n_lags:]).reshape(1, -1)

            # Predict the next value
            next_pred = self.model.predict(input_vector)[0]
            predictions.append(next_pred)

            # Append the prediction to history for the next iteration
            history.append(next_pred)

        # Create a future date index for the forecast
        last_date = self.train_series.index[-1]
        future_index = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=n_periods, freq='B')

        forecast_series = pd.Series(predictions, index=future_index, name='forecast')

        return forecast_series
