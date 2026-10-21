# Smell catalog

Checklist for the diagnosis. Each entry: what it is, how to spot it (scan signal and what to read), how it shows per ecosystem, and why it matters. Report only what you found in the code.

## Contents
1. Layering and placement of business logic
2. Coupling and cycles
3. Boundaries between domains
4. Duplication
5. Data model
6. Testing
7. State and side effects
8. Error handling and transactions
9. Configuration and security
10. Consistency and vibe-coding tells
11. Dead code
12. Design-level performance traps
13. Dependency hygiene
14. Knowledge concentration

Each section ends with a **Do not flag** list: what looks like the smell but is fine. Use it: precision is what makes a team act on a diagnosis.

---

## 1. Layering and placement of business logic

**Business rules in entry points.** Pricing, eligibility, state transitions, calculations written inside HTTP handlers, controllers, UI components, CLI commands or message consumers.
- Scan: `mixed_responsibilities` (http/ui + db/external_io in one file), high `branches` in handler files.
- Read: are there `if` chains on business values (amounts, statuses, roles, dates) inside the handler? Could the rule be tested without HTTP and a database?
- JS/TS: Next.js `route.ts`/server actions/`page.tsx` with Prisma or Supabase calls and calculations; Express handlers of 100+ lines; React components computing totals.
- PHP: Laravel controllers with Eloquent queries and business `if`s; Symfony controllers using the EntityManager directly; logic in Blade templates.
- .NET: controllers or minimal API lambdas using `DbContext`; logic in Razor pages.
- Java: `@RestController` methods using repositories and computing; "services" that are only transaction scripts calling repositories with all logic inline (fine for CRUD, a problem in a core domain).
- Go: `http.HandlerFunc` doing SQL and rules; packages named `handlers` holding everything.
- Rust: axum/actix handlers with sqlx queries and rules.
- C++: UI or network callback code holding domain logic; god classes mixing I/O and computation.
- Why: rules cannot be tested in isolation, get duplicated across entry points, and every change needs the full stack running.

**Inverted dependencies.** Lower-level code importing upper layers: a model/repository importing a controller, a service importing an HTTP request type, domain code importing the ORM or the web framework.
- Scan: module dependencies against the intended direction; cycles involving controllers.
- Why: nothing can be reused or tested without dragging the framework along.

**Anaemic core vs fat services.** Entities as pure data bags with all behaviour in 1,000-line services. Normal and fine in CRUD domains; a weakness only in a core domain with real invariants (an order that can be paid twice, stock that can go negative).

**Leaky abstractions.** Repositories returning ORM query builders, "services" taking `Request` objects, DTOs that are the ORM entities serialised straight to the API.

**Do not flag**: business rules in handlers of a pure CRUD endpoint with no rule beyond validation (moving them adds a layer for nothing); thin controllers that call the ORM directly in a `generic` or `supporting` domain when the team chose transaction scripts there; anaemic entities in CRUD domains; framework-mandated structure (Next.js `route.ts`, Laravel Form Requests, Spring `@Controller`) used as intended.

## 2. Coupling and cycles

**Module cycles.** A depends on B depends on A, directly or through others.
- Scan: `module_cycles`, `file_cycles` with an example path.
- Why: neither side can change, be tested or be extracted alone. A cycle between domains forbids any modularisation until broken.
- Note: Go forbids package cycles (a reported one is non-compiling code or a scan miss); Rust allows cycles inside a crate but not between crates; .NET forbids cycles between projects but not between namespaces of one project; Java and JS/TS allow everything.

**Hub modules.** A module with very high afferent coupling (`Ca`) that is also concrete and changing often (high churn): every change ripples everywhere. Classic: `utils.ts`, `helpers.php`, `Common` project, `shared` package holding business logic.

**Hidden coupling.** Strong git co-change between files with no import between them: a rule copied in two places, a shared convention (string keys, status codes, column names) without a shared definition.

**Temporal coupling.** Functions that must be called in a given order with nothing enforcing it (init then use, set fields then save).

**Do not flag**: a cycle between two files of the same small module that always change together (it is one unit); stable, abstract hubs (interfaces, shared types, the db client) with high fan-in, which is what they are for; Go package size alone when the package is cohesive.

## 3. Boundaries between domains

- One domain reading or writing another domain's tables or entities directly.
- A "god entity" (`User`, `Account`, `Company`) carrying fields and behaviour of every domain.
- Domains calling each other's internals instead of a small public surface.
- No public surface at all: every file importable from everywhere (no `index`/facade, no `internal/` in Go, no `pub(crate)` discipline in Rust, everything `public` in .NET/Java).
- Scan: cluster modularity below ~0.3, many cross-cluster dependencies, entities used by most domains.

**Do not flag**: shared reference entities (`User`, `Tenant`) read by several domains through a stable interface; a "shared kernel" the team deliberately keeps small (money, ids, dates).

## 4. Duplication

- **Duplicated rules** (most expensive): the same business rule in front and back, in two handlers, in a job and an API. Look for identical constants and conditions across files (discount thresholds, status lists, date windows).
- **Copy-pasted code**: scan `duplicates`. Distinguish accidental (same code, same reason to change: factor out) from incidental (same code today, different reasons to change: leave it).
- **Parallel implementations**: two HTTP clients, two date libraries, two validation approaches, two state managers. Very common in AI-generated code where each prompt brought its own solution.

**Do not flag**: incidental duplication (same code, different reasons to change: two DTOs that happen to have the same fields, two validation schemas for two APIs); test fixtures and builders; generated code; three similar lines (factoring them costs more than it saves).

## 5. Data model

- ORM entities used as API contracts (any schema change breaks clients, internal fields leak).
- Missing constraints in the database for invariants enforced only in code (or nowhere).
- Business states as free strings instead of enums or types; impossible states representable.
- Data of several domains in one table or document "for convenience".
- Mongo/document stores with no schema and code defensively checking for every field.

**Do not flag**: ORM entities as API contracts in an internal back-office with one client; free strings for states that are display-only.

## 6. Testing

- Test/prod LOC ratio (scan totals) and, more important, where tests are: tests on utils and none on the core domain is worse than few tests overall.
- Tests that need the whole stack (database, network) for every rule: a symptom of logic placement (section 1).
- Snapshot-only or "it renders" tests on business screens.
- No test at all on payment, pricing, permissions, data deletion: report as high or critical depending on exposure.
- Why it matters for the plan: refactoring without a safety net changes behaviour silently, so the plan will start with characterisation tests.

**Do not flag**: absence of unit tests on glue code (route wiring, DI configuration, thin adapters) covered by integration tests; snapshot tests on pure presentation components; low coverage in a domain that is stable and rarely changed (report it as low at most).

## 7. State and side effects

- Module-level mutable state, singletons holding request data, static mutable fields (scan signal `global_state`).
- Side effects hidden in getters, constructors, or "helpers" (sending email from a model hook, calling Stripe in a serializer).
- External calls (email, payment, storage, third-party APIs) made inline in business flows with no abstraction: untestable and impossible to retry or replace.

**Do not flag**: module-level constants and caches that are immutable after start-up; the framework's own request-scoped context (`auth()`, `request()` in Laravel controllers, `HttpContext` in ASP.NET controllers) when used in the entry layer; logging calls.

## 8. Error handling and transactions

- Multi-step writes (create order, decrement stock, charge card) without a transaction or compensation: partial failures leave inconsistent data.
- External call inside a DB transaction (holding locks during a network call) or outside it when consistency requires otherwise.
- Swallowed errors (`catch {}`, `_ = err`, `unwrap()` everywhere in Rust, `@` in PHP), generic 500s, errors as strings.
- No idempotency on payment or webhook handlers.

**Do not flag**: try/catch at the edge of the application that maps errors to responses (that is its job); `unwrap()`/`expect()` in Rust tests, build scripts and start-up code where a panic is the intended behaviour.

## 9. Configuration and security

- Secrets in code (scan `possible_secrets`; cite location only, recommend rotation, since a secret in git history stays exposed even after deletion).
- `process.env`/`getenv` read deep inside business code instead of injected configuration (scan `env_config`).
- Authorisation checks scattered in handlers, missing on some routes, or done client side only.
- SQL built by string concatenation.
These are architecture findings when they come from structure (no single place for config or authorisation); a full security audit is a separate job, say so if you see many.

**Do not flag**: `process.env`/`getenv` read in one configuration module at start-up (that is the right place); example or placeholder keys in `.env.example`, test fixtures or documentation (check before calling it a secret).

## 10. Consistency and vibe-coding tells

Typical of code generated prompt by prompt without an architectural frame:
- **Several patterns for the same job**: some routes use a service, others call the ORM directly, others go through a custom hook; three folders named `utils`, `helpers`, `lib` with overlapping content.
- **Near-duplicate files**: `UserCard.tsx` and `UserCardNew.tsx`, `api.ts` and `api2.ts`, `service.old.php`.
- **Over-engineering in the wrong places**: factories and interfaces with a single implementation around trivial code, while core rules sit in handlers. AI tools tend to add ceremony where it is cheap to generate, not where it is needed.
- **Inconsistent naming and casing** of the same concept across layers (`client`, `customer`, `account` for one entity).
- **Defensive noise**: null checks and try/catch everywhere, a sign nobody knows the invariants.
- **Comments narrating the code** (`// loop through items`) and stale TODOs from the generation.
- **Giant files**: one 2,000-line component or controller that grew by appending.
- Why it matters: a codebase with no consistent pattern gives AI agents no example to follow, so every new prompt makes the inconsistency worse. This is also why the suite produces guardrails.

**Do not flag**: two styles that coexist because a migration toward one of them is under way and documented; naming that follows the domain's vocabulary even when it looks odd (`Folio`, `Lettrage`); comments explaining *why*.

## 11. Dead code

Unused exports, unreachable routes, files with zero fan-in that are not entry points (scan: `fan_in` 0 outside routes, pages, `main`, tests), commented-out blocks, feature flags always on. Dead code inflates every metric and misleads both humans and AI agents reading the repo.

**Do not flag**: files with zero fan-in that are entry points by convention (routes, pages, migrations, commands, DI registrations, test helpers, framework providers and middleware wired by configuration); public API of a library consumed by other repositories.

## 12. Design-level performance traps

Only when visible in the structure, not micro-optimisations: N+1 queries from lazy loading in loops, loading whole tables to filter in memory, synchronous external calls in request paths that could be deferred, chatty calls between services that are really one domain.

**Do not flag**: an N+1 on an admin page listing ten rows; synchronous calls in a background job.

## 13. Dependency hygiene

From the scan's "Dependency hygiene" section, confirmed in the code:
- **Several libraries for one job** (two date libraries, two HTTP clients, two validation libraries, two ORMs): one more thing to learn, configure and keep consistent; typical of prompt-by-prompt generation where each answer brought its own library.
- **Imported but not declared**: a package used by the code but missing from the manifest. Either a phantom dependency (works only because a sibling package or the monorepo root declares it, and breaks when that changes) or a hallucinated import (an AI suggested a package that was never installed, or does not exist). Check which before reporting; a hallucinated import of a non-existent package is also a supply-chain risk (someone can publish that name).
- **Declared but never imported**: dead weight and attack surface, but only after checking scripts, config files and CLIs, which the scan does not read.

**Do not flag**: a library and its official companion (an ORM and its CLI, a framework and its test utilities); a migration from one library to another that is documented and under way; type-only packages.

## 14. Knowledge concentration

From the scan's "Knowledge distribution" section (pseudonymised):
- **Knowledge islands in hotspots**: a busy, complex file written at 80%+ by one person. Changes queue behind that person; their absence stalls the area.
- **Code whose main authors are inactive**: nobody left knows why it is the way it is; refactoring it without characterisation tests is guesswork.
- **Modules owned by one person**: report as an organisational risk for the plan (pairing, documentation, tests) and for the pitch, never as an individual's performance, and never with names.

**Do not flag**: concentration in a repository with fewer than 3 authors (normal), or in stable code nobody needs to change.
