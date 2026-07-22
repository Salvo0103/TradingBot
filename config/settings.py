"""Impostazioni centrali del TradingBot."""

from zoneinfo import ZoneInfo


# Fuso orario usato dal bot
TIMEZONE = ZoneInfo("Europe/Rome")


# Asset monitorati
ASSETS = [
    "XAUUSD",
    "GER40",
    "GBPUSD",
    "USDCHF",
    "EURUSD",
    "AUDUSD",
    "USDCAD",
    "EURCHF",
    "NAS100",
    "US30",
    "SP500",
]


# Timeframe utilizzati
TIMEFRAMES = {
    "bias_primary": "D1",
    "bias_operational": "H4",
    "context": "H1",
    "setup": "M15",
    "confirmation": "M5",
    "entry_refinement": "M1",
}


# Finestre operative in ora italiana
# Il bot può analizzare sempre, ma invia nuovi setup solo in queste fasce.
TRADING_SESSIONS = {
    "london": {
        "start": "08:00",
        "end": "12:40",
    },
    "new_york": {
        "start": "14:00",
        "end": "17:00",
    },
}


# Rapporto rischio/rendimento
MIN_RISK_REWARD = 2.0
PREFERRED_RISK_REWARD = 3.0


# Soglie del punteggio
SCORE_THRESHOLDS = {
    "monitoring": 70,
    "prepare": 75,
    "almost_ready": 80,
    "confirmed": 90,
}


# Pesi della checklist: totale 100 punti
CHECKLIST_WEIGHTS = {
    "htf_bias": 15,
    "h1_context": 8,
    "premium_discount": 7,
    "poi_reached": 10,
    "liquidity_sweep": 12,
    "order_block": 8,
    "fair_value_gap": 6,
    "smt": 5,
    "choch_bos": 12,
    "retest": 7,
    "confirmation_candle": 6,
    "risk_reward": 4,
}


# Elementi obbligatori per un segnale operativo confermato
MANDATORY_ENTRY_CONDITIONS = [
    "htf_bias",
    "poi_reached",
    "liquidity_sweep",
    "choch_bos",
    "retest",
    "confirmation_candle",
    "risk_reward",
]


# Stati possibili del setup
SETUP_STATES = {
    "monitoring": "🔵 MONITORAGGIO",
    "prepare": "🟡 PREPARATI",
    "almost_ready": "🟠 QUASI PRONTA",
    "confirmed": "🔴 OPERAZIONE CONFERMATA",
    "management": "⚫ GESTIONE",
    "invalidated": "❌ INVALIDATA",
}


# Impostazioni notifiche
NOTIFICATIONS = {
    "send_monitoring": False,
    "send_prepare": True,
    "send_almost_ready": True,
    "send_confirmed": True,
    "send_management": True,
    "send_invalidated": True,
    "avoid_duplicates": True,
}


# Gestione indicativa della posizione
TRADE_MANAGEMENT = {
    "move_stop_to_break_even_at_r": 1.0,
    "partial_profit_at_r": 2.0,
    "partial_profit_percentage": 50,
}


def validate_settings() -> None:
    """Controlla che la configurazione principale sia coerente."""

    total_weight = sum(CHECKLIST_WEIGHTS.values())

    if total_weight != 100:
        raise ValueError(
            f"I pesi della checklist devono totalizzare 100, "
            f"ma attualmente totalizzano {total_weight}."
        )

    if MIN_RISK_REWARD < 1:
        raise ValueError("MIN_RISK_REWARD deve essere almeno 1.")

    if PREFERRED_RISK_REWARD < MIN_RISK_REWARD:
        raise ValueError(
            "PREFERRED_RISK_REWARD non può essere inferiore a MIN_RISK_REWARD."
        )

    if not ASSETS:
        raise ValueError("La lista ASSETS non può essere vuota.")


validate_settings()