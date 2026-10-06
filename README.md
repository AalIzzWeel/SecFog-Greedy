# SecFog-Greedy

Ottimizzazione dei livelli delle contromisure di sicurezza di un'applicazione cloud-edge, con placement fissato e budget limitato. Il progetto confronta due strategie greedy con un'enumerazione esaustiva basata su OR-Tools CP-SAT. SecFog, eseguito tramite ProbLog, valuta lo score di sicurezza delle configurazioni.

## Problema e algoritmi

Il placement e l'insieme delle contromisure attive sono fissati. Sono consentite soltanto modifiche di livello (`MODIFY`); `L0` è un livello attivo, con costo ed efficacia propri. Le transizioni greedy avvengono tra livelli adiacenti e riguardano le contromisure richieste dai servizi sui nodi utilizzati dal placement.

Il vincolo economico è `C(finale) - C(iniziale) <= B`: gli upgrade consumano budget e i downgrade lo liberano.

| Strategia | Comportamento |
| --- | --- |
| `upgrade-then-downgrade` (UD) | Parte dallo stato originale, applica upgrade finanziabili e tenta riallocazioni tramite downgrade quando il budget non basta. |
| `downgrade-then-upgrade` (DU) | Porta inizialmente le contromisure a `L0` e aggiunge il costo liberato al budget disponibile, quindi esegue il greedy. |
| Esaustivo | CP-SAT enumera tutte le configurazioni che rispettano il budget; una callback le valuta con SecFog e conserva la migliore. |

L'euristica usa la variazione di efficacia `q(a) = e(nuovo) - e(vecchio)` e l'efficienza `eta(a) = q(a) / delta_c(a)`. Gli upgrade sono ordinati per efficienza decrescente, i downgrade per efficienza crescente. Una coppia nodo-contromisura già migliorata non può essere declassata nella stessa esecuzione.

Le riallocazioni sono accettate solo se migliorano lo score oltre la tolleranza relativa definita in `src/fast_greedy.py` (`RELATIVE_EPSILON = 1e-12`). Il greedy non garantisce l'ottimo globale; l'esaustivo lo certifica solo se l'enumerazione termina completamente con stato `OPTIMAL`.

## Installazione

Ambiente di riferimento: Python 3.12, Linux o Ubuntu su WSL. Dalla directory principale:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Esecuzione di un'istanza

Il runner usa per default `instance_n25_s5_seed42`, budget 300 e strategia UD:

```bash
python3 -m src.run_fast_greedy
python3 -m src.run_fast_greedy --budget 300 --approach downgrade-then-upgrade
```

I percorsi sono personalizzabili con `--catalog`, `--infrastructure`, `--application`, `--placement` e `--base`. Per l'esaustivo usare istanze piccole: vedere [src/README.md](src/README.md).

## Risultati e grafici

Per rigenerare i grafici di scalabilità dai 1.600 run conservati:

```bash
python3 -m experiments.plot_graphs --csv results/fast_benchmark_thesis_merged.csv
```

I grafici vengono salvati in PNG in `results/plots/`. Il confronto con l'esaustivo richiede ancora il CSV definitivo: il file disponibile nel repository usa budget 0, 100, 300, 400 e non documenta tutti i budget discussi nella tesi. Le PNG del confronto sono conservate in attesa dell'allineamento. Vedere [results/README.md](results/README.md).

## Ripetere gli esperimenti

```bash
# 160 istanze: otto taglie e 20 seed
python3 -m model.scalable_generator

# Controllo rapido: 8 run
python3 -m experiments.run_fast_benchmarks --profile quick

# Scalabilità completa: 1.600 run
python3 -m experiments.run_fast_benchmarks --profile thesis

# Confronto su cinque istanze piccole
python3 -m experiments.run_comparison_benchmarks
```

Il benchmark di confronto genera le proprie istanze. Per entrambe le famiglie, la generazione è deterministica rispetto ai seed. I nuovi benchmark producono CSV e JSON con timestamp; per scegliere esattamente i risultati da visualizzare usare sempre `--csv`.

## Struttura

| Directory | Contenuto |
| --- | --- |
| [model](model/README.md) | Catalogo, profili dei requisiti e generatori delle istanze. |
| [optimizer](optimizer/README.md) | Stati, azioni, costi, validazione ed euristica. |
| [src](src/README.md) | Algoritmi greedy ed esaustivo e relativi runner. |
| [scoring](scoring/README.md) | Collegamento Python–ProbLog e cache dello score. |
| [prolog](prolog/README.md) | Regole SecFog; il modello di trust non è incluso. |
| [experiments](experiments/README.md) | Benchmark, metriche e script dei grafici. |
| [results](results/README.md) | Risultati conservati e stato di riproducibilità. |
