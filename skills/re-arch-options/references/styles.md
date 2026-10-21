# Architecture style catalog

For each style: what it is in one paragraph, fit signals, anti-signals, concepts a developer must hold, typical hop chain, understanding cost, typical implementation size from a messy codebase, and what usually goes wrong. Sizes are indicative; adjust them to the actual code.

Style ids for `options.json` (`styles` field): `targeted`, `transaction-script`, `layered`, `feature-folders`, `vertical-slice`, `modular-monolith`, `clean`, `hexagonal`, `onion`, `rich-domain`, `cqrs`, `event-sourcing`, `domain-events`, `anti-corruption-layer`, `feature-sliced`, `microservices`.

## Contents
- Targeted refactoring (no style change)
- Transaction script
- Layered: controller / service / repository
- Feature folders / package by feature
- Vertical slice architecture
- Modular monolith
- Clean architecture
- Hexagonal (ports and adapters)
- Onion architecture
- Rich domain model (DDD tactical patterns)
- CQRS
- Event sourcing
- Domain events and outbox
- Anti-corruption layer
- Feature-sliced design (frontends)
- Microservices (mostly as a rejected option)
- Choosing between clean, hexagonal and onion

---

## Targeted refactoring (no style change)

Keep the current structure. Fix the critical and high findings in place: extract the duplicated rule into one function, break the worst cycle, add the missing transaction, move secrets out, add tests on hotspots.
- Fit: small codebase, few domains, findings are local, team under delivery pressure, current structure is roughly consistent.
- Anti-signals: findings are systemic (no layering at all, every domain entangled), or the team keeps adding features in the worst areas.
- Concepts: none new. Hops: unchanged.
- Understanding: S. Implementation: S to M.
- Goes wrong when: used to avoid a necessary structural change; the debt comes back within months. Pair it with guardrails.

## Transaction script

One function per business operation, procedural, calling the database directly. Martin Fowler's pattern; honest and readable for simple operations.
- Fit: CRUD and simple workflows, small team, rules are few and local, generic or supporting domains.
- Anti-signals: the same rule appears in several scripts; operations share invariants.
- Concepts: one function per use case. Hops: entry point -> script -> DB (2).
- Understanding: S. Implementation: S to M (mostly moving code out of handlers into named operations).
- Goes wrong when: scripts grow and copy each other; then move the shared rules to a domain module.

## Layered: controller / service / repository

The classic three layers. Controllers handle transport, services hold business logic and transactions, repositories hold data access. Dependencies go down only.
- Fit: most business apps, CRUD-heavy domains with some rules, mixed-seniority teams, frameworks that already push this way (Spring, Laravel, NestJS, ASP.NET).
- Anti-signals: a core domain with many invariants (services become 2,000-line transaction scripts); need to swap infrastructure.
- Concepts: controller, service, repository, DTO. Hops: 3.
- Understanding: M (S if the framework already imposes it). Implementation: M to L depending on how mixed the code is.
- Goes wrong when: services call each other in a web of dependencies, repositories leak ORM types, "service" becomes a dumping ground. Organise by feature inside (see below) to avoid giant technical folders.

## Feature folders / package by feature

Group code by business feature (`orders/`, `invoices/`) rather than by technical type (`controllers/`, `services/`). Can be combined with any layering inside each feature.
- Fit: almost always as a complement; especially when the domain map is clear and technical folders have grown huge.
- Concepts: feature as the unit of organisation. Hops: unchanged.
- Understanding: S. Implementation: S to M (mostly moves, best done with IDE refactoring and import rewriting).
- Goes wrong when: features import each other's internals freely; add a public entry point per feature.

## Vertical slice architecture

Each request or use case is a self-contained slice (handler + validation + data access), minimal sharing between slices; often with a mediator (MediatR in .NET). Jimmy Bogard's formulation.
- Fit: many independent use cases, CRUD plus moderate rules, teams that want to add features without touching shared layers, .NET and PHP/Laravel teams already using handlers.
- Anti-signals: strong shared invariants across use cases (a rich core domain): slices duplicate rules. Combine with a domain model for the core.
- Concepts: slice, request/handler, optional mediator. Hops: 2 to 3.
- Understanding: M. Implementation: M.
- Goes wrong when: shared logic is copied between slices instead of extracted into a domain module.

## Modular monolith

One deployable, several modules aligned on domains, each with a public API and private internals, no direct access to other modules' tables. The step before (and often instead of) microservices.
- Fit: several clear domains (domain map with medium/high confidence), cross-domain coupling is the main pain, team is growing, talk of microservices is starting.
- Anti-signals: domain map unclear or low modularity (do the domain work first); tiny app.
- Concepts: module, public API, internal visibility, module-owned data, inter-module calls or events. Hops: +1 at module boundaries.
- Understanding: M. Implementation: L to XL (data ownership is the hard part).
- Enforcement: Spring Modulith, .NET projects per module, Go `internal/`, Rust crates in a workspace, Nx/dependency-cruiser boundaries in TS, deptrac in PHP.
- Goes wrong when: modules share tables "for now" forever; boundaries not enforced in CI.

## Clean architecture

Robert C. Martin. Concentric layers: entities (enterprise rules), use cases (application rules), interface adapters (controllers, presenters, gateways), frameworks and drivers. The dependency rule: source code dependencies point inward only.
- Fit: core domain with rules worth isolating from frameworks, long-lived product, need to test rules without infrastructure, framework migration expected.
- Anti-signals: CRUD domains (the ceremony costs more than it saves), junior team without a mentor, prototype stage.
- Concepts: entity, use case/interactor, input/output ports, gateway, presenter, dependency inversion, composition root. Hops: 4 to 5.
- Understanding: L. Implementation: L, XL if applied everywhere at once.
- Goes wrong when: applied to every CRUD screen (four files to save a field), use cases become pass-throughs, mapping between layers dominates the code. Apply to the core domain only.

## Hexagonal (ports and adapters)

Alistair Cockburn. The application core exposes ports (interfaces) on its driving side (used by UI, API, tests, CLI) and driven side (persistence, messaging, third parties); adapters implement them. Symmetric view: inside vs outside, no prescribed inner layers.
- Fit: several ways to drive the application (API, CLI, jobs, tests) or several infrastructures to plug (two payment providers, legacy and new database during a migration), strong need to test the core with fakes.
- Anti-signals: single entry point, single database, CRUD; the ports become boilerplate.
- Concepts: port (driving, driven), adapter, core, dependency inversion, composition root. Hops: 3 to 4.
- Understanding: L. Implementation: L.
- Goes wrong when: one port per table, interfaces with a single implementation everywhere "just in case", domain model still anaemic so the hexagon protects nothing.

## Onion architecture

Jeffrey Palermo. Domain model at the centre, domain services, application services, infrastructure and UI outside; dependencies inward. Very close to clean architecture.
- Same fit and costs as clean architecture. Use whichever vocabulary the team or ecosystem already knows (.NET teams often know onion/clean, Java teams hexagonal).

## Rich domain model (DDD tactical patterns)

Aggregates enforcing invariants, value objects, domain services, repositories per aggregate, domain events. Eric Evans, Vaughn Vernon.
- Fit: core domain with invariants that are currently broken or scattered (money, stock, states, eligibility), domain experts available, team willing to learn.
- Anti-signals: CRUD; rules are mostly validation; no access to domain knowledge.
- Concepts: aggregate, invariant, value object, entity identity, domain service, repository per aggregate, domain event, ubiquitous language. Hops: depends on the surrounding style.
- Understanding: L (XL for a team with no OO modelling background). Implementation: M per aggregate.
- Goes wrong when: aggregates too large (whole graph loaded for each change), DDD vocabulary applied to CRUD.

## CQRS

Separate the write model (commands, invariants) from the read model (queries, views optimised for display). Ranges from "different classes for reads and writes in the same database" (cheap) to separate stores updated asynchronously (expensive).
- Fit: reads and writes diverge strongly (complex dashboards over a transactional model), heavy read load, read models built from several domains.
- Anti-signals: simple screens mirroring tables; the split doubles the code for nothing.
- Concepts: command, query, read model, (async version) projection and eventual consistency. Hops: 2 to 3 for each side.
- Understanding: M for same-database CQRS, XL with async projections. Implementation: M to XL.
- Goes wrong when: adopted with async projections and an event bus where a SQL view would have done.

## Event sourcing

State is stored as the sequence of events that happened; current state is derived by replaying them; read models are projections.
- Fit (needs a real business reason, at least one): audit trail as a requirement (finance, compliance, regulated domains), temporal queries and "state as of date X", business is naturally event-shaped (ledgers, logistics tracking, workflows), need to rebuild new views from history.
- Anti-signals: the team has never run it in production; no requirement above; CRUD. It is hard to undo once adopted.
- Concepts: event, stream, aggregate rehydration, projection, snapshot, event versioning and upcasting, eventual consistency, idempotent handlers. Hops: high.
- Understanding: XL. Implementation: XL, usually scoped to one aggregate or domain, never a whole existing app at once.
- Lighter alternative to propose first: an append-only audit/history table, or domain events with an outbox, which give most of the traceability at a fraction of the cost.

## Domain events and outbox

A domain operation publishes an event ("OrderPlaced"); other parts react (email, analytics, stock). The outbox pattern stores events in the same transaction as the state change and publishes them afterwards, so no event is lost.
- Fit: side effects inline in business flows (email, webhooks, third-party calls), domains coupled only to notify each other.
- Concepts: event, handler, (outbox) relay. Understanding: M. Implementation: S to M per flow.
- Often the best "opportunity" to propose whatever the global target.

## Anti-corruption layer

A translation layer between your model and a third-party or legacy model, so their concepts and changes do not leak in.
- Fit: third-party payloads (Stripe, ERP, legacy DB) used directly across the code.
- Understanding: S to M. Implementation: S to M per integration.

## Feature-sliced design (frontends)

Frontend methodology: layers `app`, `pages`, `widgets`, `features`, `entities`, `shared`, with slices per business area and a public API per slice; imports only downward.
- Fit: React/Vue/Angular/Svelte apps where components fetch, compute and render everything, giant `components/` folder.
- Alternatives: simple feature folders plus a data layer (TanStack Query hooks, services) for smaller apps.
- Understanding: M. Implementation: M to L.
- For frontends, also consider moving business rules to the backend or a shared pure module rather than layering the UI heavily.

## Microservices

Mostly appears under `rejected`. Propose only if the domain map is clear with high confidence, domains have different scaling or deployment needs, teams are organised per domain, and the organisation can run distributed systems (observability, CI/CD per service, on-call). Otherwise: modular monolith first, extraction later if still needed.
- Understanding: XL (distributed failure modes). Implementation: XL.

## Choosing between clean, hexagonal and onion

They share the core idea (dependency inversion, business code free of frameworks) and cost about the same. Do not present them as levels of quality. Pick the vocabulary the team or ecosystem knows, or the one whose emphasis matches the need: hexagonal when the main need is many adapters on both sides, clean when the main need is layering use cases over entities, onion when the team comes from .NET literature. Proposing two of them as separate options is a mistake: they are one option.
