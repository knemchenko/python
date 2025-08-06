# -- Configuration File --
from decouple import config  # type: ignore

# General
RANDOM_SEED = 42

# List of tickers to be processed
TICKERS = ["CSPX.L", "AAPL", "MSFT"]

# Start date for historical data
START_DATE = "2018-01-01"

# Data cache directory
DATA_DIR = "data"

# Telegram Bot Configuration
# IMPORTANT: Add your credentials to a .env file in the project root
# Example .env file:
# TELEGRAM_TOKEN="your_token_here"
# TELEGRAM_CHAT_ID="your_chat_id_here"
TELEGRAM_TOKEN = config("TELEGRAM_TOKEN", default="your_token_here")
TELEGRAM_CHAT_ID = config("TELEGRAM_CHAT_ID", default="your_chat_id_here")


# Plotting Configuration
SAVE_PLOTS_TO_DISK = True  # Whether to save the forecast plots locally

# -- Trading Strategy Parameters --
# If True, only publish signals for long positions with positive expected returns.
PUBLISH_LONG_ONLY = True
THRESHOLD_SIGMA = 0.8  # The threshold for forecast confidence (0.8 sigma).
VIX_PERCENTILE = 75  # The percentile for the VIX filter.
# The maximum Kelly criterion fraction to be used for position sizing.
KELLY_CAP = 0.25

# -- Model & Backtesting Parameters --
# ATR multipliers, MaxNAV, etc. can be added here as they are implemented.
# For now, these are placeholders.
ATR_PERIOD = 14
ATR_MULTIPLIER_LONG = 3.0
ATR_MULTIPLIER_SHORT = 3.0
MAX_NAV_RISK_PER_TRADE = 0.02
