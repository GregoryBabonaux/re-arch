#!/usr/bin/env python3
"""
validate.py: check an .re-arch/ audit before rendering or delivering it.

Errors (exit 1) break the contract or the suite's rules; warnings are worth a
look. Run it after every step that writes JSON; render.py runs it too.

Checks
  structure     every JSON file parses; enums (sizes, severities, confidence,
                kinds, categories, style ids, decision.by)
  references    ids used across files exist (domains, findings, options,
                phases, academy modules)
  evidence      cited files exist in the repository, cited lines are in range
  options       2-4 options, exactly one recommended, a light option present,
                every option justified by signals, clean/hexagonal/onion not
                split into separate options
  plan          every critical/high finding is scheduled or explicitly out of
                scope with a reason; top hotspots addressed; XL phases flagged;
                phase dependencies acyclic; a safety-net phase first
  diagnosis     non_findings present ("looks bad but is fine")
"""
import json
import os
import re
import sys

SIZES = {"S", "M", "L", "XL"}
SEVERITIES = {"critical", "high", "medium", "low"}
CONFIDENCE = {"high", "medium", "low"}
KINDS = {"core", "supporting", "generic", "technical"}
DEP_KINDS = {"imports", "shared-entity", "cochange", "runtime"}
CATEGORIES = {"layering", "domain-logic", "coupling", "cycles", "duplication", "boundaries", "data-model", "testing", "state",
              "error-handling", "config-security", "consistency", "dead-code", "performance-design", "dependencies", "knowledge", "compliance"}
STYLES = {"targeted", "transaction-script", "layered", "feature-folders", "vertical-slice", "modular-monolith", "clean", "hexagonal",
          "onion", "rich-domain", "cqrs", "event-sourcing", "domain-events", "anti-corruption-layer", "feature-sliced", "microservices", "current"}
LIGHT = {"targeted", "transaction-script", "layered", "feature-folders", "current"}
DEBT_INTENT = {"deliberate-prudent", "deliberate-reckless", "inadvertent-prudent", "inadvertent-reckless"}
PHASE_STATUS = {"not started", "in progress", "done", "dropped"}


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def load(d, name, r):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except ValueError as e:
        r.err(name, f"invalid JSON ({e})")
        return None


def enum(r, where, value, allowed, required=True):
    if value is None:
        if required:
            r.err(where, "missing value")
        return
    if value not in allowed:
        r.err(where, f"'{value}' not in {sorted(allowed)}")


def validate(archi):
    r = Report()
    repo = os.path.dirname(os.path.abspath(archi))
    data = {n: load(archi, f"{n}.json", r) for n in ("meta", "scan", "domains", "findings", "options", "plan", "pitch", "guardrails", "academy")}
    domains, findings, options, plan, pitch, academy = (data[k] for k in ("domains", "findings", "options", "plan", "pitch", "academy"))

    dom_ids = set()
    if domains:
        for i, d in enumerate(domains.get("domains", [])):
            w = f"domains.json domains[{i}] ({d.get('id')})"
            if not d.get("id"):
                r.err(w, "missing id")
            if d.get("id") in dom_ids:
                r.err(w, "duplicate id")
            dom_ids.add(d.get("id"))
            enum(r, w + ".kind", d.get("kind"), KINDS)
            enum(r, w + ".confidence", d.get("confidence"), CONFIDENCE)
            if d.get("confidence") == "low" and not d.get("confidence_reason"):
                r.warn(w, "low confidence without confidence_reason")
            for x in d.get("depends_on", []):
                enum(r, w + ".depends_on.kind", x.get("kind"), DEP_KINDS)
        for i, d in enumerate(domains.get("domains", [])):
            for x in d.get("depends_on", []):
                if x.get("id") not in dom_ids:
                    r.err(f"domains.json {d.get('id')}.depends_on", f"unknown domain '{x.get('id')}'")
            for f in d.get("files", [])[:400]:
                if not os.path.exists(os.path.join(repo, f)):
                    r.err(f"domains.json {d.get('id')}.files", f"'{f}' does not exist")

    fid = {}
    if findings:
        fs = findings.get("findings", [])
        for i, f in enumerate(fs):
            w = f"findings.json {f.get('id') or i}"
            if not f.get("id"):
                r.err(w, "missing id")
            fid[f.get("id")] = f
            enum(r, w + ".severity", f.get("severity"), SEVERITIES)
            enum(r, w + ".category", f.get("category"), CATEGORIES)
            enum(r, w + ".fix_size", f.get("fix_size"), SIZES, required=False)
            enum(r, w + ".debt_intent", f.get("debt_intent"), DEBT_INTENT, required=False)
            if not f.get("evidence"):
                r.err(w, "no evidence")
            for k in ("impact_tech", "impact_business", "recommendation"):
                if not f.get(k):
                    r.err(w, f"missing {k}")
            for d in f.get("domains", []):
                if dom_ids and d not in dom_ids:
                    r.err(w + ".domains", f"unknown domain '{d}'")
            for e in f.get("evidence", []):
                path = e.get("file")
                if not path:
                    r.err(w, "evidence without file")
                    continue
                full = os.path.join(repo, path)
                if not os.path.exists(full):
                    r.err(w, f"evidence file '{path}' does not exist")
                elif e.get("line") and os.path.isfile(full):
                    try:
                        n = sum(1 for _ in open(full, encoding="utf-8", errors="replace"))
                    except OSError:
                        n = None
                    if n is not None and int(e["line"]) > n:
                        r.err(w, f"evidence line {e['line']} beyond end of {path} ({n} lines)")
        if not findings.get("non_findings"):
            r.warn("findings.json", "no non_findings: list what looks bad but is fine, it is what makes the diagnosis credible to the team")
        if not findings.get("strengths"):
            r.warn("findings.json", "no strengths listed")
        if len(fs) > 30:
            r.warn("findings.json", f"{len(fs)} findings: are instances grouped?")

    opt_ids = set()
    if options:
        ops = options.get("options", [])
        if not 2 <= len(ops) <= 4:
            r.err("options.json", f"{len(ops)} options (expected 2 to 4)")
        recs = [o for o in ops if o.get("recommended")]
        if len(recs) != 1:
            r.err("options.json", f"{len(recs)} recommended options (expected exactly 1)")
        light = False
        style_sets = []
        for o in ops:
            w = f"options.json {o.get('id')}"
            opt_ids.add(o.get("id"))
            enum(r, w + ".understanding_cost", o.get("understanding_cost"), SIZES)
            enum(r, w + ".implementation_size", o.get("implementation_size"), SIZES)
            for s in o.get("styles", []):
                enum(r, w + ".styles", s, STYLES)
            if set(o.get("styles", [])) & LIGHT or o.get("understanding_cost") == "S":
                light = True
            if not o.get("signals"):
                r.err(w, "no signals: every option must be justified by evidence from the code")
            for x in o.get("addresses", []) + o.get("does_not_address", []):
                if fid and x not in fid:
                    r.err(w, f"unknown finding '{x}'")
            for pd in o.get("per_domain", []):
                if dom_ids and pd.get("domain") not in dom_ids:
                    r.err(w + ".per_domain", f"unknown domain '{pd.get('domain')}'")
            style_sets.append(set(o.get("styles", [])))
        if ops and not light:
            r.err("options.json", "no light option (targeted refactoring or simple layering): the suite always puts one on the table")
        splits = [s for s in style_sets if s & {"clean", "hexagonal", "onion"} and not s - {"clean", "hexagonal", "onion", "rich-domain", "domain-events"}]
        if len(splits) >= 2:
            r.warn("options.json", "clean, hexagonal and onion appear as separate options: they are one option with different vocabularies")
        dec = options.get("decision") or {}
        if dec:
            enum(r, "options.json decision.by", dec.get("by"), {"team", "assumed"})
            if dec.get("chosen") not in opt_ids:
                r.err("options.json decision.chosen", f"unknown option '{dec.get('chosen')}'")
        for q in options.get("quality_scenarios", []):
            if not q.get("id"):
                r.err("options.json quality_scenarios", "scenario without id")

    if plan:
        phases = plan.get("phases", [])
        pid = [p.get("id") for p in phases]
        if plan.get("target") and opt_ids and plan["target"] not in opt_ids:
            r.err("plan.json target", f"unknown option '{plan['target']}'")
        for p in phases:
            w = f"plan.json {p.get('id')}"
            enum(r, w + ".size", p.get("size"), SIZES)
            enum(r, w + ".status", p.get("status"), PHASE_STATUS, required=False)
            if not p.get("size_rationale"):
                r.err(w, "size without size_rationale")
            if p.get("size") == "XL" and "split" not in json.dumps(p).lower():
                r.warn(w, "XL phase: split it, or say explicitly that it must be split before starting")
            if not p.get("exit_criteria"):
                r.err(w, "no exit_criteria")
            if not p.get("rollback"):
                r.warn(w, "no rollback")
            for d in p.get("depends_on", []):
                if d not in pid:
                    r.err(w, f"depends on unknown phase '{d}'")
            for x in p.get("findings", []):
                if fid and x not in fid:
                    r.err(w, f"unknown finding '{x}'")
            for s in p.get("steps", []):
                if isinstance(s, dict) and not s.get("do"):
                    r.err(w, "structured step without 'do'")
        # dependencies acyclic
        graph = {p.get("id"): p.get("depends_on", []) for p in phases}
        state = {}

        def dfs(n):
            state[n] = 1
            for m in graph.get(n, []):
                if state.get(m) == 1:
                    return True
                if m not in state and dfs(m):
                    return True
            state[n] = 2
            return False

        if any(dfs(n) for n in graph if n not in state):
            r.err("plan.json", "cycle in phase dependencies")
        # coverage: every critical/high finding scheduled or explicitly out of scope
        scheduled = {x for p in phases for x in p.get("findings", [])}
        oos_text = json.dumps(plan.get("out_of_scope", []))
        for f in fid.values():
            if f.get("severity") in ("critical", "high") and f["id"] not in scheduled and f["id"] not in oos_text:
                r.err("plan.json", f"{f['id']} ({f['severity']}) is neither in a phase nor in out_of_scope with a reason")
        # top hotspots addressed
        scan = data["scan"]
        if scan:
            covered_files = {e.get("file") for x in scheduled if x in fid for e in fid[x].get("evidence", [])}
            text = json.dumps(phases) + oos_text
            for h in scan.get("hotspots", [])[:5]:
                if h["path"] not in covered_files and h["path"] not in text:
                    r.warn("plan.json", f"top hotspot {h['path']} is not addressed by any phase nor listed out of scope")
        t = (data["scan"] or {}).get("totals", {})
        well_tested = t.get("prod_loc") and t.get("test_loc", 0) / t["prod_loc"] >= 0.5
        if phases and not well_tested and not re.search(r"(?i)characteri|golden|safety net|filet|caract|test", json.dumps(phases[:2]) + plan.get("sequencing_rationale", "")):
            r.warn("plan.json", "no safety net (characterisation tests) in the first two phases, and the sequencing rationale does not explain why")

    if pitch:
        for x in pitch.get("risks", []):
            ev = x.get("evidence")
            evs = ev if isinstance(ev, list) else [e.strip() for e in str(ev or "").split(",") if e.strip()]
            for e in evs:
                if fid and e not in fid:
                    r.err("pitch.json risks", f"unknown finding '{e}'")
            enum(r, "pitch.json risks.likelihood", x.get("likelihood"), {"high", "medium", "low"})
        if not any(re.search(r"(?i)nothing|rien|statu quo|status quo", o.get("name", "")) for o in pitch.get("options", [])):
            r.err("pitch.json options", "no 'do nothing' option")
        inv = pitch.get("investment") or {}
        if inv and not inv.get("assumptions"):
            r.err("pitch.json investment", "no assumptions: write how the capacity range was derived")

    if academy:
        mids = {m.get("id") for m in academy.get("modules", [])}
        for m in academy.get("modules", []):
            for x in m.get("findings", []):
                if fid and x not in fid:
                    r.err(f"academy.json {m.get('id')}", f"unknown finding '{x}'")
            if m.get("file") and not os.path.exists(os.path.join(archi, m["file"])):
                r.err(f"academy.json {m.get('id')}", f"module file {m['file']} missing")
        for s in academy.get("path", []):
            for x in s.get("modules", []):
                if x not in mids:
                    r.err("academy.json path", f"unknown module '{x}'")
    return r


def main():
    archi = sys.argv[1] if len(sys.argv) > 1 else ".re-arch"
    r = validate(archi)
    for e in r.errors:
        print("ERROR   " + e)
    for w in r.warnings:
        print("warning " + w)
    print(f"{len(r.errors)} error(s), {len(r.warnings)} warning(s)")
    sys.exit(1 if r.errors else 0)


if __name__ == "__main__":
    main()
