# [IMPORT] requests - for making HTTP calls to the Telegram API
import requests

# [IMPORT] Load API keys from .env
from dotenv import load_dotenv

# [IMPORT] os to read environment variables
import os

# [FUNCTION CALL] Load keys from .env
load_dotenv()

# [VARIABLE] Your bot token and chat ID from .env
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID')

# [VARIABLE - string] Telegram API URL
# Every message goes to this endpoint
URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# [VARIABLE - dict] Message payload
payload = {
    'chat_id': CHAT_ID,
    'text': '✅ Greg_ETH_Alerts_Bot is connected and working!',
    'parse_mode': 'HTML'
}

# [API CALL] Send the message
response = requests.post(URL, data=payload)

# [CONDITIONAL] Check if it worked
if response.status_code == 200:
    print("✅ Message sent successfully! Check your Telegram.")
else:
    print(f"❌ Failed: {response.status_code} - {response.text}")