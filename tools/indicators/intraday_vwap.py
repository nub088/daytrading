"""Session-anchored VWAP for intraday bars.

A VWAP that resets at the start of each trading session — the default
"VWAP" line every 5-min momentum trader watches. For each session day:

    typical_price = (high + low + close) / 3
    cum_pv        = cumulative sum of typical_price * volume
    cum_v         = cumulative sum of volume
    vwap[t]       = cum_pv[t] / cum_v[t]

Resets happen at the date boundary, so this only makes sense on intraday
OHLCV (5-min, 1-min, etc.). On daily bars use anchored VWAP from
`tools/indicators/avwap.py` instead.
"""
from __future__ import annotations

import pandas as pd


def session_vwap(ohlcv: pd.DataFrame) -> pd.Series:
    """VWAP that restarts at each trading day's first bar.

    Assumes `ohlcv` has a DatetimeIndex of intraday bars and columns
    high/low/close/volume.
    """
    if ohlcv.empty:
        return pd.Series(dtype=float)
    typ = (ohlcv["high"] + ohlcv["low"] + ohlcv["close"]) / 3.0
    pv = typ * ohlcv["volume"]
    # Group by trading day. .date returns python date objects which group cleanly.
    session = pd.Series(ohlcv.index.date, index=ohlcv.index)
    pv_cum = pv.groupby(session).cumsum()
    vol_cum = ohlcv["volume"].groupby(session).cumsum()
    out = pv_cum / vol_cum
    out.name = "session_vwap"
    return out
