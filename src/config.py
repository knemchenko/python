# -- Configuration File --

# List of tickers to be processed
TICKERS = ["CSPX.L", "AAPL", "MSFT"]

# Start date for historical data
START_DATE = "2018-01-01"

# Data cache directory
DATA_DIR = "data"

# Telegram Bot Configuration
TELEGRAM_TOKEN = "436150352:AAEqYq-cUO93C8cZqgvbyz6gl-nV7QZsuZU"  # Replace with your bot token
TELEGRAM_CHAT_ID = "58623777"  # Replace with your channel/chat ID

# Plotting Configuration
SAVE_PLOTS_TO_DISK = True  # Whether to save the forecast plots locally

# -- Trading Strategy Parameters --
PUBLISH_LONG_ONLY = True  # If True, only publish signals for long positions with positive expected returns.
THRESHOLD_SIGMA = 0.8     # The threshold for forecast confidence (0.8 sigma).
VIX_PERCENTILE = 75       # The percentile for the VIX filter.
KELLY_CAP = 0.25          # The maximum Kelly criterion fraction to be used for position sizing.

# -- Model & Backtesting Parameters --
# ATR multipliers, MaxNAV, etc. can be added here as they are implemented.
# For now, these are placeholders.
ATR_PERIOD = 14
ATR_MULTIPLIER_LONG = 3.0
ATR_MULTIPLIER_SHORT = 3.0
MAX_NAV_RISK_PER_TRADE = 0.02
