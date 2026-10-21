# Ecosystem idioms

The patterns are language-agnostic; their idiomatic expression is not. Propose targets in the form the ecosystem's developers will recognise, and avoid importing ceremony from another culture (Java-style layers in Go, for instance).

## JavaScript / TypeScript

- **Next.js (App Router)**: route handlers and server actions are entry points only; put business code in `src/server/<domain>/` or `src/modules/<domain>/` (services, repositories), keep `app/` thin. Server components can call services directly; client components call server actions or API routes, never contain business rules. Data access through Prisma/Drizzle in repositories.
- **Express / Fastify / Hono**: routers -> controllers -> services -> repositories, organised by feature.
- **NestJS**: modules map naturally to domains; providers as services and repositories; the framework already pushes layering, so clean/hexagonal is reachable with custom providers for ports.
- **React SPA / Vue / Svelte**: feature folders or feature-sliced design; data fetching in hooks/services (TanStack Query), state per feature, business rules in pure functions or on the backend.
- **Monorepos (Nx, Turborepo, pnpm workspaces)**: packages per domain with explicit dependencies; Nx module boundary tags.
- Enforcement: dependency-cruiser, eslint-plugin-boundaries, Nx `enforce-module-boundaries`, madge for cycles.

## PHP

- **Laravel**: controllers thin, Form Requests for validation, Actions or Services for use cases, Eloquent models kept for persistence (or repositories in core domains), Jobs and Events for side effects. Modules per domain via `app/Domain/<Domain>` or packages (nwidart/laravel-modules, or plain namespaces). Pest arch tests are idiomatic for enforcement.
- **Symfony**: bundles are no longer recommended for app code; use `src/<Domain>/` with Domain/Application/Infrastructure subfolders for core domains; Messenger for commands and events; Doctrine entities can stay persistence models in non-core areas. deptrac for enforcement.
- **Legacy PHP without framework**: start with Composer PSR-4 autoload and moving SQL out of templates; layering before any pattern.
- Enforcement: deptrac, PHPArkitect, Pest `arch()` tests, PHPStan rules.

## .NET (C#)

- Projects are the natural boundary and the compiler enforces their references: `Api`, `Application`, `Domain`, `Infrastructure` for clean/onion; or one project per module for a modular monolith.
- Vertical slices with MediatR or plain handlers are very common and well understood; mix with a domain project for the core.
- EF Core `DbContext` is already a unit of work and repository: adding generic repositories on top is often useless ceremony; prefer query handlers using the context and repositories only for aggregates in core domains.
- Minimal APIs: endpoints as thin entry points, grouped per feature.
- Enforcement: project references, NetArchTest.Rules, ArchUnitNET.

## Java / Kotlin

- **Spring Boot**: package by feature with `controller`, `service`, `repository` inside, or hexagonal with `domain`, `application`, `adapter.in.web`, `adapter.out.persistence` (Tom Hombergs' layout is well known). Spring Modulith for modular monoliths (verifies module boundaries, events between modules).
- JPA entities in core domains: either accepted as domain model with discipline, or separate domain model mapped from JPA entities (costly, justify it).
- Kotlin: sealed classes for states, value classes for value objects, make impossible states unrepresentable cheaply.
- Enforcement: ArchUnit (layered architecture, slices free of cycles), Spring Modulith `verify()`, Gradle/Maven modules.

## C / C++

- Boundaries are libraries (CMake targets) with explicit `PUBLIC`/`PRIVATE` include directories and link dependencies; a domain library must not link UI, network or database libraries.
- Abstractions through pure virtual interfaces (or concepts/templates in modern C++) at the boundary with hardware, OS, network and storage; this is the hexagonal idea and is common in embedded and game code ("platform layer").
- Avoid deep inheritance hierarchies as the architecture; prefer composition and value types.
- Header hygiene matters architecturally: includes are the dependency graph; forward declarations and pimpl reduce coupling and build times.
- Enforcement: CMake target structure, include-what-you-use, clang-tidy, custom include rules in CI (the re-arch-guardrails generic checker works on includes).

## Go

- Package by feature or domain (`internal/orders`, `internal/billing`), not by technical type; no `models`/`controllers`/`services` packages holding everything.
- Interfaces are declared by the consumer, small, and only when there are several implementations or a test needs a fake: this gives hexagonal-style decoupling without upfront ports everywhere.
- `internal/` is enforced by the compiler and is the cheapest boundary tool available; `cmd/<app>` holds wiring (composition root).
- Package import cycles are compile errors, so layering problems show as giant packages rather than cycles: look for packages with very high LOC and fan-in.
- Enforcement: `internal/`, go-arch-lint, depguard (golangci-lint), `go list -deps` in CI.

## Rust

- Crates in a Cargo workspace are the strong boundary (no cycles between crates, dependencies explicit in each `Cargo.toml`): a `domain` crate with no I/O dependencies, adapter crates for persistence and HTTP, a binary crate for wiring.
- Traits as ports; generics or `dyn Trait` for adapters. Newtypes for value objects and enums for states make invalid states unrepresentable at no runtime cost.
- Inside a crate, module visibility (`pub(crate)`, private modules) carries boundaries.
- Enforcement: workspace crate structure (a forbidden dependency is simply absent from the crate's `Cargo.toml`), cargo-deny for banned crates, cargo-modules to inspect structure.
