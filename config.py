"""
=============================================================
  WhatsApp Business Chatbot - Configuration
  Menggunakan WhatsApp Business Cloud API (Meta Official)
=============================================================
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ======================== WhatsApp API Config ========================
WHATSAPP_API_URL = "https://graph.facebook.com/v18.0"
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "my_secret_verify_token")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "YOUR_APP_SECRET")

# ======================== Flask Config ========================
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-this")
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"

# ======================== Database ========================
DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///chatbot.db")

# ======================== Admin ========================
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# ======================== Bot Settings ========================
BOT_NAME = "SmartBot"
BOT_LANGUAGE = "id"  # Indonesian
SESSION_TIMEOUT_MINUTES = 30
MAX_RETRY_ATTEMPTS = 3

# ======================== AI / NLP Settings ========================
ENABLE_AI_RESPONSE = os.getenv("ENABLE_AI_RESPONSE", "False").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ======================== Rate Limiting ========================
RATE_LIMIT_MESSAGES_PER_MINUTE = 20
RATE_LIMIT_MESSAGES_PER_HOUR = 200

# ======================== Logging ========================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "chatbot.log"
