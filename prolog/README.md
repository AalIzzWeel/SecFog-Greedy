# Modulo `prolog`

`secfog_base.pl` contiene le regole SecFog usate dal progetto come oracolo probabilistico.

Il placement è fissato dal lato Python; `ScoreWrapper` genera dinamicamente:

- nodi e operatori;
- applicazione e servizi;
- security requirements;
- fatti probabilistici delle capability attive;
- query SecFog sul deployment fissato.

**Il progetto non usa il trust model di SecFog**: lo score dipende dai security requirements e dall'efficacia probabilistica delle capability attive.