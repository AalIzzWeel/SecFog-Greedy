# Modulo `optimizer`

Il modulo definisce lo spazio degli stati, i costi e l'euristica usata dal Fast Greedy.

## Panoramica

| File | Responsabilità |
| --- | --- |
| `actions.py` | Rappresentazione di una modulazione `MODIFY`. |
| `state.py` | Livello corrente di ogni coppia nodo-capability attiva. |
| `costs.py` | Costi dei livelli, delle azioni e degli stati. |
| `requirements.py` | Validazione e analisi ricorsiva dei requirement `all`/`any`. |
| `heuristic.py` | Generazione e ordinamento di upgrade e downgrade. |
| `utils.py` | Caricamento, validazione, costruzione dello stato e policy finale. |
| `profiler.py` | Utility opzionale per misurare i tempi delle funzioni. |

## Azioni e stato

`Action` rappresenta esclusivamente una modulazione:

```text
MODIFY(node, capability, Lold -> Lnew)
```

Le proprietà `is_upgrade` e `is_downgrade` distinguono la direzione della transizione. Non esistono azioni `ADD` o rimozioni.

`State` è un dizionario:

```python
{(node, capability): level}
```

Ogni valore è un intero: `None` non è ammesso perché tutte le capability nello stato sono attive. `is_feasible(action)` verifica che il livello corrente coincida con `old_level`; `apply(action)` esegue la transizione solo in questo caso. `key()` produce una tupla ordinata usata dalla cache dello score.

## Costi

`CostCalculator` legge dal catalogo il costo di ogni livello e calcola:

$$
\Delta c(a)=c(\ell_{new})-c(\ell_{old}).
$$

- `calculate_action_cost`: costo differenziale di una modulazione;
- `calculate_state_cost`: somma dei costi dei livelli nello stato;
- `calculate_net_cost`: differenza tra costo dello stato finale e iniziale.

Un costo negativo identifica un downgrade che libera budget.

## Requirement

I requirement possono essere capability atomiche oppure composizioni JSON:

```json
{
  "all": [
    "authentication",
    {"any": ["encrypted_storage", "obfuscated_storage"]}
  ]
}
```

| Funzione | Ruolo |
| --- | --- |
| `validate_requirement` | Controlla struttura, operatori e capability. |
| `required_capabilities` | Estrae ricorsivamente le capability menzionate. |
| `evaluate_requirement` | Stima la probabilità del requisito su uno stato (`all` come prodotto, `any` come unione probabilistica). |

## Euristica

`generate_actions` considera soltanto capability:

- menzionate nei requirement dei servizi collocati sul nodo;
- presenti nello stato iniziale;
- modulabili tra livelli adiacenti.

Per ciascuna azione calcola:

$$
q(a)=p(\ell_{new})-p(\ell_{old}),
\qquad
\eta(a)=\frac{q(a)}{\Delta c(a)}.
$$

dove $q(a)$ è la **_qualità specifica_** dell'azione e $eta(a)$ la sua efficienza, calcolata come il rapporto tra la qualità specifica (guadagno) e il costo dell'azione. 

Per gli upgrade e i downgrade viene utilizzata la stessa metrica euristica, ossia l'efficienza:
* gli upgrade sono ordinati per efficienza decrescente --> si prediligono le azioni che "costano poco e alzano di più lo score di sicurezza"
* i downgrade, per i quali qualità e costo sono entrambi negativi, sono ordinati per efficienza crescente 
    * conviene liberare prima le azioni che portano minor guadagno per unità di costo 

L'ordine dei nodi risolve i pareggi ed è determinato dal numero complessivo di capability menzionate nei requirement associati al nodo. I pareggi successivi sono risolti in modo deterministico tramite nome della capability e nuovo livello.

| Funzione | Ruolo |
| --- | --- |
| `group_requirements_by_node` | Associa i requirement ai nodi del placement. |
| `build_relevant_capabilities` | Estrae le capability richieste per nodo. |
| `build_capability_levels` | Ordina i livelli disponibili nel catalogo. |
| `rank_nodes_by_requirement_count` | Ordina i nodi per quantità di requirement atomici. |
| `calculate_specific_quality` | Calcola la variazione di efficacia. |
| `calculate_efficiency` | Divide qualità specifica per costo differenziale. |
| `generate_actions` | Produce e ordina candidati upgrade/downgrade. |
| `first_feasible` | Restituisce il primo candidato compatibile con lo stato e non bloccato. |

## Utility e validazione

`validate_placement` verifica che:

- il placement contenga componenti;
- `security_state` descriva esattamente i nodi usati;
- nodi, capability e livelli esistano;
- ogni capability sia applicabile al tipo di nodo;
- nessuna capability dello stato sia inattiva.

`create_initial_state` costruisce $P_0$; `build_final_policy` confronta stato iniziale e finale e produce le azioni `MODIFY`; `display_solution_summary` stampa score, budget e policy.
