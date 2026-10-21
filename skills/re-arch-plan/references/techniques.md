# Incremental refactoring techniques

When to use each technique in a plan, and how to phrase the steps.

## Characterisation tests (golden master)
Michael Feathers. Tests that record what the code does today, not what it should do. Call the entry point with representative inputs, assert on the current outputs (response bodies, database state, emitted calls), including surprising ones.
- Use first, on every flow the plan will touch.
- How: high-level tests (HTTP or use-case level) beat unit tests here, because internals are about to move. Use a test database or containers (Testcontainers exists for Java, .NET, Go, Node, Rust...), fake external services at the boundary (payment, email).
- Steps phrasing: "Write characterisation tests for POST /orders: nominal, unknown product, insufficient stock, invalid coupon. Record current responses as expected values."
- Bugs discovered: keep the test asserting current behaviour, log the bug, fix it in a separate, visible change.

## Seams
Places where behaviour can be changed without editing the code there: a parameter instead of a global, an injected dependency instead of `new`, an interface around a static call. Create seams to make code testable before moving it.

## Strangler fig
Martin Fowler. Build the new structure next to the old, route traffic or calls to the new path piece by piece, delete the old path when nothing uses it.
- Use for replacing a module, a set of endpoints, or a legacy layer.
- Steps: introduce a routing point (facade, router, proxy); move one use case; verify; repeat; delete.

## Branch by abstraction
Introduce an abstraction in front of the code to replace, switch callers to the abstraction, build the new implementation behind it, switch, remove the old implementation. Everything on the main branch, no long-lived branch.
- Use for swapping a dependency (ORM, payment provider, HTTP client) or moving a responsibility out of a widely used component.

## Parallel change (expand / contract)
Change an interface in three steps: expand (add the new form alongside the old), migrate callers, contract (remove the old form). Each step ships separately.
- Use for any contract change used in several places, including APIs consumed by other teams.
- Database version: add new column or table, write to both, backfill, read from new, stop writing old, drop old. Never rename or drop in the same release as the code change.

## Mikado method
For tangled dependencies: try the change, note what breaks, revert, solve the prerequisites first (recursively), drawing the dependency graph of prerequisites. Produces a safe order for a change that looked impossible.
- Use for breaking module cycles and extracting a module out of a hub.

## Extract module / extract function
The basic moves. In a plan, name the target location and the public surface: "Extract pricing rules from route.ts and page.tsx into src/modules/orders/pricing.ts exposing computeTotal(items, coupon); both callers use it; unit tests on computeTotal."

## Breaking a cycle
Options, from cheapest: move the shared piece to a lower module both can depend on; invert one dependency with an interface owned by the lower module; replace a call with an event; merge the two modules if they are really one domain.

## Feature toggles
Switch between old and new behaviour at runtime, per environment or per user. Use when the new path changes observable behaviour and must be rolled out progressively. Remove the toggle (and the old path) as an explicit step; stale toggles are debt.

## Boy-scout rule and refactoring capacity
Leave each file a bit better when touching it for a feature. In a plan: "Any feature touching the orders domain after P1 follows the new structure; no new code in route handlers." Combined with a fixed capacity share for dedicated phases.

## Measuring progress
Re-run `re-arch-scan` at each phase end and compare: cycles, mixed-responsibility files, test ratio in the domain, hotspot scores. Delivery indicators (lead time, change failure rate, time to restore) give the management view.
