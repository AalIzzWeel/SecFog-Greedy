import argparse
import csv
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from model.comparison_generator import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PROFILES_PATH,
    DEFAULT_SCENARIOS,
    generate_comparison_instances,
    save_comparison_instance,
)
from optimizer.utils import (
    create_initial_state,
    load_application,
    load_catalog,
    load_infrastructure,
    load_json,
    load_placement,
)
from scoring.score_wrapper import ScoreWrapper
from src.exhaustive_or_tools import ExhaustiveOrToolsOptimizer
from src.fast_greedy import (
    FastGreedyOptimizer,
    build_downgrade_then_upgrade_input,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_PATH = PROJECT_ROOT / "prolog" / "secfog_base.pl"
RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_BUDGETS = (0, 100, 300, 400)
APPROACHES = (
    "upgrade-then-downgrade",
    "downgrade-then-upgrade",
)
EPSILON = 1e-12


@dataclass(frozen=True)
class ComparisonResult:
    instance: str
    scenario: str
    nodes: int
    services: int
    state_pairs: int
    budget: int
    approach: str

    initial_score: float
    exhaustive_score: float
    greedy_score: float
    absolute_gap: float | None
    relative_gap_percent: float | None
    optimal_hit: bool | None

    exhaustive_completed: bool
    exhaustive_status: str
    theoretical_configurations: int
    feasible_configurations: int

    greedy_net_cost: int
    greedy_remaining_budget: int
    greedy_steps: int
    greedy_reallocations: int

    exhaustive_problog_evaluations: int
    greedy_problog_evaluations: int
    exhaustive_seconds: float
    greedy_seconds: float
    speedup: float | None


def _load_instance(
    instance_dir: Path,
) -> tuple[dict, dict, dict, dict, dict]:
    return (
        load_catalog(instance_dir / "catalog.json"),
        load_infrastructure(instance_dir / "infrastructure.json"),
        load_application(instance_dir / "application.json"),
        load_placement(instance_dir / "placement.json"),
        load_json(instance_dir / "metadata.json"),
    )


def _run_greedy(
    catalog: dict,
    infrastructure: dict,
    application: dict,
    placement: dict,
    original_state,
    budget: int,
    approach: str,
) -> dict:
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

    operating_state = original_state.copy()
    effective_budget = budget
    started_at = time.perf_counter()
    if approach == "downgrade-then-upgrade":
        operating_state, effective_budget = (
            build_downgrade_then_upgrade_input(
                operating_state, budget, optimizer.costs
            )
        )

    final_state, _, final_score, history = optimizer.optimize(
        operating_state, effective_budget
    )
    elapsed_seconds = time.perf_counter() - started_at
    net_cost = optimizer.costs.calculate_net_cost(
        original_state, final_state
    )

    return {
        "final_score": final_score,
        "net_cost": net_cost,
        "remaining_budget": budget - net_cost,
        "steps": len(history),
        "reallocations": sum(step.is_reallocation for step in history),
        "problog_evaluations": wrapper.solver_evaluations,
        "elapsed_seconds": elapsed_seconds,
    }


def run_instance(
    instance_dir: Path,
    budgets: list[int],
    *,
    max_exhaustive_seconds: float | None = None,
) -> list[ComparisonResult]:
    catalog, infrastructure, application, placement, metadata = (
        _load_instance(instance_dir)
    )
    initial_state = create_initial_state(
        catalog, infrastructure, placement
    )
    rows = []

    for budget in budgets:
        if budget < 0:
            raise ValueError("I budget devono essere non negativi.")

        exhaustive_wrapper = ScoreWrapper(
            catalog=catalog,
            infrastructure=infrastructure,
            application=application,
            placement=placement,
            base_path=str(BASE_PATH),
        )
        initial_score = exhaustive_wrapper.evaluate(initial_state)
        exhaustive = ExhaustiveOrToolsOptimizer(
            catalog, exhaustive_wrapper
        ).optimize(
            initial_state,
            budget,
            max_time_seconds=max_exhaustive_seconds,
        )

        for approach in APPROACHES:
            greedy = _run_greedy(
                catalog,
                infrastructure,
                application,
                placement,
                initial_state,
                budget,
                approach,
            )

            absolute_gap = None
            relative_gap = None
            optimal_hit = None
            if exhaustive.completed:
                absolute_gap = max(
                    0.0,
                    exhaustive.final_score - greedy["final_score"],
                )
                if exhaustive.final_score > 0:
                    relative_gap = (
                        absolute_gap / exhaustive.final_score * 100.0
                    )
                optimal_hit = absolute_gap <= EPSILON

            speedup = None
            if greedy["elapsed_seconds"] > 0:
                speedup = (
                    exhaustive.elapsed_seconds
                    / greedy["elapsed_seconds"]
                )

            rows.append(
                ComparisonResult(
                    instance=instance_dir.name,
                    scenario=str(metadata["scenario"]),
                    nodes=int(metadata["nodes"]),
                    services=int(metadata["services"]),
                    state_pairs=int(metadata["state_pairs"]),
                    budget=budget,
                    approach=approach,
                    initial_score=initial_score,
                    exhaustive_score=exhaustive.final_score,
                    greedy_score=greedy["final_score"],
                    absolute_gap=absolute_gap,
                    relative_gap_percent=relative_gap,
                    optimal_hit=optimal_hit,
                    exhaustive_completed=exhaustive.completed,
                    exhaustive_status=exhaustive.solver_status,
                    theoretical_configurations=(
                        exhaustive.configuration_upper_bound
                    ),
                    feasible_configurations=(
                        exhaustive.feasible_solutions
                    ),
                    greedy_net_cost=greedy["net_cost"],
                    greedy_remaining_budget=(
                        greedy["remaining_budget"]
                    ),
                    greedy_steps=greedy["steps"],
                    greedy_reallocations=greedy["reallocations"],
                    exhaustive_problog_evaluations=(
                        exhaustive_wrapper.solver_evaluations
                    ),
                    greedy_problog_evaluations=(
                        greedy["problog_evaluations"]
                    ),
                    exhaustive_seconds=exhaustive.elapsed_seconds,
                    greedy_seconds=greedy["elapsed_seconds"],
                    speedup=speedup,
                )
            )

    return rows


def _save_results(
    rows: list[ComparisonResult],
) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = RESULTS_DIR / f"comparison_family_{timestamp}.csv"
    json_path = RESULTS_DIR / f"comparison_family_{timestamp}.json"
    dictionaries = [asdict(row) for row in rows]

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(dictionaries, file, indent=2, ensure_ascii=False)
    return csv_path, json_path


def _print_result(row: ComparisonResult) -> None:
    gap = (
        f"{row.relative_gap_percent:.2f}%"
        if row.relative_gap_percent is not None
        else "n/a"
    )
    print(
        f"{row.scenario} | budget={row.budget} | {row.approach} | "
        f"opt={row.exhaustive_score:.8f} | "
        f"greedy={row.greedy_score:.8f} | gap={gap} | "
        f"hit={row.optimal_hit} | "
        f"eval={row.exhaustive_problog_evaluations}/"
        f"{row.greedy_problog_evaluations}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Confronta esaustivo e Fast Greedy su una famiglia di "
            "piccole istanze realistiche edge-cloud."
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
        "--instances-dir", type=Path, default=DEFAULT_OUTPUT_DIR
    )
    parser.add_argument(
        "--budgets",
        type=int,
        nargs="+",
        default=list(DEFAULT_BUDGETS),
    )
    parser.add_argument("--max-exhaustive-seconds", type=float)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    instances = generate_comparison_instances(
        args.scenarios,
        catalog_path=args.catalog,
        profiles_path=args.profiles,
    )
    rows = []
    for instance in instances:
        instance_dir = save_comparison_instance(
            instance, args.instances_dir
        )
        print(f"\nIstanza: {instance_dir.name}")
        rows.extend(
            run_instance(
                instance_dir,
                args.budgets,
                max_exhaustive_seconds=args.max_exhaustive_seconds,
            )
        )
    for row in rows:
        _print_result(row)

    if not args.no_save:
        csv_path, json_path = _save_results(rows)
        print(f"CSV : {csv_path}")
        print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
