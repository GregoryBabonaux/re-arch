# re-arch

[English](README.md) | [Français](README.fr.md) | [Español](README.es.md) | [Deutsch](README.de.md) | [Português](README.pt-BR.md) | **Italiano** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

Una suite di skill per agenti che analizza l'architettura di un'applicazione esistente, propone architetture target dimensionate in base a quanto costa comprenderle e realizzarle, pianifica il refactoring, presenta il caso al management, inquadra gli agenti di coding AI e la CI attorno al target scelto e produce materiale formativo basato sul codice del team stesso. Pensata per qualsiasi codebase, e in particolare per quelle vibe-coded o generate da AI.

Ecosistemi supportati: JavaScript / TypeScript, PHP, .NET (C#), Java / Kotlin, C / C++, Go, Rust.

## Cosa ottieni

Esegui `re-arch-audit` su un repository e ottieni, in `.re-arch/`:

- una **mappa dei domini** dell'applicazione (aree di business, dipendenze, sistemi esterni come vista di contesto C4, zone poco definite, livello di confidenza per dominio), anche quando la struttura delle cartelle non dice nulla;
- una **diagnosi** in cui ogni finding cita file e righe, con il suo impatto per il team e per il business e la dimensione della correzione, più i punti di forza da conservare, **ciò che sembra sbagliato ma va bene** e le domande aperte per i maintainer;
- **da 2 a 4 opzioni target** (da "refactoring mirato, stessa struttura" fino a layered, vertical slices, monolite modulare, clean / hexagonal, CQRS o event sourcing quando il codice li giustifica), ciascuna dimensionata in **costo di comprensione** e **dimensione di implementazione** (S, M, L, XL), valutata rispetto agli **scenari di qualità** del business, eventualmente diversa per dominio, con gli stili presi in considerazione e scartati;
- un **piano di refactoring a fasi** in taglie T-shirt con criteri espliciti: prima una rete di sicurezza di test di caratterizzazione, passi con un comando `verify`, exit gate, rollback, punti di arresto e copertura di ogni finding critico e alto;
- un **pitch per il management**: rischi, opzioni compresa quella di non fare nulla, investimento espresso come intervallo di capacità con la sua derivazione, milestone, indicatori, decisione richiesta;
- **guardrail**: AGENTS.md alla radice e per dominio, una skill di progetto che indica agli agenti dove va il nuovo codice, un **hook per agenti** che esegue il controllo architetturale nel turno stesso dell'agente, fitness functions per la CI adottate con una **baseline congelata** (strumenti nativi per ecosistema più un checker indipendente dal linguaggio), un ADR (MADR 4), una checklist di review;
- un'**academy**: un percorso di apprendimento allineato al piano, moduli ancorati a file reali del repo (prima/dopo, kata, domande di review), letture selezionate;
- un **report HTML responsive** che raccoglie tutto, validato rispetto al contratto dati e verificato a larghezza smartphone, stampabile in PDF, più diagrammi Mermaid per la documentazione del repo;
- un **bundle [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) (OKF v0.2)** della conoscenza architetturale (sistema, domini, sistemi esterni, decisione, regole, roadmap, storico), da committare in `docs/architecture/okf/` per le persone, gli agenti di coding e i cataloghi di conoscenza; i campi di trust indicano cosa ha validato il team, e i contenuti sensibili restano fuori;
- **ri-audit** che mostrano cosa è stato risolto, cosa è nuovo e come si sono mosse le metriche.

## Skill

| Skill | Ruolo | Script |
|---|---|---|
| `re-arch-audit` | orchestratore, checkpoint per la validazione dei domini e la scelta dell'opzione, modalità ri-audit | `diff_rearch.py` |
| `re-arch-scan` | grafo delle dipendenze (di livello compilatore quando possibile), wiring DI, unità di build, accoppiamento, cicli, hotspots, co-change, distribuzione della conoscenza, duplicazione, modello dati, route, sistemi esterni, igiene delle dipendenze, secret | `scan.py`, `precise.py`, `di.py`, `insights.py`, `ts_resolve.js`, `php_refs.php` |
| `re-arch-domains` | domini di business da import + DI + co-change + modello dati + route | `cluster.py` (Louvain) |
| `re-arch-diagnose` | finding con evidenze, gravità e dimensione della correzione; catalogo degli smell con liste "da non segnalare" | |
| `re-arch-options` | architetture target, dimensionamento su due assi, scenari di qualità, tabella di razionalizzazione, catalogo degli stili, idiomi per ecosistema | |
| `re-arch-plan` | piano a fasi, passi verificabili, exit gate, tecniche incrementali | `plan_to_md.py` |
| `re-arch-pitch` | caso per il management | `pitch_to_md.py` |
| `re-arch-guardrails` | regole per agenti, skill di progetto, hook per agenti, fitness functions con baseline, ADR | `check_architecture.py` (+ scanner incluso in vendoring) |
| `re-arch-academy` | materiale formativo sul codice del team | |
| `re-arch-report` | report HTML, validazione del contratto, controllo del rendering, export Mermaid e OKF | `render.py`, `validate.py`, `check_render.py`, `to_okf.py` |

Ogni skill funziona anche da sola. Si scambiano i dati tramite file JSON in `.re-arch/`; il contratto si trova in `skills/re-arch-audit/references/contract.md` ed è fatto rispettare da `validate.py`.

## Quanto è preciso il grafo delle dipendenze?

Lo scan usa gli strumenti propri del linguaggio quando sono disponibili e lo dichiara nella sezione "Graph sources"; altrimenti ripiega sulla risoluzione tramite regex.

| Ecosistema | Fonte precisa | Requisiti |
|---|---|---|
| C/C++ | `compile_commands.json` (`-I`/`-D` reali) + albero degli include del preprocessore | un compile database (CMake `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, `bear`), un compilatore |
| Go | `go list` (build tag, percorsi esatti dei moduli) | toolchain Go |
| Rust | `cargo metadata` (grafo dei crate, `use` tra crate) | Cargo |
| Java/Kotlin | `jdeps` sulle classi compilate | un JDK e un progetto compilato |
| .NET | grafo dei ProjectReference dei `.csproj` (elimina gli archi impossibili) | nulla |
| JS/TS | il resolver di moduli di TypeScript stesso | `typescript` nel repo, oppure `--fetch-tools` |
| PHP | tokenizer PHP con risoluzione completa dei nomi | un binario `php` |

La dependency injection viene risolta separatamente (registrazioni .NET, provider NestJS/Angular, binding e facade Laravel, servizi Symfony, `@Bean` Spring, Google Wire, implementazioni uniche) in **archi di runtime**, tenuti distinti dagli import: le regole di layering usano gli import, accoppiamento e domini usano entrambi. La reflection e la scansione basata su convenzioni restano invisibili, e ogni report lo dichiara.

## Scelte di design

- **Prima le evidenze, poi le opinioni**: uno scan deterministico viene eseguito per primo; i finding puntano al codice, e la diagnosi mostra cosa ha scelto di non segnalare.
- **Nessuna architettura di default**: un'opzione leggera è sempre sul tavolo, ogni opzione deve essere giustificata da segnali nel codice e valutata rispetto agli scenari di qualità, e clean, hexagonal e onion sono un'opzione, non livelli di qualità. "Mantenere l'architettura attuale" è un esito legittimo.
- **Il costo è visibile**: costo di comprensione accanto alla dimensione di implementazione.
- **Taglie, non giorni**: taglie T-shirt con criteri espliciti; XL significa "da suddividere"; il management riceve intervalli di capacità con la loro derivazione.
- **Due pubblici**: il tech riceve evidenze e passi verificabili, il management riceve rischi e decisioni.
- **Refactoring che dura**: fitness functions con baseline congelata, hook per agenti, regole per agenti per dominio, formazione sul repo, ri-audit.
- **Le persone non sono finding**: la concentrazione della conoscenza è riportata con pseudonimi (`A1`, `A2`), la corrispondenza resta locale.

## Requisiti

- Python 3.8+ (solo libreria standard per il core).
- Opzionale, per la modalità precisa: le toolchain dei linguaggi indicate sopra; Node per il resolver TypeScript.
- Opzionale: Playwright + Chromium per verificare il rendering del report (`pip install playwright && python -m playwright install chromium`).
- Opzionale: la cronologia git nel repo analizzato (co-change, hotspots, conoscenza; evitare i clone shallow).

## Installazione

Copia le cartelle sotto `skills/` nella directory delle skill del tuo agente (per esempio `~/.claude/skills/` o `<repo>/.claude/skills/`), oppure carica i pacchetti `.skill`. Poi chiedi un audit architetturale di un repository, o invoca `/re-arch-audit`.

## Sviluppo

- `python3 tests/test_suite.py -v`: 34 test su repository fixture per ecosistema. Ogni fixture contiene trappole su cui il livello regex sbaglia (include calcolati da macro, collisioni tra directory di include, `use` tra crate, nomi qualificati inline, collisioni di namespace tra progetti, build tag, riferimenti PHP nello stesso namespace) e verifica che il livello preciso e l'estrazione DI li gestiscano correttamente; in più baseline del checker e hook, validazione del contratto, rendering a larghezza smartphone, diff dei ri-audit, export OKF (conformità, campi di trust, cronologia del log, nessun contenuto sensibile). I test che dipendono da una toolchain vengono saltati quando la toolchain manca.
- `python3 tools/sync.py` dopo aver modificato lo scanner (la skill guardrails ne include una copia in vendoring); `--check` in CI.
- `evals/`: eval end-to-end (`evals.json`, valutate da `evals/grade.py`) che includono un repository sano in cui la risposta giusta è "non passare a hexagonal", e query di attivazione per le descrizioni delle skill (`triggers.json`).
- `.github/workflows/tests.yml` esegue tutto questo.
