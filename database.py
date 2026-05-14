import sqlite3
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = 'bot.db'

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_conn(self):
        """Context manager for safe connection handling."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Allows dict-like row access
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_db(self):
        """Initialize all tables."""
        with self.get_conn() as conn:
            # User requests / activity log
            conn.execute('''
                CREATE TABLE IF NOT EXISTS requests (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id   INTEGER NOT NULL,
                    market    TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            ''')

            # Registered users
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id    INTEGER PRIMARY KEY,
                    username   TEXT,
                    first_name TEXT,
                    joined_at  TEXT NOT NULL,
                    is_banned  INTEGER DEFAULT 0
                )
            ''')

            # Posted news cache (avoid duplicate channel posts)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS posted_news (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    url        TEXT UNIQUE NOT NULL,
                    title      TEXT,
                    market     TEXT,
                    posted_at  TEXT NOT NULL
                )
            ''')

            # User market subscriptions
            conn.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    market  TEXT NOT NULL,
                    UNIQUE(user_id, market)
                )
            ''')

            # Bot stats
            conn.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    event      TEXT NOT NULL,
                    value      INTEGER DEFAULT 1,
                    recorded_at TEXT NOT NULL
                )
            ''')

        logger.info("✅ Database initialized.")

    # ──────────────────────────────────────────────
    # REQUESTS
    # ──────────────────────────────────────────────

    def save_user_request(self, user_id: int, market: str):
        """Log a user's market request."""
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO requests (user_id, market, timestamp) VALUES (?, ?, ?)",
                (user_id, market, datetime.now().isoformat())
            )

    def get_user_requests(self, user_id: int, limit: int = 10) -> list:
        """Fetch recent requests by a user."""
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT market, timestamp FROM requests WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_top_markets(self, limit: int = 5) -> list:
        """Get most requested markets."""
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT market, COUNT(*) as count FROM requests GROUP BY market ORDER BY count DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────
    # USERS
    # ──────────────────────────────────────────────

    def save_user(self, user_id: int, username: str = None, first_name: str = None):
        """Register or update a user."""
        with self.get_conn() as conn:
            conn.execute('''
                INSERT INTO users (user_id, username, first_name, joined_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name
            ''', (user_id, username, first_name, datetime.now().isoformat()))

    def get_all_users(self, exclude_banned: bool = True) -> list:
        """Return all user IDs (for broadcasts)."""
        with self.get_conn() as conn:
            query = "SELECT user_id FROM users"
            if exclude_banned:
                query += " WHERE is_banned = 0"
            rows = conn.execute(query).fetchall()
        return [r['user_id'] for r in rows]

    def ban_user(self, user_id: int):
        with self.get_conn() as conn:
            conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))

    def unban_user(self, user_id: int):
        with self.get_conn() as conn:
            conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))

    def get_user_count(self) -> int:
        with self.get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM users WHERE is_banned = 0").fetchone()
        return row['cnt']

    # ──────────────────────────────────────────────
    # POSTED NEWS CACHE
    # ──────────────────────────────────────────────

    def is_news_posted(self, url: str) -> bool:
        """Check if a news URL was already posted to the channel."""
        with self.get_conn() as conn:
            row = conn.execute("SELECT id FROM posted_news WHERE url = ?", (url,)).fetchone()
        return row is not None

    def mark_news_posted(self, url: str, title: str, market: str):
        """Mark a news item as posted."""
        with self.get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO posted_news (url, title, market, posted_at) VALUES (?, ?, ?, ?)",
                (url, title, market, datetime.now().isoformat())
            )

    def clean_old_news(self, days: int = 7):
        """Remove news older than N days from cache."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self.get_conn() as conn:
            conn.execute("DELETE FROM posted_news WHERE posted_at < ?", (cutoff,))
        logger.info(f"🧹 Cleaned news older than {days} days.")

    # ──────────────────────────────────────────────
    # SUBSCRIPTIONS
    # ──────────────────────────────────────────────

    def subscribe(self, user_id: int, market: str):
        """Subscribe a user to a market."""
        with self.get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO subscriptions (user_id, market) VALUES (?, ?)",
                (user_id, market)
            )

    def unsubscribe(self, user_id: int, market: str):
        """Unsubscribe a user from a market."""
        with self.get_conn() as conn:
            conn.execute(
                "DELETE FROM subscriptions WHERE user_id = ? AND market = ?",
                (user_id, market)
            )

    def get_subscribers(self, market: str) -> list:
        """Get all users subscribed to a market."""
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT user_id FROM subscriptions WHERE market = ?", (market,)
            ).fetchall()
        return [r['user_id'] for r in rows]

    def get_user_subscriptions(self, user_id: int) -> list:
        """Get all markets a user is subscribed to."""
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT market FROM subscriptions WHERE user_id = ?", (user_id,)
            ).fetchall()
        return [r['market'] for r in rows]

    # ──────────────────────────────────────────────
    # STATS
    # ──────────────────────────────────────────────

    def log_stat(self, event: str, value: int = 1):
        """Log a bot event (e.g. 'news_posted', 'user_joined')."""
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO stats (event, value, recorded_at) VALUES (?, ?, ?)",
                (event, value, datetime.now().isoformat())
            )

    def get_stats_summary(self) -> dict:
        """Return a summary of key bot stats."""
        with self.get_conn() as conn:
            total_requests = conn.execute("SELECT COUNT(*) as cnt FROM requests").fetchone()['cnt']
            total_users = conn.execute("SELECT COUNT(*) as cnt FROM users WHERE is_banned = 0").fetchone()['cnt']
            total_news = conn.execute("SELECT COUNT(*) as cnt FROM posted_news").fetchone()['cnt']
            top_market = conn.execute(
                "SELECT market FROM requests GROUP BY market ORDER BY COUNT(*) DESC LIMIT 1"
            ).fetchone()

        return {
            'total_requests': total_requests,
            'total_users': total_users,
            'total_news_posted': total_news,
            'top_market': top_market['market'] if top_market else 'N/A'
        }
