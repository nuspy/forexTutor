# ForexTutor

Sistema desktop Windows di auto-apprendimento che impara a **imitare lo stile di trading** dell'utente su EURUSD (dati a 1 secondo) e poi si raffina con reward misto imitazione + P&L.

Vedi **`docs/IMPLEMENTATION_PLAN.md`** per il piano completo e **`CLAUDE.md`** per le regole di implementazione. Le ricerche di background sono in `docs/research/`.

## Prerequisiti (Windows 11)

- **Python 3.12** (il default di sistema puo' essere 3.10 → usa il venv dedicato).
- **[uv](https://docs.astral.sh/uv/)** per la gestione dell'ambiente.
- **GPU NVIDIA RTX 5090** (sm_120): richiede PyTorch ≥ 2.7 con wheel **cu128** — gia' configurato in `pyproject.toml` via `[tool.uv.sources]`. **Non** installare la wheel di default PyPI.
- **Node.js** (per `dukascopy-node` via `npx`, usato da M1).
- **Terminale MetaTrader5 di FxPro** installato, aperto e loggato (per il probe M0 e i download tick del broker). `MetaTrader5` (pip) funziona solo su Windows.
- **TA-Lib**: installata come wheel binaria `win_amd64` da PyPI (`TA-Lib>=0.5.1`), nessuna compilazione C.

## Setup

```powershell
uv venv -p 3.12
uv pip install -e ".[dev]"
```

Verifica GPU:

```powershell
.venv\Scripts\python -c "import torch; print(torch.__version__, torch.cuda.get_device_name(0))"
# atteso: 2.7.x  NVIDIA GeForce RTX 5090
```

## Milestone M0 — probe profondita' tick FxPro

Con il terminale MT5 di FxPro aperto e loggato:

```powershell
.venv\Scripts\python -m forex_tutor.scripts.probe_fxpro_depth --symbol EURUSD
```

Stampa un report (terminale, account, tick piu' vecchio disponibile, granularita' ms, campi
volume, tick/giorno) e lo salva in `data/fxpro_probe_report.json`. L'esito determina quanto
storico del broker useremo (il design non ne dipende: Dukascopy resta la base storica).

> Nota: se il simbolo FxPro ha un suffisso (es. `EURUSD.m`), passalo con `--symbol`.

## Struttura

```
src/forex_tutor/     # package
  data/  features/  sim/  models/  training/  eval/  annotations/  ui/  scripts/
configs/             # YAML di configurazione
tests/               # pytest
docs/                # piano + ricerche
data/  runs/         # gitignored (dati e output di training)
```

## Test

```powershell
.venv\Scripts\python -m pytest
```
