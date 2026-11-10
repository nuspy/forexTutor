"""Risoluzione dei percorsi del progetto.

Tutti i percorsi derivano dalla root del repository (la cartella che contiene ``pyproject.toml``),
in modo che il codice funzioni indipendentemente dalla working directory.
``data/`` e ``runs/`` sono gitignored e stanno sotto la root.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Root del repository = cartella che contiene ``pyproject.toml``.

    Cerca risalendo dai genitori di questo file; fallback a parents[2]
    (src/forex_tutor/paths.py -> root).
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return here.parents[2]


ROOT: Path = repo_root()

CONFIGS_DIR: Path = ROOT / "configs"
DATA_DIR: Path = ROOT / "data"
RUNS_DIR: Path = ROOT / "runs"

# sotto-cartelle dati
TICKS_DIR: Path = DATA_DIR / "ticks"
BARS1S_DIR: Path = DATA_DIR / "bars1s"
FEATURES_DIR: Path = DATA_DIR / "features"
ANNOTATIONS_DB: Path = DATA_DIR / "annotations" / "annotations.db"


def ensure_dirs() -> None:
    """Crea le cartelle dati/run se non esistono (idempotente)."""
    for d in (DATA_DIR, RUNS_DIR, TICKS_DIR, BARS1S_DIR, FEATURES_DIR, ANNOTATIONS_DB.parent):
        d.mkdir(parents=True, exist_ok=True)


def tick_partition(source: str, symbol: str, year: int, month: int) -> Path:
    """Percorso della partizione Parquet dei tick: ticks/source=.../symbol=.../year=.../month=..."""
    return (
        TICKS_DIR
        / f"source={source}"
        / f"symbol={symbol}"
        / f"year={year:04d}"
        / f"month={month:02d}"
        / "ticks.parquet"
    )


def bars1s_partition(source: str, symbol: str, year: int, month: int) -> Path:
    """Percorso della partizione Parquet delle barre 1s."""
    return (
        BARS1S_DIR
        / f"source={source}"
        / f"symbol={symbol}"
        / f"year={year:04d}"
        / f"month={month:02d}"
        / "bars.parquet"
    )
