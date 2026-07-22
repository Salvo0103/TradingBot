"""Costruzione del MarketContext usando gli analyzer del TradingBot."""

from dataclasses import dataclass
from datetime import datetime, time

import pandas as pd

from analysis.fvg_analyzer import FairValueGapAnalyzer
from analysis.liquidity_analyzer import LiquidityAnalyzer
from analysis.premium_discount_analyzer import PremiumDiscountAnalyzer
from analysis.structure_analyzer import StructureAnalyzer
from analysis.trend_analyzer import TrendAnalyzer
from config.settings import TIMEZONE, TRADING_SESSIONS
from engine.models import Direction, MarketContext
from engine.setup_memory import SetupMemory


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
        self.setup_memory = SetupMemory()

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
        """Analizza i DataFrame e restituisce un MarketContext completo."""

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

        active_session = self._get_active_session()

        notes = [
            f"Bias D1: {d1_trend.direction.value}",
            f"Bias H4: {h4_trend.direction.value}",
            f"Bias H1: {h1_trend.direction.value}",
            f"Direzione ponderata: {direction.value}",
            f"Zona del range: {premium_discount.zone}",
            (
                f"Sessione operativa attiva: {active_session}"
                if active_session
                else "Fuori dalle finestre operative"
            ),
        ]

        notes.extend(d1_trend.reasons)
        notes.extend(h4_trend.reasons)
        notes.extend(h1_trend.reasons)
        notes.extend(liquidity.reasons)
        notes.extend(structure.reasons)
        notes.extend(fvg.reasons)

        return MarketContext(
            asset=asset.upper(),
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
            session_name=active_session,
            risk_reward=risk_reward,
            entry=entry,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            notes=notes,
        )

    def build_from_payload(self, payload) -> MarketContext:
        """Costruisce il MarketContext dai dati grezzi di TradingView."""

        d1_bias = self._bias_from_timeframe(payload.d1)
        h4_bias = self._bias_from_timeframe(payload.h4)
        h1_bias = self._bias_from_timeframe(payload.h1)

        direction = self._calculate_weighted_direction(
            d1=d1_bias,
            h4=h4_bias,
            h1=h1_bias,
        )

        current = payload.current
        previous_2 = payload.previous_2

        bullish_sweep = (
            payload.last_swing_low is not None
            and current.low < payload.last_swing_low
            and current.close > payload.last_swing_low
        )

        bearish_sweep = (
            payload.last_swing_high is not None
            and current.high > payload.last_swing_high
            and current.close < payload.last_swing_high
        )

        current_sweep = (
            bullish_sweep
            if direction == Direction.LONG
            else bearish_sweep
            if direction == Direction.SHORT
            else False
        )

        if current_sweep and direction != Direction.NEUTRAL:
            self.setup_memory.register_sweep(
                asset=payload.asset,
                direction=direction.value,
                timestamp=payload.timestamp,
            )

        if direction != Direction.NEUTRAL:
            liquidity_sweep = self.setup_memory.has_recent_sweep(
                asset=payload.asset,
                direction=direction.value,
                current_timestamp=payload.timestamp,
            )
        else:
            liquidity_sweep = False

        bullish_structure = False
        bearish_structure = False

        if (
            payload.last_swing_high is not None
            and payload.previous_swing_high is not None
            and payload.last_swing_low is not None
            and payload.previous_swing_low is not None
        ):
            bullish_structure = (
                payload.last_swing_high > payload.previous_swing_high
                and payload.last_swing_low > payload.previous_swing_low
            )

            bearish_structure = (
                payload.last_swing_high < payload.previous_swing_high
                and payload.last_swing_low < payload.previous_swing_low
            )

        broke_swing_high = (
            payload.last_swing_high is not None
            and current.close > payload.last_swing_high
        )

        broke_swing_low = (
            payload.last_swing_low is not None
            and current.close < payload.last_swing_low
        )

        bos = False
        choch = False

        if direction == Direction.LONG and broke_swing_high:
            if bearish_structure:
                choch = True
            else:
                bos = True

        elif direction == Direction.SHORT and broke_swing_low:
            if bullish_structure:
                choch = True
            else:
                bos = True

        bullish_fvg = current.low > previous_2.high
        bearish_fvg = current.high < previous_2.low

        fair_value_gap = (
            bullish_fvg
            if direction == Direction.LONG
            else bearish_fvg
            if direction == Direction.SHORT
            else False
        )

        in_premium = False
        in_discount = False

        if (
            payload.last_swing_high is not None
            and payload.last_swing_low is not None
        ):
            midpoint = (
                payload.last_swing_high
                + payload.last_swing_low
            ) / 2

            in_premium = current.close > midpoint
            in_discount = current.close < midpoint

        poi_reached = (
            fair_value_gap
            or liquidity_sweep
            or (
                direction == Direction.LONG
                and in_discount
            )
            or (
                direction == Direction.SHORT
                and in_premium
            )
        )

        entry = current.close
        stop_loss = None
        take_profit_1 = None
        take_profit_2 = None
        risk_reward = None

        if direction == Direction.LONG:
            stop_loss = min(
                current.low,
                (
                    payload.last_swing_low
                    if payload.last_swing_low is not None
                    else current.low
                ),
            )

            risk = entry - stop_loss

            if risk > 0:
                risk_reward = 3.0
                take_profit_1 = entry + risk * 2
                take_profit_2 = entry + risk * 3

        elif direction == Direction.SHORT:
            stop_loss = max(
                current.high,
                (
                    payload.last_swing_high
                    if payload.last_swing_high is not None
                    else current.high
                ),
            )

            risk = stop_loss - entry

            if risk > 0:
                risk_reward = 3.0
                take_profit_1 = entry - risk * 2
                take_profit_2 = entry - risk * 3

        active_session = self._get_active_session()
        current_time = datetime.now(TIMEZONE)

        notes = [
            f"Bias D1: {d1_bias.value}",
            f"Bias H4: {h4_bias.value}",
            f"Bias H1: {h1_bias.value}",
            f"Direzione ponderata: {direction.value}",
            (
                "Sweep rilevato sulla candela corrente"
                if current_sweep
                else "Nessuno sweep sulla candela corrente"
            ),
            (
                "Sweep recente presente in memoria"
                if liquidity_sweep
                else "Nessuno sweep recente in memoria"
            ),
            (
                "Struttura rialzista rilevata"
                if bullish_structure
                else "Struttura rialzista non rilevata"
            ),
            (
                "Struttura ribassista rilevata"
                if bearish_structure
                else "Struttura ribassista non rilevata"
            ),
            "BOS rilevato" if bos else "BOS non rilevato",
            "CHoCH rilevato" if choch else "CHoCH non rilevato",
            f"Ora italiana del controllo: {current_time:%H:%M:%S}",
            (
                f"Sessione operativa attiva: {active_session}"
                if active_session
                else "Fuori dalle finestre operative"
            ),
        ]

        print("\n========== MARKET ==========")
        print("Asset:", payload.asset)
        print("Direction:", direction.value)
        print("Current High:", current.high)
        print("Current Low:", current.low)
        print("Current Close:", current.close)
        print("Last SH:", payload.last_swing_high)
        print("Prev SH:", payload.previous_swing_high)
        print("Last SL:", payload.last_swing_low)
        print("Prev SL:", payload.previous_swing_low)
        print("Break Swing High:", broke_swing_high)
        print("Break Swing Low:", broke_swing_low)
        print("Bullish structure:", bullish_structure)
        print("Bearish structure:", bearish_structure)
        print("BOS:", bos)
        print("CHoCH:", choch)
        print("Ora italiana:", current_time.strftime("%H:%M:%S"))
        print("Sessione ricevuta:", payload.session_name)
        print("Sessione calcolata:", active_session)
        print("============================\n")

        return MarketContext(
            asset=payload.asset.upper(),
            direction=direction,
            d1_bias=d1_bias,
            h4_bias=h4_bias,
            h1_bias=h1_bias,
            in_premium=in_premium,
            in_discount=in_discount,
            poi_reached=poi_reached,
            liquidity_sweep=liquidity_sweep,
            bos=bos,
            choch=choch,
            fair_value_gap=fair_value_gap,
            session_name=active_session,
            risk_reward=risk_reward,
            entry=entry,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            notes=notes,
        )

    @staticmethod
    def _parse_session_time(value: str) -> time:
        """Converte un orario HH:MM in un oggetto time."""

        try:
            return datetime.strptime(value, "%H:%M").time()
        except ValueError as exc:
            raise ValueError(
                f"Orario di sessione non valido: {value!r}. "
                "Usare il formato HH:MM."
            ) from exc

    @classmethod
    def _get_active_session(cls) -> str | None:
        """
        Restituisce la sessione attiva usando l'ora italiana.

        Finestre configurate:
        - London: 08:00–12:40
        - New York: 14:00–17:00

        Fuori da queste fasce restituisce None.
        """

        current_time = datetime.now(TIMEZONE).time().replace(
            tzinfo=None,
        )

        for session_name, session_config in TRADING_SESSIONS.items():
            start_time = cls._parse_session_time(
                session_config["start"],
            )
            end_time = cls._parse_session_time(
                session_config["end"],
            )

            if start_time <= current_time <= end_time:
                return session_name

        return None

    @staticmethod
    def _bias_from_timeframe(timeframe_data) -> Direction:
        """Calcola il trend usando prezzo, EMA50 ed EMA200."""

        close = timeframe_data.candle.close
        ema50 = timeframe_data.ema50
        ema200 = timeframe_data.ema200

        if ema50 is None or ema200 is None:
            return Direction.NEUTRAL

        if close > ema50 > ema200:
            return Direction.LONG

        if close < ema50 < ema200:
            return Direction.SHORT

        return Direction.NEUTRAL

    @staticmethod
    def _calculate_weighted_direction(
        d1: Direction,
        h4: Direction,
        h1: Direction,
    ) -> Direction:
        """
        Calcola il bias usando i pesi definitivi.

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