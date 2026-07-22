"""Server webhook del TradingBot per ricevere eventi da TradingView."""

import hmac
import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from engine.decision_engine import DecisionEngine
from engine.market_builder import MarketBuilder
from engine.models import Direction, MarketContext, SetupState
from engine.notification_tracker import NotificationTracker
from engine.raw_market_data import TradingViewRawPayload
from notifications.telegram_sender import TelegramSender

load_dotenv()

app = FastAPI(
    title="TradingBot Webhook",
    version="1.1.0",
)

decision_engine = DecisionEngine()
notification_tracker = NotificationTracker()
market_builder = MarketBuilder()


class TradingViewPayload(BaseModel):
    """Dati inviati dall'indicatore TradingView."""

    secret: str

    asset: str
    direction: Literal["LONG", "SHORT"]

    d1_bias: Literal["LONG", "SHORT", "NEUTRAL"]
    h4_bias: Literal["LONG", "SHORT", "NEUTRAL"]
    h1_bias: Literal["LONG", "SHORT", "NEUTRAL"]

    session_name: Literal["london", "new_york"]

    poi_reached: bool
    liquidity_sweep: bool
    bos: bool = False
    choch: bool = False

    in_premium: bool = False
    in_discount: bool = False
    order_block: bool = False
    fair_value_gap: bool = False
    imbalance: bool = False
    smt: bool = False
    engulfing: bool = False
    rejection_candle: bool = False
    retest: bool = False

    risk_reward: float = Field(ge=0)

    entry: float | None = None
    stop_loss: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None

    # Gestione del ciclo di vita del setup.
    setup_invalidated: bool = False
    invalidation_reason: str | None = None


def verify_secret(received_secret: str) -> None:
    """Verifica che il webhook provenga dalla nostra configurazione."""

    expected_secret = os.getenv("WEBHOOK_SECRET", "").strip()

    if not expected_secret:
        raise RuntimeError(
            "WEBHOOK_SECRET non configurato nel file .env."
        )

    print(f"Ricevuto: [{received_secret}]")
    print(f"Atteso:    [{expected_secret}]")

    if not hmac.compare_digest(received_secret, expected_secret):
        raise HTTPException(
            status_code=401,
            detail="Webhook secret non valido.",
        )


def format_session_name(session_name: str | None) -> str:
    """Rende leggibile il nome della sessione."""

    if not session_name:
        return "Non disponibile"

    normalized = session_name.strip().lower()

    session_labels = {
        "london": "Londra",
        "new_york": "New York",
    }

    return session_labels.get(normalized, session_name)


def format_price(asset: str, value: float | None) -> str | None:
    """Formatta i prezzi in base al tipo di strumento."""

    if value is None:
        return None

    normalized_asset = asset.upper().replace("/", "").replace("_", "")

    if "JPY" in normalized_asset:
        decimals = 3
    elif any(
        token in normalized_asset
        for token in (
            "GER40",
            "DE40",
            "DAX",
            "US30",
            "DJI",
            "NAS100",
            "USTEC",
            "SPX500",
            "US500",
            "BTC",
            "ETH",
            "XAU",
            "GOLD",
            "XAG",
            "SILVER",
        )
    ):
        decimals = 2
    else:
        decimals = 5

    return f"{value:.{decimals}f}"


def format_decision_message(
    context: MarketContext,
    decision,
) -> str:
    """Crea il report Telegram della decisione."""

    is_confirmed = decision.state == SetupState.CONFIRMED
    is_almost_ready = decision.state == SetupState.ALMOST_READY

    if is_confirmed:
        title = (
            f"🔴 <b>{context.asset} — "
            f"ENTRA {context.direction.value} ORA</b>"
        )
    elif is_almost_ready:
        title = f"🟠 <b>{context.asset} — QUASI PRONTA</b>"
    else:
        title = f"🔵 <b>{context.asset} — NESSUN INGRESSO</b>"

    lines = [
        title,
        "",
        f"<b>Qualità:</b> {decision.score:.1f}/100",
        f"<b>Direzione:</b> {context.direction.value}",
        f"<b>Sessione:</b> {format_session_name(context.session_name)}",
    ]

    # I livelli operativi vengono mostrati solo quando il setup è confermato.
    if is_confirmed:
        if decision.risk_reward is not None:
            lines.append(
                f"<b>Rischio/Rendimento:</b> "
                f"1:{decision.risk_reward:.2f}"
            )

        formatted_entry = format_price(context.asset, decision.entry)
        formatted_stop_loss = format_price(
            context.asset,
            decision.stop_loss,
        )
        formatted_take_profit_1 = format_price(
            context.asset,
            decision.take_profit_1,
        )
        formatted_take_profit_2 = format_price(
            context.asset,
            decision.take_profit_2,
        )

        if formatted_entry is not None:
            lines.append(f"<b>Entry:</b> {formatted_entry}")

        if formatted_stop_loss is not None:
            lines.append(
                f"<b>Stop Loss:</b> {formatted_stop_loss}"
            )

        if formatted_take_profit_1 is not None:
            lines.append(
                f"<b>TP1:</b> {formatted_take_profit_1}"
            )

        if formatted_take_profit_2 is not None:
            lines.append(
                f"<b>TP2:</b> {formatted_take_profit_2}"
            )

    if decision.reasons:
        lines.extend(["", "<b>Motivazione:</b>"])
        lines.extend(
            f"✅ {reason}"
            for reason in decision.reasons
        )

    if decision.optional_confirmations:
        lines.extend(["", "<b>Conferme aggiuntive:</b>"])
        lines.extend(
            f"➕ {confirmation}"
            for confirmation in decision.optional_confirmations
        )

    if decision.missing_elements:
        heading = (
            "<b>Cosa manca:</b>"
            if is_almost_ready
            else "<b>Elementi mancanti:</b>"
        )

        lines.extend(["", heading])
        lines.extend(
            f"⏳ {element}"
            for element in decision.missing_elements
        )

    return "\n".join(lines)


def format_invalidation_message(
    asset: str,
    direction: str,
    reason: str | None,
) -> str:
    """Crea il messaggio Telegram per un setup invalidato."""

    invalidation_reason = (
        reason.strip()
        if reason and reason.strip()
        else "Le condizioni del setup non sono più valide."
    )

    lines = [
        f"❌ <b>{asset} — SETUP INVALIDATO</b>",
        "",
        f"<b>Direzione:</b> {direction}",
        f"<b>Motivo:</b> {invalidation_reason}",
        "",
        "🔄 Il setup è stato chiuso dal tracker.",
        "Un nuovo setup sullo stesso asset potrà essere notificato.",
    ]

    return "\n".join(lines)


def send_telegram_message(message: str) -> bool:
    """
    Invia un messaggio Telegram e registra il risultato nel terminale.

    Restituisce True se l'invio non genera errori.
    """

    try:
        TelegramSender().send_message(message)
        print("Telegram: messaggio inviato senza errori.")
        return True
    except Exception as exc:
        print("Telegram: ERRORE durante l'invio.")
        print(f"Tipo errore: {type(exc).__name__}")
        print(f"Dettaglio: {exc}")
        return False


def print_decision_debug(
    context: MarketContext,
    decision,
    should_notify: bool,
    notification_sent: bool,
    duplicate_blocked: bool,
) -> None:
    """Stampa nel terminale tutti i dettagli della decisione."""

    print("\n========== DECISION ==========")
    print("Asset:", context.asset)
    print("Direzione:", context.direction.value)
    print("Sessione:", context.session_name)
    print("Stato:", decision.state.value)
    print("Punteggio:", decision.score)
    print("Setup valido:", decision.is_valid)
    print(
        "Stato notificabile:",
        decision.state
        in {
            SetupState.ALMOST_READY,
            SetupState.CONFIRMED,
        },
    )
    print("Tracker autorizza notifica:", should_notify)
    print("Notifica Telegram inviata:", notification_sent)
    print("Duplicato bloccato:", duplicate_blocked)

    if decision.risk_reward is not None:
        print("Risk/Reward:", decision.risk_reward)
    else:
        print("Risk/Reward: non disponibile")

    if decision.reasons:
        print("\nMotivazioni presenti:")

        for reason in decision.reasons:
            print(f"  + {reason}")
    else:
        print("\nMotivazioni presenti: nessuna")

    if decision.optional_confirmations:
        print("\nConferme aggiuntive:")

        for confirmation in decision.optional_confirmations:
            print(f"  + {confirmation}")
    else:
        print("\nConferme aggiuntive: nessuna")

    if decision.missing_elements:
        print("\nElementi mancanti:")

        for element in decision.missing_elements:
            print(f"  - {element}")
    else:
        print("\nElementi mancanti: nessuno")

    print("==============================\n")


def print_invalidation_debug(
    context: MarketContext,
    tracker_reset: bool,
    notification_sent: bool,
    reason: str | None,
) -> None:
    """Stampa i dettagli relativi all'invalidazione del setup."""

    invalidation_reason = (
        reason.strip()
        if reason and reason.strip()
        else "Le condizioni del setup non sono più valide."
    )

    print("\n======= INVALIDATION =======")
    print("Asset:", context.asset)
    print("Direzione:", context.direction.value)
    print("Motivo:", invalidation_reason)
    print("Tracker resettato:", tracker_reset)
    print("Notifica Telegram inviata:", notification_sent)
    print("Duplicato bloccato:", not tracker_reset)
    print("============================\n")


@app.get("/health")
def health_check() -> dict:
    """Controllo rapido per verificare che il server sia online."""

    return {
        "status": "ok",
        "service": "TradingBot",
    }


@app.post("/webhook/tradingview")
def tradingview_webhook(payload: TradingViewRawPayload) -> dict:
    """Riceve i dati grezzi da TradingView e li analizza."""

    verify_secret(payload.secret)

    context = market_builder.build_from_payload(payload)

    if payload.setup_invalidated:
        tracker_reset = notification_tracker.invalidate_setup(
            asset=context.asset,
            direction=context.direction.value,
        )

        notification_sent = False

        if tracker_reset:
            message = format_invalidation_message(
                asset=context.asset,
                direction=context.direction.value,
                reason=payload.invalidation_reason,
            )

            notification_sent = send_telegram_message(message)
        else:
            print(
                "Telegram: invalidazione non inviata perché "
                "il setup era già stato chiuso."
            )

        print_invalidation_debug(
            context=context,
            tracker_reset=tracker_reset,
            notification_sent=notification_sent,
            reason=payload.invalidation_reason,
        )

        return {
            "ok": True,
            "asset": context.asset,
            "direction": context.direction.value,
            "d1_bias": context.d1_bias.value,
            "h4_bias": context.h4_bias.value,
            "h1_bias": context.h1_bias.value,
            "state": SetupState.INVALIDATED.value,
            "score": 0.0,
            "notification_sent": notification_sent,
            "duplicate_blocked": not tracker_reset,
            "tracker_reset": tracker_reset,
        }

    decision = decision_engine.evaluate(context)

    notifiable_states = {
        SetupState.ALMOST_READY,
        SetupState.CONFIRMED,
    }

    notification_sent = False
    duplicate_blocked = False
    should_notify = False

    if decision.state in notifiable_states:
        should_notify = notification_tracker.should_notify(
            asset=context.asset,
            direction=context.direction.value,
            state=decision.state,
        )

        if should_notify:
            message = format_decision_message(
                context=context,
                decision=decision,
            )

            notification_sent = send_telegram_message(message)
        else:
            duplicate_blocked = True

            print(
                "Telegram: notifica bloccata dal tracker "
                "perché già inviata."
            )
    else:
        print(
            "Telegram: nessun invio perché lo stato "
            f"{decision.state.value} non è notificabile."
        )

    print_decision_debug(
        context=context,
        decision=decision,
        should_notify=should_notify,
        notification_sent=notification_sent,
        duplicate_blocked=duplicate_blocked,
    )

    return {
        "ok": True,
        "asset": decision.asset,
        "direction": context.direction.value,
        "d1_bias": context.d1_bias.value,
        "h4_bias": context.h4_bias.value,
        "h1_bias": context.h1_bias.value,
        "state": decision.state.value,
        "score": decision.score,
        "notification_sent": notification_sent,
        "duplicate_blocked": duplicate_blocked,
        "tracker_reset": False,
    }