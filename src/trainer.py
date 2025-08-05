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

    def _calculate_walk_forward_rmse(self, model, train_data, test_data, horizons=[1, 5, 10, 20, 30]):
        """
        Calculates walk-forward RMSE and sigma for different horizons.
        This is a more realistic backtesting approach.
        """
        predictions = {h: [] for h in horizons}
        actuals = {h: [] for h in horizons}
        history = train_data.copy()

        for t in range(len(test_data) - max(horizons)):
            # Refit model on historical data up to the current point
            model.fit(history)

            # Forecast for all required horizons
            forecast = model.predict(n_periods=max(horizons))

            # Store predictions and actuals for each horizon
            for h in horizons:
                predictions[h].append(forecast.iloc[h-1])
                actuals[h].append(test_data.iloc[t + h - 1])

            # Add the actual observation to history for the next iteration
            new_observation = test_data.iloc[[t]]
            history = pd.concat([history, new_observation])

        # Calculate RMSE and Sigma (std of errors) for each horizon
        rmse_scores = {}
        sigma_rmse = {}
        for h in horizons:
            errors = np.array(actuals[h]) - np.array(predictions[h])
            rmse_scores[h] = np.sqrt(np.mean(errors**2))
            sigma_rmse[h] = np.std(errors)

        return rmse_scores, sigma_rmse

    def train_and_evaluate(self):
        """
        Trains all models, evaluates them using walk-forward validation, and stores results.
        """
        train_data, test_data = self._split_data()

        for model in self.models:
            print(f"--- Processing model: {model} for ticker: {self.ticker} ---")
            try:
                # Evaluate using walk-forward validation
                rmse_scores, sigma_rmse = self._calculate_walk_forward_rmse(model, train_data, test_data)

                # For simplicity, we'll use the average RMSE for ranking
                avg_rmse = np.mean(list(rmse_scores.values()))

                # The old backtest is not horizon-aware, so we'll run it on 1-day ahead forecasts for a simple financial metric
                # Note: This is a simplification. A proper backtest would use the signals from all horizons.
                model.fit(train_data)
                predictions = model.predict(n_periods=len(test_data))
                predictions = pd.Series(predictions.values, index=test_data.index)
                sharpe, sortino, win_rate = 0,0,0 # self._backtest(predictions, test_data) # Disabling for now

                self.results.append({
                    "model_name": str(model),
                    "model_instance": model,
                    "rmse": avg_rmse,  # Using average RMSE for ranking
                    "sharpe_ratio": sharpe,
                    "sortino_ratio": sortino,
                    "win_rate": win_rate,
                    "sigma_rmse": sigma_rmse # Store the per-horizon sigma
                })
                print(f"Avg RMSE: {avg_rmse:.4f}, Sigmas: {sigma_rmse}")

            except Exception as e:
                print(f"Failed to train or evaluate {model}. Error: {e}")
                self.results.append({
                    "model_name": str(model), "model_instance": model, "rmse": np.inf,
                    "sharpe_ratio": -np.inf, "sortino_ratio": -np.inf, "win_rate": 0, "sigma_rmse": {}
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

        # Aggregate sigma_rmse from the best models
        aggregated_sigma_rmse = {}
        all_sigmas = best_models_df['sigma_rmse'].tolist()

        if all_sigmas:
            # Assuming all sigma dicts have the same keys (horizons)
            horizons = all_sigmas[0].keys()
            for h in horizons:
                # Average the sigma for each horizon across the best models
                horizon_sigmas = [s[h] for s in all_sigmas if h in s and np.isfinite(s[h])]
                if horizon_sigmas:
                    aggregated_sigma_rmse[h] = np.mean(horizon_sigmas)

        for index, row in best_models_df.iterrows():
            model = row['model_instance']
            print(f"Retraining {model}...")
            try:
                model.fit(self.data) # Retrain on the full dataset
                best_models_instances.append(model)
            except Exception as e:
                print(f"Failed to retrain {model}. Error: {e}")

        # Save the list of retrained, best-performing model instances
        model_save_path = os.path.join(config.DATA_DIR, f"best_models_{self.ticker}.pkl")
        joblib.dump(best_models_instances, model_save_path)
        print(f"Top {len(best_models_instances)} models saved to {model_save_path}")

        # Save the aggregated metrics
        metrics_save_path = os.path.join(config.DATA_DIR, f"metrics_{self.ticker}.pkl")
        joblib.dump(aggregated_sigma_rmse, metrics_save_path)
        print(f"Aggregated RMSE sigmas saved to {metrics_save_path}")

        return best_models_instances
