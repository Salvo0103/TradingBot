"""Rilevamento semplificato degli Order Block per TradingBot v1.0."""

from dataclasses import dataclass

import pandas as pd

from engine.models import Direction


@dataclass(frozen=True)
class OrderBlockAnalysis:
    """Risultato dell'analisi di un Order Block."""

    detected: bool
    direction: Direction
    upper_level: float | None
    lower_level: float | None
    mitigated: bool
    confidence: float
    reasons: list[str]


class OrderBlockAnalyzer:
    """
    Individua l'ultima candela opposta prima di un impulso strutturale.

    Bullish OB:
    ultima candela ribassista prima di un impulso rialzista.

    Bearish OB:
    ultima candela rialzista prima di un impulso ribassista.
    """

    REQUIRED_COLUMNS = {"open", "high", "low", "close"}

    def __init__(
        self,
        lookback: int = 15,
        displacement_multiplier: float = 1.5,
        minimum_bars: int = 20,
    ) -> None:
        self.lookback = lookback
        self.displacement_multiplier = displacement_multiplier
        self.minimum_bars = minimum_bars

    def analyze(
        self,
        candles: pd.DataFrame,
        direction: Direction,
    ) -> OrderBlockAnalysis:
        """Cerca un Order Block coerente con la direzione proposta."""

        self._validate_data(candles)

        recent = candles.iloc[-self.lookback:].copy()
        recent["body"] = (recent["close"] - recent["open"]).abs()

        average_body = float(recent["body"].iloc[:-1].mean())

        if average_body <= 0:
            return self._not_detected("Corpi delle candele non validi")

        for index in range(len(recent) - 2, 0, -1):
            candidate = recent.iloc[index]
            impulse = recent.iloc[index + 1]

            candidate_open = float(candidate["open"])
            candidate_close = float(candidate["close"])
            candidate_high = float(candidate["high"])
            candidate_low = float(candidate["low"])

            impulse_open = float(impulse["open"])
            impulse_close = float(impulse["close"])
            impulse_body = abs(impulse_close - impulse_open)

            strong_displacement = (
                impulse_body >= average_body * self.displacement_multiplier
            )

            if not strong_displacement:
                continue

            if direction == Direction.LONG:
                opposite_candle = candidate_close < candidate_open
                bullish_impulse = impulse_close > impulse_open

                if opposite_candle and bullish_impulse:
                    return self._build_result(
                        candles=candles,
                        direction=Direction.LONG,
                        upper_level=candidate_high,
                        lower_level=candidate_low,
                        reason=(
                            "Ultima candela ribassista prima "
                            "del displacement rialzista"
                        ),
                    )

            if direction == Direction.SHORT:
                opposite_candle = candidate_close > candidate_open
                bearish_impulse = impulse_close < impulse_open

                if opposite_candle and bearish_impulse:
                    return self._build_result(
                        candles=candles,
                        direction=Direction.SHORT,
                        upper_level=candidate_high,
                        lower_level=candidate_low,
                        reason=(
                            "Ultima candela rialzista prima "
                            "del displacement ribassista"
                        ),
                    )

        return self._not_detected(
            "Nessun Order Block coerente con la direzione"
        )

    def _build_result(
        self,
        candles: pd.DataFrame,
        direction: Direction,
        upper_level: float,
        lower_level: float,
        reason: str,
    ) -> OrderBlockAnalysis:
        current_high = float(candles["high"].iloc[-1])
        current_low = float(candles["low"].iloc[-1])

        mitigated = (
            current_low <= upper_level
            and current_high >= lower_level
        )

        confidence = 80.0
        reasons = [reason]

        if mitigated:
            confidence += 15.0
            reasons.append("Prezzo rientrato nell'Order Block")

        return OrderBlockAnalysis(
            detected=True,
            direction=direction,
            upper_level=upper_level,
            lower_level=lower_level,
            mitigated=mitigated,
            confidence=min(confidence, 100.0),
            reasons=reasons,
        )

    @staticmethod
    def _not_detected(reason: str) -> OrderBlockAnalysis:
        return OrderBlockAnalysis(
            detected=False,
            direction=Direction.NEUTRAL,
            upper_level=None,
            lower_level=None,
            mitigated=False,
            confidence=0.0,
            reasons=[reason],
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