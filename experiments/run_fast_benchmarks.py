import argparse
import csv
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

#from optimizer.profiler import Profiler
from optimizer.utils import (
    build_final_policy,
    create_initial_state,
    get_placement_nodes,
    load_application,
    load_catalog,
    load_infrastructure,
    load_placement,
)
from scoring.score_wrapper import ScoreWrapper
from src.fast_greedy import FastGreedyOptimizer, build_downgrade_then_upgrade_input


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CATALOG_PATH = (
    PROJECT_ROOT
    / "model"
    / "security_catalog.json"
)

BASE_PATH = (
    PROJECT_ROOT
    / "prolog"
    / "secfog_base.pl"
)

GENERATED_DIR = (
    PROJECT_ROOT
    / "model"
    / "generated"
)

RESULTS_DIR = (
    PROJECT_ROOT
    / "results"
)


QUICK_INSTANCES = [
    "instance_n25_s5_seed42",
    "instance_n50_s10_seed42",
]

THESIS_SEEDS = (
    42,
    123,
    999,
)

THESIS_CONFIGS = (
    (25, 5),
    (50, 10),
    (100, 15),
    (200, 25),
    (400, 50),
)

THESIS_INSTANCES = [
    (
        f"instance_n{nodes}"
        f"_s{services}"
        f"_seed{seed}"
    )
    for nodes, services in THESIS_CONFIGS
    for seed in THESIS_SEEDS
]

QUICK_BUDGETS = [
    0,
    300,
]

THESIS_BUDGETS = [
    0,
    100,
    300,
    600,
    1000,
]


def get_instance_seed(
    instance_name: str,
) -> int:
    """Estrae il seed dal nome dell'istanza."""
    marker = "_seed"

    if marker not in instance_name:
        raise ValueError(
            f"Seed non presente nel nome istanza: {instance_name}"
        )

    return int(
        instance_name.rsplit(
            marker,
            1,
        )[1]
    )


@dataclass
class FastBenchmarkResult:
    instance: str
    seed: int
    placement: str
    approach: str

    infrastructure_nodes: int
    used_nodes: int
    services: int

    state_pairs: int
    active_initial: int
    inactive_initial: int

    budget: int
    effective_budget: int

    initial_score: float
    final_score: float
    delta_score: float
    log_gain: float | None
    relative_improvement_percent: float

    net_cost: int
    remaining_budget: int

    greedy_steps: int
    reallocation_steps: int
    final_policy_actions: int

    problog_evaluations: int
    wrapper_cache_size: int

    elapsed_seconds: float


def run_experiment(
    catalog: dict,
    infrastructure: dict,
    application: dict,
    placement: dict,
    instance_name: str,
    budget: int,
    approach: str,
) -> tuple[FastBenchmarkResult, dict]:

    original_initial_state = create_initial_state(
        catalog,
        infrastructure,
        placement,
    )

    initial_state = original_initial_state.copy()

    wrapper = ScoreWrapper(
        catalog=catalog,
        infrastructure=infrastructure,
        application=application,
        placement=placement,
        base_path=str(BASE_PATH),
    )

    optimizer = FastGreedyOptimizer(
        catalog=catalog,
        application=application,
        placement=placement,
        score_wrapper=wrapper,
    )

    # Le metriche di qualita' devono usare la stessa baseline P0 per
    # entrambi gli approcci. Downgrade-then-upgrade modifica infatti lo
    # stato di partenza operativo portandolo a L0, ma questo stato non e'
    # il placement iniziale dell'istanza.
    reference_initial_score: float | None = None

    effective_budget = budget
    if approach == "downgrade-then-upgrade":
        reference_wrapper = ScoreWrapper(
            catalog=catalog,
            infrastructure=infrastructure,
            application=application,
            placement=placement,
            base_path=str(BASE_PATH),
        )
        reference_initial_score = reference_wrapper.evaluate(
            original_initial_state
        )

        initial_state, effective_budget = build_downgrade_then_upgrade_input(
            initial_state, budget, optimizer.costs
        )

    #Profiler.reset()
    start = time.perf_counter()

    (
        final_state,
        remaining_budget,
        final_score,
        history,
    ) = optimizer.optimize(
        initial_state,
        effective_budget,
    )

    elapsed_seconds = (
        time.perf_counter() - start
    )

    optimizer_initial_score = optimizer.initial_score

    if optimizer_initial_score is None:
        raise RuntimeError(
            "Lo score iniziale non è stato calcolato."
        )

    initial_score = (
        reference_initial_score
        if reference_initial_score is not None
        else optimizer_initial_score
    )

    final_policy = build_final_policy(
        original_initial_state,
        final_state,
    )

    total, active, inactive = (
        original_initial_state.count_summary()
    )

    delta_score = (
        final_score - initial_score
    )

    relative_improvement = 0.0

    if initial_score > 0:
        relative_improvement = (
            delta_score
            / initial_score
            * 100.0
        )

    log_gain = None

    if (
        initial_score > 0
        and final_score > 0
    ):
        log_gain = math.log10(
            final_score / initial_score
        )

    net_cost = optimizer.costs.calculate_net_cost(
        original_initial_state,
        final_state,
    )

    reallocation_steps = sum(
        step.is_reallocation
        for step in history
    )

    placement_name = placement.get(
        "name",
        "placement",
    )

    result = FastBenchmarkResult(
        instance=instance_name,
        seed=get_instance_seed(instance_name),
        placement=placement_name,
        approach=approach,

        infrastructure_nodes=len(
            infrastructure.get("nodes", {})
        ),
        used_nodes=len(
            get_placement_nodes(placement)
        ),
        services=len(
            application.get("services", {})
        ),

        state_pairs=total,
        active_initial=active,
        inactive_initial=inactive,

        budget=budget,
        effective_budget=effective_budget,

        initial_score=initial_score,
        final_score=final_score,
        delta_score=delta_score,
        log_gain=log_gain,
        relative_improvement_percent=(
            relative_improvement
        ),

        net_cost=net_cost,
        remaining_budget=remaining_budget,

        greedy_steps=len(history),
        reallocation_steps=reallocation_steps,
        final_policy_actions=len(final_policy),

        problog_evaluations=(
            wrapper.solver_evaluations
        ),
        wrapper_cache_size=wrapper.cache_size,

        elapsed_seconds=elapsed_seconds,
    )

    details = {
        "result": asdict(result),
        "history": [
            {
                "step": step.step_number,
                "downgrades": [
                    str(action) for action in step.downgrades
                ],
                "action": str(step.action),
                "net_cost": step.cost,
                "specific_quality": step.specific_quality,
                "efficiency": (
                    step.efficiency
                    if math.isfinite(
                        step.efficiency
                    )
                    else None
                ),
                "remaining_budget": (
                    step.remaining_budget
                ),
            }
            for step in history
        ],
        "final_policy": [
            str(action)
            for action in final_policy
        ],
    }

    return result, details


def print_result(
    result: FastBenchmarkResult,
) -> None:

    print("\n" + "=" * 90)

    print(
        f"{result.instance} "
        f"| budget={result.budget} "
        f"| approach={result.approach}"
    )

    print("=" * 90)

    print(
        f"Nodi infrastruttura  : "
        f"{result.infrastructure_nodes}"
    )
    print(
        f"Nodi usati           : "
        f"{result.used_nodes}"
    )
    print(
        f"Servizi              : "
        f"{result.services}"
    )
    print(
        f"Coppie stato         : "
        f"{result.state_pairs}"
    )
    print(
        f"Score iniziale       : "
        f"{result.initial_score:.6e}"
    )
    print(
        f"Score finale         : "
        f"{result.final_score:.6e}"
    )
    print(
        f"Delta score          : "
        f"{result.delta_score:+.6e}"
    )
    print(
        f"Log gain             : "
        + (
            f"{result.log_gain:+.3f}"
            if result.log_gain is not None
            else "n/a"
        )
    )
    print(
        f"Miglioramento %      : "
        f"{result.relative_improvement_percent:+.2f}%"
    )
    print(
        f"Costo netto          : "
        f"{result.net_cost:+d}"
    )
    print(
        f"Budget residuo       : "
        f"{result.remaining_budget}"
    )
    print(
        f"Passi greedy         : "
        f"{result.greedy_steps}"
    )
    print(
        f"Riallocazioni        : "
        f"{result.reallocation_steps}"
    )
    print(
        f"Azioni policy finale : "
        f"{result.final_policy_actions}"
    )
    print(
        f"Valutazioni ProbLog  : "
        f"{result.problog_evaluations}"
    )
    print(
        f"Tempo                : "
        f"{result.elapsed_seconds:.3f} s"
    )


def save_results(
    results: list[FastBenchmarkResult],
    details: list[dict],
    profile_name: str,
) -> tuple[Path, Path]:

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    csv_path = RESULTS_DIR / (
        f"fast_benchmark_"
        f"{profile_name}_"
        f"{timestamp}.csv"
    )

    json_path = RESULTS_DIR / (
        f"fast_benchmark_"
        f"{profile_name}_"
        f"{timestamp}.json"
    )

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(
                asdict(results[0]).keys()
            ),
        )

        writer.writeheader()

        for result in results:
            writer.writerow(
                asdict(result)
            )

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            details,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return csv_path, json_path


def resolve_configuration(
    args,
) -> tuple[list[str], list[int], str]:

    if args.instances or args.budgets:
        instances = (
            args.instances
            or QUICK_INSTANCES
        )

        budgets = (
            args.budgets
            or QUICK_BUDGETS
        )

        return (
            instances,
            budgets,
            "custom",
        )

    if args.profile == "thesis":
        return (
            THESIS_INSTANCES,
            THESIS_BUDGETS,
            "thesis",
        )

    return (
        QUICK_INSTANCES,
        QUICK_BUDGETS,
        "quick",
    )


def load_instance(
    instance_name: str,
) -> tuple[dict, dict, dict]:

    instance_dir = (
        GENERATED_DIR
        / instance_name
    )

    if not instance_dir.exists():
        raise FileNotFoundError(
            f"Istanza non trovata: {instance_dir}"
        )

    infrastructure_path = (
        instance_dir
        / "infrastructure.json"
    )

    application_path = (
        instance_dir
        / "application.json"
    )

    placement_path = (
        instance_dir
        / "placement.json"
    )

    for path in (
        infrastructure_path,
        application_path,
        placement_path,
    ):
        if not path.exists():
            raise FileNotFoundError(
                f"File mancante nell'istanza: {path}"
            )

    infrastructure = load_infrastructure(
        infrastructure_path
    )

    application = load_application(
        application_path
    )

    placement = load_placement(
        placement_path
    )

    return (
        infrastructure,
        application,
        placement,
    )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Esegue i benchmark di scalabilità "
            "del FastGreedyOptimizer."
        )
    )

    parser.add_argument(
        "--profile",
        choices=[
            "quick",
            "thesis",
        ],
        default="quick",
    )

    parser.add_argument(
        "--instances",
        nargs="+",
        help=(
            "Cartelle di istanza presenti in "
            "model/generated."
        ),
    )

    parser.add_argument(
        "--budgets",
        nargs="+",
        type=int,
    )

    parser.add_argument(
        "--approaches",
        nargs="+",
        choices=[
            "upgrade-then-downgrade",
            "downgrade-then-upgrade",
        ],
        default=["upgrade-then-downgrade", "downgrade-then-upgrade"],
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
    )

    args = parser.parse_args()

    (
        instance_names,
        budgets,
        profile_name,
    ) = resolve_configuration(args)

    if any(
        budget < 0
        for budget in budgets
    ):
        parser.error(
            "I budget devono essere non negativi."
        )

    catalog = load_catalog(
        CATALOG_PATH
    )

    results = []
    details = []

    print(
        "\nMATRICE BENCHMARK FAST GREEDY - SCALABILITA"
    )
    print(
        "Istanze : "
        + ", ".join(instance_names)
    )
    print(
        f"Budget  : {budgets}"
    )
    print(
        "Approcci: "
        + ", ".join(
            args.approaches
        )
    )

    for instance_name in instance_names:

        (
            infrastructure,
            application,
            placement,
        ) = load_instance(
            instance_name
        )

        for budget in budgets:
            for approach in (
                args.approaches
            ):

                (
                    result,
                    experiment_details,
                ) = run_experiment(
                    catalog=catalog,
                    infrastructure=infrastructure,
                    application=application,
                    placement=placement,
                    instance_name=instance_name,
                    budget=budget,
                    approach=approach,
                )

                results.append(result)
                details.append(
                    experiment_details
                )

                print_result(
                    result
                )

    if (
        results
        and not args.no_save
    ):
        (
            csv_path,
            json_path,
        ) = save_results(
            results,
            details,
            profile_name,
        )

        print("\nRisultati salvati:")
        print(
            f"- CSV  : {csv_path}"
        )
        print(
            f"- JSON : {json_path}"
        )


if __name__ == "__main__":
    main()
