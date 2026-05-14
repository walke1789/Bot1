import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from news_scraper import scraper
from database import Database
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradingNewsBot:
    def __init__(self):
        self.config = Config()
        self.db = Database()
        self.markets = ['crypto', 'forex', 'stocks', 'japan', 'global', 'company', 'asia', 'events']

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [[InlineKeyboardButton(m.title(), callback_data=m)] for m in self.markets]
        keyboard.append([InlineKeyboardButton("📢 CHANNEL", url=f"https://t.me/{self.config.CHANNEL_ID[1:]}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🚀 **Trading News Bot**\n\n"
            "Choose market or type: `crypto`, `asia`, `companies`...\n\n"
            "**New:** Company news, Asian markets, Events!",
            reply_markup=reply_markup, parse_mode='Markdown'
        )

    async def handle_market(self, update: Update, context: ContextTypes.DEFAULT_TYPE, market: str):
        try:
            user_id = update.effective_user.id
            self.db.save_user_request(user_id, market)
            news_items = await scraper.get_market_news(market, 3)
            if not news_items:
                await update.message.reply_text(f"❌ No {market} news. Try /latest")
                return
            for i, news in enumerate(news_items, 1):
                keyboard = [
                    [InlineKeyboardButton("🔗 SOURCE", url=news['url'])],
                    [InlineKeyboardButton("📢 CHANNEL", url=f"https://t.me/{self.config.CHANNEL_ID[1:]}")]
                ]
                msg = f"{i}. **{news['title']}**\n\n{news['description']}\n\n🕒 {news['published']} | {news['source']}"
                await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown', disable_web_page_preview=True)
                await self.post_to_channel(context, news, market)
        except Exception as e:
            logger.error(f"Market error {market}: {e}")
            await update.message.reply_text("⚠️ Try again or use /latest")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.lower()
        market = next((m for m in self.markets if m in text), None)
        if market:
            await self.handle_market(update, context, market)
        else:
            await update.message.reply_text("❌ Try: crypto, forex, asia, companies, events, /latest")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        market = query.data
        await query.edit_message_text(f"🔄 Loading {market} news...")
        await self.handle_market(query, context, market)

    async def latest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_market(update, context, 'global')

    async def post_to_channel(self, context, news, market):
        try:
            emoji = {'crypto': '🪙', 'asia': '🌏', 'company': '🏢'}.get(market, '📢')
            msg = f"{emoji} **{market.upper()}**\n\n**{news['title']}**\n\n{news['description']}\n\n🕒 {news['published']}\n🔗 {news['url']}"
            await context.bot.send_message(self.config.CHANNEL_ID, msg, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Channel post failed: {e}")


def main():
    bot = TradingNewsBot()
    telegram_app = Application.builder().token(bot.config.TELEGRAM_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", bot.start))
    telegram_app.add_handler(CommandHandler("latest", bot.latest))
    telegram_app.add_handler(CallbackQueryHandler(bot.button_callback))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    logger.info("🤖 Bot started!")
    telegram_app.run_polling()

if __name__ == '__main__':
    main()
