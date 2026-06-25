# Swing Trading Screener

A free, automated daily stock screener. Runs once a day after market close,
checks a watchlist against two swing-trading setups, cross-references recent
news, and emails you the results. No trades are ever placed — this is a
research/alert tool only.

## What it checks

For each symbol in `config.py`'s `WATCHLIST`:

1. **Liquidity filter** — price above `MIN_PRICE`, average volume above `MIN_AVG_VOLUME`
2. **Trend filter** — price above 50-day MA, and 50-day MA above 200-day MA
3. **One of two setups:**
   - **Pullback in an uptrend** — RSI between 40–60 (cooled off, not overbought)
   - **Oversold bounce** — RSI just crossed back above 30
4. **Volume confirmation** — today's volume vs. 20-day average (flagged, not required)
5. **News** — recent headlines for anything that got flagged

You'll get one email every day the bot runs, even if nothing matched
(that's how you know it's still alive and didn't silently break).

## One-time setup

### 1. Create the GitHub repository
- Create a new **public** repository on GitHub (e.g. `swing-screener`)
- Upload all the files in this folder to it (or use `git push` if you're
  comfortable with git — otherwise GitHub's web "upload files" button works fine)

### 2. Get a Gmail App Password (for sending email)
Regular Gmail passwords won't work for this — you need an "app password":
1. Go to your Google Account → Security
2. Turn on 2-Step Verification if it isn't already on (required for app passwords)
3. Search for "App Passwords" in your account settings
4. Generate one for "Mail" — you'll get a 16-character code
5. Save that code, you'll need it in the next step

### 3. Add your secrets to GitHub
In your repository: **Settings → Secrets and variables → Actions → New repository secret**

Add each of these one at a time (name on the left, value on the right):

| Secret name | Value |
|---|---|
| `ALPACA_API_KEY` | Your Alpaca API Key ID |
| `ALPACA_SECRET_KEY` | Your Alpaca Secret Key |
| `FINNHUB_API_KEY` | Your Finnhub API key |
| `GMAIL_ADDRESS` | The Gmail address you'll send FROM |
| `GMAIL_APP_PASSWORD` | The 16-character app password from step 2 |

### 4. Edit config.py
Open `config.py` and update:
- `EMAIL_FROM` and `EMAIL_TO` — set both to your email (or different addresses)
- `WATCHLIST` — the starter list is just an example; edit it to whatever
  stocks you want covered

### 5. Test it
Go to your repo's **Actions** tab → click **Daily Swing Screener** →
**Run workflow** (this is the manual trigger, no need to wait for the
schedule). Check the run logs, and check your email.

## Schedule

Runs automatically Monday–Friday at 21:30 UTC (after US market close).
GitHub Actions schedules can run a little late under load — that's normal
and doesn't matter for an after-close daily check.

## Important notes

- **This is a screening/alert tool, not a trading bot.** It never places
  trades or touches real money.
- **This is not financial advice.** The technical setups here are common,
  textbook patterns — they are not validated as profitable. Treat every
  email as a starting point for your own research, not a signal to act on.
- The free tiers used here (Alpaca, Finnhub, GitHub Actions) are genuinely
  free for this usage level — no credit card required for any of them.
