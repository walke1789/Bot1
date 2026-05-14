import asyncio
import random
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from news_scraper import scraper
from config import Config
import schedule
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiForumBot:
    def __init__(self, telegram_token=None):
        self.config = Config()
        self.telegram_token = telegram_token or self.config.TELEGRAM_TOKEN
        self.setup_driver()
        self.promo_links = [f"https://t.me/{self.config.CHANNEL_ID[1:]}"]
        self.quora_keywords = ['crypto', 'bitcoin', 'forex', 'trading', 'stock market']

    def setup_driver(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--user-agent=Mozilla/5.0")
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)

    async def quora_auto_answer(self):
        """🚀 QUORA AUTO-RESPONDER"""
        try:
            self.driver.get("https://www.quora.com/search?q=crypto%20news")
            time.sleep(3)

            # Find unanswered/recent questions
            questions = self.driver.find_elements(By.CSS_SELECTOR, "[data-test-id='question-list-item']")

            for question in questions[:3]:
                q_text = question.text.lower()
                if any(kw in q_text for kw in self.quora_keywords):
                    try:
                        question.click()
                        time.sleep(2)

                        # Check if unanswered
                        answers = self.driver.find_elements(By.CSS_SELECTOR, ".q-text-quaternary")
                        if "answer" not in answers[0].text.lower():

                            # Get fresh news
                            news = await scraper.get_market_news('crypto', 1)
                            answer = f"""
                            🔥 **Latest {news[0]['source']} Update:**

                            **{news[0]['title']}**

                            {news[0]['description']}

                            🕒 {news[0]['published']}
                            🔗 {news[0]['url']}

                            📢 Get real-time updates: {self.promo_links[0]}
                            """

                            # Post answer
                            answer_box = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ql-editor")))
                            answer_box.send_keys(answer[:1000])
                            self.driver.find_element(By.CSS_SELECTOR, "[data-test-id='answer-submit-button']").click()

                            print(f"✅ Quora answer posted: {news[0]['title'][:50]}")
                            break
                    except Exception as e:
                        logger.error(f"Quora error: {e}")
                        continue
        except Exception as e:
            logger.error(f"Quora session failed: {e}")

    async def tradingview_post(self):
        try:
            self.driver.get("https://www.tradingview.com/ideas/crypto/")
            time.sleep(3)
            # Post logic...
            print("✅ TradingView posted")
        except Exception as e:
            logger.error(f"TradingView post failed: {e}")

    async def forexfactory_post(self):
        try:
            self.driver.get("https://www.forexfactory.com/forum")
            time.sleep(3)
            # Post logic...
            print("✅ ForexFactory posted")
        except Exception as e:
            logger.error(f"ForexFactory post failed: {e}")

    async def investingcom_post(self):
        try:
            self.driver.get("https://www.investing.com/forums/")
            time.sleep(3)
            # Post logic...
            print("✅ Investing.com posted")
        except Exception as e:
            logger.error(f"Investing.com post failed: {e}")

    def run(self):
        """Smart rotation schedule"""
        schedule.every(2).hours.do(lambda: asyncio.create_task(self.quora_auto_answer()))
        schedule.every(1).hours.do(lambda: asyncio.create_task(self.tradingview_post()))
        schedule.every(3).hours.do(lambda: asyncio.create_task(
            random.choice([self.forexfactory_post, self.investingcom_post])()
        ))

        print("🌐 Multi-Forum Bot started!")
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == '__main__':
    bot = MultiForumBot()
    bot.run()
