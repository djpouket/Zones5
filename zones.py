"""Données de marché : Alpaca (actions US, temps réel IEX) si clés présentes, sinon yfinance."""
import os
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import yfinance as yf

# unité de temps -> (interval, period, htf_interval, htf_period)
TF = {
    "1m": ("1m", "1d", "15m", "5d"),
    "5m": ("5m", "5d", "1h", "1mo"),
    "15m": ("15m", "10d", "1h", "3mo"),
    "1h": ("1h", "60d", "1d", "1y"),
}
ALP = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "1h": "1Hour", "1d": "1Day"}
DAYS = {"1d": 2, "5d": 7, "10d": 14, "1mo": 31, "3mo": 93, "60d": 60, "1y": 365}

SYMBOL_ALIASES = {
    "EURUSD": "EURUSD=X",
    "EURUSD=X": "EURUSD=X",
    "XAUUSD": "XAUUSD=X",
    "XAUUSD=X": "XAUUSD=X",
    "XAGUSD": "XAGUSD=X",
    "XAGUSD=X": "XAGUSD=X",
    "DAX40": "^GDAXI",
    "DAX": "^GDAXI",
    "^GDAXI": "^GDAXI",
    "ETC": "ETC-USD",
    "EETH": "ETH-USD",
    "BTC": "BTC-USD",
    "BTCUSD": "BTC-USD",
    "ETH": "ETH-USD",
}


def normalize_symbol(symbol: str) -> str:
    s = (symbol or "").strip()
    if not s:
        return s
    key = s.upper().replace(" ", "")
    return SYMBOL_ALIASES.get(key, s)


def _is_stock(s: str) -> bool:
    s = normalize_symbol(s)
    return bool(re.fullmatch(r"[A-Za-z]{1,5}(?:\.[A-Za-z0-9]+)?", s)) and not any(ch in s for ch in ("=", "^", "-"))


def _alpaca(symbol: str, interval: str, period: str) -> pd.DataFrame:
    start = (datetime.now(timezone.utc) - timedelta(days=DAYS[period])).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
        headers={"APCA-API-KEY-ID": os.environ["ALPACA_KEY"], "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET"]},
        params={"timeframe": ALP[interval], "start": start, "limit": 800, "sort": "desc",
                "feed": os.getenv("ALPACA_FEED", "iex"), "adjustment": "raw"},
        timeout=20,
    )
    r.raise_for_status()
    bars = r.json().get("bars") or []
    if not bars:
        raise ValueError("Alpaca : aucune barre")
    df = pd.DataFrame(bars).rename(columns={"t": "time", "o": "open", "h": "high", "l": "low", "c": "close"})
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")[["open", "high", "low", "close"]].sort_index()
    if df.index.tz is None:
        df = df.tz_localize("UTC")
    return df.tz_convert("Europe/Paris")


def _yf(symbol: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()


def get_bars(symbol: str, interval: str, period: str):
    """Retourne (DataFrame, source)."""
    sym = normalize_symbol(symbol)
    if os.getenv("ALPACA_KEY") and os.getenv("ALPACA_SECRET") and _is_stock(sym):
        try:
            return _alpaca(sym, interval, period), "alpaca"
        except Exception as e:
            print(f"{sym}: Alpaca KO ({e}), repli yfinance")
    return _yf(sym, interval, period), "yfinance"


def get_pair(symbol: str, tf: str):
    i, p, hi, hp = TF[tf]
    df, src = get_bars(symbol, i, p)
    htf, _ = get_bars(symbol, hi, hp)
    return df, htf, src
