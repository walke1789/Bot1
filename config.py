import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8924733120:AAHiWNV8eflhQ4fSQQd7sCoykHs5dsJkQPY')
    CHANNEL_ID = os.getenv('CHANNEL_ID', '@cryptoctocknews')
    ADMIN_ID = int(os.getenv('ADMIN_ID', 1369974797))
    
    if not TELEGRAM_TOKEN:
        raise ValueError("❌ TELEGRAM_TOKEN missing in .env")
