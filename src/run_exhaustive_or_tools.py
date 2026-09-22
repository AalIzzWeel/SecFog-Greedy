import argparse
from pathlib import Path

from optimizer.utils import (
    create_initial_state,
    load_application,
    load_catalog,
    load_infrastructure,
    load_placement,
)
from scoring.score_wrapper import ScoreWrapper
from src.exhaustive_or_tools import (
    ExhaustiveOrToolsOptimizer,
    build_adjacent_policy,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = PROJECT_ROOT / "model" / "security_catalog.json"
DEFAULT_INSTANCE = (
    PROJECT_ROOT / "model" / "generated" / "instance_n25_s5_seed42"
)
DEFAULT_INFRASTRUCTURE = DEFAULT_INSTANCE / "infrastructure.json"
DEFAULT_APPLICATION = DEFAULT_INSTANCE / "application.json"
DEFAULT_PLACEMENT = DEFAULT_INSTANCE / "placement.json"
DEFAULT_BASE = PROJECT_ROOT / "prolog" / "secfog_base.pl"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Enumera con OR-Tools tutte le configurazioni ammissibili "
            "e le valuta mediante SecFog. Usare istanze piccole."
        )
    )
    parser.add_argument("--budget", type=int, default=300)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--infrastructure", type=Path, default=DEFAULT_INFRASTRUCTURE
    )
    parser.add_argument("--application", type=Path, default=DEFAULT_APPLICATION)
    parser.add_argument("--placement", type=Path, default=DEFAULT_PLACEMENT)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Limite opzionale: se raggiunto, il risultato non e' esatto.",
    )
    parser.add_argument(
        "--max-solutions",
        type=int,
        default=None,
        help="Limite opzionale: se raggiunto, il risultato non e' esatto.",
    )
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    infrastructure = load_infrastructure(args.infrastructure)
    application = load_application(args.application)
    placement = load_placement(args.placement)
    initial_state = create_initial_state(
        catalog, infrastructure, placement
    )
    wrapper = ScoreWrapper(
        catalog=catalog,
        infrastructure=infrastructure,
        application=application,
        placement=placement,
        base_path=str(args.base),
    )
    optimizer = ExhaustiveOrToolsOptimizer(catalog, wrapper)
    result = optimizer.optimize(
        initial_state,
        args.budget,
        max_time_seconds=args.max_seconds,
        max_solutions=args.max_solutions,
    )

    print("\n" + "=" * 72)
    print("RICERCA ESAUSTIVA OR-TOOLS + SECFOG")
    print("=" * 72)
    print(f"Placement                    : {placement.get('name')}")
    print(f"Stato ricerca                : {result.solver_status}")
    print(f"Enumerazione completa        : {'si' if result.completed else 'no'}")
    print(f"Configurazioni teoriche      : {result.configuration_upper_bound}")
    print(f"Configurazioni ammissibili   : {result.feasible_solutions}")
    print(f"Score iniziale               : {result.initial_score:.8f}")
    print(f"Score migliore               : {result.final_score:.8f}")
    print(f"Costo netto                  : {result.net_cost:+d}")
    print(f"Budget residuo               : {result.remaining_budget}")
    print(f"Valutazioni reali ProbLog    : {wrapper.solver_evaluations}")
    print(f"Tempo                        : {result.elapsed_seconds:.3f} s")
    print("-" * 72)
    print("Policy finale (transizioni adiacenti):")
    policy = build_adjacent_policy(initial_state, result.final_state, catalog)
    if policy:
        for action in policy:
            print(action)
    else:
        print("Nessuna modifica.")
    print("=" * 72)

    if not result.completed:
        print(
            "ATTENZIONE: la ricerca e' stata interrotta; la soluzione "
            "mostrata e' la migliore trovata, ma non e' certificata ottima."
        )


if __name__ == "__main__":
    main()
