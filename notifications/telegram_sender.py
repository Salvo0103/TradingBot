"""Invio delle notifiche Telegram del TradingBot."""

import os
from dataclasses import dataclass
from typing import Optional

import requests
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class TelegramConfig:
    """Configurazione necessaria per inviare messaggi Telegram."""

    bot_token: str
    chat_id: str

    @classmethod
    def from_environment(cls) -> "TelegramConfig":
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN non configurato nel file .env.")

        if not chat_id:
            raise ValueError("TELEGRAM_CHAT_ID non configurato nel file .env.")

        return cls(bot_token=bot_token, chat_id=chat_id)


class TelegramSender:
    """Client semplice per inviare messaggi tramite Telegram Bot API."""

    def __init__(
        self,
        config: Optional[TelegramConfig] = None,
        timeout_seconds: int = 15,
    ) -> None:
        self.config = config or TelegramConfig.from_environment()
        self.timeout_seconds = timeout_seconds
        self.base_url = (
            f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        )

    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> dict:
        """Invia un messaggio e restituisce la risposta JSON di Telegram."""

        clean_text = text.strip()

        if not clean_text:
            raise ValueError("Il messaggio Telegram non può essere vuoto.")

        payload = {
            "chat_id": self.config.chat_id,
            "text": clean_text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
            "disable_notification": disable_notification,
        }

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Errore durante l'invio del messaggio Telegram: {exc}"
            ) from exc

        response_data = response.json()

        if not response_data.get("ok"):
            raise RuntimeError(
                f"Telegram ha rifiutato il messaggio: {response_data}"
            )

        return response_data