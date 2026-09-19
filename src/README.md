# Modulo `src`

Contiene l'implementazione del **Gain-Based Greedy Reallocation** e il relativo runner da riga di comando.

## `fast_greedy.py`

### `FastGreedyStep`

Rappresenta un passo dell'algoritmo greedy. 
Ogni elemento della history registra:

| Campo | Significato |
| --- | --- |
| `step_number` | Posizione della mossa nella run. |
| `action` | Upgrade selezionato. |
| `cost` | Costo netto dello step. |
| `specific_quality` | Guadagno euristico netto dello step. |
| `efficiency` | Efficienza dell'upgrade obiettivo. |
| `remaining_budget` | Budget residuo dopo lo step. |
| `downgrades` | Eventuali downgrade usati per finanziare l'upgrade. |

`is_reallocation` è vero quando `downgrades` non è vuoto. 

### `build_downgrade_then_upgrade_input`

Costruisce l'input del secondo approccio sperimentale (`downgrade_then_upgrade`):

1. copia lo stato iniziale;
2. porta a `L0` ogni capability attiva;
3. calcola il costo liberato;
4. lo aggiunge al budget fornito.

La funzione richiede che ogni capability disponga di `L0` e non rimuove alcuna coppia nodo-capability.

### `FastGreedyOptimizer`

`optimize(initial_state, budget)` esegue il seguente ciclo:

1. genera una sola volta tutte le transizioni adiacenti* di upgrade e downgrade rilevanti;
    * Per adiacenti si intende che l'algoritmo considera solo passaggi tra livelli consecutivi e non sono ammessi salti come, ad esempio, L0 a L2. Quindi, genera:
        * L0 → L1 e L1 → L2 per gli upgrade;
        * L2 → L1 e L1 → L0 per i downgrade.
2. valuta con SecFog lo stato iniziale;
3. applica, nell'ordine euristico, tutti gli upgrade fattibili e finanziabili;
4. aggiorna lo score dopo il gruppo di upgrade diretti;
5. se il primo upgrade ancora fattibile non è finanziabile, accumula downgrade fino a coprire il budget mancante;
6. applica tentativamente downgrade e upgrade;
7. accetta l'intera riallocazione solo se lo score SecFog aumenta;
8. termina quando non esistono altre mosse fattibili, non è possibile finanziare il prossimo upgrade oppure una riallocazione non migliora lo score.

Una capability migliorata durante la run viene inserita in `improved_capabilities` e non può essere successivamente declassata.

Il metodo restituisce:

```python
(final_state, remaining_budget, final_score, history)
```

## `run_fast_greedy.py`

Esecuzione predefinita:

```bash
python3 -m src.run_fast_greedy
```

Con approccio e budget espliciti:

```bash
python3 -m src.run_fast_greedy \
  --budget 300 \
  --approach downgrade-then-upgrade
```

Opzioni:

| Opzione | Valore predefinito |
| --- | --- |
| `--budget` | `300` |
| `--approach` | `upgrade-then-downgrade` |
| `--catalog` | `model/security_catalog.json` |
| `--infrastructure` | Infrastruttura di `instance_n25_s5_seed42` |
| `--application` | Applicazione di `instance_n25_s5_seed42` |
| `--placement` | Placement di `instance_n25_s5_seed42` |
| `--base` | `prolog/secfog_base.pl` |

L'output mostra score iniziale e finale, history degli step, costo netto, budget residuo, policy finale e numero di valutazioni reali ProbLog.
