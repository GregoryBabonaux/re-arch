# Template: architecture rules for AI coding agents

Adapt to the repo: real paths, real file names, real commands. Keep it under about 120 lines; agents read it on every task. Write in the team's working language.

```markdown
## Architecture

This codebase follows <target in one sentence, e.g. "layered architecture per domain; the orders domain uses clean architecture">.
Decision record: docs/adr/0001-target-architecture.md.

### Domains
| Domain | Folder | Style |
|---|---|---|
| Orders | src/modules/orders | clean architecture |
| Catalog | src/modules/catalog | service + repository |

### Where new code goes
| You are adding... | Put it in | Reference example |
|---|---|---|
| an HTTP endpoint | src/app/api/<domain>/route.ts, thin: parse, call the service, map the result | src/app/api/orders/route.ts |
| a business rule | src/modules/<domain>/domain/ as a pure function or entity method, with unit tests | src/modules/orders/domain/pricing.ts |
| a use case | src/modules/<domain>/application/<verb-noun>.ts | src/modules/orders/application/place-order.ts |
| database access | src/modules/<domain>/infrastructure/<entity>-repository.ts | ... |
| a call to a third-party API | an adapter in src/modules/<domain>/infrastructure/, behind an interface owned by the domain | ... |
| UI | src/app/<route>/ components; no business calculation in components | ... |

### Rules (and why)
- Never call the database client from routes, pages or components: it puts business logic where it cannot be tested (see finding F1).
- Never duplicate a business rule between client and server: import the shared pure function.
- A domain imports another domain only through its `index.ts`: internals change without notice.
- No new files in `src/utils` for business logic: it belongs to a domain.
- Side effects (email, payment, webhooks) go through the domain's adapters, never inline in a route.
- Do not add a new library for something the codebase already does (HTTP client, dates, validation): use <existing choices>.
- Do not create interfaces, factories or layers that the table above does not ask for.

### Before proposing a change
1. Run `python3 tools/re-arch/check_architecture.py tools/re-arch/architecture-rules.json --baseline tools/re-arch/re-arch-baseline.json --changed-only --format agent` (or the native tool) and fix any new violation by moving the code, never by editing the rules or the baseline.
2. Add or update tests for every business rule you touch (`<test command>`).
3. If the change does not fit the table above, stop and ask instead of inventing a new pattern.

### Legacy areas
Code in <legacy paths> does not follow these rules yet (refactoring plan phase <N>). When you modify it, do not extend the old pattern; put new logic in the target structure and call it from the old code.
```

## Domain-specific files

When a domain has its own style (for example clean architecture in `orders`, plain layering elsewhere), put its rules in `src/orders/AGENTS.md`: the closest AGENTS.md to the edited file wins, so the root file stays simple. A domain file only states what differs: its folder table, its forbidden imports, its reference implementation.
