# re-arch

[English](README.md) | **Français** | [Español](README.es.md) | [Deutsch](README.de.md) | [Português](README.pt-BR.md) | [Italiano](README.it.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) · **[Site web](https://gregorybabonaux.github.io/re-arch/?lang=fr)**

![Rapport re-arch : synthèse et carte des domaines](docs/images/banner.png)

Une suite de skills pour agents qui audite l'architecture d'une application existante, propose des architectures cibles dimensionnées selon ce qu'elles coûtent à comprendre et à construire, planifie le refactoring, construit l'argumentaire pour la direction, encadre les agents de code IA et la CI autour de la cible retenue, et produit du matériel de formation construit sur le propre code de l'équipe. Conçue pour toute base de code, et en particulier pour les bases vibe-coded ou générées par IA.

Écosystèmes supportés : JavaScript / TypeScript, PHP, .NET (C#), Java / Kotlin, C / C++, Go, Rust.

## Ce que vous obtenez

Lancez `re-arch-audit` sur un dépôt et vous obtenez, dans `.re-arch/` :

- une **cartographie des domaines** de l'application (zones métier, dépendances, systèmes externes sous forme de vue de contexte C4, zones floues, niveau de confiance par domaine), même quand l'arborescence ne veut rien dire ;
- un **diagnostic** où chaque constat cite des fichiers et des lignes, avec son impact pour l'équipe et pour le métier et la taille de sa correction, ainsi que les points forts à conserver, **ce qui a l'air mauvais mais ne l'est pas**, et les questions ouvertes pour les mainteneurs ;
- **2 à 4 options cibles** (du « refactoring ciblé, même structure » à l'architecture en couches, aux vertical slices, au monolithe modulaire, à clean / hexagonal, CQRS ou event sourcing quand le code les justifie), chacune dimensionnée en **coût de compréhension** et en **taille d'implémentation** (S, M, L, XL), évaluée au regard des **scénarios de qualité** du métier, éventuellement différente selon le domaine, avec les styles envisagés puis écartés ;
- un **plan de refactoring par phases** en tailles de T-shirt aux critères explicites : d'abord un filet de sécurité de tests de caractérisation, des étapes munies d'une commande `verify`, des critères de sortie, un rollback, des points d'arrêt, et la couverture de chaque constat critique et élevé ;
- un **argumentaire pour la direction** : risques, options y compris ne rien faire, investissement exprimé en fourchette de capacité avec son calcul, jalons, indicateurs, décision attendue ;
- des **garde-fous** : AGENTS.md à la racine et par domaine, une skill projet qui indique aux agents où placer le nouveau code, un **hook d'agent** qui exécute la vérification d'architecture pendant le tour de l'agent lui-même, des fitness functions pour la CI adoptées avec une **baseline gelée** (outils natifs par écosystème plus un vérificateur indépendant du langage), un ADR (MADR 4), une checklist de revue ;
- une **académie** : un parcours d'apprentissage aligné sur le plan, des modules ancrés dans de vrais fichiers du dépôt (avant/après, katas, questions de revue), des lectures sélectionnées ;
- un **rapport HTML responsive** qui rassemble le tout, validé par rapport au contrat de données et vérifié en largeur mobile, imprimable en PDF, plus des diagrammes Mermaid pour la documentation du dépôt ;
- un **bundle [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) (OKF v0.2)** de la connaissance d'architecture (système, domaines, systèmes externes, décision, règles, feuille de route, historique), à committer sous `docs/architecture/okf/` pour les humains, les agents de code et les catalogues de connaissance ; des champs de confiance indiquent ce que l'équipe a validé, et le contenu sensible en est exclu ;
- des **re-audits** qui montrent ce qui a été résolu, ce qui est nouveau et comment les métriques ont évolué.

## Exemple de rapport

Généré par re-arch sur *Factureo*, une app de facturation vibe codée fictive écrite pour les évals. [Téléchargez le rapport complet](docs/example/report-factureo.html) et ouvrez-le dans un navigateur.

**Carte des domaines** : domaines métier et leurs dépendances, dépendances mutuelles en orange.

![Carte des domaines](docs/images/domain-map.png)

**Options** : 2 à 4 cibles, chacune dimensionnée en coût de compréhension et en taille d'implémentation, évaluée au regard des scénarios de qualité du métier.

![Options](docs/images/options.png)

**Plan** : phases avec leur taille, leurs critères de sortie, le rollback et les points d'arrêt.

![Plan](docs/images/plan.png)

**Sur téléphone** : chaque onglet est vérifié à 390 px de large.

![Sur téléphone](docs/images/mobile.png)

## Skills

| Skill | Rôle | Scripts |
|---|---|---|
| `re-arch-audit` | orchestrateur, points de contrôle pour la validation des domaines et le choix de l'option, mode re-audit | `diff_rearch.py` |
| `re-arch-scan` | graphe de dépendances (précision compilateur quand c'est possible), câblage DI, unités de build, couplage, cycles, hotspots, co-change, répartition de la connaissance, duplication, modèle de données, routes, systèmes externes, hygiène des dépendances, secrets | `scan.py`, `precise.py`, `di.py`, `insights.py`, `ts_resolve.js`, `php_refs.php` |
| `re-arch-domains` | domaines métier à partir des imports + DI + co-change + modèle de données + routes | `cluster.py` (Louvain) |
| `re-arch-diagnose` | constats avec preuves, sévérité et taille de correction ; catalogue de smells avec listes « à ne pas signaler » | |
| `re-arch-options` | architectures cibles, dimensionnement sur deux axes, scénarios de qualité, tableau de rationalisation, catalogue de styles, idiomes par écosystème | |
| `re-arch-plan` | plan par phases, étapes vérifiables, critères de sortie, techniques incrémentales | `plan_to_md.py` |
| `re-arch-pitch` | argumentaire pour la direction | `pitch_to_md.py` |
| `re-arch-guardrails` | règles pour agents, skill projet, hooks d'agent, fitness functions avec baseline, ADR | `check_architecture.py` (+ scanner embarqué) |
| `re-arch-academy` | matériel de formation sur le propre code de l'équipe | |
| `re-arch-report` | rapport HTML, validation du contrat, vérification du rendu, export Mermaid et OKF | `render.py`, `validate.py`, `check_render.py`, `to_okf.py` |

Chaque skill fonctionne aussi seule. Elles échangent leurs données via des fichiers JSON dans `.re-arch/` ; le contrat est décrit dans `skills/re-arch-audit/references/contract.md` et appliqué par `validate.py`.

## Quelle est la précision du graphe de dépendances ?

Le scan utilise les outils propres au langage quand ils sont disponibles et l'indique dans sa section « Graph sources » ; sinon il se rabat sur une résolution par regex.

| Écosystème | Source précise | Prérequis |
|---|---|---|
| C/C++ | `compile_commands.json` (vrais `-I`/`-D`) + arbre d'inclusion du préprocesseur | une base de compilation (CMake `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, `bear`), un compilateur |
| Go | `go list` (build tags, chemins de modules exacts) | toolchain Go |
| Rust | `cargo metadata` (graphe des crates, `use` inter-crates) | Cargo |
| Java/Kotlin | `jdeps` sur les classes compilées | un JDK et un projet compilé |
| .NET | graphe des ProjectReference des `.csproj` (élague les arêtes impossibles) | rien |
| JS/TS | le résolveur de modules de TypeScript lui-même | `typescript` dans le dépôt, ou `--fetch-tools` |
| PHP | tokenizer PHP avec résolution complète des noms | un binaire `php` |

L'injection de dépendances est résolue à part (enregistrements .NET, providers NestJS/Angular, bindings et facades Laravel, services Symfony, `@Bean` Spring, Google Wire, implémentations uniques) en **arêtes runtime**, tenues séparées des imports : les règles de couches s'appuient sur les imports, le couplage et les domaines sur les deux. La réflexion et le scanning par convention restent invisibles, et chaque rapport le précise.

## Choix de conception

- **Les preuves avant l'opinion** : un scan déterministe s'exécute d'abord ; les constats pointent vers le code, et le diagnostic montre ce qu'il a choisi de ne pas signaler.
- **Pas d'architecture par défaut** : une option légère est toujours sur la table, chaque option doit être justifiée par des signaux dans le code et évaluée au regard des scénarios de qualité, et clean, hexagonal et onion forment une seule option, pas des niveaux de qualité. « Conserver l'architecture actuelle » est une issue légitime.
- **Le coût est visible** : le coût de compréhension à côté de la taille d'implémentation.
- **Des tailles, pas des jours** : tailles de T-shirt aux critères explicites ; XL signifie « à découper » ; la direction reçoit des fourchettes de capacité avec leur calcul.
- **Deux publics** : la tech reçoit des preuves et des étapes vérifiables, la direction des risques et des décisions.
- **Un refactoring qui tient** : fitness functions à baseline gelée, hooks d'agent, règles pour agents par domaine, formation sur le dépôt, re-audits.
- **Les personnes ne sont pas des constats** : la concentration de la connaissance est rapportée sous pseudonymes (`A1`, `A2`), la table de correspondance reste locale.

## Prérequis

- Python 3.8+ (bibliothèque standard uniquement pour le cœur).
- Optionnel, pour le mode précis : les toolchains listées ci-dessus ; Node pour le résolveur TypeScript.
- Optionnel : Playwright + Chromium pour vérifier le rendu du rapport (`pip install playwright && python -m playwright install chromium`).
- Optionnel : l'historique git du dépôt audité (co-change, hotspots, connaissance ; évitez les shallow clones).

## Installation

**Claude Code** (une seule étape, Claude Code 2.1.275 ou plus récent) :

```
/plugin install re-arch --marketplace GregoryBabonaux/re-arch
```

Versions plus anciennes : `/plugin marketplace add GregoryBabonaux/re-arch`, puis `/plugin install re-arch@re-arch`.

**Tout autre agent** (Codex, Cursor, Gemini, Copilot…) :

```
npx skills add GregoryBabonaux/re-arch
```

Ajoutez `-g` pour l'installer pour tous vos projets.

Ensuite, dans le projet à auditer, demandez simplement : *« audite l'architecture de ce dépôt »*.

Mise à jour : `claude plugin update re-arch@re-arch` (Claude Code) ou `npx skills update`.

## Développement

- `python3 tests/test_suite.py -v` : 34 tests sur des dépôts de fixtures par écosystème. Chaque fixture pose des pièges sur lesquels la couche regex se trompe (includes calculés par macro, collisions de répertoires d'inclusion, `use` inter-crates, noms qualifiés en ligne, collisions de namespaces entre projets, build tags, références PHP dans le même namespace) et vérifie que la couche précise et l'extraction DI les traitent correctement ; plus la baseline du vérificateur et les hooks, la validation du contrat, le rendu en largeur mobile, les diffs de re-audit, l'export OKF (conformité, champs de confiance, historique du log, aucun contenu sensible). Les tests qui dépendent d'une toolchain sont ignorés quand celle-ci est absente.
- `python3 tools/sync.py` après toute modification du scanner (la skill guardrails en embarque une copie) ; `--check` en CI.
- `evals/` : evals de bout en bout (`evals.json`, notées par `evals/grade.py`), dont un dépôt sain où la bonne réponse est « ne pas passer en hexagonal », et des requêtes de déclenchement pour les descriptions des skills (`triggers.json`).
- `.github/workflows/tests.yml` exécute l'ensemble.
