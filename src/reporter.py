import json
import os
import asyncio
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode
from typing import List, Dict, Any
from src import config

def format_signals(ticker: str, signals: List[Dict[str, Any]]) -> str:
    """
    Formats signals into a concise Markdown V2 message for Telegram.
    """
    # Filter signals based on the criteria
    filtered_signals = [
        s for s in signals
        if abs(s['expected_return']) >= 0.005 or abs(s['confidence_sigma']) >= 0.5
    ]

    # --- 1. Determine TL;DR Bias ---
    if not filtered_signals:
        tldr = "⚪️ No clear edge"
    else:
        long_strength = sum(s['weight'] for s in filtered_signals if s['direction'] == 'Long')
        short_strength = sum(s['weight'] for s in filtered_signals if s['direction'] == 'Short')
        if long_strength > short_strength * 1.1:
            tldr = "🟩 Long bias"
        elif short_strength > long_strength * 1.1:
            tldr = "🟥 Short bias"
        else:
            tldr = "⚪️ No clear edge"

    # --- 2. Format Header ---
    # Telegram MarkdownV2 requires escaping special characters
    ticker_escaped = ticker.replace('.', '\\.')
    date_str = pd.Timestamp.now().strftime("%d %b %Y")
    header = f"📈 *{ticker_escaped} — Signals ({date_str})*\n\nTL;DR → {tldr}"

    if not filtered_signals:
        return header

    # --- 3. Format Table ---
    table_lines = [
        "H   DIR   Δ%    σ   W%",
        "-----------------------"
    ]

    filtered_signals.sort(key=lambda x: x['horizon_days'])

    for s in filtered_signals:
        h = f"{s['horizon_days']}d".ljust(4)
        direction = "🟩" if s['direction'] == 'Long' else "🟥"
        ret_str = f"{s['expected_return']:+.2%}".replace('%', '\\%').replace('-', '\\-').replace('+', '\\+')
        ret = f"{ret_str}".rjust(8)
        sigma = f"{s['confidence_sigma']:.1f}".rjust(4)
        weight_str = f"{s['weight']:.2%}".replace('%', '\\%') if s['weight'] >= 0.0001 else "\\-"
        weight = weight_str.rjust(7)

        table_lines.append(f"{h}{direction}  {ret} {sigma} {weight}")

    table_lines.append("-----------------------")
    table_lines.append("DIR: 🟩 (Long) 🟥 (Short)")

    # Combine all parts
    full_message = header + "\n\n```\n" + "\n".join(table_lines) + "\n```"

    return full_message


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

    async def send_report(self, ticker: str, signals: List[Dict[str, Any]], plot_path: str):
        """
        Formats and sends the full report. It sends a message even if there are no signals.
        """
        report_text = format_signals(ticker, signals)

        # Log the signals that are being sent
        if signals:
             self._log_published_signals(signals)

        # Don't send a plot if there are no signals to report
        if not signals or not plot_path or not os.path.exists(plot_path):
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=report_text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                print(f"Successfully sent text-only report for {ticker} to Telegram chat {self.chat_id}")
            except Exception as e:
                print(f"Failed to send text-only report to Telegram. Error: {e}")
            return

        try:
            with open(plot_path, 'rb') as photo:
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo,
                    caption=report_text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            print(f"Successfully sent report for {ticker} to Telegram chat {self.chat_id}")
        except Exception as e:
            print(f"Failed to send report to Telegram. Error: {e}")
