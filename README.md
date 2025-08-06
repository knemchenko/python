# Financial Forecasting and Trading Signal Engine

This project provides a framework for fetching financial data, training time-series forecasting models, generating trading signals, and reporting them. It is designed to be run as a daily automated pipeline.

## Features

- **Multi-Model Ensemble:** Uses a variety of models (ARIMA, Holt-Winters, GARCH, RandomForest, XGBoost) to generate robust forecasts.
- **Walk-Forward Validation:** Employs realistic walk-forward validation for model evaluation.
- **Signal Generation:** Creates actionable trading signals based on forecast confidence, market regime (VIX), and volume filters.
- **Automated Reporting:** Sends daily signal reports with charts to a Telegram channel.
- **Performance Tracking:** Includes a weekly job to calculate key performance metrics like Sharpe Ratio, Coverage, and Population Stability Index (PSI).
- **Historical Back-filling:** Provides a script to generate historical signals to bootstrap performance analysis.

## Workflow

The project operates in a two-stage automated workflow:

1.  **Daily Update (`run_daily_update.py`):**
    *   This script runs every day.
    *   It fetches the latest price data for the configured tickers and the VIX index.
    *   It loads the best-performing pre-trained models.
    *   It generates new price forecasts and calculates expected returns.
    *   It then generates trading signals based on a set of configurable filters.
    *   All generated signals are stored in `data/forecast_history.parquet`.
    *   If any signals pass the final filters (e.g., `PUBLISH_LONG_ONLY`), a report with a forecast chart is sent to Telegram.

2.  **Weekly Metrics Job (`metrics_job.py`):**
    *   This script is intended to be run weekly (e.g., via a cron job).
    *   It reads the entire `forecast_history.parquet` file.
    *   It calculates performance metrics like the 60-day walk-forward Sharpe Ratio.
    *   It appends these metrics to `data/metrics.csv`.
    *   If performance degrades significantly (Sharpe Ratio < 0.5), it creates a `RETRAIN_REQUIRED` file, indicating that the models should be retrained from scratch.

## Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  Install the required Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```
    *New dependencies include `yfinance`, `pandas`, `scikit-learn`, `statsmodels`, `xgboost`, `matplotlib`, `python-telegram-bot`, `arch`, `numpy`, `scipy`, `joblib`, `pmdarima`, `torch`, `darts`, and `tqdm`.*

## Configuration

All configuration is handled in the `src/config.py` file. Update the parameters to match your setup.

```python
# src/config.py

# -- Core Settings --
TICKERS = ["CSPX.L", "AAPL", "MSFT"]
START_DATE = "2018-01-01"
DATA_DIR = "data"

# -- Telegram Bot Configuration --
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

# -- Trading Strategy Parameters --
# If True, only publish signals for long positions with positive expected returns.
PUBLISH_LONG_ONLY = True
# The threshold for forecast confidence (e.g., 0.8 means r_hat must be > 0.8 * sigma).
THRESHOLD_SIGMA = 0.8
# The VIX percentile above which signals will be filtered out.
VIX_PERCENTILE = 75
# The maximum Kelly criterion fraction to be used for position sizing.
KELLY_CAP = 0.25

# ... other parameters
```

## Usage

1.  **Initial Model Training:**
    Before you can run the daily updates, you must train an initial set of models.
    ```bash
    python scripts/train_initial_models.py
    ```
    This will train models for each ticker in `config.TICKERS`, evaluate them, and save the best ones to the `data/` directory, along with the `metrics_{ticker}.pkl` files containing the error sigmas.

2.  **Run the Daily Update:**
    To manually trigger the daily update process:
    ```bash
    python scripts/run_daily_update.py
    ```

3.  **Run the Weekly Metrics Job:**
    To manually trigger the weekly metrics calculation:
    ```bash
    python scripts/metrics_job.py
    ```

4.  **(Optional) Back-fill Historical Signals:**
    To populate the `forecast_history.parquet` file with data from the past, run the back-fill script. This is useful for getting a baseline for your metrics. **Note:** This can take a long time to run.
    ```bash
    python scripts/backfill_history.py
    ```

## Dashboard

This project includes a Flask-based web dashboard for monitoring signals, performance, and system status.

### Running with Docker

The easiest way to run the dashboard is with Docker Compose.

1.  **Build and Run the Container:**
    ```bash
    docker-compose up --build
    ```

2.  Open your browser and navigate to `http://localhost:5001`.

3.  Login with the credentials specified in your `docker-compose.yml` or environment variables (default: `admin`/`supersecret`).

## Data Schema

For details on the data schemas for `forecast_history.parquet` and `metrics.csv`, please see the `docs/migrations.md` file.
