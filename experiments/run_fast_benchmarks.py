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
from src.fast_greedy import FastGreedyOptimizer


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
    reversal_policy: str

    infrastructure_nodes: int
    used_nodes: int
    services: int

    state_pairs: int
    active_initial: int
    inactive_initial: int

    budget: int

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
    reversal_policy: str,
) -> tuple[FastBenchmarkResult, dict]:

    initial_state = create_initial_state(
        catalog,
        infrastructure,
        placement,
    )

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
        allow_reversal=(
            reversal_policy == "allow"
        ),
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
        budget,
    )

    elapsed_seconds = (
        time.perf_counter() - start
    )

    initial_score = optimizer.initial_score

    if initial_score is None:
        raise RuntimeError(
            "Lo score iniziale non è stato calcolato."
        )

    final_policy = build_final_policy(
        initial_state,
        final_state,
    )

    total, active, inactive = (
        initial_state.count_summary()
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

    net_cost = (
        budget - remaining_budget
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
        reversal_policy=reversal_policy,

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
                "downgrade": (
                    str(step.downgrade)
                    if step.downgrade is not None
                    else None
                ),
                "action": str(step.action),
                "net_cost": step.cost,
                "benefit": step.benefit,
                "efficiency": (
                    step.efficiency
                    if math.isfinite(
                        step.efficiency
                    )
                    else None
                ),
                "node_priority": (
                    step.node_priority
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
        f"| reversal={result.reversal_policy}"
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
        "--reversal-policies",
        nargs="+",
        choices=[
            "allow",
            "forbid",
        ],
        default=["allow"],
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
        "Reversal: "
        + ", ".join(
            args.reversal_policies
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
            for reversal_policy in (
                args.reversal_policies
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
                    reversal_policy=(
                        reversal_policy
                    ),
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
