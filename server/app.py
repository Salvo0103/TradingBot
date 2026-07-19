"""Server webhook del TradingBot per ricevere eventi da TradingView."""

import hmac
import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from engine.decision_engine import DecisionEngine
from engine.models import Direction, MarketContext, SetupState
from engine.notification_tracker import NotificationTracker
from notifications.telegram_sender import TelegramSender


load_dotenv()

app = FastAPI(
    title="TradingBot Webhook",
    version="1.1.0",
)

decision_engine = DecisionEngine()
notification_tracker = NotificationTracker()


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


def format_decision_message(
    context: MarketContext,
    decision,
) -> str:
    """Crea il report Telegram completo della decisione."""

    if decision.state == SetupState.CONFIRMED:
        title = (
            f"🔴 <b>{context.asset} — "
            f"ENTRA {context.direction.value} ORA</b>"
        )
    elif decision.state == SetupState.ALMOST_READY:
        title = f"🟠 <b>{context.asset} — QUASI PRONTA</b>"
    else:
        title = f"🔵 <b>{context.asset} — NESSUN INGRESSO</b>"

    lines = [
        title,
        "",
        f"<b>Qualità:</b> {decision.score:.1f}/100",
        f"<b>Direzione:</b> {context.direction.value}",
        f"<b>Sessione:</b> {context.session_name}",
    ]

    if decision.risk_reward is not None:
        lines.append(
            f"<b>Rischio/Rendimento:</b> "
            f"1:{decision.risk_reward:.2f}"
        )

    if decision.entry is not None:
        lines.append(f"<b>Entry:</b> {decision.entry}")

    if decision.stop_loss is not None:
        lines.append(f"<b>Stop Loss:</b> {decision.stop_loss}")

    if decision.take_profit_1 is not None:
        lines.append(f"<b>TP1:</b> {decision.take_profit_1}")

    if decision.take_profit_2 is not None:
        lines.append(f"<b>TP2:</b> {decision.take_profit_2}")

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
        lines.extend(["", "<b>Elementi mancanti:</b>"])
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


@app.get("/health")
def health_check() -> dict:
    """Controllo rapido per verificare che il server sia online."""

    return {
        "status": "ok",
        "service": "TradingBot",
    }


@app.post("/webhook/tradingview")
def tradingview_webhook(payload: TradingViewPayload) -> dict:
    """Riceve il contesto da TradingView e lo valuta."""

    verify_secret(payload.secret)

    asset = payload.asset.upper()
    direction = payload.direction.upper()

    # Se TradingView comunica l'invalidazione, chiudiamo il vecchio
    # setup prima di effettuare una nuova valutazione.
    if payload.setup_invalidated:
        invalidation_sent = notification_tracker.invalidate_setup(
            asset=asset,
            direction=direction,
        )

        if invalidation_sent:
            message = format_invalidation_message(
                asset=asset,
                direction=direction,
                reason=payload.invalidation_reason,
            )
            TelegramSender().send_message(message)

        return {
            "ok": True,
            "asset": asset,
            "direction": direction,
            "state": SetupState.INVALIDATED.value,
            "notification_sent": invalidation_sent,
            "duplicate_blocked": not invalidation_sent,
            "tracker_reset": invalidation_sent,
        }

    context = MarketContext(
        asset=asset,
        direction=Direction(payload.direction),
        d1_bias=Direction(payload.d1_bias),
        h4_bias=Direction(payload.h4_bias),
        h1_bias=Direction(payload.h1_bias),
        in_premium=payload.in_premium,
        in_discount=payload.in_discount,
        poi_reached=payload.poi_reached,
        liquidity_sweep=payload.liquidity_sweep,
        bos=payload.bos,
        choch=payload.choch,
        order_block=payload.order_block,
        fair_value_gap=payload.fair_value_gap,
        imbalance=payload.imbalance,
        smt=payload.smt,
        engulfing=payload.engulfing,
        rejection_candle=payload.rejection_candle,
        retest=payload.retest,
        session_name=payload.session_name,
        risk_reward=payload.risk_reward,
        entry=payload.entry,
        stop_loss=payload.stop_loss,
        take_profit_1=payload.take_profit_1,
        take_profit_2=payload.take_profit_2,
    )

    decision = decision_engine.evaluate(context)

    notifiable_states = {
        SetupState.ALMOST_READY,
        SetupState.CONFIRMED,
    }

    notification_sent = False
    duplicate_blocked = False

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
            TelegramSender().send_message(message)
            notification_sent = True
        else:
            duplicate_blocked = True

    return {
        "ok": True,
        "asset": decision.asset,
        "state": decision.state.value,
        "score": decision.score,
        "notification_sent": notification_sent,
        "duplicate_blocked": duplicate_blocked,
        "tracker_reset": False,
    }