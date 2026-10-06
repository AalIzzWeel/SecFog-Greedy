# Esperimenti

Tutti i comandi si eseguono dalla directory principale del repository.

## Scalabilità

Comandi:
```bash
python3 -m experiments.run_fast_benchmarks --profile quick
python3 -m experiments.run_fast_benchmarks --profile thesis
```

| Profilo | Nodi/servizi | Seed | Budget | Run |
| --- | --- | --- | --- | ---: |
| `quick` | 25/5, 50/10 | 42 | 0, 300 | 8 |
| `thesis` | 25/5, 50/10, 100/15, 200/25, 400/50, 600/70, 800/90, 1000/100 | 42, 123, 999, 1000–1016 | 0, 100, 300, 600, 1000 | 1600 |

Entrambi i profili eseguono UD e DU. Le opzioni `--instances`, `--budgets` e `--approaches` sostituiscono le scelte predefinite; `--no-save` disabilita il salvataggio. Per esempio:

```bash
python3 -m experiments.run_fast_benchmarks \
  --instances instance_n600_s70_seed42 instance_n800_s90_seed42 \
  --budgets 0 300
```

I risultati sono salvati in `results/fast_benchmark_<profilo>_<timestamp>.csv` e `.json`. Il CSV contiene le metriche di ogni run; il JSON include anche history e policy finale.

### Metriche

| Campo | Significato |
| --- | --- |
| `initial_score`, `final_score` | Score originale e finale. Il riferimento originale è lo stesso per UD e DU. |
| `relative_improvement_percent` | `100 * (final_score - initial_score) / initial_score`. |
| `log_gain` | `log10(final_score / initial_score)`. |
| `log_gain_percent` | `100 * ln(final_score / initial_score)`, distinto dal miglioramento percentuale ordinario. |
| `greedy_steps` | Upgrade accettati, inclusi quelli ottenuti mediante riallocazione. |
| `reallocation_steps` | Passi accettati che comprendono downgrade. |
| `problog_evaluations` | Invocazioni effettive di ProbLog da parte del wrapper dell'ottimizzatore. |
| `state_pairs` | Numero di coppie nodo-contromisura nello stato. |
| `effective_budget` | Budget operativo; in DU include il costo liberato dal reset a `L0`. |
| `preparation_seconds` | Tempo di preparazione dell'esecuzione. |
| `initial_evaluation_seconds` | Tempo della valutazione dello stato iniziale operativo. |
| `greedy_loop_seconds` | Tempo del ciclo di ottimizzazione. |
| `elapsed_seconds` | Tempo totale misurato dal benchmark. |

In DU la valutazione baseline dello stato originale è separata dal wrapper dell'ottimizzatore. I rapporti logaritmici sono definiti solo per score positivi.

### Grafici

```bash
python3 -m experiments.plot_graphs --csv results/fast_benchmark_thesis_merged.csv
```

Senza `--csv`, viene scelto il CSV thesis modificato più recentemente. L'opzione esplicita garantisce la scelta del dataset conservato.

Lo script produce soltanto PNG in `results/plots/`: score finale, runtime, valutazioni ProbLog, guadagno logaritmico, passi greedy, riallocazioni e tempo del ciclo rispetto alle coppie dello stato. I pannelli separano UD e DU. Il grafico dello score finale usa `log10(final_score)`; quello del guadagno usa `log_gain_percent`. I fit lineari e quadratici del tempo sono descrittivi e non dimostrano la complessità asintotica. Il filtraggio degli outlier è applicato nelle funzioni che lo prevedono; non modifica il CSV.

## Confronto con l'esaustivo

```bash
python3 -m experiments.run_comparison_benchmarks
python3 -m experiments.run_comparison_benchmarks \
  --seeds 42 123 --budgets 0 300 600 --max-exhaustive-seconds 300
```

Il benchmark genera le istanze in `model/comparison/` usando i seed richiesti. Ogni istanza ha 3 nodi, 3 servizi e 7 coppie nodo-contromisura. I seed predefiniti sono 42, 123, 999, 1000, 1001; i budget predefiniti sono 0, 100, 300, 400. Sono previste 20 ricerche esaustive e 40 run greedy.

Opzioni disponibili: `--seeds`, `--catalog`, `--profiles`, `--instances-dir`, `--budgets`, `--max-exhaustive-seconds`, `--no-save`. I risultati sono salvati in `results/comparison_family_<timestamp>.csv` e `.json`.

Per ogni istanza-budget, l'esaustivo viene eseguito una volta e confrontato con entrambi gli approcci. Il gap è calcolato soltanto quando l'ottimo è certificato:

```text
absolute_gap = max(0, exhaustive_score - greedy_score)
relative_gap_percent = 100 * absolute_gap / exhaustive_score
speedup = exhaustive_seconds / greedy_seconds
```

Se l'enumerazione non è completa, gap e `optimal_hit` restano non definiti. Il codice gestisce separatamente lo score esaustivo nullo.

### Grafici del confronto

```bash
python3 -m experiments.plot_comparison_results \
  --csv results/comparison_family_20260928_153915.csv
```

Questo comando visualizza il CSV disponibile, ancora da sostituire con quello definitivo della tesi. Non usarlo per sovrascrivere le PNG definitive prima di avere allineato i risultati.

Lo script richiede enumerazioni complete con stato `OPTIMAL`, entrambi gli approcci per ogni istanza-budget e lo stesso numero di istanze per budget. Produce soltanto PNG di gap relativo, score finale, valutazioni ProbLog e runtime (asse verticale logaritmico) in `results/comparison_plots/`. Le statistiche aggregano i seed con media e deviazione standard. `--output-dir` consente una directory alternativa. Senza `--csv` sceglie il file di confronto modificato più recentemente.
