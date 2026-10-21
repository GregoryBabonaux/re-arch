---
name: re-arch-audit
description: Use this skill whenever someone questions the overall structure or health of an existing codebase and wants a verdict and a way forward, not a single code fix. This covers "is our repo/workspace/solution well structured?", layer or dependency leaks (domain code depending on the DB or framework), and projects, crates or modules nobody can untangle. It also covers an inherited legacy monolith or a vibe-coded/AI-generated app that is getting hard to change, rewrite vs incremental cleanup, tech debt assessment, refactoring roadmaps, and justifying the investment to a CTO, management or board. Also use it for team architecture rules and re-audits. Produces an evidence-based audit (domain map, weaknesses with file references, sized options from light fixes to modular monolith, hexagonal or CQRS, phased plan, management pitch, CI and AI guardrails, HTML report). JS/TS, PHP/Laravel/Symfony, .NET, Java/Kotlin, C/C++, Go, Rust. Not for one PR review, one-function refactor, security audit or cloud diagram.
---

# re-arch-audit (orchestrator)

This skill runs the re-arch suite in order. Each step is a separate skill so a team can also run one step alone (for example only `re-arch-pitch` once the plan is validated).

## Why the suite is built this way

- **Evidence before opinion.** A deterministic scan comes first, compiler-grade when the toolchain allows. Every weakness points to files and lines, and the diagnosis also shows what it chose not to flag: a finding without proof gets dismissed in the first review meeting.
- **No architecture by default.** Hexagonal is not the answer to everything. Options always include a light one, each target must be justified by signals in the code, and options are scored against the qualities the business cares about. The right target for a CRUD domain is often plain service/repository layering, and "keep the current architecture, fix these findings" is a legitimate outcome.
- **Cost is shown, not only benefit.** Each option is sized in understanding cost and implementation size (S, M, L, XL). The team's capacity to absorb concepts matters as much as the domain complexity.
- **Two audiences.** Tech teams get evidence, options and a verifiable plan. Management gets risks, options including "do nothing", investment as capacity ranges with their assumptions, and milestones.
- **The refactoring must stick.** Guardrails (agent rules, agent hooks, fitness functions with a frozen baseline) and training material keep the code from sliding back; re-audits measure progress.

## Workflow

All artifacts go to `.re-arch/` at the root of the audited repository (suggest adding it to `.gitignore` unless the team wants to version the audit; `authors-map.json` must never be versioned or shared). The data contract is in `references/contract.md`; read it once before starting.

Copy this checklist into your notes and tick it as you go:
```
- [ ] 1 Frame (meta.json, quality drivers, assumptions)
- [ ] 2 Scan (graph sources checked)
- [ ] 3 Domains (checkpoint: map validated or assumed)
- [ ] 4 Diagnose (validate.py clean)
- [ ] 5 Options (checkpoint: option chosen or assumed)
- [ ] 6 Plan (validate.py: coverage OK)
- [ ] 7 Pitch
- [ ] 8 Guardrails (rules tested)
- [ ] 9 Academy
- [ ] 10 Report (validate.py 0 error, check_render.py OK, screenshots looked at, OKF bundle 0 error)
- [ ] 11 Hand over
```

1. **Frame** (no skill): find out, from the conversation or by asking in one short message if the person is present:
   - scope (whole repo, a sub-folder, a service in a monorepo);
   - audience of the report (tech team, management, both: default both);
   - team context if known (size, seniority, AI-assisted coding or not, delivery pressure);
   - **2 or 3 quality drivers**: what the business needs most from this software in the next year (ship changes in X fast, never lose a payment, pass an audit, onboard developers quickly, swap a provider...). They become the quality scenarios the options are scored against;
   - whether build steps may run (`--allow-build` executes the project's build scripts: CMake configure, Maven/Gradle compile) and whether tools may be downloaded (`--fetch-tools`);
   - language of the deliverables (default: the language the person writes in).
   Write `.re-arch/meta.json`. If the person is not there to answer, take the defaults (no build steps, tools may be fetched, drivers inferred from the product and marked as assumed), list every default in `meta.assumptions` (the report shows them in its header), and carry on. Keep appending to `meta.assumptions` whenever a later step decides instead of the team.

2. **Scan**: run `re-arch-scan`. Read `.re-arch/scan-summary.md`, starting with "Graph sources". Query `scan.json` with short scripts for details.

3. **Domains**: run `re-arch-domains` -> `.re-arch/domains.json`. **Checkpoint**: if the person is present, show the map in a few lines and ask for corrections; every later step is organised per domain, and a wrong map spreads errors everywhere. If absent, `validated_by_team: false` and continue.

4. **Diagnose**: run `re-arch-diagnose` -> `.re-arch/findings.json`.

5. **Options**: run `re-arch-options` -> `.re-arch/options.json`. **Checkpoint**: present the options (one line each with both sizes and their fit with the quality scenarios) and ask which one the team retains. If nobody answers, take the recommended one with `decision.by: "assumed"`; the report says it awaits validation.

6. **Plan**: run `re-arch-plan` for the retained option -> `.re-arch/plan.json` + `plan.md`.

7. **Pitch**: run `re-arch-pitch` -> `.re-arch/pitch.json` + `pitch.md` (skip only if the person said management is not an audience).

8. **Guardrails**: run `re-arch-guardrails` -> `.re-arch/guardrails/` + `guardrails.json`.

9. **Academy**: run `re-arch-academy` -> `.re-arch/academy/` + `academy.json`.

10. **Report**: run `re-arch-report` -> `.re-arch/report.html` (+ `architecture.md` with Mermaid diagrams, + `okf/`: the audit as an Open Knowledge Format bundle for the repository's docs and for agents).

11. **Verify, then hand over.** Before saying anything is done, run and read the output of:
    - `python3 <re-arch-report-dir>/scripts/validate.py <repo>/.re-arch`: 0 error (fix the JSON, re-render);
    - `python3 <re-arch-report-dir>/scripts/check_render.py <repo>/.re-arch/report.html`: OK at 390px and 1280px, and look at the phone screenshots of the summary and the domain map.
    A claim of success needs fresh command output, not a recollection of an earlier run. Then deliver `report.html` as a file (with the session's file-sending tool if there is one; otherwise give its path). If the session can publish web pages, offer in one line to publish it, but do not publish without asking: the report contains code excerpts and possibly the location of secrets. In the message: the main weakness, the recommended or retained option with its two sizes, the size of the first phase, the decision requested from management if any, and the open questions for the maintainers. Do not recap the steps.

## Re-audit mode

When `.re-arch/` already holds an audit (the person asks for a follow-up, "where are we", "re-run the audit"):
1. `python3 <this-skill-dir>/scripts/diff_rearch.py snapshot <repo>/.re-arch` (copies the current audit to `.re-arch/history/<date>_<head>/`).
2. Re-run the steps. The diagnosis reads the previous `findings.json` and keeps the same id for persisting findings; the plan keeps phase ids and updates each phase `status` from the code and the exit criteria (verified, not assumed); options and pitch change only if the context changed (say so).
3. `python3 <this-skill-dir>/scripts/diff_rearch.py compare <repo>/.re-arch/history/<snapshot> <repo>/.re-arch` -> `diff.json` + `diff.md`: findings resolved, new, worse, better; metric trends; phase status. The report shows it at the top of the summary.
4. Re-export the OKF bundle (`to_okf.py`): `log.md` gains a dated entry from `diff.json` and keeps the previous ones.
5. Refresh the guardrails: shrink the baseline (`--baseline-update`), update reference implementations in AGENTS.md if new, better examples now exist.

## Modes

- **Quick diagnosis** (quick look requested, or tiny repo): steps 1 to 5 and 10, options without plan. Say that plan, pitch, guardrails and academy can follow.
- **Full audit** (default for an audit, a refactoring plan or a roadmap).
- **Single step**: run that skill alone; it reads what exists in `.re-arch/` and says what is missing.

## Small repositories

Below roughly 2,000 lines of production code, scale the deliverables to the code: 3 to 10 findings (grouped harder), 2 to 4 options, 2 to 4 phases, 2 to 4 academy modules, a one-page pitch. A full audit of a small app should be readable in fifteen minutes; volume is not rigor.

## Large repositories

Above roughly 2,000 source files or several services:
- scan each service or top-level package separately (`--out .re-arch/<service>`), then audit the service that matters most first, or the one the person names;
- if subagents are available, delegate per-domain reading to them (each gets the domain's file list, the smell catalog with its do-not-flag lists and the severity rubric), then merge findings yourself so severities stay consistent.

## Honesty rules for every step

- State what the scan cannot see; do not present heuristic signals as facts without opening the code.
- If the codebase is in good shape, say so. Recommending a big refactoring to justify the audit is the failure mode to avoid.
- No dramatisation. State facts, risks and consequences plainly.
- Say what could not be executed (tests that do not run on the available runtime, native tools that could not be installed, a bug read in the code but not reproduced) and keep the confidence of the affected findings accordingly.
- People are never findings: knowledge risks are pseudonymised and framed as organisational.
