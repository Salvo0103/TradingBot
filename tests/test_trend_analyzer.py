"""Test del Trend Analyzer con dati simulati."""

import unittest

import numpy as np
import pandas as pd

from analysis.trend_analyzer import TrendAnalyzer
from engine.models import Direction


def create_candles(
    start: float,
    end: float,
    bars: int = 100,
    oscillation: float = 0.4,
) -> pd.DataFrame:
    """Crea candele simulate con una direzione controllata."""

    base = np.linspace(start, end, bars)
    wave = np.sin(np.linspace(0, 8 * np.pi, bars)) * oscillation
    close = base + wave

    return pd.DataFrame(
        {
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
        }
    )


class TrendAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = TrendAnalyzer()

    def test_identifica_trend_rialzista(self) -> None:
        candles = create_candles(100, 120)

        result = self.analyzer.analyze(candles)

        self.assertEqual(result.direction, Direction.LONG)
        self.assertGreaterEqual(result.confidence, 60)

    def test_identifica_trend_ribassista(self) -> None:
        candles = create_candles(120, 100)

        result = self.analyzer.analyze(candles)

        self.assertEqual(result.direction, Direction.SHORT)
        self.assertGreaterEqual(result.confidence, 60)

    def test_rifiuta_dati_insufficienti(self) -> None:
        candles = create_candles(100, 102, bars=20)

        with self.assertRaises(ValueError):
            self.analyzer.analyze(candles)


if __name__ == "__main__":
    unittest.main()