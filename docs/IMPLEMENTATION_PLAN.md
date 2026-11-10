# ForexTutor — Sistema di auto-apprendimento per trading forex basato su imitazione + deep learning

Piano di implementazione completo, calibrato per esecuzione da parte di Opus 4.8. Progetto greenfield in `E:\Projects\forexTutor` (directory vuota). Basato su due ricerche di stato dell'arte 2024-26 (metodi di imitation/reinforcement learning; fonti dati con volumi) e su design architetturale dettagliato.

## Context

L'utente vuole un sistema desktop Windows che impari a replicare — e poi raffinare — il suo stile di trading su EURUSD:

1. **Dati**: storici a risoluzione 1 secondo (da tick), con volumi.
2. **Annotazione umana**: su un grafico storico l'utente traccia col mouse le operazioni (segmento entrata→uscita con punto marcatore a ciascuna estremità; la **direzione è dedotta dal segmento**: sale → acquisto/long, scende → vendita/short; anche **sovrapposte**: più posizioni aperte contemporaneamente, chiuse indipendentemente), sceglie lo stile della sessione (scalping / day / swing / multi-day 1-5gg) e piazza un **marker "fine periodo"**: oltre quel punto il sistema non apprende da nuove aperture (censoring esplicito) ma impara comunque a NON tradare.
3. **Simulatore accelerato**: riproduce il flusso a 1s alla massima velocità, senza look-ahead; l'agente vede solo il passato e gestisce un portafoglio di posizioni multiple concorrenti.
4. **Feature engine**: per ogni secondo ~150 indicatori tecnici, candele su 15 timeframe (1m→5d), chart pattern, candlestick pattern, fase di mercato, feature di volume — tutto calcolato in modo INCREMENTALE.
5. **Apprendimento**: sistema di premi/punizioni multidimensionale e autocorreggente che avvicina le decisioni dell'agente a quelle dell'utente (fase imitazione) e poi le raffina con reward misto imitazione+P&L (scelta "ibrido a fasi" confermata dall'utente).
6. **Visualizzazione per turno di apprendimento**: dopo ogni round la UI mostra le operazioni che l'app avrebbe fatto (segmenti con punti alle estremità) sovrapposte a quelle dell'utente, con statistiche: P&L utente vs app, indice di corrispondenza, indice di progresso per round, win rate, drawdown, n. operazioni, tempo medio in posizione.

Decisioni confermate dall'utente: UI **desktop nativa PyQt6 + pyqtgraph**; dati **con volumi** (ha account FxPro); obiettivo **ibrido a fasi**; hardware **workstation locale PLUTO-MAX, RTX 5090, Windows 11**; **posizioni multiple sovrapposte**; visualizzazione per round come sopra.

## Risultati della ricerca (sintesi decisionale)

### Metodo di apprendimento (ricerca 1)
- **Metodo primario: Behavioral Cloning (BC) gerarchico pesato sugli eventi.** GAIL/AIRL scartati (instabili con poche demo; con 99.9% di "hold" il discriminatore impara scorciatoie). Decision Transformer scartato (non necessario con demo omogenee e poche). Riferimento diretto: "Human-aligned trading by imitative multi-loss RL" (Expert Systems with Applications 2023/2024).
- **Policy gerarchica a 2 livelli** contro la class imbalance estrema: (a) **gate "se agire ora"** = event detector supervised (focal loss γ=2, event-centric sampling ±N s attorno alle annotazioni + hold uniformi 4:1, metrica PR-AUC); (b) **testa "cosa fare"** (apri long/short, chiudi posizione i) attivata dal gate. Pattern EarnHFT / HARL-TRADE.
- **Fine-tuning RL nel simulatore** (che è replay senza rischio → RL "online" possibile): policy inizializzata da BC, replay buffer seedato ~50% con le demo (stile RLPD), critic **distributional QR**, regolarizzazione **KL verso la policy BC**, frame-skip adattivo.
- **Reward decomposta multidimensionale e autocorreggente**: (i) imitazione = **potential-based reward shaping** (teorema Ng-Harada-Russell: non corrompe la policy ottima) sulla similarità alle decisioni utente, coefficiente **decadente per round**; (ii) P&L netto costi; (iii) penalità rischio (drawdown incrementale + CVaR); (iv) penalità frequenza/churn. Componenti loggate SEPARATAMENTE → diagnosi e ribilanciamento; pesi esposti come manopole.
- **Pretraining self-supervised dell'encoder** (masked prediction) su tutto lo storico non annotato — sfrutta dati abbondanti dove le label sono poche.
- **Anti-hindsight-bias** (rischio n.1 del progetto): modalità annotazione "replay" opzionale (il grafico avanza, il futuro non è mai renderizzato); label con tolleranza temporale (smoothing gaussiano σ=10s), mai punti esatti.
- **Anti-look-ahead**: calcolo incrementale by-construction + test automatico di perturbazione del futuro.
- **Validazione**: walk-forward obbligatoria (rolling: train 18 mesi → val 3 mesi, stride 3).
- Evoluzioni future (non in scope iniziale): DAgger-style active queries e preference learning a coppie.

### Strategia dati (ricerca 2)
Fatto chiave: i tick MT5 forex NON hanno volume di size (campi `volume`/`volume_real` vuoti) — solo quote bid/ask con timestamp ms, da cui si deriva il tick count. Dukascopy invece fornisce `bidVolume/askVolume` = liquidità top-of-book del suo ECN. Il tick volume è informativo (correlazione ~0.85-0.90 con volume reale CME su H1 per EURUSD) ma broker-dependent → usare SOLO in forma normalizzata (z-score per ora del giorno, rolling percentile).

Strategia a tre layer:
1. **Base storica: Dukascopy** (gratis, tick EURUSD dal 2003, bid/ask + bidVolume/askVolume) via `dukascopy-node` (npm, batch mensili).
2. **Coerenza broker: FxPro MT5** (pacchetto Python `MetaTrader5`, solo Windows — ok): `copy_ticks_range` chunked per giorno; profondità storica IGNOTA a priori → **primo esperimento del progetto = script di probe** che va a ritroso finché il server risponde.
3. **Opzionale (non in scope iniziale): CME 6E via Databento** come volume reale esogeno; alternativa gratuita Darwinex FTP.

Storage: **Parquet zstd partizionato `source/symbol/year/month`**; feed diversi MAI fusi (join solo a feature-engineering time). Stima 5 anni tick: ~3-6 GB Parquet — banale.

## Valutazione del progetto (parere espresso all'utente)

Solido e realizzabile con le scelte giuste. Rischi principali e come il design li affronta: hindsight bias delle annotazioni (replay mode + label smoothing + probe di causal feasibility in futuro); class imbalance 99.9% hold (policy gerarchica + event-centric sampling); costo computazionale 150 indicatori × 15 TF a 1s (precompute a tier, il training non usa mai il loop incrementale); poche annotazioni (modello piccolo ~0.5M parametri + SSL pretraining + regolarizzazione); non-stazionarietà (walk-forward + feature di regime); sim-to-real gap (bid/ask reali, latenza 100-500ms, slippage stocastico).

---

# DESIGN DI DETTAGLIO

Vincoli: Python 3.12 (venv dedicato — il default di sistema è 3.10), PyTorch ≥2.7 **cu128** (RTX 5090 = sm_120: MAI wheel di default PyPI), polars/duckdb/pyarrow, PyQt6+pyqtgraph, talipp+TA-Lib (wheel binaria win_amd64), Gymnasium, scipy, pydantic. Un solo repo, tutto locale.

## 1. Struttura repo

```
E:\Projects\forexTutor\
├─ pyproject.toml                  # "forex-tutor", py3.12, deps pinnate; [project.scripts]
├─ README.md                       # setup: uv venv -p 3.12, Node.js per dukascopy-node, TA-Lib wheel
├─ .gitignore                      # data/, runs/, *.npy, .venv/
├─ configs\
│  ├─ default.yaml                 # path dati, symbol=EURUSD, seed
│  ├─ features.yaml                # TF, indicatori per gruppo, parametri → spec_hash versionante
│  ├─ sim.yaml                     # K=4 slot, latenza U(100,500)ms, slippage, costi, stili
│  ├─ model.yaml                   # dimensioni encoder/heads, dropout 0.1, weight decay
│  └─ training\ssl.yaml, bc.yaml, rl.yaml, walkforward.yaml
├─ src\forex_tutor\
│  ├─ config.py                    # pydantic dataclass; load_config→AppConfig; freeze nel run dir
│  ├─ constants.py                 # TF_LIST (15), PIP=1e-4, colonne schema, K default
│  ├─ paths.py
│  ├─ data\                        # dukascopy.py (subprocess npx), fxpro_mt5.py (chunked+retry),
│  │                               # databento_cme.py (opz.), tick_store.py (validazioni),
│  │                               # bars.py (polars group_by_dynamic "1s"), calendar.py (sessioni/weekend)
│  ├─ features\                    # spec.py, tf_aggregator.py, indicators.py (talipp + warmup TA-Lib),
│  │                               # patterns_cdl.py, patterns_chart.py (ZigZag/S-R/trendline/triangoli),
│  │                               # regime.py, volume.py, engine.py, store.py, precompute.py
│  ├─ sim\                         # portfolio.py, execution.py, reward.py, env.py, vec_env.py
│  ├─ models\                      # encoder.py, heads.py, policy.py, ssl_heads.py
│  ├─ training\                    # datasets.py, replay_buffer.py, ssl_train.py, bc_train.py,
│  │                               # rl_train.py, walk_forward.py, checkpoints.py, run.py (CLI unificata)
│  ├─ eval\                        # rollout.py, matching.py (Hungarian), metrics.py
│  ├─ annotations\                 # models.py, db.py (SQLite DAO, migrazioni, versioning)
│  ├─ ui\                          # app.py, main_window.py (tab Annotate/Train/Review),
│  │                               # chart\candlestick_item.py, chart_widget.py, trade_overlay.py,
│  │                               # annotate_tab.py, train_tab.py, review_tab.py
│  └─ scripts\                     # probe_fxpro_depth.py, download_dukascopy.py, build_bars.py,
│                                  # build_features.py, run_sim_sanity.py, export_round_report.py
├─ tests\                          # test_bars, test_feature_lookahead, test_engine_resume,
│                                  # test_portfolio, test_env_api, test_matching, test_annotations_db
├─ data\   (gitignored)            # ticks\source=…\symbol=…\year=…\month=…\, bars1s\…,
│                                  # features\<spec_hash>\tierA|tierB\, annotations\annotations.db
└─ runs\   (gitignored)
```

## 2. Schemi dati

Convenzioni: timestamp UTC; prezzi f64 (f32 insufficiente per cumulate a 5 decimali); feature f16/f32; pip=1e-4.

**Parquet tick** (zstd level 3, row group ~1M, metadata file-level `source/symbol/ingest_version/...`):
`ts_ms:int64, bid:f64, ask:f64, bid_vol:f32, ask_vol:f32` (FxPro: vol=NaN). Validazioni a write: `ask>=bid`, spread <50 pip (outlier drop+log), ts monotono.

**Parquet barre 1s** (una riga per secondo di mercato con ≥1 tick; secondi vuoti forward-fillati a read-time):
`ts_s:int64, o/h/l/c_bid:f64, o/h/l/c_ask:f64, tick_count:u32, bid_vol_sum:f32, ask_vol_sum:f32, spread_mean:f32(pip), imbalance:f32`.

**Feature precomputate — storage a 3 tier** (evita i ~112 GB del precompute denso; l'osservazione è per costruzione "per-TF alle chiusure candela" + piccolo blocco 1s):
- **Tier A** (memmap numpy f16 + ts int64, un file/anno): ~32 feature native a 1s (spread, tick_count z-score orario, imbalance, vol z-score, distanze S/R, posizione nel range sessione, sin/cos ora/giorno, flag sessione). 5 anni ≈ **7 GB**. Accesso O(1) via `np.searchsorted`.
- **Tier B** (Parquet per TF): per ogni candela CHIUSA: OHLC normalizzati + ~150 indicatori + pattern id + regime. Tutti i 15 TF < **1 GB**. A batch-time: `searchsorted(close_ts_tf, t)-1` → ultime 64 righe. **Anti-look-ahead strutturale: si indicizzano solo candele con close_ts ≤ t.**
- **Tier C** (candela in formazione): NON storata; ricostruita on-the-fly (cummax/cummin vettoriali) o mantenuta incrementalmente da `MultiTFAggregator` nel percorso sim/replay.

Sidecar `meta.json` per tier: `{spec_hash, columns, t_start_ms, t_end_ms, n_rows, dtype}`. Cambia `features.yaml` → cambia `spec_hash` → directory nuova, mai overwrite.

**SQLite annotazioni** (`annotations.db`, WAL): tabelle `schema_info(version)`; `sessions(id, created_utc, symbol, source, style CHECK IN scalping/day/swing/multiday, t_start_ms, t_end_ms, end_marker_ms NULL, replay_mode, revision, notes)`; `trades(id, session_id FK, direction CHECK long/short, t_entry_ms, t_exit_ms CHECK >entry, price_entry, price_exit, size, created_utc, deleted soft)` — `direction` è DERIVATA al salvataggio dal segmento disegnato (`long` se price_exit > price_entry, `short` se <; uguali → rifiutato), mai scelta con uno strumento; `trade_history(hist_id, trade_id, snapshot_json, edited_utc, session_revision)` — versioning append-only: ogni edit incrementa `revision` e snapshotta il vecchio record. Sovrapposizioni ammesse; warning se >K concorrenti.

**Run di training** (`runs\<YYYYMMDD_HHMMSS_<phase>>\`): `config_frozen.yaml`; `metrics.jsonl` (una riga JSON per log-step con loss e **componenti reward separate** `r_imitation/r_pnl/r_risk/r_activity` + `kl_bc`); `checkpoints\ckpt_step<N>.pt` e `latest.pt` (scrittura atomica tmp+`os.replace`; contenuto: model/optim state, step, phase, feature_spec_hash, config, stati RNG, `bc_reference_state` in fase C); `eval\round_<n>\app_trades.json` + `metrics.json`; `eval\progress.json` (serie indice di corrispondenza per round); file sentinella `STOP` (creato dalla UI → il trainer salva e termina).

## 3. Interfacce chiave

```python
# features/engine.py
class FeatureEngine:
    def __init__(self, spec: FeatureSpec): ...
    def warm_up(self, bars_1s: pl.DataFrame) -> None: ...   # vettoriale TA-Lib fino a t0
    def update(self, bar: Bar1s) -> FeatureFrame: ...       # 1 chiamata/secondo, solo passato
    def get_state(self) -> bytes: ...                       # snapshot per resume
    @classmethod
    def from_state(cls, spec, blob) -> "FeatureEngine": ...

@dataclass
class FeatureFrame:
    ts_s: int
    fast: np.ndarray          # (32,) f32
    tf_candles: np.ndarray    # (15, 64, 9) f32 — ultime 64 candele CHIUSE per TF
    tf_indicators: np.ndarray # (15, 150) f32 — snapshot all'ultimo close (NaN→0 + mask)
    tf_forming: np.ndarray    # (15, 6) f32 — OHLC parziale + % completamento
    patterns: np.ndarray      # (15, 8) int32 — id CDL/chart attivi, padded 0
    regime: np.ndarray        # (16,) f32
```

**Env Gymnasium — azione multi-posizione a K slot** (K=4 default). Una posizione occupa il primo slot libero e lo mantiene fino a chiusura (identità stabile per la testa di chiusura per-slot):

```python
action_space = spaces.Dict({
    "open":  spaces.Discrete(3),      # 0=hold, 1=long, 2=short
    "close": spaces.MultiBinary(K),   # bit i → chiudi slot i (no-op se vuoto)
})
# step: prima i close (latenza+slippage), poi l'open se slot libero e consentito.
# Masking: open vietato se slot pieni, dopo end_marker, o fuori dalle regole di stile.
observation_space = spaces.Dict({
    "candles": (15,64,9) f32, "indicators": (15,150) f32, "ind_mask": (15,150),
    "fast": (32,), "forming": (15,6), "patterns": (15,8) i32, "regime": (16,),
    "portfolio": (K,8) f32,  # per slot: is_open, dir, upl_pips_norm, time_in_pos_norm,
                             # dist_entry_pips, mae_pips, mfe_pips, size
    "action_mask": {"open_allowed": MultiBinary(3), "close_valid": MultiBinary(K)},
})
```
Fine episodio: `truncated` a fine finestra, posizioni residue chiuse forzate con flag+penalità. Dopo `end_marker`: open mascherato, l'episodio continua (impara il "non tradare"). `info` contiene `reward_components`, `fills`, `equity`. `BatchedTradingEnv(n_envs)` vettorizzato in-process numpy con `step_batch`.

**Reward decomposta** (`sim/reward.py`):
```python
@dataclass
class RewardComponents:
    imitation: float  # potential-based: γ·Φ(s')−Φ(s); Φ = affinità alle demo (kernel gaussiano ±N s
                      # attorno a entry/exit annotati, indicizzate per-secondo in DemoIndex)
    pnl: float        # Δequity netto costi, pip normalizzati, clip
    risk: float       # −drawdown incrementale − λ·CVaR_α(rolling returns)
    activity: float   # −c_open·1[open] − c_churn·1[riapertura < min_gap]
class RewardComposer:
    def set_imitation_coef(self, round_idx): ...  # w0 * 0.7**round
    def on_step(self, t_s, action, fills, portfolio) -> RewardComponents: ...
```

**Matching Hungarian** (`eval/matching.py`) per l'indice di corrispondenza:
```python
def match_trades(user, app, *, tau_entry_s=900, tau_exit_s=1800,
                 w_entry=.35, w_exit=.25, w_iou=.40, max_cost=.75) -> MatchResult:
    # cost[i,j] = w_entry·min(|Δt_entry|/τ,1) + w_exit·min(|Δt_exit|/τ,1) + w_iou·(1−IoU)
    # direzione diversa → +inf; scipy linear_sum_assignment; cost>max_cost → unmatched
    # correspondence_index = Σ(1−cost) / max(N_user, N_app)
```
IoU e Δt calcolati in **secondi di mercato** (calendar.py), non wall-clock (corretto per multi-day). Indice di progresso = serie del correspondence_index per round da `progress.json`.

## 4. Modello e training

**Modello (~0.5M parametri)**: TCN condiviso tra TF (9→32→48→64, kernel 3, dilation 1/2/4, GroupNorm) sulle 64 candele → token/TF + TF-embedding (15×64); indicatori in 5 gruppi semantici → MLP(→96→64) → 5 token; pattern → embedding table (~62 CDL + ~12 chart)×16 sum-pool sommati al token TF; portafoglio → linear(8→64)+slot-embedding → K token ("empty" appreso, mascherato); **VSN stile TFT** sui 20+K token (pesi softmax loggati → ispezionabilità "il modello guarda RSI-H4"); TransformerEncoder 2 layer/4 head/d64 + CLS. Heads: Gate MLP(64→64→1); Open MLP(64→3); Close per-slot MLP(concat[CLS, token_slot]→64→1); Critic QR 32 quantili; SSL head.

**Fase A — SSL**: `WindowDataset` su finestre 4h uniformi da storico non annotato; masked prediction (15% token TF mascherati → predici ret/range/body normalizzati); AdamW, cosine, bf16 autocast; DataLoader workers=4, memmap riaperti in `worker_init_fn`.

**Fase B — BC gerarchico**: `EventCentricDataset` (t campionati ±30s attorno a ogni entry/exit con peso gaussiano σ=10s + hold uniformi 4:1; dopo end_marker solo esempi "non aprire"). Loss = focal(gate, γ=2) + CE(open) pesata + BCE(close_slot) solo su slot aperti nello stato ricostruito dalle annotazioni. Metriche: PR-AUC gate, accuracy open, F1 close. Early stop su split temporale.

**Fase C — RL**: feature precomputate → dinamica env = pura indicizzazione numpy → `BatchedTradingEnv` in-process, N_env=64, batch inference GPU (NIENTE multiprocessing per il RL). SAC discreto fattorizzato (softmax open ⊗ Bernoulli close/slot), critic QR, target entropia per testa, actor loss += β·KL(π‖π_BC frozen), replay 50/50 demo/online (RLPD), UTD=4. Frame-skip adattivo: gate<0.1 → skip 15s con hold (mark-to-market interno resta a 1s per drawdown/CVaR), soglia annealing→0. Walk-forward: fold rolling 18m→3m stride 3m, report per fold, asserzione anti-leakage train_end < val_start.

**Processi (Windows spawn)**: entrypoint sempre sotto `__main__`; ai worker solo path+config picklabili (mai memmap/MT5/talipp). Multiprocessing SOLO in precompute feature (ProcessPoolExecutor per mese) e DataLoader. UI↔training: `QProcess` che lancia `python -m forex_tutor.training.run --phase {ssl,bc,rl,round}`; comunicazione file-based (`metrics.jsonl` letto incrementalmente + sentinella `STOP`). Nessuna queue cross-process.

## 5. UI (PyQt6 + pyqtgraph)

- **MainWindow**: tab Annotate / Train / Review, selettore sessione, status bar.
- **ChartWidget**: candele con item custom `QPicture`-cached, selettore TF, zoom/pan, lazy load barre visibili via duckdb (mai tutto in RAM), crosshair, downsampling se >5000 candele visibili.
- **TradeOverlayItem**: segmenti entry→exit con `ScatterPlotItem` alle estremità; verde/rosso long/short utente; **ciano/arancio per l'app**; tooltip P&L su hover.
- **AnnotateTab**: toolbar Pan / Draw Trade / Erase / Set End-Marker; drag = trade (snap tempo a candela, prezzo mid). **La direzione è dedotta dal segmento disegnato**: prezzo uscita > prezzo entrata → long (acquisto); prezzo uscita < prezzo entrata → short (vendita); segmento piatto (stesso prezzo) → rifiutato con messaggio. Nessuno strumento separato long/short. Stile sessione; autosave SQLite; linea verticale end-marker. **Replay mode**: il chart clampa xmax al cursore, QTimer 1x-300x, pausa/step — il futuro non è mai renderizzato.
- **TrainTab**: form fase/sessione/override, Start (QProcess) / Stop (scrive `STOP`); curve loss + 4 componenti reward separate (QTimer 1s legge `metrics.jsonl` incrementale con seek); console stdout.
- **ReviewTab**: dropdown run/round; **overlay trade app vs utente**; tabella statistiche (P&L utente/app, correspondence index, win rate, max DD, n. op, tempo medio in posizione); **grafico indice di progresso per round**; bar chart pesi VSN.
- Threading: widget solo dal main thread; query chart in QThread con segnali; training sempre in QProcess (niente multiprocessing nel processo UI: spawn re-importa il main → rischio doppia QApplication).

## 6. Milestone M0→M8 (incrementali, ciascuna con verifica eseguibile)

**M0 — Bootstrap + probe profondità FxPro** (PRIMO esperimento)
Scope: pyproject (deps pinnate, torch cu128), venv 3.12 (`uv venv -p 3.12`), config/paths/constants, `scripts/probe_fxpro_depth.py` (MT5 init → `copy_ticks_range` a ritroso per giorno finché vuoto; report: primo giorno disponibile, tick/giorno, campi presenti, granularità ms → `data\fxpro_probe_report.json`).
Verifica: `python -c "import torch; print(torch.cuda.get_device_name(0))"` → RTX 5090; probe stampa report. L'esito determina quanto storico FxPro usare (il design NON dipende dall'esito: Dukascopy resta la base).

**M1 — Pipeline dati**
Scope: `data/` completo, script download/build_bars, test_bars. Node.js richiesto per dukascopy-node (README).
Verifica: download 2024-01→03 + build bars → ~5.8M barre attese, 0 spread negativi, gap coerenti col calendario; `pytest tests/test_bars.py` verde.

**M2 — FeatureEngine + anti-look-ahead**
Scope: `features/` completo, build_features, test_feature_lookahead (perturba il futuro → feature a ≤t identiche bit-exact), test_engine_resume (get_state/from_state → traiettoria identica).
Verifica: pytest verdi; build 3 mesi Tier A+B con meta.json in < 30 min.

**M3 — UI annotazione**
Scope: `annotations/`, `ui/` (app, chart, annotate_tab con replay mode), test_annotations_db.
Verifica: aprire 2024-02, disegnare 3 trade (2 sovrapposti; uno con segmento ascendente e uno discendente → direction salvate rispettivamente long e short senza selezione manuale), end-marker, stile "day"; riaprire l'app → annotazioni identiche; in replay mode il chart non mostra mai candele oltre il cursore.

**M4 — Simulatore**
Scope: `sim/` completo, run_sim_sanity, test_env_api (gymnasium env_checker), test_portfolio (identità equity = cash + Σ unrealized).
Verifica: pytest verdi; `run_sim_sanity --n-envs 64 --steps 1000000` < 60s, equity ≈ −costi per policy random, 0 violazioni invarianti (posizioni>K, open dopo marker, exit<entry).

**M5 — Fase A (SSL)**
Scope: encoder, ssl_heads, datasets, ssl_train, checkpoints, run.py.
Verifica: run SSL 2023-01→2024-06 → loss −20% in 30 min GPU; linear probe AUC segno ret 1min ≥ baseline+0.02; checkpoint ricaricabile.

**M6 — Fase B (BC) + round review**
Scope: heads, policy, bc_train, eval/ completo, export_round_report, review_tab, test_matching (casi sintetici con matching ottimo noto).
Verifica: pytest matching verde; BC su sessione annotata → PR-AUC gate > 3× prevalenza; export round_1; ReviewTab mostra overlay + statistiche + correspondence_index ∈ (0,1].

**M7 — Fase C (RL) + walk-forward**
Scope: replay_buffer, rl_train, walk_forward, critic QR.
Verifica: run RL da checkpoint BC → metrics.jsonl con 4 componenti reward + kl_bc; su validazione P&L RL ≥ BC (stampato a confronto); walk-forward produce report per fold con asserzione anti-leakage.

**M8 — Loop integrato per-round + indice di progresso**
Scope: train_tab, orchestrazione `--phase round` (BC/RL incrementale + rollout + matching + append progress.json), decay imitazione per round, vista VSN.
Verifica end-to-end dalla UI: annotare sessione → "Train round" ×3 → ReviewTab si aggiorna a ogni round con overlay e statistiche; grafico progresso con 3 punti; Stop → terminazione pulita con checkpoint, nessun processo orfano.

## 7. Rischi e mitigazioni

1. **Python lento a 1s**: il training non usa MAI il loop incrementale (gather vettoriali su Tier A/B); loop incrementale solo per replay/precompute (parallelo per mese); hot-path eventuali → Numba su array, misurati prima con cProfile.
2. **RTX 5090**: sm_120 → PyTorch ≥2.7 cu128 pinnato con index-url dedicato; smoke test in M0.
3. **TA-Lib su Windows**: wheel binaria win_amd64 (PyPI ≥0.5); nessuna compilazione.
4. **MT5**: richiede terminale FxPro installato e loggato; chiamate confinate in `fxpro_mt5.py`; probe M0 dà errori chiari.
5. **Memoria**: mai Parquet interi in RAM; chart via duckdb range-query; training via memmap+searchsorted; replay buffer con obs f16.
6. **PyQt threading / spawn**: regole in §4-§5; test resume copre il round-trip di stato.
7. **Look-ahead subdolo** (z-score, S/R, normalizzazioni): tutte le statistiche rolling/causali per contratto di FeatureEngine; test di perturbazione in CI, da rieseguire a ogni modifica di `features/`.
8. **Overfitting su poche annotazioni**: modello 0.5M, label smoothing, walk-forward, early stop, decay imitazione, dropout 0.1 + weight decay.
9. **Gap weekend/festività**: `calendar.py` unica fonte di verità; IoU/Δt del matching in secondi di mercato.
10. **Domain shift volumi** (Dukascopy vs FxPro): solo feature normalizzate (z-score orario, percentile), mai assolute.

## Verifica complessiva end-to-end

Percorso finale (= verifica M8): dall'app desktop, annotare una sessione su dati reali scaricati (M1), lanciare 3 round di training e osservare: (a) overlay delle operazioni dell'app sovrapposte alle proprie, (b) statistiche comparative P&L/win rate/drawdown, (c) indice di corrispondenza che cresce attraverso i round nel grafico di progresso, (d) pesi VSN ispezionabili. Test automatici: `pytest tests\` tutto verde, incluso il test anti-look-ahead.
