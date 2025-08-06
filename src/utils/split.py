import pandas as pd
from typing import Tuple


def train_test_split_ts(
    data: pd.Series, test_size: float = 0.3
) -> Tuple[pd.Series, pd.Series]:
    """
    Splits a time series into training and testing sets without shuffling.

    Args:
        data (pd.Series): The time series data to split.
        test_size (float): The proportion of the dataset to include in the test split.

    Returns:
        Tuple[pd.Series, pd.Series]: A tuple containing the train and test splits.
    """
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Data must have a DatetimeIndex.")

    split_index = int(len(data) * (1 - test_size))
    train_data = data.iloc[:split_index]
    test_data = data.iloc[split_index:]

    # Ensure there is no overlap
    if not train_data.index.max() < test_data.index.min():
        raise ValueError("Train and test sets are overlapping or not ordered correctly.")

    return train_data, test_data
