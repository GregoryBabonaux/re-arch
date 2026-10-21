#!/usr/bin/env python3
"""
grade.py: deterministic grading of an re-arch eval run.

  python3 evals/grade.py <eval-id> <repo>/.re-arch [--out grading.json]

Writes grading.json in the skill-creator format: {"expectations": [{"text", "passed", "evidence"}]}.
Assertions that need human judgment (tone, quality of explanations) are left to the review viewer.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VALIDATE = os.path.join(ROOT, "skills", "re-arch-report", "scripts", "validate.py")
CHECK_RENDER = os.path.join(ROOT, "skills", "re-arch-report", "scripts", "check_render.py")
HEAVY = {"clean", "hexagonal", "onion"}


def load(archi, name):
    p = os.path.join(archi, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def cites(findings, *paths, severities=None):
    for f in findings.get("findings", []):
        if severities and f.get("severity") not in severities:
            continue
        files = {e.get("file") for e in f.get("evidence", [])}
        if all(any((x or "").startswith(p) for x in files) for p in paths):
            return f["id"]
    return None


def text_of(*objs):
    return json.dumps(objs, ensure_ascii=False).lower()


def grade(eval_id, archi):
    meta, findings, options, plan, pitch, guard, domains = (load(archi, n) for n in
        ("meta.json", "findings.json", "options.json", "plan.json", "pitch.json", "guardrails.json", "domains.json"))
    rec = next((o for o in options.get("options", []) if o.get("recommended")), {})
    chosen_heavy_everywhere = set(rec.get("styles", [])) & HEAVY and rec.get("scope") != "per-domain"
    res = []

    def check(aid, text, passed, evidence):
        res.append({"text": f"[{aid}] {text}", "passed": bool(passed), "evidence": evidence})

    v = subprocess.run([sys.executable, VALIDATE, archi], capture_output=True, text=True)
    check("valid", "validate.py reports 0 error", v.returncode == 0, v.stdout.strip().splitlines()[-1] if v.stdout else v.stderr[-300:])

    if eval_id == 1:
        check("lang", "meta.lang is fr", str(meta.get("lang", "")).startswith("fr"), meta.get("lang"))
        fid = cites(findings, "src/utils/utils.ts", severities={"critical", "high"})
        sec = [f["id"] for f in findings.get("findings", []) if f.get("category") == "config-security" or re.search(r"(?i)stripe|secret|clé|cle ", f.get("title", ""))]
        check("secret", "critical/high finding on the hard-coded Stripe key", fid and fid in sec, f"{fid} in {sec}")
        check("webhook", "finding cites the Stripe webhook route", cites(findings, "src/app/api/webhooks/stripe"), cites(findings, "src/app/api/webhooks/stripe"))
        check("vat-dup", "finding cites both utils.ts and invoices/new/page.tsx", cites(findings, "src/utils/utils.ts", "src/app/invoices/new/page.tsx"),
              cites(findings, "src/utils/utils.ts", "src/app/invoices/new/page.tsx"))
        t = text_of(findings)
        check("hygiene", "two date libraries or two API clients reported", ("moment" in t and "date-fns" in t) or ("api2" in t), "searched moment/date-fns/api2 in findings")
        light = any(set(o.get("styles", [])) & {"targeted", "layered", "feature-folders", "transaction-script", "current"} or o.get("understanding_cost") == "S" for o in options.get("options", []))
        check("light", "light option present and recommendation not heavy everywhere", light and not chosen_heavy_everywhere, f"recommended {rec.get('id')} styles {rec.get('styles')}")
        first = text_of(plan.get("phases", [])[:2])
        check("safety-net", "characterisation tests in the first two phases", re.search(r"caract|characteri|golden", first), "searched in P0-P1")
    if eval_id in (1,):
        names = text_of([o.get("name") for o in pitch.get("options", [])])
        check("do-nothing", "pitch has a do-nothing option", re.search(r"nothing|rien|statu quo|status quo", names), names[:200])
        check("non-findings", "at least one non_finding", len(findings.get("non_findings", [])) >= 1, len(findings.get("non_findings", [])))
    if eval_id == 2:
        check("no-hexa-reco", "recommended option has no clean/hexagonal/onion style", not (set(rec.get("styles", [])) & HEAVY), f"{rec.get('id')} {rec.get('styles')}")
        hexa = any(set(o.get("styles", [])) & HEAVY for o in options.get("options", [])) or re.search(r"hexagon", text_of(options.get("rejected", [])))
        check("hexa-addressed", "hexagonal discussed (option or rejected)", hexa, "")
        sev = [f["id"] for f in findings.get("findings", []) if f.get("severity") in ("critical", "high")]
        check("few-severe", "at most 2 critical/high findings", len(sev) <= 2, sev)
        check("strengths", "3+ strengths and 2+ non_findings", len(findings.get("strengths", [])) >= 3 and len(findings.get("non_findings", [])) >= 2,
              f"{len(findings.get('strengths', []))} strengths, {len(findings.get('non_findings', []))} non_findings")
        check("small-plan", "no XL phase", all(p.get("size") != "XL" for p in plan.get("phases", [])), [p.get("size") for p in plan.get("phases", [])])
    if eval_id == 3:
        ids = text_of([d.get("id") + " " + d.get("name", "") for d in domains.get("domains", [])])
        check("domains", "4+ domains incl. articles and comments", len(domains.get("domains", [])) >= 4 and "article" in ids and "comment" in ids, ids[:200])
        check("prereq", "upgrade listed as a prerequisite", re.search(r"upgrade|laravel|php", text_of(options.get("prerequisites", []))), text_of(options.get("prerequisites", []))[:200])
        check("no-hexa-reco", "recommended option not heavy everywhere", not chosen_heavy_everywhere, f"{rec.get('id')} {rec.get('styles')} {rec.get('scope')}")
        check("baseline", "guardrails adopt a baseline", "baseline" in text_of(guard), guard.get("adoption"))
    if eval_id in (1, 3):
        html = os.path.join(archi, "report.html")
        if os.path.exists(html):
            r = subprocess.run([sys.executable, CHECK_RENDER, html], capture_output=True, text=True)
            check("render", "check_render.py passes", r.returncode == 0, (r.stdout.strip().splitlines() or [""])[-1])
        else:
            check("render", "check_render.py passes", False, "report.html missing")
    return {"expectations": res, "summary": {"passed": sum(x["passed"] for x in res), "failed": sum(not x["passed"] for x in res), "total": len(res), "pass_rate": round(sum(x["passed"] for x in res) / max(1, len(res)), 3)}}


if __name__ == "__main__":
    eid, archi = int(sys.argv[1]), sys.argv[2]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(archi, "grading.json")
    g = grade(eid, archi)
    json.dump(g, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for e in g["expectations"]:
        print(("PASS " if e["passed"] else "FAIL ") + e["text"] + f"  ({e['evidence']})")
    print(f"{g['summary']['passed']}/{g['summary']['total']}")
