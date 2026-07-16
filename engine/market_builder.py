"""Costruzione del MarketContext usando gli analyzer del TradingBot."""

from dataclasses import dataclass

import pandas as pd

from analysis.fvg_analyzer import FairValueGapAnalyzer
from analysis.liquidity_analyzer import LiquidityAnalyzer
from analysis.premium_discount_analyzer import PremiumDiscountAnalyzer
from analysis.structure_analyzer import StructureAnalyzer
from analysis.trend_analyzer import TrendAnalyzer
from engine.models import Direction, MarketContext


@dataclass(frozen=True)
class MarketDataBundle:
    """Dati multi-timeframe necessari per analizzare un asset."""

    d1: pd.DataFrame
    h4: pd.DataFrame
    h1: pd.DataFrame
    m15: pd.DataFrame
    m5: pd.DataFrame


class MarketBuilder:
    """Unisce tutti gli analyzer e costruisce il contesto operativo."""

    def __init__(self) -> None:
        self.trend_analyzer = TrendAnalyzer()
        self.liquidity_analyzer = LiquidityAnalyzer()
        self.structure_analyzer = StructureAnalyzer()
        self.fvg_analyzer = FairValueGapAnalyzer()
        self.premium_discount_analyzer = PremiumDiscountAnalyzer()

    def build(
        self,
        asset: str,
        data: MarketDataBundle,
        session_name: str | None,
        risk_reward: float | None,
        entry: float | None = None,
        stop_loss: float | None = None,
        take_profit_1: float | None = None,
        take_profit_2: float | None = None,
        technical_zone_reached: bool = False,
    ) -> MarketContext:
        """Analizza i timeframe e restituisce un MarketContext completo."""

        d1_trend = self.trend_analyzer.analyze(data.d1)
        h4_trend = self.trend_analyzer.analyze(data.h4)
        h1_trend = self.trend_analyzer.analyze(data.h1)

        direction = self._calculate_weighted_direction(
            d1=d1_trend.direction,
            h4=h4_trend.direction,
            h1=h1_trend.direction,
        )

        premium_discount = self.premium_discount_analyzer.analyze(
            data.h1,
            direction=direction,
        )

        liquidity = self.liquidity_analyzer.analyze(data.m5)

        structure = self.structure_analyzer.analyze(
            data.m5,
            previous_direction=h1_trend.direction,
        )

        fvg = self.fvg_analyzer.analyze(data.m15)

        direction_consistent_sweep = (
            liquidity.detected
            and liquidity.direction == direction
        )

        direction_consistent_structure = (
            structure.current_direction == direction
        )

        direction_consistent_fvg = (
            fvg.detected
            and fvg.direction == direction
        )

        poi_reached = (
            technical_zone_reached
            or direction_consistent_fvg
        )

        notes = [
            f"Bias D1: {d1_trend.direction.value}",
            f"Bias H4: {h4_trend.direction.value}",
            f"Bias H1: {h1_trend.direction.value}",
            f"Direzione ponderata: {direction.value}",
            f"Zona del range: {premium_discount.zone}",
        ]

        notes.extend(d1_trend.reasons)
        notes.extend(h4_trend.reasons)
        notes.extend(h1_trend.reasons)
        notes.extend(liquidity.reasons)
        notes.extend(structure.reasons)
        notes.extend(fvg.reasons)

        return MarketContext(
            asset=asset,
            direction=direction,
            d1_bias=d1_trend.direction,
            h4_bias=h4_trend.direction,
            h1_bias=h1_trend.direction,
            in_premium=premium_discount.in_premium,
            in_discount=premium_discount.in_discount,
            poi_reached=poi_reached,
            liquidity_sweep=direction_consistent_sweep,
            bos=structure.bos and direction_consistent_structure,
            choch=structure.choch and direction_consistent_structure,
            fair_value_gap=direction_consistent_fvg,
            session_name=session_name,
            risk_reward=risk_reward,
            entry=entry,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            notes=notes,
        )

    @staticmethod
    def _calculate_weighted_direction(
        d1: Direction,
        h4: Direction,
        h1: Direction,
    ) -> Direction:
        """
        Calcola il bias usando i pesi definitivi:

        D1 = 20%
        H4 = 50%
        H1 = 30%
        """

        scores = {
            Direction.LONG: 0,
            Direction.SHORT: 0,
        }

        weights = [
            (d1, 20),
            (h4, 50),
            (h1, 30),
        ]

        for direction, weight in weights:
            if direction in scores:
                scores[direction] += weight

        long_score = scores[Direction.LONG]
        short_score = scores[Direction.SHORT]

        if long_score == short_score:
            return Direction.NEUTRAL

        if long_score > short_score:
            return Direction.LONG

        return Direction.SHORT