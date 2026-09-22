import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_OUTPUT_DIR = RESULTS_DIR / "comparison_plots"

APPROACH_ORDER = (
    "upgrade-then-downgrade",
    "downgrade-then-upgrade",
)
APPROACH_LABELS = {
    "upgrade-then-downgrade": "Upgrade-then-downgrade",
    "downgrade-then-upgrade": "Downgrade-then-upgrade",
}
APPROACH_COLORS = {
    "upgrade-then-downgrade": "#0072B2",
    "downgrade-then-upgrade": "#D55E00",
}
APPROACH_MARKERS = {
    "upgrade-then-downgrade": "s",
    "downgrade-then-upgrade": "^",
}
EXACT_COLOR = "#222222"


plt.rcParams.update(
    {
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "legend.fontsize": 9,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "lines.linewidth": 1.9,
        "figure.dpi": 120,
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Genera i grafici medi del confronto rispetto al budget."
        )
    )
    parser.add_argument("--csv", type=Path)
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR
    )
    return parser.parse_args()


def latest_csv(
    pattern: str = "comparison_family_*.csv",
) -> Path:
    matches = sorted(
        RESULTS_DIR.glob(pattern), key=lambda path: path.stat().st_mtime
    )
    if not matches:
        raise FileNotFoundError(
            f"Nessun file '{pattern}' trovato in {RESULTS_DIR}."
        )
    return matches[-1]


def resolve_csv(argument: Path | None) -> Path:
    path = argument if argument is not None else latest_csv()
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"CSV non trovato: {path}")
    return path


def validate_dataframe(df: pd.DataFrame) -> None:
    required = {
        "instance",
        "scenario",
        "nodes",
        "services",
        "state_pairs",
        "budget",
        "approach",
        "exhaustive_score",
        "greedy_score",
        "relative_gap_percent",
        "exhaustive_completed",
        "exhaustive_status",
        "exhaustive_problog_evaluations",
        "greedy_problog_evaluations",
        "exhaustive_seconds",
        "greedy_seconds",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"CSV: colonne mancanti: {', '.join(sorted(missing))}"
        )
    if set(df["approach"]) != set(APPROACH_ORDER):
        raise ValueError("CSV: approcci inattesi.")
    if not df["exhaustive_completed"].all():
        raise ValueError("CSV: sono presenti ricerche incomplete.")
    if set(df["exhaustive_status"]) != {"OPTIMAL"}:
        raise ValueError("CSV: stato esaustivo non ottimo.")
    if df.duplicated(["instance", "budget", "approach"]).any():
        raise ValueError(
            "CSV: righe duplicate per istanza, budget e approccio."
        )

    expected = len(APPROACH_ORDER)
    rows_per_run = df.groupby(["instance", "budget"]).size()
    if not (rows_per_run == expected).all():
        raise ValueError(
            "CSV: ogni istanza e budget devono contenere entrambi "
            "gli approcci."
        )

    instances_per_budget = df.groupby("budget")["instance"].nunique()
    if instances_per_budget.nunique() != 1:
        raise ValueError(
            "CSV: ogni budget deve contenere lo stesso numero di istanze."
        )


def setup_axis(ax, budgets: list[int], ylabel: str) -> None:
    ax.set_xlabel("Budget")
    ax.set_ylabel(ylabel)
    ax.set_xticks(budgets)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(True, alpha=0.28)


def save_figure(fig, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{stem}.pdf"
    png_path = output_dir / f"{stem}.png"
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Grafico salvato: {pdf_path}")


def aggregate_values(
    df: pd.DataFrame, value: str
) -> pd.DataFrame:
    result = (
        df.groupby("budget")[value]
        .agg(mean="mean", std="std")
        .reset_index()
        .sort_values("budget")
    )
    result["std"] = result["std"].fillna(0.0)
    return result


def exact_values(
    df: pd.DataFrame, value: str
) -> pd.DataFrame:
    unique = df.drop_duplicates(["instance", "budget"])
    return aggregate_values(unique, value)


def approach_values(
    df: pd.DataFrame, approach: str, value: str
) -> pd.DataFrame:
    return aggregate_values(
        df[df["approach"] == approach], value
    )


def plot_mean_and_std(
    ax,
    values: pd.DataFrame,
    *,
    color: str,
    marker: str,
    label: str,
    linestyle: str = "-",
    log_scale: bool = False,
    zorder: int | None = None,
) -> None:
    mean = values["mean"]
    std = values["std"]

    if log_scale:
        max_lower_error = (mean - 1e-9).clip(lower=0)
        lower_error = std.where(std <= max_lower_error, max_lower_error)
        yerr = [lower_error, std]
    else:
        yerr = std

    ax.errorbar(
        values["budget"],
        mean,
        yerr=yerr,
        color=color,
        marker=marker,
        linestyle=linestyle,
        label=label,
        capsize=4,
        capthick=1.1,
        elinewidth=1.1,
        zorder=zorder,
    )

def plot_relative_gap(df: pd.DataFrame, output_dir: Path) -> None:
    budgets = sorted(int(value) for value in df["budget"].unique())
    fig, ax = plt.subplots(figsize=(7.4, 4.8))

    for approach in APPROACH_ORDER:
        group = approach_values(
            df, approach, "relative_gap_percent"
        )
        plot_mean_and_std(
            ax,
            group,
            color=APPROACH_COLORS[approach],
            marker=APPROACH_MARKERS[approach],
            label=APPROACH_LABELS[approach],
        )

    setup_axis(ax, budgets, "Gap relativo rispetto all'ottimo (%)")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=True)
    fig.tight_layout()
    save_figure(fig, output_dir, "relative_gap_comparison")


def plot_scores(df: pd.DataFrame, output_dir: Path) -> None:
    budgets = sorted(int(value) for value in df["budget"].unique())
    fig, ax = plt.subplots(figsize=(7.4, 4.8))

    exact = exact_values(df, "exhaustive_score")
    plot_mean_and_std(
        ax,
        exact,
        color=EXACT_COLOR,
        marker="o",
        label="Ottimo esaustivo",
        zorder=4,
    )
    for approach in APPROACH_ORDER:
        group = approach_values(df, approach, "greedy_score")
        plot_mean_and_std(
            ax,
            group,
            color=APPROACH_COLORS[approach],
            marker=APPROACH_MARKERS[approach],
            linestyle="--",
            label=APPROACH_LABELS[approach],
        )

    setup_axis(ax, budgets, "Score finale SecFog")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=True)
    fig.tight_layout()
    save_figure(fig, output_dir, "score_comparison")


def plot_problog_evaluations(
    df: pd.DataFrame, output_dir: Path
) -> None:
    budgets = sorted(int(value) for value in df["budget"].unique())
    fig, ax = plt.subplots(figsize=(7.4, 4.8))

    exact = exact_values(df, "exhaustive_problog_evaluations")
    plot_mean_and_std(
        ax,
        exact,
        color=EXACT_COLOR,
        marker="o",
        label="Ricerca esaustiva",
    )
    for approach in APPROACH_ORDER:
        group = approach_values(
            df, approach, "greedy_problog_evaluations"
        )
        plot_mean_and_std(
            ax,
            group,
            color=APPROACH_COLORS[approach],
            marker=APPROACH_MARKERS[approach],
            label=APPROACH_LABELS[approach],
        )

    setup_axis(ax, budgets, "Numero di valutazioni ProbLog")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=True)
    fig.tight_layout()
    save_figure(fig, output_dir, "problog_evaluations_comparison")


def plot_runtime(df: pd.DataFrame, output_dir: Path) -> None:
    budgets = sorted(int(value) for value in df["budget"].unique())
    fig, ax = plt.subplots(figsize=(7.4, 4.8))

    exact = exact_values(df, "exhaustive_seconds")
    plot_mean_and_std(
        ax,
        exact,
        color=EXACT_COLOR,
        marker="o",
        label="Ricerca esaustiva",
        log_scale=True,
    )
    for approach in APPROACH_ORDER:
        group = approach_values(df, approach, "greedy_seconds")
        plot_mean_and_std(
            ax,
            group,
            color=APPROACH_COLORS[approach],
            marker=APPROACH_MARKERS[approach],
            label=APPROACH_LABELS[approach],
            log_scale=True,
        )

    setup_axis(ax, budgets, "Tempo di esecuzione (s, scala log)")
    ax.set_yscale("log")
    ax.legend(frameon=True)
    fig.tight_layout()
    save_figure(fig, output_dir, "runtime_comparison")


def main() -> None:
    args = parse_args()
    csv_path = resolve_csv(args.csv)
    output_dir = args.output_dir.expanduser().resolve()

    dataframe = pd.read_csv(csv_path)
    validate_dataframe(dataframe)

    print("=" * 72)
    print("GRAFICI MEDI CONFRONTO ESAUSTIVO - FAST GREEDY")
    print("=" * 72)
    print(f"CSV        : {csv_path}")
    print(f"Istanze    : {dataframe['instance'].nunique()}")
    print(
        "Scenari   : "
        + ", ".join(sorted(dataframe["scenario"].unique()))
    )
    print("Barre      : media +/- deviazione standard")
    print(f"Output     : {output_dir}")
    print("-" * 72)

    plot_relative_gap(dataframe, output_dir)
    plot_scores(dataframe, output_dir)
    plot_problog_evaluations(dataframe, output_dir)
    plot_runtime(dataframe, output_dir)

    print("=" * 72)
    print("Generazione completata.")


if __name__ == "__main__":
    main()
