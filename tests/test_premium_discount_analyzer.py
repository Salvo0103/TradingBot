"""Test del Premium/Discount Analyzer con dati simulati."""

import unittest

import numpy as np
import pandas as pd

from analysis.premium_discount_analyzer import PremiumDiscountAnalyzer
from engine.models import Direction


def create_range_candles(
    start: float,
    end: float,
    bars: int = 50,
) -> pd.DataFrame:
    """Crea una sequenza di candele con range controllato."""

    close = np.linspace(start, end, bars)

    return pd.DataFrame(
        {
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
        }
    )


class PremiumDiscountAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = PremiumDiscountAnalyzer(
            lookback=50,
            minimum_bars=50,
        )

    def test_rileva_discount_per_long(self) -> None:
        candles = create_range_candles(110, 90)

        result = self.analyzer.analyze(
            candles,
            direction=Direction.LONG,
        )

        self.assertEqual(result.zone, "discount")
        self.assertTrue(result.in_discount)
        self.assertFalse(result.in_premium)
        self.assertEqual(result.confidence, 95.0)

    def test_rileva_premium_per_short(self) -> None:
        candles = create_range_candles(90, 110)

        result = self.analyzer.analyze(
            candles,
            direction=Direction.SHORT,
        )

        self.assertEqual(result.zone, "premium")
        self.assertTrue(result.in_premium)
        self.assertFalse(result.in_discount)
        self.assertEqual(result.confidence, 95.0)

    def test_rileva_equilibrium(self) -> None:
        candles = create_range_candles(95, 105)

        middle = len(candles) - 1
        equilibrium = (
            float(candles["high"].max())
            + float(candles["low"].min())
        ) / 2

        candles.loc[middle, "close"] = equilibrium

        result = self.analyzer.analyze(
            candles,
            direction=Direction.NEUTRAL,
        )

        self.assertEqual(result.zone, "equilibrium")
        self.assertFalse(result.in_premium)
        self.assertFalse(result.in_discount)

    def test_rifiuta_dati_insufficienti(self) -> None:
        candles = create_range_candles(100, 105, bars=20)

        with self.assertRaises(ValueError):
            self.analyzer.analyze(candles)


if __name__ == "__main__":
    unittest.main()