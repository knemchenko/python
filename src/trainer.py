import pandas as pd
import numpy as np
import joblib
import os

from src.models.arima import ArimaModel
from src.models.holt_winters import HoltWintersModel
from src.models.garch import GarchModel
from src.models.random_forest import RandomForestModel
from src.models.xgboost import XGBoostModel
from src import config

class Trainer:
    """
    Handles the training, evaluation, and selection of forecasting models.
    """

    def __init__(self, ticker: str, data: pd.DataFrame):
        """
        Initializes the Trainer.

        Args:
            ticker (str): The ticker symbol for which to train models.
            data (pd.DataFrame): The dataframe containing the historical price data.
        """
        self.ticker = ticker
        self.data = data['Close'] # We are forecasting the 'Close' price
        self.models = self._get_all_models()
        self.results = []

        # Ensure the directory for saving models exists
        if not os.path.exists(config.DATA_DIR):
            os.makedirs(config.DATA_DIR)

    def _get_all_models(self):
        """
        Instantiates and returns a list of all models to be trained.
        """
        # TODO: Add hyperparameter tuning or more specific configurations here later
        # TODO: Add hyperparameter tuning or more specific configurations here later
        return [
            ArimaModel(order=(5,1,0)), # Removed invalid kwargs for statsmodels version
            HoltWintersModel(seasonal_periods=52), # Assuming weekly seasonality in daily data
            GarchModel(),
            RandomForestModel(n_lags=10),
            XGBoostModel(n_lags=10)
        ]

    def _split_data(self, test_size=0.3):
        """
        Splits the data into training and testing sets.
        """
        split_index = int(len(self.data) * (1 - test_size))
        train_data = self.data.iloc[:split_index]
        test_data = self.data.iloc[split_index:]
        return train_data, test_data

    def _calculate_rmse(self, y_true, y_pred):
        """
        Calculates the Root Mean Squared Error.
        """
        return np.sqrt(np.mean((y_true - y_pred)**2))

    def _backtest(self, predictions: pd.Series, actual: pd.Series):
        """
        Performs a simple backtest to calculate financial metrics.
        Strategy: Go long if forecast for tomorrow > today's price. Otherwise, do nothing.
        """
        if predictions.empty or actual.empty:
            return 0, 0, 0

        # Align series and calculate strategy returns
        actual_shifted = actual.shift(1).dropna()
        # Reindex both series to ensure they align perfectly, then compare their values to avoid label-based comparison issues.
        common_index = predictions.index.intersection(actual_shifted.index)
        preds_aligned = predictions.reindex(common_index)
        actuals_aligned = actual_shifted.reindex(common_index)
        strategy_signals = pd.Series(preds_aligned.values > actuals_aligned.values, index=common_index)

        returns = actual.pct_change().dropna()
        strategy_returns = pd.Series(np.where(strategy_signals.reindex(returns.index).fillna(False), returns, 0), index=returns.index)

        if strategy_returns.std() == 0 or len(strategy_returns) < 2:
            return 0, 0, 0

        # Calculate metrics
        sharpe_ratio = (strategy_returns.mean() / strategy_returns.std()) * np.sqrt(252) if strategy_returns.std() > 0 else 0

        downside_returns = strategy_returns[strategy_returns < 0]
        sortino_ratio = (strategy_returns.mean() / downside_returns.std()) * np.sqrt(252) if len(downside_returns) > 1 and downside_returns.std() > 0 else 0

        win_rate = (strategy_returns > 0).sum() / (strategy_returns != 0).sum() if (strategy_returns != 0).sum() > 0 else 0

        return sharpe_ratio, sortino_ratio, win_rate

    def train_and_evaluate(self):
        """
        Trains all models, evaluates them, and stores the results.
        """
        train_data, test_data = self._split_data()

        for model in self.models:
            print(f"--- Processing model: {model} for ticker: {self.ticker} ---")
            try:
                # Train model
                model.fit(train_data)

                # Make predictions
                predictions_raw = model.predict(n_periods=len(test_data))

                # Force alignment of predictions with the test data index for robust evaluation
                predictions = pd.Series(predictions_raw.values, index=test_data.index)

                # Evaluate
                rmse = self._calculate_rmse(test_data, predictions)
                sharpe, sortino, win_rate = self._backtest(predictions, test_data)

                self.results.append({
                    "model_name": str(model),
                    "model_instance": model,
                    "rmse": rmse,
                    "sharpe_ratio": sharpe,
                    "sortino_ratio": sortino,
                    "win_rate": win_rate
                })
                print(f"RMSE: {rmse:.4f}, Sharpe: {sharpe:.4f}, Sortino: {sortino:.4f}, WinRate: {win_rate:.2%}")

            except Exception as e:
                print(f"Failed to train or evaluate {model}. Error: {e}")
                # Optionally, store failure result
                self.results.append({
                    "model_name": str(model),
                    "model_instance": model,
                    "rmse": np.inf, "sharpe_ratio": -np.inf, "sortino_ratio": -np.inf, "win_rate": 0
                })

    def select_and_save_best_models(self, n_best=3):
        """
        Selects the best N models based on a weighted ranking, retrains them on all data,
        and saves them to a file.
        """
        if not self.results:
            print("No models were successfully evaluated. Cannot select best models.")
            return

        df_results = pd.DataFrame(self.results)

        # Create ranks for each metric
        df_results['rmse_rank'] = df_results['rmse'].rank(ascending=True)
        df_results['sharpe_rank'] = df_results['sharpe_ratio'].rank(ascending=False)
        df_results['sortino_rank'] = df_results['sortino_ratio'].rank(ascending=False)

        # Calculate weighted score (lower is better)
        df_results['final_score'] = (
            0.50 * df_results['rmse_rank'] +
            0.30 * df_results['sharpe_rank'] +
            0.20 * df_results['sortino_rank']
        )

        df_results = df_results.sort_values(by='final_score', ascending=True)

        print("\n--- Model Evaluation Ranking ---")
        print(df_results[['model_name', 'rmse', 'sharpe_ratio', 'sortino_ratio', 'final_score']])

        best_models_df = df_results.head(n_best)
        best_models_instances = []

        print(f"\n--- Retraining Top {n_best} Models on Full Dataset ---")
        for index, row in best_models_df.iterrows():
            model = row['model_instance']
            print(f"Retraining {model}...")
            try:
                model.fit(self.data) # Retrain on the full dataset
                best_models_instances.append(model)
            except Exception as e:
                print(f"Failed to retrain {model}. Error: {e}")

        # Save the list of retrained, best-performing model instances
        save_path = os.path.join(config.DATA_DIR, f"best_models_{self.ticker}.pkl")
        joblib.dump(best_models_instances, save_path)
        print(f"Top {len(best_models_instances)} models saved to {save_path}")

        return best_models_instances
