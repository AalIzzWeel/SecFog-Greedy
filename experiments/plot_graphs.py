import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


# ============================================================
# PATH E COSTANTI
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUT_DIR = RESULTS_DIR / "plots"
CSV_PATTERN = "fast_benchmark_thesis_*.csv"

APPROACH_ORDER = (
    "upgrade-then-downgrade",
    "downgrade-then-upgrade",
)

APPROACH_LABELS = {
    "upgrade-then-downgrade": "Upgrade-then-downgrade",
    "downgrade-then-upgrade": "Downgrade-then-upgrade",
}


# ============================================================
# CONFIGURAZIONE GRAFICA
# ============================================================

plt.rcParams.update(
    {
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "legend.fontsize": 9,
        "legend.title_fontsize": 10,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "lines.linewidth": 1.8,
    }
)


# ============================================================
# UTILITA'
# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Genera i grafici comparativi dei due approcci del Fast Greedy."
        )
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help=(
            "CSV da elaborare. Se omesso, viene usato il benchmark thesis "
            "modificato piu' recentemente nella cartella results."
        ),
    )
    return parser.parse_args()


def get_latest_csv() -> Path:
    """Restituisce il benchmark thesis modificato piu' recentemente."""
    csv_files = sorted(
        RESULTS_DIR.glob(CSV_PATTERN),
        key=lambda path: path.stat().st_mtime,
    )

    if not csv_files:
        raise FileNotFoundError(
            f"Nessun file '{CSV_PATTERN}' trovato in {RESULTS_DIR}"
        )

    return csv_files[-1]


def resolve_csv_path(argument: Path | None) -> Path:
    if argument is None:
        return get_latest_csv()

    csv_path = argument.expanduser().resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV non trovato: {csv_path}")
    return csv_path


def validate_columns(df: pd.DataFrame) -> None:
    """Controlla struttura e valori principali del CSV."""
    required_columns = {
        "approach",
        "infrastructure_nodes",
        "budget",
        "elapsed_seconds",
        "problog_evaluations",
        "final_score",
        "log_gain",
        "greedy_steps",
        "reallocation_steps",
        "state_pairs",
    }

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            "Nel CSV mancano le seguenti colonne: "
            + ", ".join(sorted(missing))
        )

    approaches = set(df["approach"].unique())
    expected = set(APPROACH_ORDER)
    if approaches != expected:
        raise ValueError(
            "La colonna 'approach' deve contenere esattamente: "
            + ", ".join(APPROACH_ORDER)
        )

    if (df["final_score"] <= 0).any():
        raise ValueError(
            "Gli score finali devono essere positivi per la scala logaritmica."
        )


def save_figure(fig, filename: str) -> None:
    """Salva un grafico vettoriale PDF adatto alla tesi."""
    output_path = OUTPUT_DIR / filename
    fig.savefig(output_path, bbox_inches="tight")
    print(f"Grafico salvato: {output_path}")
    plt.close(fig)


def compute_summary(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Calcola media e deviazione standard sui seed."""
    return (
        df.groupby(
            ["approach", "infrastructure_nodes", "budget"],
            as_index=False,
        )
        .agg(mean=(column, "mean"), std=(column, "std"))
        .sort_values(
            ["approach", "budget", "infrastructure_nodes"]
        )
    )


def build_budget_colors(df: pd.DataFrame) -> dict[int, tuple]:
    budgets = sorted(int(value) for value in df["budget"].unique())
    color_map = plt.get_cmap("viridis")
    positions = np.linspace(0.08, 0.92, len(budgets))
    return {
        budget: color_map(position)
        for budget, position in zip(budgets, positions)
    }


def create_comparison_axes() -> tuple:
    fig, axes = plt.subplots(
        1,
        len(APPROACH_ORDER),
        figsize=(13, 5.2),
        sharex=True,
        sharey=True,
    )
    return fig, np.atleast_1d(axes)


def finish_comparison_figure(
    fig,
    axes,
    title: str,
    budget_colors: dict[int, tuple],
    extra_handles: list | None = None,
) -> None:
    """Aggiunge titolo e legenda comuni ai due pannelli."""
    handles = [
        Line2D(
            [0],
            [0],
            color=color,
            marker="o",
            markersize=5,
            label=str(budget),
        )
        for budget, color in budget_colors.items()
    ]
    if extra_handles:
        handles.extend(extra_handles)

    fig.suptitle(title, fontsize=15, y=0.99)
    fig.legend(
        handles=handles,
        title="Budget",
        loc="upper center",
        bbox_to_anchor=(0.5, 0.93),
        ncol=len(handles),
        frameon=True,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.82))
    fig.subplots_adjust(wspace=0.08)


def plot_metric_by_nodes(
    df: pd.DataFrame,
    column: str,
    ylabel: str,
    title: str,
    filename: str,
    start_from_zero: bool = True,
) -> None:
    """Confronta una metrica nei due approcci, separati per pannello."""
    summary = compute_summary(df, column)
    budget_colors = build_budget_colors(df)
    nodes = sorted(int(value) for value in df["infrastructure_nodes"].unique())
    fig, axes = create_comparison_axes()

    for ax, approach in zip(axes, APPROACH_ORDER):
        approach_summary = summary[summary["approach"] == approach]

        for budget, group in approach_summary.groupby("budget"):
            budget = int(budget)
            ax.errorbar(
                group["infrastructure_nodes"],
                group["mean"],
                yerr=group["std"],
                color=budget_colors[budget],
                marker="o",
                markersize=5,
                capsize=3,
            )

        ax.set_title(APPROACH_LABELS[approach])
        ax.set_xlabel("Numero di nodi dell'infrastruttura")
        ax.set_xticks(nodes)
        ax.grid(True, alpha=0.3)

    axes[0].set_ylabel(ylabel)
    if start_from_zero:
        axes[0].set_ylim(bottom=0)
    finish_comparison_figure(fig, axes, title, budget_colors)
    save_figure(fig, filename)


# ============================================================
# 1. SCORE FINALE
# ============================================================


def plot_final_score(df: pd.DataFrame) -> None:
    """Confronta lo score finale su una scala logaritmica in base 10."""
    plot_df = df.copy()
    plot_df["log10_final_score"] = np.log10(plot_df["final_score"])

    plot_metric_by_nodes(
        df=plot_df,
        column="log10_final_score",
        ylabel=r"Media di $\log_{10}(score\ finale)$",
        title="Score finale di sicurezza",
        filename="final_score_scalability.pdf",
        start_from_zero=False,
    )


# ============================================================
# 2. RUNTIME
# ============================================================


def plot_runtime(df: pd.DataFrame) -> None:
    plot_metric_by_nodes(
        df=df,
        column="elapsed_seconds",
        ylabel="Tempo medio di esecuzione (s)",
        title="Tempo di esecuzione del Fast Greedy",
        filename="runtime_scalability.pdf",
    )


# ============================================================
# 3. VALUTAZIONI PROBLOG
# ============================================================


def plot_problog_evaluations(df: pd.DataFrame) -> None:
    plot_metric_by_nodes(
        df=df,
        column="problog_evaluations",
        ylabel="Numero medio di valutazioni ProbLog",
        title="Valutazioni reali dell'oracolo ProbLog",
        filename="problog_evaluations_scalability.pdf",
    )


# ============================================================
# 4. LOG GAIN
# ============================================================


def plot_log_gain(df: pd.DataFrame) -> None:
    plot_metric_by_nodes(
        df=df,
        column="log_gain",
        ylabel="Log gain medio dello score",
        title="Miglioramento dello score di sicurezza",
        filename="log_gain_scalability.pdf",
    )


# ============================================================
# 5. PASSI GREEDY
# ============================================================


def plot_greedy_steps(df: pd.DataFrame) -> None:
    plot_metric_by_nodes(
        df=df,
        column="greedy_steps",
        ylabel="Numero medio di passi greedy",
        title="Numero di passi del Fast Greedy",
        filename="greedy_steps_scalability.pdf",
    )


# ============================================================
# 6. RIALLOCAZIONI
# ============================================================


def plot_reallocation_steps(df: pd.DataFrame) -> None:
    plot_metric_by_nodes(
        df=df,
        column="reallocation_steps",
        ylabel="Numero medio di riallocazioni",
        title="Riallocazioni del budget durante l'ottimizzazione",
        filename="reallocation_steps_scalability.pdf",
    )


# ============================================================
# 7. STATE PAIRS VS RUNTIME
# ============================================================


def plot_runtime_vs_state_pairs(df: pd.DataFrame) -> None:
    """
    Confronta la relazione tra dimensione dello stato e runtime.

    Il fit quadratico e' descrittivo e non rappresenta una stima
    della complessita' asintotica.
    """
    budget_colors = build_budget_colors(df)
    fig, axes = create_comparison_axes()

    for ax, approach in zip(axes, APPROACH_ORDER):
        approach_df = df[df["approach"] == approach]

        for budget, group in approach_df.groupby("budget"):
            budget = int(budget)
            ax.scatter(
                group["state_pairs"],
                group["elapsed_seconds"],
                color=budget_colors[budget],
                s=38,
                alpha=0.8,
            )

        x = approach_df["state_pairs"].to_numpy(dtype=float)
        y = approach_df["elapsed_seconds"].to_numpy(dtype=float)
        correlation = np.corrcoef(x, y)[0, 1]
        coefficients = np.polyfit(x, y, 2)
        x_fit = np.linspace(x.min(), x.max(), 300)
        y_fit = np.polyval(coefficients, x_fit)
        y_predicted = np.polyval(coefficients, x)
        residual_sum = np.sum((y - y_predicted) ** 2)
        total_sum = np.sum((y - np.mean(y)) ** 2)
        r_squared = (
            1 - residual_sum / total_sum
            if total_sum > 0
            else float("nan")
        )

        ax.plot(
            x_fit,
            y_fit,
            color="black",
            linestyle="--",
            linewidth=1.8,
        )

        ax.text(
            0.04,
            0.96,
            (
                f"Pearson r = {correlation:.3f}\n"
                f"Fit quadratico $R^2$ = {r_squared:.3f}"
            ),
            transform=ax.transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "alpha": 0.15},
        )

        ax.set_title(APPROACH_LABELS[approach])
        ax.set_xlabel("Numero di coppie nodo-contromisura")
        ax.grid(True, alpha=0.3)

    axes[0].set_ylabel("Tempo di esecuzione (s)")
    axes[0].set_ylim(bottom=0)
    fit_handle = Line2D(
        [0],
        [0],
        color="black",
        linestyle="--",
        label="Fit quadratico",
    )
    finish_comparison_figure(
        fig,
        axes,
        "Tempo di esecuzione rispetto alla dimensione dello stato",
        budget_colors,
        extra_handles=[fit_handle],
    )
    save_figure(fig, "runtime_vs_state_pairs.pdf")


# ============================================================
# MAIN
# ============================================================


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = resolve_csv_path(args.csv)

    print("=" * 72)
    print("GENERAZIONE GRAFICI COMPARATIVI FAST GREEDY")
    print("=" * 72)
    print(f"CSV utilizzato : {csv_path}")
    print(f"Cartella output: {OUTPUT_DIR}")

    df = pd.read_csv(csv_path)
    validate_columns(df)

    print(f"Run caricati    : {len(df)}")
    print(
        "Approcci        : "
        + ", ".join(APPROACH_LABELS[value] for value in APPROACH_ORDER)
    )
    print(
        "Nodi            : "
        + str(sorted(int(value) for value in df["infrastructure_nodes"].unique()))
    )
    print(
        "Budget          : "
        + str(sorted(int(value) for value in df["budget"].unique()))
    )
    print("-" * 72)

    plot_final_score(df)
    plot_runtime(df)
    plot_problog_evaluations(df)
    plot_log_gain(df)
    plot_greedy_steps(df)
    plot_reallocation_steps(df)
    plot_runtime_vs_state_pairs(df)

    print("=" * 72)
    print("Generazione completata.")
    print("=" * 72)


if __name__ == "__main__":
    main()
