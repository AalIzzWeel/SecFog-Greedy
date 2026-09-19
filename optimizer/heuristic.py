from dataclasses import dataclass
import math

from optimizer.actions import Action
from optimizer.costs import CostCalculator
from optimizer.requirements import required_capabilities, validate_requirement
from optimizer.state import State


@dataclass(frozen=True)
class HeuristicCandidate:
    action: Action
    cost: int
    specific_quality: float
    efficiency: float

    @property
    def benefit(self) -> float:
        return self.specific_quality


def group_requirements_by_node(
    application: dict, placement: dict, catalog: dict
) -> dict[str, list]:
    """Raggruppa i requisiti rispettando l'ordine dei nodi in input."""
    if placement.get("application") != application.get("name"):
        raise ValueError(
            "L'applicazione del placement non coincide con quella caricata."
        )
    services = application.get("services", {})
    grouped: dict[str, list] = {}
    for component in placement.get("components", []):
        service_name = component["name"]
        node = component["node"]
        if service_name not in services:
            raise ValueError(f"Servizio {service_name} non definito nell'applicazione.")
        requirement = services[service_name].get("requirements")
        if requirement is None:
            raise ValueError(f"Requisiti mancanti per il servizio {service_name}.")
        validate_requirement(requirement, catalog)
        grouped.setdefault(node, []).append(requirement)
    return grouped


def build_relevant_capabilities(
    grouped_requirements: dict[str, list]
) -> dict[str, tuple[str, ...]]:
    result = {}
    for node, requirements in grouped_requirements.items():
        capabilities: set[str] = set()
        for requirement in requirements:
            capabilities.update(required_capabilities(requirement))
        result[node] = tuple(sorted(capabilities))
    return result


def build_capability_levels(catalog: dict) -> dict[str, tuple[int, ...]]:
    return {
        capability: tuple(sorted(map(int, data["levels"])))
        for capability, data in catalog.get("capabilities", {}).items()
    }


def rank_nodes_by_requirement_count(
    grouped_requirements: dict[str, list]
) -> list[str]:
    """Ordine decrescente; l'ordine di input risolve le parita'."""
    return sorted(
        grouped_requirements,
        key=lambda node: -sum(
            len(required_capabilities(requirement))
            for requirement in grouped_requirements[node]
        ),
    )


def _attack_probability(catalog: dict, capability: str, level: int) -> float:
    effectiveness = float(
        catalog["capabilities"][capability]["levels"][str(level)]["probability"]
    )
    return 1.0 - effectiveness


def calculate_specific_quality(action: Action, catalog: dict) -> float:
    """Qualita' specifica = p_before - p_after (p: rischio d'attacco)."""
    p_before = _attack_probability(catalog, action.capability, action.old_level)
    p_after = _attack_probability(catalog, action.capability, action.new_level)
    return p_before - p_after


def calculate_efficiency(action: Action, catalog: dict, costs: CostCalculator) -> float:
    cost = costs.calculate_action_cost(action)
    quality = calculate_specific_quality(action, catalog)
    if cost == 0:
        return math.copysign(math.inf, quality) if quality else 0.0
    return quality / cost


def generate_actions(
    initial_state: State,
    catalog: dict,
    grouped_requirements: dict[str, list],
) -> tuple[list[HeuristicCandidate], list[HeuristicCandidate]]:
    """Genera da S0 tutte e sole le modulazioni delle capability richieste."""
    costs = CostCalculator(catalog)
    levels_by_capability = build_capability_levels(catalog)
    relevant = build_relevant_capabilities(grouped_requirements)
    node_order = rank_nodes_by_requirement_count(grouped_requirements)
    node_position = {node: index for index, node in enumerate(node_order)}
    upgrades: list[HeuristicCandidate] = []
    downgrades: list[HeuristicCandidate] = []

    for node in node_order:
        for capability in relevant[node]:
            key = (node, capability)
            if key not in initial_state:
                # Un ramo ANY puo' menzionare capability non applicabili
                # al tipo di nodo; SecFog le considera false.
                continue
            initial_level = initial_state[key]
            levels = levels_by_capability[capability]

            # Tutte le transizioni di upgrade adiacenti restano nella lista:
            # una L1 -> L2 puo' diventare fattibile dopo una L0 -> L1.
            for old_level, new_level in zip(levels, levels[1:]):
                action = Action.modify(node, capability, old_level, new_level)
                cost = costs.calculate_action_cost(action)
                quality = calculate_specific_quality(action, catalog)
                if cost <= 0:
                    continue
                candidate = HeuristicCandidate(
                    action=action,
                    cost=cost,
                    specific_quality=quality,
                    efficiency=calculate_efficiency(action, catalog, costs),
                )
                upgrades.append(candidate)

            # Come gli upgrade, anche i downgrade sono transizioni
            # adiacenti. Una L1 -> L0 inizialmente non fattibile resta
            # disponibile e puo' diventarlo dopo una L2 -> L1.
            # Il blocco dei downgrade successivi a un upgrade e' gestito
            # dall'ottimizzatore, che conosce la cronologia delle azioni.
            for old_level, new_level in zip(levels[:0:-1], levels[-2::-1]):
                action = Action.modify(node, capability, old_level, new_level)
                cost = costs.calculate_action_cost(action)
                if cost >= 0:
                    continue
                downgrades.append(
                    HeuristicCandidate(
                        action=action,
                        cost=cost,
                        specific_quality=calculate_specific_quality(
                            action, catalog
                        ),
                        efficiency=calculate_efficiency(
                            action, catalog, costs
                        ),
                    )
                )

    def tie(candidate: HeuristicCandidate) -> tuple:
        action = candidate.action
        return node_position[action.node], action.capability, action.new_level

    upgrades.sort(key=lambda candidate: (-candidate.efficiency, *tie(candidate)))
    downgrades.sort(key=lambda candidate: (candidate.efficiency, *tie(candidate)))
    return upgrades, downgrades


def first_feasible(
    candidates: list[HeuristicCandidate],
    state: State,
    blocked_keys: set[tuple[str, str]] | None = None,
) -> tuple[int, HeuristicCandidate] | None:
    blocked_keys = blocked_keys or set()
    for index, candidate in enumerate(candidates):
        if (
            candidate.action.key not in blocked_keys
            and state.is_feasible(candidate.action)
        ):
            return index, candidate
    return None
