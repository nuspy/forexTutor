"""Configurazione dell'applicazione (pydantic v2).

``load_config()`` legge ``configs/default.yaml`` (piu' eventuali override) e ritorna un ``AppConfig``
immutabile. All'avvio di un run, ``AppConfig.freeze_to(run_dir)`` scrive il config congelato
in ``runs/<id>/config_frozen.yaml`` per riproducibilita'.

In M0 il modello e' volutamente minimale (dati + symbol + seed): le sezioni di feature/sim/model/
training verranno aggiunte come sotto-modelli nelle milestone successive senza rompere questa API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from . import constants as C
from . import paths


class DataConfig(BaseModel):
    """Parametri della pipeline dati."""

    model_config = {"frozen": True}

    symbol: str = C.SYMBOL_DEFAULT
    primary_source: str = "dukascopy"  # base storica
    broker_source: str = "fxpro"  # coerenza col broker di esecuzione


class FxProConfig(BaseModel):
    """Parametri di connessione/probe MT5 FxPro.

    Le credenziali NON vanno messe qui: MT5 usa il terminale gia' loggato
    (``mt5.initialize()`` senza login). login/password/server sono opzionali,
    usati solo se si vuole forzare una connessione esplicita.
    """

    model_config = {"frozen": True}

    login: int | None = None
    password: str | None = None
    server: str | None = None
    terminal_path: str | None = None  # path del terminal64.exe, se non auto-rilevabile


class AppConfig(BaseModel):
    """Config radice dell'applicazione."""

    model_config = {"frozen": True}

    seed: int = 42
    data: DataConfig = Field(default_factory=DataConfig)
    fxpro: FxProConfig = Field(default_factory=FxProConfig)

    def freeze_to(self, run_dir: Path) -> Path:
        """Scrive il config congelato in ``run_dir/config_frozen.yaml`` e ritorna il path."""
        run_dir.mkdir(parents=True, exist_ok=True)
        out = run_dir / "config_frozen.yaml"
        out.write_text(
            yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return out


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge ricorsivo di due dict (override vince). Non muta gli input."""
    out = dict(base)
    for key, val in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(*override_paths: str | Path) -> AppConfig:
    """Carica ``configs/default.yaml`` con override opzionali (in ordine, l'ultimo vince).

    Se ``default.yaml`` non esiste, ritorna i default del modello.
    """
    merged: dict[str, Any] = {}
    default_yaml = paths.CONFIGS_DIR / "default.yaml"
    candidates = [default_yaml, *[Path(p) for p in override_paths]]
    for path in candidates:
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            merged = _deep_merge(merged, data)
    return AppConfig.model_validate(merged)
