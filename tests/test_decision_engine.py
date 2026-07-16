"""Test del Decision Engine con scenari di mercato simulati."""

import unittest

from engine.decision_engine import DecisionEngine
from engine.models import Direction, MarketContext, SetupState


class DecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DecisionEngine()

    def test_operazione_confermata_senza_engulfing(self) -> None:
        """Engulfing e retest non devono essere obbligatori."""

        context = MarketContext(
            asset="GER40",
            direction=Direction.SHORT,
            h4_bias=Direction.SHORT,
            h1_bias=Direction.SHORT,
            in_premium=True,
            poi_reached=True,
            liquidity_sweep=True,
            choch=True,
            order_block=True,
            engulfing=False,
            retest=False,
            session_name="london",
            risk_reward=3.2,
            entry=25149,
            stop_loss=25168,
            take_profit_1=25095,
            take_profit_2=25052,
        )

        decision = self.engine.evaluate(context)

        self.assertEqual(decision.state, SetupState.CONFIRMED)
        self.assertTrue(decision.is_valid)
        self.assertGreaterEqual(decision.score, 90)
        self.assertEqual(decision.missing_elements, [])

    def test_quasi_pronta_quando_manca_solo_choch_o_bos(self) -> None:
        """Invia il preallarme quando manca solo la conferma strutturale."""

        context = MarketContext(
            asset="GBPUSD",
            direction=Direction.LONG,
            h4_bias=Direction.LONG,
            h1_bias=Direction.LONG,
            in_discount=True,
            poi_reached=True,
            liquidity_sweep=True,
            bos=False,
            choch=False,
            order_block=True,
            session_name="new_york",
            risk_reward=3.0,
        )

        decision = self.engine.evaluate(context)

        self.assertEqual(decision.state, SetupState.ALMOST_READY)
        self.assertFalse(decision.is_valid)
        self.assertIn("BOS oppure CHoCH", decision.missing_elements)

    def test_nessun_segnale_con_bias_htf_contrario(self) -> None:
        """Un contesto contrario al bias HTF non deve produrre segnali."""

        context = MarketContext(
            asset="EURUSD",
            direction=Direction.LONG,
            h4_bias=Direction.SHORT,
            h1_bias=Direction.SHORT,
            poi_reached=True,
            liquidity_sweep=True,
            choch=True,
            session_name="london",
            risk_reward=3.5,
        )

        decision = self.engine.evaluate(context)

        self.assertEqual(decision.state, SetupState.MONITORING)
        self.assertFalse(decision.is_valid)
        self.assertIn("Contesto HTF coerente", decision.missing_elements)

    def test_nessun_segnale_fuori_sessione(self) -> None:
        """Un setup completo fuori Londra/NY non deve generare un ingresso."""

        context = MarketContext(
            asset="XAUUSD",
            direction=Direction.LONG,
            h4_bias=Direction.LONG,
            h1_bias=Direction.LONG,
            poi_reached=True,
            liquidity_sweep=True,
            bos=True,
            session_name=None,
            risk_reward=4.0,
        )

        decision = self.engine.evaluate(context)

        self.assertEqual(decision.state, SetupState.MONITORING)
        self.assertFalse(decision.is_valid)
        self.assertIn(
            "Sessione Londra o New York",
            decision.missing_elements,
        )


if __name__ == "__main__":
    unittest.main()