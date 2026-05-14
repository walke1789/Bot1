# 📈 Trading News Telegram Bot

A fully automated Telegram bot that scrapes real-time financial news across **10+ markets** and posts to your channel, notifies subscribers, and promotes across trading forums.

---

## 🗂️ Project Structure

```
├── bot.py              # Main Telegram bot (commands + inline buttons)
├── auto_poster.py      # Scheduled auto-posting to Telegram channel
├── forums_bot.py       # Multi-forum promotion bot (Quora, TradingView, etc.)
├── news_scraper.py     # Async RSS news fetcher with caching
├── database.py         # SQLite database (users, requests, subscriptions, stats)
├── config.py           # Loads environment variables
├── Procfile            # Heroku/Render process definitions
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── README.md           # This file
```

---

## ⚙️ Features

- 🪙 **10+ Markets** — Crypto, Forex, Stocks, Asia, Japan, India, Commodities, Events, Global, Company
- 📡 **Async RSS Scraping** — Parallel feed fetching with 15-min cache
- 📢 **Auto-posting** to Telegram channel on schedule
- 🔔 **Subscriber alerts** — Users can subscribe to specific markets
- 🗞️ **Daily digest** — Morning summary posted at 8:00 AM
- 📊 **Admin stats** — Uptime, post count, user stats every 12 hours
- 🌐 **Forum promotion** — Auto-answers on Quora, TradingView, ForexFactory
- 🗄️ **SQLite database** — Tracks users, requests, subscriptions, posted news
- 🔁 **Duplicate prevention** — Never posts the same article twice

---

## 🚀 Quick Start (Local)

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/trading-news-bot.git
cd trading-news-bot
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
```
Edit `.env` and fill in your values:
```
TELEGRAM_TOKEN=8924733120:AAHiWNV8eflhQ4fSQQd7sCoykHs5dsJkQPY
CHANNEL_ID=@cryptoctocknews
ADMIN_ID=1369974797
```

### 5. Run the bot
```bash
python bot.py
```

### 6. Run the auto-poster (separate terminal)
```bash
python auto_poster.py
```

### 7. Run the forums bot (optional, separate terminal)
```bash
python forums_bot.py
```

---

## ☁️ Deploy on Heroku

### 1. Install Heroku CLI and log in
```bash
heroku login
```

### 2. Create a new app
```bash
heroku create your-app-name
```

### 3. Add Chrome buildpacks (required for Selenium)
```bash
heroku buildpacks:add heroku/python
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-chromedriver
```

### 4. Set environment variables
```bash
heroku config:set TELEGRAM_TOKEN=your_token_here
heroku config:set CHANNEL_ID=@cryptoctocknews
heroku config:set ADMIN_ID=1369974797
```

### 5. Deploy
```bash
git add .
git commit -m "Initial deploy"
git push heroku main
```

### 6. Scale dynos
```bash
heroku ps:scale web=1 worker=1 forums=1
```

---

## ☁️ Deploy on Render

1. Go to [render.com](https://render.com) and create a new account
2. Click **New → Web Service** and connect your GitHub repo
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `gunicorn bot:app`
5. Add environment variables under **Environment** tab
6. For `worker` and `forums`, create additional **Background Worker** services with:
   - Worker: `python auto_poster.py`
   - Forums: `python forums_bot.py`

---

## 🤖 Bot Commands

| Command | Description |
|---|---|
| `/start` | Show market menu with inline buttons |
| `/latest` | Get latest global news |
| Type `crypto` | Get crypto news directly |
| Type `forex` | Get forex news directly |
| Type `asia` | Get Asian market news |
| *(any market name)* | Works for all supported markets |

---

## 📡 Supported Markets

| Market | Sources |
|---|---|
| 🪙 Crypto | CoinDesk, CoinTelegraph, Decrypt, Bitcoin Magazine |
| 💱 Forex | MoneyControl, Reuters, FXStreet |
| 📈 Stocks | Economic Times, Yahoo Finance, MarketWatch |
| 🌍 Global | Reuters, Yahoo Finance, BBC Business, NY Times |
| 🌏 Asia | Economic Times Asia, Reuters Asia, SCMP |
| 🗾 Japan | Reuters, NHK Business |
| 🏢 Company | MoneyControl, Reuters Company |
| 🛢️ Commodities | Reuters Commodities, Investing.com |
| 🇮🇳 India | Economic Times, MoneyControl, NDTV Profit |
| 📅 Events | Investing.com, Reuters |

---

## 🗄️ Database Tables

| Table | Purpose |
|---|---|
| `requests` | Logs every user market request |
| `users` | Stores user profiles and ban status |
| `posted_news` | Prevents duplicate channel posts |
| `subscriptions` | User market alert subscriptions |
| `stats` | General bot event tracking |

---

## 📦 Key Dependencies

| Package | Purpose |
|---|---|
| `python-telegram-bot` | Telegram Bot API |
| `feedparser` | RSS feed parsing |
| `aiohttp` | Async HTTP requests |
| `selenium` | Browser automation for forums |
| `schedule` | Job scheduling |
| `flask` + `gunicorn` | Web server for Heroku/Render |
| `python-dotenv` | Environment variable loading |
| `beautifulsoup4` | HTML cleaning |

---

## 🔐 Security Notes

- Never commit your `.env` file to Git — add it to `.gitignore`
- Rotate your Telegram bot token if it was ever exposed publicly
- Use environment variables on Heroku/Render instead of hardcoding credentials

---

## 📄 License

MIT License — free to use and modify.
```
