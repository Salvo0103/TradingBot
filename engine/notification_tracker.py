"""Gestione degli stati già notificati per evitare messaggi duplicati."""

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
        Restituisce True soltanto quando lo stato è nuovo.

        Esempio:
        QUASI PRONTA → notifica
        QUASI PRONTA di nuovo → nessuna notifica
        CONFERMATA → nuova notifica
        """

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
        """Elimina lo stato salvato quando un setup termina o viene annullato."""

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