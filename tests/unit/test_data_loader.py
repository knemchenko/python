import unittest
from src.data_loader import DataLoader


class TestDataLoader(unittest.TestCase):
    def test_initialization(self):
        """
        Tests that the DataLoader initializes without errors.
        """
        try:
            _ = DataLoader()
            # If the above line runs without error, the test passes.
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"DataLoader initialization failed with an exception: {e}")


if __name__ == "__main__":
    unittest.main()
