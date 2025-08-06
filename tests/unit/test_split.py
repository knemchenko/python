import unittest
import pandas as pd
from src.utils.split import train_test_split_ts


class TestSplit(unittest.TestCase):
    def setUp(self):
        """Set up a sample time series for testing."""
        dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=100, freq="D"))
        self.ts_data = pd.Series(range(100), index=dates)

    def test_split_ratio(self):
        """Tests that the split ratio is approximately correct."""
        train, test = train_test_split_ts(self.ts_data, test_size=0.3)
        self.assertEqual(len(train), 70)
        self.assertEqual(len(test), 30)

    def test_no_overlap(self):
        """Tests that the last date in train is before the first date in test."""
        train, test = train_test_split_ts(self.ts_data, test_size=0.3)
        self.assertLess(train.index.max(), test.index.min())

    def test_no_data_loss(self):
        """Tests that the total number of samples is conserved."""
        train, test = train_test_split_ts(self.ts_data, test_size=0.25)
        self.assertEqual(len(train) + len(test), len(self.ts_data))

    def test_non_datetime_index_raises_error(self):
        """Tests that a ValueError is raised for non-datetime index."""
        non_ts_data = pd.Series(range(10))
        with self.assertRaises(ValueError):
            train_test_split_ts(non_ts_data)


if __name__ == "__main__":
    unittest.main()
