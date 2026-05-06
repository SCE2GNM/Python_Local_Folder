"""
Weekly portfolio rebalance script.
Called by cron every Monday 01:00 UTC.
Recalculates reserved_capital per strategy based on current total portfolio value.
Sends Telegram summary with updated allocations.
"""

import sys
import os
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'core', 'execution'))

load_dotenv(os.path.join(BASE_DIR, '.env'))

from binance.client import Client
from portfolio_manager import rebalance_portfolio, get_portfolio_summary


def send_telegram(message):
    token   = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={'chat_id': chat_id, 'text': message},
                timeout=10
            )
        except Exception as e:
            print(f"Telegram send failed: {e}")


if __name__ == '__main__':
    api_key    = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_SECRET_KEY')

    if not api_key or not api_secret:
        send_telegram("🚨 Weekly rebalance FAILED: Binance API credentials not found in environment")
        sys.exit(1)

    client = Client(api_key, api_secret)

    try:
        total   = rebalance_portfolio(client)
        summary = get_portfolio_summary(client)
        msg     = f"📊 Weekly portfolio rebalance\nTotal: ${total:,.2f}\n{summary}"
        send_telegram(msg)
        print(msg)
    except Exception as e:
        send_telegram(f"🚨 Weekly rebalance FAILED: {e}")
        raise
