---
name: re-arch-academy
description: Produces training material to upskill a development team on the architecture and practices of a refactoring - a learning path ordered by the refactoring plan, modules anchored in the team's own code (before/after taken from their repository, katas extracted from real files, exercises, review checklists), curated references, for juniors and seniors. Use when a team must learn clean architecture, hexagonal, DDD, layering, testing legacy code or refactoring techniques, when a tech lead wants onboarding or workshop material about their codebase's target architecture, when developers who vibe-code need to learn craftsmanship basics, or as the training step of an architecture audit. Part of the re-arch suite; reads .re-arch/findings.json, options.json and plan.json.
---

# re-arch-academy

Generic tutorials on clean architecture are everywhere and change little in a team. What changes practice is material built on the team's own code: "here is our `route.ts`, here is why it hurts, here is the same code after, now you do the next one". That is the only kind of material this skill produces.

## Inputs

`.re-arch/findings.json` (what is wrong), `.re-arch/options.json` (retained target and its concepts), `.re-arch/plan.json` (when each concept is needed), `.re-arch/domains.json`, `.re-arch/guardrails.json` if present, `.re-arch/meta.json` (team seniority, language). Read the code files the modules will use as examples.

## Steps

1. **Derive the learning needs.** From the retained option's concepts (`understanding_detail.concepts`), the findings (each recurring finding is a missing habit) and the plan's techniques (characterisation tests, strangler fig...). Drop what the team visibly masters already (consistent use of a pattern in the code is evidence).
2. **Order them as a path aligned on the plan**: what must be understood before phase 0 (usually testing legacy code), before phase 1, and so on. Training that arrives after the phase it was needed for is wasted.
3. **Write one module per need** in `.re-arch/academy/NN-slug.md` using `references/module-template.md`. Each module:
   - starts from a finding and real code in the repo (file path and the relevant excerpt, short);
   - explains the concept in as few words as possible, with the reason it exists (what problem it solves here);
   - shows the before/after on that same code, compilable or close to it, in the project's language and framework;
   - gives a kata: another real place in the repo with the same problem, to refactor in pairs or alone, with acceptance criteria (tests to pass, rule to satisfy);
   - adds a review checklist (3 to 6 questions) so the habit carries into code review;
   - points to one or two references from `references/reading.md`, chapter-level when possible;
   - marks the level: `foundation` (every developer), `practitioner` (people who will lead refactoring phases), `advanced` (patterns used locally, such as event sourcing scoped to one domain).
4. **AI-assisted teams**: include a module on working with AI agents in the target architecture: how the project skill, AGENTS.md and the architecture hook frame the agent; how to review AI-generated changes against the rules (moved or copied? new abstraction with a caller? library already in use?); recognising the vibe-coding tells from the diagnosis (several libraries for one job, phantom or hallucinated dependencies, near-duplicate files). Developers who generate code need to be able to judge it.
5. **Workshop formats** (in `academy/README.md`): suggested sessions (duration, format: mob refactoring on a kata, code review dojo, lunch talk on the ADR), and who could animate them.
6. Write `.re-arch/academy.json` (index used by the report) and `.re-arch/academy/README.md` (path and how to use the material).

## How many modules

One module per recurring habit, not per finding: usually 3 to 5 modules for a small repository or team, 6 to 10 for a large one. Fewer, well-anchored modules beat a complete curriculum nobody follows.

## Quality bar

- Every module cites at least one real file of the repo. A module that could be pasted into any other project is not finished.
- Code in the project's language, framework and conventions, consistent with the guardrails.
- Short: a module is read in 15 to 30 minutes and practised in 1 to 2 hours.
- Honest about trade-offs: each pattern module says when not to use it (this prevents the "now everything is hexagonal" overcorrection).
- No condescension towards the code being refactored: it shipped the product.

## Output: `.re-arch/academy.json`

```json
{
  "modules": [
    {
      "id": "A1", "title": "...", "audience": "all developers", "level": "foundation", "duration": "30 min read + 1h kata",
      "why_here": "F1, F3: pricing and stock rules live in HTTP handlers", "findings": ["F1", "F3"],
      "concepts": ["pure function", "service layer"], "file": "academy/01-business-rules-out-of-handlers.md"
    }
  ],
  "path": [{"step": 1, "modules": ["A1", "A2"], "when": "before phase P0"}],
  "reading": [{"title": "Working Effectively with Legacy Code", "author": "Michael Feathers", "why": "characterisation tests and seams, needed for P0"}]
}
```
Strings in the deliverable language.

## When run alone

List the path (steps, modules, when) in the conversation and point to `academy/README.md`.
