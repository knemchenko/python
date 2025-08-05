# --- Main Configuration File ---

# List of assets to be processed
# Format: Ticker, Base_Currency, Beta_Benchmark
ASSETS = [
    ("CSPX.L", "USD", "SPY"),
    ("AAPL", "USD", "SPY"),
    ("MSFT", "USD", "SPY"),
    ("EUNL.DE", "EUR", "EXSA.DE"), # Example for a European asset
]

# General data settings
DATA_SETTINGS = {
    "start_date": "2018-01-01",
    "data_dir": "data",
    "prices_path": "daily_prices",
    "forecasts_path": "forecasts",
    "fx_rates_path": "fx_rates"
}

# --- Trading Strategy Configuration ---

FILTERS = {
    "vix_percentile": 75,
    "volume_ma_days": 30,
    "rmse_sigma_threshold": 0.8
}

PUBLISHER = {
    "long_only": True,
    "threshold_sigma": 0.8,
    "chat_id": "YOUR_TELEGRAM_CHAT_ID" # Replace with your channel/chat ID
}

RISK = {
    "kelly_cap": 0.25,
    "cvar_cap_pct_nav": 0.75,
    "max_trade_pct_nav": 0.03,
    "portfolio_long_cap_pct_nav": 30.0,
    "portfolio_short_cap_pct_nav": 30.0,
    "max_dd_10day_cap_pct_nav": 4.0
}

EXITS = {
    "stop_mult_atr": 3.0,
    "overnight_gap_atr": 2.0,
    "trail_mult_atr": 1.2,
    "tp_factor": 0.8
}

# --- System and API Configuration ---

TELEGRAM = {
    "token": "YOUR_TELEGRAM_BOT_TOKEN" # Replace with your bot token
}

# Interactive Brokers API settings
IB_API = {
    "host": "127.0.0.1",
    "port": 5000, # Default for Gateway, use 7497 for TWS
    "client_id": 1,
    "paper_account": "YOUR_PAPER_ACCOUNT_ID" # Replace with your paper trading account ID
}

# Plotting Configuration
SAVE_PLOTS_TO_DISK = True  # Whether to save the forecast plots locally
