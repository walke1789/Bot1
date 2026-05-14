import schedule
import time
import asyncio
import logging
import random
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError, RetryAfter, Forbidden
from config import Config
from news_scraper import scraper
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

config = Config()
db = Database()

# ── Market post schedule config ──────────────────────
# (market, interval_hours, emoji, label)
MARKET_SCHEDULE = [
    ('crypto',      1,   '🪙', 'CRYPTO'),
    ('forex',       2,   '💱', 'FOREX'),
    ('stocks',      2,   '📈', 'STOCKS'),
    ('global',      3,   '🌍', 'GLOBAL'),
    ('asia',        3,   '🌏', 'ASIA'),
    ('japan',       4,   '🗾', 'JAPAN'),
    ('company',     3,   '🏢', 'COMPANY'),
    ('commodities', 4,   '🛢️', 'COMMODITIES'),   # ✨ New
    ('india',       2,   '🇮🇳', 'INDIA'),         # ✨ New
    ('events',      6,   '📅', 'EVENTS'),
]

# ── Retry config ─────────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


class AutoPoster:
    def __init__(self):
        self.bot = Bot(token=config.TELEGRAM_TOKEN)
        self.posted_count = 0
        self.failed_count = 0
        self.start_time = datetime.now()

    # ──────────────────────────────────────────────
    # MESSAGE FORMATTING  ✨ Improved
    # ──────────────────────────────────────────────

    def _format_message(self, news: dict, emoji: str, label: str) -> str:
        """Build a rich Telegram channel message."""
        title = news.get('title', 'No title')
        description = news.get('description', '')
        published = news.get('published', '')
        source = news.get('source', '')
        url = news.get('url', '')

        lines = [
            f"{emoji} **{label} NEWS**",
            "",
            f"**{title}**",
        ]
        if description:
            lines += ["", description]
        if published or source:
            meta = " | ".join(filter(None, [published, source]))
            lines += ["", f"🕒 {meta}"]
        if url:
            lines += [f"🔗 {url}"]
        lines += ["", f"📢 {config.CHANNEL_ID}"]

        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # SEND WITH RETRY  ✨ New
    # ──────────────────────────────────────────────

    async def _send_with_retry(self, message: str) -> bool:
        """Send a message to the channel with retry on rate-limit."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await self.bot.send_message(
                    config.CHANNEL_ID,
                    message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                return True

            except RetryAfter as e:
                wait = e.retry_after + 2
                logger.warning(f"⏳ Rate limited. Waiting {wait}s (attempt {attempt}/{MAX_RETRIES})")
                await asyncio.sleep(wait)

            except Forbidden:
                logger.error("🚫 Bot is not allowed to post in the channel. Check bot permissions.")
                return False

            except TelegramError as e:
                logger.error(f"❌ Telegram error (attempt {attempt}): {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)

        return False

    # ──────────────────────────────────────────────
    # POST A SINGLE MARKET
    # ──────────────────────────────────────────────

    async def post_market(self, market: str, emoji: str, label: str, limit: int = 1):
        """Fetch and post news for a given market."""
        logger.info(f"📤 Posting {label} news...")
        try:
            news_items = await scraper.get_market_news(market, limit)

            if not news_items:
                logger.warning(f"⚠️ No {market} news available.")
                return

            posted = 0
            for news in news_items:
                # ✨ Skip already-posted articles
                if db.is_news_posted(news['url']):
                    logger.info(f"⏭️ Skipping already posted: {news['title'][:50]}")
                    continue

                message = self._format_message(news, emoji, label)
                success = await self._send_with_retry(message)

                if success:
                    db.mark_news_posted(news['url'], news['title'], market)
                    db.log_stat('news_posted')
                    self.posted_count += 1
                    posted += 1
                    logger.info(f"✅ Posted [{label}]: {news['title'][:60]}")

                    # ✨ Also notify subscribed users
                    await self._notify_subscribers(market, news, emoji, label)

                    # Small delay between multiple posts
                    if limit > 1:
                        await asyncio.sleep(2)
                else:
                    self.failed_count += 1

            if posted == 0:
                logger.info(f"ℹ️ All {label} articles already posted.")

        except Exception as e:
            logger.error(f"❌ post_market failed [{market}]: {e}")
            self.failed_count += 1

    # ──────────────────────────────────────────────
    # NOTIFY SUBSCRIBERS  ✨ New
    # ──────────────────────────────────────────────

    async def _notify_subscribers(self, market: str, news: dict, emoji: str, label: str):
        """Send news to users subscribed to this market."""
        subscribers = db.get_subscribers(market)
        if not subscribers:
            return

        message = self._format_message(news, emoji, label)
        sent = 0
        for user_id in subscribers:
            try:
                await self.bot.send_message(
                    user_id, message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                sent += 1
                await asyncio.sleep(0.05)  # Telegram rate limit safety
            except Forbidden:
                logger.warning(f"⚠️ User {user_id} blocked the bot — skipping.")
            except TelegramError as e:
                logger.error(f"Subscriber notify failed ({user_id}): {e}")

        if sent:
            logger.info(f"📬 Notified {sent} subscribers for [{label}]")

    # ──────────────────────────────────────────────
    # DIGEST POST  ✨ New
    # ──────────────────────────────────────────────

    async def post_daily_digest(self):
        """Post a morning digest covering all markets."""
        logger.info("📋 Posting daily digest...")
        try:
            markets_data = await scraper.get_multi_market_news(
                ['crypto', 'stocks', 'forex', 'global'], limit_per_market=1
            )
            lines = ["🗞️ **DAILY MARKET DIGEST**", f"📅 {datetime.now().strftime('%A, %d %B %Y')}", ""]

            emojis = {'crypto': '🪙', 'stocks': '📈', 'forex': '💱', 'global': '🌍'}
            for market, articles in markets_data.items():
                if articles:
                    a = articles[0]
                    lines.append(f"{emojis.get(market, '📌')} **{market.upper()}**")
                    lines.append(f"{a['title']}")
                    lines.append(f"🔗 {a['url']}")
                    lines.append("")

            lines.append(f"📢 Follow {config.CHANNEL_ID} for live updates!")
            message = "\n".join(lines)

            success = await self._send_with_retry(message)
            if success:
                db.log_stat('digest_posted')
                logger.info("✅ Daily digest posted.")
        except Exception as e:
            logger.error(f"❌ Daily digest failed: {e}")

    # ──────────────────────────────────────────────
    # STATS REPORT  ✨ New
    # ──────────────────────────────────────────────

    async def post_stats_to_admin(self):
        """Send a stats summary to the admin."""
        if not config.ADMIN_ID:
            return
        try:
            summary = db.get_stats_summary()
            uptime = datetime.now() - self.start_time
            hours, rem = divmod(int(uptime.total_seconds()), 3600)
            minutes = rem // 60

            msg = (
                "📊 **Auto-Poster Stats**\n\n"
                f"⏱ Uptime: {hours}h {minutes}m\n"
                f"✅ Posted this session: {self.posted_count}\n"
                f"❌ Failed: {self.failed_count}\n"
                f"👥 Total users: {summary['total_users']}\n"
                f"📰 Total news posted (all time): {summary['total_news_posted']}\n"
                f"🔥 Top market: {summary['top_market']}\n"
            )
            await self.bot.send_message(config.ADMIN_ID, msg, parse_mode='Markdown')
            logger.info("📊 Stats sent to admin.")
        except Exception as e:
            logger.error(f"Stats report failed: {e}")

    # ──────────────────────────────────────────────
    # SCHEDULE SETUP
    # ──────────────────────────────────────────────

    def setup_schedule(self):
        """Register all scheduled jobs."""
        for market, interval, emoji, label in MARKET_SCHEDULE:
            m, e, l = market, emoji, label  # capture loop vars
            schedule.every(interval).hours.do(
                lambda _m=m, _e=e, _l=l: asyncio.run(self.post_market(_m, _e, _l))
            )
            logger.info(f"📅 Scheduled [{label}] every {interval}h")

        # ✨ Daily digest at 8:00 AM
        schedule.every().day.at("08:00").do(
            lambda: asyncio.run(self.post_daily_digest())
        )

        # ✨ Stats report to admin every 12 hours
        schedule.every(12).hours.do(
            lambda: asyncio.run(self.post_stats_to_admin())
        )

        # ✨ Clean old news cache from DB weekly
        schedule.every().week.do(lambda: db.clean_old_news(days=7))

    # ──────────────────────────────────────────────
    # RUN
    # ──────────────────────────────────────────────

    async def run_startup_posts(self):
        """Post one item from each major market on startup."""
        logger.info("🚀 Running startup posts...")
        for market, _, emoji, label in MARKET_SCHEDULE[:4]:
            await self.post_market(market, emoji, label)
            await asyncio.sleep(3)

    def run(self):
        logger.info("🤖 AutoPoster started!")
        self.setup_schedule()

        # Post on startup
        asyncio.run(self.run_startup_posts())

        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == '__main__':
    poster = AutoPoster()
    poster.run()
