from dataclasses import dataclass
import logging

from optimizer.actions import Action
from optimizer.costs import CostCalculator
from optimizer.heuristic import (
    HeuristicCandidate,
    build_capability_levels,
    build_relevant_capabilities,
    find_best_improvement_action,
    find_best_reallocation_action,
    generate_downgrade_actions,
    group_requirements_by_node,
    rank_nodes,
    select_better_candidate,
)
from optimizer.state import State
from scoring.score_wrapper import ScoreWrapper


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FastGreedyStep:
    """Rappresenta una scelta eseguita dal greedy veloce."""

    step_number: int
    action: Action
    cost: int
    benefit: float
    efficiency: float
    node_priority: float
    remaining_budget: int
    downgrade: Action | None = None

    @property
    def is_reallocation(self) -> bool:
        return self.downgrade is not None


class FastGreedyOptimizer:
    """
    Greedy euristico per l'ottimizzazione delle security capability.

    Usa SecFog soltanto per valutare lo stato iniziale e quello finale;
    le decisioni intermedie sono guidate dall'euristica sui security
    requirements dell'applicazione.
    """

    EPSILON = 1e-12

    def __init__(
        self,
        catalog: dict,
        application: dict,
        placement: dict,
        score_wrapper: ScoreWrapper,
        allow_reversal: bool = True,
    ):
        self.catalog = catalog
        self.application = application
        self.placement = placement
        self.score_wrapper = score_wrapper
        self.allow_reversal = allow_reversal
        self.costs = CostCalculator(catalog)

        self.grouped_requirements = group_requirements_by_node(
            application,
            placement,
            catalog,
        )

        self.relevant_capabilities_by_node = build_relevant_capabilities(
            self.grouped_requirements
        )

        self.levels_by_capability = build_capability_levels(catalog)
        self.initial_score: float | None = None

    def optimize(
        self,
        initial_state: State,
        budget: int,
    ) -> tuple[State, int, float, list[FastGreedyStep]]:
        """Esegue il greedy veloce sul placement fisso."""
        if budget < 0:
            raise ValueError(
                "Il budget iniziale deve essere non negativo."
            )

        current_state = initial_state.copy()
        remaining_budget = budget
        history: list[FastGreedyStep] = []

        downgraded_capabilities: set[tuple[str, str]] = set()
        improved_capabilities: set[tuple[str, str]] = set()

        self.initial_score = self.score_wrapper.evaluate(current_state)
        step_number = 1

        while True:
            selected: tuple[float, HeuristicCandidate] | None = None

            ranked_nodes = rank_nodes(
                self.grouped_requirements,
                current_state,
                self.catalog,
            )

            # Riutilizziamo le priorità già calcolate dal ranking
            # durante tutte le riallocazioni della stessa iterazione.
            current_priorities = dict(ranked_nodes)

            blocked_downgrade_capabilities = (
                downgraded_capabilities.copy()
            )

            if not self.allow_reversal:
                blocked_downgrade_capabilities.update(
                    improved_capabilities
                )

            downgrade_actions = generate_downgrade_actions(
                current_state,
                self.catalog,
                self.costs,
                blocked_downgrade_capabilities,
                levels_by_capability=self.levels_by_capability,
            )

            downgrade_candidates = [
                (
                    action,
                    self.costs.calculate_action_cost(action),
                )
                for action in downgrade_actions
            ]

            for node, node_priority in ranked_nodes:
                direct = find_best_improvement_action(
                    node,
                    self.grouped_requirements[node],
                    current_state,
                    self.catalog,
                    remaining_budget,
                    costs=self.costs,
                    relevant_capabilities=(
                        self.relevant_capabilities_by_node[node]
                    ),
                    levels_by_capability=self.levels_by_capability,
                )

                reallocation = find_best_reallocation_action(
                    node=node,
                    requirements=self.grouped_requirements[node],
                    grouped_requirements=self.grouped_requirements,
                    state=current_state,
                    catalog=self.catalog,
                    available_budget=remaining_budget,
                    costs=self.costs,
                    downgrade_candidates=downgrade_candidates,
                    current_priorities=current_priorities,
                    relevant_capabilities=(
                        self.relevant_capabilities_by_node[node]
                    ),
                    levels_by_capability=self.levels_by_capability,
                )

                candidate = select_better_candidate(
                    direct,
                    reallocation,
                )

                if candidate is not None:
                    selected = (
                        node_priority,
                        candidate,
                    )
                    break

            if selected is None:
                break

            node_priority, candidate = selected

            if candidate.downgrade is not None:
                current_state.apply(candidate.downgrade)
                downgraded_capabilities.add(
                    candidate.downgrade.key
                )

            current_state.apply(candidate.action)
            improved_capabilities.add(candidate.action.key)
            remaining_budget -= candidate.cost

            history.append(
                FastGreedyStep(
                    step_number=step_number,
                    action=candidate.action,
                    downgrade=candidate.downgrade,
                    cost=candidate.cost,
                    benefit=candidate.benefit,
                    efficiency=candidate.efficiency,
                    node_priority=node_priority,
                    remaining_budget=remaining_budget,
                )
            )

            description = (
                f"{candidate.downgrade} + {candidate.action}"
                if candidate.downgrade is not None
                else str(candidate.action)
            )

            logger.info(
                "Step %d | %s | beneficio=%.8f | "
                "costo netto=%+d | budget=%d",
                step_number,
                description,
                candidate.benefit,
                candidate.cost,
                remaining_budget,
            )

            step_number += 1

        final_score = self.score_wrapper.evaluate(current_state)

        if final_score <= self.initial_score + self.EPSILON:
            logger.warning(
                "La configurazione euristica non migliora lo score "
                "SecFog: viene restituito lo stato iniziale."
            )

            return (
                initial_state.copy(),
                budget,
                self.initial_score,
                [],
            )

        return (
            current_state,
            remaining_budget,
            final_score,
            history,
        )
