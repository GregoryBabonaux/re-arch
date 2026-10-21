# Module template

~~~markdown
# A<n>. <Title stating the skill, e.g. "Pulling business rules out of route handlers">

Level: foundation | practitioner | advanced
Audience: <who>
Time: <read> + <practice>
Related findings: F1, F3
Needed before: phase P1

## The problem in our code
<2-4 sentences. What hurts, where, with a short excerpt (10-25 lines max) from the real file.>

`src/app/api/orders/route.ts`
```ts
<excerpt>
```

## The idea
<The concept in plain words, 1-3 short paragraphs. Why it exists: the problem it solves, in this codebase's terms.>

## Before / after
<The same code refactored in the target style, in the project's language and conventions. Show the new files with their paths. Explain each change in one line.>

## When not to use it
<Situations where the concept costs more than it brings, including in this repo.>

## Kata
Target: `<another real file with the same problem>`
1. <step>
2. <step>
Done when:
- [ ] <test or check that proves it, e.g. "unit tests on computeTotal cover the 4 discount cases">
- [ ] <architecture check passes>
Suggested format: <solo, pair, mob>, <duration>.

## In code review, ask
- <question>
- <question>
- <question>

## Go further
- <Reference, chapter>: <why this one>
~~~

Writing tips:
- Excerpts are short and trimmed to the point; never paste secrets from the repo (replace them with placeholders).
- The "after" must follow the guardrails (AGENTS.md rules, folder table) exactly, so that material and enforcement say the same thing.
- One module, one idea. If you need "and", split.
