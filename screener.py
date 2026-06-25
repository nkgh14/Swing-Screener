"""
screener.py

Fetches historical daily price data from Alpaca for each symbol in the
watchlist, computes the indicators we care about (moving averages, RSI,
volume surge), and flags symbols matching either swing-trade setup:

  Setup A - "Pullback in an uptrend"
  Setup B - "Oversold bounce"

This module has NO side effects (no emailing, no printing) - it just
returns structured results. That makes it easy to test on its own.
"""

import os
from datetime import datetime, timedelta

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import config


def get_alpaca_client():
    """
    Builds the Alpaca historical data client using API keys from environment
    variables (never hardcode keys in this file).
    """
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    return StockHistoricalDataClient(api_key, secret_key)


def fetch_daily_bars(client, symbols, lookback_days=300):
    """
    Pulls daily OHLCV bars for the given symbols, far enough back to compute
    a 200-day moving average plus some buffer.

    Returns a dict: { "AAPL": DataFrame, "MSFT": DataFrame, ... }
    Each DataFrame is indexed by date with columns: open, high, low, close, volume
    """
    end = datetime.now()
    start = end - timedelta(days=lookback_days)

    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
    )

    bar_set = client.get_stock_bars(request)
    df_all = bar_set.df  # multi-index DataFrame: (symbol, timestamp)

    result = {}
    for symbol in symbols:
        try:
            df = df_all.loc[symbol].copy()
            df.index = pd.to_datetime(df.index)
            result[symbol] = df
        except KeyError:
            # No data returned for this symbol (bad ticker, delisted, etc.)
            result[symbol] = None

    return result


def compute_rsi(close_prices, period=14):
    """
    Standard RSI calculation (Wilder's smoothing).
    Returns a pandas Series of RSI values, same length as input.
    """
    delta = close_prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def evaluate_symbol(symbol, df):
    """
    Applies all filters to a single symbol's price history.

    Returns a dict describing what (if anything) was flagged, or None if
    the symbol didn't have enough data to evaluate.
    """
    if df is None or len(df) < config.TREND_LOOKBACK_LONG:
        return None

    df = df.sort_index()
    close = df["close"]
    volume = df["volume"]

    latest_price = close.iloc[-1]
    latest_volume = volume.iloc[-1]

    # --- Liquidity / quality filter ---
    avg_volume_20 = volume.tail(config.VOLUME_SURGE_LOOKBACK).mean()
    if latest_price < config.MIN_PRICE or avg_volume_20 < config.MIN_AVG_VOLUME:
        return None

    # --- Trend filter ---
    ma_short = close.rolling(config.TREND_LOOKBACK_SHORT).mean().iloc[-1]
    ma_long = close.rolling(config.TREND_LOOKBACK_LONG).mean().iloc[-1]
    in_uptrend = (latest_price > ma_short) and (ma_short > ma_long)

    if not in_uptrend:
        return None  # both setups require an uptrend, so stop here

    # --- Momentum ---
    rsi_series = compute_rsi(close, config.RSI_PERIOD)
    latest_rsi = rsi_series.iloc[-1]
    prev_rsi = rsi_series.iloc[-2]

    setups_hit = []

    # Setup A: Pullback in an uptrend
    if config.PULLBACK_RSI_MIN <= latest_rsi <= config.PULLBACK_RSI_MAX:
        setups_hit.append("pullback")

    # Setup B: Oversold bounce (RSI crossing back above threshold)
    crossed_up = (prev_rsi < config.OVERSOLD_RSI_THRESHOLD) and (
        latest_rsi >= config.OVERSOLD_RSI_THRESHOLD
    )
    if crossed_up:
        setups_hit.append("oversold_bounce")

    if not setups_hit:
        return None

    # --- Volume confirmation ---
    volume_ratio = latest_volume / avg_volume_20 if avg_volume_20 > 0 else 0
    volume_confirmed = volume_ratio >= config.VOLUME_SURGE_MULTIPLIER

    return {
        "symbol": symbol,
        "price": round(float(latest_price), 2),
        "rsi": round(float(latest_rsi), 1),
        "ma50": round(float(ma_short), 2),
        "ma200": round(float(ma_long), 2),
        "volume_ratio": round(float(volume_ratio), 2),
        "volume_confirmed": bool(volume_confirmed),
        "setups": setups_hit,
    }


def run_screen():
    """
    Main entry point: fetches data for the full watchlist and returns a list
    of flagged results (only symbols that matched at least one setup).
    """
    client = get_alpaca_client()
    bars_by_symbol = fetch_daily_bars(client, config.WATCHLIST)

    flagged = []
    for symbol in config.WATCHLIST:
        result = evaluate_symbol(symbol, bars_by_symbol.get(symbol))
        if result is not None:
            flagged.append(result)

    return flagged


if __name__ == "__main__":
    # Lets you run `python screener.py` directly to sanity-check results
    # without sending an email.
    results = run_screen()
    if not results:
        print("No symbols matched today.")
    for r in results:
        print(r)
