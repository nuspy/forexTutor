"""Costanti globali del progetto.

Fonte di verita' unica per: lista dei timeframe, dimensioni derivate, schemi colonne,
parametri strutturali del simulatore. Le shape dei tensori NON vanno mai hardcoded altrove:
derivarle sempre da qui (es. ``N_TF``, ``K_SLOTS``).

Nota sui timeframe: la specifica dell'utente elenca 14 timeframe
(1,5,10,15,30min; 1,2,3,6,12h; 1,2,3,5 giorni). Il piano cita "15" per un errore di conteggio:
la fonte di verita' e' ``TF_LIST`` (14 elementi) e ``N_TF = len(TF_LIST)``.
"""

from __future__ import annotations

from typing import Final

# --- strumento ---
SYMBOL_DEFAULT: Final[str] = "EURUSD"
PIP: Final[float] = 1e-4  # 1 pip su EURUSD (5 decimali -> 1 pip = 10 points)
PRICE_DECIMALS: Final[int] = 5

# --- timeframe (nome -> durata in secondi) --------------------------------------------------
# Ordine crescente di durata; questo ordine e' l'asse "TF" di tutti i tensori feature.
TF_SECONDS: Final[dict[str, int]] = {
    "1m": 60,
    "5m": 300,
    "10m": 600,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "3h": 10800,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
    "2d": 172800,
    "3d": 259200,
    "5d": 432000,
}
TF_LIST: Final[tuple[str, ...]] = tuple(TF_SECONDS.keys())
N_TF: Final[int] = len(TF_LIST)  # = 14

# --- dimensioni feature (contratto FeatureFrame / observation space) ------------------------
N_CANDLE_LOOKBACK: Final[int] = 64  # ultime N candele CHIUSE per TF
N_CANDLE_FIELDS: Final[int] = 9  # o,h,l,c (normalizzati) + ret + range + body + tick_count + vol
N_INDICATORS: Final[int] = 150  # slot indicatori per TF (padding se meno; vedi FeatureSpec)
N_FORMING_FIELDS: Final[int] = 6  # OHLC parziale + % completamento candela + range parziale
N_PATTERN_SLOTS: Final[int] = 8  # id pattern (CDL/chart) attivi per TF, padded a 0
N_FAST_FEATURES: Final[int] = 32  # feature native a 1s (Tier A)
N_REGIME_FEATURES: Final[int] = 16  # feature di regime/sessione/tempo

# gruppi semantici di indicatori (per Variable Selection Network)
INDICATOR_GROUPS: Final[tuple[str, ...]] = (
    "trend",
    "momentum",
    "volatility",
    "volume",
    "support_resistance",
)

# --- simulatore / portafoglio ---------------------------------------------------------------
K_SLOTS: Final[int] = 4  # posizioni concorrenti massime (portafoglio multi-posizione)
N_PORTFOLIO_FIELDS: Final[int] = 8  # per slot: is_open, dir, upl, time_in_pos, dist_entry, mae, mfe, size

# direzione trade
DIR_LONG: Final[int] = 1
DIR_SHORT: Final[int] = -1
DIR_FLAT: Final[int] = 0

# azione "open" discreta
OPEN_HOLD: Final[int] = 0
OPEN_LONG: Final[int] = 1
OPEN_SHORT: Final[int] = 2
N_OPEN_ACTIONS: Final[int] = 3

# stili di trading (finestra tipica del trade)
TRADING_STYLES: Final[tuple[str, ...]] = ("scalping", "day", "swing", "multiday")

# --- schemi colonne (ordine FISSO) ----------------------------------------------------------
TICK_COLUMNS: Final[tuple[str, ...]] = ("ts_ms", "bid", "ask", "bid_vol", "ask_vol")

BAR1S_COLUMNS: Final[tuple[str, ...]] = (
    "ts_s",
    "o_bid", "h_bid", "l_bid", "c_bid",
    "o_ask", "h_ask", "l_ask", "c_ask",
    "tick_count",
    "bid_vol_sum",
    "ask_vol_sum",
    "spread_mean",  # in pip
    "imbalance",
)

# --- sorgenti dati ammesse ------------------------------------------------------------------
DATA_SOURCES: Final[tuple[str, ...]] = ("dukascopy", "fxpro", "databento", "darwinex")
