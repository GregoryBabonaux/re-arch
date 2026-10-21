#!/usr/bin/env python3
"""
to_okf.py: export an audit (.re-arch/*.json) as an Open Knowledge Format (OKF v0.2) bundle.

  python3 to_okf.py <repo>/.re-arch [--out <dir>] [--stale-days 120]
  python3 to_okf.py --check <bundle-dir>          # OKF v0.2 conformance check (spec section 11)

Writes <repo>/.re-arch/okf/ (regenerated each time, never edit by hand; log.md history is kept):
  index.md                          bundle root (okf_version: "0.2")
  system.md                         Software System: domains, context, target, intended oddities
  domains/<id>.md                   Business Domain: responsibility, entities, code, dependencies, rules, weaknesses
  external-systems/<slug>.md        External System
  decisions/0001-target-architecture.md   Architecture Decision (ADR content)
  rules/<id>.md                     Architecture Rule: why, how it is checked, checker definition
  plan/roadmap.md                   Refactoring Plan: phases with status and exit criteria
  glossary.md                       Glossary (if any)
  log.md                            history, newest first (re-audits from diff.json)

Deliberately left out: knowledge distribution and authors, the pitch (investment, risks for management),
security findings and their evidence details, secret-like strings (masked). The bundle is meant to be
committed to the audited repository (docs/architecture/okf/) and read by people and coding agents.
Standard library only.
"""
import datetime as dt
import json
import os
import re
import shutil
import sys

PRODUCER = "re-arch/1.0"
OKF_VERSION = "0.2"
SECURITY_CATEGORIES = {"config-security", "security"}
SECRET_RX = re.compile(r"(sk|pk|rk)_(live|test)_[A-Za-z0-9]{6,}|AKIA[0-9A-Z]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
                       r"gh[pousr]_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}")
SECRET_WORDS = re.compile(r"(?i)secret|password|passwd|credential|api[ _-]?key|token|mot de passe|clé|private key")

L = {
    "en": {"domains": "Domains", "external": "External systems", "target": "Target architecture", "drivers": "Quality drivers",
           "intended": "Looks wrong but is intended", "strengths": "Strengths to keep", "questions": "Open questions",
           "shared": "Shared code", "fuzzy": "Fuzzy zones", "responsibility": "Responsibility", "entities": "Entities", "code": "Code",
           "depends": "Depends on", "used_by": "Used by", "rules": "Rules", "weaknesses": "Known weaknesses", "target_style": "Target style",
           "kind": "Kind", "confidence": "Confidence", "context": "Context", "decision_drivers": "Decision drivers",
           "considered": "Considered options", "decision": "Decision", "rejected": "Styles considered and rejected",
           "consequences": "Consequences", "confirmation": "Confirmation", "prerequisites": "Prerequisites", "rule": "Rule",
           "why": "Why", "checked": "How it is checked", "definition": "Checker definition", "applies": "Applies to",
           "prevents": "Prevents", "phases": "Phases", "exit": "Done when", "order": "Order", "glossary": "Glossary",
           "status": "Status", "size": "size", "understanding": "understanding cost", "implementation": "implementation size",
           "covered": "addressed in", "more_files": "more files", "violations": "current violations", "mode": "mode",
           "reference": "Reference implementations", "domain_of": "domain", "phase": "phase",
           "root_concepts": "Concepts", "subdirs": "Subdirectories", "log_title": "Architecture knowledge log",
           "created": "Generated the bundle from the re-arch audit", "reaudit": "Re-audit", "resolved": "resolved", "new": "new",
           "worse": "worse", "better": "better", "phase_status": "phases", "proposed": "proposed (awaiting team validation)",
           "accepted": "accepted", "assumed_map": "Domain map not yet validated by the team.",
           "agents": "For coding agents: place new code according to the target style of its domain and the rules below; run the check before finishing.",
           "none": "none", "sec_phase": "Security fixes (details in the audit report, not in this bundle)."},
    "fr": {"domains": "Domaines", "external": "Systèmes externes", "target": "Architecture cible", "drivers": "Exigences qualité",
           "intended": "Paraît discutable mais est voulu", "strengths": "Points forts à conserver", "questions": "Questions ouvertes",
           "shared": "Code partagé", "fuzzy": "Zones floues", "responsibility": "Responsabilité", "entities": "Entités", "code": "Code",
           "depends": "Dépend de", "used_by": "Utilisé par", "rules": "Règles", "weaknesses": "Faiblesses connues", "target_style": "Style cible",
           "kind": "Nature", "confidence": "Confiance", "context": "Contexte", "decision_drivers": "Critères de décision",
           "considered": "Options étudiées", "decision": "Décision", "rejected": "Styles étudiés et écartés",
           "consequences": "Conséquences", "confirmation": "Vérification", "prerequisites": "Prérequis", "rule": "Règle",
           "why": "Pourquoi", "checked": "Comment c'est vérifié", "definition": "Définition pour le vérificateur", "applies": "S'applique à",
           "prevents": "Empêche", "phases": "Phases", "exit": "Terminé quand", "order": "Ordre", "glossary": "Glossaire",
           "status": "Statut", "size": "taille", "understanding": "coût de compréhension", "implementation": "taille de mise en œuvre",
           "covered": "traité en", "more_files": "autres fichiers", "violations": "violations actuelles", "mode": "mode",
           "reference": "Implémentations de référence", "domain_of": "domaine", "phase": "phase",
           "root_concepts": "Concepts", "subdirs": "Sous-répertoires", "log_title": "Journal de la connaissance d'architecture",
           "created": "Bundle généré à partir de l'audit re-arch", "reaudit": "Ré-audit", "resolved": "résolus", "new": "nouveaux",
           "worse": "aggravés", "better": "améliorés", "phase_status": "phases", "proposed": "proposée (en attente de validation par l'équipe)",
           "accepted": "acceptée", "assumed_map": "Carte des domaines pas encore validée par l'équipe.",
           "agents": "Pour les agents de code : placer le nouveau code selon le style cible de son domaine et les règles ci-dessous ; lancer la vérification avant de terminer.",
           "none": "aucun", "sec_phase": "Corrections de sécurité (détails dans le rapport d'audit, pas dans ce bundle)."},
}
STATUS_FR = {"not started": "à faire", "in progress": "en cours", "done": "terminée", "dropped": "abandonnée"}
TYPE_ORDER = ["Software System", "Business Domain", "External System", "Architecture Decision", "Architecture Rule", "Refactoring Plan", "Glossary"]


# ---------------------------------------------------------------- helpers
def load(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p, encoding="utf-8"))
    except (ValueError, OSError):
        return {}


masked = [0]
redacted = [0]


def clean(s):
    """Mask secret-like values in any text that goes to the bundle."""
    s = "" if s is None else str(s)
    def rep(m):
        masked[0] += 1
        return m.group(0)[:4] + "…(masked)"
    return SECRET_RX.sub(rep, s)


def q(v):
    """YAML scalar: JSON-style double-quoted strings are valid YAML 1.1 and 1.2."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(clean(v), ensure_ascii=False)


def frontmatter(fields):
    out = ["---"]
    for k, v in fields.items():
        if v is None or v == [] or v == "":
            continue
        if k in ("generated",) or (k == "verified" and isinstance(v, dict)):
            out.append(f"{k}: {{ by: {q(v['by'])}, at: {q(v['at'])} }}")
        elif k == "sources":
            out.append("sources:")
            for s in v:
                first = True
                for sk, sv in s.items():
                    out.append(("  - " if first else "    ") + f"{sk}: {q(sv)}")
                    first = False
        elif isinstance(v, list):
            out.append(f"{k}: [" + ", ".join(q(x) for x in v) + "]")
        else:
            out.append(f"{k}: {q(v)}")
    out.append("---")
    return "\n".join(out) + "\n"


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    return s or "item"


def iso(date, days=0):
    try:
        d = dt.date.fromisoformat(str(date)[:10])
    except ValueError:
        d = dt.date.today()
    return (dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc) + dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def sentence(s, limit=200):
    """OKF description: one sentence."""
    s = re.sub(r"\s+", " ", clean(s)).strip()
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    s = m.group(1) if m else s
    return s if len(s) <= limit else s[:limit - 1].rsplit(" ", 1)[0] + "…"


def bullets(items):
    return "\n".join(f"- {clean(x)}" for x in items if x) + "\n"


def redact(s):
    """Drop the clauses of a free-text string that point at secrets (where a key lives is itself sensitive)."""
    s = "" if s is None else str(s)
    if not SECRET_WORDS.search(s):
        return s
    parts = re.split(r"(?<=[,;.])\s+|\s+(?:et|and)\s+(?=(?:la|le|les|the|a|an|une|un)\b)", s)
    kept = [x for x in parts if not SECRET_WORDS.search(x)]
    redacted[0] += len(parts) - len(kept)
    return " ".join(kept).strip(" ,;") or "…"


def is_sensitive_finding(f):
    if f.get("category") in SECURITY_CATEGORIES:
        return True
    return bool(SECRET_WORDS.search(f.get("title", "") + " " + f.get("recommendation", "")))


# ---------------------------------------------------------------- export
def export(archi, out=None, stale_days=120):
    masked[0] = 0
    redacted[0] = 0
    out = out or os.path.join(archi, "okf")
    meta, domains, findings, options, plan, pitch, guard, diff = (load(archi, n) for n in (
        "meta.json", "domains.json", "findings.json", "options.json", "plan.json", "pitch.json", "guardrails.json", "diff.json"))
    scan_head = (load(archi, "scan.json") or {}).get("head") or meta.get("head")
    lang = "fr" if str(meta.get("lang", "en")).startswith("fr") else "en"
    t = L[lang]
    c = " : " if lang == "fr" else ": "
    date = meta.get("date") or dt.date.today().isoformat()
    generated = {"by": PRODUCER, "at": iso(date)}
    stale = iso(date, stale_days)
    project = meta.get("project") or os.path.basename(os.path.dirname(os.path.abspath(archi)))
    validated = bool(domains.get("validated_by_team"))
    decision = options.get("decision") or {}
    team_decided = decision.get("by") == "team"
    verifier = meta.get("reviewed_by")  # optional human id; falls back to the team
    human = {"by": "human:" + (verifier or "team"), "at": iso(date)}
    src_scan = {"id": "audit", "resource": f"re-arch audit of {project}" + (f" at commit {scan_head}" if scan_head else ""),
                "title": "re-arch audit (deterministic scan reviewed in the code)", "author": PRODUCER}

    old_log = ""
    if os.path.exists(os.path.join(out, "log.md")):
        old_log = open(os.path.join(out, "log.md"), encoding="utf-8").read()
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    files = {}

    def write(rel, fm, body):
        files[rel] = fm
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(frontmatter(fm) + "\n" + body.rstrip() + "\n")

    doms = domains.get("domains", [])
    dom_ids = {d["id"] for d in doms}
    all_findings = findings.get("findings", [])
    pub_findings = [f for f in all_findings if not is_sensitive_finding(f)]
    phase_of = {}
    for ph in plan.get("phases", []):
        for fid in ph.get("findings", []):
            phase_of.setdefault(fid, ph)
    rec = next((o for o in options.get("options", []) if o.get("id") == decision.get("chosen")), None) \
        or next((o for o in options.get("options", []) if o.get("recommended")), None) or {}
    per_domain = {p.get("domain"): p.get("style") for p in rec.get("per_domain", []) or []}
    ext = domains.get("external_systems", [])
    ext_slug = {e.get("name"): slug(e.get("name")) for e in ext}
    rules = guard.get("rules", [])
    finding_domains = {f["id"]: f.get("domains", []) for f in all_findings}
    rule_domains = {}
    for r in rules:
        ds = sorted({d for fid in r.get("prevents", []) for d in finding_domains.get(fid, []) if d in dom_ids})
        rule_domains[r["id"]] = ds
    checker_defs = {}
    rules_file = os.path.join(archi, "guardrails", "tools", "re-arch", "architecture-rules.json")
    if os.path.exists(rules_file):
        try:
            def walk(x, ctx=None):
                if isinstance(x, dict):
                    if isinstance(x.get("id"), str):
                        checker_defs.setdefault(x["id"], []).append({"in": ctx, **x} if ctx else x)
                    for k, v in x.items():
                        walk(v, k if isinstance(v, (list, dict)) else ctx)
                elif isinstance(x, list):
                    for v in x:
                        walk(v, ctx)
            walk(json.load(open(rules_file, encoding="utf-8")))
        except ValueError:
            pass
    dec_rel = "decisions/0001-target-architecture.md"
    has_decision = bool(options.get("options"))
    has_plan = bool(plan.get("phases"))

    def flink(fid):
        f = next((x for x in all_findings if x["id"] == fid), None)
        if not f or is_sensitive_finding(f):
            return None
        return f"{fid} {clean(f.get('title'))}"

    # ---- domains
    for d in doms:
        did = d["id"]
        body = []
        if not validated:
            body.append(f"> {t['assumed_map']}\n")
        body.append(f"# {t['responsibility']}\n\n{clean(redact(d.get('description', '')))}\n")
        body.append(f"- {t['kind']}{c}{d.get('kind', '')}\n- {t['confidence']}{c}{d.get('confidence', '')}"
                    + (f" ({clean(d['confidence_reason'])})" if d.get("confidence_reason") else "") + "\n")
        style = per_domain.get(did) or (", ".join(rec.get("styles", [])) if rec else "")
        if style and has_decision:
            body.append(f"# {t['target_style']}\n\n{clean(style)} ([{t['target']}](/{dec_rel}))\n")
        if d.get("entities"):
            body.append(f"# {t['entities']}\n\n" + bullets(f"`{e}`" for e in d["entities"]))
        fl = d.get("files", [])
        if fl:
            body.append(f"# {t['code']}\n\n" + bullets(f"`{x}`" for x in fl[:30])
                        + (f"- … {len(fl) - 30} {t['more_files']}\n" if len(fl) > 30 else ""))
        deps = [x for x in d.get("depends_on", []) if x.get("id") in dom_ids]
        if deps:
            body.append(f"# {t['depends']}\n\n" + bullets(
                f"[{next(o.get('name', o['id']) for o in doms if o['id'] == x['id'])}](/domains/{x['id']}.md) ({x.get('kind', '')})"
                + (f"{c}{x['note']}" if x.get("note") else "") for x in deps))
        users = [o for o in doms if any(x.get("id") == did for x in o.get("depends_on", []))]
        if users:
            body.append(f"# {t['used_by']}\n\n" + bullets(f"[{o.get('name', o['id'])}](/domains/{o['id']}.md)" for o in users))
        es = [e for e in ext if did in (e.get("used_by") or [])]
        if es:
            body.append(f"# {t['external']}\n\n" + bullets(f"[{e['name']}](/external-systems/{ext_slug[e['name']]}.md) ({e.get('kind', '')})" for e in es))
        rs = [r for r in rules if did in rule_domains.get(r["id"], [])]
        if rs:
            body.append(f"# {t['rules']}\n\n" + bullets(f"[{r['id']}](/rules/{slug(r['id'])}.md){c}{r.get('rule', '')}" for r in rs))
        ws = [f for f in pub_findings if did in f.get("domains", [])]
        if ws:
            lines = []
            for f in ws:
                ph = phase_of.get(f["id"])
                where = ", ".join(f"`{e.get('file')}" + (f":{e['line']}" if e.get("line") else "") + "`" for e in f.get("evidence", [])[:4])
                lines.append(f"**{f['id']}** {f.get('title', '')} ({f.get('severity', '')}, {t['size']} {f.get('fix_size', '?')})"
                             + (f" {where}" if where else "")
                             + (f"; {t['covered']} [{ph['id']}](/plan/roadmap.md)" if ph and has_plan else ""))
            body.append(f"# {t['weaknesses']}\n\n" + bullets(lines))
        fz = [z for z in domains.get("fuzzy_zones", []) if set(z.get("files", [])) & set(fl)]
        if fz:
            body.append(f"# {t['fuzzy']}\n\n" + bullets(f"**{z.get('title', '')}**{c}{redact(z.get('detail', ''))}" for z in fz))
        fm = {"type": "Business Domain", "title": d.get("name", did), "description": sentence(redact(d.get("description", ""))),
              "tags": [x for x in ["domain", d.get("kind")] if x], "status": "stable" if validated else "draft",
              "domain_kind": d.get("kind"), "generated": generated}
        if validated:
            fm["verified"] = human
        fm.update({"stale_after": stale, "sources": [src_scan]})
        write(f"domains/{did}.md", fm, "\n".join(body))

    # ---- external systems
    for e in ext:
        body = [f"# {t['used_by']}\n\n" + bullets(f"[{next((o.get('name', u) for o in doms if o['id'] == u), u)}](/domains/{u}.md)"
                                                  for u in e.get("used_by", []) if u in dom_ids)]
        write(f"external-systems/{ext_slug[e['name']]}.md",
              {"type": "External System", "title": e["name"], "description": f"{e.get('kind', '')}".strip(),
               "tags": ["external-system", e.get("kind")] if e.get("kind") else ["external-system"],
               "generated": generated, "stale_after": stale, "sources": [src_scan]}, "\n".join(body))

    # ---- decision
    if has_decision:
        scen = options.get("quality_scenarios", [])
        body = []
        ctx = options.get("context", {})
        body.append(f"# {t['context']}\n\n" + bullets([ctx.get("domain_complexity"), ctx.get("team")] + list(ctx.get("constraints", []))))
        if scen:
            body.append(f"# {t['decision_drivers']}\n\n" + bullets(f"**{s['id']}** {s.get('scenario', '')}" + (f" ({s.get('driver')})" if s.get("driver") else "") for s in scen))
        lines = []
        for o in options.get("options", []):
            fit = ", ".join(f"{k} {v}" for k, v in (o.get("scenario_fit") or {}).items())
            lines.append(f"**{o['id']} {o.get('name', '')}** ({', '.join(o.get('styles', []))}; {t['understanding']} {o.get('understanding_cost')}, "
                         f"{t['implementation']} {o.get('implementation_size')}{'; ' + fit if fit else ''}){c}{o.get('summary', '')}")
        body.append(f"# {t['considered']}\n\n" + bullets(lines))
        if rec:
            dec = [f"**{rec['id']} {rec.get('name', '')}**{c}{rec.get('why') or rec.get('summary', '')}"]
            if per_domain:
                dec += [f"[{p}](/domains/{p}.md){c}{s}" for p, s in per_domain.items() if p in dom_ids]
            if decision.get("note"):
                dec.append(redact(decision["note"]))
            body.append(f"# {t['decision']}\n\n" + bullets(dec))
            cons = ([rec.get("tradeoffs")] if rec.get("tradeoffs") else []) + list(rec.get("benefits", [])) + list(rec.get("drawbacks", []))
            if cons:
                body.append(f"# {t['consequences']}\n\n" + bullets(redact(x) for x in cons))
        if options.get("rejected"):
            body.append(f"# {t['rejected']}\n\n" + bullets(f"**{r.get('style')}**{c}{r.get('why', '')}" for r in options["rejected"]))
        if options.get("prerequisites"):
            body.append(f"# {t['prerequisites']}\n\n" + bullets(f"{redact(p.get('title'))} ({t['size']} {p.get('size', '?')})" for p in options["prerequisites"]))
        if rules:
            body.append(f"# {t['confirmation']}\n\n" + bullets(f"[{r['id']}](/rules/{slug(r['id'])}.md){c}{r.get('rule', '')}" for r in rules))
        fm = {"type": "Architecture Decision", "title": f"{t['target']}{c}{rec.get('name', '')}" if rec else t["target"],
              "description": sentence(redact(rec.get("summary") or "")) if rec else "", "tags": ["adr", "architecture"],
              "status": "stable" if team_decided else "draft", "adr_status": "accepted" if team_decided else "proposed",
              "generated": generated}
        if team_decided:
            fm["verified"] = human
        fm["sources"] = [src_scan]
        write(dec_rel, fm, "\n".join(body))

    # ---- rules
    for r in rules:
        body = [f"# {t['rule']}\n\n{clean(r.get('rule', ''))}\n"]
        defs = checker_defs.get(r["id"], [])
        why = r.get("why") or next((x.get("why") for x in defs if x.get("why")), "")
        if why:
            body.append(f"# {t['why']}\n\n{clean(why)}\n")
        prev = [x for x in (flink(fid) for fid in r.get("prevents", [])) if x]
        if prev:
            body.append(f"# {t['prevents']}\n\n" + bullets(prev))
        if rule_domains.get(r["id"]):
            body.append(f"# {t['applies']}\n\n" + bullets(f"[{x}](/domains/{x}.md)" for x in rule_domains[r["id"]]))
        chk = [f"{r.get('enforced_by', '')}"]
        if r.get("mode"):
            chk.append(f"{t['mode']}{c}{r['mode']}")
        if r.get("current_violations") is not None:
            chk.append(f"{t['violations']}{c}{r['current_violations']}")
        body.append(f"# {t['checked']}\n\n" + bullets(chk))
        if defs:
            body.append(f"# {t['definition']}\n\n```json\n" + clean(json.dumps(defs, ensure_ascii=False, indent=1)) + "\n```\n")
        write(f"rules/{slug(r['id'])}.md",
              {"type": "Architecture Rule", "title": f"{r['id']} {r.get('rule', '')}", "description": r.get("rule", ""),
               "tags": ["rule", "fitness-function"], "rule_id": r["id"], "enforced_by": r.get("enforced_by"),
               "status": "stable" if team_decided else "draft", "generated": generated, "sources": [src_scan]}, "\n".join(body))

    # ---- plan
    if has_plan:
        body = []
        if plan.get("sequencing_rationale"):
            body.append(f"{t['order']}{c}{clean(plan['sequencing_rationale'])}\n")
        sens_ids = {f["id"] for f in all_findings if is_sensitive_finding(f)}
        for ph in plan["phases"]:
            st = ph.get("status", "not started")
            if st != "done" and sens_ids & set(ph.get("findings", [])):
                ph = dict(ph, goal=t["sec_phase"], exit_criteria=[])
            st_l = STATUS_FR.get(st, st) if lang == "fr" else st
            body.append(f"# {ph['id']} {clean(redact(ph.get('name', '')))} ({ph.get('size', '?')}, {st_l})\n\n{clean(redact(ph.get('goal', '')))}\n")
            if ph.get("domains"):
                body.append(f"{t['domains']}{c}" + ", ".join(f"[{x}](/domains/{x}.md)" for x in ph["domains"] if x in dom_ids) + "\n")
            if ph.get("exit_criteria"):
                body.append(f"{t['exit']}{c}\n\n" + bullets(redact(x) for x in ph["exit_criteria"]))
        write("plan/roadmap.md",
              {"type": "Refactoring Plan", "title": f"{t['phases']}{c}{project}", "description": sentence(redact(plan.get("sequencing_rationale", ""))),
               "tags": ["plan", "refactoring"], "target_option": plan.get("target"), "status": "stable" if team_decided else "draft",
               "generated": generated, "stale_after": iso(date, min(stale_days, 60)), "sources": [src_scan]}, "\n".join(body))

    # ---- glossary
    gl = list(pitch.get("glossary", []) or []) + list(domains.get("glossary", []) or [])
    if gl:
        write("glossary.md", {"type": "Glossary", "title": t["glossary"], "description": f"{t['glossary']} {project}",
                              "tags": ["glossary"], "generated": generated},
              "".join(f"# {clean(g.get('term'))}\n\n{clean(g.get('definition', ''))}\n\n" for g in gl))

    # ---- system
    body = [f"{t['agents']}\n"]
    if doms:
        body.append(f"# {t['domains']}\n\n" + bullets(f"[{d.get('name', d['id'])}](/domains/{d['id']}.md) ({d.get('kind', '')}){c}{redact(d.get('description', ''))}" for d in doms))
    if ext:
        body.append(f"# {t['external']}\n\n" + bullets(f"[{e['name']}](/external-systems/{ext_slug[e['name']]}.md)" for e in ext))
    if domains.get("shared"):
        body.append(f"# {t['shared']}\n\n" + bullets(f"`{s.get('path')}`{c}{redact(s.get('role', ''))}" for s in domains["shared"]))
    if has_decision and rec:
        body.append(f"# {t['target']}\n\n[{rec['id']} {rec.get('name', '')}](/{dec_rel})"
                    + f"{c}{t['accepted'] if team_decided else t['proposed']}\n")
    if rules:
        body.append(f"# {t['rules']}\n\n" + bullets(f"[{r['id']}](/rules/{slug(r['id'])}.md){c}{r.get('rule', '')}" for r in rules))
    if meta.get("quality_drivers"):
        body.append(f"# {t['drivers']}\n\n" + bullets(meta["quality_drivers"]))
    if findings.get("non_findings"):
        body.append(f"# {t['intended']}\n\n" + bullets(f"**{redact(n.get('title'))}**{c}{redact(n.get('why', ''))}"
                                                     + (" (" + ", ".join(f"`{x}`" for x in n.get("files", [])[:3]) + ")" if n.get("files") else "")
                                                     for n in findings["non_findings"]))
    if findings.get("strengths"):
        body.append(f"# {t['strengths']}\n\n" + bullets(redact(x) for x in findings["strengths"]))
    if findings.get("open_questions"):
        body.append(f"# {t['questions']}\n\n" + bullets(redact(x) for x in findings["open_questions"]))
    if has_plan:
        body.append(f"# {t['phases']}\n\n[{plan['phases'][0]['id']} … {plan['phases'][-1]['id']}](/plan/roadmap.md)\n")
    fm = {"type": "Software System", "title": project, "description": meta.get("scope") and f"{project} ({meta['scope']})" or project,
          "tags": ["architecture", "system"], "status": "stable" if validated else "draft", "generated": generated}
    if validated:
        fm["verified"] = human
    fm.update({"stale_after": stale, "sources": [src_scan]})
    write("system.md", fm, "\n".join(body))

    # ---- log (keep previous dated sections)
    entries = []
    if diff:
        F = diff.get("findings", {})
        n_sec = sum(1 for f in F.get("new", []) if is_sensitive_finding(f))
        done = sum(1 for p in diff.get("phases", []) if p.get("status") == "done")
        entries.append(f"* **Update**: {t['reaudit']} {diff.get('from', {}).get('head') or '?'} -> {diff.get('to', {}).get('head') or '?'}{c}"
                       f"{len(F.get('resolved', []))} {t['resolved']}, {len(F.get('new', [])) - n_sec} {t['new']}, "
                       f"{len(F.get('regressed', []))} {t['worse']}, {len(F.get('improved', []))} {t['better']}; "
                       f"{t['phase_status']} {done}/{len(diff.get('phases', []))}. [{t['phases']}](/plan/roadmap.md)")
    else:
        entries.append(f"* **Creation**: {t['created']}" + (f" ({scan_head})" if scan_head else "") + ". [System](/system.md)")
    if team_decided and has_decision:
        entries.append(f"* **Update**: [{t['target']}](/{dec_rel}) {t['accepted']}.")
    old_sections = re.split(r"(?m)^## (?=\d{4}-\d{2}-\d{2}\s*$)", old_log)
    kept = [s for s in old_sections[1:] if not s.startswith(date)]
    log = [f"# {t['log_title']}", "", f"## {date}"] + entries + [""]
    for s in kept:
        log.append("## " + s.rstrip() + "\n")
    open(os.path.join(out, "log.md"), "w", encoding="utf-8").write("\n".join(log).rstrip() + "\n")

    # ---- indexes (no frontmatter except okf_version at the root)
    write_indexes(out, files, t)
    return out, len(files), masked[0] + redacted[0], len(all_findings) - len(pub_findings)


def write_indexes(out, files, t):
    dirs = {}
    for rel, fm in files.items():
        d = os.path.dirname(rel)
        dirs.setdefault(d, []).append((fm.get("type", "Other"), fm.get("title") or os.path.basename(rel)[:-3], os.path.basename(rel), fm.get("description", "")))
    order = lambda ty: (TYPE_ORDER.index(ty) if ty in TYPE_ORDER else len(TYPE_ORDER), ty)
    for d in set(dirs) | {""}:
        entries = dirs.get(d, [])
        groups = {}
        for ty, title, link, desc in entries:
            groups.setdefault(ty, []).append((title, link, desc))
        lines = []
        if d == "":
            lines += ["---", f'okf_version: "{OKF_VERSION}"', "---", ""]
        for ty in sorted(groups, key=order):
            lines += [f"# {ty}", ""] + [f"* [{clean(ti)}]({li})" + (f" - {clean(de)}" if de else "") for ti, li, de in sorted(groups[ty], key=lambda e: str(e[0]).lower())] + [""]
        if d == "":
            subs = sorted(x for x in dirs if x and "/" not in x)
            if subs:
                lines += [f"# {t['subdirs']}", ""] + [f"* [{s}]({s}/index.md) - {', '.join(sorted({g for g, *_ in dirs[s]}))}" for s in subs] + [""]
        open(os.path.join(out, d, "index.md"), "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")


# ---------------------------------------------------------------- conformance check (OKF v0.2, section 11)
def parse_fm(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_text = "\n".join(lines[1:i])
            try:
                import yaml  # optional: real YAML parse when available
                class Lo(yaml.SafeLoader):
                    pass
                Lo.yaml_implicit_resolvers = {k: [(tg, r) for tg, r in v if tg != "tag:yaml.org,2002:timestamp"] for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()}
                fm = yaml.load(fm_text, Loader=Lo) or {}
            except ImportError:
                fm = {}
                for ln in lines[1:i]:
                    m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
                    if m:
                        v = m.group(2).strip()
                        fm[m.group(1)] = json.loads(v) if v.startswith('"') else v
            return fm, "\n".join(lines[i + 1:])
    raise ValueError("unterminated frontmatter")


def check(bundle):
    errors, warnings, n = [], [], 0
    for root, _, fs in os.walk(bundle):
        for f in fs:
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, bundle)
            text = open(p, encoding="utf-8").read()
            try:
                fm, body = parse_fm(text)
            except Exception as e:  # noqa: BLE001 - report any YAML error
                errors.append(f"{rel}: invalid frontmatter ({e})")
                continue
            if f == "index.md":
                if fm is not None and (root != bundle or set(fm) - {"okf_version"}):
                    errors.append(f"{rel}: index.md may only carry okf_version, at the bundle root")
                continue
            if f == "log.md":
                for h in re.findall(r"(?m)^## (.+)$", body):
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", h.strip()):
                        errors.append(f"{rel}: log heading '{h}' is not YYYY-MM-DD")
                continue
            n += 1
            if not isinstance(fm, dict):
                errors.append(f"{rel}: no YAML frontmatter")
                continue
            if not str(fm.get("type") or "").strip():
                errors.append(f"{rel}: frontmatter has no non-empty 'type'")
            for k in ("generated",):
                g = fm.get(k)
                if isinstance(g, dict) and not g.get("by"):
                    errors.append(f"{rel}: generated.by is required within generated")
            if fm.get("status") and fm["status"] not in ("draft", "stable", "deprecated"):
                warnings.append(f"{rel}: status '{fm['status']}' is not draft|stable|deprecated")
            for m in re.finditer(r"\]\((/[^)#\s]+)\)", body):
                if not os.path.exists(os.path.join(bundle, m.group(1).lstrip("/"))):
                    warnings.append(f"{rel}: broken link {m.group(1)} (allowed by the spec)")
            if SECRET_RX.search(text):
                errors.append(f"{rel}: secret-like value")
    return errors, warnings, n


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if a[0] == "--check":
        errors, warnings, n = check(a[1])
        for w in warnings:
            print("WARN  " + w)
        for e in errors:
            print("ERROR " + e)
        print(f"OKF {OKF_VERSION} check: {n} concepts, {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1 if errors else 0
    archi = a[0]
    out = a[a.index("--out") + 1] if "--out" in a else None
    days = int(a[a.index("--stale-days") + 1]) if "--stale-days" in a else 120
    out, n, nmask, nsec = export(archi, out, days)
    print(f"written {out}: {n} concepts (OKF {OKF_VERSION})" + (f", {nmask} secret-like value(s) or secret location(s) masked" if nmask else "")
          + (f", {nsec} security finding(s) left out" if nsec else ""))
    errors, warnings, _ = check(out)
    for e in errors:
        print("ERROR " + e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
