"""
screener.py

Fetches historical daily price data from Alpaca for each symbol in the
watchlist and applies three filters:

  1. Uptrend  — price > MA20 > MA50 > MA200, all three MAs sloping higher
  2. ADR      — average daily range >= ADR_MIN_PCT (stock is actually moving)
  3. Tight    — recent ATR has contracted vs the prior period (consolidation)

This module has NO side effects (no emailing, no printing) - it just
returns structured results. That makes it easy to test on its own.
"""

import os
from datetime import datetime, timedelta

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import config


def get_alpaca_client():
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    return StockHistoricalDataClient(api_key, secret_key)


def fetch_daily_bars(client, symbols, lookback_days=300):
    """
    Pulls daily OHLCV bars for the given symbols.
    Returns a dict: { "AAPL": DataFrame, ... }
    """
    # End 1 day back — free IEX tier rejects requests that reach into today.
    end = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=lookback_days)
    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )

    bar_set = client.get_stock_bars(request)
    df_all = bar_set.df

    result = {}
    for symbol in symbols:
        try:
            df = df_all.loc[symbol].copy()
            df.index = pd.to_datetime(df.index)
            result[symbol] = df.sort_index()
        except KeyError:
            result[symbol] = None

    return result


def fetch_volatility_bars(client, symbol):
    """
    Fetches 3 years of daily bars for the historical volatility filter.
    """
    end = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=3 * 365)

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )

    try:
        bar_set = client.get_stock_bars(request)
        df = bar_set.df.loc[symbol].copy()
        df.index = pd.to_datetime(df.index)
        return df.sort_index()
    except Exception:
        return None


def compute_adr(df):
    """Average Daily Range over the last ADR_LOOKBACK days, as a percentage."""
    recent = df.tail(config.ADR_LOOKBACK)
    daily_range_pct = (recent["high"] - recent["low"]) / recent["close"] * 100
    return float(daily_range_pct.mean())


def compute_atr(prices, n):
    """Simple ATR (true range average) over the last n bars."""
    tr = pd.concat([
        prices["high"] - prices["low"],
        (prices["high"] - prices["close"].shift(1)).abs(),
        (prices["low"]  - prices["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return float(tr.tail(n).mean())


def compute_volatility_pct(df, window=10, swing_threshold=0.10):
    """
    Fraction of rolling `window`-day periods (over 3 years of history) where
    the high-to-low swing exceeded swing_threshold relative to the window open.

    # This is a measure of historical capability to move 10%+ in 10 trading
    # days — not a prediction that it will happen again.
    """
    opens = df["open"].values
    highs = df["high"].values
    lows  = df["low"].values

    n = len(df)
    if n < window:
        return 0.0

    hit = 0
    total = n - window + 1
    for i in range(total):
        period_open = opens[i]
        if period_open == 0:
            total -= 1
            continue
        swing = (highs[i : i + window].max() - lows[i : i + window].min()) / period_open
        if swing >= swing_threshold:
            hit += 1

    return hit / total if total > 0 else 0.0


def passes_volatility_filter(client, symbol, min_pct=0.25):
    """
    Returns (passes: bool, vol_pct: float). Requires at least 25% of rolling
    10-day windows over 3 years of history to have shown a 10%+ swing.
    """
    df = fetch_volatility_bars(client, symbol)
    if df is None or df.empty:
        return False, 0.0
    vol_pct = compute_volatility_pct(df)
    return vol_pct >= min_pct, round(vol_pct * 100, 1)


def evaluate_symbol(symbol, df):
    """
    Applies all price-based filters to a single symbol.
    Returns a result dict if it passes, or None if it doesn't.
    """
    min_bars = config.MA_LONG + config.MA_SLOPE_LOOKBACK
    if df is None or len(df) < min_bars:
        return None

    close  = df["close"]
    volume = df["volume"]

    latest_price  = float(close.iloc[-1])
    latest_volume = float(volume.iloc[-1])

    # --- Liquidity filter ---
    avg_volume_20 = float(volume.tail(config.VOLUME_SURGE_LOOKBACK).mean())
    if latest_price < config.MIN_PRICE or avg_volume_20 < config.MIN_AVG_VOLUME:
        return None

    # --- Uptrend: stacked MAs, all sloping higher ---
    ma20  = close.rolling(config.MA_SHORT).mean()
    ma50  = close.rolling(config.MA_MID).mean()
    ma200 = close.rolling(config.MA_LONG).mean()

    ma20_now,  ma20_then  = float(ma20.iloc[-1]),  float(ma20.iloc[-1 - config.MA_SLOPE_LOOKBACK])
    ma50_now,  ma50_then  = float(ma50.iloc[-1]),  float(ma50.iloc[-1 - config.MA_SLOPE_LOOKBACK])
    ma200_now, ma200_then = float(ma200.iloc[-1]), float(ma200.iloc[-1 - config.MA_SLOPE_LOOKBACK])

    stacked  = latest_price > ma20_now > ma50_now > ma200_now
    sloping  = ma20_now > ma20_then and ma50_now > ma50_then and ma200_now > ma200_then

    if not (stacked and sloping):
        return None

    # --- ADR filter: stock must be actually moving ---
    adr = compute_adr(df)
    if adr < config.ADR_MIN_PCT:
        return None

    # --- Tight consolidation: recent ATR contracted vs prior period ---
    n_recent = config.CONSOLIDATION_RECENT
    n_prior  = config.CONSOLIDATION_PRIOR
    if len(df) < n_recent + n_prior:
        return None

    atr_recent = compute_atr(df.tail(n_recent), n_recent)
    atr_prior  = compute_atr(df.tail(n_recent + n_prior).head(n_prior), n_prior)

    if atr_prior == 0:
        return None

    atr_ratio = atr_recent / atr_prior
    if atr_ratio > config.CONSOLIDATION_MAX_RATIO:
        return None

    # --- Volume confirmation ---
    volume_ratio    = latest_volume / avg_volume_20 if avg_volume_20 > 0 else 0
    volume_confirmed = volume_ratio >= config.VOLUME_SURGE_MULTIPLIER

    change_1d = round((float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100, 2)
    change_5d = round((float(close.iloc[-1]) / float(close.iloc[-6]) - 1) * 100, 2)

    return {
        "symbol":           symbol,
        "price":            round(latest_price, 2),
        "change_1d":        change_1d,
        "change_5d":        change_5d,
        "ma20":             round(ma20_now, 2),
        "ma50":             round(ma50_now, 2),
        "ma200":            round(ma200_now, 2),
        "adr":              round(adr, 2),
        "atr_ratio":        round(atr_ratio, 2),
        "volume_ratio":     round(volume_ratio, 2),
        "volume_confirmed": bool(volume_confirmed),
        "setups":           ["tight_consolidation"],
        "vol_pct":          None,  # filled in by run_screen after volatility check
    }


def run_screen():
    """
    Fetches data for the full watchlist, applies all filters, and returns
    a list of symbols that passed every check.
    """
    client = get_alpaca_client()
    bars_by_symbol = fetch_daily_bars(client, config.WATCHLIST)

    candidates = []
    for symbol in config.WATCHLIST:
        result = evaluate_symbol(symbol, bars_by_symbol.get(symbol))
        if result is not None:
            candidates.append(result)

    flagged = []
    for result in candidates:
        passes, vol_pct = passes_volatility_filter(client, result["symbol"])
        if passes:
            result["vol_pct"] = vol_pct
            flagged.append(result)

    return flagged


if __name__ == "__main__":
    results = run_screen()
    if not results:
        print("No symbols matched today.")
    for r in results:
        print(r)
