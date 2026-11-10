# Ricerca: fonti dati tick/1s EURUSD con volumi per training ML

Report prodotto durante la fase di progettazione (2026-07-25). Le decisioni derivate sono consolidate in `docs/IMPLEMENTATION_PLAN.md` — in caso di conflitto vale il piano.

## 1. FxPro: piattaforme e accesso ai tick

**Piattaforme**: FxPro offre MT4, MT5, cTrader e una piattaforma proprietaria. MT5 è la scelta giusta perché il pacchetto Python `MetaTrader5` (solo Windows — perfetto sulla workstation Win11) parla direttamente col terminale installato.

**`copy_ticks_range` e volumi — punto critico**: i tick MT5 (`MqlTick`) hanno i campi `time_msc, bid, ask, last, volume, volume_real, flags`, ma **per gli strumenti forex i campi `last`, `volume` e `volume_real` restano vuoti/zero** (documentato nei forum MQL5 e nel libro ufficiale MQL5). Il forex OTC di un broker CFD non ha trade volume per tick; il "tick volume" delle barre MT5 è il **conteggio dei tick per barra**. Da FxPro MT5 si ottiene: stream di quote bid/ask con timestamp ms + flags (TICK_FLAG_BID/ASK), da cui derivare tick count e "quote intensity" per qualsiasi aggregazione. Nessun volume "di size" per tick.

**Profondità storica**: non pubblicata da FxPro, varia per broker/server/account. Esperienza riportata su MQL5: i server MT5 retail tengono tick reali tipicamente dal 2017–2021 in poi; segnalazioni di problemi con `copy_ticks_range` oltre ~5 anni. **Va verificata empiricamente** — è il probe di M0 (`scripts/probe_fxpro_depth.py`).

**Limiti pratici**: scaricare a chunk (giorno per giorno: richieste multi-mese esauriscono memoria o vanno in timeout; la prima richiesta su un periodo è lenta perché il terminale scarica on-demand); datetime in **UTC**; il limite "Max bars in chart" riguarda le barre, non i tick. Qualità: i tick riflettono il feed del server FxPro — perfettamente coerenti col broker di esecuzione, che è il loro pregio principale.

**cTrader Open API (alternativa)**: `ProtoOAGetTickDataReq/Res` (protobuf): tick storici bid **o** ask, max 1 settimana per richiesta (paging con `hasMore`), **solo timestamp+prezzo, niente volume**. Più laborioso di MT5 Python, senza vantaggi sui volumi.

## 2. Dukascopy

- **Campi tick**: `timestamp, bidPrice, askPrice, bidVolume, askVolume`. **I volumi ci sono**: rappresentano la **liquidità disponibile al best bid/ask** sul feed SWFX (top-of-book only; convenzionalmente in milioni di unità di valuta base, es. 0.75 ≈ 750k EUR). Nuovo record quando cambia il top-of-book. È **liquidity size quotata**, non traded volume.
- **Profondità EURUSD**: tick e 1s dal **4 maggio 2003**; daily dal 1973. La base storica free più profonda con un campo volume.
- **Download**: `dukascopy-node` (npm, il più mantenuto: CSV/JSON, batch, retry), `duka` (Python), `tickterial`, Tickstory (GUI), o file raw `.bi5` (LZMA) da `datafeed.dukascopy.com`.
- **Affidabilità**: standard de-facto da 15 anni; qualche buco weekend/festività da pulire; è comunque il feed di *un* broker ECN svizzero.

## 3. Altre fonti con volumi

| Fonte | Cosa dà | Volumi | Profondità | Costo/licenza |
|---|---|---|---|---|
| **Darwinex** | Tick FTP (gzip orari, bid e ask separati, ts ms) | Sì: size liquidità top-of-book | ~2017/2018+ | Gratis per clienti verificati (senza deposito minimo); package `darwinex-ticks` |
| **LMAX** | Limit order book anonimo, matching centrale | Sì: bid/ask volume reali del book LMAX | Da 2013 (via Sierra Chart) | Fee da listino; via Sierra Chart con conto LMAX senza fee extra. Il "volume vero" più accessibile in spot FX, ma solo venue LMAX |
| **TrueFX** | Tick CSV mensili gratuiti | No (solo bid/ask) | ~2009+ | Gratis (registrazione) |
| **Polygon.io** | Quote forex aggregate, OHLCV | `v` = quote count, non traded volume | ~10 anni | ~29–199 $/mese |
| **Databento (CME 6E)** | Euro FX futures: Trades, TBBO, MBP, MBO, OHLCV | **Sì: volume REALE da exchange**, ns timestamps | Dal 2010-06 | Usage-based (decine–centinaia di $ per 5 anni di un symbol), licenza ML/interna ok |

**Futures 6E come proxy del volume spot** — Pro: unico volume vero e auditabile; correlazione altissima col flusso EURUSD spot; order flow features di qualità. Contro: orari e microstruttura diversi (rollover trimestrali, liquidità fuori RTH USA), ~10% del mercato EURUSD globale, allineamento timestamp da curare. Come **feature esogena affiancata** al feed spot: eccellente; come sostituto: no.

## 4. Quanto vale il tick volume come feature ML

Nel forex OTC il volume aggregato reale non esiste. Opzioni: (a) tick count, (b) liquidity size del singolo venue, (c) volume reale ma parziale di un exchange (CME 6E, LMAX).

La letteratura è favorevole: **Caspar Marney (2011), "Are price updates a good proxy for actual traded volume?"** trova correlazioni "strikingly high" tra tick activity e traded volume reale interbancario su EURUSD e altri major. Analisi successive (MT4 tick volume vs CME 6E) riportano **correlazioni ~0.85–0.90 su barre H1** per EURUSD; la correlazione degrada su coppie illiquide, timeframe piccoli, ore morte, e non è stabile nel tempo.

Implicazioni: tick volume = feature **informativa ma rumorosa e broker-dependent**. Usarla in forma relativa/normalizzata (z-score rispetto alla stessa ora del giorno, rolling percentile), mai in assoluto; trattare i volumi Dukascopy bid/ask come feature di *liquidità* (depth, imbalance) — informazione complementare al tick count. Attenzione al **domain shift** Dukascopy↔FxPro: serve normalizzazione robusta.

## 5. Raccomandazione operativa (adottata nel piano)

**Strategia a tre layer**:
1. **Base storica lunga — Dukascopy** (gratis): tick EURUSD con `bidVolume/askVolume`, download con `dukascopy-node` in batch mensili → barre 1s con OHLC bid/ask, tick count, liquidity volumes, spread medio, quote imbalance.
2. **Coerenza broker — FxPro MT5**: scaricare tutta la profondità disponibile con `copy_ticks_range` chunked (probe M0), poi downloader incrementale giornaliero. Serve per fine-tuning/validazione sulla distribuzione del broker di esecuzione e per misurare lo spread reale FxPro.
3. **Volume vero opzionale — CME 6E via Databento** (usage-based) come feature esogena; alternativa gratuita Darwinex FTP come secondo venue.

**Stima disco 5 anni tick EURUSD** (~100–200k tick/giorno, ~130–260M righe): CSV ~10–20 GB; `.bi5` ~3–5 GB; **Parquet zstd ~3–6 GB**; barre 1s < 1 GB. Full history 2003–oggi < ~20 GB Parquet.

**Formato**: Parquet partizionato `source/symbol/year/month` (`ts_ms:int64 UTC, bid:f64, ask:f64, bid_vol:f32, ask_vol:f32`), zstd, righe ordinate per timestamp; lettura polars/duckdb/pyarrow. Feed separati per `source`, join solo a feature-engineering time, mai fusione di tick di feed diversi.

Fonti principali: docs MQL5 `copy_ticks_range` · MQL5 book/forum (volume vuoto su forex; limiti tick >5 anni) · help cTrader Open API · dukascopy-node docs · Darwinex tick data · Sierra Chart LMAX · TrueFX downloads · Databento 6E catalog · studio Marney (varianse.com PDF).
