import argparse
from pathlib import Path

from optimizer.requirements import (
    required_capabilities,
    validate_requirement,
)
from optimizer.utils import load_json, save_json


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "model" / "security_catalog.json"
DEFAULT_PROFILES_PATH = (
    PROJECT_ROOT / "model" / "requirement_profiles.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "model" / "comparison"

NODE_SPECS = {
    "edge1": {"type": "edge", "operator": "edgeOp"},
    "cloud1": {"type": "cloud", "operator": "cloudOp"},
}

# Le istanze cambiano soltanto nei profili assegnati ai due servizi.
# Capability, probabilita' e costi provengono sempre dai JSON del progetto.
SCENARIO_PROFILES = {
    "storage": {
        "edge_service": ("secure_storage",),
        "cloud_service": ("secure_storage", "physical_security"),
    },
    "communication": {
        "edge_service": (
            "intrusion_detection",
            "network_protection",
        ),
        "cloud_service": (
            "secure_communication",
            "physical_security",
        ),
    },
    "monitoring": {
        "edge_service": ("secure_storage",),
        "cloud_service": ("monitoring", "physical_security"),
    },
    "network": {
        "edge_service": (
            "intrusion_detection",
            "network_protection",
        ),
        "cloud_service": (
            "network_protection",
            "physical_security",
        ),
    },
    "detection": {
        "edge_service": ("secure_storage",),
        "cloud_service": (
            "intrusion_detection",
            "physical_security",
        ),
    },
}
DEFAULT_SCENARIOS = tuple(SCENARIO_PROFILES)

SERVICE_NODES = {
    "edge_service": "edge1",
    "cloud_service": "cloud1",
}


def _combine_profiles(profile_names: tuple[str, ...], profiles: dict):
    missing = [name for name in profile_names if name not in profiles]
    if missing:
        raise ValueError(f"Profili mancanti: {missing}.")

    requirements = [profiles[name] for name in profile_names]
    if len(requirements) == 1:
        return requirements[0]
    return {"all": requirements}


def _applicable_capabilities(
    requirement,
    node_type: str,
    catalog: dict,
) -> list[str]:
    capabilities = []
    for capability in sorted(required_capabilities(requirement)):
        data = catalog["capabilities"][capability]
        applicable_to = data.get("applicable_to", [])
        if not applicable_to or node_type in applicable_to:
            capabilities.append(capability)
    return capabilities


def _middle_level(catalog: dict, capability: str) -> int:
    levels = sorted(
        int(level)
        for level in catalog["capabilities"][capability]["levels"]
    )
    if not levels:
        raise ValueError(f"{capability} non dispone di livelli.")
    return levels[len(levels) // 2]


def _level_cost(catalog: dict, capability: str, level: int) -> int:
    return int(
        catalog["capabilities"][capability]["levels"][str(level)][
            "cost"
        ]
    )


def _validate_catalog(catalog: dict) -> None:
    if catalog.get("actions") != {"allow_modify": True}:
        raise ValueError(
            "Il catalogo deve consentire esclusivamente azioni MODIFY."
        )
    if not catalog.get("capabilities"):
        raise ValueError("Il catalogo non contiene capability.")


def generate_comparison_instance(
    scenario: str,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    profiles_path: Path = DEFAULT_PROFILES_PATH,
) -> dict:
    """Genera un'istanza deterministica della famiglia edge-cloud."""
    if scenario not in SCENARIO_PROFILES:
        raise ValueError(
            f"Scenario sconosciuto: {scenario}. "
            f"Valori ammessi: {', '.join(DEFAULT_SCENARIOS)}."
        )

    catalog = load_json(catalog_path)
    profiles = load_json(profiles_path)
    _validate_catalog(catalog)

    services = {}
    components = []
    security_state = {}
    capabilities_by_node = {}

    for service_name, profile_names in SCENARIO_PROFILES[
        scenario
    ].items():
        requirement = _combine_profiles(profile_names, profiles)
        validate_requirement(requirement, catalog)

        node = SERVICE_NODES[service_name]
        node_type = NODE_SPECS[node]["type"]
        capabilities = _applicable_capabilities(
            requirement, node_type, catalog
        )
        if len(capabilities) != 3:
            raise ValueError(
                f"Il nodo {node} dello scenario {scenario} deve avere "
                f"3 capability attive, trovate {len(capabilities)}."
            )

        services[service_name] = {
            "class": "comparison",
            "profiles": list(profile_names),
            "requirements": requirement,
        }
        components.append({"name": service_name, "node": node})
        capabilities_by_node[node] = capabilities
        security_state[node] = {
            capability: _middle_level(catalog, capability)
            for capability in capabilities
        }

    if len({component["node"] for component in components}) != len(
        components
    ):
        raise ValueError("Ogni nodo puo' ospitare al massimo un servizio.")

    initial_cost = sum(
        _level_cost(catalog, capability, level)
        for capabilities in security_state.values()
        for capability, level in capabilities.items()
    )
    application_name = f"realistic_edge_cloud_app_{scenario}"
    instance_name = f"realistic_edge_cloud_{scenario}"

    infrastructure = {"nodes": NODE_SPECS}
    application = {
        "name": application_name,
        "services": services,
    }
    placement = {
        "name": instance_name,
        "application": application_name,
        "operator": "appOp",
        "components": components,
        "security_state": security_state,
    }
    metadata = {
        "family": "deterministic_realistic_edge_cloud",
        "scenario": scenario,
        "nodes": len(NODE_SPECS),
        "services": len(services),
        "state_pairs": sum(
            len(capabilities) for capabilities in security_state.values()
        ),
        "initial_cost": initial_cost,
        "capabilities_by_node": capabilities_by_node,
        "catalog_source": catalog_path.name,
        "profiles_source": profiles_path.name,
        "description": (
            "L'ottimo non e' predefinito: viene calcolato dalla ricerca "
            "esaustiva per ciascun budget."
        ),
    }

    return {
        "catalog": catalog,
        "infrastructure": infrastructure,
        "application": application,
        "placement": placement,
        "metadata": metadata,
    }


def generate_comparison_instances(
    scenarios: list[str] | tuple[str, ...] = DEFAULT_SCENARIOS,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    profiles_path: Path = DEFAULT_PROFILES_PATH,
) -> list[dict]:
    return [
        generate_comparison_instance(
            scenario,
            catalog_path=catalog_path,
            profiles_path=profiles_path,
        )
        for scenario in scenarios
    ]


def save_comparison_instance(instance: dict, output_dir: Path) -> Path:
    instance_dir = output_dir / instance["placement"]["name"]
    for name in (
        "catalog",
        "infrastructure",
        "application",
        "placement",
        "metadata",
    ):
        save_json(instance[name], instance_dir / f"{name}.json")
    return instance_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Genera la famiglia deterministica di istanze edge-cloud."
        )
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=DEFAULT_SCENARIOS,
        default=list(DEFAULT_SCENARIOS),
    )
    parser.add_argument(
        "--catalog", type=Path, default=DEFAULT_CATALOG_PATH
    )
    parser.add_argument(
        "--profiles", type=Path, default=DEFAULT_PROFILES_PATH
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR
    )
    args = parser.parse_args()

    instances = generate_comparison_instances(
        args.scenarios,
        catalog_path=args.catalog,
        profiles_path=args.profiles,
    )
    for instance in instances:
        instance_dir = save_comparison_instance(
            instance, args.output_dir
        )
        print(f"Generata: {instance_dir}")


if __name__ == "__main__":
    main()
