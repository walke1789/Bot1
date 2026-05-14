import feedparser
import hashlib
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Cache TTL (minutes) ──────────────────────────────
CACHE_TTL_MINUTES = 15


class RSSNewsScraper:
    def __init__(self):
        self.rss_feeds = {
            'crypto': [
                'https://www.coindesk.com/arc/outboundfeeds/rss/',
                'https://cointelegraph.com/rss',
                'https://decrypt.co/feed',                          # ✨ Added
                'https://bitcoinmagazine.com/.rss/full/',           # ✨ Added
            ],
            'forex': [
                'https://www.moneycontrol.com/rss/marketreports.xml',
                'https://feeds.reuters.com/reuters/businessNews',
                'https://www.fxstreet.com/rss/news',                # ✨ Added
            ],
            'stocks': [
                'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
                'https://finance.yahoo.com/news/rssindex',
                'https://feeds.marketwatch.com/marketwatch/topstories/', # ✨ Added
            ],
            'company': [
                'https://www.moneycontrol.com/news/business/companies/rss',
                'https://feeds.reuters.com/reuters/companynews',
            ],
            'asia': [
                'https://economictimes.indiatimes.com/markets/asianmarkets/rssfeeds/2146842.cms',
                'https://feeds.reuters.com/reuters/asiaNews',
                'https://www.scmp.com/rss/91/feed',                 # ✨ Added: South China Morning Post
            ],
            'events': [
                'https://www.investing.com/rss/news_71.rss',
                'https://feeds.reuters.com/reuters/companyNews',    # ✨ Added
            ],
            'japan': [
                'https://feeds.reuters.com/reuters/businessNews',
                'https://www3.nhk.or.jp/rss/news/cat6.xml',        # ✨ Added: NHK Japan business
            ],
            'global': [
                'https://feeds.reuters.com/reuters/businessNews',
                'https://finance.yahoo.com/news/rssindex',
                'https://feeds.bbci.co.uk/news/business/rss.xml',  # ✨ Added: BBC Business
                'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',  # ✨ Added
            ],
            'india': [                                              # ✨ New market
                'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
                'https://www.moneycontrol.com/rss/marketreports.xml',
                'https://feeds.feedburner.com/ndtvprofit-latest',
            ],
            'commodities': [                                        # ✨ New market
                'https://feeds.reuters.com/reuters/commoditiesNews',
                'https://www.investing.com/rss/news_11.rss',
            ],
        }

        # In-memory cache: { cache_key: (timestamp, articles) }
        self._cache: dict = {}

    # ──────────────────────────────────────────────
    # CACHE HELPERS
    # ──────────────────────────────────────────────

    def _cache_key(self, market: str, limit: int) -> str:
        return f"{market}:{limit}"

    def _get_cached(self, key: str) -> Optional[list]:
        if key in self._cache:
            ts, data = self._cache[key]
            if datetime.now() - ts < timedelta(minutes=CACHE_TTL_MINUTES):
                logger.info(f"📦 Cache hit: {key}")
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: list):
        self._cache[key] = (datetime.now(), data)

    def clear_cache(self):
        self._cache.clear()
        logger.info("🧹 News cache cleared.")

    # ──────────────────────────────────────────────
    # PARSING
    # ──────────────────────────────────────────────

    def _clean_html(self, text: str) -> str:
        """Strip basic HTML tags from description."""
        import re
        return re.sub(r'<[^>]+>', '', text or '').strip()

    def _format_date(self, entry) -> str:
        """Return a human-friendly publish date."""
        pub = getattr(entry, 'published_parsed', None)
        if pub:
            try:
                dt = datetime(*pub[:6])
                diff = datetime.now() - dt
                if diff.seconds < 3600:
                    return f"{diff.seconds // 60}m ago"
                elif diff.days == 0:
                    return f"{diff.seconds // 3600}h ago"
                else:
                    return dt.strftime("%d %b %Y")
            except Exception:
                pass
        return getattr(entry, 'published', 'Recently')

    def parse_feed(self, url: str, cutoff_hours: int = 48) -> list:
        """Parse a single RSS feed URL and return articles."""
        try:
            feed = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})

            if feed.bozo and not feed.entries:
                logger.warning(f"⚠️ Feed error ({url}): {feed.bozo_exception}")
                return []

            articles = []
            cutoff = datetime.now() - timedelta(hours=cutoff_hours)
            source_name = getattr(feed.feed, 'title', url.split('/')[2])

            for entry in feed.entries[:8]:  # ✨ Increased from 5 to 8
                pub_parsed = getattr(entry, 'published_parsed', None)

                # Skip if too old (only if date is available)
                if pub_parsed:
                    pub_dt = datetime(*pub_parsed[:6])
                    if pub_dt < cutoff:
                        continue

                # ✨ Improved description: clean HTML, fallback to summary/content
                raw_desc = (
                    getattr(entry, 'summary', None) or
                    (entry.content[0].value if getattr(entry, 'content', None) else None) or
                    ''
                )
                description = self._clean_html(raw_desc)
                if len(description) > 350:
                    description = description[:347] + '...'

                articles.append({
                    'id':          hashlib.md5(entry.link.encode()).hexdigest(),
                    'title':       self._clean_html(entry.title),
                    'description': description,
                    'url':         entry.link,
                    'published':   self._format_date(entry),   # ✨ Human-readable date
                    'source':      source_name,
                })

            return articles

        except Exception as e:
            logger.error(f"❌ parse_feed failed ({url}): {e}")
            return []

    # ──────────────────────────────────────────────
    # ASYNC FETCH (parallel feeds) ✨ New
    # ──────────────────────────────────────────────

    async def _fetch_feed_async(self, url: str) -> list:
        """Run blocking feedparser in a thread so it doesn't block the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.parse_feed, url)

    async def get_market_news(self, market: str, limit: int = 3) -> list:
        """Fetch news for a market. Uses cache + parallel async fetching."""
        market = market.lower()
        cache_key = self._cache_key(market, limit)

        # Return cached result if fresh
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        feeds = self.rss_feeds.get(market, self.rss_feeds['global'])

        # ✨ Fetch all feeds in parallel
        tasks = [self._fetch_feed_async(url) for url in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        seen_ids = set()

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Feed task error: {result}")
                continue
            for article in result:
                if article['id'] not in seen_ids:     # ✨ Deduplicate by hash
                    seen_ids.add(article['id'])
                    all_articles.append(article)

        # Sort by published (best-effort; strings with "ago" sort well enough)
        all_articles.sort(key=lambda x: x['published'], reverse=False)

        final = all_articles[:limit]
        self._set_cache(cache_key, final)

        logger.info(f"📰 {market.upper()}: fetched {len(final)} articles (from {len(all_articles)} total)")
        return final

    # ──────────────────────────────────────────────
    # MULTI-MARKET FETCH ✨ New
    # ──────────────────────────────────────────────

    async def get_multi_market_news(self, markets: list, limit_per_market: int = 2) -> dict:
        """Fetch news for multiple markets at once."""
        tasks = {m: self.get_market_news(m, limit_per_market) for m in markets}
        results = {}
        for market, coro in tasks.items():
            try:
                results[market] = await coro
            except Exception as e:
                logger.error(f"Multi-market fetch failed for {market}: {e}")
                results[market] = []
        return results

    # ──────────────────────────────────────────────
    # SEARCH ✨ New
    # ──────────────────────────────────────────────

    async def search_news(self, keyword: str, limit: int = 5) -> list:
        """Search across all markets for a keyword."""
        keyword = keyword.lower()
        all_results = []
        seen_ids = set()

        for market in self.rss_feeds:
            articles = await self.get_market_news(market, limit=5)
            for a in articles:
                if (
                    keyword in a['title'].lower() or
                    keyword in a['description'].lower()
                ) and a['id'] not in seen_ids:
                    seen_ids.add(a['id'])
                    all_results.append({**a, 'market': market})

        return all_results[:limit]

    # ──────────────────────────────────────────────
    # AVAILABLE MARKETS
    # ──────────────────────────────────────────────

    def get_available_markets(self) -> list:
        return list(self.rss_feeds.keys())


# Singleton instance used across the project
scraper = RSSNewsScraper()
