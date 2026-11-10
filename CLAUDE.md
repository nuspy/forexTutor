# ForexTutor — istruzioni per l'implementazione

Sistema desktop Windows di auto-apprendimento che impara a imitare lo stile di trading dell'utente su EURUSD (dati 1 secondo) e poi si raffina con reward misto imitazione+P&L.

## Documenti di riferimento (leggere PRIMA di implementare)

1. **`docs/IMPLEMENTATION_PLAN.md`** — il piano completo e vincolante: architettura, schemi dati, interfacce, milestone M0→M8 con criteri di verifica. In caso di dubbio vale questo documento.
2. `docs/research/metodi-apprendimento.md` — perché sono stati scelti BC gerarchico + RL con reward decomposta (e perché GAIL/Decision Transformer sono stati scartati). Consultare solo se serve contesto.
3. `docs/research/fonti-dati.md` — dettagli su Dukascopy/FxPro MT5/volumi. Consultare per implementare `src/forex_tutor/data/`.

## Stato di avanzamento

- [x] M0 — Bootstrap + probe profondità FxPro *(codice completo; env + GPU verificati. Il dato reale di profondità richiede il terminale MT5 FxPro aperto e loggato, poi `ft-probe-fxpro`)*
- [ ] M1 — Pipeline dati (Dukascopy + FxPro → Parquet → barre 1s)
- [ ] M2 — FeatureEngine incrementale + test anti-look-ahead
- [ ] M3 — UI annotazione (PyQt6, replay mode)
- [ ] M4 — Simulatore Gymnasium multi-posizione
- [ ] M5 — Fase A: pretraining self-supervised encoder
- [ ] M6 — Fase B: Behavioral Cloning + ReviewTab
- [ ] M7 — Fase C: RL fine-tuning + walk-forward
- [ ] M8 — Loop integrato per-round + indice di progresso

**Aggiornare questa checklist al completamento di ogni milestone.** Implementare le milestone IN ORDINE: ognuna ha un criterio di verifica eseguibile nel piano — non passare alla successiva finché la verifica non passa.

## Regole non negoziabili

- **Anti-look-ahead**: ogni feature al tempo t dipende SOLO da dati ≤ t. Tutte le normalizzazioni (z-score, percentili) sono rolling/causali, mai fit su tutto il dataset. Il test `tests/test_feature_lookahead.py` (perturba il futuro → feature a ≤t bit-exact identiche) va rieseguito a ogni modifica di `src/forex_tutor/features/`.
- **PyTorch cu128**: la RTX 5090 è sm_120 → serve PyTorch ≥2.7 con wheel `cu128` da index-url dedicato PyTorch. MAI installare la wheel di default di PyPI (non supporta la GPU).
- **Python 3.12** in venv dedicato (`uv venv -p 3.12`) — il Python di sistema è 3.10.
- **Feed dati mai fusi**: Dukascopy/FxPro/altri restano partizioni `source=` separate; join solo a feature-engineering time.
- **Prezzi in f64** (f32 insufficiente a 5 decimali), timestamp UTC, feature f16/f32.
- **Direzione trade dedotta dal segmento** disegnato dall'utente: prezzo uscita > entrata → long, < → short, uguale → rifiutato. Nessuno strumento long/short separato.
- **Multiprocessing su Windows (spawn)**: entrypoint sotto `if __name__ == "__main__"`; ai worker solo path+config picklabili (mai memmap/handle MT5/oggetti talipp). NIENTE multiprocessing nel processo UI: il training gira in QProcess separato, comunicazione file-based (`metrics.jsonl` + sentinella `STOP`).
- **Widget PyQt solo dal main thread**; lavoro pesante in QThread (query chart) o QProcess (training).
- **Checkpoint atomici**: scrivere su tmp + `os.replace`.
- Le componenti della reward (`imitation/pnl/risk/activity`) vanno SEMPRE loggate separatamente in `metrics.jsonl`.

## Comandi principali (una volta implementati)

```
python -m forex_tutor.scripts.probe_fxpro_depth --symbol EURUSD   # M0
python -m forex_tutor.scripts.download_dukascopy --from 2024-01 --to 2024-03
python -m forex_tutor.scripts.build_bars --source dukascopy --from 2024-01 --to 2024-03
python -m forex_tutor.scripts.build_features --from 2024-01 --to 2024-03
python -m forex_tutor.ui.app                                      # app desktop
python -m forex_tutor.training.run --phase {ssl,bc,rl,round} ...
pytest tests\
```

## Prerequisiti macchina (documentati anche nel README)

- Terminale MT5 di FxPro installato e loggato (per `MetaTrader5.initialize()`).
- Node.js (per `dukascopy-node` via npx).
- TA-Lib: wheel binaria win_amd64 (PyPI ≥ 0.5), nessuna compilazione.
- Dati e run in `data\` e `runs\` (gitignored), entrambi sotto la root del progetto.
