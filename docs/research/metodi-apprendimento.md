# Ricerca: stato dell'arte 2024–2026 — Imitazione delle decisioni di trading umane su forex (EURUSD, 1s)

Report prodotto durante la fase di progettazione (2026-07-25). Le decisioni derivate da questo report sono consolidate in `docs/IMPLEMENTATION_PLAN.md` — in caso di conflitto vale il piano.

---

## 1. Imitation Learning

### Approcci principali

**Behavioral Cloning (BC)** — supervised learning stato→azione sulle dimostrazioni. Semplice, stabile, funziona anche con pochissimi dati. Limite noto: **covariate shift** — l'errore si accumula quando la policy visita stati mai visti nelle dimostrazioni ([Interactive and Hybrid Imitation Learning, arXiv 2024-25](https://arxiv.org/html/2412.07057v3)). Nel trading il problema è attenuato rispetto alla robotica: lo stato di mercato NON dipende dalle azioni dell'agente (l'agente non muove il prezzo EURUSD in simulazione). Il covariate shift esiste solo sulla componente di stato controllata dall'agente (posizione aperta, P&L non realizzato, tempo in posizione): l'utente dimostra uscite solo da posizioni "sue", ma l'agente si troverà in posizioni aperte in momenti sbagliati che l'utente non ha mai gestito. Questo è il punto debole preciso di BC nel nostro caso.

**DAgger** — interroga l'esperto sugli stati visitati dalla policy, risolvendo il covariate shift. Teoricamente ideale perché **l'esperto esiste ed è disponibile**: dopo un rollout, il sistema può mostrare all'utente i punti dove ha aperto/chiuso e chiedere "qui cosa avresti fatto?". In pratica il costo di labeling umano è il collo di bottiglia; le varianti moderne (HG-DAgger, active-DAgger che chiede label solo dove la policy è incerta) riducono le query del 90%+. Fortemente raccomandato come loop di correzione, non come metodo primario.

**GAIL** — un discriminatore distingue traiettorie esperte da traiettorie della policy; la policy è addestrata con RL contro il discriminatore. Pro: gestisce il long-horizon matching. Contro: **instabile con poche dimostrazioni** (il discriminatore overfitta), sample-inefficient, e con azioni sparse al 99.9% "hold" il discriminatore impara scorciatoie banali ("l'esperto quasi non agisce mai"). Sconsigliato come metodo principale.

**AIRL** — variante di GAIL che recupera una reward function disentangled e trasferibile. Interessante perché la reward appresa potrebbe trasferirsi tra regimi di mercato, ma eredita l'instabilità adversarial e in finanza i risultati riportati sono misti ([survey RL in quantitative finance, arXiv 2408.10932](https://arxiv.org/pdf/2408.10932)).

**IQ-Learn** ([Garg et al.](https://www.emergentmind.com/papers/2106.12142)) — impara direttamente la Q-function che spiega le dimostrazioni, senza discriminatore né reward esplicita. Nei benchmark è **il metodo che degrada meno con dimostrazioni scarse** (funziona con 1–10 traiettorie), superando BC, GAIL e ValueDICE. Candidato "IRL-style" più adatto al regime low-data. Contro: sensibile agli iperparametri.

**SQIL** ([arXiv 1905.11108](https://arxiv.org/abs/1905.11108)) — reward=1 sulle transizioni dimostrate, reward=0 su quelle della policy, poi soft Q-learning. Robusto, quasi zero iperparametri, buon baseline dopo BC. Attenzione: con azioni sparse premia anche l'imitazione dell'"hold", serve riponderare gli eventi.

**Lavori specifici trading**: [Human-aligned trading by imitative multi-loss RL (Expert Systems with Applications, 2023)](https://www.sciencedirect.com/science/article/pii/S0957417423014410) e il follow-up [Improving algorithmic trading consistency via human alignment and imitation learning (2024)](https://www.sciencedirect.com/science/article/abs/pii/S0957417424012168) — combinano loss supervisionata di imitazione + Q-learning + termini di allineamento umano in un'unica multi-loss: è letteralmente il nostro problema, **riferimento primario**. Anche [Transaction-aware IRL for stock trading (Applied Intelligence)](https://link.springer.com/article/10.1007/s10489-023-04959-w) e il [capitolo CFA 2025 su RL/IRL per investment management](https://rpc.cfainstitute.org/research/foundation/2025/chapter-6-reinforcement-learning-inverse-reinforcement-learning).

### Verdetto per poche dimostrazioni sparse
Ordine di preferenza: **BC (con pesatura degli eventi) → + reward shaping dalle demo → IQ-Learn/SQIL come alternativa → DAgger-style active queries come loop di raffinamento**. GAIL/AIRL sconsigliati con poche demo. Nota chiave: le "poche dimostrazioni" annotate su anni di storico sono in realtà **molti eventi di decisione** (ogni entrata/uscita è un esempio) — il problema non è la quantità di segnale ma la sparsità temporale (§5).

---

## 2. Offline RL / Batch RL

- **CQL**: penalizza Q su azioni out-of-distribution. Con un dataset composto SOLO da traiettorie esperte tende a comportarsi come un BC regolarizzato costoso.
- **IQL**: evita di valutare azioni OOD tramite expectile regression; robusto, poche parti mobili, default de-facto 2024-25. Buon candidato per la fase offline dopo BC.
- **TD3+BC**: minimale ed efficace, ma pensato per azioni continue; il nostro spazio azioni è discreto → meglio IQL/CQL discreti.
- **Decision Transformer / Trajectory Transformer**: sequence modeling condizionato sul return-to-go. Riferimento trading: [GPT-2 + LoRA come Decision Transformer per offline RL, arXiv 2411.17900](https://arxiv.org/abs/2411.17900). Ma la letteratura critica ([arXiv 2305.14550](https://arxiv.org/html/2305.14550), [arXiv 2507.10174](https://arxiv.org/pdf/2507.10174)) mostra che DT è preferibile con dati subottimali eterogenei e reward sparse, **non fa trajectory stitching** e con pochi dati IQL o il semplice BC spesso vincono. Con dimostrazioni umane omogenee e poche, DT è un lusso non necessario.

**Punto chiave**: poiché abbiamo un **simulatore fedele e senza rischio** (replay storico), non siamo vincolati al setting offline: possiamo fare RL "online nel simulatore". L'approccio moderno di riferimento è **RLPD / RL con prior data** — RL online (SAC-style) con replay buffer seedato al ~50% con le dimostrazioni umane — che nel 2023-25 ha soppiantato gran parte del learning-from-demonstrations classico ([overview reward engineering arXiv 2408.10215](https://arxiv.org/html/2408.10215v1)).

---

## 3. Preference-based / Reward Learning; reward multidimensionali autocorreggenti

- **Reward shaping da dimostrazioni**: le demo codificate come **potential-based shaping function** — potenziale = similarità tra stato-azione corrente e le decisioni annotate ([RLfD through Shaping, IJCAI 2015](https://www.ijcai.org/Proceedings/15/Papers/472.pdf); [PBRS overview](https://www.emergentmind.com/topics/potential-based-reward-shaping)). Il teorema di Ng-Harada-Russell (1999) garantisce **policy invariance**: se lo shaping è F(s,s') = γΦ(s') − Φ(s), la policy ottima rispetto alla reward "vera" (P&L) non cambia. È esattamente il meccanismo per il "premio per vicinanza alle decisioni utente" senza corrompere l'obiettivo economico. Caveat: la reward di distanza dipende dall'azione → formalmente serve un potenziale su (s,a) (advantage-based shaping) o accettare una policy bias controllata con coefficiente che decade — standard ingegneristico 2024-25.
- **Preference learning / RLHF-style**: l'utente confronta coppie di traiettorie e si fitta una reward model alla Bradley-Terry ([FinRL Contests survey, arXiv 2504.02281](https://arxiv.org/html/2504.02281v3)). Promettente come **fase 2 di raffinamento**: i confronti sono cognitivamente più economici delle annotazioni puntuali. Attenzione al reward hacking ([arXiv 2502.18770](https://arxiv.org/abs/2502.18770): reward bounded, crescita rapida poi saturazione).
- **Multi-objective RL / reward decomposition**: reward vettoriale (distanza-da-utente, P&L, drawdown, frequenza operazioni, tempo in posizione) con scalarizzazione adattiva o critic separati per componente ([Risk-Adjusted DRL multi-reward](https://ouci.dntb.gov.ua/en/works/lmbbvRvm/); [composite risk-aware reward, arXiv 2506.04358](https://arxiv.org/html/2506.04358v1)). La decomposizione rende il sistema "autocorreggente": si diagnostica quale termine domina e si ribilancia; i pesi diventano manopole di stile.
- **Distributional RL**: C51/QR-DQN/IQN apprendono la distribuzione dei ritorni ([distributional RL risk-averse per futures, arXiv 2501.04421](https://arxiv.org/abs/2501.04421): C51 +32% sui baseline, CVaR per avversione al rischio regolabile). Un critic distributional (QR) è un upgrade quasi gratuito che stabilizza il training su reward rumorose e permette risk-sensitivity per stile. Vedi anche [arXiv 2110.13578](https://arxiv.org/pdf/2110.13578).

---

## 4. Architetture encoder per stato multi-scala (~150 indicatori + pattern)

Consenso 2024-26 ([benchmark risk-adjusted, arXiv 2603.01820](https://arxiv.org/html/2603.01820v1)):

- **PatchTST** resta il transformer di riferimento per serie lunghe, ma è pensato per forecasting su raw series, non per stati RL già feature-izzati.
- **Mamba/SSM e ibridi Mamba-Transformer**: trend 2025 — [SST (CIKM'25)](https://github.com/XiongxiaoXu/SST), [T-Mamba](https://dl.acm.org/doi/10.1145/3746709.3746715), [MoU](https://arxiv.org/html/2408.15997v1).
- **Realismo**: il nostro stato NON è una sequenza grezza a 1s da 5 giorni (432k step — ingestibile). È un **vettore di feature già multi-risoluzione**. L'encoder giusto:
  - un branch per timeframe (TCN o piccolo transformer sulle ultime 32-64 candele) → un token per TF;
  - cross-timeframe attention sui token (architettura minuscola e interpretabile);
  - indicatori raggruppati semanticamente (trend, momentum, volatilità, volume, S/R) → MLP per gruppo → token → attention, con **Variable Selection Network del Temporal Fusion Transformer** ([tutorial](https://towardsdatascience.com/temporal-fusion-transformer-time-series-forecasting-with-deep-learning-complete-tutorial-d32c1e51cd91/); [applicazione trading, MDPI 2025](https://www.mdpi.com/2079-8954/13/6/474)): pesi di importanza appresi e ispezionabili;
  - pattern discreti come embedding categoriali;
  - con **poche demo l'encoder grande overfitta**: TCN/GRU per branch (10⁵–10⁶ parametri totali) + **pretraining self-supervised** su tutto lo storico non annotato (masked prediction / contrastive) — modo standard 2025 di sfruttare dati abbondanti con label scarse. LSTM semplici restano baseline competitive ([StockBot 2.0](https://arxiv.org/pdf/2601.00197)).

---

## 5. Class imbalance estrema (99.9%+ hold)

1. **Event-centric sampling** (la più importante): minibatch campionati attorno agli eventi annotati (±N s con curriculum di negativi) + campione uniforme di hold per calibrazione. Il dataset di training diventa "decision points", non "timesteps". Risolve il 90% del problema.
2. **Focal loss** + class weighting sulla testa azione; ricalibrare le probabilità dopo il training.
3. **Hierarchical policy / gating**: (a) modello "se agire ora" (event detector, alta recall), (b) modello "cosa fare" attivato solo quando (a) scatta. Struttura dei sistemi HFT gerarchici: [EarnHFT (AAAI 2024)](https://www.researchgate.net/publication/379291676_EarnHFT_Efficient_Hierarchical_Reinforcement_Learning_for_High_Frequency_Trading), [HARL-TRADE (2025)](https://pubs.aip.org/aip/cha/article/36/2/023132/3380328/), [HRT (arXiv 2410.14927)](https://arxiv.org/html/2410.14927v1). Il detector è un problema supervised puro valutabile con PR-AUC.
4. Alternativa: "tempo al prossimo evento" / temporal point process — elegante ma meno maturo; la gerarchia (3) è più pratica.
5. Per l'RL: **frame-skip adattivo / opzioni temporalmente estese** (hold persiste k step lontano da eventi) riduce l'orizzonte e il credit assignment.

---

## 6. Framework e strumenti

| Strumento | Verdetto |
|---|---|
| FinRL ([FinRL-X, arXiv 2603.21330](https://arxiv.org/pdf/2603.21330)) | Daily/minute-oriented, research-grade. Ispirazione, non base. |
| [gym-anytrading](https://github.com/AminHP/gym-anytrading) | Troppo semplicistico. Solo didattico. |
| [gym-trading-env](https://gym-trading-env.readthedocs.io/) | Pulito; ispirazione per l'API Gymnasium del nostro env. |
| [TensorTrade](https://github.com/tensortrade-org/tensortrade) | Architettura componibile elegante da imitare; progetto poco manutenuto. |
| [hftbacktest](https://github.com/nkaz001/hftbacktest) | Riferimento per realismo di esecuzione (latenze, queue). Ispirazione per il fill simulator. |
| [NautilusTrader](https://nautilustrader.io) | Candidato serio come base se si andrà verso il live; curva di apprendimento alta. |
| vectorbt | Vettoriale, inadatto a simulazione event-driven stateful con agente RL. |

**Indicatori incrementali**: [talipp](https://github.com/nardew/talipp) — calcolo incrementale O(1) per update, supporta update/remove dell'ultimo valore (candele in formazione). Pattern d'uso: **warm-up vettoriale TA-Lib + regime incrementale talipp**. Se il profiling lo richiede: port Numba/Rust dei 20-30 indicatori hot (EMA, Wilder, rolling min/max con deque monotona sono <30 righe in forma ricorsiva).

**Conclusione**: nessun framework fa già "simulatore 1s + indicatori incrementali + imitazione umana" → simulatore proprietario leggero con API Gymnasium.

---

## 7. Fonti dati storici forex 1s/tick

- **Dukascopy** — standard de-facto gratuito: tick bid/ask con volumi dal loro ECN, EURUSD dal ~2003, file `.bi5` (LZMA). Strumenti: [dukascopy-node](https://github.com/Leo4815162342/dukascopy-node) (il più mantenuto), [duka](https://giuse88.github.io/duka/), Tickstory. Licenza: uso personale/ricerca tollerato; non ridistribuire.
- **TrueFX** — tick bid/ask da banche tier-1, CSV mensili gratuiti, dal 2009. Ottimo per cross-validazione dello spread.
- **HistData** — gratuito ma qualità inferiore, senza volumi.
- Nota: il forex è OTC — non esiste "il" prezzo a 1s; ogni fonte è il feed di un aggregatore.

---

## 8. Insidie note

1. **Hindsight bias nelle annotazioni** — rischio n.1: l'utente che annota sul grafico storico vede il futuro e marca minimi/massimi perfetti = policy non causale inimitabile. Mitigazioni: (a) UI di annotazione in **replay mode**; (b) label come "eventi ± tolleranza temporale"; (c) probe model di "causal feasibility" (predice l'annotazione solo da feature passate: se AUC bassa, l'annotazione è irrealizzabile).
2. **Look-ahead bias tecnico** — indicatori su candele non chiuse, resampling ancorato male, normalizzazioni fit su tutto il dataset. Difesa: calcolo incrementale by-construction + test di perturbazione del futuro ([arXiv 2607.04958](https://arxiv.org/pdf/2607.04958)).
3. **Non-stazionarietà** — walk-forward validation obbligatoria ([arXiv 2512.12924](https://arxiv.org/html/2512.12924v1)); feature di regime nello stato; la policy imita *lo stile*, più stabile del segnale alpha.
4. **Overfitting su singolo asset + poche demo** — modelli piccoli, regolarizzazione forte, early stopping out-of-time, eventuale pretraining multi-coppia.
5. **Sim-to-real gap** — bid/ask reali (mai mid+spread fisso), latenza 100–500ms, slippage stocastico, stress-test con spread da news.
6. **Reward hacking dello shaping** — potential-based shaping, reward bounded, penalità frequenza, monitoraggio componenti decomposte.

---

## Raccomandazione sintetica (adottata nel piano)

**BC pesato sugli eventi + encoder multi-branch pretrained self-supervised + policy gerarchica (gate/testa) + fine-tuning RL (SAC discreto, critic distributional QR) con replay buffer seedato dalle demo (RLPD) e reward decomposta** = potential-based shaping sulla distanza dalle decisioni utente (peso decadente) + P&L netto + penalità rischio/frequenza. DAgger active labeling e preference learning come loop futuri. GAIL/AIRL e Decision Transformer: non necessari.

Pipeline a fasi: Fase 0 dati+simulatore → Fase A pretraining SSL encoder → Fase B BC gerarchico → Fase C fine-tuning RL → Fase D loop umano (DAgger + preferenze) → walk-forward continua.
