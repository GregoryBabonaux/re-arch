---
name: re-arch-scan
description: Deterministic structural scan of a codebase for architecture work - dependency graph (compiler-grade when the toolchain is available, regex fallback otherwise), dependency-injection wiring, build units, module coupling, cycles, hotspots, git co-change, knowledge distribution, duplicated code, data model, HTTP routes, external systems, dependency hygiene and files mixing UI or HTTP with persistence. Use as the first step of any architecture audit or refactoring plan, or whenever someone asks for a dependency graph, coupling metrics, cycles, hotspots or bus-factor risks of a JavaScript/TypeScript, PHP, .NET/C#, Java/Kotlin, C/C++, Go or Rust project. Part of the re-arch suite (re-arch-audit runs it automatically).
---

# re-arch-scan

Produce facts before anyone forms an opinion. The scan is a set of scripts (Python standard library, plus the language's own tools when present) so it gives the same answer every time and does not depend on the model reading thousands of files.

## Run it

```bash
python3 <this-skill-dir>/scripts/scan.py <repo-root> [--out <repo-root>/.re-arch] [--exclude 'legacy/**'] [--since '12 months ago']
```

Options that change what the scan may do:
- `--precise auto` (default): use compiler-grade sources when available (table below). `--precise off` forces the regex layer, useful only to compare.
- `--fetch-tools`: allows downloading analysis tools from the package registry (today: the `typescript` package for the JS/TS resolver, cached in `~/.cache/re-arch-scan`). It never runs repository code. Use it when the repo has no `node_modules` and the network allows it.
- `--allow-build`: allows steps that execute the project's build scripts (CMake configure to produce `compile_commands.json`, Maven/Gradle compile for `jdeps`). **Ask the person before using it**: build scripts are code from the repository. Without it, the scan uses what is already built or falls back.
- `--module-depth auto` (default) uses build units (projects, crates, Maven/Gradle modules, workspace packages) as the first level of modules when they exist, otherwise the first folder below the source root, and splits any module holding more than 35% of the code.
- `--exclude` for generated code, vendored libraries or legacy folders the team explicitly leaves out. Ask before excluding anything the team did not mention.
- No git history (archive, shallow clone): pass `--no-git` and say that churn, hotspots by change frequency, co-change and knowledge distribution are missing. With a shallow clone, suggest `git fetch --unshallow` first. An inactive repository (no commit in the window) automatically falls back to its last 500 commits.
- Monorepo with unrelated services: scan each service with its own `--out` (for example `.re-arch/billing`).

Python 3.8+ is the only hard requirement.

## How dependencies are resolved

The summary starts with a "Graph sources" section. Read it first: it says how much to trust each language's graph.

| Ecosystem | Precise source (used automatically when available) | Fallback |
|---|---|---|
| C/C++ | `compile_commands.json` (real `-I`/`-D` per file) + preprocessor include tree (`clang++/g++ -E -H`: macro-computed includes, conditional compilation) | include dirs parsed from CMakeLists, then conventional roots |
| Go | `go list -e -json` (exact import paths, build tags, std excluded; `GOPROXY=off`, no download) | module path from go.mod |
| Rust | `cargo metadata --no-deps --offline` (crate graph, crate roots, cross-crate `use`) | Cargo.toml parsed directly |
| Java/Kotlin | `jdeps` on compiled classes (class-level, sees inline qualified names, Kotlin) | imports + same-package names |
| .NET | `.csproj` ProjectReference graph (exact, no build): cross-project edges not declared are dropped as resolution errors | namespaces + type names |
| JS/TS | TypeScript's own resolver (tsconfig per file with `extends`, `paths`, `exports`, workspaces) from the repo's `typescript` or `--fetch-tools` | tsconfig paths + workspace names parsed by the scanner |
| PHP | PHP tokenizer: every class reference resolved with namespace and `use` rules (same-namespace, `::class`, inline names) | `use` statements + same namespace |

When a precise source was not available, the summary says why in "note:" lines and how to get it (install dependencies, generate `compile_commands.json`, build the Java project). Pass that on to the person when the graph matters for the conclusions.

## Read the result

Read `.re-arch/scan-summary.md` first, it is short on purpose. `scan.json` holds every file with its imports, runtime imports, signals, churn and metrics; query it with a few lines of Python for details rather than loading it whole.

| Section | Use it to |
|---|---|
| Graph sources, notes | know how far to trust each graph |
| Build units | the compiler-enforced structure (projects, crates, modules, packages); phantom workspace dependencies |
| Dependency injection | bindings found (an empty section is normal when the framework generates implementations, as Spring Data repositories, or when constructors are wired explicitly) (explicit registrations, facades, single implementations) and runtime edges consumer -> implementation. Runtime edges are kept apart from imports: layering rules use imports, coupling and domains use both |
| Modules (Ca, Ce, I) and dependencies | modules everything depends on, modules depending on everything; "at runtime (DI)" lines show hidden coupling |
| Cycles | module cycles block layering and extraction; file cycles are often the first refactoring step |
| Mixed responsibilities | candidates for business logic in controllers/components: open each file, the signals are regexes |
| Hotspots | complex code that changes often: where refactoring pays first |
| Fix commits, most fixed files | the most concrete evidence of cost for both audiences |
| Knowledge distribution | knowledge islands in hotspots, code whose authors left, modules owned by one person (pseudonymised, see below) |
| Duplicated blocks | copy-paste, frequent in generated code |
| Data model | raw material for domain discovery |
| Co-change pairs | hidden coupling; commits sharing a ticket id (JIRA-123, #456) are grouped as one change |
| Dependency hygiene | several libraries for one job, packages imported but not declared (phantom or hallucinated), declared but never imported |
| External systems | databases, payment, email, queues, LLM APIs, hard-coded HTTP hosts: the C4 context view |
| HTTP routes | routes and handler files; the main domain signal in framework-convention layouts |
| Possible secrets | a security finding; never copy the value anywhere, cite the location only |

## People data

Knowledge distribution is about people. The scan pseudonymises authors (`A1` is the largest contributor) in `scan.json` and every deliverable; the mapping goes to `.re-arch/authors-map.json`, with a `.gitignore` next to it, for the tech lead only. Never put real names or emails in findings, report or pitch, and present knowledge concentration as an organisational risk, never as individual performance. With fewer than 3 authors, concentration is normal and is not reported as islands.

## Limits to keep in mind

The summary ends with the limits that apply to this run. The main ones:
- reflection, string-built class names, convention-based registration (assembly scanning, component scanning without type references) stay invisible even in precise mode;
- framework file-based conventions (Next.js routing, Laravel routes) are covered by route extraction, not by the import graph;
- responsibility signals (`db`, `http`, `ui`, `external_io`, `env_config`, `global_state`) are pattern matches: open the cited line before turning one into a finding;
- "declared but never imported" lists candidates: packages used only from scripts, config or CLIs are legitimately absent from imports.

## Output for the next steps

Nothing to write beyond the script output. Tell the orchestrator (or the person, when run alone) in a few lines: size, test ratio, graph sources and their precision, number of module cycles, mixed-responsibility files, the top three hotspots, the share of fix commits, and anything the person should do to get a precise graph.
