---
name: re-arch-domains
description: Identifies the business domains of an existing application (bounded-context candidates) from its code, data model, routes, dependency-injection wiring and git history, and draws a domain map with dependencies, external systems (C4 context view), shared technical parts, fuzzy zones and a confidence level per domain. Use when someone wants to understand what an application is made of, visualise its functional areas, prepare a modular monolith or microservice split, organise a refactoring per domain, or as the domain-mapping step of an architecture audit. Works even when folder names mean nothing, as in vibe-coded apps. Part of the re-arch suite; needs .re-arch/scan.json from re-arch-scan.
---

# re-arch-domains

Goal: a map of the application's business areas that a developer and a manager can both read. It will not always lead to a clean architecture per domain; its first job is to make the application visible, and every later step (diagnosis, options, plan) is organised by it.

## Why several signals

Folder structure lies in vibe-coded apps: files land where the AI put them. Each signal sees something different:
- **imports**: the structure as written;
- **runtime (DI) edges**: what actually runs together when a container injects implementations;
- **git co-change** (grouped by ticket when commit messages carry one): the structure as maintained; files that always change together belong together, or share a duplicated rule;
- **data model**: entities and the files that use them, the most stable trace of the business;
- **routes and naming**: what the code says it is about (`/api/invoices`, `InvoiceService`).

No single signal is enough. A domain proposed by two or three of them is credible; one supported by only one is a hypothesis.

## Steps

1. **Cluster** (deterministic):
   ```bash
   python3 <this-skill-dir>/scripts/cluster.py <repo-root>/.re-arch [--resolution 1.0]
   ```
   Read `.re-arch/domains-candidates.md`. Too coarse (one cluster with most of the code): rerun with `--resolution 1.5`; too fragmented: `0.7`. Note the modularity: below about 0.3 the code has weak boundaries, which is itself a finding for the diagnosis.

   **Framework-convention layouts** (Laravel, Rails, Django, Symfony, Spring MVC with `controller/service/repository` packages, NestJS by layer): files are grouped by technical type and wired by the framework, so the import graph mostly shows layers and clusters come out mixed. There, use **routes and entities as the primary signal**: start from the "HTTP routes" section of the scan summary (or `scan.json` `routes`), group routes by resource, and attach to each group its controller, requests/validators, transformers/serializers, policies and models. Use the clusters only to confirm. Files reported as "used by 0 files" in such layouts (middleware, providers) are usually wired by the framework, not dead.

2. **Read the code to name and correct.** For each cluster, open its entry points (routes, controllers, pages, commands, handlers) and its main entities. Decide:
   - its business name, in the vocabulary the product uses (a page title, a route, a table name), not a technical one;
   - merges (two clusters that are one domain split by a technical seam, such as API and page of the same feature) and splits (one cluster mixing two business areas through a shared file);
   - its kind: `core` (what makes the product different, rules worth investing in), `supporting` (needed, specific, simpler), `generic` (auth, billing provider, email: buy or keep simple), `technical` (not a business domain: db client, logging, UI kit).
   The `kind` drives the options later: rich patterns are worth their cost in `core` domains much more than in `generic` ones.

3. **Dependencies between domains.** From cluster dependencies, runtime edges, cross co-change and shared entities, list who depends on whom and why, in one short note each ("orders reads user email to send the confirmation"). A dependency in both directions is worth flagging: it is often the first thing to break. Use `kind: runtime` for dependencies that exist only through the DI container.

4. **External systems.** From the scan's "External systems" section, keep the systems that matter to the business (database, payment, email, queues, identity, LLM APIs, third-party SaaS, hard-coded HTTP hosts) and attach each to the domains that use it. This becomes the C4 context view of the report. Merge duplicates (two database drivers are one database unless there really are two).

5. **Fuzzy zones.** List what does not fit cleanly: an entity used by four domains (`User` almost always), a rule computed in two domains, a "utils" file holding business logic, files with no link at all. These are often the most valuable findings; do not hide them to make the map look clean.

6. **Confidence.** Per domain: `high` when supported by structure, data and history; `medium` with two signals; `low` with one, or when inferred mostly from names. Give the reason in one line. Never present a low-confidence domain as established.

7. **Write `.re-arch/domains.json`** following the schema below.

8. **Validate with people.** If someone is in the conversation, show the map as a short list (name, kind, confidence, main dependencies) and ask for corrections before going on: the team knows its product better than the graph does. Record `validated_by_team: true` only when someone confirmed.

## Output: `.re-arch/domains.json`

```json
{
  "method": "imports + DI + co-change + data model + routes, clustered (modularity 0.42) then reviewed in the code",
  "validated_by_team": false,
  "domains": [
    {
      "id": "orders", "name": "Orders", "kind": "core",
      "description": "Cart validation, pricing, discounts, order creation, payment",
      "confidence": "high", "confidence_reason": "own entities, cohesive cluster, co-change inside",
      "files": ["src/app/api/orders/route.ts", "src/app/checkout/page.tsx"],
      "entities": ["Order", "OrderItem", "Coupon"], "loc": 120,
      "depends_on": [{"id": "users", "kind": "imports", "strength": 2, "note": "reads user email for the confirmation"}]
    }
  ],
  "external_systems": [{"name": "Stripe", "kind": "payment", "used_by": ["orders"]}],
  "shared": [{"path": "src/lib/db.ts", "role": "Prisma client used by every domain"}],
  "fuzzy_zones": [{"title": "Discount rules", "detail": "computed in the checkout page and in the orders API", "files": ["src/app/checkout/page.tsx", "src/app/api/orders/route.ts"]}]
}
```
`kind` in `core | supporting | generic | technical`; `depends_on.kind` in `imports | shared-entity | cochange | runtime`. Strings in the deliverable language (`.re-arch/meta.json` `lang`, else the person's language). List all files per domain (the report truncates for display). Run `python3 <re-arch-report-dir>/scripts/validate.py <repo>/.re-arch` after writing: it checks ids and that every listed file exists.

## When run alone

Also give the person the map in the conversation (one line per domain, then notable dependencies, external systems and fuzzy zones), and offer to render it with `re-arch-report`, which draws the domain map and the context view, and exports both as Mermaid in `.re-arch/architecture.md` for the repository's docs.
