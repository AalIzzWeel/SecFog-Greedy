# Modulo `experiments`

Contiene i benchmark del Fast Greedy, il confronto con la ricerca esaustiva e gli script di visualizzazione. Tutti i comandi vanno eseguiti dalla root del progetto.

## File

| File | Scopo |
| --- | --- |
| `run_fast_benchmarks.py` | Benchmark di scalabilità dei due approcci greedy. |
| `plot_graphs.py` | Grafici del benchmark di scalabilità. |
| `run_comparison_benchmarks.py` | Confronto Fast Greedy–esaustivo sulle istanze piccole. |
| `plot_comparison_results.py` | Grafici medi del confronto rispetto al budget. |

## Benchmark di scalabilità del Fast Greedy

```bash
python3 -m experiments.run_fast_benchmarks --profile quick
python3 -m experiments.run_fast_benchmarks --profile thesis
```

| Profilo | Istanze | Seed | Budget | Approcci | Run |
| --- | --- | --- | --- | ---: | ---: |
| `quick` | 25/5 e 50/10 nodi/servizi | 42 | 0, 300 | 2 | 8 |
| `thesis` | 25/5, 50/10, 100/15, 200/25, 400/50 | 42, 123, 999 | 0, 100, 300, 600, 1000 | 2 | 150 |

Gli approcci sono:

- `upgrade-then-downgrade`;
- `downgrade-then-upgrade`.

Esecuzione personalizzata:

```bash
python3 -m experiments.run_fast_benchmarks \
  --instances instance_n25_s5_seed42 instance_n50_s10_seed42 \
  --budgets 0 300 \
  --approaches upgrade-then-downgrade downgrade-then-upgrade
```

| Opzione | Descrizione |
| --- | --- |
| `--profile {quick,thesis}` | Matrice predefinita; default `quick`. |
| `--instances ...` | Sostituisce le istanze del profilo. |
| `--budgets ...` | Sostituisce i budget del profilo. |
| `--approaches ...` | Seleziona uno o entrambi gli approcci. |
| `--no-save` | Stampa i risultati senza creare CSV e JSON. |

Le metriche di qualità usano sempre lo score del placement originale. Nel `downgrade-then-upgrade`, `effective_budget` registra il budget operativo dopo l'aggiunta del costo liberato portando le capability a `L0`.

### Output

```text
results/fast_benchmark_<profilo>_<timestamp>.csv
results/fast_benchmark_<profilo>_<timestamp>.json
```

Il CSV contiene una riga per run; il JSON aggiunge history e policy finale. Le metriche comprendono dimensione dell'istanza, budget, score, costo netto, passi, riallocazioni, valutazioni ProbLog, cache e runtime.

Il log gain è:

```text
log_gain = log10(final_score / initial_score)
```

### Grafici di scalabilità

Senza `--csv` viene usato il file `fast_benchmark_thesis_*.csv` più recente:

```bash
python3 -m experiments.plot_graphs
```

Oppure:

```bash
python3 -m experiments.plot_graphs \
  --csv results/fast_benchmark_thesis_20260921_194402.csv
```

Il CSV deve contenere entrambi gli approcci. Le curve sono aggregate sui seed con media e deviazione standard. Ogni grafico viene salvato in PDF e PNG dentro `results/plots/`:

- `final_score_scalability`;
- `runtime_scalability`;
- `problog_evaluations_scalability`;
- `log_gain_scalability`;
- `greedy_steps_scalability`;
- `reallocation_steps_scalability`;
- `runtime_vs_state_pairs`.

L'ultimo grafico riporta correlazione di Pearson e fit quadratico descrittivo; il fit non è una stima della complessità asintotica.

## Confronto Fast Greedy–esaustivo

Il benchmark usa la famiglia deterministica in `model/comparison/`. Per ogni scenario e budget:

1. esegue una volta l'esaustivo sullo stato originale;
2. esegue entrambi gli approcci greedy;
3. confronta gli score soltanto se l'esaustivo ha completato l'enumerazione.

Esecuzione completa predefinita:

```bash
python3 -m experiments.run_comparison_benchmarks
```

Configurazione predefinita:

- scenari: `storage`, `communication`, `monitoring`, `network`, `detection`;
- budget: `0 100 300 400`;
- due approcci greedy;
- 40 righe finali (`5 scenari x 4 budget x 2 approcci`).

Esempi:

```bash
python3 -m experiments.run_comparison_benchmarks \
  --scenarios storage communication \
  --budgets 0 100 300

python3 -m experiments.run_comparison_benchmarks \
  --max-exhaustive-seconds 300 \
  --no-save
```

| Opzione | Descrizione |
| --- | --- |
| `--scenarios ...` | Sottoinsieme dei cinque scenari. |
| `--catalog` | Catalogo sorgente. |
| `--profiles` | Profili di requirement sorgente. |
| `--instances-dir` | Directory delle istanze generate. |
| `--budgets ...` | Budget da confrontare. |
| `--max-exhaustive-seconds` | Limite temporale per ciascuna ricerca esaustiva. |
| `--no-save` | Non salva CSV e JSON. |

Output:

```text
results/comparison_family_<timestamp>.csv
results/comparison_family_<timestamp>.json
```

Metriche principali:

```text
absolute_gap = exhaustive_score - greedy_score
relative_gap_percent = absolute_gap / exhaustive_score * 100
speedup = exhaustive_seconds / greedy_seconds
```

Il gap viene limitato inferiormente a zero per assorbire differenze numeriche. `absolute_gap`, `relative_gap_percent` e `optimal_hit` restano non definiti quando `exhaustive_completed=False`, perché in quel caso non è disponibile un ottimo certificato.

## Grafici del confronto

Senza `--csv` viene usato il `comparison_family_*.csv` più recente:

```bash
python3 -m experiments.plot_comparison_results
```

Con percorsi espliciti:

```bash
python3 -m experiments.plot_comparison_results \
  --csv results/comparison_family_20260921_192535.csv \
  --output-dir results/comparison_plots
```

Lo script accetta solo risultati esaustivi completi con stato `OPTIMAL` e con entrambi gli approcci per ogni coppia istanza-budget. Aggrega gli scenari mediante media e deviazione standard e produce, in PDF e PNG:

- `relative_gap_comparison`;
- `score_comparison`;
- `problog_evaluations_comparison`;
- `runtime_comparison`.

Nel grafico dei tempi l'asse verticale è logaritmico.

## Sequenza riproducibile consigliata

```bash
# 1. Genera le istanze scalabili
python3 -m model.scalable_generator

# 2. Benchmark e grafici greedy
python3 -m experiments.run_fast_benchmarks --profile thesis
python3 -m experiments.plot_graphs

# 3. Benchmark e grafici contro l'ottimo
python3 -m experiments.run_comparison_benchmarks
python3 -m experiments.plot_comparison_results
```