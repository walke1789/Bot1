cat > ~/Bot1/main.py << 'EOF'
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.request import HTTPXRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('TELEGRAM_TOKEN', '8924733120:AAHiWNV8eflhQ4fSQQd7sCoykHs5dsJkQPY')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@cryptoctocknews')
MARKETS = ['crypto', 'forex', 'stocks', 'japan', 'global', 'company', 'asia', 'events']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(m.title(), callback_data=m)] for m in MARKETS]
    keyboard.append([InlineKeyboardButton("📢 CHANNEL", url=f"https://t.me/{CHANNEL_ID[1:]}")])
    await update.message.reply_text(
        "🚀 *Trading News Bot*\n\nChoose a market below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 Fetching latest global news...")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    market = next((m for m in MARKETS if m in text), None)
    if market:
        await update.message.reply_text(f"🔄 Fetching {market} news...")
    else:
        await update.message.reply_text("❌ Try: crypto, forex, asia, stocks, /latest")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"🔄 Loading {query.data} news...")

if __name__ == '__main__':
    logger.info("🤖 Starting bot...")
    request = HTTPXRequest(proxy="socks5://proxy.server:3128")
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .get_updates_request(HTTPXRequest(proxy="http://proxy.pythonanywhere.com:3128"))
        .request(HTTPXRequest(proxy="http://proxy.pythonanywhere.com:3128"))
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("latest", latest))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Bot is running!")
    app.run_polling(drop_pending_updates=True)
EOF
