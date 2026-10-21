---
name: re-arch-plan
description: Builds an executable, phased refactoring plan toward a chosen target architecture, sized in T-shirt sizes (S, M, L, XL) with explicit criteria, starting with a safety net of characterisation tests, migrating domain by domain with strangler fig, branch by abstraction and expand/contract; each phase shippable, reversible, with verifiable steps, exit gates and stop points, covering every critical and high finding. Use when someone needs a refactoring roadmap or technical-debt plan, a migration path to clean architecture, hexagonal, modular monolith or simpler layering, wants to refactor a vibe-coded app without breaking it, or as the planning step of an architecture audit. Part of the re-arch suite.
---

# re-arch-plan

A plan the team (or an AI agent) can start on Monday: small steps, each one delivering value and safe to stop after, each one checkable by a command rather than by trust. Big-bang rewrites of working software fail far more often than incremental refactoring; the plan makes the incremental path concrete.

## Inputs

`.re-arch/options.json` (use `decision.chosen`; if absent, ask which option or take the recommended one and say so), `.re-arch/findings.json`, `.re-arch/domains.json`, `.re-arch/scan.json` (hotspots, churn, cycles, knowledge), `.re-arch/meta.json`. In re-audit mode, the previous `plan.json`: keep phase ids, update `status`.

## T-shirt sizes

No estimates in days: a size with its criterion is discussable, a day count produced without knowing the team is not.

| Size | Criteria |
|---|---|
| S | one module touched, covered by tests, no contract change |
| M | several modules of one domain, internal contracts change |
| L | several domains, new abstractions introduced, safety net to build first |
| XL | data model change or global style change |

Every phase gets a size **and the criterion that justifies it** (`size_rationale`). An XL phase is a signal to split: split it until each piece is L or smaller, or keep it XL only with an explicit note that it must be split before starting.

## Principles

1. **The safety net comes first.** Characterisation tests (golden master) on the flows the refactoring will touch, starting with core domains and hotspots: capture current behaviour, including its oddities, so refactoring cannot change it silently. Plus CI running them. Only quick security fixes may come before it (a leaked secret to rotate). Skip parts already well covered, and say so.
2. **Quick wins early.** Critical or high findings with `fix_size` S go in the first phases: they reduce risk now and build trust in the effort.
3. **Domain by domain, ordered by value.** Order by: severity of findings in the domain, hotspot score, business importance (`core` first), knowledge risk (a hotspot only one inactive person understood needs its tests first), and dependencies (break cycles before extracting). Explain the order in `sequencing_rationale`.
4. **Incremental techniques** (when to use each in `references/techniques.md`): strangler fig, branch by abstraction, parallel change (expand/contract), seams, Mikado method for tangled dependencies, feature toggles, expand/contract migrations for the database.
5. **Each phase is shippable and reversible.** Production keeps working at the end of every phase. State the rollback (revert the PRs, toggle off, keep the old path until the exit criteria hold).
6. **Refactoring alongside delivery.** Assume features keep shipping: phases interleave with feature work (a capacity share, or the boy-scout rule in the domain being worked on). Adapt if the team context says otherwise.
7. **Guardrails as you go.** As soon as a boundary exists, its fitness function enters CI with a frozen baseline (existing violations tolerated, new ones fail; see `re-arch-guardrails`). The plan says in which phase each rule's baseline must reach zero.
8. **Deletions are planned, not hoped for.** Old paths, duplicated copies, feature toggles and compatibility shims are removed in an explicit step (or a final cleanup phase). "We'll clean up later" is how a codebase ends with two versions of everything.
9. **Stop points.** Mark the phases after which the team can stop and still be better off.
10. **Coverage.** Every critical and high finding is in a phase or in `out_of_scope` with a reason; every top-5 hotspot is addressed or explicitly left alone. The validator checks this.

## Verifiable steps

A step is a ticket a developer or an agent can execute and prove done. Prefer the structured form:
```json
{"do": "Extract VAT computation from src/utils/utils.ts and src/app/invoices/new/page.tsx into src/server/invoicing/vat.ts (pure function computeTotal)",
 "moves": [{"from": "src/utils/utils.ts#computeTotal", "to": "src/server/invoicing/vat.ts#computeTotal"}],
 "verify": "! grep -rn 'vatRate / 100' src --include='*.ts*' | grep -v src/server/invoicing"}
```
- `verify` is a shell command that **exits 0 when the step is done**: a test command, the architecture checker with a rule id, or a negated search (`! grep -rq 'pattern' src`, since a grep that finds nothing exits 1). A step without a possible check is a smell: rewrite it.
- `moves` lists exact relocations so nobody (human or agent) copies instead of moving.
Plain strings stay accepted for steps that are not mechanically checkable (a workshop, a decision).

## Exit gates

Each phase's `exit_criteria` are verifiable, and always include, adapted to the phase:
- the characterisation and unit tests of the touched flows are green in CI;
- the architecture check passes with the baseline (`check_architecture.py --baseline`): no new violation; the phase's target rules at zero;
- every new abstraction has at least one caller in production code (no speculative interfaces);
- moved code is gone from its old location (moved, not copied); duplicated rules exist once;
- no new file above the size limit, no new cycle in the scan.
A phase is `done` only when these were run after the last change and passed: fresh command output, not a recollection. Agents executing the plan follow the same rule.

## Rule ids

Verify commands and exit gates often need architecture rules that `re-arch-guardrails` writes later. Reserve them here: list them in `plan.json` `rules_needed` (`[{"id": "R1", "rule": "domain code never imports Prisma", "by_phase": "P2"}]`) and reference the ids in steps and exit criteria. The guardrails step implements exactly these ids (and may add preventive ones).

## Starter kit

Phase 0 is easier to start when its first deliverable already exists. When the toolchain is available in the session, write in `.re-arch/starter/`:
- **characterisation tests** for the most critical flow (the top hotspot of a core domain), in the project's test framework, capturing today's behaviour including its oddities;
- optionally, the **extracted pure module** for the main duplicated or misplaced rule, with its unit tests, as a reference implementation for phase 1;
- optionally, a **reference slice**: one endpoint or use case rewritten end to end in the target style (entry point, application code, domain, persistence, tests), so the team and the agents have a concrete template before phase 1. Keep it small and in the project's conventions; AGENTS.md then points to it.
Run them against a scratch copy of the repository (never modify the repository itself) and record the result in `plan.json` `starter` (`{"files": [...], "command": "...", "result": "8 passed"}`). If dependencies cannot be installed, still write the tests and say they were not executed. Tests that fail on current behaviour are written down as known bugs, not "fixed" in the starter.

## Steps

1. Map the retained option to a target state per domain, and list what must be true at the end.
2. Draft phases following the principles: goal, size + rationale, domains, findings addressed, verifiable steps, exit criteria, rollback, risks, dependencies, stop point.
3. Re-read as the team lead who must run it: can each step be picked up as a ticket? Is any phase hiding an XL? Does the safety net come first? Are deletions scheduled?
4. Write `.re-arch/plan.json`, validate (`python3 <re-arch-report-dir>/scripts/validate.py <repo>/.re-arch`: coverage of critical/high findings and hotspots, ids, cycles in phase dependencies), fix errors, then generate the ticket-friendly `.re-arch/plan.md` (never by hand; re-run after any JSON edit):
   ```bash
   python3 <this-skill-dir>/scripts/plan_to_md.py <repo>/.re-arch
   ```

## Output: `.re-arch/plan.json`

```json
{
  "target": "O2",
  "sequencing_rationale": "...",
  "assumptions": ["features keep shipping, about a third of capacity on refactoring"],
  "out_of_scope": ["F12 (low): naming in the admin module, stable and rarely changed"],
  "phases": [
    {
      "id": "P0", "name": "Safety net and quick wins", "status": "not started",
      "goal": "...", "size": "M", "size_rationale": "one domain, no contract change, test harness to create",
      "domains": ["orders"], "findings": ["F5", "F9"], "depends_on": [],
      "steps": [
        {"do": "Rotate the Stripe key found in src/utils/format.ts and read it from env config", "verify": "! grep -rq 'sk_live_' src"},
        "Agree with the team which order flows the characterisation tests must cover"
      ],
      "exit_criteria": ["Characterisation tests cover POST /api/orders happy path and the 4 rejection cases, green in CI"],
      "rollback": "tests and config only",
      "risks": ["..."],
      "stop_point": false
    }
  ]
}
```
`status`: `not started | in progress | done | dropped` (updated in re-audits). Strings in the deliverable language.

## When run alone

Give the phase list in the conversation (id, name, size, one-line goal), the first phase's steps, and point to `plan.md` for the ticket-ready version.
