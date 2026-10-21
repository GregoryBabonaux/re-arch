---
name: re-arch-options
description: Proposes and compares 2 to 4 target architectures for an existing codebase, each sized by human understanding cost and implementation size (S, M, L, XL), scored against the business's quality scenarios, justified by signals in the code and possibly different per domain. Covers targeted refactoring, transaction script, layered service/repository, feature folders, vertical slices, modular monolith, clean/hexagonal/onion, rich domain model, CQRS, event sourcing, domain events, anti-corruption layers and feature-sliced design, with reasons for rejected styles. Never defaults to hexagonal. Use when choosing which architecture to move to, comparing clean vs hexagonal vs simpler options, deciding whether event sourcing or CQRS is worth it, or as the options step of an architecture audit. Part of the re-arch suite.
---

# re-arch-options

The goal is a decision, not a lecture. Each option says what it costs to understand, what it costs to build, what it fixes, what it does not fix, how it serves the qualities the business cares about, and which signals in this code justify it.

## Inputs

`.re-arch/findings.json`, `.re-arch/domains.json`, `.re-arch/scan-summary.md`, `.re-arch/meta.json` (team context, quality drivers). If findings are missing, run `re-arch-diagnose` first: options without a diagnosis are fashion.

## The two size axes

**Understanding cost**: what a developer must learn and keep in mind to work in the target.

| Size | Meaning |
|---|---|
| S | no new concept; the request path stays as short as today |
| M | 1 to 3 widely known concepts (service, repository, DTO, module facade); at most 3 hops from entry point to data |
| L | 4 to 6 concepts including dependency inversion (ports, adapters, use cases, aggregates); 4 to 5 hops; needs training and examples in the repo |
| XL | paradigm change with new failure modes (eventual consistency, projections rebuilt from events, sagas); needs sustained practice and at least one experienced person |

Give the concrete list of concepts and the hop chain (`controller -> use case -> port -> adapter -> ORM`).

**Implementation size**: effort to reach the target from today's code, same scale as the plan.

| Size | Criteria |
|---|---|
| S | one module touched, covered by tests, no contract change |
| M | several modules of one domain, internal contracts change |
| L | several domains, new abstractions, safety net to build first |
| XL | data model change or global style change; must be split before committing |

## Quality scenarios

Architecture choices trade qualities against each other. Make the trade explicit with 2 to 4 quality scenarios (ATAM / arc42 style), taken from `meta.json` `quality_drivers` when the person gave them, otherwise inferred from the product and the findings and marked as assumed:
- a scenario is concrete and testable: "A change to VAT rules ships in one day, touching one module, with tests", "A payment provider outage does not lose an order", "A new developer ships a feature in their first week";
- typical drivers: speed of change in the core domain, reliability of a critical flow, auditability, onboarding, swapping a provider, performance under load, cost to run.

Each option then rates each scenario `+` (helps), `0` (neutral) or `-` (hurts) in `scenario_fit`, and names its main trade-off in `tradeoffs`. This is what turns "which architecture is best" into "which one serves what matters here".

## Method

1. **Characterise the context** in three lines: domain complexity per domain (CRUD, workflow, rich rules), team (size, seniority, familiarity with the patterns, AI-assisted or not), constraints (no feature freeze, framework that stays, deadline).
2. **Read the style catalog** in `references/styles.md` (fit signals, anti-signals, concepts, costs) and `references/ecosystems.md` for the idiomatic form in the detected ecosystem (a Go or Laravel team does not express layering the way a Spring or .NET team does).
3. **Select 2 to 4 options** under these rules, which exist because the easy mistake is to recommend the most sophisticated style:
   - **Always include a light option**: "targeted refactoring in the current structure" or a simple layering, whichever fits. It is often the right answer for small apps, CRUD-heavy apps and junior teams.
   - **Every option cites the signals that justify it** (finding ids, scan facts, domain kinds). No signal, no option.
   - **Clean/hexagonal only when** there is a core domain with real rules worth isolating, or infrastructure that must be swappable or tested in isolation (several payment providers, a legacy system being replaced, offline mode). Clean, hexagonal and onion are one option, not three levels.
   - **CQRS / event sourcing only when** the code or the domain shows the need: audit trail or history as a business requirement, temporal queries, read and write models diverging strongly, high read/write asymmetry. Otherwise list them under `rejected`, or as an `opportunity` scoped to one place.
   - **Prefer per-domain targets when domains differ**: a core domain in clean architecture and the rest in plain layering usually beats one style everywhere. Use `per_domain`.
   - **Options must differ in outcome**, not be three intensities of the same style.
   - **A style the person asked about is always answered.** If they mention it ("a consultant told us to go hexagonal", "should we do microservices?"), either include it as an option with its honest signals and sizes, or put it in `rejected` with a direct verdict tied to the code. Never leave the question unanswered because no signal supported it.
4. **Check yourself against the rationalization table** below before keeping an option.
5. **For each option**, fill both sizes with their details, benefits, drawbacks (including the cost of the abstraction for a team new to it), `scenario_fit`, `tradeoffs`, the findings it addresses and the ones it does not.
6. **Recommend one** and say why in two or three sentences, weighing the team's capacity to absorb the concepts as much as the code and the quality scenarios. If the honest answer is "the light option", recommend it. If the codebase is healthy, "keep the current architecture and fix these findings" is a legitimate recommendation.
7. **Opportunities**: targeted patterns worth applying locally whatever the global choice (domain events to decouple notifications, an anti-corruption layer around a third-party API, a strategy for pricing rules, an outbox for reliable messaging).
8. **Prerequisites**: work every option needs (an unsupported framework or language version, a test suite that no longer runs, a broken CI). Put it in `prerequisites`, not inside each option.
9. **Rejected**: styles considered and not proposed, one line each. This answers "why not hexagonal / microservices / event sourcing?" before it is asked.
10. **Validate** with `python3 <re-arch-report-dir>/scripts/validate.py <repo>/.re-arch` (light option present, signals, ids, style ids), then the **decision checkpoint**: if someone is present, ask which option they retain; otherwise record the recommended one with `decision.by: "assumed"`.

## Rationalization table

Arguments that sound right and usually are not. If you catch yourself using one, check the counter-signal.

| Tempting argument | Check before keeping it |
|---|---|
| "The core domain deserves hexagonal" | Does the core domain have invariants that break today (findings), or is it CRUD with validation? Are there several adapters on either side? If not, a service layer with pure functions for the rules is enough. |
| "Event sourcing gives us history" | Is history a business requirement (audit, compliance, temporal queries) or a nice-to-have? An append-only audit table or domain events with an outbox give most of it at a fraction of the cost. |
| "Microservices will decouple the teams" | Is there more than one team? Are domain boundaries high-confidence? Can the organisation run distributed systems? A modular monolith gives the boundaries first. |
| "Clean architecture makes it testable" | Testability comes from pure business logic and seams; layers alone add mapping code. Would extracting the rules into pure functions give the same tests? |
| "Best practice says repositories everywhere" | With EF Core, Prisma or Eloquent, the ORM already is a repository. Add repositories where they protect an aggregate or a seam, not on every table. |
| "The team will learn it" | Who will review the first ten PRs in the new style? Without someone experienced, an L or XL understanding cost becomes a cargo cult. |
| "AI agents will write the boilerplate" | Agents copy what they see. More layers mean more places for agents to put code wrong; guardrails must exist before the style does. |

## Output: `.re-arch/options.json`

```json
{
  "context": {"domain_complexity": "...", "team": "...", "constraints": ["..."]},
  "quality_scenarios": [
    {"id": "Q1", "driver": "Speed of change on invoicing rules", "scenario": "A VAT rule change ships in one day, one module, with tests", "assumed": false}
  ],
  "options": [
    {
      "id": "O2", "name": "Layered everywhere, clean architecture for orders",
      "styles": ["layered", "clean"], "scope": "per-domain",
      "per_domain": [{"domain": "orders", "style": "clean"}, {"domain": "catalog", "style": "layered"}],
      "summary": "...",
      "understanding_cost": "M",
      "understanding_detail": {"concepts": ["service", "repository", "use case", "port (orders only)"], "indirections": "route -> service -> repository; orders: route -> use case -> port -> adapter"},
      "implementation_size": "L",
      "implementation_detail": "safety net on orders, then extraction domain by domain",
      "scenario_fit": {"Q1": "+"},
      "tradeoffs": "More files per feature in orders in exchange for rules testable without a database",
      "benefits": ["..."], "drawbacks": ["..."],
      "signals": ["F1", "F3", "orders is core with pricing and stock invariants"],
      "addresses": ["F1", "F2", "F3"], "does_not_address": ["F7"],
      "recommended": true, "why": "..."
    }
  ],
  "prerequisites": [{"title": "...", "why": "...", "size": "M"}],
  "rejected": [{"style": "Event sourcing", "why": "..."}],
  "opportunities": [{"pattern": "Domain events", "where": "orders -> notifications", "signal": "F4"}],
  "decision": {"chosen": "O2", "by": "assumed", "note": "recommended option, awaiting team validation"}
}
```
`styles` uses the ids listed at the top of `references/styles.md`. Strings in the deliverable language. Option ids are stable: the plan, pitch and guardrails refer to them.

## When run alone

Present the options as a compact comparison (name, understanding cost, implementation size, fit with the quality scenarios, what it fixes, main drawback), then the recommendation and the rejected styles in one line each, and ask which one to retain.
