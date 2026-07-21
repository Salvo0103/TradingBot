"""Gestione degli stati già notificati per evitare messaggi duplicati."""

import os
import sqlite3
from pathlib import Path

from engine.models import SetupState


class NotificationTracker:
    """Salva l'ultimo stato notificato per ogni asset e direzione."""

    STATE_PRIORITY = {
        SetupState.MONITORING.value: 0,
        SetupState.ALMOST_READY.value: 1,
        SetupState.CONFIRMED.value: 2,
        SetupState.INVALIDATED.value: 3,
    }

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

        Transizioni consentite:
        MONITORING -> ALMOST_READY -> CONFIRMED -> INVALIDATED

        Non permette mai di tornare a uno stato precedente.

        In TEST_MODE=true consente notifiche duplicate dello stesso stato,
        ma continua a bloccare le transizioni all'indietro.
        """

        setup_key = self._build_key(asset, direction)

        previous_state = self.get_last_state(
            asset=asset,
            direction=direction,
        )

        if previous_state is None:
            self._save_state(
                setup_key=setup_key,
                state=state,
            )
            return True

        if previous_state == SetupState.INVALIDATED.value:
            return False

        if self._is_backward_transition(
            previous_state=previous_state,
            new_state=state.value,
        ):
            return False

        if previous_state == state.value:
            return self._test_mode_enabled()

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

        In TEST_MODE=true permette di testare invalidazioni ripetute.
        In produzione invalida soltanto setup ALMOST_READY o CONFIRMED.
        """

        setup_key = self._build_key(asset, direction)

        previous_state = self.get_last_state(
            asset=asset,
            direction=direction,
        )

        if self._test_mode_enabled():
            self._save_state(
                setup_key=setup_key,
                state=SetupState.INVALIDATED,
            )
            return True

        active_states = {
            SetupState.ALMOST_READY.value,
            SetupState.CONFIRMED.value,
        }

        if previous_state not in active_states:
            return False

        self._save_state(
            setup_key=setup_key,
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

    def _is_backward_transition(
        self,
        previous_state: str,
        new_state: str,
    ) -> bool:
        """
        Controlla se il nuovo stato è precedente rispetto a quello salvato.

        Esempi bloccati:
        CONFIRMED -> ALMOST_READY
        CONFIRMED -> MONITORING
        ALMOST_READY -> MONITORING
        """

        previous_priority = self.STATE_PRIORITY.get(previous_state)
        new_priority = self.STATE_PRIORITY.get(new_state)

        if previous_priority is None or new_priority is None:
            return False

        return new_priority < previous_priority

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