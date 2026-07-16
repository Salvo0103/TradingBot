"""Test del Market Builder con dati multi-timeframe simulati."""

import unittest

import numpy as np
import pandas as pd

from engine.market_builder import MarketBuilder, MarketDataBundle
from engine.models import Direction


def create_trending_candles(
    start: float,
    end: float,
    bars: int = 100,
    include_open: bool = False,
) -> pd.DataFrame:
    """Crea candele simulate con trend controllato."""

    base = np.linspace(start, end, bars)
    wave = np.sin(np.linspace(0, 8 * np.pi, bars)) * 0.30
    close = base + wave

    data = {
        "high": close + 0.25,
        "low": close - 0.25,
        "close": close,
    }

    if include_open:
        data["open"] = close - 0.05

    return pd.DataFrame(data)


def create_m5_with_bullish_sweep_and_bos() -> pd.DataFrame:
    """Crea candele M5 con sweep dei minimi e rottura rialzista."""

    candles = create_trending_candles(
        100,
        110,
        bars=40,
        include_open=True,
    )

    previous_low = float(candles.iloc[-21:-1]["low"].min())

    candles.iloc[-2] = {
        "open": previous_low + 0.20,
        "high": previous_low + 0.45,
        "low": previous_low - 0.30,
        "close": previous_low + 0.15,
    }

    recent_high = float(candles.iloc[:-1]["high"].max())

    candles.iloc[-1] = {
        "open": recent_high - 0.20,
        "high": recent_high + 1.00,
        "low": recent_high - 0.30,
        "close": recent_high + 0.60,
    }

    return candles


def create_m15_with_bullish_fvg() -> pd.DataFrame:
    """Crea dati M15 con un bullish FVG sulle ultime tre candele."""

    candles = create_trending_candles(
        100,
        105,
        bars=60,
        include_open=True,
    )

    candles.iloc[-3] = {
        "open": 104.0,
        "high": 104.2,
        "low": 103.8,
        "close": 104.1,
    }

    candles.iloc[-2] = {
        "open": 104.3,
        "high": 105.5,
        "low": 104.3,
        "close": 105.2,
    }

    candles.iloc[-1] = {
        "open": 105.0,
        "high": 105.8,
        "low": 104.8,
        "close": 105.6,
    }

    return candles


class MarketBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = MarketBuilder()

    def test_costruisce_contesto_long_multi_timeframe(self) -> None:
        data = MarketDataBundle(
            d1=create_trending_candles(100, 120),
            h4=create_trending_candles(100, 118),
            h1=create_trending_candles(100, 115),
            m15=create_m15_with_bullish_fvg(),
            m5=create_m5_with_bullish_sweep_and_bos(),
        )

        context = self.builder.build(
            asset="GBPUSD",
            data=data,
            session_name="london",
            risk_reward=3.0,
            entry=1.3420,
            stop_loss=1.3410,
            take_profit_1=1.3440,
            take_profit_2=1.3450,
            technical_zone_reached=True,
        )

        self.assertEqual(context.asset, "GBPUSD")
        self.assertEqual(context.direction, Direction.LONG)
        self.assertEqual(context.d1_bias, Direction.LONG)
        self.assertEqual(context.h4_bias, Direction.LONG)
        self.assertEqual(context.h1_bias, Direction.LONG)
        self.assertTrue(context.poi_reached)
        self.assertEqual(context.session_name, "london")
        self.assertEqual(context.risk_reward, 3.0)

    def test_h4_pesa_piu_di_d1(self) -> None:
        direction = self.builder._calculate_weighted_direction(
            d1=Direction.SHORT,
            h4=Direction.LONG,
            h1=Direction.LONG,
        )

        self.assertEqual(direction, Direction.LONG)

    def test_parita_restituisce_neutral(self) -> None:
        direction = self.builder._calculate_weighted_direction(
            d1=Direction.NEUTRAL,
            h4=Direction.LONG,
            h1=Direction.SHORT,
        )

        self.assertEqual(direction, Direction.LONG)


if __name__ == "__main__":
    unittest.main()