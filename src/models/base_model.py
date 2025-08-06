from abc import ABC, abstractmethod
import pandas as pd  # type: ignore
from typing import Any


class BaseModel(ABC):
    """
    Abstract base class for all forecasting models.
    It defines the standard interface for fitting and predicting.
    """

    @abstractmethod
    def __init__(self, **kwargs: Any) -> None:
        """
        Initializes the model. Hyperparameters can be passed as keyword arguments.
        """
        self.model: Any = None
        self.train_series: pd.Series | None = None

    @abstractmethod
    def fit(self, data: pd.Series) -> None:
        """
        Fits the model to the provided time series data.

        Args:
            data (pd.Series): The time series data to train the model on.
        """
        pass

    @abstractmethod
    def predict(self, n_periods: int) -> pd.Series:
        """
        Makes a forecast for a specified number of future periods.

        Args:
            n_periods (int): The number of periods to forecast into the future.

        Returns:
            pd.Series: A series containing the forecasted values, with a DatetimeIndex.
        """
        pass

    def __str__(self) -> str:
        return self.__class__.__name__
