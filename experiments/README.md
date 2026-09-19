# Modulo `experiments`

Contiene il runner dei benchmark di scalabilità e lo script che genera i grafici comparativi dei due approcci.

## Benchmark

`run_fast_benchmarks.py` esegue `FastGreedyOptimizer` sulle istanze in `model/generated/`.

```bash
python3 -m experiments.run_fast_benchmarks --profile quick
python3 -m experiments.run_fast_benchmarks --profile thesis
```

| Profilo | Istanze | Seed | Budget | Run totali |
| --- | --- | --- | --- | ---: |
| `quick` | 25/5 e 50/10 nodi/servizi | 42 | 0, 300 | 8 |
| `thesis` | 25/5, 50/10, 100/15, 200/25 e 400/50 | 42, 123, 999 | 0, 100, 300, 600, 1000 | 150 |

Il totale include entrambi gli approcci:

- `upgrade-then-downgrade`;
- `downgrade-then-upgrade`.

### Esecuzione personalizzata

```bash
python3 -m experiments.run_fast_benchmarks \
  --instances instance_n25_s5_seed42 instance_n50_s10_seed42 \
  --budgets 0 300 \
  --approaches upgrade-then-downgrade downgrade-then-upgrade
```

| Opzione | Descrizione |
| --- | --- |
| `--profile {quick,thesis}` | Seleziona la matrice predefinita; default `quick`. |
| `--instances ...` | Sostituisce le istanze del profilo. |
| `--budgets ...` | Sostituisce i budget del profilo. |
| `--approaches ...` | Seleziona uno o entrambi gli approcci. |
| `--no-save` | Stampa i risultati senza creare CSV e JSON. |

Se vengono specificati `--instances` o `--budgets`, l'output usa il nome profilo `custom`. I budget devono essere non negativi.

### Baseline dei due approcci

Le metriche di qualità usano sempre lo score del placement originale $P_0$. Per `downgrade-then-upgrade`, lo stato operativo viene prima portato a `L0`, ma lo score di tale stato non sostituisce la baseline. `effective_budget` registra il budget dopo l'aggiunta del costo liberato.

### Output

Salvo `--no-save`, vengono creati:

```text
results/fast_benchmark_<profilo>_<timestamp>.csv
results/fast_benchmark_<profilo>_<timestamp>.json
```

Il CSV contiene una riga per run; il JSON aggiunge history completa e policy finale.

Metriche principali:

- dimensione dell'infrastruttura, nodi usati, servizi e coppie dello stato;
- budget iniziale, budget effettivo, costo netto e residuo;
- score iniziale/finale, delta, miglioramento percentuale e `log_gain`;
- passi greedy, riallocazioni e azioni della policy finale;
- valutazioni ProbLog, dimensione della cache e runtime.

Il log gain è:

$$
log\_gain=\log_{10}\left(\frac{score_{finale}}{score_{iniziale}}\right).
$$

## Grafici

Senza argomenti, `plot_graphs.py` usa il CSV `fast_benchmark_thesis_*.csv` modificato più recentemente:

```bash
python3 -m experiments.plot_graphs
```

È possibile indicare un file preciso:

```bash
python3 -m experiments.plot_graphs \
  --csv results/fast_benchmark_thesis_20260918_203718.csv
```

Il CSV deve contenere entrambi gli approcci. I risultati sono aggregati sui seed mediante media e deviazione standard e salvati come PDF vettoriali in `results/plots/`.

| File | Contenuto |
| --- | --- |
| `final_score_scalability.pdf` | Media di $\log_{10}(score\ finale)$ rispetto ai nodi. |
| `runtime_scalability.pdf` | Tempo medio di esecuzione. |
| `problog_evaluations_scalability.pdf` | Numero medio di valutazioni reali dell'oracolo. |
| `log_gain_scalability.pdf` | Miglioramento medio rispetto alla baseline. |
| `greedy_steps_scalability.pdf` | Numero medio di passi greedy. |
| `reallocation_steps_scalability.pdf` | Numero medio di riallocazioni accettate. |
| `runtime_vs_state_pairs.pdf` | Runtime rispetto alle coppie nodo-capability. |

L'ultimo grafico riporta correlazione di Pearson e fit quadratico. Il fit è descrittivo e non costituisce una stima della complessità asintotica.
