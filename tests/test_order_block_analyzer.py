"""Test dell'Order Block Analyzer con dati simulati."""

import unittest

import pandas as pd

from analysis.order_block_analyzer import OrderBlockAnalyzer
from engine.models import Direction


def create_base_candles() -> pd.DataFrame:
    """Crea una sequenza neutra sufficiente per i test."""

    rows = []

    for index in range(25):
        price = 100 + (index * 0.05)

        rows.append(
            {
                "open": price,
                "high": price + 0.20,
                "low": price - 0.20,
                "close": price + 0.03,
            }
        )

    return pd.DataFrame(rows)


class OrderBlockAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = OrderBlockAnalyzer(
            lookback=15,
            displacement_multiplier=1.5,
            minimum_bars=20,
        )

    def test_rileva_bullish_order_block(self) -> None:
        candles = create_base_candles()

        candles.iloc[-4] = {
            "open": 101.50,
            "high": 101.70,
            "low": 101.10,
            "close": 101.20,
        }

        candles.iloc[-3] = {
            "open": 101.25,
            "high": 102.40,
            "low": 101.20,
            "close": 102.20,
        }

        candles.iloc[-1] = {
            "open": 101.60,
            "high": 101.75,
            "low": 101.30,
            "close": 101.55,
        }

        result = self.analyzer.analyze(
            candles,
            direction=Direction.LONG,
        )

        self.assertTrue(result.detected)
        self.assertEqual(result.direction, Direction.LONG)
        self.assertEqual(result.upper_level, 101.70)
        self.assertEqual(result.lower_level, 101.10)
        self.assertTrue(result.mitigated)

    def test_rileva_bearish_order_block(self) -> None:
        candles = create_base_candles()

        candles.iloc[-4] = {
            "open": 102.00,
            "high": 102.40,
            "low": 101.80,
            "close": 102.30,
        }

        candles.iloc[-3] = {
            "open": 102.25,
            "high": 102.30,
            "low": 101.00,
            "close": 101.20,
        }

        candles.iloc[-1] = {
            "open": 102.10,
            "high": 102.20,
            "low": 101.90,
            "close": 102.00,
        }

        result = self.analyzer.analyze(
            candles,
            direction=Direction.SHORT,
        )

        self.assertTrue(result.detected)
        self.assertEqual(result.direction, Direction.SHORT)
        self.assertEqual(result.upper_level, 102.40)
        self.assertEqual(result.lower_level, 101.80)
        self.assertTrue(result.mitigated)

    def test_nessun_order_block_coerente(self) -> None:
        candles = create_base_candles()

        result = self.analyzer.analyze(
            candles,
            direction=Direction.LONG,
        )

        self.assertFalse(result.detected)
        self.assertEqual(result.direction, Direction.NEUTRAL)
        self.assertIsNone(result.upper_level)
        self.assertIsNone(result.lower_level)
        self.assertFalse(result.mitigated)

    def test_rifiuta_dati_insufficienti(self) -> None:
        candles = create_base_candles().iloc[:10]

        with self.assertRaises(ValueError):
            self.analyzer.analyze(
                candles,
                direction=Direction.LONG,
            )


if __name__ == "__main__":
    unittest.main()