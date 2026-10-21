---
name: re-arch-guardrails
description: Generates the guardrails that keep a codebase in its chosen architecture - rules for AI coding agents (root and per-domain AGENTS.md, CLAUDE.md, Cursor rules), a project skill telling agents where new code goes, agent hooks that run the architecture check during the agent's own turn, fitness functions for CI with a frozen baseline (dependency-cruiser, deptrac, Pest arch, NetArchTest, ArchUnit, Spring Modulith, go-arch-lint, depguard, Cargo workspaces, cargo-deny, CMake targets, plus a language-agnostic checker), an ADR (MADR) and a review checklist. Use after choosing a target architecture, when AI agents keep putting code in the wrong place, to enforce layering or module boundaries, set up architecture tests, or frame vibe coding. Part of the re-arch suite.
---

# re-arch-guardrails

A refactoring that is not enforced erodes within months, faster with AI agents generating code from whatever examples they find. Guardrails make the target explicit for agents and humans, check it in the agent's own loop, and make it mechanical in CI.

## Inputs

`.re-arch/options.json` (`decision.chosen`), `.re-arch/domains.json`, `.re-arch/plan.json` (phases tell when each rule must reach zero), `.re-arch/findings.json` (each rule prevents a finding), `.re-arch/scan.json` (ecosystems, graph sources, current violations), `.re-arch/meta.json`. Retained option missing: ask, or take the recommended one and say so.

## What to produce

Use this tree so teams and the report always find the same thing:
```
.re-arch/guardrails/
  README.md                 where each file goes in the repo, in which order to adopt them
  AGENTS.md                 root rules (or AGENTS.section.md to merge into an existing file)
  domains/<domain>/AGENTS.md   only for domains whose target style differs from the root
  skills/<project>-architecture/SKILL.md
  hooks/                    agent hook configs (Claude Code settings snippet, others)
  checks/                   native tool configs (.dependency-cruiser.cjs, deptrac.yaml, ArchitectureTests.cs...)
  tools/re-arch/              check_architecture.py + scanner modules + architecture-rules.json + re-arch-baseline.json
  ci/                       CI job snippet
  adr/0001-target-architecture.md
  review-checklist.md
```
And `.re-arch/guardrails.json` listing rules and files (schema below).

### 1. Agent rules (AGENTS.md)

Based on `references/agent-rules.md`. Concrete and short: where each kind of code goes (a table: "HTTP entry point -> `src/app/api/<domain>/route.ts`, thin, calls the domain service"), what is forbidden (with the reason in one clause), naming, one reference implementation per pattern by file path (the cleanest existing example, or the one created in plan phase 1), and the command to run before finishing. Agents follow examples more than prose: point to files.

`AGENTS.md` at the repo root is read by most agents (Codex, Cursor, Copilot, Gemini, Claude Code through an `@AGENTS.md` line in `CLAUDE.md`). Nested `AGENTS.md` files apply to their folder and the closest one wins: when the options give a domain its own style (clean architecture for `orders`, plain layering elsewhere), put the domain-specific rules in `src/<domain>/AGENTS.md` instead of conditionals in the root file. If the repo already has these files, produce a section to merge, never a replacement.

### 2. Project skill

`skills/<project>-architecture/SKILL.md`, installed by the team in `.claude/skills/` (or the agent's equivalent) so any feature request triggers it: decision table for placing new code, step-by-step recipe for adding a use case in the target style, the checklist to run before proposing a change, links to the reference implementations. Description pushy enough to trigger on any feature work in the repo.

### 3. Fitness functions with a frozen baseline

For the detected ecosystems, from `references/fitness-functions.md`: native tool config and/or the generic checker. The generic checker works for every supported language and is the default for C/C++:
- copy `scripts/check_architecture.py`, `scan.py`, `precise.py`, `di.py`, `insights.py`, `ts_resolve.js`, `php_refs.php` into `tools/re-arch/`;
- write `architecture-rules.json` (schema at the top of the script). A file belongs to the **first** layer whose globs match (specific layers first); a layer **absent from `allow`** may import anything (list every layer, `[]` for "nothing outside itself"); `forbid_patterns` covers rules that are not imports (framework helpers like `auth()`, `request()`, `process.env`, static facades); `why` gives the reason shown to humans and agents, per layer or rule kind;
- **adopt with a frozen baseline, not with warnings**: `check_architecture.py architecture-rules.json --baseline-write re-arch-baseline.json` once, then CI runs `--baseline re-arch-baseline.json`. Existing violations are tolerated, every new one fails from day one, fixed ones leave the baseline with `--baseline-update` (it only shrinks). A warn-only period lets new debt pile up unnoticed. Native tools have the same mechanism (ArchUnit `FreezingArchRule`, deptrac baseline, dependency-cruiser `--ignore-known`): use it.

Test what you write:
- run the native tool if it can be installed in the session (some ship as standalone binaries or PHARs that run on a different runtime than the project's, such as deptrac's PHAR); if the package registry is blocked or the stack is too old, say so and use the fallbacks below; otherwise run the generic checker with equivalent rules and say in README.md and `guardrails.json` that the native config was not executed, with the command the team should run first;
- when rules target folders that do not exist yet (the plan creates them), running them on today's code proves nothing: build a throwaway fixture in the scratch area reproducing the target tree with one compliant and one violating file per rule, check that each rule fires, and note it;
- if the stack is too old for the native tools (they do not install on the framework or language version in use), write the native configs anyway, tie their activation to the plan phase that upgrades the stack, and enforce with the generic checker meanwhile.
Report the number of current violations per rule.

### 4. Agent hooks

CI catches violations after the push; a hook catches them in the agent's own turn, while it still has the context to fix them. For Claude Code, write `hooks/claude-settings.json` to merge into `.claude/settings.json`:
```json
{
  "hooks": {
    "Stop": [{"hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/re-arch/check_architecture.py\" \"$CLAUDE_PROJECT_DIR/tools/re-arch/architecture-rules.json\" --root \"$CLAUDE_PROJECT_DIR\" --baseline \"$CLAUDE_PROJECT_DIR/tools/re-arch/re-arch-baseline.json\" --changed-only --hook"}]}]
  }
}
```
`--hook` prints the violations in an agent-oriented format on stderr and exits 2, which sends Claude back to fix them; on a second Stop in a row (`stop_hook_active`) it reports without blocking, so the agent cannot loop. For large repositories where the scan takes more than a few seconds, keep it on `Stop` only (not `PostToolUse`). For other agents, check their current hook documentation; when unsure, put the same command in AGENTS.md as the last step before finishing, and say in README.md that it is an instruction, not an enforced hook.

### 5. CI job

The job that runs the checks with the baseline (GitHub Actions, GitLab CI or what the repo uses; follow existing CI config).

### 6. ADR (MADR 4)

`adr/0001-target-architecture.md` using `references/adr-template.md`: context, decision drivers (the quality scenarios of `options.json`), considered options (including rejected styles), decision outcome, consequences, and **Confirmation**: how compliance is checked, naming the rule ids of the fitness functions. Status `proposed` if `decision.by` is `assumed`, `accepted` if the team chose.

### 7. Review checklist

`review-checklist.md`: 8 to 12 questions for human code review in the target architecture, derived from the findings (each item prevents a finding from coming back), including how to review AI-generated changes.

### 8. Architecture docs

Copy `.re-arch/architecture.md` (Mermaid domain map and context view written by `re-arch-report`) to `docs/architecture.md` in the plan, so the diagram lives in the repository and is refreshed at each audit.

If `.re-arch/okf/` exists (or once `re-arch-report` has run), add to README.md the step "copy `.re-arch/okf/` to `docs/architecture/okf/`" and point to it from the root AGENTS.md ("architecture knowledge: `docs/architecture/okf/index.md`, start with `system.md` and the domain you are changing"): agents get the domain map, the rules with their reason and the intended oddities as small linked files instead of a long report. Re-copy it after each re-audit (its `log.md` carries the history). It is safe to commit: `to_okf.py` leaves out authors, the pitch and security findings.

## `.re-arch/guardrails.json`

```json
{
  "target": "O2",
  "adoption": "frozen baseline (re-arch-baseline.json), new violations fail from day one",
  "rules": [{"id": "R1", "rule": "Domain code never imports Prisma or Next.js", "prevents": ["F1"],   // same ids as plan.json rules_needed and the rules file "enforced_by": "dependency-cruiser rule domain-is-pure",
             "mode": "baseline, must reach 0 at end of P2", "current_violations": 14, "tested": "native tool run"}],
  "hooks": [{"agent": "Claude Code", "event": "Stop", "file": "guardrails/hooks/claude-settings.json"}],
  "files": [{"path": "guardrails/AGENTS.md", "purpose": "Architecture rules for AI coding agents"}]
}
```
`tested`: `native tool run`, `generic checker run`, `fixture only`, `not run` (say why).

## Principles

- **Rules derive from findings and the target**, not from a generic best-practice list. Each rule says which finding it prevents (`prevents`); a purely preventive rule protecting the target structure has `prevents: []` and a one-line reason.
- **Rules that are not about code** (configuration properties, profiles, CI settings, forbidden files) go in the CI job as small explicit checks (a grep, a config lint) next to the architecture check, listed in `guardrails.json` with `enforced_by: "ci step <name>"`.
- **Examples beat rules.** For agents and juniors alike, "do it like `src/modules/orders/pricing.ts`" works better than an abstract principle.
- **Explain the why in one clause** per rule (`why` in the rules file): agents and humans apply rules better when they know what they protect, and are less tempted to silence them.
- **Do not write rules the team cannot follow yet.** If the target structure does not exist yet, rules describe the target and say which phase creates it; meanwhile the rule for agents is "new code in domain X follows the target; do not extend the old pattern".
- **Native tools first** when the ecosystem has a well-known one (the team finds documentation and help), generic checker as fallback and for C/C++. Write configs for the tool versions visible in the repo (lock files, build files) and say which version you assumed.
- Never overwrite files in the repo. Everything goes to `.re-arch/guardrails/`, with instructions for where each file goes.

## When run alone

List the produced files with one line each, the number of current violations per rule, and the adoption order (baseline, CI job, hook, AGENTS.md).
