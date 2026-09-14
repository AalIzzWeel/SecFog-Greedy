import argparse
from pathlib import Path

from optimizer.profiler import Profiler
from optimizer.utils import (
    create_initial_state,
    display_solution_summary,
    load_application,
    load_catalog,
    load_infrastructure,
    load_placement,
)
from scoring.score_wrapper import ScoreWrapper
from src.fast_greedy import FastGreedyOptimizer


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_CATALOG = (
    PROJECT_ROOT
    / "model"
    / "security_catalog.json"
)

DEFAULT_INSTANCE = (
    PROJECT_ROOT
    / "model"
    / "generated"
    / "instance_n25_s5_seed42"
)

DEFAULT_INFRASTRUCTURE = (
    DEFAULT_INSTANCE
    / "infrastructure.json"
)

DEFAULT_APPLICATION = (
    DEFAULT_INSTANCE
    / "application.json"
)

DEFAULT_PLACEMENT = (
    DEFAULT_INSTANCE
    / "placement.json"
)

DEFAULT_BASE = (
    PROJECT_ROOT
    / "prolog"
    / "secfog_base.pl"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Esegue il fast greedy su una istanza "
            "cloud-edge generata."
        )
    )

    parser.add_argument(
        "--budget",
        type=int,
        default=300,
    )

    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
    )

    parser.add_argument(
        "--infrastructure",
        type=Path,
        default=DEFAULT_INFRASTRUCTURE,
    )

    parser.add_argument(
        "--application",
        type=Path,
        default=DEFAULT_APPLICATION,
    )

    parser.add_argument(
        "--placement",
        type=Path,
        default=DEFAULT_PLACEMENT,
    )

    parser.add_argument(
        "--base",
        type=Path,
        default=DEFAULT_BASE,
    )

    parser.add_argument(
        "--reversal-policy",
        choices=("allow", "forbid"),
        default="allow",
        help=(
            "Consente oppure vieta il downgrade "
            "di capability migliorate in passi precedenti."
        ),
    )

    args = parser.parse_args()

    catalog = load_catalog(
        args.catalog
    )

    infrastructure = load_infrastructure(
        args.infrastructure
    )

    application = load_application(
        args.application
    )

    placement = load_placement(
        args.placement
    )

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
        base_path=str(args.base),
    )

    optimizer = FastGreedyOptimizer(
        catalog=catalog,
        application=application,
        placement=placement,
        score_wrapper=wrapper,
        allow_reversal=(
            args.reversal_policy == "allow"
        ),
    )

    (
        final_state,
        remaining_budget,
        final_score,
        history,
    ) = optimizer.optimize(
        initial_state,
        args.budget,
    )

    print("\n" + "=" * 90)

    print(
        "PLACEMENT: "
        f"{placement.get('name', args.placement.stem)}"
    )

    print(
        "Politica reversal: "
        f"{args.reversal_policy}"
    )

    print(
        f"Score iniziale : "
        f"{optimizer.initial_score:.8f}"
    )

    print(
        f"Score finale   : "
        f"{final_score:.8f}"
    )

    print(
        f"Passi          : "
        f"{len(history)}"
    )

    print("=" * 90)

    for step in history:
        description = (
            f"{step.downgrade} + {step.action}"
            if step.is_reallocation
            else str(step.action)
        )

        print(
            f"{step.step_number:2d}. "
            f"{description} | "
            f"costo_netto={step.cost:+4d} | "
            f"beneficio={step.benefit:+.8f} | "
            f"efficienza={step.efficiency:.10f} | "
            f"priorita_nodo={step.node_priority:.8f}"
        )

    display_solution_summary(
        initial_state,
        final_state,
        final_score,
        args.budget,
        remaining_budget,
    )

    print(
        "Valutazioni reali ProbLog: "
        f"{wrapper.solver_evaluations}"
    )

    #Profiler.report()


if __name__ == "__main__":
    main()