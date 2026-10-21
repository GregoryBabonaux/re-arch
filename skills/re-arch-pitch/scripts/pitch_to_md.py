#!/usr/bin/env python3
"""Generate .re-arch/pitch.md (memo to paste in an email or a slide) from .re-arch/pitch.json. Never edit pitch.md by hand."""
import json
import os
import sys

L = {
    "en": {"title": "Refactoring proposal", "situation": "Situation", "risks": "Risks today", "options": "Options",
           "reco": "Recommendation", "invest": "Investment", "assumptions": "Assumptions", "milestones": "Milestones",
           "kpis": "How we will know it works", "decision": "Decision requested", "glossary": "Glossary",
           "likelihood": "likelihood", "size": "size", "gain": "Gain", "risk": "Risk", "baseline": "today", "target": "target"},
    "fr": {"title": "Proposition de refactoring", "situation": "Situation", "risks": "Risques aujourd'hui", "options": "Options",
           "reco": "Recommandation", "invest": "Investissement", "assumptions": "Hypothèses", "milestones": "Jalons",
           "kpis": "Comment on saura que ça marche", "decision": "Décision attendue", "glossary": "Glossaire",
           "likelihood": "probabilité", "size": "taille", "gain": "Gain", "risk": "Risque", "baseline": "aujourd'hui", "target": "cible"},
}
LIKELY = {"fr": {"high": "élevée", "medium": "moyenne", "low": "faible"}, "en": {}}


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else ".re-arch"
    p = json.load(open(os.path.join(d, "pitch.json"), encoding="utf-8"))
    meta = {}
    if os.path.exists(os.path.join(d, "meta.json")):
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    lang = "fr" if str(meta.get("lang", "en")).startswith("fr") else "en"
    t, c = L[lang], (" : " if lang == "fr" else ": ")
    out = [f"# {t['title']}{(' · ' + meta['project']) if meta.get('project') else ''}", ""]
    if p.get("headline"):
        out += [f"**{p['headline']}**", ""]
    if p.get("situation"):
        out += [f"## {t['situation']}", "", p["situation"], ""]
    if p.get("risks"):
        out += [f"## {t['risks']}", ""]
        for r in p["risks"]:
            lk = LIKELY[lang].get(r.get("likelihood"), r.get("likelihood", ""))
            out.append(f"- **{r.get('risk')}**{c}{r.get('consequence', '')} ({t['likelihood']} {lk})")
        out.append("")
    if p.get("options"):
        out += [f"## {t['options']}", ""]
        for o in p["options"]:
            out.append(f"- **{o.get('name')}** ({t['size']} {o.get('size', '-')})")
            if o.get("gain"):
                out.append(f"  - {t['gain']}{c}{o['gain']}")
            if o.get("risk"):
                out.append(f"  - {t['risk']}{c}{o['risk']}")
        out.append("")
    if p.get("recommendation"):
        out += [f"## {t['reco']}", "", p["recommendation"], ""]
    inv = p.get("investment") or {}
    if inv:
        out += [f"## {t['invest']}", "", f"{t['size'].capitalize()} {inv.get('size', '?')}{c}{inv.get('capacity', '')}", ""]
        if inv.get("assumptions"):
            out += [f"{t['assumptions']}{c}", ""] + [f"- {a}" for a in inv["assumptions"]] + [""]
    if p.get("milestones"):
        out += [f"## {t['milestones']}", ""] + [f"- **{m.get('when')}**{c}{m.get('what', '')}" + (f" ({m['indicator']})" if m.get("indicator") else "") for m in p["milestones"]] + [""]
    if p.get("kpis"):
        out += [f"## {t['kpis']}", ""] + [f"- {k.get('name')}{c}{t['baseline']} {k.get('baseline', '?')}, {t['target']} {k.get('target', '?')}" for k in p["kpis"]] + [""]
    if p.get("decision_requested"):
        out += [f"## {t['decision']}", "", p["decision_requested"], ""]
    if p.get("glossary"):
        out += [f"## {t['glossary']}", ""] + [f"- **{g.get('term')}**{c}{g.get('definition', '')}" for g in p["glossary"]] + [""]
    path = os.path.join(d, "pitch.md")
    open(path, "w", encoding="utf-8").write("\n".join(out))
    print(f"written {path}")


if __name__ == "__main__":
    main()
