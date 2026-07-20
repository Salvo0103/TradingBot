"""Motore decisionale del TradingBot v1.0."""

from engine.models import (
    Direction,
    MarketContext,
    SetupDecision,
    SetupState,
)

MIN_RISK_REWARD = 2.0
CONFIRMED_MIN_SCORE = 80.0
VALID_SESSIONS = {"london", "new_york"}


class DecisionEngine:
    """Valuta il contesto e produce una decisione operativa."""

    def evaluate(self, context: MarketContext) -> SetupDecision:
        reasons: list[str] = []
        missing: list[str] = []
        optional: list[str] = []

        score = self._calculate_score(
            context=context,
            reasons=reasons,
            optional=optional,
        )

        session_valid = (
            context.session_name is not None
            and context.session_name.lower() in VALID_SESSIONS
        )

        risk_reward_valid = (
            context.risk_reward is not None
            and context.risk_reward >= MIN_RISK_REWARD
        )

        mandatory_conditions = {
            "Contesto HTF coerente": context.htf_aligned,
            "Zona tecnica raggiunta": context.poi_reached,
            "Sweep di liquidità": context.liquidity_sweep,
            "BOS oppure CHoCH": context.structure_confirmation,
            "RR minimo 1:2": risk_reward_valid,
            "Sessione Londra o New York": session_valid,
        }

        for label, condition in mandatory_conditions.items():
            if not condition:
                missing.append(label)

        all_mandatory_conditions_valid = all(
            mandatory_conditions.values()
        )

        confirmed = (
            all_mandatory_conditions_valid
            and score >= CONFIRMED_MIN_SCORE
        )

        almost_ready = (
            not confirmed
            and self._is_almost_ready(
                context=context,
                session_valid=session_valid,
                risk_reward_valid=risk_reward_valid,
            )
        )

        if confirmed:
            state = SetupState.CONFIRMED
            is_valid = True
        elif almost_ready:
            state = SetupState.ALMOST_READY
            is_valid = False
        else:
            state = SetupState.MONITORING
            is_valid = False

        return SetupDecision(
            asset=context.asset,
            direction=context.direction,
            state=state,
            score=round(score, 1),
            is_valid=is_valid,
            reasons=reasons,
            missing_elements=missing,
            optional_confirmations=optional,
            entry=context.entry,
            stop_loss=context.stop_loss,
            take_profit_1=context.take_profit_1,
            take_profit_2=context.take_profit_2,
            risk_reward=context.risk_reward,
        )

    def _calculate_score(
        self,
        context: MarketContext,
        reasons: list[str],
        optional: list[str],
    ) -> float:
        score = 0.0

        if context.htf_aligned:
            score += 25
            reasons.append("Bias e contesto HTF coerenti")

        if context.poi_reached:
            score += 15
            reasons.append("Prezzo in una zona tecnica valida")

        if context.liquidity_sweep:
            score += 20
            reasons.append("Sweep di liquidità completato")

        if context.structure_confirmation:
            score += 20

            if context.choch:
                reasons.append("CHoCH confermato")
            elif context.bos:
                reasons.append("BOS confermato")

        if context.risk_reward is not None:
            if context.risk_reward >= 3:
                score += 10
                reasons.append(
                    f"Rapporto rischio/rendimento favorevole: "
                    f"1:{context.risk_reward:.1f}"
                )
            elif context.risk_reward >= 2:
                score += 7
                reasons.append(
                    f"Rapporto rischio/rendimento valido: "
                    f"1:{context.risk_reward:.1f}"
                )

        if context.in_discount and context.direction == Direction.LONG:
            score += 3
            optional.append("Prezzo in discount")

        if context.in_premium and context.direction == Direction.SHORT:
            score += 3
            optional.append("Prezzo in premium")

        optional_checks = {
            "Order Block presente": context.order_block,
            "FVG presente": context.fair_value_gap,
            "Imbalance presente": context.imbalance,
            "SMT presente": context.smt,
            "Retest completato": context.retest,
            "Engulfing presente": context.engulfing,
            "Rejection candle presente": context.rejection_candle,
        }

        optional_points = {
            "Order Block presente": 2,
            "FVG presente": 2,
            "Imbalance presente": 1,
            "SMT presente": 2,
            "Retest completato": 2,
            "Engulfing presente": 1,
            "Rejection candle presente": 1,
        }

        for label, condition in optional_checks.items():
            if condition:
                optional.append(label)
                score += optional_points[label]

        return min(score, 100.0)

    def _is_almost_ready(
        self,
        context: MarketContext,
        session_valid: bool,
        risk_reward_valid: bool,
    ) -> bool:
        """Quasi pronta solo se manca sweep oppure conferma strutturale."""

        base_context_valid = (
            context.htf_aligned
            and context.poi_reached
            and session_valid
            and risk_reward_valid
        )

        if not base_context_valid:
            return False

        sweep_missing = not context.liquidity_sweep
        structure_missing = not context.structure_confirmation

        # Preallarme soltanto quando manca un unico elemento decisivo.
        return sweep_missing != structure_missing