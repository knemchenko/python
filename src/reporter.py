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

    def _format_report(self, ticker: str, current_price: float, forecasts: Dict[str, pd.Series], accuracy_results: Dict) -> str:
        """
        Formats the textual part of the report.

        Args:
            ticker (str): The ticker symbol.
            current_price (float): The latest actual price.
            forecasts (Dict[str, pd.Series]): The forecasts from the models.
            accuracy_results (Dict): A dictionary with historical accuracy metrics.

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

        # Add historical accuracy table
        if accuracy_results:
            report_lines.append("\n---")
            report_lines.append("*Historical Accuracy*")
            # Using Markdown code block for a table-like structure
            header = f"`{'h':<4} | {'RMSE':<6} | {'MAPE':<8}`"
            divider = "`" + "-"*25 + "`"
            report_lines.append(header)
            report_lines.append(divider)
            for horizon, metrics in accuracy_results.items():
                line = f"`{horizon:<4} | {metrics['RMSE']:<6.2f} | {metrics['MAPE']:<7.2f}%`"
                report_lines.append(line)

        return "\n".join(report_lines)

    async def send_report(self, ticker: str, current_price: float, forecasts: Dict[str, pd.Series], accuracy_results: Dict, plot_path: str):
        """
        Formats and sends the full report. This is now an async method.
        """
        if not plot_path or not os.path.exists(plot_path):
            print("Plot file not found. Cannot send report.")
            return

        report_text = self._format_report(ticker, current_price, forecasts, accuracy_results)

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
