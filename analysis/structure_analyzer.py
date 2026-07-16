"""Analisi della struttura di mercato: swing, BOS e CHoCH."""

from dataclasses import dataclass

import pandas as pd

from engine.models import Direction


@dataclass(frozen=True)
class StructureAnalysis:
    """Risultato dell'analisi della struttura di mercato."""

    current_direction: Direction
    bos: bool
    choch: bool
    broken_level: float | None
    last_swing_high: float | None
    last_swing_low: float | None
    confidence: float
    reasons: list[str]


class StructureAnalyzer:
    """Rileva swing high, swing low, BOS e CHoCH."""

    REQUIRED_COLUMNS = {"high", "low", "close"}

    def __init__(
        self,
        swing_window: int = 2,
        minimum_bars: int = 30,
    ) -> None:
        self.swing_window = swing_window
        self.minimum_bars = minimum_bars

    def analyze(
        self,
        candles: pd.DataFrame,
        previous_direction: Direction = Direction.NEUTRAL,
    ) -> StructureAnalysis:
        """Analizza la struttura e rileva eventuali rotture."""

        self._validate_data(candles)

        swing_highs = self._find_swing_highs(candles)
        swing_lows = self._find_swing_lows(candles)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return StructureAnalysis(
                current_direction=Direction.NEUTRAL,
                bos=False,
                choch=False,
                broken_level=None,
                last_swing_high=None,
                last_swing_low=None,
                confidence=0.0,
                reasons=["Swing insufficienti per valutare la struttura"],
            )

        last_swing_high = float(swing_highs[-1][1])
        previous_swing_high = float(swing_highs[-2][1])

        last_swing_low = float(swing_lows[-1][1])
        previous_swing_low = float(swing_lows[-2][1])

        current_close = float(candles["close"].iloc[-1])

        bullish_structure = (
            last_swing_high > previous_swing_high
            and last_swing_low > previous_swing_low
        )

        bearish_structure = (
            last_swing_high < previous_swing_high
            and last_swing_low < previous_swing_low
        )

        if bullish_structure:
            current_direction = Direction.LONG
        elif bearish_structure:
            current_direction = Direction.SHORT
        else:
            current_direction = Direction.NEUTRAL

        bos = False
        choch = False
        broken_level: float | None = None
        confidence = 40.0
        reasons: list[str] = []

        broke_high = current_close > last_swing_high
        broke_low = current_close < last_swing_low

        if broke_high:
            broken_level = last_swing_high

            if previous_direction in {Direction.LONG, Direction.NEUTRAL}:
                bos = True
                confidence = 85.0
                reasons.append("BOS rialzista sopra l'ultimo swing high")
            else:
                choch = True
                confidence = 90.0
                reasons.append(
                    "CHoCH rialzista contro la precedente struttura ribassista"
                )

            current_direction = Direction.LONG

        elif broke_low:
            broken_level = last_swing_low

            if previous_direction in {Direction.SHORT, Direction.NEUTRAL}:
                bos = True
                confidence = 85.0
                reasons.append("BOS ribassista sotto l'ultimo swing low")
            else:
                choch = True
                confidence = 90.0
                reasons.append(
                    "CHoCH ribassista contro la precedente struttura rialzista"
                )

            current_direction = Direction.SHORT

        else:
            if current_direction == Direction.LONG:
                confidence = 65.0
                reasons.append("Struttura con massimi e minimi crescenti")
            elif current_direction == Direction.SHORT:
                confidence = 65.0
                reasons.append("Struttura con massimi e minimi decrescenti")
            else:
                confidence = 35.0
                reasons.append("Struttura laterale o non definita")

        return StructureAnalysis(
            current_direction=current_direction,
            bos=bos,
            choch=choch,
            broken_level=broken_level,
            last_swing_high=last_swing_high,
            last_swing_low=last_swing_low,
            confidence=confidence,
            reasons=reasons,
        )

    def _find_swing_highs(
        self,
        candles: pd.DataFrame,
    ) -> list[tuple[int, float]]:
        """Individua gli swing high locali."""

        highs = candles["high"].tolist()
        swings: list[tuple[int, float]] = []

        for index in range(
            self.swing_window,
            len(highs) - self.swing_window,
        ):
            current = highs[index]
            left = highs[index - self.swing_window:index]
            right = highs[
                index + 1:index + self.swing_window + 1
            ]

            if current > max(left) and current > max(right):
                swings.append((index, float(current)))

        return swings

    def _find_swing_lows(
        self,
        candles: pd.DataFrame,
    ) -> list[tuple[int, float]]:
        """Individua gli swing low locali."""

        lows = candles["low"].tolist()
        swings: list[tuple[int, float]] = []

        for index in range(
            self.swing_window,
            len(lows) - self.swing_window,
        ):
            current = lows[index]
            left = lows[index - self.swing_window:index]
            right = lows[
                index + 1:index + self.swing_window + 1
            ]

            if current < min(left) and current < min(right):
                swings.append((index, float(current)))

        return swings

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