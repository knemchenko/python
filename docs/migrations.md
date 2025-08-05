# Data Schema Migrations

This document outlines the schema for the data files generated and used by the project.

## `forecast_history.parquet`

This file stores the raw output of the signal generation process. It is appended to on each run of `run_daily_update.py`.

- **ticker** (`string`): The stock ticker symbol (e.g., "AAPL").
- **timestamp** (`datetime64[ns]`): The timestamp when the forecast was generated. For back-filled data, this is the date of the historical data point.
- **horizon_days** (`int64`): The forecast horizon in days (e.g., 1, 5, 30).
- **direction** (`string`): The direction of the predicted trade ("Long" or "Short").
- **expected_return** (`float64`): The ensemble model's predicted return (`r_hat`) for this horizon.
- **confidence_sigma** (`float64`): The confidence of the signal, measured as the ratio of the absolute expected return to the historical RMSE sigma for that horizon (`|r_hat| / sigma`).
- **weight** (`float64`): The suggested trade size, capped by the Kelly criterion (`KELLY_CAP`).
- **vix_filter** (`bool`): Whether the VIX filter was passed at the time of signal generation.
- **volume_filter** (`bool`): Whether the volume filter was passed at the time of signal generation.

## `metrics.csv`

This file stores the output of the weekly `metrics_job.py`. A new row is appended each time the job runs.

- **date** (`string`, `YYYY-MM-DD`): The date the metrics were calculated.
- **sharpe_ratio_60d** (`float64`): The annualized Sharpe Ratio calculated on the realized returns of the last 60 days of trades.
- **coverage_pct** (`float64`): The percentage of trading days in the history that a signal was generated.
- **psi_confidence** (`float64`): The Population Stability Index for the `confidence_sigma` score, comparing the first half of the data to the second half. A low value (< 0.1) indicates a stable distribution.
