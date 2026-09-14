import json
from pathlib import Path
import random

from optimizer.utils import (
    get_applicable_capabilities,
    save_json,
)


SERVICE_CLASSES = {
    "light": 1,
    "medium": 2,
    "heavy": 3,
}

SERVICE_CLASS_RATIOS = {
    "light": 0.3,
    "medium": 0.5,
    "heavy": 0.2,
}

SCALABILITY_CONFIGS = (
    (25, 5),
    (50, 10),
    (100, 15),
    (200, 25),
    (400, 50),
)


def generate_nodes(
    total_nodes: int,
    cloud_ratio: float = 0.3,
) -> dict[str, dict[str, str]]:
    if total_nodes <= 0:
        raise ValueError("total_nodes deve essere maggiore di 0.")

    if not 0.0 <= cloud_ratio <= 1.0:
        raise ValueError("cloud_ratio deve essere compreso tra 0 e 1.")

    cloud_count = round(total_nodes * cloud_ratio)
    edge_count = total_nodes - cloud_count

    nodes = {}

    for index in range(1, cloud_count + 1):
        node_name = f"cloud{index}"
        nodes[node_name] = {
            "type": "cloud",
            "operator": "cloudOp",
        }

    for index in range(1, edge_count + 1):
        node_name = f"edge{index}"
        nodes[node_name] = {
            "type": "edge",
            "operator": "edgeOp",
        }

    return nodes


def build_infrastructure(
    total_nodes: int,
    cloud_ratio: float = 0.3,
) -> dict:
    return {
        "nodes": generate_nodes(
            total_nodes=total_nodes,
            cloud_ratio=cloud_ratio,
        ),
    }


def generate_services(
    total_services: int,
) -> dict:
    if total_services <= 0:
        raise ValueError(
            "total_services deve essere maggiore di 0."
        )

    return {
        "services": {
            f"service{index}": {}
            for index in range(1, total_services + 1)
        }
    }


def check_applicability(
    requirement,
    node_type: str,
    catalog: dict,
) -> bool:
    if isinstance(requirement, str):
        capability = catalog["capabilities"][requirement]
        applicable_to = capability.get("applicable_to", [])

        return (
            not applicable_to
            or node_type in applicable_to
        )

    if not isinstance(requirement, dict):
        raise ValueError(
            f"Requirement non valido: {requirement}"
        )

    if "all" in requirement:
        return all(
            check_applicability(
                child,
                node_type,
                catalog,
            )
            for child in requirement["all"]
        )

    if "any" in requirement:
        return any(
            check_applicability(
                child,
                node_type,
                catalog,
            )
            for child in requirement["any"]
        )

    raise ValueError(
        f"Requirement non valido: {requirement}"
    )


def load_requirement_profiles(
    path: Path,
) -> dict:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_service_class_distribution(
    total_services: int,
) -> dict[str, int]:
    if total_services <= 0:
        raise ValueError(
            "total_services deve essere maggiore di 0."
        )

    exact_counts = {
        class_name: total_services * ratio
        for class_name, ratio in SERVICE_CLASS_RATIOS.items()
    }

    counts = {
        class_name: int(value)
        for class_name, value in exact_counts.items()
    }

    remaining = total_services - sum(counts.values())

    remainder_order = sorted(
        SERVICE_CLASS_RATIOS,
        key=lambda class_name: (
            exact_counts[class_name] - counts[class_name],
            SERVICE_CLASS_RATIOS[class_name],
        ),
        reverse=True,
    )

    for class_name in remainder_order[:remaining]:
        counts[class_name] += 1

    return counts


def assign_service_classes(
    application: dict,
    distribution: dict[str, int],
) -> dict:
    services = application["services"]

    if sum(distribution.values()) != len(services):
        raise ValueError(
            "La distribuzione delle classi non coincide "
            "con il numero di servizi."
        )

    classes = []

    for class_name in ("light", "medium", "heavy"):
        classes.extend(
            [class_name] * distribution[class_name]
        )

    for service_name, class_name in zip(
        services,
        classes,
    ):
        services[service_name]["class"] = class_name

    return application


def assign_profiles_to_services(
    application: dict,
    profiles: dict,
    seed: int = 42,
) -> dict:
    profile_names = list(profiles.keys())
    rng = random.Random(seed)

    for service in application["services"].values():
        class_name = service["class"]

        if class_name not in SERVICE_CLASSES:
            raise ValueError(
                f"Classe di servizio non valida: {class_name}"
            )

        profile_count = SERVICE_CLASSES[class_name]

        if profile_count > len(profile_names):
            raise ValueError(
                "Numero di profili insufficiente."
            )

        service["profiles"] = rng.sample(
            profile_names,
            profile_count,
        )

    return application


def build_service_requirements(
    application: dict,
    profiles: dict,
) -> dict:
    for service in application["services"].values():
        assigned_profiles = service.get("profiles", [])

        if not assigned_profiles:
            raise ValueError(
                "Il servizio non ha profili assegnati."
            )

        requirements = [
            profiles[profile_name]
            for profile_name in assigned_profiles
        ]

        if len(requirements) == 1:
            service["requirements"] = requirements[0]
        else:
            service["requirements"] = {
                "all": requirements,
            }

    return application


def get_service_applicability(
    application: dict,
    catalog: dict,
) -> dict[str, set[str]]:
    result = {}

    for service_name, service in application["services"].items():
        requirement = service.get("requirements")

        if requirement is None:
            raise ValueError(
                f"Il servizio {service_name} non ha requirements."
            )

        supported_types = set()

        for node_type in ("cloud", "edge"):
            if check_applicability(
                requirement,
                node_type,
                catalog,
            ):
                supported_types.add(node_type)

        if not supported_types:
            raise ValueError(
                f"Il servizio {service_name} non è applicabile "
                "né a cloud né a edge."
            )

        result[service_name] = supported_types

    return result


def assign_services_to_nodes(
    application: dict,
    infrastructure: dict,
    applicability: dict[str, set[str]],
    seed: int = 42,
) -> list[dict[str, str]]:
    rng = random.Random(seed)

    nodes = infrastructure["nodes"]
    placement = []

    for service_name in application["services"]:
        compatible_types = applicability[service_name]

        candidate_nodes = [
            node_name
            for node_name, node_data in nodes.items()
            if node_data["type"] in compatible_types
        ]

        if not candidate_nodes:
            raise ValueError(
                f"Nessun nodo compatibile per {service_name}."
            )

        chosen_node = rng.choice(candidate_nodes)

        placement.append(
            {
                "name": service_name,
                "node": chosen_node,
            }
        )

    return placement


def build_placement(
    components: list[dict[str, str]],
) -> dict:
    if not components:
        raise ValueError(
            "Il placement deve contenere almeno un componente."
        )

    return {
        "components": components,
    }


def _requirement_is_active(
    requirement,
    node_state: dict[str, int | None],
) -> bool:
    if isinstance(requirement, str):
        return (
            requirement in node_state
            and node_state[requirement] is not None
        )

    if not isinstance(requirement, dict):
        raise ValueError(
            f"Requirement non valido: {requirement}"
        )

    if "all" in requirement:
        return all(
            _requirement_is_active(
                child,
                node_state,
            )
            for child in requirement["all"]
        )

    if "any" in requirement:
        return any(
            _requirement_is_active(
                child,
                node_state,
            )
            for child in requirement["any"]
        )

    raise ValueError(
        f"Requirement non valido: {requirement}"
    )


def ensure_requirement_satisfied(
    requirement,
    node_type: str,
    node_state: dict[str, int | None],
    catalog: dict,
    rng: random.Random,
) -> None:
    """
    Garantisce che il requirement sia soddisfatto sul nodo.

    Le capability inattive necessarie vengono attivate al livello
    minimo disponibile. Per un ANY viene attivato un solo ramo
    compatibile, scelto in modo riproducibile.
    """
    if _requirement_is_active(
        requirement,
        node_state,
    ):
        return

    if isinstance(requirement, str):
        if requirement not in node_state:
            raise ValueError(
                f"La capability {requirement} non è disponibile "
                f"sul tipo di nodo {node_type}."
            )

        levels = sorted(
            int(level)
            for level in catalog["capabilities"][
                requirement
            ]["levels"]
        )

        if not levels:
            raise ValueError(
                f"La capability {requirement} non ha livelli."
            )

        node_state[requirement] = levels[0]
        return

    if not isinstance(requirement, dict):
        raise ValueError(
            f"Requirement non valido: {requirement}"
        )

    if "all" in requirement:
        for child in requirement["all"]:
            ensure_requirement_satisfied(
                child,
                node_type,
                node_state,
                catalog,
                rng,
            )
        return

    if "any" in requirement:
        compatible_children = [
            child
            for child in requirement["any"]
            if check_applicability(
                child,
                node_type,
                catalog,
            )
        ]

        if not compatible_children:
            raise ValueError(
                f"Nessun ramo ANY compatibile con il nodo {node_type}."
            )

        chosen_child = rng.choice(
            compatible_children
        )

        ensure_requirement_satisfied(
            chosen_child,
            node_type,
            node_state,
            catalog,
            rng,
        )
        return

    raise ValueError(
        f"Requirement non valido: {requirement}"
    )


def generate_security_state(
    placement: dict,
    infrastructure: dict,
    application: dict,
    catalog: dict,
    seed: int = 42,
) -> dict[str, dict[str, int | None]]:
    """
    Genera lo stato iniziale delle security capability.

    Prima assegna livelli casuali alle capability applicabili dei
    nodi usati dal placement. Poi garantisce che i requirement
    di tutti i servizi siano soddisfatti sul nodo assegnato.
    """
    rng = random.Random(seed)

    used_nodes = {
        component["node"]
        for component in placement["components"]
    }

    security_state = {}

    for node_name in sorted(used_nodes):
        node_type = infrastructure["nodes"][
            node_name
        ]["type"]

        capabilities = get_applicable_capabilities(
            catalog,
            node_type,
        )

        node_state = {}

        for capability_name in capabilities:
            level = rng.choices(
                population=[None, 0, 1, 2],
                weights=[0.2, 0.4, 0.3, 0.1],
                k=1,
            )[0]

            node_state[capability_name] = level

        security_state[node_name] = node_state

    services = application["services"]

    for component in placement["components"]:
        service_name = component["name"]
        node_name = component["node"]

        if service_name not in services:
            raise ValueError(
                f"Servizio {service_name} non presente "
                "nell'applicazione."
            )

        requirement = services[
            service_name
        ].get("requirements")

        if requirement is None:
            raise ValueError(
                f"Il servizio {service_name} non ha requirements."
            )

        node_type = infrastructure["nodes"][
            node_name
        ]["type"]

        if not check_applicability(
            requirement,
            node_type,
            catalog,
        ):
            raise ValueError(
                f"I requirements di {service_name} non sono "
                f"applicabili al nodo {node_name}."
            )

        ensure_requirement_satisfied(
            requirement,
            node_type,
            security_state[node_name],
            catalog,
            rng,
        )

    return security_state


def add_security_state(
    placement: dict,
    security_state: dict,
) -> dict:
    placement["security_state"] = security_state
    return placement


def save_instance(
    infrastructure: dict,
    application: dict,
    placement: dict,
    output_dir: Path,
) -> None:
    save_json(
        infrastructure,
        output_dir / "infrastructure.json",
    )

    save_json(
        application,
        output_dir / "application.json",
    )

    save_json(
        placement,
        output_dir / "placement.json",
    )


def generate_instance(
    total_nodes: int,
    total_services: int,
    catalog: dict,
    profiles: dict,
    seed: int = 42,
) -> tuple[dict, dict, dict]:
    infrastructure = build_infrastructure(
        total_nodes=total_nodes,
        cloud_ratio=0.3,
    )

    application = generate_services(
        total_services=total_services,
    )

    application["name"] = (
        f"scalable_app_{total_services}"
    )

    distribution = get_service_class_distribution(
        total_services
    )

    application = assign_service_classes(
        application,
        distribution,
    )

    application = assign_profiles_to_services(
        application,
        profiles,
        seed=seed,
    )

    application = build_service_requirements(
        application,
        profiles,
    )

    applicability = get_service_applicability(
        application,
        catalog,
    )

    components = assign_services_to_nodes(
        application,
        infrastructure,
        applicability,
        seed=seed + 1,
    )

    placement = build_placement(
        components
    )

    placement["name"] = (
        f"placement_n{total_nodes}_s{total_services}"
    )
    placement["application"] = application["name"]
    placement["operator"] = "appOp"

    security_state = generate_security_state(
        placement,
        infrastructure,
        application,
        catalog,
        seed=seed + 2,
    )

    placement = add_security_state(
        placement,
        security_state,
    )

    return (
        infrastructure,
        application,
        placement,
    )


def generate_scalable_instances(
    catalog: dict,
    profiles: dict,
    output_root: Path,
    seed: int = 42,
    configurations=SCALABILITY_CONFIGS,
) -> list[Path]:
    generated = []

    for total_nodes, total_services in configurations:
        infrastructure, application, placement = (
            generate_instance(
                total_nodes=total_nodes,
                total_services=total_services,
                catalog=catalog,
                profiles=profiles,
                seed=seed,
            )
        )

        instance_dir = (
            output_root
            / (
                f"instance_n{total_nodes}"
                f"_s{total_services}"
                f"_seed{seed}"
            )
        )

        save_instance(
            infrastructure,
            application,
            placement,
            instance_dir,
        )

        generated.append(instance_dir)

    return generated


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    catalog_path = (
        PROJECT_ROOT
        / "model"
        / "security_catalog.json"
    )

    profiles_path = (
        PROJECT_ROOT
        / "model"
        / "requirement_profiles.json"
    )

    output_root = (
        PROJECT_ROOT
        / "model"
        / "generated"
    )

    with catalog_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        catalog = json.load(file)

    profiles = load_requirement_profiles(
        profiles_path
    )

    seeds = (
        42,
        123,
        999,
    )

    for seed in seeds:
        generated = generate_scalable_instances(
            catalog=catalog,
            profiles=profiles,
            output_root=output_root,
            seed=seed,
        )

        for path in generated:
            print(f"Generata: {path}")
