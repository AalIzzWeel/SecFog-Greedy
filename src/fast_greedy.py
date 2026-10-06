from dataclasses import dataclass
import logging
import time

from optimizer.actions import Action
from optimizer.costs import CostCalculator
from optimizer.heuristic import (
    HeuristicCandidate,
    first_feasible,
    generate_actions,
    group_requirements_by_node,
)
from optimizer.state import State
from scoring.score_wrapper import ScoreWrapper


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FastGreedyStep:
    step_number: int
    action: Action
    cost: int
    specific_quality: float
    efficiency: float
    remaining_budget: int
    downgrades: tuple[Action, ...] = ()

    @property
    def benefit(self) -> float:
        return self.specific_quality

    @property
    def downgrade(self) -> Action | None:
        return self.downgrades[0] if self.downgrades else None

    @property
    def is_reallocation(self) -> bool:
        return bool(self.downgrades)


def build_downgrade_then_upgrade_input(
    initial_state: State,
    budget: int,
    costs: CostCalculator,
) -> tuple[State, int]:
    """Porta tutte le capability a L0 e recupera il costo liberato."""
    if budget < 0:
        raise ValueError("Il budget iniziale deve essere non negativo.")

    l0_state = initial_state.copy()

    for (node, capability), _level in l0_state.items():
        available_levels = sorted(
            map(int, costs.capabilities[capability]["levels"])
        )
        if 0 not in available_levels:
            raise ValueError(
                f"La capability {capability} non dispone di L0."
            )
        l0_state.set_level(node, capability, 0)

    released = (
        costs.calculate_state_cost(initial_state)
        - costs.calculate_state_cost(l0_state)
    )
    return l0_state, budget + released


class FastGreedyOptimizer:
    """Implementazione del Gain-Based Greedy Reallocation (GUBR)."""

    # Tolleranza relativa: indipendente dalla scala dello score.
    RELATIVE_EPSILON = 1e-12

    @classmethod
    def score_improved(cls, candidate: float, current: float) -> bool:
        """Accetta solo miglioramenti superiori alla tolleranza relativa."""
        if candidate <= current:
            return False

        if current == 0:
            return candidate > 0

        tolerance = cls.RELATIVE_EPSILON * max(
            abs(candidate), abs(current)
        )
        return candidate - current > tolerance

    def __init__(
        self,
        catalog: dict,
        application: dict,
        placement: dict,
        score_wrapper: ScoreWrapper,
        allow_reversal: bool | None = None,
    ):
        self.catalog = catalog
        self.application = application
        self.placement = placement
        self.score_wrapper = score_wrapper
        self.costs = CostCalculator(catalog)

        preparation_start = time.perf_counter()
        self.grouped_requirements = group_requirements_by_node(
            application, placement, catalog
        )
        self.preparation_seconds = (
            time.perf_counter() - preparation_start
        )
        self.initial_evaluation_seconds = 0.0
        self.greedy_loop_seconds = 0.0
        self.initial_score: float | None = None

    def optimize(
        self,
        initial_state: State,
        budget: int,
    ) -> tuple[State, int, float, list[FastGreedyStep]]:
        if budget < 0:
            raise ValueError("Il budget iniziale deve essere non negativo.")

        state = initial_state.copy()
        remaining_budget = budget
        history: list[FastGreedyStep] = []
        improved_capabilities: set[tuple[str, str]] = set()

        preparation_start = time.perf_counter()
        upgrades, downgrades = generate_actions(
            initial_state, self.catalog, self.grouped_requirements
        )
        self.preparation_seconds += (
            time.perf_counter() - preparation_start
        )

        evaluation_start = time.perf_counter()
        score = self.score_wrapper.evaluate(state)
        self.initial_evaluation_seconds = (
            time.perf_counter() - evaluation_start
        )
        self.initial_score = score

        loop_start = time.perf_counter()
        step_number = 1

        while True:
            direct_applied = False

            while True:
                affordable = next(
                    (
                        (index, candidate)
                        for index, candidate in enumerate(upgrades)
                        if state.is_feasible(candidate.action)
                        and candidate.cost <= remaining_budget
                    ),
                    None,
                )

                if affordable is None:
                    break

                index, candidate = affordable
                state.apply(candidate.action)
                improved_capabilities.add(candidate.action.key)
                remaining_budget -= candidate.cost
                upgrades.pop(index)
                direct_applied = True

                history.append(
                    FastGreedyStep(
                        step_number=step_number,
                        action=candidate.action,
                        cost=candidate.cost,
                        specific_quality=candidate.specific_quality,
                        efficiency=candidate.efficiency,
                        remaining_budget=remaining_budget,
                    )
                )
                step_number += 1

            if direct_applied:
                score = self.score_wrapper.evaluate(state)

            next_upgrade = first_feasible(upgrades, state)

            if next_upgrade is None:
                self.greedy_loop_seconds = (
                    time.perf_counter() - loop_start
                )
                return state, remaining_budget, score, history

            upgrade_index, target = next_upgrade
            missing_budget = max(
                0, target.cost - remaining_budget
            )

            if missing_budget == 0:
                continue

            tentative_state = state.copy()
            tentative_budget = remaining_budget
            tentative_downgrades = list(downgrades)
            used_downgrades: list[HeuristicCandidate] = []
            freed = 0

            while freed < missing_budget:
                feasible = first_feasible(
                    tentative_downgrades,
                    tentative_state,
                    # Non declassare capability già migliorate
                    # né quella interessata dall'upgrade candidato.
                    blocked_keys=(
                        improved_capabilities | {target.action.key}
                    ),
                )

                if feasible is None:
                    self.greedy_loop_seconds = (
                        time.perf_counter() - loop_start
                    )
                    return state, remaining_budget, score, history

                downgrade_index, downgrade = feasible
                tentative_state.apply(downgrade.action)
                saving = -downgrade.cost
                freed += saving
                tentative_budget += saving
                used_downgrades.append(downgrade)
                tentative_downgrades.pop(downgrade_index)

            tentative_state.apply(target.action)
            tentative_budget -= target.cost
            tentative_score = self.score_wrapper.evaluate(
                tentative_state
            )

            if not self.score_improved(tentative_score, score):
                logger.info(
                    "Riallocazione rifiutata | "
                    "score corrente=%.16e | "
                    "score candidato=%.16e | "
                    "delta=%.16e | "
                    "tolleranza=%.16e",
                    score,
                    tentative_score,
                    tentative_score - score,
                    self.RELATIVE_EPSILON
                    * max(abs(score), abs(tentative_score)),
                )
                self.greedy_loop_seconds = (
                    time.perf_counter() - loop_start
                )
                return state, remaining_budget, score, history

            net_cost = target.cost + sum(
                item.cost for item in used_downgrades
            )
            state = tentative_state
            improved_capabilities.add(target.action.key)
            remaining_budget = tentative_budget
            score = tentative_score
            downgrades = tentative_downgrades
            upgrades.pop(upgrade_index)

            history.append(
                FastGreedyStep(
                    step_number=step_number,
                    action=target.action,
                    cost=net_cost,
                    specific_quality=(
                        target.specific_quality
                        + sum(
                            item.specific_quality
                            for item in used_downgrades
                        )
                    ),
                    efficiency=target.efficiency,
                    remaining_budget=remaining_budget,
                    downgrades=tuple(
                        item.action for item in used_downgrades
                    ),
                )
            )
            step_number += 1

            logger.info(
                "Riallocazione accettata | "
                "downgrade=%d | upgrade=%s | score=%.16e",
                len(used_downgrades),
                target.action,
                score,
            )