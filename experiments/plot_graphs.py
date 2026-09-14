from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ============================================================
# PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUT_DIR = RESULTS_DIR / "plots"

CSV_PATTERN = "fast_benchmark_thesis_*.csv"


# ============================================================
# CONFIGURAZIONE GRAFICA
# ============================================================

plt.rcParams.update(
    {
        "font.size": 11,
        "axes.titlesize": 15,
        "axes.labelsize": 12,
        "legend.fontsize": 10,
        "legend.title_fontsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
    }
)


# ============================================================
# UTILITÀ
# ============================================================


def get_latest_csv() -> Path:
    """
    Restituisce il file fast_benchmark_thesis_*.csv
    modificato più recentemente.
    """
    csv_files = sorted(
        RESULTS_DIR.glob(CSV_PATTERN),
        key=lambda path: path.stat().st_mtime,
    )

    if not csv_files:
        raise FileNotFoundError(
            f"Nessun file '{CSV_PATTERN}' trovato in {RESULTS_DIR}"
        )

    return csv_files[-1]


def validate_columns(df: pd.DataFrame) -> None:
    """Controlla che il CSV contenga tutte le colonne necessarie."""

    required_columns = {
        "infrastructure_nodes",
        "budget",
        "elapsed_seconds",
        "problog_evaluations",
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


def save_figure(fig, filename: str) -> None:
    """
    Salva il grafico in PDF.

    Il PDF è vettoriale ed è quindi adatto
    all'inserimento nella tesi.
    """
    output_path = OUTPUT_DIR / filename

    fig.tight_layout()

    fig.savefig(
        output_path,
        bbox_inches="tight",
    )

    print(f"Grafico salvato: {output_path}")

    plt.close(fig)


def compute_summary(
    df: pd.DataFrame,
    column: str,
) -> pd.DataFrame:
    """
    Calcola media e deviazione standard sui seed
    per ogni coppia (numero nodi, budget).
    """

    return (
        df.groupby(
            ["infrastructure_nodes", "budget"],
            as_index=False,
        )
        .agg(
            mean=(column, "mean"),
            std=(column, "std"),
        )
        .sort_values(
            ["budget", "infrastructure_nodes"]
        )
    )


def plot_metric_by_nodes(
    df: pd.DataFrame,
    column: str,
    ylabel: str,
    title: str,
    filename: str,
    start_from_zero: bool = True,
) -> None:
    """
    Grafico generico della media ± deviazione standard
    di una metrica rispetto al numero di nodi.

    Ogni linea rappresenta un budget differente.
    """

    summary = compute_summary(df, column)

    fig, ax = plt.subplots(figsize=(8, 5))

    for budget, group in summary.groupby("budget"):
        ax.errorbar(
            group["infrastructure_nodes"],
            group["mean"],
            yerr=group["std"],
            marker="o",
            markersize=6,
            linewidth=1.8,
            capsize=4,
            label=str(budget),
        )

    ax.set_xlabel("Numero di nodi dell'infrastruttura")
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    ax.set_xticks(
        sorted(df["infrastructure_nodes"].unique())
    )

    if start_from_zero:
        ax.set_ylim(bottom=0)

    ax.grid(
        True,
        alpha=0.3,
    )

    ax.legend(
        title="Budget",
        frameon=True,
    )

    save_figure(fig, filename)


# ============================================================
# 1. RUNTIME
# ============================================================


def plot_runtime(df: pd.DataFrame) -> None:
    """
    Tempo medio di esecuzione rispetto alla
    dimensione dell'istanza.
    """

    plot_metric_by_nodes(
        df=df,
        column="elapsed_seconds",
        ylabel="Tempo medio di esecuzione (s)",
        title="Tempo di esecuzione del Fast Greedy",
        filename="runtime_scalability.pdf",
    )


# ============================================================
# 2. VALUTAZIONI PROBLOG
# ============================================================


def plot_problog_evaluations(df: pd.DataFrame) -> None:
    """
    Numero medio di valutazioni reali di ProbLog.

    Nel Fast Greedy questo permette di evidenziare
    il comportamento dell'oracolo rispetto alla
    dimensione dell'istanza.
    """

    plot_metric_by_nodes(
        df=df,
        column="problog_evaluations",
        ylabel="Numero medio di valutazioni ProbLog",
        title="Valutazioni reali dell'oracolo ProbLog",
        filename="problog_evaluations_scalability.pdf",
    )


# ============================================================
# 3. LOG GAIN
# ============================================================


def plot_log_gain(df: pd.DataFrame) -> None:
    """
    Miglioramento dello score espresso tramite log gain.
    """

    summary = compute_summary(
        df,
        "log_gain",
    )

    fig, ax = plt.subplots(figsize=(8, 5))

    for budget, group in summary.groupby("budget"):
        ax.errorbar(
            group["infrastructure_nodes"],
            group["mean"],
            yerr=group["std"],
            marker="o",
            markersize=6,
            linewidth=1.8,
            capsize=4,
            label=str(budget),
        )

    # Riferimento concettuale:
    # log_gain = 0 significa nessun miglioramento.
    ax.axhline(
        y=0,
        linestyle="--",
        linewidth=1.4,
    )

    ax.set_xlabel("Numero di nodi dell'infrastruttura")
    ax.set_ylabel("Log gain medio dello score")
    ax.set_title("Miglioramento dello score di sicurezza")

    ax.set_xticks(
        sorted(df["infrastructure_nodes"].unique())
    )

    ax.set_ylim(bottom=-0.1)

    ax.grid(
        True,
        alpha=0.3,
    )

    ax.legend(
        title="Budget",
        frameon=True,
    )

    save_figure(
        fig,
        "log_gain_scalability.pdf",
    )


# ============================================================
# 4. PASSI GREEDY
# ============================================================


def plot_greedy_steps(df: pd.DataFrame) -> None:
    """
    Numero di passi eseguiti dall'algoritmo.
    """

    plot_metric_by_nodes(
        df=df,
        column="greedy_steps",
        ylabel="Numero medio di passi greedy",
        title="Numero di passi del Fast Greedy",
        filename="greedy_steps_scalability.pdf",
    )


# ============================================================
# 5. RIALLOCAZIONI
# ============================================================


def plot_reallocation_steps(df: pd.DataFrame) -> None:
    """
    Numero di passi di riallocazione prodotti
    dalle operazioni di downgrade/reimpiego del budget.
    """

    plot_metric_by_nodes(
        df=df,
        column="reallocation_steps",
        ylabel="Numero medio di riallocazioni",
        title="Riallocazioni del budget durante l'ottimizzazione",
        filename="reallocation_steps_scalability.pdf",
    )


# ============================================================
# 6. STATE PAIRS VS RUNTIME
# ============================================================


def plot_runtime_vs_state_pairs(df: pd.DataFrame) -> None:
    """
    Analizza la relazione tra la dimensione effettiva
    dello spazio di stato e il tempo di esecuzione.

    Mostra:
    - singole osservazioni;
    - budget;
    - correlazione di Pearson;
    - fit quadratico;
    - coefficiente R^2 del fit.

    Il fit è puramente descrittivo e non rappresenta
    una stima della complessità asintotica.
    """

    fig, ax = plt.subplots(figsize=(8, 5))

    # --------------------------------------------------------
    # Scatter delle singole esecuzioni
    # --------------------------------------------------------

    for budget, group in df.groupby("budget"):
        ax.scatter(
            group["state_pairs"],
            group["elapsed_seconds"],
            s=45,
            alpha=0.8,
            label=str(budget),
        )

    # --------------------------------------------------------
    # Dati
    # --------------------------------------------------------

    x = df["state_pairs"].to_numpy(dtype=float)
    y = df["elapsed_seconds"].to_numpy(dtype=float)

    # --------------------------------------------------------
    # Correlazione di Pearson
    # --------------------------------------------------------

    correlation = np.corrcoef(x, y)[0, 1]

    # --------------------------------------------------------
    # Fit quadratico
    # y = ax² + bx + c
    # --------------------------------------------------------

    coefficients = np.polyfit(
        x,
        y,
        2,
    )

    x_fit = np.linspace(
        x.min(),
        x.max(),
        300,
    )

    y_fit = np.polyval(
        coefficients,
        x_fit,
    )

    ax.plot(
        x_fit,
        y_fit,
        linestyle="--",
        linewidth=2,
        label="Fit quadratico",
    )

    # --------------------------------------------------------
    # R² del fit quadratico
    # --------------------------------------------------------

    y_predicted = np.polyval(
        coefficients,
        x,
    )

    residual_sum = np.sum(
        (y - y_predicted) ** 2
    )

    total_sum = np.sum(
        (y - np.mean(y)) ** 2
    )

    r_squared = (
        1 - residual_sum / total_sum
        if total_sum > 0
        else float("nan")
    )

    # --------------------------------------------------------
    # Box statistiche
    # --------------------------------------------------------

    statistics = (
        f"Pearson r = {correlation:.3f}\n"
        f"Fit quadratico $R^2$ = {r_squared:.3f}"
    )

    ax.text(
        0.045,
        0.955,
        statistics,
        transform=ax.transAxes,
        verticalalignment="top",
        bbox={
            "boxstyle": "round",
            "alpha": 0.2,
        },
    )

    # --------------------------------------------------------
    # Aspetto del grafico
    # --------------------------------------------------------

    ax.set_xlabel(
        "Numero di coppie nodo-contromisura"
    )

    ax.set_ylabel(
        "Tempo di esecuzione (s)"
    )

    ax.set_title(
        "Tempo di esecuzione rispetto alla dimensione dello stato"
    )

    ax.set_ylim(bottom=0)

    ax.grid(
        True,
        alpha=0.3,
    )

    ax.legend(
        title="Budget",
        frameon=True,
    )

    save_figure(
        fig,
        "runtime_vs_state_pairs.pdf",
    )


# ============================================================
# MAIN
# ============================================================


def main() -> None:
    # Crea results/plots se non esiste.
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Individua automaticamente l'ultimo benchmark thesis.
    csv_path = get_latest_csv()

    print("=" * 72)
    print("GENERAZIONE GRAFICI FAST GREEDY")
    print("=" * 72)
    print(f"CSV utilizzato : {csv_path}")
    print(f"Cartella output: {OUTPUT_DIR}")

    # --------------------------------------------------------
    # Caricamento
    # --------------------------------------------------------

    df = pd.read_csv(csv_path)

    validate_columns(df)

    print(f"Run caricati    : {len(df)}")
    
    nodes = sorted(int(x) for x in df["infrastructure_nodes"].unique())
    budgets = sorted(int(x) for x in df["budget"].unique())

    print(f"Nodi            : {nodes}")
    print(f"Budget          : {budgets}")

    print("-" * 72)

    # --------------------------------------------------------
    # Generazione
    # --------------------------------------------------------

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