import pandas as pd
import numpy as np
from typing import Dict, List, Any
from src import config

def generate_signals(
    ticker: str,
    forecasts: Dict[str, Dict[str, pd.Series]],
    sigma_dict: Dict[int, float],
    vix_data: pd.Series = None,
    volume_data: pd.Series = None
) -> List[Dict[str, Any]]:
    """
    Generates trading signals based on model forecasts, confidence, and market filters.

    Args:
        ticker (str): The ticker symbol.
        forecasts (Dict): The forecasts from the predictor, including 'r_hat'.
                          e.g., {'Arima': {'forecast': pd.Series, 'r_hat': pd.Series}}
        sigma_dict (Dict): A dictionary mapping horizon (int) to its historical RMSE sigma.
        vix_data (pd.Series, optional): Historical VIX data. Defaults to None.
        volume_data (pd.Series, optional): Historical volume data. Defaults to None.

    Returns:
        List[Dict[str, Any]]: A list of signal dictionaries. Each dictionary
                              represents a potential trade.
    """
    signals = []

    # --- 1. Ensemble Forecasting ---
    # Average the r_hat across all models for each horizon
    all_r_hats = [f['r_hat'] for f in forecasts.values() if not f['r_hat'].empty]
    if not all_r_hats:
        return []

    ensemble_r_hat = pd.concat(all_r_hats, axis=1).mean(axis=1)

    # Define the horizons we are interested in, to match the trainer
    horizons_to_check = [1, 5, 10, 20, 30]

    for h in horizons_to_check:
        # Check if the horizon exists in the sigma dictionary
        if h not in sigma_dict:
            continue

        # Check if the forecast is long enough for this horizon
        if len(ensemble_r_hat) < h:
            continue

        # Get the return and sigma for the specific horizon `h`
        r_hat = ensemble_r_hat.iloc[h - 1]
        sigma = sigma_dict[h]
        # The signal is considered confident if the predicted return is greater than a threshold of its own error
        is_confident = abs(r_hat) > (sigma * config.THRESHOLD_SIGMA)

        # --- 3. VIX Filter ---
        vix_filter_passed = True # Default to True
        if vix_data is not None and not vix_data.empty:
            vix_percentile_threshold = np.percentile(vix_data, config.VIX_PERCENTILE)
            current_vix = vix_data.iloc[-1]
            if current_vix > vix_percentile_threshold:
                vix_filter_passed = False # High VIX, market is fearful, filter out signal

        # --- 4. Volume Filter ---
        volume_filter_passed = True # Placeholder for now
        # Example logic: if volume_data.iloc[-1] < volume_data.mean(): volume_filter_passed = False

        # --- 5. Generate Signal ---
        if is_confident and vix_filter_passed and volume_filter_passed:
            direction = "Long" if r_hat > 0 else "Short"

            # Kelly Criterion for position sizing (simplified)
            # K = W - (1 - W) / R, where W is win probability and R is win/loss ratio.
            # We can approximate W using our confidence and R using r_hat vs sigma.
            # For simplicity, we'll use a more direct heuristic for now.
            # A higher |r_hat|/sigma ratio suggests a better trade.

            weight = min(abs(r_hat) / (sigma * 2), config.KELLY_CAP) # Capped weight

            signals.append({
                "ticker": ticker,
                "timestamp": pd.Timestamp.now(),
                "horizon_days": h,
                "direction": direction,
                "expected_return": r_hat,
                "confidence_sigma": abs(r_hat) / sigma if sigma > 0 else 0,
                "weight": weight,
                "vix_filter": vix_filter_passed,
                "volume_filter": volume_filter_passed
            })

    return signals
