# Modulo `src`

## `fast_greedy.py`

Implementa `FastGreedyOptimizer` e `FastGreedyStep`.

```python
@dataclass(frozen=True)
class FastGreedyStep:
    """Rappresenta una scelta eseguita dal greedy veloce."""

    step_number: int
    action: Action
    cost: int
    benefit: float
    efficiency: float
    node_priority: float
    remaining_budget: int
    downgrade: Action | None = None

    @property
    def is_reallocation(self) -> bool:
        return self.downgrade is not None
```

La ricerca usa l'euristica di `optimizer/heuristic.py` invece di interrogare SecFog per ogni candidato. SecFog viene usato dal `ScoreWrapper` per lo score iniziale e finale. Ogni step può essere:

- un miglioramento diretto (`ADD` o upgrade `MODIFY`);
- una riallocazione atomica composta da downgrade + miglioramento.

Il budget è aggiornato con il costo netto della mossa. 

La politica `allow_reversal` controlla se una capability migliorata in precedenza può successivamente essere usata come sorgente di downgrade.

## `run_fast_greedy.py`

Runner da riga di comando:

```bash
python3 -m src.run_fast_greedy --budget 300 --reversal-policy allow
```

Carica catalogo, infrastruttura, applicazione e placement, costruisce lo stato iniziale, esegue il fast greedy e stampa history, score finale, budget residuo e numero di valutazioni reali ProbLog.
