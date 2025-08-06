import unittest
import pandas as pd
from src.models.random_forest import RandomForestModel
from src.models.xgboost import XGBoostModel


class TestModelFeatureCreation(unittest.TestCase):
    def setUp(self):
        """Set up a sample time series for testing."""
        dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=20, freq="D"))
        self.ts_data = pd.Series(range(20), index=dates)

    def test_no_future_leakage_rf(self):
        """
        Tests that the feature creation for RandomForestModel does not leak future info.
        The value of y at index i should correspond to the value of the original
        series at index i + n_lags.
        """
        n_lags = 5
        model = RandomForestModel(n_lags=n_lags)
        X, y = model._create_features(self.ts_data)

        # The first value of y should be the (n_lags)-th value of the original series
        self.assertEqual(y.iloc[0], self.ts_data.iloc[n_lags])

        # The last value of y should be the last value of the original series
        self.assertEqual(y.iloc[-1], self.ts_data.iloc[-1])

        # Check a random value in the middle
        i = 10
        self.assertEqual(y.iloc[i], self.ts_data.iloc[i + n_lags])

    def test_no_future_leakage_xgb(self):
        """
        Tests that the feature creation for XGBoostModel does not leak future info.
        """
        n_lags = 7
        model = XGBoostModel(n_lags=n_lags)
        X, y = model._create_features(self.ts_data)

        # The first value of y should be the (n_lags)-th value of the original series
        self.assertEqual(y.iloc[0], self.ts_data.iloc[n_lags])

        # The last value of y should be the last value of the original series
        self.assertEqual(y.iloc[-1], self.ts_data.iloc[-1])


if __name__ == "__main__":
    unittest.main()
