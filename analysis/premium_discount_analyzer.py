"""Analisi delle zone Premium, Equilibrium e Discount."""

from dataclasses import dataclass

import pandas as pd

from engine.models import Direction


@dataclass(frozen=True)
class PremiumDiscountAnalysis:
    """Risultato dell'analisi Premium/Discount."""

    zone: str
    in_premium: bool
    in_discount: bool
    equilibrium: float
    range_high: float
    range_low: float
    confidence: float
    reasons: list[str]


class PremiumDiscountAnalyzer:
    """Classifica il prezzo corrente rispetto al range recente."""

    REQUIRED_COLUMNS = {"high", "low", "close"}

    def __init__(
        self,
        lookback: int = 50,
        minimum_bars: int = 50,
        equilibrium_tolerance: float = 0.05,
    ) -> None:
        self.lookback = lookback
        self.minimum_bars = minimum_bars
        self.equilibrium_tolerance = equilibrium_tolerance

    def analyze(
        self,
        candles: pd.DataFrame,
        direction: Direction = Direction.NEUTRAL,
    ) -> PremiumDiscountAnalysis:
        """Determina se il prezzo è in premium, discount o equilibrium."""

        self._validate_data(candles)

        recent = candles.iloc[-self.lookback:]

        range_high = float(recent["high"].max())
        range_low = float(recent["low"].min())
        current_close = float(recent["close"].iloc[-1])

        total_range = range_high - range_low

        if total_range <= 0:
            raise ValueError("Il range analizzato non è valido.")

        equilibrium = (range_high + range_low) / 2
        tolerance = total_range * self.equilibrium_tolerance

        in_premium = current_close > equilibrium + tolerance
        in_discount = current_close < equilibrium - tolerance

        if in_premium:
            zone = "premium"
            confidence = 85.0
            reasons = ["Prezzo sopra l'equilibrium del range"]

            if direction == Direction.SHORT:
                confidence = 95.0
                reasons.append("Zona favorevole per una possibile operazione short")

        elif in_discount:
            zone = "discount"
            confidence = 85.0
            reasons = ["Prezzo sotto l'equilibrium del range"]

            if direction == Direction.LONG:
                confidence = 95.0
                reasons.append("Zona favorevole per una possibile operazione long")

        else:
            zone = "equilibrium"
            confidence = 60.0
            reasons = ["Prezzo vicino all'equilibrium del range"]

        return PremiumDiscountAnalysis(
            zone=zone,
            in_premium=in_premium,
            in_discount=in_discount,
            equilibrium=equilibrium,
            range_high=range_high,
            range_low=range_low,
            confidence=confidence,
            reasons=reasons,
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