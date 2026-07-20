"""Modelli dei dati grezzi ricevuti da TradingView."""

from pydantic import BaseModel


class CandleData(BaseModel):
    open: float
    high: float
    low: float
    close: float


class TimeframeData(BaseModel):
    candle: CandleData
    ema50: float | None = None
    ema200: float | None = None


class TradingViewRawPayload(BaseModel):
    secret: str

    asset: str
    timeframe: str
    timestamp: int

    session_name: str

    current: CandleData
    previous_1: CandleData
    previous_2: CandleData

    atr: float | None = None

    last_swing_high: float | None = None
    last_swing_low: float | None = None

    previous_swing_high: float | None = None
    previous_swing_low: float | None = None

    # Gestione del ciclo di vita del setup
    setup_invalidated: bool = False
    invalidation_reason: str | None = None

    d1: TimeframeData
    h4: TimeframeData
    h1: TimeframeData