# Modulo `model`

Contiene il catalogo delle capability, i template dei security requirement e le istanze scalabili usate negli esperimenti.

## File principali

| Percorso | Contenuto |
| --- | --- |
| `security_catalog.json` | Categoria, applicabilità, livelli, probabilità e costi delle capability. |
| `requirement_profiles.json` | Template riutilizzabili di security requirement `all`/`any`. |
| `scalable_generator.py` | Generatore deterministico delle istanze. |
| `generated/` | Istanze prodotte per benchmark e test. |

I template in `requirement_profiles.json` descrivono esclusivamente requisiti di sicurezza applicativi.

## Struttura di un'istanza

Ogni directory `instance_n<N>_s<S>_seed<SEED>/` contiene:

```text
infrastructure.json  # nodi cloud/edge e operatori
application.json     # servizi, classi, template assegnati e requirement
placement.json       # assegnazione servizio-nodo e security_state iniziale
```

`security_state` contiene soltanto capability attive e assegna a ciascuna un livello `L0`, `L1` o `L2`. `L0` non significa assenza: è un livello attivo con costo ed efficacia propri.

## Generazione

Il generatore crea le configurazioni:

| Nodi | Servizi |
| ---: | ---: |
| 25 | 5 |
| 50 | 10 |
| 100 | 15 |
| 200 | 25 |
| 400 | 50 |

Per ogni configurazione usa i seed `42`, `123` e `999`:

```bash
python3 -m model.scalable_generator
```

Le scelte principali sono:

- 30% dei nodi cloud e 70% edge;
- classi di servizio `light`, `medium` e `heavy` in proporzione 30/50/20;
- rispettivamente 1, 2 o 3 template di requirement per servizio;
- assegnazione dei servizi soltanto a tipi di nodo compatibili;
- attivazione iniziale delle capability menzionate dai requirement e applicabili al nodo;
- livello iniziale scelto in modo pseudo-casuale ma riproducibile.

Lo stesso seed produce la stessa istanza. Il generatore usa `seed`, `seed + 1` e `seed + 2` per separare rispettivamente template, placement e stato di sicurezza.

## Formato del catalogo

Esempio ridotto:

```json
{
  "capabilities": {
    "authentication": {
      "category": "virtualization",
      "applicable_to": ["cloud", "edge"],
      "levels": {
        "0": {"probability": 0.75, "cost": 100},
        "1": {"probability": 0.86, "cost": 180},
        "2": {"probability": 0.95, "cost": 320}
      }
    }
  }
}
```

`probability` rappresenta l'efficacia probabilistica della capability al livello indicato; `cost` è il costo assoluto del livello. L'ottimizzatore usa la differenza tra costi assoluti per valutare una transizione.
