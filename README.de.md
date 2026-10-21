# re-arch

[English](README.md) | [Français](README.fr.md) | [Español](README.es.md) | **Deutsch** | [Português](README.pt-BR.md) | [Italiano](README.it.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

Eine Suite von Agent-Skills, die die Architektur einer bestehenden Anwendung auditiert, Zielarchitekturen vorschlägt und danach bemisst, was sie an Verständnis und an Umsetzung kosten, das Refactoring plant, das Management überzeugt, KI-Coding-Agents und CI auf das gewählte Ziel ausrichtet und Schulungsmaterial auf Basis des eigenen Codes des Teams erstellt. Gedacht für jede Codebasis, insbesondere für vibe-coded oder KI-generierte.

Unterstützte Ökosysteme: JavaScript / TypeScript, PHP, .NET (C#), Java / Kotlin, C / C++, Go, Rust.

## Was du bekommst

Führe `re-arch-audit` auf einem Repository aus, und du erhältst in `.re-arch/`:

- eine **Domänenkarte** der Anwendung (Fachbereiche, Abhängigkeiten, externe Systeme als C4-Kontextsicht, unscharfe Zonen, Konfidenz pro Domäne), selbst wenn die Ordnerstruktur nichts aussagt;
- eine **Diagnose**, in der jeder Befund Dateien und Zeilen zitiert, mit seinen Auswirkungen für das Team und für das Geschäft sowie seiner Fix-Größe, dazu die zu bewahrenden Stärken, **was schlecht aussieht, aber in Ordnung ist**, und offene Fragen an die Maintainer;
- **2 bis 4 Zieloptionen** (von "gezieltes Refactoring, gleiche Struktur" bis zu Schichten, Vertical Slices, modularem Monolithen, clean / hexagonal, CQRS oder Event Sourcing, wenn der Code sie rechtfertigt), jeweils bemessen nach **Verständniskosten** und **Umsetzungsgröße** (S, M, L, XL), bewertet anhand der **Qualitätsszenarien** des Geschäfts, gegebenenfalls unterschiedlich pro Domäne, samt der geprüften und verworfenen Stile;
- einen **phasenweisen Refactoring-Plan** in T-Shirt-Größen mit expliziten Kriterien: zuerst ein Sicherheitsnetz aus Charakterisierungstests, Schritte mit einem `verify`-Befehl, Exit Gates, Rollback, Haltepunkte und Abdeckung jedes kritischen und hohen Befunds;
- einen **Pitch für das Management**: Risiken, Optionen einschließlich Nichtstun, Investition als Kapazitätsspanne mit ihrer Herleitung, Meilensteine, Indikatoren, erbetene Entscheidung;
- **Guardrails**: AGENTS.md im Root und pro Domäne, ein Projekt-Skill, der Agents sagt, wohin neuer Code gehört, ein **Agent-Hook**, der den Architektur-Check im eigenen Turn des Agents ausführt, fitness functions für die CI, eingeführt mit einer **eingefrorenen Baseline** (native Tools pro Ökosystem plus ein sprachunabhängiger Checker), ein ADR (MADR 4), eine Review-Checkliste;
- eine **Academy**: ein Lernpfad, abgestimmt auf den Plan, Module verankert in echten Dateien des Repos (Vorher/Nachher, Katas, Review-Fragen), kuratierte Lektüre;
- einen **responsiven HTML-Bericht**, der alles bündelt, gegen den Datenvertrag validiert und in Smartphone-Breite geprüft, als PDF druckbar, dazu Mermaid-Diagramme für die Doku des Repos;
- ein **[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) (OKF v0.2) Bundle** des Architekturwissens (System, Domänen, externe Systeme, Entscheidung, Regeln, Roadmap, Historie), zum Committen unter `docs/architecture/okf/` für Menschen, Coding-Agents und Knowledge-Kataloge; Trust-Felder geben an, was das Team validiert hat, und sensible Inhalte bleiben außen vor;
- **Re-Audits**, die zeigen, was behoben wurde, was neu ist und wie sich die Metriken entwickelt haben.

## Skills

| Skill | Rolle | Skripte |
|---|---|---|
| `re-arch-audit` | Orchestrator, Checkpoints für Domänenvalidierung und Optionswahl, Re-Audit-Modus | `diff_rearch.py` |
| `re-arch-scan` | Abhängigkeitsgraph (wenn möglich in Compiler-Qualität), DI-Verdrahtung, Build-Einheiten, Kopplung, Zyklen, Hotspots, Co-Change, Wissensverteilung, Duplikation, Datenmodell, Routen, externe Systeme, Abhängigkeitshygiene, Secrets | `scan.py`, `precise.py`, `di.py`, `insights.py`, `ts_resolve.js`, `php_refs.php` |
| `re-arch-domains` | Fachdomänen aus Imports + DI + Co-Change + Datenmodell + Routen | `cluster.py` (Louvain) |
| `re-arch-diagnose` | Befunde mit Belegen, Schweregrad und Fix-Größe; Smell-Katalog mit "nicht melden"-Listen | |
| `re-arch-options` | Zielarchitekturen, Bemessung auf zwei Achsen, Qualitätsszenarien, Begründungstabelle, Stilkatalog, Idiome der Ökosysteme | |
| `re-arch-plan` | phasenweiser Plan, überprüfbare Schritte, Exit Gates, inkrementelle Techniken | `plan_to_md.py` |
| `re-arch-pitch` | Business Case für das Management | `pitch_to_md.py` |
| `re-arch-guardrails` | Agent-Regeln, Projekt-Skill, Agent-Hooks, fitness functions mit Baseline, ADR | `check_architecture.py` (+ vendored Scanner) |
| `re-arch-academy` | Schulungsmaterial auf dem eigenen Code des Teams | |
| `re-arch-report` | HTML-Bericht, Vertragsvalidierung, Rendering-Check, Mermaid- und OKF-Export | `render.py`, `validate.py`, `check_render.py`, `to_okf.py` |

Jeder Skill funktioniert auch allein. Sie tauschen Daten über JSON-Dateien in `.re-arch/` aus; der Vertrag steht in `skills/re-arch-audit/references/contract.md` und wird von `validate.py` durchgesetzt.

## Wie präzise ist der Abhängigkeitsgraph?

Der Scan nutzt die Tools der jeweiligen Sprache, wenn sie verfügbar sind, und weist das in seinem Abschnitt "Graph sources" aus; andernfalls greift er auf Regex-Auflösung zurück.

| Ökosystem | Präzise Quelle | Voraussetzungen |
|---|---|---|
| C/C++ | `compile_commands.json` (echte `-I`/`-D`) + Include-Baum des Präprozessors | eine Compile-Datenbank (CMake `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, `bear`), ein Compiler |
| Go | `go list` (Build-Tags, exakte Modulpfade) | Go-Toolchain |
| Rust | `cargo metadata` (Crate-Graph, crate-übergreifendes `use`) | Cargo |
| Java/Kotlin | `jdeps` auf kompilierten Klassen | ein JDK und ein gebautes Projekt |
| .NET | `.csproj`-ProjectReference-Graph (entfernt unmögliche Kanten) | nichts |
| JS/TS | der eigene Modul-Resolver von TypeScript | `typescript` im Repo oder `--fetch-tools` |
| PHP | PHP-Tokenizer mit vollständiger Namensauflösung | ein `php`-Binary |

Dependency Injection wird separat aufgelöst (.NET-Registrierungen, NestJS/Angular-Provider, Laravel-Bindings und -Facades, Symfony-Services, Spring `@Bean`, Google Wire, Einzelimplementierungen), und zwar in **Laufzeitkanten**, getrennt von den Imports: Schichtregeln verwenden Imports, Kopplung und Domänen verwenden beides. Reflection und konventionsbasiertes Scanning bleiben unsichtbar, und jeder Bericht sagt das.

## Designentscheidungen

- **Belege vor Meinung**: zuerst läuft ein deterministischer Scan; Befunde verweisen auf Code, und die Diagnose zeigt, was sie bewusst nicht gemeldet hat.
- **Keine Architektur per Default**: eine leichte Option liegt immer auf dem Tisch, jede Option muss durch Signale im Code begründet und anhand von Qualitätsszenarien bewertet werden, und clean, hexagonal und onion sind eine Option, keine Qualitätsstufen. "Die aktuelle Architektur beibehalten" ist ein legitimes Ergebnis.
- **Kosten sind sichtbar**: Verständniskosten neben der Umsetzungsgröße.
- **Größen, keine Tage**: T-Shirt-Größen mit expliziten Kriterien; XL heißt "aufteilen"; das Management bekommt Kapazitätsspannen mit ihrer Herleitung.
- **Zwei Zielgruppen**: Tech bekommt Belege und überprüfbare Schritte, das Management Risiken und Entscheidungen.
- **Refactoring, das hält**: fitness functions mit eingefrorener Baseline, Agent-Hooks, Agent-Regeln pro Domäne, Schulung am Repo, Re-Audits.
- **Menschen sind keine Befunde**: Wissenskonzentration wird mit Pseudonymen (`A1`, `A2`) berichtet, die Zuordnung bleibt lokal.

## Voraussetzungen

- Python 3.8+ (für den Kern nur die Standardbibliothek).
- Optional, für den präzisen Modus: die oben genannten Toolchains; Node für den TypeScript-Resolver.
- Optional: Playwright + Chromium, um das Rendering des Berichts zu prüfen (`pip install playwright && python -m playwright install chromium`).
- Optional: Git-Historie im auditierten Repo (Co-Change, Hotspots, Wissen; Shallow Clones vermeiden).

## Installation

Kopiere die Ordner unter `skills/` in das Skills-Verzeichnis deines Agents (zum Beispiel `~/.claude/skills/` oder `<repo>/.claude/skills/`) oder lade die `.skill`-Pakete hoch. Bitte dann um ein Architektur-Audit eines Repositorys oder rufe `/re-arch-audit` auf.

## Entwicklung

- `python3 tests/test_suite.py -v`: 34 Tests auf Fixture-Repositorys pro Ökosystem. Jede Fixture legt Fallen aus, an denen die Regex-Schicht scheitert (per Makro berechnete Includes, Kollisionen von Include-Verzeichnissen, crate-übergreifendes `use`, inline qualifizierte Namen, Namespace-Kollisionen zwischen Projekten, Build-Tags, PHP-Referenzen im selben Namespace), und prüft, dass die präzise Schicht und die DI-Extraktion sie richtig auflösen; dazu Checker-Baseline und Hooks, Vertragsvalidierung, Rendering in Smartphone-Breite, Re-Audit-Diffs, OKF-Export (Konformität, Trust-Felder, Log-Historie, nichts Sensibles). Toolchain-abhängige Tests werden übersprungen, wenn die Toolchain fehlt.
- `python3 tools/sync.py` nach Änderungen am Scanner (der Guardrails-Skill enthält eine vendored Kopie); `--check` in der CI.
- `evals/`: End-to-End-Evals (`evals.json`, bewertet von `evals/grade.py`), darunter ein gesundes Repository, bei dem die richtige Antwort "nicht auf hexagonal umstellen" lautet, sowie Trigger-Queries für die Skill-Beschreibungen (`triggers.json`).
- `.github/workflows/tests.yml` führt all das aus.
