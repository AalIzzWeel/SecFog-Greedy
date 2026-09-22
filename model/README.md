# Modulo `model`

Contiene il catalogo delle capability, i profili dei security requirement e i generatori delle istanze usate nei benchmark.

## Struttura

| Percorso | Contenuto |
| --- | --- |
| `security_catalog.json` | Capability, categorie, applicabilità, livelli, efficacia e costi. |
| `requirement_profiles.json` | Profili riutilizzabili di requirement `all`/`any`. |
| `applications/smartbuilding.json` | Applicazione di esempio. |
| `scalable_generator.py` | Generatore delle istanze di scalabilità. |
| `generated/` | Istanze scalabili generate. |
| `comparison_generator.py` | Generatore delle piccole istanze per il confronto esatto. |
| `comparison/` | Famiglia deterministica usata da greedy ed esaustivo. |

## Catalogo delle capability

Esempio ridotto:

```json
{
  "actions": {"allow_modify": true},
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

`probability` rappresenta l'efficacia probabilistica della capability. Il rischio locale usato dall'euristica è `1 - probability`. `cost` è il costo assoluto del livello; il costo di una modifica è la differenza fra costo nuovo e precedente.

La versione corrente ammette soltanto azioni `MODIFY`. `L0` non rappresenta una capability assente: è un livello attivo con costo ed efficacia propri.

## Profili dei requirement

`requirement_profiles.json` contiene template ricorsivi basati su:

```json
{"all": ["firewall", "network_ids"]}
```

```json
{"any": ["encrypted_storage", "obfuscated_storage"]}
```

- `all`: devono contribuire tutti i figli;
- `any`: sono ammesse alternative;
- una stringa identifica direttamente una capability.

I generatori verificano che i requirement siano validi e applicabili al tipo di nodo scelto.

## Istanze scalabili

Ogni directory `generated/instance_n<N>_s<S>_seed<SEED>/` contiene:

```text
infrastructure.json  # nodi cloud/edge e operatori
application.json     # servizi, classi, profili e requirement
placement.json       # placement fissato e security_state iniziale
```

Configurazioni predefinite:

| Nodi | Servizi |
| ---: | ---: |
| 25 | 5 |
| 50 | 10 |
| 100 | 15 |
| 200 | 25 |
| 400 | 50 |

Per ogni taglia vengono usati i seed `42`, `123` e `999`, per un totale di 15 istanze.

Caratteristiche:

- 30% dei nodi cloud e 70% edge;
- classi `light`, `medium`, `heavy` distribuite circa 30/50/20;
- rispettivamente 1, 2 o 3 profili di requirement per servizio;
- servizi assegnati soltanto a nodi compatibili;
- `security_state` limitato alle capability richieste e applicabili;
- livelli iniziali scelti pseudo-casualmente fra quelli disponibili;
- nodi dello stato ordinati per numero decrescente di capability menzionate dai requirement.

La generazione è deterministica. Per ogni seed principale vengono usati:

- `seed` per assegnare i profili;
- `seed + 1` per il placement;
- `seed + 2` per i livelli iniziali.

Generazione:

```bash
python3 -m model.scalable_generator
```

Il comando genera o aggiorna tutte le 15 directory in `model/generated/`.

## Istanze per il confronto esatto

`comparison_generator.py` crea piccole istanze deterministiche, sufficientemente contenute da poter essere enumerate da OR-Tools.

Ogni scenario contiene:

- 2 nodi: `edge1` e `cloud1`;
- 2 servizi, uno per nodo;
- 3 capability attive per nodo;
- livelli iniziali centrali;
- 6 coppie nodo-capability complessive.

Scenari disponibili:

| Scenario | Focus |
| --- | --- |
| `storage` | Protezione dello storage e sicurezza fisica. |
| `communication` | Comunicazione sicura, protezione di rete e rilevamento intrusioni. |
| `monitoring` | Monitoraggio, storage e sicurezza fisica. |
| `network` | Protezione della rete e sicurezza fisica. |
| `detection` | Rilevamento intrusioni, storage e sicurezza fisica. |

Generazione completa:

```bash
python3 -m model.comparison_generator
```

Sottoinsieme e directory personalizzata:

```bash
python3 -m model.comparison_generator \
  --scenarios storage communication \
  --output-dir model/comparison
```

Opzioni disponibili:

| Opzione | Default |
| --- | --- |
| `--scenarios ...` | Tutti e cinque gli scenari |
| `--catalog` | `model/security_catalog.json` |
| `--profiles` | `model/requirement_profiles.json` |
| `--output-dir` | `model/comparison/` |

Ogni directory `comparison/realistic_edge_cloud_<scenario>/` contiene:

```text
catalog.json
infrastructure.json
application.json
placement.json
metadata.json
```

Il catalogo viene copiato nell'istanza per rendere il confronto autosufficiente. `metadata.json` registra scenario, dimensioni, costo iniziale e capability presenti. L'ottimo non è incorporato nelle istanze: viene calcolato dalla ricerca esaustiva per ogni budget.

## Relazione fra le due famiglie

| Famiglia | Scopo | Algoritmo principale |
| --- | --- | --- |
| `generated/` | Valutare scalabilità e comportamento sui seed | Fast Greedy |
| `comparison/` | Misurare gap, runtime e chiamate ProbLog rispetto all'ottimo | Fast Greedy + esaustivo |

Le istanze di confronto servono a valutare la qualità della soluzione greedy; quelle scalabili servono a mostrare che il greedy rimane applicabile quando l'enumerazione completa diventa impraticabile.
