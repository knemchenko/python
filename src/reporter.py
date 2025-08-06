import json
import os
import asyncio
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode
from typing import List, Dict, Any
from src import config

def format_signals_to_table(signals: List[Dict[str, Any]]) -> (str, bool):
    """
    Formats signals into a concise Markdown V2 table.
    Returns the formatted table string and a boolean indicating if there were any signals.
    """
    # Filter signals based on the criteria
    filtered_signals = [
        s for s in signals
        if abs(s['expected_return']) >= 0.005 or abs(s['confidence_sigma']) >= 0.5
    ]

    if not filtered_signals:
        return "", False

    # --- Format Table ---
    # Using a non-special character for the separator
    separator = '—' * 23
    table_lines = [
        "`H   DIR   Δ%    σ   W%`",
        f"`{separator}`"
    ]

    filtered_signals.sort(key=lambda x: x['horizon_days'])

    for s in filtered_signals:
        h = f"{s['horizon_days']}d".ljust(4)
        direction = "🟩" if s['direction'] == 'Long' else "🟥"

        # No need to escape characters inside a code block
        ret = f"{s['expected_return'] * 100:+.2f}".rjust(6)
        sigma = f"{s['confidence_sigma']:.1f}".rjust(4)
        weight = f"{s['weight'] * 100:.2f}".rjust(5) if s['weight'] >= 0.0001 else "-".rjust(5)

        table_lines.append(f"`{h}{direction}  {ret} {sigma} {weight}`")

    full_message = "\n".join(table_lines)

    return full_message, True


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

    async def send_report(self, ticker: str, signals: List[Dict[str, Any]], plot_path: str):
        """
        Formats and sends the full report if there are any valid signals.
        """
        report_text, has_signals = format_signals_to_table(signals)

        if not has_signals:
            print(f"No signals to report for {ticker} after filtering. Skipping Telegram message.")
            return

        # Log the original signals that are being sent (before filtering)
        if signals:
             self._log_published_signals(signals)

        try:
            # Use a different parse mode if the message is just the table
            parse_mode = ParseMode.MARKDOWN_V2 if "TL;DR" in report_text else ParseMode.HTML

            with open(plot_path, 'rb') as photo:
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo,
                    caption=f"<b>{ticker}</b>\n<pre>{report_text}</pre>",
                    parse_mode=ParseMode.HTML
                )
            print(f"Successfully sent report for {ticker} to Telegram chat {self.chat_id}")
        except Exception as e:
            print(f"Failed to send report to Telegram. Error: {e}")
