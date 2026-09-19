# Modulo `prolog`

`secfog_base.pl` contiene il nucleo dichiarativo di SecFog utilizzato come oracolo probabilistico.

## Regole

Il file definisce:

```prolog
secFog(OpA, A, D) :-
    app(A, L),
    deployment(OpA, L, D).

deployment(_, [], []).

deployment(OpA, [C|Cs], [d(C, N, OpN)|D]) :-
    node(N, OpN),
    securityRequirements(C, N),
    deployment(OpA, Cs, D).
```

Per ogni servizio, `deployment/3` verifica che il nodo assegnato esista e soddisfi il relativo `securityRequirements/2`. Le probabilità derivano dai fatti delle capability generati dal wrapper Python.

## Contenuto generato a runtime

[`scoring/score_wrapper.py`](../scoring/score_wrapper.py) aggiunge dinamicamente:

- nodi e operatori dell'infrastruttura;
- applicazione e servizi;
- security requirement;
- fatti probabilistici delle capability;
- query con il deployment completo già fissato.

Il progetto usa quindi SecFog per **valutare** un placement, non per cercare un'assegnazione alternativa dei servizi.

## Perimetro rispetto a SecFog originale

L'articolo originale descrive anche relazioni e modelli di trust tra operatori. Questa implementazione **non include il trust model**: lo score dipende soltanto dai security requirement e dall'efficacia probabilistica delle capability attive.
