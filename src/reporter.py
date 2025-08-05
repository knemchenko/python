import json
import os
import asyncio
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode
from typing import List, Dict, Any
from src import config

class Reporter:
    """
    Handles formatting and sending the daily report to Telegram and logging signals.
    """

    def __init__(self):
        """
        Initializes the Reporter and the Telegram Bot.
        """
        self.bot = Bot(token=config.TELEGRAM_TOKEN)
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.log_path = os.path.join(config.DATA_DIR, "publish_log.json")

    def _log_published_signals(self, signals: List[Dict[str, Any]]):
        """Logs the signals that are being published to a JSON file."""
        log_entry = {str(pd.Timestamp.now()): signals}

        # Custom JSON serializer for pandas Timestamp
        def default(o):
            if isinstance(o, (pd.Timestamp, pd.Timestamp)):
                return o.isoformat()
            raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, 'r+') as f:
                    data = json.load(f)
                    data.update(log_entry)
                    f.seek(0)
                    json.dump(data, f, indent=4, default=default)
            else:
                with open(self.log_path, 'w') as f:
                    json.dump(log_entry, f, indent=4, default=default)
            print(f"Successfully logged {len(signals)} signals to {self.log_path}")
        except Exception as e:
            print(f"Error logging signals: {e}")

    def _format_report(self, ticker: str, signals: List[Dict[str, Any]]) -> str:
        """
        Formats the textual part of the report based on signals.
        """
        if not signals:
            return f"*{ticker} Report*\n\nNo confident signals to publish today."

        report_lines = [f"*{ticker} Trading Signals*"]

        # Sort signals by horizon for cleaner reporting
        signals.sort(key=lambda x: x['horizon_days'])

        for signal in signals:
            report_lines.append("---")
            report_lines.append(f"*Direction:* {signal['direction']} ({signal['horizon_days']}-day horizon)")
            report_lines.append(f"*Expected Return:* `{signal['expected_return']:.2%}`")
            report_lines.append(f"*Confidence:* `{signal['confidence_sigma']:.2f} σ`")
            report_lines.append(f"*Suggested Weight:* `{signal['weight']:.2%}`")

        return "\n".join(report_lines)

    async def send_report(self, ticker: str, signals: List[Dict[str, Any]], plot_path: str):
        """
        Formats and sends the full report if there are signals.
        """
        if not signals:
            print(f"No signals to report for {ticker}. Skipping Telegram message.")
            return

        if not plot_path or not os.path.exists(plot_path):
            print("Plot file not found. Cannot send report with plot.")
            return

        report_text = self._format_report(ticker, signals)

        # Log the signals that are being sent
        self._log_published_signals(signals)

        try:
            with open(plot_path, 'rb') as photo:
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo,
                    caption=report_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            print(f"Successfully sent report for {ticker} to Telegram chat {self.chat_id}")
        except Exception as e:
            print(f"Failed to send report to Telegram. Error: {e}")
