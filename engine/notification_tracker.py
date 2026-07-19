"""Gestione degli stati già notificati per evitare messaggi duplicati."""

import os
import sqlite3
from pathlib import Path

from engine.models import SetupState


class NotificationTracker:
    """Salva l'ultimo stato notificato per ogni asset e direzione."""

    def __init__(self, database_path: str = "data/notifications.db") -> None:
        self.database_path = database_path

        Path(database_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._create_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _create_table(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_states (
                    setup_key TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def should_notify(
        self,
        asset: str,
        direction: str,
        state: SetupState,
    ) -> bool:
        """
        Restituisce True quando la notifica deve essere inviata.

        In TEST_MODE=true permette anche notifiche duplicate.
        In TEST_MODE=false mantiene il normale blocco duplicati.
        """

        if self._test_mode_enabled():
            return True

        setup_key = self._build_key(asset, direction)

        previous_state = self.get_last_state(
            asset=asset,
            direction=direction,
        )

        if previous_state == state.value:
            return False

        self._save_state(
            setup_key=setup_key,
            state=state,
        )

        return True

    def invalidate_setup(
        self,
        asset: str,
        direction: str,
    ) -> bool:
        """
        Invalida un setup attivo.

        In TEST_MODE=true permette di testare anche invalidazioni ripetute.
        In produzione invalida soltanto setup ALMOST_READY o CONFIRMED.
        """

        if self._test_mode_enabled():
            self._save_state(
                setup_key=self._build_key(asset, direction),
                state=SetupState.INVALIDATED,
            )
            return True

        previous_state = self.get_last_state(
            asset=asset,
            direction=direction,
        )

        active_states = {
            SetupState.ALMOST_READY.value,
            SetupState.CONFIRMED.value,
        }

        if previous_state not in active_states:
            return False

        self._save_state(
            setup_key=self._build_key(asset, direction),
            state=SetupState.INVALIDATED,
        )

        return True

    def get_last_state(
        self,
        asset: str,
        direction: str,
    ) -> str | None:
        setup_key = self._build_key(asset, direction)

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT state
                FROM notification_states
                WHERE setup_key = ?
                """,
                (setup_key,),
            ).fetchone()

        if row is None:
            return None

        return str(row[0])

    def reset_setup(
        self,
        asset: str,
        direction: str,
    ) -> None:
        """Elimina completamente lo stato salvato di un setup."""

        setup_key = self._build_key(asset, direction)

        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM notification_states
                WHERE setup_key = ?
                """,
                (setup_key,),
            )

    def _save_state(
        self,
        setup_key: str,
        state: SetupState,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO notification_states (
                    setup_key,
                    state,
                    updated_at
                )
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(setup_key)
                DO UPDATE SET
                    state = excluded.state,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (setup_key, state.value),
            )

    @staticmethod
    def _build_key(asset: str, direction: str) -> str:
        return f"{asset.upper()}:{direction.upper()}"

    @staticmethod
    def _test_mode_enabled() -> bool:
        value = os.getenv("TEST_MODE", "false").strip().lower()

        return value in {
            "1",
            "true",
            "yes",
            "on",
        }