#!/usr/bin/env python3
"""Generate .re-arch/plan.md (ticket-ready) from .re-arch/plan.json. Never edit plan.md by hand."""
import json
import os
import sys

L = {
    "en": {"title": "Refactoring plan", "target": "Target option", "order": "Order", "assumptions": "Assumptions",
           "oos": "Out of scope", "size": "Size", "goal": "Goal", "domains": "Domains", "findings": "Findings",
           "after": "After", "steps": "Steps", "move": "Move", "verify": "Check", "status": "Status", "exit": "Done when", "rollback": "Rollback", "risks": "Risks",
           "stop": "Safe stop point: the team can stop after this phase and still be better off.",
           "scale": "Sizes: S one module, tested, no contract change. M several modules of one domain. L several domains, new abstractions. XL data model or global style change, to split."},
    "fr": {"title": "Plan de refactoring", "target": "Option cible", "order": "Ordre", "assumptions": "Hypothèses",
           "oos": "Hors périmètre", "size": "Taille", "goal": "Objectif", "domains": "Domaines", "findings": "Constats",
           "after": "Après", "steps": "Étapes", "move": "Déplacer", "verify": "Vérifier", "status": "Statut", "exit": "Terminé quand", "rollback": "Retour arrière", "risks": "Risques",
           "stop": "Point d'arrêt possible : l'équipe peut s'arrêter après cette phase et rester gagnante.",
           "scale": "Tailles : S un module, testé, sans changement de contrat. M plusieurs modules d'un domaine. L plusieurs domaines, nouvelles abstractions. XL changement de modèle de données ou de style global, à découper."},
}


STATUS = {"fr": {"not started": "à faire", "in progress": "en cours", "done": "terminée", "dropped": "abandonnée"}}


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else ".re-arch"
    plan = json.load(open(os.path.join(d, "plan.json"), encoding="utf-8"))
    meta = {}
    if os.path.exists(os.path.join(d, "meta.json")):
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    lang = "fr" if str(meta.get("lang", "en")).startswith("fr") else "en"
    t = L[lang]
    c = " : " if t is L["fr"] else ": "
    out = [f"# {t['title']}{(' · ' + meta['project']) if meta.get('project') else ''}", ""]
    if plan.get("target"):
        name = ""
        op = os.path.join(d, "options.json")
        if os.path.exists(op):
            opts = json.load(open(op, encoding="utf-8"))
            name = next((o.get("name", "") for o in opts.get("options", []) if o.get("id") == plan["target"]), "")
        out.append(f"**{t['target']}**{c}{plan['target']}{(' · ' + name) if name else ''}  ")
    if plan.get("sequencing_rationale"):
        out.append(f"**{t['order']}**{c}{plan['sequencing_rationale']}")
    out += ["", f"_{t['scale']}_", ""]
    for ph in plan.get("phases", []):
        out.append(f"## {ph.get('id')} · {ph.get('name')} ({ph.get('size')})" + (f" · {STATUS.get(lang, {}).get(ph['status'], ph['status'])}" if ph.get("status") else ""))
        out.append("")
        out.append(f"**{t['goal']}**{c}{ph.get('goal', '')}  ")
        if ph.get("size_rationale"):
            out.append(f"**{t['size']} {ph.get('size')}**{c}{ph['size_rationale']}  ")
        if ph.get("domains"):
            out.append(f"**{t['domains']}**{c}{', '.join(ph['domains'])}  ")
        if ph.get("findings"):
            out.append(f"**{t['findings']}**{c}{', '.join(ph['findings'])}  ")
        if ph.get("depends_on"):
            out.append(f"**{t['after']}**{c}{', '.join(ph['depends_on'])}  ")
        out += ["", f"### {t['steps']}", ""]
        for st in ph.get("steps", []):
            if isinstance(st, dict):
                out.append(f"- [ ] {st.get('do', '')}")
                for mv in st.get("moves", []):
                    out.append(f"  - {t['move']}{c}`{mv.get('from')}` -> `{mv.get('to')}`")
                if st.get("verify"):
                    out.append(f"  - {t['verify']}{c}`{st['verify']}`")
            else:
                out.append(f"- [ ] {st}")
        if ph.get("exit_criteria"):
            out += ["", f"### {t['exit']}", ""] + [f"- [ ] {s}" for s in ph["exit_criteria"]]
        if ph.get("rollback"):
            out += ["", f"**{t['rollback']}**{c}{ph['rollback']}"]
        if ph.get("risks"):
            out += ["", f"**{t['risks']}**", ""] + [f"- {r}" for r in ph["risks"]]
        if ph.get("stop_point"):
            out += ["", f"> {t['stop']}"]
        out.append("")
    if plan.get("assumptions"):
        out += [f"## {t['assumptions']}", ""] + [f"- {a}" for a in plan["assumptions"]] + [""]
    if plan.get("out_of_scope"):
        out += [f"## {t['oos']}", ""] + [f"- {a}" for a in plan["out_of_scope"]] + [""]
    p = os.path.join(d, "plan.md")
    open(p, "w", encoding="utf-8").write("\n".join(out))
    print(f"written {p}")


if __name__ == "__main__":
    main()
