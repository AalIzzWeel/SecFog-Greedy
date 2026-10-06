# Modello e istanze

| Percorso | Contenuto |
| --- | --- |
| `security_catalog.json` | Contromisure, applicabilità, livelli, efficacia probabilistica e costi. |
| `requirement_profiles.json` | Profili ricorsivi di requisiti di sicurezza. |
| `applications/` | Applicazioni di esempio. |
| `scalable_generator.py`, `generated/` | Generatore e istanze di scalabilità. |
| `comparison_generator.py`, `comparison/` | Generatore e istanze del confronto con l'esaustivo. |

## Catalogo e requisiti

Ogni livello contiene `probability` (efficacia probabilistica) e `cost` (costo assoluto). Il costo di una modifica è la differenza fra costo nuovo e precedente. `L0` è un livello attivo. Il catalogo consente esclusivamente `MODIFY`.

Una stringa nei requisiti identifica una contromisura. Le composizioni `all` e `any` rappresentano rispettivamente congiunzione e disgiunzione, anche annidate:

```json
{"all": ["authentication", {"any": ["encrypted_storage", "obfuscated_storage"]}]}
```

## Scalabilità

```bash
python3 -m model.scalable_generator
```

Il comando genera otto taglie: 25/5, 50/10, 100/15, 200/25, 400/50, 600/70, 800/90, 1000/100 nodi/servizi. Ogni taglia usa 20 seed: 42, 123, 999 e 1000–1016, per 160 istanze.

Ogni directory `generated/instance_n<N>_s<S>_seed<SEED>/` contiene `infrastructure.json`, `application.json` e `placement.json`.

L'infrastruttura ha circa il 30% di nodi cloud e il 70% edge. I servizi sono distribuiti nelle classi light, medium e heavy con proporzioni 30/50/20 e rispettivamente 1, 2 e 3 profili. Il placement usa nodi edge compatibili; lo stato comprende le contromisure richieste sui nodi usati. I livelli iniziali sono scelti pseudo-casualmente.

La generazione è deterministica: il seed principale determina i profili, `seed + 1` il placement e `seed + 2` i livelli iniziali.

## Confronto esatto

```bash
python3 -m model.comparison_generator
python3 -m model.comparison_generator --seeds 42 123 --output-dir model/comparison
```

I seed predefiniti sono 42, 123, 999, 1000, 1001. Ogni directory `comparison/comparison_n3_s3_seed<SEED>/` contiene `catalog.json`, `infrastructure.json`, `application.json`, `placement.json` e `metadata.json`.

Le istanze hanno due nodi edge e uno cloud, con un servizio per nodo. Sono presenti due contromisure per ciascun edge e tre sul cloud: sette coppie complessive. Il seed determina la scelta dei profili e la distribuzione dei livelli iniziali, composta da due `L0`, tre `L1` e due `L2`.

Con tre livelli per coppia, lo spazio ha `3^7 = 2187` configurazioni prima del filtro del budget. L'ottimo viene calcolato dall'esaustivo, non incorporato nel generatore.

Opzioni: `--seeds`, `--catalog`, `--profiles`, `--output-dir`. Il benchmark di confronto genera automaticamente queste istanze.
