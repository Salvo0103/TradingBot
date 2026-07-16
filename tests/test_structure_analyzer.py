"""Test dello Structure Analyzer con dati simulati."""

import unittest

import pandas as pd

from analysis.structure_analyzer import StructureAnalyzer
from engine.models import Direction


def create_structure_candles() -> pd.DataFrame:
    """Crea una sequenza con swing high e swing low ben riconoscibili."""

    closes = [
        100.0,
        101.0,
        102.0,
        101.2,
        100.6,
        101.4,
        102.6,
        103.4,
        102.5,
        101.8,
        102.7,
        104.0,
        105.0,
        104.1,
        103.3,
        104.2,
        105.4,
        106.2,
        105.2,
        104.4,
        105.3,
        106.6,
        107.4,
        106.3,
        105.5,
        106.4,
        107.6,
        108.3,
        107.2,
        106.4,
        107.2,
        108.6,
        109.4,
        108.3,
        107.5,
    ]

    rows = []

    for close in closes:
        rows.append(
            {
                "high": close + 0.30,
                "low": close - 0.30,
                "close": close,
            }
        )

    return pd.DataFrame(rows)


class StructureAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = StructureAnalyzer(
            swing_window=1,
            minimum_bars=30,
        )

    def test_rileva_bos_rialzista(self) -> None:
        candles = create_structure_candles()

        baseline = self.analyzer.analyze(
            candles,
            previous_direction=Direction.LONG,
        )

        self.assertIsNotNone(baseline.last_swing_high)

        new_row = {
            "high": baseline.last_swing_high + 1.0,
            "low": baseline.last_swing_high - 0.2,
            "close": baseline.last_swing_high + 0.6,
        }

        candles = pd.concat(
            [candles, pd.DataFrame([new_row])],
            ignore_index=True,
        )

        result = self.analyzer.analyze(
            candles,
            previous_direction=Direction.LONG,
        )

        self.assertTrue(result.bos)
        self.assertFalse(result.choch)
        self.assertEqual(result.current_direction, Direction.LONG)
        self.assertAlmostEqual(
            result.broken_level,
            result.last_swing_high,
        )

    def test_rileva_choch_ribassista(self) -> None:
        candles = create_structure_candles()

        baseline = self.analyzer.analyze(
            candles,
            previous_direction=Direction.LONG,
        )

        self.assertIsNotNone(baseline.last_swing_low)

        new_row = {
            "high": baseline.last_swing_low + 0.2,
            "low": baseline.last_swing_low - 1.0,
            "close": baseline.last_swing_low - 0.6,
        }

        candles = pd.concat(
            [candles, pd.DataFrame([new_row])],
            ignore_index=True,
        )

        result = self.analyzer.analyze(
            candles,
            previous_direction=Direction.LONG,
        )

        self.assertFalse(result.bos)
        self.assertTrue(result.choch)
        self.assertEqual(result.current_direction, Direction.SHORT)
        self.assertAlmostEqual(
            result.broken_level,
            result.last_swing_low,
        )

    def test_struttura_senza_rottura(self) -> None:
        candles = create_structure_candles()

        result = self.analyzer.analyze(
            candles,
            previous_direction=Direction.LONG,
        )

        self.assertFalse(result.bos)
        self.assertFalse(result.choch)
        self.assertIsNone(result.broken_level)

    def test_rifiuta_dati_insufficienti(self) -> None:
        candles = create_structure_candles().iloc[:10]

        with self.assertRaises(ValueError):
            self.analyzer.analyze(candles)


if __name__ == "__main__":
    unittest.main()