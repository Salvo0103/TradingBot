"""Rilevamento dei Fair Value Gap (FVG)."""

from dataclasses import dataclass

import pandas as pd

from engine.models import Direction


@dataclass(frozen=True)
class FairValueGapAnalysis:
    detected: bool
    direction: Direction
    upper_level: float | None
    lower_level: float | None
    confidence: float
    reasons: list[str]


class FairValueGapAnalyzer:
    """Individua Fair Value Gap rialzisti e ribassisti."""

    REQUIRED_COLUMNS = {"high", "low"}

    def __init__(self, minimum_bars: int = 3) -> None:
        self.minimum_bars = minimum_bars

    def analyze(
        self,
        candles: pd.DataFrame,
    ) -> FairValueGapAnalysis:

        self._validate_data(candles)

        c1 = candles.iloc[-3]
        c2 = candles.iloc[-2]
        c3 = candles.iloc[-1]

        # Bullish FVG
        if float(c3["low"]) > float(c1["high"]):

            return FairValueGapAnalysis(
                detected=True,
                direction=Direction.LONG,
                upper_level=float(c3["low"]),
                lower_level=float(c1["high"]),
                confidence=90.0,
                reasons=[
                    "Bullish Fair Value Gap rilevato"
                ],
            )

        # Bearish FVG
        if float(c3["high"]) < float(c1["low"]):

            return FairValueGapAnalysis(
                detected=True,
                direction=Direction.SHORT,
                upper_level=float(c1["low"]),
                lower_level=float(c3["high"]),
                confidence=90.0,
                reasons=[
                    "Bearish Fair Value Gap rilevato"
                ],
            )

        return FairValueGapAnalysis(
            detected=False,
            direction=Direction.NEUTRAL,
            upper_level=None,
            lower_level=None,
            confidence=0.0,
            reasons=[
                "Nessun Fair Value Gap rilevato"
            ],
        )

    def _validate_data(self, candles: pd.DataFrame):

        missing = self.REQUIRED_COLUMNS.difference(
            candles.columns
        )

        if missing:
            raise ValueError(
                f"Colonne mancanti: {missing}"
            )

        if len(candles) < self.minimum_bars:
            raise ValueError(
                "Numero di candele insufficiente."
            )