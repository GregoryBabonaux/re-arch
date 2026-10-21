---
name: re-arch-pitch
description: Writes the management-facing case for a refactoring or architecture effort, without jargon - current risks tied to evidence, options including doing nothing, recommendation, investment in T-shirt sizes and team capacity with explicit assumptions, milestones, success indicators and the decision requested. Use when someone must convince a CTO, CEO, board, product management or a steering committee to fund technical-debt reduction or a refactoring, needs an executive summary of an architecture audit, or asks how to explain a refactoring to non-technical people. Part of the re-arch suite; reads .re-arch/findings.json, options.json and plan.json.
---

# re-arch-pitch

Management funds risk reduction and delivery capacity, not architecture. The pitch translates the audit into those terms, honestly enough to survive the first hard question in a steering committee.

## Inputs

`.re-arch/findings.json`, `.re-arch/options.json`, `.re-arch/plan.json` (sizes, phases), `.re-arch/domains.json`, `.re-arch/meta.json`. If the plan is missing, the pitch can still compare options, but say that the investment is indicative until the plan exists.

## What decision-makers need

1. **Headline**: the decision in one sentence ("Fund a three-phase restructuring of the ordering module, about a third of the team for one quarter, to stop pricing incidents and halve the cost of changes in that area").
2. **Situation**: what the application is, what works well (strengths from the diagnosis), what the problem is, in plain words. No layer, pattern or tool names.
3. **Risks**: the 3 to 5 that matter, each with its concrete consequence (incidents, delays, disputes, security exposure, dependency on one person, inability to ship a planned feature), its likelihood, and the finding id behind it so a technical reviewer can check. Business impact comes from `impact_business` in the findings. The share of fix commits and knowledge concentration (pseudonymised, never named) are usually the most convincing facts for non-technical readers: "half of the changes since launch were fixes", "two critical areas are understood by one person".
4. **Options**, always including **do nothing** with its real consequences (sometimes acceptable: say so when it is), and the light option. Per option: size, what it brings, what it risks.
5. **Recommendation** and why, in a few sentences.
6. **Investment**: the overall size first. Add a capacity hypothesis (share of the team over a number of sprints, always a range) because management needs one to decide; when the team has no calibration of its own, derive it from this reference only, so that runs stay consistent. Units are developer-sprints (one developer for one sprint) for every size:

| Size | Codebase of 5,000+ lines of production code | Smaller codebase |
|---|---|---|
| S | up to 0.5 | up to 0.25 |
| M | 1 to 2 | 0.25 to 0.5 |
| L | 3 to 6 | 1 to 2 |
| XL | split before estimating | split before estimating |

Sum the phases, divide by the capacity share to get calendar sprints, and write the derivation in the assumptions ("P0 M + P1 S + P2 L = 4 to 8.5 developer-sprints; one third of 3 developers = 1 developer-sprint per sprint; 4 to 9 sprints"). Derive it from the plan, not from intuition, and write the derivation in `investment.assumptions` so anyone can redo it: which phases are counted, their sizes, the team size and the share of capacity assumed. If the team has its own calibration (past velocity on similar work, the tech lead's reference for an M), use it and say so; otherwise say the range is an order of magnitude to calibrate. A T-shirt size is not a commitment: say that the tech lead calibrates it with the team before the decision. Never go below the sprint as a unit (no day counts) and never convert into money.
7. **Milestones**: what changes visibly after each phase, and the stop points (the effort can stop after phase N and still pay off).
8. **Success indicators**: a few measurable ones with baseline ("to measure" if unknown) and target. Prefer delivery and quality metrics management already understands: incidents and bugs in the area, lead time for changes, change failure rate, time to restore, onboarding time, time to ship a typical feature in the area.
9. **Decision requested**: exactly what is asked (capacity, priority over features, a review date).
10. **Glossary**: only for the few terms that could not be avoided.

## Tone

- Factual, no dramatisation, no alarm vocabulary. A risk is stated with its consequence and likelihood, not amplified.
- No blame on the people who wrote the code: vibe-coded or rushed code is usually a rational trade-off that served the business at the time. Use the findings' `debt_intent` to say it precisely: deliberate-prudent debt ("we shipped first, knowing the cost") is a normal business decision now coming due; inadvertent debt is what a team learns by building.
- Short. The whole pitch fits on two printed pages; the report gives the details for those who want them.
- Do not overpromise: refactoring reduces risk and cost of change, it does not make features free.

## Output

- `.re-arch/pitch.json` (rendered by `re-arch-report` in the management tab):
```json
{
  "headline": "...", "situation": "...",
  "risks": [{"risk": "...", "consequence": "...", "likelihood": "high", "evidence": "F1"}],
  "options": [{"name": "Do nothing", "size": "-", "gain": "...", "risk": "..."}, {"name": "...", "size": "L", "gain": "...", "risk": "..."}],
  "recommendation": "...",
  "investment": {"size": "L", "capacity": "about a third of the team over 3 to 4 sprints (hypothesis to calibrate)", "assumptions": ["..."]},
  "milestones": [{"when": "end of P1", "what": "...", "indicator": "..."}],
  "kpis": [{"name": "...", "baseline": "to measure", "target": "..."}],
  "decision_requested": "...",
  "glossary": [{"term": "...", "definition": "..."}]
}
```
- `.re-arch/pitch.md`: the same as a short memo to paste into an email or a slide, generated from the JSON (never by hand; re-run after any edit):
  ```bash
  python3 <this-skill-dir>/scripts/pitch_to_md.py <repo>/.re-arch
  ```

Strings in the deliverable language. Before finishing, re-read as a CFO who has never written code: every sentence should make sense to them.

## When run alone

Give the headline, the recommendation and the decision requested in the conversation, and the memo as `pitch.md`.
