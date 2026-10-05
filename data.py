import pandas as pd
import yfinance as yf

# unité de temps -> (interval, period, htf_interval, htf_period)
TF = {
    "1m": ("1m", "1d", "15m", "5d"),
    "5m": ("5m", "5d", "1h", "1mo"),
    "15m": ("15m", "10d", "1h", "3mo"),
    "1h": ("1h", "60d", "1d", "1y"),
}


def get_bars(symbol: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
    return df


def get_pair(symbol: str, tf: str):
    i, p, hi, hp = TF[tf]
    return get_bars(symbol, i, p), get_bars(symbol, hi, hp)
