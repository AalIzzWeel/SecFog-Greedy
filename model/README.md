# Modulo `model`

Contiene i dati e il generatore delle istanze sperimentali.

- `security_catalog.json`: capability, categorie, applicabilità, livelli, probabilità e costi;
- `requirement_profiles.json`: profili di security requirement riutilizzabili;
- `scalable_generator.py`: generazione deterministica di infrastruttura, applicazione, placement e security state a partire da taglia e seed;
- `generated/`: istanze usate nei benchmark.

Ogni cartella in `generated/` contiene:

```text
infrastructure.json
application.json
placement.json
```

Le istanze della tesi usano taglie crescenti di nodi/servizi e seed multipli, così da misurare la scalabilità del fast greedy su configurazioni riproducibili.


