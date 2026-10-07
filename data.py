"""Données de marché : Alpaca (actions US, temps réel IEX) si clés présentes, sinon yfinance."""
import os
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


def _is_stock(s: str) -> bool:
    return s.replace(".", "").isalpha()  # NVDA oui ; GC=F, BTC-USD non


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
    if os.getenv("ALPACA_KEY") and os.getenv("ALPACA_SECRET") and _is_stock(symbol):
        try:
            return _alpaca(symbol, interval, period), "alpaca"
        except Exception as e:
            print(f"{symbol}: Alpaca KO ({e}), repli yfinance")
    return _yf(symbol, interval, period), "yfinance"


def get_pair(symbol: str, tf: str):
    i, p, hi, hp = TF[tf]
    df, src = get_bars(symbol, i, p)
    htf, _ = get_bars(symbol, hi, hp)
    return df, htf, src
