from dataclasses import dataclass
import math

from optimizer.actions import Action
from optimizer.costs import CostCalculator
#from optimizer.profiler import profile
from optimizer.requirements import (
    evaluate_requirement,
    required_capabilities,
    validate_requirement,
)
from optimizer.state import State


@dataclass(frozen=True)
class HeuristicCandidate:
    action: Action
    cost: int
    benefit: float
    efficiency: float
    downgrade: Action | None = None

    @property
    def is_reallocation(self) -> bool:
        return self.downgrade is not None


def group_requirements_by_node(
    application: dict,
    placement: dict,
    catalog: dict,
) -> dict[str, list]:
    """Raggruppa i requisiti dei servizi in base al nodo fissato."""
    if placement.get("application") != application.get("name"):
        raise ValueError(
            "L'applicazione del placement non coincide con quella caricata."
        )

    services = application.get("services", {})
    grouped = {}

    for component in placement.get("components", []):
        service_name = component["name"]
        node = component["node"]

        if service_name not in services:
            raise ValueError(
                f"Servizio {service_name} non definito nell'applicazione."
            )

        requirement = services[service_name].get("requirements")

        if requirement is None:
            raise ValueError(
                f"Requisiti mancanti per il servizio {service_name}."
            )

        validate_requirement(requirement, catalog)
        grouped.setdefault(node, []).append(requirement)

    return grouped


def build_relevant_capabilities(
    grouped_requirements: dict[str, list],
) -> dict[str, tuple[str, ...]]:
    """Precalcola le capability richieste su ciascun nodo."""
    relevant_by_node = {}

    for node, requirements in grouped_requirements.items():
        capabilities = set()
        for requirement in requirements:
            capabilities.update(required_capabilities(requirement))
        relevant_by_node[node] = tuple(sorted(capabilities))

    return relevant_by_node


def build_capability_levels(
    catalog: dict,
) -> dict[str, tuple[int, ...]]:
    """Precalcola i livelli ordinati di ciascuna capability."""
    return {
        capability: tuple(
            sorted(int(level) for level in capability_data["levels"])
        )
        for capability, capability_data
        in catalog.get("capabilities", {}).items()
    }


# @profile("1.5 Heuristic.calculate_node_priority")
def calculate_node_priority(
    node: str,
    requirements: list,
    state: State,
    catalog: dict,
    overrides: dict[tuple[str, str], int] | None = None,
) -> float:
    """Calcola la criticità euristica di un nodo."""
    priority = 0.0

    for requirement in requirements:
        satisfaction = evaluate_requirement(
            requirement,
            node,
            state,
            catalog,
            overrides,
        )
        capability_count = len(required_capabilities(requirement))
        priority += capability_count * (1.0 - satisfaction)

    return priority


def calculate_action_benefit(
    action: Action,
    requirements: list,
    state: State,
    catalog: dict,
) -> float:
    """Stima quanto l'azione riduce la criticità del nodo."""
    old_priority = calculate_node_priority(
        action.node,
        requirements,
        state,
        catalog,
    )

    new_priority = calculate_node_priority(
        action.node,
        requirements,
        state,
        catalog,
        overrides={action.key: action.new_level},
    )

    return old_priority - new_priority


# @profile("1.6 Heuristic.calculate_reallocation_benefit")
def calculate_reallocation_benefit(
    downgrade: Action,
    improvement: Action,
    grouped_requirements: dict[str, list],
    state: State,
    catalog: dict,
    current_priorities: dict[str, float] | None = None,
) -> float:
    """Calcola il beneficio sui soli nodi modificati."""
    if downgrade.key == improvement.key:
        raise ValueError(
            "Downgrade e miglioramento devono riguardare capability differenti."
        )

    affected_nodes = {downgrade.node, improvement.node}

    if current_priorities is None:
        current_priorities = {
            node: calculate_node_priority(
                node,
                grouped_requirements[node],
                state,
                catalog,
            )
            for node in affected_nodes
        }

    old_priority = sum(
        current_priorities[node]
        for node in affected_nodes
    )

    overrides = {
        downgrade.key: downgrade.new_level,
        improvement.key: improvement.new_level,
    }

    new_priority = sum(
        calculate_node_priority(
            node,
            grouped_requirements[node],
            state,
            catalog,
            overrides,
        )
        for node in affected_nodes
    )

    return old_priority - new_priority


#@profile("1. Heuristic.rank_nodes")
def rank_nodes(
    grouped_requirements: dict[str, list],
    state: State,
    catalog: dict,
) -> list[tuple[str, float]]:
    """Ordina i nodi dal più critico al meno critico."""
    ranked = [
        (
            node,
            calculate_node_priority(
                node,
                requirements,
                state,
                catalog,
            ),
        )
        for node, requirements in grouped_requirements.items()
    ]

    return sorted(ranked, key=lambda item: (-item[1], item[0]))


#@profile("1.1 Heuristic.generate_improvement_actions")
def generate_improvement_actions(
    node: str,
    requirements: list,
    state: State,
    catalog: dict,
    relevant_capabilities: tuple[str, ...] | None = None,
    levels_by_capability: dict[str, tuple[int, ...]] | None = None,
) -> list[Action]:
    """Genera le ADD e gli upgrade rilevanti per un nodo."""
    if relevant_capabilities is None:
        relevant = set()
        for requirement in requirements:
            relevant.update(required_capabilities(requirement))
        relevant_capabilities = tuple(sorted(relevant))

    actions = []
    allow_add = catalog.get("actions", {}).get("allow_add", True)
    allow_modify = catalog.get("actions", {}).get("allow_modify", True)

    for capability in relevant_capabilities:
        key = (node, capability)
        if key not in state:
            continue

        current_level = state.get_level(node, capability)

        if levels_by_capability is None:
            levels = tuple(
                sorted(
                    int(level)
                    for level in catalog["capabilities"][capability]["levels"]
                )
            )
        else:
            levels = levels_by_capability[capability]

        for new_level in levels:
            if current_level is None:
                if allow_add:
                    actions.append(Action.add(node, capability, new_level))
            elif allow_modify and new_level > current_level:
                actions.append(
                    Action.modify(
                        node,
                        capability,
                        current_level,
                        new_level,
                    )
                )

    return actions


#@profile("1.2 Heuristic.generate_downgrade_actions")
def generate_downgrade_actions(
    state: State,
    catalog: dict,
    costs: CostCalculator,
    downgraded_capabilities: set[tuple[str, str]],
    levels_by_capability: dict[str, tuple[int, ...]] | None = None,
) -> list[Action]:
    """Genera soltanto i downgrade che liberano budget."""
    allow_modify = catalog.get("actions", {}).get("allow_modify", True)
    if not allow_modify:
        return []

    actions = []

    for (node, capability), current_level in sorted(state.items()):
        if current_level is None:
            continue

        key = (node, capability)
        if key in downgraded_capabilities:
            continue

        current_cost = costs.get_capability_cost(capability, current_level)

        if levels_by_capability is None:
            levels = tuple(
                sorted(
                    int(level)
                    for level in catalog["capabilities"][capability]["levels"]
                )
            )
        else:
            levels = levels_by_capability[capability]

        for new_level in levels:
            if new_level >= current_level:
                continue

            new_cost = costs.get_capability_cost(capability, new_level)
            if new_cost >= current_cost:
                continue

            actions.append(
                Action.modify(
                    node,
                    capability,
                    current_level,
                    new_level,
                )
            )

    return actions


#@profile("1.3 Heuristic.find_best_improvement_action")
def find_best_improvement_action(
    node: str,
    requirements: list,
    state: State,
    catalog: dict,
    available_budget: int,
    costs: CostCalculator | None = None,
    relevant_capabilities: tuple[str, ...] | None = None,
    levels_by_capability: dict[str, tuple[int, ...]] | None = None,
) -> HeuristicCandidate | None:
    """Trova la migliore ADD/upgrade finanziabile sul nodo."""
    if costs is None:
        costs = CostCalculator(catalog)

    best = None
    actions = generate_improvement_actions(
        node,
        requirements,
        state,
        catalog,
        relevant_capabilities=relevant_capabilities,
        levels_by_capability=levels_by_capability,
    )

    for action in actions:
        cost = costs.calculate_action_cost(action)
        if cost > available_budget:
            continue

        benefit = calculate_action_benefit(
            action,
            requirements,
            state,
            catalog,
        )
        if benefit <= 0:
            continue

        efficiency = math.inf if cost <= 0 else benefit / cost

        candidate = HeuristicCandidate(
            action=action,
            cost=cost,
            benefit=benefit,
            efficiency=efficiency,
        )

        if _is_better_candidate(candidate, best):
            best = candidate

    return best


#@profile("1.4 Heuristic.find_best_reallocation_action")
def find_best_reallocation_action(
    node: str,
    requirements: list,
    grouped_requirements: dict[str, list],
    state: State,
    catalog: dict,
    available_budget: int,
    costs: CostCalculator,
    downgrade_candidates: list[tuple[Action, int]],
    current_priorities: dict[str, float] | None = None,
    relevant_capabilities: tuple[str, ...] | None = None,
    levels_by_capability: dict[str, tuple[int, ...]] | None = None,
) -> HeuristicCandidate | None:
    """Trova la migliore coppia downgrade + miglioramento."""
    best = None

    improvement_actions = generate_improvement_actions(
        node,
        requirements,
        state,
        catalog,
        relevant_capabilities=relevant_capabilities,
        levels_by_capability=levels_by_capability,
    )

    for improvement in improvement_actions:
        improvement_cost = costs.calculate_action_cost(improvement)

        if improvement_cost <= available_budget:
            continue

        improvement_benefit = calculate_action_benefit(
            improvement,
            requirements,
            state,
            catalog,
        )

        if improvement_benefit <= 0:
            continue

        for downgrade, downgrade_cost in downgrade_candidates:
            if downgrade.key == improvement.key:
                continue

            net_cost = downgrade_cost + improvement_cost
            if net_cost > available_budget:
                continue

            benefit = calculate_reallocation_benefit(
                downgrade,
                improvement,
                grouped_requirements,
                state,
                catalog,
                current_priorities,
            )

            if benefit <= 0:
                continue

            efficiency = math.inf if net_cost <= 0 else benefit / net_cost

            candidate = HeuristicCandidate(
                action=improvement,
                downgrade=downgrade,
                cost=net_cost,
                benefit=benefit,
                efficiency=efficiency,
            )

            if _is_better_candidate(candidate, best):
                best = candidate

    return best


def select_better_candidate(
    direct: HeuristicCandidate | None,
    reallocation: HeuristicCandidate | None,
) -> HeuristicCandidate | None:
    """Sceglie il migliore tra azione diretta e riallocazione."""
    if direct is None:
        return reallocation
    if reallocation is None:
        return direct
    if _is_better_candidate(reallocation, direct):
        return reallocation
    return direct


def _is_better_candidate(
    candidate: HeuristicCandidate,
    best: HeuristicCandidate | None,
) -> bool:
    if best is None:
        return True

    if not math.isclose(candidate.efficiency, best.efficiency):
        return candidate.efficiency > best.efficiency

    if not math.isclose(candidate.benefit, best.benefit):
        return candidate.benefit > best.benefit

    if candidate.cost != best.cost:
        return candidate.cost < best.cost

    return str(candidate.action) < str(best.action)
