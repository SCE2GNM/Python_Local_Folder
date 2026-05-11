"""
Weekly portfolio rebalance script.
Called by cron every Monday 01:00 UTC.
Recalculates reserved_capital per strategy based on current total portfolio value.
Sends Telegram summary with updated allocations.
"""

import sys
import os
import requests
from datetime import datetime, timedelta
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
        result        = rebalance_portfolio(client)
        total         = result['total_val']
        next_rebal    = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

        lines = [
            f"📊 Weekly Portfolio Rebalance — {datetime.now().strftime('%Y-%m-%d')}",
            f"Portfolio value: ${total:,.2f}",
            "",
        ]
        for name, info in result['strategies'].items():
            b, a, p, act = info['before'], info['after'], info['proposed'], info['action']
            if act == 'increased':
                lines.append(f"{name}: ${b:,.0f} → ${a:,.0f} ✅ (portfolio grew)")
            elif act == 'fixed':
                lines.append(f"{name}: ${a:,.0f} 🔒 (fixed allocation — not rebalanced)")
            elif act == 'protected':
                lines.append(f"{name}: ${a:,.0f} — unchanged (pct formula: ${p:,.0f} — protected from reduction)")
            else:
                lines.append(f"{name}: ${b:,.0f} → ${a:,.0f} ({act})")

        lines += ["", f"Next rebalance: Monday {next_rebal} 01:00 UTC"]
        msg = "\n".join(lines)
        send_telegram(msg)
        print(msg)
    except Exception as e:
        send_telegram(f"🚨 Weekly rebalance FAILED: {e}")
        raise
