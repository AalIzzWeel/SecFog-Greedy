"""Istanze riproducibili per il confronto tra esaustivo e Fast Greedy."""

import argparse
import random
from pathlib import Path

from optimizer.requirements import required_capabilities, validate_requirement
from optimizer.utils import load_json, save_json


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "model" / "security_catalog.json"
DEFAULT_PROFILES_PATH = PROJECT_ROOT / "model" / "requirement_profiles.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "model" / "comparison"
DEFAULT_SEEDS = (42, 123, 999, 1000, 1001)

NODE_SPECS = {
    "edge1": {"type": "edge", "operator": "edgeOp"},
    "cloud1": {"type": "cloud", "operator": "cloudOp"},
    "edge2": {"type": "edge", "operator": "edgeOp"},
}
SERVICE_NODES = {
    "edge_service1": "edge1",
    "cloud_service": "cloud1",
    "edge_service2": "edge2",
}

# I profili provengono dal progetto: due capability su ciascun edge,
# tre sul cloud, per sette coppie nodo-capability in totale.
EDGE_PROFILES = (
    ("intrusion_detection",),
    ("network_protection",),
    ("monitoring",),
    ("edge_communication",),
    ("secure_communication",),
    ("physical_security",),
)
CLOUD_PROFILES = (
    ("secure_storage", "physical_security"),
    ("monitoring", "physical_security"),
    ("network_protection", "physical_security"),
    ("intrusion_detection", "physical_security"),
    ("secure_communication", "physical_security"),
)


def _requirement(profile_names: tuple[str, ...], profiles: dict):
    missing = [name for name in profile_names if name not in profiles]
    if missing:
        raise ValueError(f"Profili mancanti: {missing}.")
    requirements = [profiles[name] for name in profile_names]
    return requirements[0] if len(requirements) == 1 else {"all": requirements}


def _capabilities(requirement, node_type: str, catalog: dict) -> list[str]:
    result = []
    for capability in sorted(required_capabilities(requirement)):
        data = catalog["capabilities"][capability]
        types = data.get("applicable_to", [])
        if not types or node_type in types:
            result.append(capability)
    return result


def _middle_level(catalog: dict, capability: str) -> int:
    levels = sorted(map(int, catalog["capabilities"][capability]["levels"]))
    if not levels:
        raise ValueError(f"La capability {capability} non dispone di livelli.")
    return levels[len(levels) // 2]


def generate_comparison_instance(
    seed: int,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    profiles_path: Path = DEFAULT_PROFILES_PATH,
) -> dict:
    """Genera sette coppie con ridondanza ANY; nessun filtro sugli esiti."""
    catalog = load_json(catalog_path)
    profiles = load_json(profiles_path)
    if catalog.get("actions") != {"allow_modify": True}:
        raise ValueError("Il catalogo deve consentire esclusivamente MODIFY.")

    rng = random.Random(seed)
    chosen_profiles = {
        "edge_service1": ("physical_security",),
        "cloud_service": rng.choice(CLOUD_PROFILES),
        "edge_service2": rng.choice(EDGE_PROFILES),
    }
    services = {}
    components = []
    security_state = {}
    capabilities_by_node = {}

    for service, node in SERVICE_NODES.items():
        names = chosen_profiles[service]
        requirement = _requirement(names, profiles)
        validate_requirement(requirement, catalog)
        capabilities = _capabilities(requirement, NODE_SPECS[node]["type"], catalog)
        expected = 3 if node == "cloud1" else 2
        if len(capabilities) != expected:
            raise ValueError(
                f"{node}: attese {expected} capability, trovate {len(capabilities)}."
            )
        services[service] = {
            "class": "comparison",
            "profiles": list(names),
            "requirements": requirement,
        }
        components.append({"name": service, "node": node})
        capabilities_by_node[node] = capabilities
        security_state[node] = {
            capability: _middle_level(catalog, capability)
            for capability in capabilities
        }

    # Un ramo ANY inizialmente ben protetto consente di recuperare
    # budget con una perdita limitata dello score globale. L'euristica
    # locale usa invece le probabilita' delle singole capability.
    # La costruzione dipende solo dal seed, mai dagli esiti dei solver.
    redundant = list(capabilities_by_node["edge1"])
    rng.shuffle(redundant)
    security_state["edge1"] = dict(zip(redundant, (2, 1)))

    # Gli altri nodi possono presentare colli di bottiglia (L0), livelli
    # intermedi e protezioni elevate. Non si selezionano le estrazioni.
    for node in ("cloud1", "edge2"):
        for capability in security_state[node]:
            level = rng.choice((0, 1, 2))
            if str(level) not in catalog["capabilities"][capability]["levels"]:
                raise ValueError(f"Livello L{level} mancante per {capability}.")
            security_state[node][capability] = level

    initial_cost = sum(
        int(catalog["capabilities"][capability]["levels"][str(level)]["cost"])
        for levels in security_state.values()
        for capability, level in levels.items()
    )
    application_name = f"comparison_any_app_n3_s3_seed{seed}"
    instance_name = f"comparison_any_n3_s3_seed{seed}"
    return {
        "catalog": catalog,
        "infrastructure": {"nodes": NODE_SPECS},
        "application": {"name": application_name, "services": services},
        "placement": {
            "name": instance_name,
            "application": application_name,
            "operator": "appOp",
            "components": components,
            "security_state": security_state,
        },
        "metadata": {
            "family": "comparison_n3_s3_redundant_any_v2",
            "seed": seed,
            "nodes": 3,
            "services": 3,
            "state_pairs": sum(map(len, security_state.values())),
            "initial_level_counts": {
                f"L{level}": sum(value == level for levels in security_state.values()
                                  for value in levels.values())
                for level in (0, 1, 2)
            },
            "initial_cost": initial_cost,
            "capabilities_by_node": capabilities_by_node,
            "catalog_source": catalog_path.name,
            "profiles_source": profiles_path.name,
            "description": (
                "ANY ridondante su edge1; altri livelli estratti dal seed. "
                "Catalogo originale, nessuna selezione in base al gap. "
                "L'ottimo viene calcolato dall'esaustivo per ciascun budget."
            ),
        },
    }


def generate_comparison_instances(
    seeds: list[int] | tuple[int, ...] = DEFAULT_SEEDS,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    profiles_path: Path = DEFAULT_PROFILES_PATH,
) -> list[dict]:
    if len(set(seeds)) != len(seeds):
        raise ValueError("I seed devono essere distinti.")
    return [
        generate_comparison_instance(seed, catalog_path, profiles_path)
        for seed in seeds
    ]


def save_comparison_instance(instance: dict, output_dir: Path) -> Path:
    instance_dir = output_dir / instance["placement"]["name"]
    for name in ("catalog", "infrastructure", "application", "placement", "metadata"):
        save_json(instance[name], instance_dir / f"{name}.json")
    return instance_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera istanze del confronto con tre nodi e tre servizi."
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    for instance in generate_comparison_instances(
        args.seeds, catalog_path=args.catalog, profiles_path=args.profiles
    ):
        print(f"Generata: {save_comparison_instance(instance, args.output_dir)}")


if __name__ == "__main__":
    main()
