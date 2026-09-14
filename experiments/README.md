# Modulo `experiments`

## `run_fast_benchmarks.py`

Esegue benchmark di scalabilità del `FastGreedyOptimizer` su istanze in `model/generated/`.

Profili disponibili:

```bash
python3 -m experiments.run_fast_benchmarks --profile quick
python3 -m experiments.run_fast_benchmarks --profile thesis
```

Parametri personalizzabili: `--instances`, `--budgets`, `--reversal-policies`, `--no-save`.

Per ogni run vengono raccolti, tra gli altri: nodi totali/usati, servizi, coppie di stato, score iniziale/finale, log gain, costo netto, budget residuo, passi greedy, riallocazioni, azioni finali, valutazioni ProbLog e tempo.

## `plot_graphs.py`

Legge il CSV dei benchmark della tesi e genera i grafici finali nella cartella `results/plots/`.

Per il momento (14 settembre 2026) vengono generati i seguenti grafici:
* greedy_steps_scalability.pdf
* log_gain_scalability.pdf
* problog_evaluations_scalability.pdf
* reallocation_steps_scalability.pdf
* runtime_scalability.pdf
* runtime_vs_state_pairs.pdf