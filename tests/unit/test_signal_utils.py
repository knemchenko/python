import unittest
import pandas as pd
from src.signal_utils import generate_signals


class TestSignalUtils(unittest.TestCase):
    def test_generate_signals_no_forecast(self):
        """
        Tests that generate_signals returns an empty list when there are no forecasts.
        """
        signals = generate_signals(
            ticker="TEST", forecasts={}, sigma_dict={1: 0.1}, vix_data=pd.Series([15])
        )
        self.assertEqual(signals, [])

    def test_generate_signals_dummy_forecast(self):
        """
        Tests the basic signal generation logic with a dummy forecast.
        Note: This is a placeholder test. More comprehensive tests with mocked
        data and edge cases should be added.
        """
        dummy_forecast_data = {
            "model1": {
                "r_hat": pd.Series([0.05, 0.10]),
                "forecast": pd.Series([105, 110]),
            }
        }
        sigma_dict = {1: 0.01, 2: 0.02}
        vix_data = pd.Series([15, 16])

        signals = generate_signals(
            ticker="TEST",
            forecasts=dummy_forecast_data,
            sigma_dict=sigma_dict,
            vix_data=vix_data,
        )
        # We expect signals because the r_hat (0.05, 0.10) is > sigma * threshold
        self.assertGreater(len(signals), 0)
        self.assertEqual(signals[0]["ticker"], "TEST")


if __name__ == "__main__":
    unittest.main()
