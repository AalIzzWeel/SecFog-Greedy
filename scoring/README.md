# Modulo `scoring`

`score_wrapper.py` collega lo stato Python all'oracolo SecFog implementato in ProbLog.

## Responsabilità

`ScoreWrapper` riceve:

- catalogo delle capability;
- infrastruttura Cloud-Edge;
- applicazione e security requirement;
- placement fissato;
- regole di base in `prolog/secfog_base.pl`.

Per ogni stato costruisce un programma ProbLog composto da:

1. regole generiche SecFog;
2. fatti relativi ai nodi e agli operatori;
3. applicazione e lista dei servizi;
4. regole `securityRequirements/2` tradotte dal JSON;
5. fatti probabilistici delle capability attive ai livelli correnti;
6. query sul deployment fissato dal placement.

Il costo delle capability non entra nello score: è gestito separatamente dall'ottimizzatore.

## Traduzione dei requirement

| JSON | ProbLog |
| --- | --- |
| `"authentication"` | `authentication(N)` |
| `{"all": [A, B]}` | congiunzione `(A, B)` |
| `{"any": [A, B]}` | disgiunzione `(A; B)` |

Lo stato viene convertito in fatti del tipo:

```prolog
0.86::authentication(edge1).
```

Per evitare errori `UnknownClause`, il wrapper dichiara inoltre ogni predicato del catalogo sul nodo fittizio `secfog_dummy` con probabilità zero. Questi fatti non attivano capability sui nodi reali.

## Query fissata

Il placement non viene cercato da SecFog: è incorporato nella query. Per esempio:

```prolog
query(secFog(appOp, app, [d(service1, edge1, edgeOp)])).
```

Lo score risultante appartiene a $[0,1]$; valori maggiori indicano una probabilità superiore di soddisfare i security requirement del deployment.

## Cache e contatori

`evaluate(state)` usa `state.key()` come chiave:

- in caso di cache hit restituisce lo score già calcolato;
- in caso di cache miss costruisce il programma, invoca l'API nativa di ProbLog e incrementa `solver_evaluations`.

| Membro | Ruolo |
| --- | --- |
| `cache_size` | Numero di stati memorizzati. |
| `solver_evaluations` | Numero di invocazioni reali di ProbLog. |
| `clear_cache()` | Svuota la cache senza modificare il contatore. |
| `evaluate(state)` | Restituisce lo score dello stato. |
| `_build_program(state)` | Assembla il programma completo. |
| `_build_structure()` | Genera nodi, operatori e applicazione. |
| `_requirement_to_prolog()` | Traduce ricorsivamente un requirement. |
| `_build_security_requirements()` | Genera le regole per tutti i servizi. |
| `_build_query()` | Costruisce la query del placement fissato. |
| `_build_probabilistic_facts()` | Emette i fatti delle capability. |
| `_run_problog_api()` | Esegue ProbLog e restituisce lo score massimo ottenuto. |


Documentazione consultata:
* Using Problog from Python: https://problog.readthedocs.io/en/latest/python.html
* API documentation: https://problog.readthedocs.io/en/latest/api.html

> Nota: L'implementazione del progetto non usa il modello di trust di SecFog.
