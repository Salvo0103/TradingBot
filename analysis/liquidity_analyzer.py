"""Rilevamento degli sweep di liquidità."""

from dataclasses import dataclass

import pandas as pd

from engine.models import Direction


@dataclass(frozen=True)
class LiquiditySweepAnalysis:
    """Risultato dell'analisi di uno sweep di liquidità."""

    detected: bool
    direction: Direction
    swept_level: float | None
    confidence: float
    reasons: list[str]


class LiquidityAnalyzer:
    """Rileva sweep sopra massimi o sotto minimi recenti."""

    REQUIRED_COLUMNS = {"open", "high", "low", "close"}

    def __init__(
        self,
        lookback: int = 20,
        minimum_bars: int = 30,
        minimum_rejection_ratio: float = 0.35,
    ) -> None:
        self.lookback = lookback
        self.minimum_bars = minimum_bars
        self.minimum_rejection_ratio = minimum_rejection_ratio

    def analyze(self, candles: pd.DataFrame) -> LiquiditySweepAnalysis:
        """Analizza l'ultima candela rispetto alla liquidità recente."""

        self._validate_data(candles)

        previous = candles.iloc[-(self.lookback + 1):-1]
        current = candles.iloc[-1]

        previous_high = float(previous["high"].max())
        previous_low = float(previous["low"].min())

        current_open = float(current["open"])
        current_high = float(current["high"])
        current_low = float(current["low"])
        current_close = float(current["close"])

        candle_range = current_high - current_low

        if candle_range <= 0:
            return LiquiditySweepAnalysis(
                detected=False,
                direction=Direction.NEUTRAL,
                swept_level=None,
                confidence=0.0,
                reasons=["Candela senza range valido"],
            )

        upper_wick = current_high - max(current_open, current_close)
        lower_wick = min(current_open, current_close) - current_low

        upper_rejection_ratio = upper_wick / candle_range
        lower_rejection_ratio = lower_wick / candle_range

        swept_high = (
            current_high > previous_high
            and current_close < previous_high
        )

        swept_low = (
            current_low < previous_low
            and current_close > previous_low
        )

        if swept_low:
            confidence = 70.0
            reasons = [
                "Minimo recente superato",
                "Chiusura tornata sopra il livello di liquidità",
            ]

            if lower_rejection_ratio >= self.minimum_rejection_ratio:
                confidence += 20
                reasons.append("Forte rejection wick inferiore")

            if current_close > current_open:
                confidence += 10
                reasons.append("Candela chiusa rialzista")

            return LiquiditySweepAnalysis(
                detected=True,
                direction=Direction.LONG,
                swept_level=previous_low,
                confidence=min(confidence, 100.0),
                reasons=reasons,
            )

        if swept_high:
            confidence = 70.0
            reasons = [
                "Massimo recente superato",
                "Chiusura tornata sotto il livello di liquidità",
            ]

            if upper_rejection_ratio >= self.minimum_rejection_ratio:
                confidence += 20
                reasons.append("Forte rejection wick superiore")

            if current_close < current_open:
                confidence += 10
                reasons.append("Candela chiusa ribassista")

            return LiquiditySweepAnalysis(
                detected=True,
                direction=Direction.SHORT,
                swept_level=previous_high,
                confidence=min(confidence, 100.0),
                reasons=reasons,
            )

        return LiquiditySweepAnalysis(
            detected=False,
            direction=Direction.NEUTRAL,
            swept_level=None,
            confidence=0.0,
            reasons=["Nessuno sweep di liquidità rilevato"],
        )

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