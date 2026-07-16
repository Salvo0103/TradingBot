"""Test del Fair Value Gap Analyzer con dati simulati."""

import unittest

import pandas as pd

from analysis.fvg_analyzer import FairValueGapAnalyzer
from engine.models import Direction


class FairValueGapAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = FairValueGapAnalyzer()

    def test_rileva_bullish_fvg(self) -> None:
        candles = pd.DataFrame(
            [
                {"high": 100.0, "low": 99.0},
                {"high": 102.0, "low": 100.5},
                {"high": 103.0, "low": 101.0},
            ]
        )

        result = self.analyzer.analyze(candles)

        self.assertTrue(result.detected)
        self.assertEqual(result.direction, Direction.LONG)
        self.assertEqual(result.lower_level, 100.0)
        self.assertEqual(result.upper_level, 101.0)

    def test_rileva_bearish_fvg(self) -> None:
        candles = pd.DataFrame(
            [
                {"high": 103.0, "low": 102.0},
                {"high": 101.5, "low": 100.0},
                {"high": 101.0, "low": 99.0},
            ]
        )

        result = self.analyzer.analyze(candles)

        self.assertTrue(result.detected)
        self.assertEqual(result.direction, Direction.SHORT)
        self.assertEqual(result.upper_level, 102.0)
        self.assertEqual(result.lower_level, 101.0)

    def test_nessun_fvg(self) -> None:
        candles = pd.DataFrame(
            [
                {"high": 100.0, "low": 99.0},
                {"high": 100.5, "low": 99.5},
                {"high": 100.2, "low": 99.4},
            ]
        )

        result = self.analyzer.analyze(candles)

        self.assertFalse(result.detected)
        self.assertEqual(result.direction, Direction.NEUTRAL)
        self.assertIsNone(result.upper_level)
        self.assertIsNone(result.lower_level)

    def test_rifiuta_dati_insufficienti(self) -> None:
        candles = pd.DataFrame(
            [
                {"high": 100.0, "low": 99.0},
                {"high": 101.0, "low": 100.0},
            ]
        )

        with self.assertRaises(ValueError):
            self.analyzer.analyze(candles)


if __name__ == "__main__":
    unittest.main()