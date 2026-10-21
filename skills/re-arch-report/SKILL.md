---
name: re-arch-report
description: Renders the results of an architecture audit (.re-arch/*.json from the re-arch suite) into one self-contained, responsive HTML report with a management summary, domain map diagram, findings with evidence, options compared by understanding cost and implementation size, phased refactoring plan, learning path and guardrails, then checks the rendering at phone and desktop widths, and exports the architecture knowledge as an Open Knowledge Format (OKF) bundle for the repository docs and coding agents. Use at the end of an architecture audit, whenever someone asks to see, share, print or re-render the audit report, or after editing any .re-arch JSON file. Part of the re-arch suite.
---

# re-arch-report

One HTML file the team can open on a phone in a meeting, send to management, or print to PDF. It renders whatever `.re-arch/*.json` files exist, so it also works after a partial run.

## Steps

1. **Validate the inputs.**
   ```bash
   python3 <this-skill-dir>/scripts/validate.py <repo>/.re-arch
   ```
   It checks the contract (enums, cross-file ids, evidence files and lines, plan coverage of critical/high findings and hotspots, a light option and a "do nothing" option present). Fix every error in the JSON (never in the renderer) and read the warnings.

2. **Render**:
   ```bash
   python3 <this-skill-dir>/scripts/render.py <repo>/.re-arch
   ```
   Output: `<repo>/.re-arch/report.html` and `<repo>/.re-arch/architecture.md` (domain map and context view as Mermaid, for the repository's docs), standard library only, no network needed to view it (no external fonts, scripts or images). Language of the labels comes from `meta.json` `lang` (`fr` or `en`; other languages fall back to English labels with your content strings unchanged, so tell the person if that happens).

3. **Check the rendering, do not assume it.**
   ```bash
   python3 <this-skill-dir>/scripts/check_render.py <repo>/.re-arch/report.html
   ```
   It visits every tab at 390px and 1280px, fails on horizontal scroll or overflowing elements, and writes screenshots to `.re-arch/screenshots/`. Look at the 390px screenshots of the summary and the domain map yourself (Read the PNG): text clipped in a domain box, unreadable labels or an empty section are content problems to fix in the JSON (shorter domain names, fewer words in a title). If Playwright is not available, say so and explain how to check by hand with browser device emulation.

4. **Export the knowledge bundle (OKF).**
   ```bash
   python3 <this-skill-dir>/scripts/to_okf.py <repo>/.re-arch
   ```
   Writes `<repo>/.re-arch/okf/`, an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) v0.2 bundle: Markdown concepts with YAML frontmatter that people, coding agents and knowledge catalogs read without tooling. One concept per domain (responsibility, entities, code, dependencies, target style, rules, known weaknesses), per external system, per architecture rule, plus the target decision, the roadmap, the system overview (including what looks wrong but is intended) and a `log.md` that keeps its history across re-audits. Trust is explicit: `generated.by: re-arch/<version>`, `status: draft` and no `verified` until the team validated the domain map (`validated_by_team`) or chose the option (`decision.by: team`); then `verified: human:<meta.reviewed_by or team>`. `stale_after` defaults to 120 days (`--stale-days`), 60 for the roadmap.
   The script leaves out what must not be committed: knowledge distribution, the pitch, security findings and open security phases (described generically), where secrets live, and masks secret-like strings; it ends with the spec section 11 conformance check (`to_okf.py --check <dir>` runs it alone). Read its last line: 0 error expected.

5. **Deliver** the HTML file. In the message: the main weakness, the recommended or retained option with its two sizes, the size of the first phase, and the decision requested from management if any. Mention that the report prints cleanly to PDF (all tabs expand when printing) and that the screenshots are available if they want to paste the domain map somewhere.

## What the report contains

| Tab | Source | Audience |
|---|---|---|
| Summary | progress since the previous audit (diff.json), pitch.json (or a minimal summary), key figures from scan | management first, everyone |
| Domains | domains.json: domain map and C4 context view (separate layouts for desktop and phone), cards, fuzzy zones, shared parts | everyone |
| Diagnosis | findings.json: strengths, findings filterable by severity with fix size, evidence, impacts, non-findings, open questions | tech |
| Options | options.json: quality scenarios matrix, comparison with both sizes, retained or recommended option, prerequisites, rejected styles, opportunities | tech and decision-makers |
| Plan | plan.json: phases timeline, sizes with rationale, steps as checklists, exit criteria, rollback, stop points | tech leads |
| Upskilling | academy.json | team, managers |
| AI & CI guardrails | guardrails.json | tech |
| Appendix | scan.json: graph sources, build units, DI bindings, knowledge distribution (pseudonymised), dependency hygiene, routes, hotspots, modules, cycles, limits | tech |

Links between ids work across tabs (a risk links to its finding, a phase to the findings it fixes).

## Editing after review

People will comment ("rename this domain", "phase 2 is too big"). Edit the JSON file concerned, re-run `render.py` and `check_render.py`. Never hand-edit `report.html`: the next render overwrites it.
