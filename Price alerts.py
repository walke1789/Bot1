import asyncio
import aiohttp
import logging
import schedule
import time
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError, RetryAfter, Forbidden
from config import Config
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

config = Config()
db = Database()

# ── Tracked Assets ───────────────────────────────────
# Format: { display_name: coingecko_id }
CRYPTO_ASSETS = {
    'Bitcoin':   'bitcoin',
    'Ethereum':  'ethereum',
    'Solana':    'solana',
    'BNB':       'binancecoin',
    'XRP':       'ripple',
    'Cardano':   'cardano',
    'Dogecoin':  'dogecoin',
    'Polygon':   'matic-network',
}

# Format: { display_name: ticker_symbol } — via Yahoo Finance
STOCK_ASSETS = {
    'Apple':     'AAPL',
    'Microsoft': 'MSFT',
    'NVIDIA':    'NVDA',
    'Tesla':     'TSLA',
    'Google':    'GOOGL',
    'Amazon':    'AMZN',
    'Meta':      'META',
    'Nikkei':    '^N225',   # Japan
    'Sensex':    '^BSESN',  # India
    'S&P 500':   '^GSPC',
}

# Format: base currency → list of quote currencies — via open.er-api.com (free, no key)
FOREX_BASE = 'USD'
FOREX_PAIRS = ['EUR', 'GBP', 'JPY', 'INR', 'AUD', 'CAD', 'CHF', 'SGD']

# ── Alert Thresholds ─────────────────────────────────
# Send a SPIKE alert if price changes more than this % since last check
SPIKE_THRESHOLD_PCT = 3.0   # 3% move triggers an alert

# ── Price memory (previous prices for spike detection) ──
_prev_prices: dict = {}


class PriceAlerts:
    def __init__(self):
        self.bot = Bot(token=config.TELEGRAM_TOKEN)
        self.session: aiohttp.ClientSession = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _get(self, url: str, params: dict = None) -> dict | None:
        try:
            session = await self._get_session()
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"HTTP {resp.status} from {url}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout: {url}")
        except Exception as e:
            logger.error(f"GET failed ({url}): {e}")
        return None

    async def fetch_crypto_prices(self) -> dict:
        ids = ','.join(CRYPTO_ASSETS.values())
        data = await self._get(
            'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': ids, 'vs_currencies': 'usd', 'include_24hr_change': 'true'}
        )
        if not data:
            return {}

        result = {}
        for name, cg_id in CRYPTO_ASSETS.items():
            if cg_id in data:
                result[name] = {
                    'price': data[cg_id].get('usd', 0),
                    'change_24h': data[cg_id].get('usd_24h_change', 0),
                    'symbol': name,
                }
        return result

    async def fetch_forex_rates(self) -> dict:
        data = await self._get(f'https://open.er-api.com/v6/latest/{FOREX_BASE}')
        if not data or data.get('result') != 'success':
            return {}

        rates = data.get('rates', {})
        result = {}
        for pair in FOREX_PAIRS:
            if pair in rates:
                result[f'{FOREX_BASE}/{pair}'] = {
                    'price': round(rates[pair], 4),
                    'change_24h': None,
                    'symbol': f'{FOREX_BASE}/{pair}',
                }
        return result

    async def fetch_stock_prices(self) -> dict:
        result = {}
        for name, ticker in STOCK_ASSETS.items():
            try:
                data = await self._get(
                    f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}',
                    params={'interval': '1d', 'range': '2d'}
                )
                if not data:
                    continue
                meta = data.get('chart', {}).get('result', [{}])[0].get('meta', {})
                price = meta.get('regularMarketPrice')
                prev_close = meta.get('previousClose') or meta.get('chartPreviousClose')

                if price:
                    change = ((price - prev_close) / prev_close * 100) if prev_close else None
                    result[name] = {
                        'price': round(price, 2),
                        'change_24h': round(change, 2) if change else None,
                        'symbol': ticker,
                        'currency': meta.get('currency', 'USD'),
                    }
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Stock fetch failed ({ticker}): {e}")
        return result

    def run(self):
        logger.info("💹 PriceAlerts started!")


if __name__ == '__main__':
    alerts = PriceAlerts()
    alerts.run()
