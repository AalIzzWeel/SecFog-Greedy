import math

from optimizer.state import State

def validate_requirement(requirement, catalog: dict) -> None:
    """Valida ricorsivamente un requisito composto con all/any."""
    if isinstance(requirement, str):
        if requirement not in catalog.get("capabilities", {}):
            raise ValueError(
                f"Capability sconosciuta nel requisito: {requirement}."
            )
        return

    if not isinstance(requirement, dict) or len(requirement) != 1:
        raise ValueError(
            "Un requisito deve essere una capability oppure un solo all/any."
        )

    operator, children = next(iter(requirement.items()))

    if operator not in {"all", "any"}:
        raise ValueError(f"Operatore non valido: {operator}.")

    if not isinstance(children, list) or not children:
        raise ValueError(
            f"{operator} deve contenere almeno un requisito."
        )

    for child in children:
        validate_requirement(child, catalog)


def required_capabilities(requirement) -> set[str]:
    """Restituisce tutte le capability presenti nel requisito."""
    if isinstance(requirement, str):
        return {requirement}

    _, children = next(iter(requirement.items()))
    capabilities = set()

    for child in children:
        capabilities.update(required_capabilities(child))

    return capabilities


def evaluate_requirement(
    requirement,
    node: str,
    state: State,
    catalog: dict,
    overrides: dict[tuple[str, str], int] | None = None,
) -> float:
    """Stima la soddisfazione, applicando eventuali livelli temporanei."""
    if isinstance(requirement, str):
        key = (node, requirement)

        if overrides is not None and key in overrides:
            level = overrides[key]
        elif key not in state:
            return 0.0
        else:
            level = state.get_level(node, requirement)

        if level is None:
            return 0.0

        level_data = catalog["capabilities"][requirement]["levels"][str(level)]
        return float(level_data["probability"])

    operator, children = next(iter(requirement.items()))

    values = [
        evaluate_requirement(
            child,
            node,
            state,
            catalog,
            overrides,
        )
        for child in children
    ]

    if operator == "all":
        return math.prod(values)

    return 1.0 - math.prod(
        1.0 - value
        for value in values
    )