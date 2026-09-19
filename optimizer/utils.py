import json
from pathlib import Path

from optimizer.actions import Action
from optimizer.state import State


def load_json(path) -> dict:
    """Carica un file JSON e restituisce il contenuto come dizionario."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_catalog(path) -> dict:
    """Carica il catalogo delle security capability."""
    return load_json(path)


def load_infrastructure(path) -> dict:
    """Carica la descrizione dell'infrastruttura."""
    return load_json(path)


def load_application(path) -> dict:
    """Carica la descrizione di un'applicazione."""
    return load_json(path)


def load_placement(path) -> dict:
    """Carica un placement."""
    return load_json(path)


def save_json(
    data: dict,
    output_path: Path,
) -> None:
    """Salva un dizionario su file JSON."""
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
        )


def get_placement_nodes(placement: dict) -> list[str]:
    """Restituisce i nodi usati dal placement senza duplicati."""
    nodes = []

    for component in placement.get("components", []):
        node = component["node"]

        if node not in nodes:
            nodes.append(node)

    return nodes


def get_applicable_capabilities(
    catalog: dict,
    node_type: str,
) -> list[str]:
    """
    Restituisce le capability applicabili a un certo tipo di nodo.
    """
    capabilities = []

    for capability_name, capability_data in catalog.get(
        "capabilities",
        {},
    ).items():
        applicable_to = capability_data.get(
            "applicable_to",
            [],
        )

        if not applicable_to or node_type in applicable_to:
            capabilities.append(capability_name)

    return capabilities


def validate_placement(
    catalog: dict,
    infrastructure: dict,
    placement: dict,
) -> None:
    """
    Controlla che il placement sia coerente con
    catalogo e infrastruttura.
    """
    infrastructure_nodes = infrastructure.get("nodes", {})
    catalog_capabilities = catalog.get("capabilities", {})

    components = placement.get("components", [])
    security_state = placement.get("security_state", {})

    if not components:
        raise ValueError(
            "Il placement non contiene componenti applicativi."
        )

    placement_nodes = get_placement_nodes(placement)

    if set(security_state) != set(placement_nodes):
        raise ValueError(
            "security_state deve contenere esattamente "
            "i nodi usati dal placement."
        )

    for node in placement_nodes:
        if node not in infrastructure_nodes:
            raise ValueError(
                f"Il nodo {node} non esiste nell'infrastruttura."
            )

        node_data = infrastructure_nodes[node]
        node_type = node_data.get("type")

        if node_type is None:
            raise ValueError(
                f"Il nodo {node} non specifica il tipo."
            )

        # Nei test/placement legacy le capability possono essere
        # dichiarate esplicitamente nel nodo.
        # Nelle istanze scalabili vengono invece derivate
        # automaticamente da applicable_to.
        explicit_capabilities = node_data.get("capabilities")

        if explicit_capabilities is not None:
            available_capabilities = set(explicit_capabilities)
        else:
            available_capabilities = set(
                get_applicable_capabilities(
                    catalog,
                    node_type,
                )
            )

        state_capabilities = set(
            security_state[node]
        )

        if not state_capabilities.issubset(available_capabilities):
            raise ValueError(
                f"Le capability di {node} nel placement "
                "non sono un sottoinsieme di quelle disponibili "
                "per il nodo."
            )

        for capability, level in security_state[node].items():
            if capability not in catalog_capabilities:
                raise ValueError(
                    f"Capability {capability} "
                    "non presente nel catalogo."
                )

            applicable_to = catalog_capabilities[
                capability
            ].get(
                "applicable_to",
                [],
            )

            if applicable_to and node_type not in applicable_to:
                raise ValueError(
                    f"La capability {capability} "
                    f"non e' applicabile al nodo {node}."
                )

            if level is None:
                raise ValueError(
                    f"La capability {node}.{capability} deve essere attiva."
                )

            valid_levels = catalog_capabilities[
                capability
            ].get(
                "levels",
                {},
            )

            if str(level) not in valid_levels:
                raise ValueError(
                    f"Livello {level} non valido per "
                    f"{node}.{capability}."
                )


def create_initial_state(
    catalog: dict,
    infrastructure: dict,
    placement: dict,
) -> State:
    """
    Costruisce lo stato iniziale P0 a partire
    da un placement.
    """
    validate_placement(
        catalog,
        infrastructure,
        placement,
    )

    levels = {}

    for node in get_placement_nodes(placement):
        for capability, level in (
            placement["security_state"][node].items()
        ):
            levels[(node, capability)] = level

    return State(levels)


def build_final_policy(
    initial_state: State,
    final_state: State,
) -> list[Action]:
    """Costruisce la politica finale confrontando P0 e stato finale."""
    if set(initial_state.levels) != set(final_state.levels):
        raise ValueError(
            "Stato iniziale e finale devono contenere le stesse coppie."
        )

    policy = []

    for key, initial_level in sorted(initial_state.items()):
        node, capability = key
        final_level = final_state[key]

        if initial_level == final_level:
            continue

        policy.append(
            Action.modify(
                node,
                capability,
                initial_level,
                final_level,
            )
        )

    return policy


def display_solution_summary(
    initial_state: State,
    final_state: State,
    final_score: float,
    initial_budget: int,
    remaining_budget: int,
) -> None:
    print("\n" + "=" * 60)
    print("RIEPILOGO SOLUZIONE")
    print("=" * 60)
    print(f"Score finale     : {final_score:.8f}")
    print(f"Budget iniziale  : {initial_budget}")
    print(f"Budget residuo   : {remaining_budget}")
    print(
        f"Budget netto usato: "
        f"{initial_budget - remaining_budget}"
    )
    print("-" * 60)

    for action in build_final_policy(
        initial_state,
        final_state,
    ):
        print(action)

    print("=" * 60)
