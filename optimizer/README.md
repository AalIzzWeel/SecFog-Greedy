# Modulo `optimizer`

Il modulo contiene le strutture e la logica euristica usate dal `FastGreedyOptimizer`.

| File | Responsabilità |
| --- | --- |
| `state.py` | Rappresentazione della configurazione corrente. |
| `actions.py` | Tipi di azione `ADD` e `MODIFY`. |
| `costs.py` | Costo di un'azione, costo di stato e costo netto. |
| `requirements.py` | Valutazione ricorsiva dei requirement (`all`, `any`, capability atomiche). |
| `heuristic.py` | Priorità dei nodi, candidati, upgrade, downgrade e riallocazioni. |
| `utils.py` | Caricamento/validazione dati, stato iniziale, policy finale e output. |

## Stato

`State` associa ogni coppia `(node, capability)` a un livello intero oppure a `None`. `None` rappresenta una capability disponibile ma inattiva. `State.apply()` verifica la coerenza di `ADD` e `MODIFY` prima di aggiornare lo stato.

| Funzione | Descrizione |
| :--- | :--- |
| `__post_init__` | Metodo speciale delle dataclass eseguito dopo l'inizializzazione; assicura che il dizionario `levels` sia istanziato se non fornito. |
| `copy` | Restituisce una nuova istanza di `State` contenente una copia indipendente del dizionario dei livelli. |
| `get_level` | Restituisce il livello corrente (intero o `None`) della capability specificata per un dato nodo. |
| `set_level` | Imposta o aggiorna il livello di una capability per un determinato nodo. |
| `is_active` | Verifica se una specifica capability su un nodo è attualmente attiva (ovvero se il suo livello non è `None`). |
| `apply` | Applica un'azione valida (`ADD` o `MODIFY`) allo stato, effettuando i dovuti controlli di coerenza e aggiornando il livello. |
| `key` | Genera e restituisce una rappresentazione immutabile (tupla ordinata) dello stato, utilizzabile come chiave per la cache. |
| `items` | Restituisce un'iterazione sulle coppie `((nodo, capability), livello)` presenti nello stato. |
| `__getitem__` | Permette di accedere al livello di una capability tramite la sintassi a parentesi quadre `state[(node, capability)]`. |
| `__contains__` | Permette di verificare la presenza della chiave `(node, capability)` nello stato usando l'operatore `in`. |
| `__str__` | Restituisce una rappresentazione in formato stringa formattata e ordinata di tutte le capability e dei relativi stati/livelli. |
| `count_summary` | Calcola e restituisce una tupla contenente il conteggio totale delle capability, di quelle attive e di quelle inattive. |


## `actions.py`
| Funzione | Descrizione |
| :--- | :--- |
| `__post_init__` | Metodo di validazione eseguito dopo l'istanziazione dell'azione; controlla che le azioni `ADD` non abbiano un livello precedente e che le azioni `MODIFY` abbiano un livello precedente valido e distinto da quello nuovo. |
| `add` | Metodo di classe (factory) per creare facilmente un'istanza di `Action` di tipo `ADD` specificando nodo, capability e nuovo livello. |
| `modify` | Metodo di classe (factory) per creare facilmente un'istanza di `Action` di tipo `MODIFY` specificando nodo, capability, vecchio e nuovo livello. |
| `key` | Property che restituisce la tupla `(node, capability)`, identificativo univoco della risorsa coinvolta nell'azione. |
| `__str__` | Restituisce una rappresentazione in formato stringa leggibile dell'azione (es. `ADD(node, cap, L1)` oppure `MODIFY(node, cap, L1 -> L2)`). |


## `costs.py`
| Funzione | Descrizione |
| :--- | :--- |
| `__init__` | Inizializza l'istanza di `CostCalculator` estraendo e memorizzando il dizionario delle capability dal catalogo fornito. |
| `get_capability_cost` | Recupera e restituisce il costo associato a un determinato livello per una specifica capability, verificandone la presenza nel catalogo. |
| `calculate_action_cost` | Calcola la variazione di costo (delta c) introdotta da una singola azione, calcolata come differenza tra il costo del nuovo livello e quello del vecchio livello (pari a 0 se assente). |
| `calculate_state_cost` | Calcola il costo totale sommando i costi di tutte le capability attualmente attive (ovvero con livello diverso da `None`) presenti nello stato. |
| `calculate_net_cost` | Calcola la differenza di costo totale (costo netto) tra un stato finale e uno stato iniziale, verificando prima che entrambi gli stati contengano la medesima struttura di nodi e capability. |


## `requirements.py`
| Funzione | Descrizione |
| :--- | :--- |
| `validate_requirement` | Valida ricorsivamente la struttura JSON di un requisito, verificando che gli operatori siano validi (`all` / `any`) e che le capability specificate esistano nel catalogo. |
| `required_capabilities` | Estrae e restituisce l'insieme (`set`) di tutte le capability menzionate ricorsivamente all'interno di un requisito. |
| `evaluate_requirement` | Calcola e restituisce la probabilita' di soddisfazione di un requisito per un dato nodo e stato, supportando la sovrascrittura temporanea dei livelli tramite `overrides`. |

## Euristica

Il flusso principale è:

1. raggruppare i requirements per nodo;
2. calcolare la criticità dei nodi;
3. generare solo miglioramenti rilevanti;
4. se necessario, valutare riallocazioni composte da downgrade + miglioramento;
5. selezionare il candidato migliore secondo beneficio/efficienza e vincolo di budget.

I downgrade non rappresentano rimozioni: modificano una capability già attiva verso un livello inferiore per liberare budget.

| Funzione | Descrizione |
| :--- | :--- |
| `is_reallocation` | Property della dataclass `HeuristicCandidate` che indica se il candidato include un'azione di downgrade (ovvero se si tratta di una riallocazione di budget). |
| `group_requirements_by_node` | Raggruppa i requisiti dei servizi per ciascun nodo in base alla mappatura definita nel placement, validando la congruenza dell'applicazione e dei requisiti. |
| `build_relevant_capabilities` | Precalcola e restituisce una mappa contenente le capability uniche (ordinate) richieste da tutti i servizi associati a ciascun nodo. |
| `build_capability_levels` | Precalcola e restituisce un dizionario contenente la sequenza ordinata di livelli numerici disponibili per ogni capability del catalogo. |
| `calculate_node_priority` | Calcola il punteggio euristico di criticità di un nodo basandosi insoddisfazione dei requisiti associati e sul numero di capability richieste (con supporto per `overrides` temporanei). |
| `calculate_action_benefit` | Stima la riduzione della criticità (beneficio) ottenibile su un nodo applicando una specifica azione di miglioramento. |
| `calculate_reallocation_benefit` | Calcola il beneficio netto combinato ottenuto applicando un downgrade su una capability e un miglioramento su un'altra. |
| `rank_nodes` | Ordina la lista dei nodi dell'infrastruttura dal più critico al meno critico in base alla priorità calcolata. |
| `generate_improvement_actions` | Genera tutte le possibili azioni valide di aggiunta (`ADD`) o incremento (`MODIFY` in upgrade) per un dato nodo e i suoi requisiti. |
| `generate_downgrade_actions` | Genera l'elenco delle azioni di ridimensionamento (`MODIFY` in downgrade) che consentono di liberare budget, escludendo le capability già ridimensionate. |
| `find_best_improvement_action` | Individua la migliore azione diretta di miglioramento (con maggiore efficienza/beneficio) finanziabile con il budget disponibile su un determinato nodo. |
| `find_best_reallocation_action` | Cerca la migliore combinazione di downgrade e miglioramento che rispetti il budget disponibile e massimizzi l'efficienza complessiva. |
| `select_better_candidate` | Confronta e seleziona il candidato migliore tra un'azione diretta di miglioramento e un'azione di riallocazione. |
| `_is_better_candidate` | Confronta due candidati e determina se il primo è strettamente migliore del secondo valutando in ordine: efficienza, beneficio, costo minore e ordinamento alfabetico dell'azione. |


## `utils.py`
| Funzione | Descrizione |
| --- | --- |
| `load_json` | Carica un file JSON e restituisce il contenuto come dizionario. |
| `load_catalog` | Carica il catalogo delle security capability. |
| `load_infrastructure` | Carica la descrizione dell'infrastruttura. |
| `load_application` | Carica la descrizione di un'applicazione. |
| `load_placement` | Carica la configurazione del placement. |
| `save_json` | Salva un dizionario su file JSON creando le cartelle se mancanti. |
| `get_placement_nodes` | Restituisce la lista dei nodi usati dal placement senza duplicati. |
| `get_applicable_capabilities` | Restituisce le capability del catalogo applicabili a un certo tipo di nodo. |
| `validate_placement` | Controlla che il placement sia coerente con catalogo e infrastruttura. |
| `create_initial_state` | Costruisce e convalida lo stato iniziale ($P_0$) a partire da un placement. |
| `build_final_policy` | Costruisce la politica finale confrontando lo stato iniziale con quello finale. |
| `display_solution_summary` | Stampa a terminale un riepilogo della soluzione con score, budget e azioni. |