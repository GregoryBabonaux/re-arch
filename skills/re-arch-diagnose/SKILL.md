---
name: re-arch-diagnose
description: Diagnoses the architectural weaknesses of an existing codebase with evidence (file and line) for every finding, rated by severity and fix size, explained in technical and business impact, with the strengths to keep and what looks bad but is fine. Covers layering, business logic in controllers or UI, coupling and cycles, duplicated rules, domain boundaries, data model, testability, state, error handling, configuration and secrets, dependency hygiene, knowledge concentration, and the tells of vibe-coded or AI-generated code. Use for architecture-level code reviews, technical debt assessments, "what is wrong with this codebase", before a refactoring plan, or as the diagnosis step of an architecture audit. Part of the re-arch suite; reads .re-arch/scan.json and domains.json.
---

# re-arch-diagnose

A finding is useful when a developer can open the file and see it, and a manager can understand why it costs money. Both halves are mandatory. A diagnosis is trusted when it also shows what it chose not to flag.

## Inputs

- `.re-arch/scan-summary.md` and `.re-arch/scan.json` (run `re-arch-scan` first if missing);
- `.re-arch/domains.json` if it exists: attach each finding to its domains;
- `.re-arch/meta.json`: deliverable language, team context, quality drivers;
- in re-audit mode, the previous `findings.json` (see `re-arch-audit`): keep the same id for a finding that persists, so progress can be tracked.

## Progress checklist

Copy it into your working notes and tick it as you go:
```
- [ ] Orient: README, docs, ADRs, CONTRIBUTING, existing AGENTS.md / CLAUDE.md read
- [ ] Graph sources checked (precise or regex per language)
- [ ] Git signals read (fix share, most fixed files, knowledge)
- [ ] Every scan candidate opened (mixed files, cycles, hotspots, duplicates, secrets, hygiene)
- [ ] Domain rules checked against the domain (regulations, market)
- [ ] Stack support status checked (sources cited)
- [ ] Production-readiness signals checked
- [ ] Hotspots and core domains read in depth
- [ ] Smell catalog walked, with its "do not flag" lists
- [ ] Instances grouped, severity and fix size rated
- [ ] Strengths and non-findings written
- [ ] findings.json validated (validate.py)
```

## Method

1. **Orient before judging.** Read the README, docs, ADRs and any existing agent instructions. A choice that looks odd may be a documented decision (a deliberate monolith, a vendored library, a performance trade-off). Judge it against its stated reason, and say so.
2. **Check how far to trust the graph.** The scan's "Graph sources" section says, per language, whether dependencies come from compiler-grade tools or regex. A cycle or a layer violation found only by regex must be confirmed in the code before it becomes a finding.
3. **Use the git signals.** The share of fix commits and the most-fixed files are the most concrete evidence of cost for both audiences: "half of the commits since launch are fixes, mostly on these three files" convinces faster than any metric. Knowledge islands in hotspots and code whose authors left are organisational risks; report them as such (category `knowledge`), with pseudonyms only.
4. **Start from the scan, then read the code.** Open every candidate (mixed-responsibility files, cycles, hotspots, duplicates, runtime DI edges crossing domains, dependency hygiene, secrets). Discard false positives.
5. **Check the domain rules against the domain.** Architecture problems often hide wrong business rules: duplicated rules that already diverged, rules that are simply wrong. When the domain is regulated or well codified (invoicing and VAT, accounting, payments and refunds, personal data and consent, health records, legal retention), compare what the code does with what the domain requires in the country and market the product serves, and report deviations (category `compliance`, or `domain-logic` when it is a plain business error). Do not invent regulations: state the rule you rely on, flag uncertainty, and put "to validate with an accountant / lawyer / DPO" in `open_questions`. Upcoming regulatory deadlines that the current model cannot meet are worth a finding: they turn a refactoring into a necessity.
6. **Check the support status of the stack.** For the framework, language runtime and main libraries in use (manifests, lock files), check whether the versions still receive security fixes. Use web search when available and cite the source (official release or support pages); otherwise say the dates are from memory and must be checked. An unsupported stack is often the real first phase, and the native fitness-function tools may not even install on it.
7. **Check production readiness signals** from the scan (secrets with hard-coded defaults, management endpoints exposed, demo data seeded in production profiles, debug mode, open CORS, no migration tool, endpoints without authentication or ownership checks). They are not architecture in the narrow sense, but an audit that misses them loses credibility; report them under `config-security`, and say when a full security audit is warranted.
8. **Read the hotspots and the core domains in depth**, even where the scan saw nothing: business logic placement, error handling, transactions, validation and test quality only show up when reading. Prioritise by hotspot score, then by domain `kind` (core first).
9. **Walk the smell catalog** in `references/smells.md`, including its **do not flag** lists. Use it as a checklist, not as a template to fill: report only what you actually found.
10. **Group instances into findings.** Twelve controllers calling the ORM directly is one finding with twelve pieces of evidence (cite the three or four most telling, give the count). The number of findings follows what you found, not the size of the repo: a typical app gives 8 to 20; more usually means instances are not grouped; fewer than 5 on a large app usually means not enough was read.
11. **Rate severity** with the rubric below, from consequences, not from distance to a textbook. **Rate the fix size** (S/M/L/XL, same scale as the plan): critical or high findings with an S fix are the quick wins of phase 0.
12. **Write the strengths and the non-findings.** Strengths: what is consistent, well tested or well modelled and must survive the refactoring. Non-findings: what a reviewer could flag but is fine here, and why (an anaemic model in a CRUD domain, a large but stable generated file, a duplicated block whose two copies change for different reasons, a framework file that looks unused). This section is required: it is what makes the team trust the rest, and it stops the next reviewer from "fixing" them.
13. **Validate**: `python3 <re-arch-report-dir>/scripts/validate.py <repo>/.re-arch`. It checks enums, ids, that every evidence file exists and every line is in range. Fix every error.

## Severity rubric

| Severity | Criteria |
|---|---|
| critical | causes or will cause incidents, data corruption, security exposure, or blocks any change in a core domain (a secret in the repo, payment logic with no transaction, a cycle across all core modules) |
| high | makes changes in a core or busy area slow and risky: business rules in handlers with no tests, duplicated rules that can diverge, a hotspot everybody touches, a core module only one (inactive) person knows |
| medium | real cost but localised, or in a supporting domain |
| low | consistency, naming, structure style; fix opportunistically |

Severity drops when the area is stable and rarely changed (low churn, low business value): ugly code nobody touches is not a priority. Say so when relevant.

## Writing each finding

- **title**: the problem in plain words, specific ("Pricing rules live in the HTTP route and are duplicated in the checkout page"), never generic ("Poor separation of concerns").
- **evidence**: file, line, one-line detail. For a structural finding, a folder or namespace is acceptable (omit the line). Never paste secrets; cite the location only.
- **impact_tech**: what it does to developers (cost of change, testability, onboarding, regressions).
- **impact_business**: what it does to the product or the company (incidents, delays, disputes, security, inability to ship). No dramatisation: the consequence and its likelihood.
- **recommendation**: the direction of the fix in one or two sentences, independent of the target architecture (the options step chooses the target).
- **fix_size**: S, M, L or XL.
- **debt_intent** (optional, when the history or docs make it clear): `deliberate-prudent` ("we ship now and know the cost"), `deliberate-reckless`, `inadvertent-prudent` ("now we know how we should have done it"), `inadvertent-reckless` (Fowler's quadrant). Vibe-coded code is usually inadvertent; code written under a known deadline is often deliberate-prudent. It helps the pitch explain debt without blame and helps decide what to leave alone.

## Output: `.re-arch/findings.json`

```json
{
  "metrics": {"prod_loc": 9800, "test_ratio": 0.04, "module_cycles": 3, "mixed_files": 21, "modularity": 0.24, "fix_share": 0.5},
  "strengths": ["Prisma schema is normalised and consistently named"],
  "non_findings": [
    {"title": "Catalog entities are plain data classes", "why": "catalog is CRUD with no invariant; an anaemic model is the right choice there", "files": ["src/catalog/product.ts"]}
  ],
  "open_questions": ["Is the 5% bulk discount still a business rule, or a leftover from a promotion?"],
  "findings": [
    {
      "id": "F1", "title": "...", "category": "domain-logic", "severity": "high", "fix_size": "M",
      "debt_intent": "inadvertent-reckless", "domains": ["orders"],
      "evidence": [{"file": "src/app/api/orders/route.ts", "line": 21, "detail": "..."}],
      "impact_tech": "...", "impact_business": "...", "recommendation": "..."
    }
  ]
}
```
Categories: `layering`, `domain-logic`, `coupling`, `cycles`, `duplication`, `boundaries`, `data-model`, `testing`, `state`, `error-handling`, `config-security`, `consistency`, `dead-code`, `performance-design`, `dependencies`, `knowledge`, `compliance`. Sort by severity, then by number of domains affected. `open_questions` collects what only the maintainers can answer; the report lists them. Strings in the deliverable language.

## When run alone

Also summarise in the conversation: the 3 to 5 findings that matter most (title, severity, fix size, one line of evidence), the main strength, the most useful non-finding, and the next step (choosing a target with `re-arch-options`).
