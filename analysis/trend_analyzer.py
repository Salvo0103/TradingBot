"""Analisi del trend e del bias di mercato."""

from dataclasses import dataclass

import pandas as pd

from engine.models import Direction


@dataclass(frozen=True)
class TrendAnalysis:
    """Risultato dell'analisi del trend."""

    direction: Direction
    confidence: float
    bullish_score: float
    bearish_score: float
    reasons: list[str]


class TrendAnalyzer:
    """Determina il bias usando struttura e medie mobili."""

    REQUIRED_COLUMNS = {"high", "low", "close"}

    def __init__(
        self,
        structure_window: int = 20,
        fast_ema: int = 20,
        slow_ema: int = 50,
        minimum_bars: int = 60,
    ) -> None:
        self.structure_window = structure_window
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.minimum_bars = minimum_bars

    def analyze(self, candles: pd.DataFrame) -> TrendAnalysis:
        """Analizza un DataFrame OHLC e restituisce il bias."""

        self._validate_data(candles)

        data = candles.copy()
        data["ema_fast"] = data["close"].ewm(
            span=self.fast_ema,
            adjust=False,
        ).mean()
        data["ema_slow"] = data["close"].ewm(
            span=self.slow_ema,
            adjust=False,
        ).mean()

        bullish_score = 0.0
        bearish_score = 0.0
        reasons: list[str] = []

        previous = data.iloc[
            -(self.structure_window * 2):-self.structure_window
        ]
        recent = data.iloc[-self.structure_window:]

        previous_high = float(previous["high"].max())
        previous_low = float(previous["low"].min())
        recent_high = float(recent["high"].max())
        recent_low = float(recent["low"].min())

        higher_high = recent_high > previous_high
        higher_low = recent_low > previous_low
        lower_high = recent_high < previous_high
        lower_low = recent_low < previous_low

        if higher_high:
            bullish_score += 20
            reasons.append("Massimo recente superiore al precedente")

        if higher_low:
            bullish_score += 20
            reasons.append("Minimo recente superiore al precedente")

        if lower_high:
            bearish_score += 20
            reasons.append("Massimo recente inferiore al precedente")

        if lower_low:
            bearish_score += 20
            reasons.append("Minimo recente inferiore al precedente")

        last_close = float(data["close"].iloc[-1])
        last_fast_ema = float(data["ema_fast"].iloc[-1])
        last_slow_ema = float(data["ema_slow"].iloc[-1])

        if last_close > last_slow_ema:
            bullish_score += 20
            reasons.append("Prezzo sopra EMA lenta")
        elif last_close < last_slow_ema:
            bearish_score += 20
            reasons.append("Prezzo sotto EMA lenta")

        if last_fast_ema > last_slow_ema:
            bullish_score += 20
            reasons.append("EMA veloce sopra EMA lenta")
        elif last_fast_ema < last_slow_ema:
            bearish_score += 20
            reasons.append("EMA veloce sotto EMA lenta")

        fast_ema_past = float(data["ema_fast"].iloc[-6])

        if last_fast_ema > fast_ema_past:
            bullish_score += 20
            reasons.append("EMA veloce inclinata al rialzo")
        elif last_fast_ema < fast_ema_past:
            bearish_score += 20
            reasons.append("EMA veloce inclinata al ribasso")

        direction, confidence = self._classify_direction(
            bullish_score=bullish_score,
            bearish_score=bearish_score,
        )

        return TrendAnalysis(
            direction=direction,
            confidence=confidence,
            bullish_score=bullish_score,
            bearish_score=bearish_score,
            reasons=reasons,
        )

    @staticmethod
    def _classify_direction(
        bullish_score: float,
        bearish_score: float,
    ) -> tuple[Direction, float]:
        """Converte i punteggi in LONG, SHORT oppure NEUTRAL."""

        difference = abs(bullish_score - bearish_score)
        strongest_score = max(bullish_score, bearish_score)

        if strongest_score < 60 or difference < 20:
            return Direction.NEUTRAL, strongest_score

        if bullish_score > bearish_score:
            return Direction.LONG, bullish_score

        return Direction.SHORT, bearish_score

    def _validate_data(self, candles: pd.DataFrame) -> None:
        missing_columns = self.REQUIRED_COLUMNS.difference(candles.columns)

        if missing_columns:
            raise ValueError(
                "Colonne mancanti nel DataFrame: "
                + ", ".join(sorted(missing_columns))
            )

        if len(candles) < self.minimum_bars:
            raise ValueError(
                f"Servono almeno {self.minimum_bars} candele, "
                f"ma ne sono state ricevute {len(candles)}."
            )

        if candles[list(self.REQUIRED_COLUMNS)].isnull().any().any():
            raise ValueError("I dati OHLC contengono valori mancanti.")