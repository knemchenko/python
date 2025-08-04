import pandas as pd
import asyncio
import os
from telegram import Bot
from telegram.constants import ParseMode
from typing import Dict
from src import config

class Reporter:
    """
    Handles formatting and sending the daily report to Telegram.
    """

    def __init__(self):
        """
        Initializes the Reporter and the Telegram Bot.
        """
        if not config.TELEGRAM_TOKEN or config.TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
            raise ValueError("Telegram token is not configured in src/config.py")
        if not config.TELEGRAM_CHAT_ID or config.TELEGRAM_CHAT_ID == "YOUR_TELEGRAM_CHAT_ID":
            raise ValueError("Telegram chat ID is not configured in src/config.py")

        self.bot = Bot(token=config.TELEGRAM_TOKEN)
        self.chat_id = config.TELEGRAM_CHAT_ID

    def _format_report(self, ticker: str, current_price: float, forecasts: Dict[str, pd.Series]) -> str:
        """
        Formats the textual part of the report.

        Args:
            ticker (str): The ticker symbol.
            current_price (float): The latest actual price.
            forecasts (Dict[str, pd.Series]): The forecasts from the models.

        Returns:
            str: A Markdown-formatted string for the report.
        """
        report_lines = [
            f"*{ticker} Daily Forecast Report*",
            f"*Current Price:* `${current_price:,.2f}`",
            "---",
            "*Forecasts:*"
        ]

        for model_name, forecast in forecasts.items():
            # Robust check for an empty or all-NaN forecast series
            if not forecast.empty and not forecast.isnull().all():
                pred_1d = forecast.iloc[0]
                pred_7d = forecast.iloc[6] if len(forecast) > 6 else forecast.iloc[-1]
                pred_30d = forecast.iloc[29] if len(forecast) > 29 else forecast.iloc[-1]

                report_lines.append(f"*- {model_name}:*")
                report_lines.append(f"  - 1 Day: `${pred_1d:,.2f}`")
                report_lines.append(f"  - 7 Days: `${pred_7d:,.2f}`")
                report_lines.append(f"  - 30 Days: `${pred_30d:,.2f}`")
            else:
                report_lines.append(f"*- {model_name}:* `Forecast failed`")

        # Note: Historical accuracy part is omitted as per the implementation plan.
        # It can be added later by storing and retrieving past forecasts.

        return "\n".join(report_lines)

    async def send_report(self, ticker: str, current_price: float, forecasts: Dict[str, pd.Series], plot_path: str):
        """
        Formats and sends the full report. This is now an async method.
        """
        if not plot_path or not os.path.exists(plot_path):
            print("Plot file not found. Cannot send report.")
            return

        report_text = self._format_report(ticker, current_price, forecasts)

        try:
            with open(plot_path, 'rb') as photo:
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo,
                    caption=report_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            print(f"Successfully sent report to Telegram chat {self.chat_id}")
        except Exception as e:
            print(f"Failed to send report to Telegram. Error: {e}")
