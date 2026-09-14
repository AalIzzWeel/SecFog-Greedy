# Modulo `scoring`

`score_wrapper.py` collega lo stato Python a SecFog/ProbLog.

`ScoreWrapper` riceve catalogo, infrastruttura, applicazione, placement e file base ProbLog. Prima valida i dati, poi costruisce il programma completo concatenando:

1. regole SecFog di base;
2. struttura di infrastruttura e applicazione;
3. security requirements;
4. fatti probabilistici delle capability attive;
5. query del deployment fissato.

---

| Funzione | Descrizione |
| :--- | :--- |
| `cache_size` | Property che restituisce il numero attuale di elementi memorizzati nella cache delle valutazioni. |
| `solver_evaluations` | Property che restituisce il conteggio totale delle valutazioni effettuate tramite il solver ProbLog. |
| `clear_cache` | Svuota la cache interna contenente i risultati delle precedenti valutazioni degli stati. |
| `_validate_application` | Metodo privato che verifica che tutti i servizi specificati nel placement siano effettivamente presenti nell'applicazione. |
| `evaluate` | Calcola e restituisce lo score SecFog per un dato stato; utilizza la cache se lo stato è già stato calcolato, altrimenti esegue il programma ProbLog. |
| `_build_program` | Metodo privato che assembla la stringa completa del programma ProbLog unendo regole base, struttura, requisiti di sicurezza, fatti probabilistici e la query. |
| `_build_structure` | Metodo privato che genera i fatti ProbLog relativi ai nodi dell'infrastruttura e all'applicazione con la lista dei suoi servizi. |
| `_requirement_to_prolog` | Metodo privato che converte ricorsivamente le strutture condizionali dei requisiti JSON (`all`, `any`, stringhe) nella sintassi Prolog corrispondente. |
| `_build_security_requirements` | Metodo privato che costruisce le regole Prolog `securityRequirements/2` per ciascun servizio definito nell'applicazione. |
| `_build_query` | Metodo privato che crea la query ProbLog `secFog(...)` basandosi sui componenti e sui nodi assegnati nel placement. |
| `_build_probabilistic_facts` | Metodo privato che converte lo stato corrente in fatti probabilistici ProbLog, raggruppandoli per nodo e categoria di sicurezza. |
| `_run_prolog_api` | Metodo privato che esegue la stringa del programma ProbLog tramite l'API nativa di ProbLog e ne estrae lo score massimo. |

OSS:
* `evaluate(state)` usa `state.key()` come chiave di cache. Solo i cache miss incrementano `solver_evaluations` e invocano realmente ProbLog tramite API Python nativa.

* `clear_cache()` permette di azzerare la cache quando serve nei test o in analisi separate.