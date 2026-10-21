# ADR template (MADR 4)

Fill from `options.json` and `guardrails.json`. Write in the team's working language. Keep it to one or two screens: the report holds the details.

```markdown
---
status: proposed            # proposed if decision.by = assumed, accepted if the team chose
date: YYYY-MM-DD
decision-makers: <roles, not names, unless the team wants names>
---

# 0001. Target architecture: <name of the retained option>

## Context and problem statement

<3-6 sentences: what the application is, what hurts (2-3 key findings with ids), why a decision is needed now.>

## Decision drivers

- <Q1 driver: scenario, from options.json quality_scenarios>
- <Q2 ...>
- <Team capacity: size, experience with the patterns>
- <Constraints: framework that stays, no feature freeze...>

## Considered options

1. <O1 name> (understanding <S>, implementation <M>)
2. <O2 name> (understanding <M>, implementation <L>)
3. <O3 name> ...
Also considered and rejected: <style: one-line reason>, <style: reason>.

## Decision outcome

Chosen option: "<O2 name>", because <2-3 sentences tying the choice to the drivers>.
Per domain: <domain: style>, <domain: style>.

### Consequences

- Good, because <...>
- Bad, because <cost, learning curve, more files in X>
- Neutral: <...>

### Confirmation

Compliance is checked by:
- <R1 rule: tool, where it runs (CI job, agent hook), baseline target phase>
- <R2 ...>
- Review checklist: `docs/architecture/review-checklist.md`.
This decision is revisited at the re-audit after phase <Pn>, or earlier if <condition>.

## Pros and cons of the options

### <O1 name>
- Good, because <...>
- Bad, because <...>
- Fit with drivers: Q1 <+/0/->, Q2 <...>

### <O2 name>
...
```
