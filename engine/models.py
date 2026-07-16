"""Modelli dati principali del TradingBot."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class SetupState(str, Enum):
    MONITORING = "monitoring"
    PREPARE = "prepare"
    ALMOST_READY = "almost_ready"
    CONFIRMED = "confirmed"
    MANAGEMENT = "management"
    INVALIDATED = "invalidated"


@dataclass
class MarketContext:
    asset: str
    direction: Direction

    d1_bias: Direction = Direction.NEUTRAL
    h4_bias: Direction = Direction.NEUTRAL
    h1_bias: Direction = Direction.NEUTRAL

    in_premium: bool = False
    in_discount: bool = False
    poi_reached: bool = False

    liquidity_sweep: bool = False
    bos: bool = False
    choch: bool = False

    order_block: bool = False
    fair_value_gap: bool = False
    imbalance: bool = False
    smt: bool = False

    engulfing: bool = False
    rejection_candle: bool = False
    retest: bool = False

    session_name: Optional[str] = None
    risk_reward: Optional[float] = None

    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None

    notes: list[str] = field(default_factory=list)

    @property
    def structure_confirmation(self) -> bool:
        """Una conferma strutturale è valida con BOS oppure CHoCH."""
        return self.bos or self.choch

    @property
    def htf_aligned(self) -> bool:
        """Controlla se H4 e H1 sono coerenti con la direzione proposta."""
        if self.direction == Direction.LONG:
            return (
                self.h4_bias == Direction.LONG
                and self.h1_bias in {Direction.LONG, Direction.NEUTRAL}
            )

        if self.direction == Direction.SHORT:
            return (
                self.h4_bias == Direction.SHORT
                and self.h1_bias in {Direction.SHORT, Direction.NEUTRAL}
            )

        return False


@dataclass
class SetupDecision:
    asset: str
    direction: Direction
    state: SetupState
    score: float

    is_valid: bool
    reasons: list[str]
    missing_elements: list[str]
    optional_confirmations: list[str]

    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    risk_reward: Optional[float] = None