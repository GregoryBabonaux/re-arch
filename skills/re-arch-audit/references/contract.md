# .re-arch/ data contract

Every step writes its own file. The report renderer reads whatever exists and skips missing sections, so steps can run alone. `re-arch-report/scripts/validate.py` checks this contract (enums, cross-file ids, evidence files, plan coverage); run it after any step that writes JSON. Examples below are annotated with `//` comments for readability; the files themselves must be valid JSON. All human-readable strings use the deliverable language from `meta.json`. Ids are short, stable ASCII (`orders`, `F3`, `O2`, `P1`, `Q1`, `A2`, `R4`).

Enums:
- sizes: `S`, `M`, `L`, `XL`
- severity: `critical`, `high`, `medium`, `low`
- confidence: `high`, `medium`, `low`
- domain kind: `core`, `supporting`, `generic`, `technical`
- dependency kind: `imports`, `shared-entity`, `cochange`, `runtime`
- finding category: `layering`, `domain-logic`, `coupling`, `cycles`, `duplication`, `boundaries`, `data-model`, `testing`, `state`, `error-handling`, `config-security`, `consistency`, `dead-code`, `performance-design`, `dependencies`, `knowledge`, `compliance`
- debt intent: `deliberate-prudent`, `deliberate-reckless`, `inadvertent-prudent`, `inadvertent-reckless`
- style ids: `targeted`, `transaction-script`, `layered`, `feature-folders`, `vertical-slice`, `modular-monolith`, `clean`, `hexagonal`, `onion`, `rich-domain`, `cqrs`, `event-sourcing`, `domain-events`, `anti-corruption-layer`, `feature-sliced`, `microservices`
- scenario fit: `+`, `0`, `-`
- phase status: `not started`, `in progress`, `done`, `dropped`

```
.re-arch/
  meta.json                              orchestrator
  scan.json, scan-summary.md             re-arch-scan (script)
  authors-map.json, .gitignore           re-arch-scan (script) LOCAL ONLY, never shared
  domains-candidates.json/.md            re-arch-domains (script)
  domains.json                           re-arch-domains
  findings.json                          re-arch-diagnose
  options.json                           re-arch-options
  plan.json, plan.md                     re-arch-plan (plan.md generated)
  pitch.json, pitch.md                   re-arch-pitch (pitch.md generated)
  guardrails.json + guardrails/          re-arch-guardrails
  academy.json + academy/                re-arch-academy
  report.html, architecture.md, screenshots/   re-arch-report (scripts)
  okf/                                   re-arch-report (to_okf.py): OKF v0.2 bundle, generated, never edited by hand
  history/<date>_<head>/, diff.json, diff.md   re-arch-audit re-audit mode (script)
```

## meta.json
```json
{
  "project": "shopvibe", "date": "2026-10-19", "lang": "fr", "scope": "whole repository", "head": "af68dc6",
  "audience": ["tech", "management"],
  "team": "6 devs, mostly mid-level, heavy AI-assisted coding",
  "quality_drivers": ["Ship pricing changes in a day without regressions", "Never lose a paid order"],
  "build_steps_allowed": false, "tools_fetch_allowed": true,
  "mode": "full",                       // full | quick | single-step | re-audit
  "assumptions": ["Nobody available: deliverables in French, audience tech + management", "Option O2 retained by default"]
}
```

## domains.json
```json
{
  "method": "imports + DI + co-change + data model + routes, clustered then reviewed in the code",
  "validated_by_team": false,
  "domains": [
    {
      "id": "orders", "name": "Orders", "kind": "core",
      "description": "Cart validation, pricing, discounts, order creation and payment",
      "confidence": "high", "confidence_reason": "cohesive cluster, own entities, strong co-change inside",
      "files": ["src/app/api/orders/route.ts"], "entities": ["Order", "OrderItem", "Coupon"], "loc": 120,
      "depends_on": [{"id": "users", "kind": "imports", "strength": 2, "note": "reads user email to send confirmation"}]
    }
  ],
  "external_systems": [{"name": "Stripe", "kind": "payment", "used_by": ["orders"]}],
  "shared": [{"path": "src/lib/db.ts", "role": "Prisma client used by every domain"}],
  "fuzzy_zones": [{"title": "Discount rules", "detail": "computed both in checkout page and orders API", "files": ["..."]}]
}
```

## findings.json
```json
{
  "metrics": {"prod_loc": 9800, "test_ratio": 0.04, "module_cycles": 3, "mixed_files": 21, "modularity": 0.24, "fix_share": 0.5},
  "strengths": ["Consistent use of TypeScript strict mode"],
  "non_findings": [{"title": "Catalog uses plain data classes", "why": "CRUD domain without invariants: an anaemic model is right there", "files": ["src/catalog/product.ts"]}],
  "open_questions": ["Is the 5% bulk discount still a business rule?"],
  "findings": [
    {
      "id": "F1", "title": "Pricing rules live in the HTTP route and are duplicated in the UI",
      "category": "domain-logic", "severity": "high", "fix_size": "M", "debt_intent": "inadvertent-reckless",
      "domains": ["orders"],
      "evidence": [
        {"file": "src/app/api/orders/route.ts", "line": 21, "detail": "coupon cap and 5% bulk discount computed inline"},
        {"file": "src/app/checkout/page.tsx", "line": 9, "detail": "same rules re-implemented client side"}
      ],
      "impact_tech": "Any pricing change must be made twice; untestable without HTTP and a database",
      "impact_business": "Displayed total and charged total can diverge: disputes and refunds",
      "recommendation": "Extract a pure pricing module used by both sides, covered by unit tests"
    }
  ]
}
```
`evidence.file` may be a folder or namespace for structural findings (no `line` then). Persisting findings keep their id across re-audits.

## options.json
```json
{
  "context": {"domain_complexity": "...", "team": "...", "constraints": ["no feature freeze possible"]},
  "quality_scenarios": [{"id": "Q1", "driver": "Speed of change on pricing", "scenario": "A pricing rule change ships in one day, one module, with tests", "assumed": false}],
  "options": [
    {
      "id": "O1", "name": "Targeted refactoring, same structure", "styles": ["targeted"], "scope": "global", "per_domain": [],
      "summary": "...",
      "understanding_cost": "S", "understanding_detail": {"concepts": [], "indirections": "unchanged: route -> prisma (1 hop)"},
      "implementation_size": "S", "implementation_detail": "4 to 6 independent PRs",
      "scenario_fit": {"Q1": "0"}, "tradeoffs": "...",
      "benefits": ["..."], "drawbacks": ["..."],
      "signals": ["small codebase", "F1 and F4 fixable locally"],
      "addresses": ["F1", "F4"], "does_not_address": ["F2"],
      "recommended": false, "why": "..."
    }
  ],
  "prerequisites": [{"title": "Upgrade the framework to a supported version", "why": "...", "size": "L"}],
  "rejected": [{"style": "Event sourcing", "why": "no audit-trail or temporal-query need"}],
  "opportunities": [{"pattern": "Domain events", "where": "orders -> email", "signal": "F4"}],
  "decision": {"chosen": "O2", "by": "assumed", "note": "recommended option, awaiting validation"}
}
```
`decision.by`: `team` or `assumed`. Rules checked by the validator: 2 to 4 options, exactly one recommended, at least one light option, every option has `signals`.

## plan.json
```json
{
  "target": "O2",
  "sequencing_rationale": "Safety net first, then the domain with the most incidents and churn",
  "assumptions": ["team keeps ~30% capacity for refactoring"],
  "out_of_scope": ["F12 (low): admin naming, stable and rarely changed"],
  "rules_needed": [{"id": "R1", "rule": "domain code never imports Prisma", "by_phase": "P2"}],
  "starter": {"files": ["starter/orders.characterization.test.ts"], "command": "npx vitest run", "result": "8 passed"},
  "phases": [
    {
      "id": "P0", "name": "Safety net", "status": "not started",
      "goal": "Characterisation tests on the order flow so refactoring cannot change behaviour silently",
      "size": "M", "size_rationale": "one domain, no contract change, but the test harness must be created",
      "domains": ["orders"], "findings": ["F5"], "depends_on": [],
      "steps": [
        {"do": "...", "moves": [{"from": "a.ts#fn", "to": "b.ts#fn"}], "verify": "command that succeeds or prints nothing"},
        "plain string steps are accepted when nothing can be checked mechanically"
      ],
      "exit_criteria": ["..."], "rollback": "tests only, nothing to roll back", "risks": ["..."], "stop_point": false
    }
  ]
}
```
Validator: every critical/high finding is in a phase or in `out_of_scope` (by id) with a reason; top-5 hotspots addressed; no cycle in `depends_on`.

## pitch.json
```json
{
  "headline": "One sentence decision summary",
  "situation": "Short paragraph, no jargon",
  "risks": [{"risk": "...", "consequence": "...", "likelihood": "high", "evidence": ["F1", "F2"]}],   // one id or a list
  "options": [{"name": "Do nothing", "size": "-", "gain": "...", "risk": "..."}, {"name": "Option O2", "size": "L", "gain": "...", "risk": "..."}],
  "recommendation": "...",
  "investment": {"size": "L", "capacity": "a third of the team for 3 to 5 sprints (range to calibrate)", "assumptions": ["how the range was derived: phases counted, sizes, team size, capacity share"]},
  "milestones": [{"when": "end of phase P1", "what": "...", "indicator": "..."}],
  "kpis": [{"name": "Change failure rate on orders", "baseline": "to measure", "target": "halved"}],
  "decision_requested": "...",
  "glossary": [{"term": "Refactoring", "definition": "..."}]
}
```
Validator: a "do nothing" option exists; investment has assumptions.

## guardrails.json
```json
{
  "target": "O2",
  "adoption": "frozen baseline (re-arch-baseline.json), new violations fail from day one",
  "rules": [{"id": "R1", "rule": "Domain code never imports Prisma or Next.js", "prevents": ["F1"], "enforced_by": "dependency-cruiser rule domain-is-pure",
             "mode": "baseline, 0 at end of P2", "current_violations": 14, "tested": "native tool run"}],
  "hooks": [{"agent": "Claude Code", "event": "Stop", "file": "guardrails/hooks/claude-settings.json"}],
  "files": [{"path": "guardrails/AGENTS.md", "purpose": "Architecture rules for AI coding agents"}]
}
```

## academy.json
```json
{
  "modules": [
    {"id": "A1", "title": "Pulling business rules out of route handlers", "audience": "all developers", "level": "foundation", "duration": "30 min + 1h kata",
     "why_here": "F1, F3: pricing and stock rules live in HTTP handlers", "findings": ["F1", "F3"],
     "concepts": ["pure functions", "service layer", "characterisation test"], "file": "academy/01-business-rules-out-of-handlers.md"}
  ],
  "path": [{"step": 1, "modules": ["A1", "A2"], "when": "before phase P1"}],
  "reading": [{"title": "Working Effectively with Legacy Code", "author": "Michael Feathers", "why": "characterisation tests and seams"}]
}
```

## diff.json (re-audit, generated by diff_rearch.py)
Findings `resolved`, `new`, `regressed`, `improved`, `persisting`; `metrics` with before/after/trend; `phases` with status. Rendered at the top of the summary.

## okf/ (generated by to_okf.py, OKF v0.2)
Derived only from the files above; no extra input except optional `meta.reviewed_by` (a person's id for `verified: human:<id>`, default `team`).
Concept types: `Software System` (system.md), `Business Domain` (domains/<id>.md), `External System`, `Architecture Decision` (extension key `adr_status`), `Architecture Rule` (extension keys `rule_id`, `enforced_by`), `Refactoring Plan`, `Glossary`. Links are bundle-absolute (`/domains/orders.md`). Never exported: authors and knowledge distribution, pitch.json, findings of category `config-security` or whose title mentions secrets, evidence `detail` strings, clauses of free text that say where a secret lives; a plan phase that addresses a security finding and is not `done` is described generically, without its exit criteria. Secret-like values are masked.

