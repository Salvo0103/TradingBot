"""Test del Liquidity Analyzer con dati simulati."""

import unittest

import pandas as pd

from analysis.liquidity_analyzer import LiquidityAnalyzer
from engine.models import Direction


def create_base_candles() -> pd.DataFrame:
    """Crea una sequenza neutra di 30 candele."""

    rows = []

    for index in range(30):
        price = 100 + (index * 0.05)

        rows.append(
            {
                "open": price,
                "high": price + 0.30,
                "low": price - 0.30,
                "close": price + 0.05,
            }
        )

    return pd.DataFrame(rows)


class LiquidityAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = LiquidityAnalyzer()

    def test_rileva_sweep_dei_minimi(self) -> None:
        candles = create_base_candles()

        previous_low = float(candles.iloc[-21:-1]["low"].min())

        candles.iloc[-1] = {
            "open": previous_low + 0.20,
            "high": previous_low + 0.45,
            "low": previous_low - 0.25,
            "close": previous_low + 0.15,
        }

        result = self.analyzer.analyze(candles)

        self.assertTrue(result.detected)
        self.assertEqual(result.direction, Direction.LONG)
        self.assertAlmostEqual(result.swept_level, previous_low)

    def test_rileva_sweep_dei_massimi(self) -> None:
        candles = create_base_candles()

        previous_high = float(candles.iloc[-21:-1]["high"].max())

        candles.iloc[-1] = {
            "open": previous_high - 0.20,
            "high": previous_high + 0.25,
            "low": previous_high - 0.45,
            "close": previous_high - 0.15,
        }

        result = self.analyzer.analyze(candles)

        self.assertTrue(result.detected)
        self.assertEqual(result.direction, Direction.SHORT)
        self.assertAlmostEqual(result.swept_level, previous_high)

    def test_nessuno_sweep(self) -> None:
        candles = create_base_candles()

        previous = candles.iloc[-21:-1]
        previous_high = float(previous["high"].max())
        previous_low = float(previous["low"].min())
        middle_price = (previous_high + previous_low) / 2

        candles.iloc[-1] = {
            "open": middle_price,
            "high": middle_price + 0.10,
            "low": middle_price - 0.10,
            "close": middle_price + 0.03,
        }

        result = self.analyzer.analyze(candles)

        self.assertFalse(result.detected)
        self.assertEqual(result.direction, Direction.NEUTRAL)
        self.assertIsNone(result.swept_level)


if __name__ == "__main__":
    unittest.main()