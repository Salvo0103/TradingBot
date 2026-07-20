"""Memoria temporanea degli eventi strutturali del TradingBot."""

import sqlite3
from pathlib import Path


class SetupMemory:
    """Memorizza sweep e direzione per le successive conferme strutturali."""

    def __init__(self, database_path: str = "data/setup_memory.db") -> None:
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
                CREATE TABLE IF NOT EXISTS setup_memory (
                    setup_key TEXT PRIMARY KEY,
                    sweep_detected INTEGER NOT NULL DEFAULT 0,
                    sweep_timestamp INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def register_sweep(
        self,
        asset: str,
        direction: str,
        timestamp: int,
    ) -> None:
        """Salva uno sweep valido."""

        setup_key = self._build_key(asset, direction)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO setup_memory (
                    setup_key,
                    sweep_detected,
                    sweep_timestamp,
                    updated_at
                )
                VALUES (?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(setup_key)
                DO UPDATE SET
                    sweep_detected = 1,
                    sweep_timestamp = excluded.sweep_timestamp,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    setup_key,
                    timestamp,
                ),
            )

    def has_recent_sweep(
        self,
        asset: str,
        direction: str,
        current_timestamp: int,
        maximum_age_ms: int = 3_600_000,
    ) -> bool:
        """Controlla se esiste uno sweep valido nell’ultima ora."""

        setup_key = self._build_key(asset, direction)

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT sweep_detected, sweep_timestamp
                FROM setup_memory
                WHERE setup_key = ?
                """,
                (setup_key,),
            ).fetchone()

        if row is None:
            return False

        sweep_detected = bool(row[0])
        sweep_timestamp = row[1]

        if not sweep_detected or sweep_timestamp is None:
            return False

        age = current_timestamp - int(sweep_timestamp)

        return 0 <= age <= maximum_age_ms

    def reset(
        self,
        asset: str,
        direction: str,
    ) -> None:
        """Cancella gli eventi memorizzati del setup."""

        setup_key = self._build_key(asset, direction)

        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM setup_memory
                WHERE setup_key = ?
                """,
                (setup_key,),
            )

    @staticmethod
    def _build_key(asset: str, direction: str) -> str:
        return f"{asset.upper()}:{direction.upper()}"