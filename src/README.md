# Modulo `src`

Contiene i due algoritmi confrontati nel progetto:

- **Fast Greedy (GUBR)**: ricerca euristica rapida guidata da qualità specifica ed efficienza;
- **Exhaustive OR-Tools**: enumerazione di tutte le configurazioni ammissibili e valutazione di ciascuna tramite SecFog.

Il placement e l'insieme delle coppie `(nodo, capability)` restano invariati. Gli algoritmi modificano esclusivamente i livelli delle capability già attive; anche `L0` è un livello attivo, con costo ed efficacia propri.

## File

| File | Contenuto |
| --- | --- |
| `fast_greedy.py` | Implementazione del Gain-Based Greedy Reallocation. |
| `run_fast_greedy.py` | Runner del Fast Greedy. |
| `exhaustive_or_tools.py` | Enumeratore CP-SAT con callback SecFog. |
| `run_exhaustive_or_tools.py` | Runner della ricerca esaustiva. |

## Fast Greedy

### Euristica

Per una transizione adiacente `old -> new`, il costo incrementale è:

```text
delta_c = cost(new) - cost(old)
```

La qualità specifica è la riduzione locale della probabilità di attacco:

```text
q = p_attack(old) - p_attack(new)
```
>Nota: La probabilità di attacco è definita come il complemento dell’efficacia probabilistica della capability. Viene utilizzata dall’euristica per stimare il beneficio locale di una modulazione, mentre l’effetto globale della configurazione viene valutato dall’oracolo SecFog.

L'efficienza è:

```text
eta = q / delta_c
```

Gli upgrade sono ordinati per efficienza decrescente. I downgrade sono ordinati per efficienza crescente, così da privilegiare la minore perdita di qualità per unità di costo liberata. Le transizioni sono sempre tra livelli consecutivi disponibili: per esempio `L0 -> L1 -> L2`.

### Ciclo di ottimizzazione

`FastGreedyOptimizer.optimize(initial_state, budget)`:

1. genera tutte le transizioni adiacenti rilevanti;
2. valuta lo stato iniziale con SecFog;
3. applica gli upgrade fattibili e direttamente finanziabili nell'ordine euristico;
4. valuta con SecFog lo stato ottenuto dal gruppo di upgrade;
5. se il miglior upgrade fattibile non è finanziabile, accumula downgrade fino a coprire il budget mancante;
6. applica provvisoriamente l'intera riallocazione;
7. la conferma solo se lo score SecFog aumenta di più della tolleranza numerica;
8. termina quando non restano upgrade fattibili, non è possibile finanziare il prossimo upgrade o la riallocazione tentata non migliora lo score.

Una capability già migliorata viene inserita in `improved_capabilities` e non può essere successivamente usata come sorgente di downgrade.

Il metodo restituisce:

```python
(final_state, remaining_budget, final_score, history)
```

Ogni `FastGreedyStep` registra l'upgrade, gli eventuali downgrade, il costo netto, la qualità specifica netta, l'efficienza dell'upgrade obiettivo e il budget residuo.

### Approcci

| Approccio | Stato operativo iniziale | Budget operativo |
| --- | --- | --- |
| `upgrade-then-downgrade` | Stato originale | Budget fornito |
| `downgrade-then-upgrade` | Tutte le capability a `L0` | Budget fornito + costo liberato |

`build_downgrade_then_upgrade_input()` costruisce il secondo input senza disattivare capability.

### Esecuzione

Dalla root del progetto:

```bash
python3 -m src.run_fast_greedy
```

Esempio con parametri espliciti:

```bash
python3 -m src.run_fast_greedy \
  --budget 300 \
  --approach downgrade-then-upgrade \
  --infrastructure model/generated/instance_n25_s5_seed42/infrastructure.json \
  --application model/generated/instance_n25_s5_seed42/application.json \
  --placement model/generated/instance_n25_s5_seed42/placement.json
```

| Opzione | Default |
| --- | --- |
| `--budget` | `300` |
| `--approach` | `upgrade-then-downgrade` |
| `--catalog` | `model/security_catalog.json` |
| `--infrastructure` | Istanza `n25_s5_seed42` |
| `--application` | Istanza `n25_s5_seed42` |
| `--placement` | Istanza `n25_s5_seed42` |
| `--base` | `prolog/secfog_base.pl` |

L'output mostra score iniziale/finale, history, costo netto, budget residuo e numero di valutazioni ProbLog.

## Ricerca esaustiva OR-Tools

### Modello CP-SAT

Per ogni coppia `(nodo, capability)` e livello disponibile `l` viene creata una variabile booleana:

```text
x[node, capability, l] = 1  se il livello l è selezionato
```

Il vincolo one-hot impone esattamente un livello:

```text
sum_l x[node, capability, l] = 1
```

Il vincolo di budget è:

```text
final_cost <= initial_cost + budget
```

equivalente a `net_cost <= budget`.

SecFog è una funzione black-box e non viene inserita come obiettivo CP-SAT. OR-Tools enumera le configurazioni ammissibili; `_SecFogSolutionCallback` decodifica ogni assegnazione, ne calcola lo score e conserva la migliore. A parità di score sono preferiti, nell'ordine:

1. costo netto minore;
2. chiave dello stato lessicograficamente minore, per rendere il risultato deterministico.

La soluzione è certificata ottima soltanto quando `completed=True`. Se interviene un limite di tempo o di soluzioni, viene restituita la migliore configurazione visitata, ma non l'ottimo globale.

`configuration_upper_bound` è il prodotto del numero di livelli disponibili per ogni capability; non considera il filtro del budget. `feasible_solutions` conta invece le configurazioni effettivamente enumerate.

### Policy finale

`build_adjacent_policy()` espande ogni differenza fra stato iniziale e finale in transizioni consecutive. Per esempio:

```text
L0 -> L2  diventa  L0 -> L1, L1 -> L2
```

La funzione descrive le modifiche necessarie, ma il loro ordine lessicografico non garantisce che ogni prefisso della policy rispetti il budget; il vincolo è garantito sullo stato finale.

### Esecuzione

Usare istanze piccole, perché ogni configurazione ammissibile richiede una valutazione SecFog:

```bash
python3 -m src.run_exhaustive_or_tools \
  --budget 300 \
  --infrastructure model/comparison/realistic_edge_cloud_storage/infrastructure.json \
  --application model/comparison/realistic_edge_cloud_storage/application.json \
  --placement model/comparison/realistic_edge_cloud_storage/placement.json \
  --catalog model/comparison/realistic_edge_cloud_storage/catalog.json
```

Limiti opzionali (aggiunti per possibili estensioni future):

```bash
python3 -m src.run_exhaustive_or_tools \
  --budget 300 \
  --max-seconds 60 \
  --max-solutions 10000
```

| Opzione | Default |
| --- | --- |
| `--budget` | `300` |
| `--catalog` | `model/security_catalog.json` |
| `--infrastructure`, `--application`, `--placement` | Istanza `n25_s5_seed42` |
| `--base` | `prolog/secfog_base.pl` |
| `--max-seconds` | Nessun limite |
| `--max-solutions` | Nessun limite |

Controllare sempre `Enumerazione completa`. Se vale `no`, lo score mostrato non è certificato ottimo.

## Confronto sintetico

| Caratteristica | Fast Greedy | Esaustivo |
| --- | --- | --- |
| Selezione | Euristica locale | Tutte le configurazioni ammissibili |
| Chiamate SecFog | Stato iniziale, gruppi di upgrade e riallocazioni tentate | Una per configurazione ammissibile, salvo cache |
| Garanzia di ottimalità | No | Sì, solo se `completed=True` |
| Uso consigliato | Istanze scalabili | Istanze piccole di confronto |