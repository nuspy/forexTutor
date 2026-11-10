"""M0 — smoke test dei moduli fondativi (nessuna GPU, nessun MT5 richiesto).

Verifica che package, costanti, paths e config siano coerenti e importabili.
"""

from __future__ import annotations

from forex_tutor import __version__, config, constants, paths


def test_version():
    assert isinstance(__version__, str) and __version__


def test_timeframes_consistent():
    # TF_LIST e' la fonte di verita'; N_TF ne deriva. La spec utente elenca 14 timeframe.
    assert constants.N_TF == len(constants.TF_LIST) == 14
    # durata strettamente crescente
    secs = [constants.TF_SECONDS[tf] for tf in constants.TF_LIST]
    assert secs == sorted(secs) and len(set(secs)) == len(secs)
    assert constants.TF_SECONDS["1m"] == 60
    assert constants.TF_SECONDS["5d"] == 432000


def test_column_schemas_are_unique_and_ordered():
    for cols in (constants.TICK_COLUMNS, constants.BAR1S_COLUMNS):
        assert len(cols) == len(set(cols))  # nessun duplicato
    assert constants.TICK_COLUMNS[0] == "ts_ms"
    assert constants.BAR1S_COLUMNS[0] == "ts_s"


def test_portfolio_and_action_constants():
    assert constants.K_SLOTS >= 1
    assert constants.N_OPEN_ACTIONS == 3
    assert {constants.OPEN_HOLD, constants.OPEN_LONG, constants.OPEN_SHORT} == {0, 1, 2}
    assert constants.DIR_LONG == 1 and constants.DIR_SHORT == -1


def test_paths_resolve_under_repo_root():
    root = paths.repo_root()
    assert (root / "pyproject.toml").is_file()
    assert paths.DATA_DIR.parent == root
    p = paths.tick_partition("dukascopy", "EURUSD", 2024, 7)
    assert p.parts[-1] == "ticks.parquet"
    assert "source=dukascopy" in str(p) and "year=2024" in str(p) and "month=07" in str(p)


def test_config_loads_defaults():
    cfg = config.load_config()
    assert cfg.seed == 42
    assert cfg.data.symbol == "EURUSD"
    assert cfg.data.primary_source == "dukascopy"
    assert cfg.data.broker_source == "fxpro"


def test_config_freeze_roundtrip(tmp_path):
    cfg = config.load_config()
    out = cfg.freeze_to(tmp_path / "run1")
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "symbol: EURUSD" in text
