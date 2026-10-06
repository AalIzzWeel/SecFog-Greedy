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
        "log_gain_percent",
        "greedy_loop_seconds",
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
    """Salva il grafico esclusivamente in PNG."""
    png_path = (OUTPUT_DIR / filename).with_suffix(".png")
    fig.savefig(png_path, dpi=180, bbox_inches="tight")
    print(f"Grafico salvato: {png_path}")
    plt.close(fig)
GROUP_COLUMNS = ["approach", "infrastructure_nodes", "budget"]

def without_outliers(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Esclude outlier di Tukey per metrica e per scenario (1.5 × IQR)."""
    parts = []
    removed = 0
    for _, group in df.groupby(GROUP_COLUMNS, sort=False):
        values = group[column].dropna()
        if len(values) < 4:
            parts.append(group.loc[values.index])
            continue
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        keep = values.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)
        parts.append(group.loc[keep[keep].index])
        removed += int((~keep).sum())
    print(f"{column}: esclusi {removed} outlier su {len(df)} run "
          "(IQR per approccio, nodi e budget)")
    return pd.concat(parts) if parts else df.iloc[:0]

def compute_summary(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Calcola la sola media dopo il filtro IQR sui seed di ogni scenario."""
    filtered = without_outliers(df, column)
    return (filtered.groupby(GROUP_COLUMNS, as_index=False)
            .agg(mean=(column, "mean"))
            .sort_values(["approach", "budget", "infrastructure_nodes"]))

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
        sharey=False,
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
    #fig.text(0.5, 0.01, "Scale verticali indipendenti nei due pannelli",
           #  ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0.05, 1, 0.82))
    fig.subplots_adjust(wspace=0.24)

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
            ax.plot(
                group["infrastructure_nodes"],
                group["mean"],
                color=budget_colors[budget],
                marker="o",
                markersize=5,
            )
        ax.set_title(APPROACH_LABELS[approach])
        ax.set_xlabel("Numero di nodi dell'infrastruttura")
        ax.set_xticks(nodes)
        ax.tick_params(axis="x", labelrotation=35)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        if start_from_zero:
            ax.set_ylim(bottom=0)
        if column == "reallocation_steps" and approach == "downgrade-then-upgrade" \
                and (approach_summary["mean"] == 0).all():
            ax.set_ylim(0, 1)
            ax.text(0.04, 0.95, "Nessuna riallocazione registrata",
                    transform=ax.transAxes, va="top", fontsize=9)
        if column == "problog_evaluations" and approach == "downgrade-then-upgrade" \
                and approach_summary["mean"].nunique() == 1:
            value = approach_summary["mean"].iloc[0]
            ax.set_ylim(0, max(3, value * 1.3))
            ax.text(0.04, 0.95, f"Valore costante: {value:g}",
                    transform=ax.transAxes, va="top", fontsize=9)
        if approach == "upgrade-then-downgrade" and column in \
                ("problog_evaluations", "reallocation_steps"):
            large = approach_summary[approach_summary["infrastructure_nodes"] >= 400]
            if len(large["infrastructure_nodes"].unique()) >= 2 and \
                    large.groupby("budget")["mean"].nunique().eq(1).all():
                label = ("400–1000 nodi: valutazioni costanti per budget"
                         if column == "problog_evaluations"
                         else "400–1000 nodi: nessuna riallocazione")
                ax.text(0.04, 0.95, label, transform=ax.transAxes,
                        va="top", fontsize=9)
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
        filename="final_score_scalability.png",
        start_from_zero=False,
    )

# ============================================================
# 2. RUNTIME

# ============================================================

def plot_runtime(df: pd.DataFrame) -> None:
    plot_metric_by_nodes(
        df=df,
        column="greedy_loop_seconds",
        ylabel="Tempo medio del ciclo greedy (s)",
        title="Tempo del ciclo greedy",
        filename="runtime_scalability.png",
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
        filename="problog_evaluations_scalability.png",
    )

# ============================================================
# 4. LOG GAIN

# ============================================================

def plot_log_gain(df: pd.DataFrame) -> None:
    plot_metric_by_nodes(
        df=df,
        column="log_gain_percent",
        ylabel="Log gain medio (%)",
        title="Miglioramento dello score di sicurezza",
        filename="log_gain_scalability.png",
        start_from_zero=False,
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
        filename="greedy_steps_scalability.png",
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
        filename="reallocation_steps_scalability.png",
    )

# ============================================================
# 7. STATE PAIRS VS RUNTIME

# ============================================================

def plot_runtime_vs_state_pairs(df: pd.DataFrame) -> None:
    """Fit lineare e quadratico per entrambi gli approcci."""
    budget_colors = build_budget_colors(df)
    filtered = without_outliers(df, "greedy_loop_seconds")
    fig, axes = create_comparison_axes()
    for ax, approach in zip(axes, APPROACH_ORDER):
        approach_df = filtered[filtered["approach"] == approach]
        for budget, group in approach_df.groupby("budget"):
            ax.scatter(group["state_pairs"], group["greedy_loop_seconds"],
                       color=budget_colors[int(budget)], s=38, alpha=0.8)
        x = approach_df["state_pairs"].to_numpy(dtype=float)
        y = approach_df["greedy_loop_seconds"].to_numpy(dtype=float)
        if len(np.unique(x)) >= 2:
            x_line = np.linspace(x.min(), x.max(), 300)
            ax.plot(x_line, np.polyval(np.polyfit(x, y, 1), x_line),
                    color="black", linestyle="--", linewidth=2)
        if len(np.unique(x)) >= 3:
            ax.plot(x_line, np.polyval(np.polyfit(x, y, 2), x_line),
                    color="firebrick", linestyle=":", linewidth=2)
        ax.set_title(APPROACH_LABELS[approach])
        ax.set_xlabel("Numero di coppie nodo-contromisura")
        ax.grid(True, alpha=0.3)
        ax.set_ylabel("Tempo del ciclo greedy (s)")
        ax.set_ylim(bottom=0)
    finish_comparison_figure(fig, axes,
        "Tempo del ciclo rispetto alla dimensione dello stato", budget_colors,
        extra_handles=[Line2D([0], [0], color="black", linestyle="--",
                              label="Fit lineare"),
                       Line2D([0], [0], color="firebrick", linestyle=":",
                              label="Fit quadratico")])
    save_figure(fig, "runtime_vs_state_pairs.png")

# ============================================================
# MAIN

# ============================================================

def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for extension in ("pdf", "png"):
        (OUTPUT_DIR / f"preparation_scalability.{extension}").unlink(missing_ok=True)
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
