"""M0 — Probe della profondita' storica dei tick del broker FxPro via MetaTrader5.

E' il PRIMO esperimento del progetto: la profondita' dello storico tick di FxPro su MT5 non e'
pubblicata e va misurata empiricamente. L'esito determina quanto storico del broker potremo usare
per il fine-tuning/validazione (il design NON dipende dall'esito: Dukascopy resta la base storica).

Cosa fa:
  1. si connette al terminale MT5 GIA' aperto e loggato (``mt5.initialize()``);
  2. riporta terminale, account e broker (server);
  3. seleziona EURUSD e trova il tick piu' vecchio disponibile (``copy_ticks_from`` da data remota);
  4. ispeziona i campi dei tick (bid/ask/last/volume/volume_real/flags) e la granularita' ms
     -> conferma atteso: per il forex FxPro ``last``/``volume``/``volume_real`` sono ~0 (nessun
     traded volume), quindi il "volume" utilizzabile e' il tick count derivato;
  5. campiona i tick/giorno su alcuni giorni feriali recenti;
  6. scrive un report leggibile a schermo e ``data/fxpro_probe_report.json``.

Uso:
    python -m forex_tutor.scripts.probe_fxpro_depth --symbol EURUSD

Prerequisito: terminale MetaTrader5 di FxPro installato, aperto e loggato sul conto.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from .. import constants as C
from .. import paths

# Flag dei tick MT5 (da MqlTick.flags) — ridefiniti qui per non dipendere dall'import a modulo caricato.
TICK_FLAG_BID = 2
TICK_FLAG_ASK = 4
TICK_FLAG_LAST = 8
TICK_FLAG_VOLUME = 16
TICK_FLAG_BUY = 32
TICK_FLAG_SELL = 64

# data "molto vecchia" da cui chiedere i primi tick: precede qualsiasi storico broker plausibile
_EPOCH_PROBE = datetime(2000, 1, 1, tzinfo=timezone.utc)


@dataclass
class ProbeReport:
    ok: bool = False
    error: str | None = None
    symbol: str = C.SYMBOL_DEFAULT
    generated_utc: str = ""
    # terminale / account
    terminal: dict = field(default_factory=dict)
    account: dict = field(default_factory=dict)
    symbol_info: dict = field(default_factory=dict)
    # profondita'
    earliest_tick_utc: str | None = None
    earliest_tick_ms: int | None = None
    history_span_days: float | None = None
    # campi
    field_stats: dict = field(default_factory=dict)
    ms_granularity: bool | None = None
    flags_seen: list[str] = field(default_factory=list)
    # campionamento giornaliero
    daily_samples: list[dict] = field(default_factory=list)
    recommendation: str = ""


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _decode_flags(flag_val: int) -> list[str]:
    names = []
    for bit, name in (
        (TICK_FLAG_BID, "BID"),
        (TICK_FLAG_ASK, "ASK"),
        (TICK_FLAG_LAST, "LAST"),
        (TICK_FLAG_VOLUME, "VOLUME"),
        (TICK_FLAG_BUY, "BUY"),
        (TICK_FLAG_SELL, "SELL"),
    ):
        if flag_val & bit:
            names.append(name)
    return names


def _connect(mt5, args) -> None:
    """Inizializza MT5 verso il terminale gia' aperto. Solleva RuntimeError su fallimento."""
    kwargs = {}
    if args.terminal_path:
        kwargs["path"] = args.terminal_path
    # login esplicito solo se fornito (di norma non serve: si usa la sessione del terminale)
    if args.login:
        kwargs.update(login=int(args.login), password=args.password or "", server=args.server or "")
    ok = mt5.initialize(**kwargs) if kwargs else mt5.initialize()
    if not ok:
        code, msg = mt5.last_error()
        raise RuntimeError(
            f"mt5.initialize() fallito (code={code}): {msg}. "
            "Verifica che il terminale MetaTrader5 di FxPro sia APERTO e LOGGATO."
        )


def _find_earliest(mt5, symbol: str):
    """Ritorna il primo tick disponibile (structured array di 1 elemento) o None.

    Metodo: ``copy_ticks_from`` da una data molto vecchia ritorna i tick PIU' VECCHI del server.
    """
    ticks = mt5.copy_ticks_from(symbol, _EPOCH_PROBE, 1, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        return None
    return ticks[0]


def _sample_day(mt5, symbol: str, day: datetime):
    """Conta i tick di un giorno UTC [00:00, 24:00) e ritorna (count, first_msc, last_msc, sample)."""
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    ticks = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        return 0, None, None, None
    return len(ticks), int(ticks[0]["time_msc"]), int(ticks[-1]["time_msc"]), ticks


def _recent_weekdays(n: int) -> list[datetime]:
    """Ultimi ``n`` giorni feriali (lun-ven) completi, escludendo oggi (potenzialmente parziale)."""
    out: list[datetime] = []
    d = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    while len(out) < n:
        if d.weekday() < 5:  # 0=lun ... 4=ven
            out.append(d)
        d -= timedelta(days=1)
    return out


def _field_stats(ticks) -> tuple[dict, bool, list[str]]:
    """Frazione di valori non-zero per last/volume/volume_real; granularita' ms; flag visti."""
    n = len(ticks)
    last_nz = int((ticks["last"] != 0).sum())
    vol_nz = int((ticks["volume"] != 0).sum())
    volr_nz = float((ticks["volume_real"] != 0).sum())
    bidvol_nz = 0  # MT5 forex non ha bid/ask volume: campo assente nella struct MqlTick
    # granularita' ms: esistono time_msc non multipli di 1000 (cioe' frazioni di secondo)?
    ms = ticks["time_msc"].astype("int64")
    ms_granular = bool(((ms % 1000) != 0).any())
    # flag: unione dei flag visti su un campione
    seen: set[str] = set()
    for fv in ticks["flags"][: min(n, 5000)]:
        seen.update(_decode_flags(int(fv)))
    stats = {
        "n_ticks_sampled": n,
        "last_nonzero_frac": round(last_nz / n, 6) if n else None,
        "volume_nonzero_frac": round(vol_nz / n, 6) if n else None,
        "volume_real_nonzero_frac": round(volr_nz / n, 6) if n else None,
        "bidask_volume_present": bidvol_nz > 0,
    }
    return stats, ms_granular, sorted(seen)


def run_probe(args) -> ProbeReport:
    rep = ProbeReport(symbol=args.symbol, generated_utc=_utc(datetime.now(timezone.utc)))
    try:
        import MetaTrader5 as mt5  # import ritardato: dipendenza solo-Windows
    except Exception as exc:  # noqa: BLE001
        rep.error = f"Impossibile importare MetaTrader5: {exc}. Installa il pacchetto su Windows."
        rep.recommendation = "Installa MetaTrader5 (pip) ed esegui su Windows con il terminale FxPro aperto."
        return rep

    try:
        _connect(mt5, args)
    except RuntimeError as exc:
        rep.error = str(exc)
        rep.recommendation = "Apri e logga il terminale MetaTrader5 di FxPro, poi ripeti."
        return rep

    try:
        term = mt5.terminal_info()
        acc = mt5.account_info()
        if term is not None:
            rep.terminal = {"name": term.name, "company": term.company, "path": term.path, "build": term.build}
        if acc is not None:
            rep.account = {"login": acc.login, "server": acc.server, "company": acc.company, "currency": acc.currency}

        if not mt5.symbol_select(args.symbol, True):
            rep.error = f"Impossibile selezionare il simbolo {args.symbol}. Nome corretto nel Market Watch?"
            rep.recommendation = "Verifica il nome esatto del simbolo FxPro (potrebbe avere suffisso, es. EURUSD.m)."
            return rep

        si = mt5.symbol_info(args.symbol)
        if si is not None:
            rep.symbol_info = {"digits": si.digits, "point": si.point, "spread": si.spread, "path": si.path}

        # 1) tick piu' vecchio
        first = _find_earliest(mt5, args.symbol)
        if first is None:
            rep.error = "copy_ticks_from non ha restituito tick: storico tick non disponibile via MT5."
            rep.recommendation = "Usa Dukascopy come unica base storica; FxPro solo per tick recenti in avanti."
            return rep
        earliest_ms = int(first["time_msc"])
        earliest_dt = datetime.fromtimestamp(earliest_ms / 1000, tz=timezone.utc)
        rep.earliest_tick_ms = earliest_ms
        rep.earliest_tick_utc = _utc(earliest_dt)
        rep.history_span_days = round((datetime.now(timezone.utc) - earliest_dt).total_seconds() / 86400, 1)

        # 2) campionamento giornaliero recente + ispezione campi sul giorno piu' ricco
        richest = None
        for day in _recent_weekdays(args.sample_days):
            count, first_msc, last_msc, ticks = _sample_day(mt5, args.symbol, day)
            rep.daily_samples.append(
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "tick_count": count,
                    "first_msc": first_msc,
                    "last_msc": last_msc,
                }
            )
            if ticks is not None and (richest is None or count > len(richest)):
                richest = ticks

        if richest is not None:
            rep.field_stats, rep.ms_granularity, rep.flags_seen = _field_stats(richest)

        # 3) raccomandazione
        vol_frac = rep.field_stats.get("volume_nonzero_frac")
        vol_note = (
            "volume di size ASSENTE (atteso per forex OTC): usa tick_count come proxy di volume"
            if not vol_frac
            else f"volume non-zero nel {vol_frac:.1%} dei tick (inatteso: verifica se e' vero traded volume)"
        )
        rep.recommendation = (
            f"Storico tick FxPro disponibile da {rep.earliest_tick_utc} "
            f"(~{rep.history_span_days} giorni). {vol_note}. "
            "Piano: Dukascopy come base storica lunga (con volumi di liquidita'); "
            "FxPro per coerenza col broker su finestre recenti + downloader incrementale in avanti."
        )
        rep.ok = True
        return rep
    finally:
        mt5.shutdown()


def _print_report(rep: ProbeReport) -> None:
    line = "=" * 72
    print(line)
    print(f"  FxPro MT5 — probe profondita' tick  [{rep.symbol}]   {rep.generated_utc} UTC")
    print(line)
    if not rep.ok:
        print(f"  ESITO: FALLITO\n  Errore: {rep.error}")
        if rep.recommendation:
            print(f"  Suggerimento: {rep.recommendation}")
        print(line)
        return
    t, a = rep.terminal, rep.account
    print(f"  Terminale : {t.get('name')} (build {t.get('build')}) — {t.get('company')}")
    print(f"  Account   : login={a.get('login')} server={a.get('server')} ccy={a.get('currency')}")
    print(f"  Simbolo   : digits={rep.symbol_info.get('digits')} point={rep.symbol_info.get('point')}")
    print("-" * 72)
    print(f"  Tick piu' vecchio : {rep.earliest_tick_utc} UTC  (~{rep.history_span_days} giorni di storico)")
    print(f"  Granularita' ms   : {'SI' if rep.ms_granularity else 'NO (solo secondi)'}")
    print(f"  Flag visti        : {', '.join(rep.flags_seen) or '-'}")
    fs = rep.field_stats
    print(
        f"  Campi tick        : last!=0 {fs.get('last_nonzero_frac')} | "
        f"volume!=0 {fs.get('volume_nonzero_frac')} | volume_real!=0 {fs.get('volume_real_nonzero_frac')}"
    )
    print("-" * 72)
    print("  Tick/giorno (giorni feriali recenti):")
    for s in rep.daily_samples:
        print(f"    {s['date']}  ->  {s['tick_count']:>10,} tick")
    print("-" * 72)
    print(f"  Raccomandazione: {rep.recommendation}")
    print(line)


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe profondita' storica tick FxPro (MT5).")
    ap.add_argument("--symbol", default=C.SYMBOL_DEFAULT, help="Simbolo (default EURUSD; occhio a suffissi broker).")
    ap.add_argument("--sample-days", type=int, default=5, help="Giorni feriali recenti da campionare.")
    ap.add_argument("--login", type=int, default=None, help="Login MT5 esplicito (di norma non serve).")
    ap.add_argument("--password", default=None)
    ap.add_argument("--server", default=None)
    ap.add_argument("--terminal-path", default=None, help="Path a terminal64.exe se non auto-rilevabile.")
    args = ap.parse_args()

    rep = run_probe(args)
    _print_report(rep)

    paths.ensure_dirs()
    out = paths.DATA_DIR / "fxpro_probe_report.json"
    out.write_text(json.dumps(asdict(rep), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport salvato in: {out}")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
