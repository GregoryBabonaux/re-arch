#!/usr/bin/env python3
"""
re-arch-report / render.py

Renders .re-arch/*.json into one self-contained, responsive HTML report
(.re-arch/report.html). Standard library only. Every section is optional:
missing files simply hide their tab, so the report works after any subset
of the re-arch steps.

Usage: python3 render.py <repo>/.re-arch [--out report.html]
"""
import argparse
import collections
import html
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

LABELS = {
    "en": {
        "title": "Architecture audit", "summary": "Summary", "domains": "Domains", "diagnosis": "Diagnosis",
        "options": "Options", "plan": "Plan", "academy": "Upskilling", "guardrails": "AI & CI guardrails",
        "appendix": "Appendix", "generated": "Generated", "scope": "Scope", "commit": "Commit",
        "decision_needed": "Decision requested", "recommendation": "Recommendation", "situation": "Situation",
        "risks": "Risks", "risk": "Risk", "consequence": "Consequence", "likelihood": "Likelihood",
        "evidence": "Evidence", "investment": "Investment", "milestones": "Milestones", "kpis": "Success indicators",
        "baseline": "Baseline", "target": "Target", "glossary": "Glossary", "size": "Size", "gain": "Gain",
        "option": "Option", "loc": "lines of code", "test_ratio": "test code / production code", "cycles": "module cycles",
        "crit_high": "critical + high findings", "strengths": "Strengths to keep", "findings": "Findings",
        "impact_tech": "Impact for the team", "impact_business": "Impact for the business", "fix": "Direction of the fix",
        "understanding": "Understanding cost", "implementation": "Implementation size", "concepts": "Concepts",
        "hops": "Request path", "benefits": "Benefits", "drawbacks": "Drawbacks", "addresses": "Addresses",
        "not_addresses": "Does not address", "signals": "Justified by", "recommended": "Recommended",
        "chosen": "Retained", "assumed": "Recommended, awaiting team validation", "rejected": "Considered and rejected",
        "opportunities": "Local opportunities", "why": "Why", "phase": "Phase", "goal": "Goal", "steps": "Steps",
        "exit": "Done when", "rollback": "Rollback", "stop_point": "Safe stop point", "depends": "After",
        "assumptions": "Assumptions", "out_of_scope": "Out of scope", "sequencing": "Order", "path": "Learning path",
        "modules": "Modules", "reading": "Reading", "rules": "Rules", "enforced_by": "Enforced by", "mode": "Mode",
        "violations": "Current violations", "files": "Files", "purpose": "Purpose", "kind": "Kind",
        "confidence": "Confidence", "entities": "Entities", "depends_on": "Depends on", "shared": "Shared technical parts",
        "fuzzy": "Fuzzy zones", "map": "Domain map", "map_validated": "Domain map validated by the team",
        "map_not_validated": "Domain map not yet validated by the team", "core": "core", "supporting": "supporting",
        "generic": "generic", "technical": "technical", "high": "high", "medium": "medium", "low": "low",
        "critical": "critical", "all": "All", "severity": "Severity", "method": "Method", "limits": "Limits of the analysis",
        "hotspots": "Hotspots", "module_table": "Modules", "file": "File", "score": "Score", "churn": "Changes",
        "branches": "Branches", "context": "Context", "team": "Team", "constraints": "Constraints",
        "domain_complexity": "Domain complexity", "legend_dep": "depends on", "legend_both": "mutual dependency", "legend_runtime": "injected at runtime (DI)",
        "no_js": "", "size_scale": "S small · M medium · L large · XL to split", "level": "Level", "duration": "Duration",
        "when": "When", "audience": "Audience", "metrics": "Key figures", "print": "Print / PDF", "cochange": "changed together",
        "imports": "imports", "shared-entity": "shared data", "runtime": "runtime call", "do_nothing_hint": "",
        "capacity": "Capacity", "per_domain": "Per domain", "top": "Back to top", "fan_in": "Used by",
        "colon": ": ", "non_findings": "Looks bad but is fine", "open_questions": "Questions for the maintainers", "fix_size": "fix", "debt": {"deliberate-prudent": "deliberate, prudent", "deliberate-reckless": "deliberate, reckless", "inadvertent-prudent": "inadvertent, prudent", "inadvertent-reckless": "inadvertent, reckless"},
        "quality": "Quality scenarios", "scenario": "Scenario", "fit": {"+": "helps", "0": "neutral", "-": "hurts"}, "tradeoffs": "Trade-offs",
        "context_view": "Context view (C4)", "app": "Application", "external": "External systems", "graph_sources": "How dependencies were resolved",
        "units": "Build units", "di": "Dependency injection", "knowledge": "Knowledge distribution", "islands": "Knowledge islands in hotspots",
        "orphaned": "Code mainly written by people who left", "hygiene": "Dependency hygiene", "same_job": "Several libraries for the same job",
        "undeclared": "Imported but not declared", "unused": "Declared but not imported", "routes": "HTTP routes by resource",
        "progress": "Progress since the previous audit", "resolved": "resolved", "new_f": "new", "worse": "worse", "better_m": "better",
        "verify": "check", "status": {"not started": "not started", "in progress": "in progress", "done": "done", "dropped": "dropped"},
        "abstraction": "Abstraction", "implementation_h": "Implementation", "registered": "Registered in", "tech": "tech team", "management": "management", "assumptions_made": "Assumptions made during the audit",
        "fix_share": "of commits are fixes", "prerequisites": "Prerequisites for every option", "low_conf": "low confidence",
    },
    "fr": {
        "title": "Audit d'architecture", "summary": "Synthèse", "domains": "Domaines", "diagnosis": "Diagnostic",
        "options": "Options", "plan": "Plan", "academy": "Montée en compétence", "guardrails": "Cadrage IA & CI",
        "appendix": "Annexes", "generated": "Généré le", "scope": "Périmètre", "commit": "Commit",
        "decision_needed": "Décision attendue", "recommendation": "Recommandation", "situation": "Situation",
        "risks": "Risques", "risk": "Risque", "consequence": "Conséquence", "likelihood": "Probabilité",
        "evidence": "Preuves", "investment": "Investissement", "milestones": "Jalons", "kpis": "Indicateurs de succès",
        "baseline": "Aujourd'hui", "target": "Cible", "glossary": "Glossaire", "size": "Taille", "gain": "Gain",
        "option": "Option", "loc": "lignes de code", "test_ratio": "code de test / code de production", "cycles": "cycles entre modules",
        "crit_high": "constats critiques + élevés", "strengths": "Points forts à préserver", "findings": "Constats",
        "impact_tech": "Impact pour l'équipe", "impact_business": "Impact pour l'entreprise", "fix": "Piste de correction",
        "understanding": "Coût de compréhension", "implementation": "Taille d'implémentation", "concepts": "Concepts",
        "hops": "Chemin d'une requête", "benefits": "Bénéfices", "drawbacks": "Inconvénients", "addresses": "Traite",
        "not_addresses": "Ne traite pas", "signals": "Justifié par", "recommended": "Recommandée",
        "chosen": "Retenue", "assumed": "Recommandée, en attente de validation par l'équipe", "rejected": "Envisagés et écartés",
        "opportunities": "Opportunités locales", "why": "Pourquoi", "phase": "Phase", "goal": "Objectif", "steps": "Étapes",
        "exit": "Terminé quand", "rollback": "Retour arrière", "stop_point": "Point d'arrêt possible", "depends": "Après",
        "assumptions": "Hypothèses", "out_of_scope": "Hors périmètre", "sequencing": "Ordre", "path": "Parcours",
        "modules": "Modules", "reading": "Lectures", "rules": "Règles", "enforced_by": "Contrôlée par", "mode": "Mode",
        "violations": "Violations actuelles", "files": "Fichiers", "purpose": "Rôle", "kind": "Type",
        "confidence": "Confiance", "entities": "Entités", "depends_on": "Dépend de", "shared": "Parties techniques partagées",
        "fuzzy": "Zones floues", "map": "Carte des domaines", "map_validated": "Carte des domaines validée par l'équipe",
        "map_not_validated": "Carte des domaines pas encore validée par l'équipe", "core": "cœur", "supporting": "support",
        "generic": "générique", "technical": "technique", "high": "élevée", "medium": "moyenne", "low": "faible",
        "critical": "critique", "all": "Tous", "severity": "Gravité", "method": "Méthode", "limits": "Limites de l'analyse",
        "hotspots": "Points chauds", "module_table": "Modules", "file": "Fichier", "score": "Score", "churn": "Modifs",
        "branches": "Branches", "context": "Contexte", "team": "Équipe", "constraints": "Contraintes",
        "domain_complexity": "Complexité du domaine", "legend_dep": "dépend de", "legend_both": "dépendance mutuelle", "legend_runtime": "injectée à l'exécution (DI)",
        "no_js": "", "size_scale": "S petit · M moyen · L grand · XL à découper", "level": "Niveau", "duration": "Durée",
        "when": "Quand", "audience": "Public", "metrics": "Chiffres clés", "print": "Imprimer / PDF", "cochange": "modifiés ensemble",
        "imports": "imports", "shared-entity": "données partagées", "runtime": "appel à l'exécution", "do_nothing_hint": "",
        "capacity": "Capacité", "per_domain": "Par domaine", "top": "Haut de page", "fan_in": "Utilisé par",
        "colon": "\u00a0: ", "non_findings": "Ce qui a l'air fragile mais ne l'est pas", "open_questions": "Questions pour les mainteneurs", "fix_size": "correction", "debt": {"deliberate-prudent": "délibérée, prudente", "deliberate-reckless": "délibérée, imprudente", "inadvertent-prudent": "involontaire, prudente", "inadvertent-reckless": "involontaire, imprudente"},
        "quality": "Scénarios de qualité", "scenario": "Scénario", "fit": {"+": "favorise", "0": "neutre", "-": "pénalise"}, "tradeoffs": "Compromis",
        "context_view": "Vue contexte (C4)", "app": "Application", "external": "Systèmes externes", "graph_sources": "Comment les dépendances ont été résolues",
        "units": "Unités de build", "di": "Injection de dépendances", "knowledge": "Répartition de la connaissance", "islands": "Îlots de connaissance dans les points chauds",
        "orphaned": "Code écrit surtout par des personnes parties", "hygiene": "Hygiène des dépendances", "same_job": "Plusieurs librairies pour le même besoin",
        "undeclared": "Importées mais non déclarées", "unused": "Déclarées mais jamais importées", "routes": "Routes HTTP par ressource",
        "progress": "Progression depuis l'audit précédent", "resolved": "résolus", "new_f": "nouveaux", "worse": "aggravés", "better_m": "mieux",
        "verify": "vérif.", "status": {"not started": "à faire", "in progress": "en cours", "done": "terminée", "dropped": "abandonnée"},
        "abstraction": "Abstraction", "implementation_h": "Implémentation", "registered": "Déclarée dans", "tech": "équipe tech", "management": "direction", "assumptions_made": "Hypothèses prises pendant l'audit",
        "fix_share": "des commits sont des corrections", "prerequisites": "Préalables communs à toutes les options", "low_conf": "confiance faible",
    },
}
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SIZES = ["S", "M", "L", "XL"]

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def md(s):
    """Escape then allow `code` and **bold**."""
    t = esc(s)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return t


def load(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except ValueError as e:
        print(f"warning: {name} is not valid JSON ({e}); section skipped", file=sys.stderr)
        return None


def ul(items, cls=""):
    items = [i for i in (items or []) if i not in (None, "")]
    if not items:
        return ""
    return f'<ul class="{cls}">' + "".join(f"<li>{md(i)}</li>" for i in items) + "</ul>"


def size_badge(size, label=""):
    size = (size or "").upper()
    idx = SIZES.index(size) if size in SIZES else -1
    bars = "".join(f'<i class="{"on" if i <= idx else ""}"></i>' for i in range(4))
    title = f' title="{esc(label)}"' if label else ""
    return f'<span class="size size-{esc(size.lower() or "na")}"{title}><b>{esc(size or "?")}</b><span class="bars">{bars}</span></span>'


def chip(text, cls=""):
    return f'<span class="chip {cls}">{esc(text)}</span>'


# ---------------------------------------------------------------------------
# Domain map (SVG)
# ---------------------------------------------------------------------------


def wrap_text(text, max_chars):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w[:max_chars]
    if cur:
        lines.append(cur)
    return lines[:2] if len(lines) <= 2 else [lines[0], (lines[1][: max_chars - 1] + "…")]


def layout_layers(domains):
    ids = [d["id"] for d in domains]
    deps = {d["id"]: [x["id"] for x in d.get("depends_on", []) if x.get("id") in ids and x.get("id") != d["id"]] for d in domains}
    # break cycles: DFS, drop back edges for layering only
    state, acyclic = {}, {i: [] for i in ids}

    def dfs(n):
        state[n] = 1
        for m in deps[n]:
            if state.get(m) == 1:
                continue
            acyclic[n].append(m)
            if m not in state:
                dfs(m)
        state[n] = 2

    for i in ids:
        if i not in state:
            dfs(i)
    # layer = longest path to a sink (sinks at the bottom)
    memo = {}

    def height(n, seen=()):
        if n in memo:
            return memo[n]
        h = 0
        for m in acyclic[n]:
            if m not in seen:
                h = max(h, 1 + height(m, seen + (n,)))
        memo[n] = h
        return h

    hmax = max((height(i) for i in ids), default=0)
    layers = collections.defaultdict(list)
    for i in ids:
        layers[hmax - height(i)].append(i)
    order = [layers[k] for k in sorted(layers)]
    # barycenter ordering, one downward pass
    pos = {}
    for li, layer in enumerate(order):
        if li > 0:
            def bary(n):
                parents = [pos[p] for p in ids if n in deps.get(p, []) and p in pos]
                return sum(parents) / len(parents) if parents else 999
            layer.sort(key=bary)
        for k, n in enumerate(layer):
            pos[n] = k
    return order, deps


def domain_svg(domains, cols, L, width):
    if not domains:
        return ""
    by_id = {d["id"]: d for d in domains}
    order, deps = layout_layers(domains)
    rows = []
    for layer in order:
        for k in range(0, len(layer), cols):
            rows.append(layer[k:k + cols])
    node_w = (width - 90 - (cols - 1) * 24) / cols
    node_w = min(node_w, 220)
    node_h, row_gap = 74, 70
    max_chars = max(10, int(node_w / 9.5))
    coords = {}
    for r, row in enumerate(rows):
        total = len(row) * node_w + (len(row) - 1) * 24
        x0 = (width - total) / 2
        for k, n in enumerate(row):
            coords[n] = (x0 + k * (node_w + 24), 20 + r * (node_h + row_gap))
    height = 20 + len(rows) * (node_h + row_gap) - row_gap + 30
    parts = [f'<svg viewBox="0 0 {width} {height:.0f}" role="img" aria-label="{esc(L["map"])}" class="dmap">']
    parts.append('<defs><marker id="ah{c}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="ah"/></marker>'
                 '<marker id="ahw{c}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="ahw"/></marker></defs>'.format(c=cols))
    row_of = {n: r for r, row in enumerate(rows) for n in row}
    row_y = {r: 20 + r * (node_h + row_gap) for r in range(len(rows))}
    lanes_r, lanes_l = collections.Counter(), collections.Counter()
    kinds = collections.defaultdict(set)
    for dm in domains:
        for x in dm.get("depends_on", []):
            kinds[(dm["id"], x.get("id"))].add(x.get("kind", "imports"))
    static = lambda a, b: bool(kinds.get((a, b), {"imports"}) - {"runtime"})
    drawn = set()
    for a, targets in deps.items():
        for b in targets:
            if (a, b) in drawn:
                continue
            mutual = a in deps.get(b, []) and static(a, b) and static(b, a)
            runtime_only = not static(a, b)
            drawn.add((a, b))
            if mutual:
                drawn.add((b, a))
            ax, ay = coords[a]
            bx, by = coords[b]
            ra, rb = row_of[a], row_of[b]
            if rb == ra + 1 or (rb == ra - 1):
                # adjacent rows: direct curve between facing sides
                if rb > ra:
                    x1, y1, x2, y2 = ax + node_w / 2, ay + node_h, bx + node_w / 2, by - 2
                else:
                    x1, y1, x2, y2 = ax + node_w / 2, ay, bx + node_w / 2, by + node_h + 2
                my = (y1 + y2) / 2
                d = f"M{x1:.0f},{y1:.0f} C{x1:.0f},{my:.0f} {x2:.0f},{my:.0f} {x2:.0f},{y2:.0f}"
            elif rb == ra:
                left = bx > ax
                between = [n for n in coords if row_of[n] == ra and min(ax, bx) < coords[n][0] < max(ax, bx)]
                if not between:
                    x1 = ax + (node_w if left else 0)
                    x2 = bx + (0 if left else node_w)
                    yy = ay + node_h / 2
                    d = f"M{x1:.0f},{yy:.0f} L{x2 + (-2 if left else 2):.0f},{yy:.0f}"
                else:
                    # boxes in between: go under the row, through the gap, never across a box
                    k = lanes_r[("row", ra)]
                    lanes_r[("row", ra)] += 1
                    gy = ay + node_h + 14 + 8 * k
                    x1, x2 = ax + node_w * (0.62 if left else 0.38), bx + node_w * (0.38 if left else 0.62)
                    d = f"M{x1:.0f},{ay + node_h:.0f} L{x1:.0f},{gy:.0f} L{x2:.0f},{gy:.0f} L{x2:.0f},{ay + node_h + 2:.0f}"
            else:
                # spans several rows: go around the boxes through a side lane
                lo, hi = min(ra, rb), max(ra, rb)
                between = [n for n in coords if lo <= row_of[n] <= hi]
                right_edge = max([coords[n][0] + node_w for n in between] + [ax + node_w, bx + node_w])
                left_edge = min([coords[n][0] for n in between] + [ax, bx])
                use_right = (width - right_edge) >= (left_edge - 0) or rb > ra
                if use_right and right_edge + 14 < width - 4:
                    k = lanes_r[(lo, hi)]
                    lanes_r[(lo, hi)] += 1
                    lane = min(width - 6, right_edge + 14 + 9 * k)
                    sx, ex = ax + node_w, bx + node_w
                else:
                    k = lanes_l[(lo, hi)]
                    lanes_l[(lo, hi)] += 1
                    lane = max(6, left_edge - 14 - 9 * k)
                    sx, ex = ax, bx
                up = by < ay
                k_off = (lanes_r[(lo, hi)] + lanes_l[(lo, hi)]) * 6
                x1 = ax + node_w / 2 + (12 if lane > ax else -12)
                y1 = ay if up else ay + node_h
                gy1 = (ay - row_gap / 2 - k_off) if up else (ay + node_h + row_gap / 2 + k_off)
                # enter the target from the gap on the side we come from, never across its row
                gy2 = (by + node_h + row_gap / 2 - k_off) if up else (by - row_gap / 2 + k_off)
                x2 = bx + node_w / 2 + (12 if lane > bx else -12)
                y2 = (by + node_h + 2) if up else (by - 2)
                d = f"M{x1:.0f},{y1:.0f} L{x1:.0f},{gy1:.0f} L{lane:.0f},{gy1:.0f} L{lane:.0f},{gy2:.0f} L{x2:.0f},{gy2:.0f} L{x2:.0f},{y2:.0f}"
            cls = "edge mutual" if mutual else "edge runtime" if runtime_only else "edge"
            mk = f"ahw{cols}" if mutual else f"ah{cols}"
            start_m = f' marker-start="url(#{mk})"' if mutual else ""
            parts.append(f'<path d="{d}" class="{cls}" marker-end="url(#{mk})"{start_m}/>')
            if not mutual and a in deps.get(b, []):
                drawn.discard((b, a))  # the reverse edge, of another kind, is drawn on its own
    for n, (x, y) in coords.items():
        dm = by_id[n]
        kind = dm.get("kind", "supporting")
        conf = dm.get("confidence", "medium")
        parts.append(f'<g class="node k-{esc(kind)} c-{esc(conf)}"><rect x="{x:.0f}" y="{y:.0f}" width="{node_w:.0f}" height="{node_h}" rx="10"/>')
        lines = wrap_text(dm.get("name", n), max_chars)
        ty = y + (26 if len(lines) == 2 else 34)
        for i, line in enumerate(lines):
            parts.append(f'<text x="{x + node_w / 2:.0f}" y="{ty + i * 19:.0f}" class="nt">{esc(line)}</text>')
        sub = f'{L.get(kind, kind)} · {dm.get("loc", "?")} loc'
        parts.append(f'<text x="{x + node_w / 2:.0f}" y="{y + node_h - 12:.0f}" class="ns">{esc(sub)}</text></g>')
    parts.append("</svg>")
    return "".join(parts)


def route_resource(path):
    segs = [x for x in path.split("/") if x and not x.startswith((":", "{", "<", "[")) and not re.match(r"^v\d+$|^api$|^admin$|^public$", x)]
    return segs[0].lower() if segs else "/"


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def context_svg(domains, systems, L, width, cols):
    """C4-style context view. Wide: one row of domains above one row of systems.
    Narrow, or too many domains for one row: domains in a left column, systems in a
    right column, edges as horizontal curves. Edges never cross a box."""
    doms = [d for d in domains if d.get("kind") != "technical"]
    if not doms or not systems:
        return ""
    by_id = {d["id"]: d for d in doms}
    two_col = cols <= 2 or len(doms) > 7 or len(systems) > 7
    parts, coords_d, coords_s = [], {}, {}
    if two_col:
        bw, bh, gap = min(190, (width - 100) / 2), 50, 14
        maxc = max(8, int(bw / 8.6))
        n = max(len(doms), len(systems))
        h = 40 + n * (bh + gap) + 10
        yd0 = 40 + (n - len(doms)) * (bh + gap) / 2
        ys0 = 40 + (n - len(systems)) * (bh + gap) / 2
        for i, d in enumerate(doms):
            coords_d[d["id"]] = (12, yd0 + i * (bh + gap))
        for i, x in enumerate(systems):
            coords_s[x["name"]] = (width - 12 - bw, ys0 + i * (bh + gap))
        parts.append(f'<svg viewBox="0 0 {width} {h:.0f}" role="img" aria-label="{esc(L["context_view"])}" class="dmap ctxmap">')
        parts.append(f'<text x="12" y="24" class="frame-label">{esc(L["app"])}</text><text x="{width - 12 - bw:.0f}" y="24" class="frame-label">{esc(L["external"])}</text>')
        parts.append(f'<defs><marker id="ahctx{cols}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="ah"/></marker></defs>')
        for x in systems:
            for did in x.get("used_by", []):
                if did in coords_d:
                    ax, ay = coords_d[did]
                    bx, by = coords_s[x["name"]]
                    x1, y1, x2, y2 = ax + bw, ay + bh / 2, bx - 2, by + bh / 2
                    mx = (x1 + x2) / 2
                    parts.append(f'<path d="M{x1:.0f},{y1:.0f} C{mx:.0f},{y1:.0f} {mx:.0f},{y2:.0f} {x2:.0f},{y2:.0f}" class="edge" marker-end="url(#ahctx{cols})"/>')
    else:
        gap, bh = 14, 54
        bw = min(190, (width - 24 - (max(len(doms), len(systems)) - 1) * gap) / max(len(doms), len(systems)))
        maxc = max(8, int(bw / 8.6))

        def row(items, y):
            total = len(items) * bw + (len(items) - 1) * gap
            x0 = (width - total) / 2
            return {it: (x0 + k * (bw + gap), y) for k, it in enumerate(items)}

        coords_d = row([d["id"] for d in doms], 44)
        coords_s = row([x["name"] for x in systems], 44 + bh + 110)
        h = 44 + 2 * bh + 110 + 16
        parts.append(f'<svg viewBox="0 0 {width} {h:.0f}" role="img" aria-label="{esc(L["context_view"])}" class="dmap ctxmap">')
        parts.append(f'<rect x="6" y="8" width="{width - 12}" height="{bh + 52}" rx="14" class="appframe"/>')
        parts.append(f'<text x="18" y="30" class="frame-label">{esc(L["app"])}</text><text x="18" y="{44 + bh + 92}" class="frame-label">{esc(L["external"])}</text>')
        parts.append(f'<defs><marker id="ahctx{cols}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="ah"/></marker></defs>')
        for x in systems:
            for did in x.get("used_by", []):
                if did in coords_d:
                    ax, ay = coords_d[did]
                    bx, by = coords_s[x["name"]]
                    x1, y1, x2, y2 = ax + bw / 2, ay + bh, bx + bw / 2, by - 2
                    my = (y1 + y2) / 2
                    parts.append(f'<path d="M{x1:.0f},{y1:.0f} C{x1:.0f},{my:.0f} {x2:.0f},{my:.0f} {x2:.0f},{y2:.0f}" class="edge" marker-end="url(#ahctx{cols})"/>')
    for did, (x, y) in coords_d.items():
        d = by_id[did]
        lines = wrap_text(d.get("name", did), maxc)
        parts.append(f'<g class="node k-{esc(d.get("kind", ""))}"><rect x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="{bh if not two_col else 50}" rx="9"/>')
        hh = 50 if two_col else bh
        for i, line in enumerate(lines):
            parts.append(f'<text x="{x + bw / 2:.0f}" y="{y + (hh / 2 - 3 if len(lines) == 2 else hh / 2 + 5) + i * 16:.0f}" class="nt sm">{esc(line)}</text>')
        parts.append("</g>")
    for x in systems:
        sx, sy = coords_s[x["name"]]
        hh = 50 if two_col else bh
        lines = wrap_text(x["name"], maxc)
        parts.append(f'<g class="node ext"><rect x="{sx:.0f}" y="{sy:.0f}" width="{bw:.0f}" height="{hh}" rx="9"/>')
        if len(lines) == 1:
            parts.append(f'<text x="{sx + bw / 2:.0f}" y="{sy + hh / 2 - 2:.0f}" class="nt sm">{esc(lines[0])}</text>'
                         f'<text x="{sx + bw / 2:.0f}" y="{sy + hh / 2 + 15:.0f}" class="ns">{esc(x.get("kind", ""))}</text></g>')
        else:
            parts.append("".join(f'<text x="{sx + bw / 2:.0f}" y="{sy + hh / 2 - 3 + i * 16:.0f}" class="nt sm">{esc(l)}</text>' for i, l in enumerate(lines)) + "</g>")
    parts.append("</svg>")
    return "".join(parts)


def section_summary(L, data):
    pitch, findings, options, plan, scan, domains = (data.get(k) for k in ("pitch", "findings", "options", "plan", "scan", "domains"))
    out = []
    diff = data.get("diff")
    if diff:
        F = diff.get("findings", {})
        trend = "".join(f'<li>{esc(m["metric"])}{L["colon"]}{esc(m["before"])} → {esc(m["after"])} <span class="chip t-{esc(m["trend"])}">{esc(m["trend"])}</span></li>' for m in diff.get("metrics", []) if m["trend"] != "same")
        out.append(f'<div class="callout ok"><h3>{L["progress"]}</h3><p><b>{len(F.get("resolved", []))}</b> {L["resolved"]} · <b>{len(F.get("new", []))}</b> {L["new_f"]} · <b>{len(F.get("regressed", []))}</b> {L["worse"]}</p>'
                   + (f"<ul>{trend}</ul>" if trend else "") + "</div>")
    if pitch and pitch.get("headline"):
        out.append(f'<p class="headline">{md(pitch["headline"])}</p>')
    # key figures
    tiles = []
    if scan:
        t = scan.get("totals", {})
        ratio = (t.get("test_loc", 0) / t["prod_loc"]) if t.get("prod_loc") else 0
        tiles.append((f'{t.get("prod_loc", 0):,}'.replace(",", " "), L["loc"]))
        tiles.append((f"{round(ratio * 100)}\u00a0%", L["test_ratio"]))
        tiles.append((str(len(scan.get("module_cycles", []))), L["cycles"]))
        h = scan.get("history") or {}
        if h.get("fix_share") is not None and h.get("commits_analyzed", 0) >= 10:
            tiles.append((f"{round(h['fix_share'] * 100)}\u00a0%", L["fix_share"]))
    if findings:
        fs = findings.get("findings", [])
        tiles.append((str(sum(1 for f in fs if f.get("severity") in ("critical", "high"))), L["crit_high"]))
    if domains:
        tiles.append((str(len(domains.get("domains", []))), L["domains"].lower()))
    if tiles:
        out.append('<div class="tiles">' + "".join(f'<div class="tile"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for v, k in tiles) + "</div>")
    if pitch:
        if pitch.get("situation"):
            out.append(f'<h3>{L["situation"]}</h3><p>{md(pitch["situation"])}</p>')
        if pitch.get("risks"):
            rows = "".join(
                f'<tr><td data-l="{esc(L["risk"])}">{md(r.get("risk"))}</td><td data-l="{esc(L["consequence"])}">{md(r.get("consequence"))}</td>'
                f'<td data-l="{esc(L["likelihood"])}">{chip(L.get(r.get("likelihood", ""), r.get("likelihood", "")), "lk-" + esc(r.get("likelihood", "")))}</td>'
                f'<td data-l="{esc(L["evidence"])}">' + " ".join(f'<a href="#{esc(e)}">{esc(e)}</a>' for e in (r.get("evidence") if isinstance(r.get("evidence"), list) else [x.strip() for x in str(r.get("evidence") or "").split(",") if x.strip()])) + '</td></tr>'
                for r in pitch["risks"])
            out.append(f'<h3>{L["risks"]}</h3><table class="stack"><thead><tr><th>{L["risk"]}</th><th>{L["consequence"]}</th><th>{L["likelihood"]}</th><th>{L["evidence"]}</th></tr></thead><tbody>{rows}</tbody></table>')
        if pitch.get("options"):
            rows = "".join(
                f'<tr><td data-l="{esc(L["option"])}"><strong>{md(o.get("name"))}</strong></td><td data-l="{esc(L["size"])}">{size_badge(o.get("size")) if o.get("size") in SIZES else esc(o.get("size", "-"))}</td>'
                f'<td data-l="{esc(L["gain"])}">{md(o.get("gain"))}</td><td data-l="{esc(L["risk"])}">{md(o.get("risk"))}</td></tr>'
                for o in pitch["options"])
            out.append(f'<h3>{L["options"]}</h3><table class="stack"><thead><tr><th>{L["option"]}</th><th>{L["size"]}</th><th>{L["gain"]}</th><th>{L["risk"]}</th></tr></thead><tbody>{rows}</tbody></table>')
        if pitch.get("recommendation"):
            out.append(f'<div class="callout"><h3>{L["recommendation"]}</h3><p>{md(pitch["recommendation"])}</p></div>')
        inv = pitch.get("investment")
        if inv:
            out.append(f'<h3>{L["investment"]}</h3><p>{size_badge(inv.get("size"))} {md(inv.get("capacity", ""))}</p>')
            if inv.get("assumptions"):
                out.append(f'<p class="muted">{L["assumptions"]}</p>' + ul(inv["assumptions"]))
        if pitch.get("milestones"):
            out.append(f'<h3>{L["milestones"]}</h3><ol class="milestones">' + "".join(
                f'<li><b>{md(m.get("when"))}</b> {md(m.get("what"))}' + (f'<br><span class="muted">{md(m.get("indicator"))}</span>' if m.get("indicator") else "") + "</li>"
                for m in pitch["milestones"]) + "</ol>")
        if pitch.get("kpis"):
            rows = "".join(f'<tr><td data-l="KPI">{md(k.get("name"))}</td><td data-l="{esc(L["baseline"])}">{md(k.get("baseline"))}</td><td data-l="{esc(L["target"])}">{md(k.get("target"))}</td></tr>' for k in pitch["kpis"])
            out.append(f'<h3>{L["kpis"]}</h3><table class="stack"><thead><tr><th>KPI</th><th>{L["baseline"]}</th><th>{L["target"]}</th></tr></thead><tbody>{rows}</tbody></table>')
        if pitch.get("decision_requested"):
            out.append(f'<div class="callout decision"><h3>{L["decision_needed"]}</h3><p>{md(pitch["decision_requested"])}</p></div>')
        if pitch.get("glossary"):
            out.append(f'<details><summary>{L["glossary"]}</summary><dl>' + "".join(f'<dt>{esc(g.get("term"))}</dt><dd>{md(g.get("definition"))}</dd>' for g in pitch["glossary"]) + "</dl></details>")
    else:
        # minimal summary from other files
        if findings:
            top = sorted(findings.get("findings", []), key=lambda f: SEV_ORDER.get(f.get("severity"), 9))[:5]
            out.append(f'<h3>{L["findings"]}</h3><ul>' + "".join(f'<li>{chip(L.get(f.get("severity"), f.get("severity")), "sev-" + esc(f.get("severity")))} <a href="#{esc(f.get("id"))}">{md(f.get("title"))}</a></li>' for f in top) + "</ul>")
        if options:
            rec = next((o for o in options.get("options", []) if o.get("recommended")), None)
            if rec:
                out.append(f'<div class="callout"><h3>{L["recommendation"]}</h3><p><strong>{md(rec.get("name"))}</strong> {size_badge(rec.get("understanding_cost"), L["understanding"])} {size_badge(rec.get("implementation_size"), L["implementation"])}</p><p>{md(rec.get("why"))}</p></div>')
    return "".join(out)


def section_domains(L, d):
    out = []
    note = L["map_validated"] if d.get("validated_by_team") else L["map_not_validated"]
    out.append(f'<p class="muted">{esc(note)}{(" · " + md(d["method"])) if d.get("method") else ""}</p>')
    doms = d.get("domains", [])
    out.append('<figure class="mapfig">')
    out.append(f'<div class="map-wide">{domain_svg(doms, 4, L, 960)}</div>')
    out.append(f'<div class="map-narrow">{domain_svg(doms, 2, L, 420)}</div>')
    out.append('<figcaption class="legend">'
               f'<span><i class="sw k-core"></i>{L["core"]}</span><span><i class="sw k-supporting"></i>{L["supporting"]}</span>'
               f'<span><i class="sw k-generic"></i>{L["generic"]}</span><span><i class="sw k-technical"></i>{L["technical"]}</span>'
               f'<span><i class="ln"></i>{L["legend_dep"]}</span><span><i class="ln mutual"></i>{L["legend_both"]}</span><span><i class="ln dashed"></i>{L["legend_runtime"]}</span>'
               f'<span><i class="sw dashed"></i>{L["low_conf"]}</span></figcaption></figure>')
    systems = d.get("external_systems") or []
    if systems:
        out.append(f'<h3>{L["context_view"]}</h3><figure class="mapfig"><div class="map-wide">{context_svg(doms, systems, L, 960, 5)}</div>'
                   f'<div class="map-narrow">{context_svg(doms, systems, L, 420, 2)}</div></figure>')
    cards = []
    names = {x["id"]: x.get("name", x["id"]) for x in doms}
    for dm in doms:
        deps = "".join(
            f'<li><strong>{esc(names.get(x.get("id"), x.get("id")))}</strong> <span class="muted">({esc(L.get(x.get("kind"), x.get("kind", "")))})</span>{(" " + md(x.get("note"))) if x.get("note") else ""}</li>'
            for x in dm.get("depends_on", []))
        files = dm.get("files", [])
        flist = "".join(f"<li><code>{esc(f)}</code></li>" for f in files[:40]) + (f'<li class="muted">… +{len(files) - 40}</li>' if len(files) > 40 else "")
        cards.append(
            f'<article class="card dom k-{esc(dm.get("kind", ""))}" id="dom-{esc(dm["id"])}">'
            f'<header><h3>{esc(dm.get("name", dm["id"]))}</h3>{chip(L.get(dm.get("kind"), dm.get("kind", "")), "kind k-" + esc(dm.get("kind", "")))}'
            f'{chip(L["confidence"] + " " + L.get(dm.get("confidence"), dm.get("confidence", "")), "conf c-" + esc(dm.get("confidence", "")))}</header>'
            f'<p>{md(dm.get("description"))}</p>'
            + (f'<p class="muted">{md(dm.get("confidence_reason"))}</p>' if dm.get("confidence_reason") else "")
            + (f'<p><b>{L["entities"]}</b> {", ".join(esc(e) for e in dm.get("entities", []))}</p>' if dm.get("entities") else "")
            + (f'<p><b>{L["depends_on"]}</b></p><ul>{deps}</ul>' if deps else "")
            + (f'<details><summary>{L["files"]} ({len(files)}, {esc(dm.get("loc", "?"))} loc)</summary><ul class="files">{flist}</ul></details>' if files else "")
            + "</article>")
    out.append('<div class="cards">' + "".join(cards) + "</div>")
    if d.get("fuzzy_zones"):
        out.append(f'<h3>{L["fuzzy"]}</h3><div class="cards">' + "".join(
            f'<article class="card fuzzy"><h4>{md(z.get("title"))}</h4><p>{md(z.get("detail"))}</p>' + ("<ul class=\"files\">" + "".join(f"<li><code>{esc(f)}</code></li>" for f in z.get("files", [])[:12]) + "</ul>" if z.get("files") else "") + "</article>"
            for z in d["fuzzy_zones"]) + "</div>")
    if d.get("shared"):
        out.append(f'<h3>{L["shared"]}</h3><ul>' + "".join(f'<li><code>{esc(s.get("path"))}</code> {md(s.get("role"))}</li>' for s in d["shared"]) + "</ul>")
    return "".join(out)


def section_diagnosis(L, f, domains):
    out = []
    names = {x["id"]: x.get("name", x["id"]) for x in (domains or {}).get("domains", [])}
    if f.get("strengths"):
        out.append(f'<div class="callout ok"><h3>{L["strengths"]}</h3>{ul(f["strengths"])}</div>')
    fs = sorted(f.get("findings", []), key=lambda x: SEV_ORDER.get(x.get("severity"), 9))
    counts = collections.Counter(x.get("severity") for x in fs)
    btns = [f'<button type="button" class="flt on" data-sev="all">{L["all"]} ({len(fs)})</button>']
    for s in ("critical", "high", "medium", "low"):
        if counts.get(s):
            btns.append(f'<button type="button" class="flt" data-sev="{s}">{esc(L[s])} ({counts[s]})</button>')
    out.append(f'<div class="filters" role="group" aria-label="{esc(L["severity"])}">' + "".join(btns) + "</div>")
    items = []
    for x in fs:
        sev = x.get("severity", "medium")
        ev = "".join(
            f'<li><code>{esc(e.get("file"))}{(":" + esc(e.get("line"))) if e.get("line") else ""}</code> {md(e.get("detail"))}</li>'
            for e in x.get("evidence", []))
        doms = ", ".join(esc(names.get(dd, dd)) for dd in x.get("domains", []))
        items.append(
            f'<details class="finding sev-{esc(sev)}" id="{esc(x.get("id"))}" data-sev="{esc(sev)}">'
            f'<summary><span class="fid">{esc(x.get("id"))}</span>{chip(L.get(sev, sev), "sev-" + esc(sev))}'
            + (f'<span class="fixsz" title="{esc(L["fix_size"])}">{esc(L["fix_size"])} {size_badge(x.get("fix_size"))}</span>' if x.get("fix_size") in SIZES else "")
            + f'<span class="ftitle">{md(x.get("title"))}</span>'
            + (f'<span class="muted fdom">{doms}</span>' if doms else "") + "</summary>"
            f'<div class="fbody"><h4>{L["evidence"]}</h4><ul class="evidence">{ev}</ul>'
            f'<div class="two"><div><h4>{L["impact_tech"]}</h4><p>{md(x.get("impact_tech"))}</p></div>'
            f'<div><h4>{L["impact_business"]}</h4><p>{md(x.get("impact_business"))}</p></div></div>'
            f'<h4>{L["fix"]}</h4><p>{md(x.get("recommendation"))}</p>'
            + (f'<p class="muted">{esc(L["debt"].get(x.get("debt_intent"), x.get("debt_intent")))}</p>' if x.get("debt_intent") else "")
            + '</div></details>')
    out.append('<div class="findings">' + "".join(items) + "</div>")
    if f.get("open_questions"):
        out.append(f'<div class="callout"><h3>{L["open_questions"]}</h3>{ul(f["open_questions"])}</div>')
    if f.get("non_findings"):
        out.append(f'<h3>{L["non_findings"]}</h3><div class="cards">' + "".join(
            f'<article class="card fine"><h4>{md(n.get("title"))}</h4><p>{md(n.get("why"))}</p>'
            + ("<ul class=\"files\">" + "".join(f"<li><code>{esc(x)}</code></li>" for x in n.get("files", [])[:6]) + "</ul>" if n.get("files") else "") + "</article>"
            for n in f["non_findings"]) + "</div>")
    return "".join(out)


def section_options(L, o):
    out = []
    ctx = o.get("context") or {}
    if ctx:
        out.append('<dl class="ctx">' + (f'<dt>{L["domain_complexity"]}</dt><dd>{md(ctx.get("domain_complexity"))}</dd>' if ctx.get("domain_complexity") else "")
                   + (f'<dt>{L["team"]}</dt><dd>{md(ctx.get("team"))}</dd>' if ctx.get("team") else "")
                   + (f'<dt>{L["constraints"]}</dt><dd>{ul(ctx.get("constraints"))}</dd>' if ctx.get("constraints") else "") + "</dl>")
    qs = o.get("quality_scenarios") or []
    if qs:
        ops = o.get("options", [])
        head = "".join(f"<th>{esc(op.get('id'))}</th>" for op in ops)
        rows = ""
        for q in qs:
            cells = ""
            for op in ops:
                v = (op.get("scenario_fit") or {}).get(q.get("id"), "")
                cells += f'<td data-l="{esc(op.get("id"))} {esc(op.get("name", ""))[:40]}"><span class="fit fit{ {"+": "p", "0": "z", "-": "m"}.get(v, "z") }">{esc(L["fit"].get(v, v or "?"))}</span></td>'
            rows += f'<tr><td data-l="{esc(L["scenario"])}"><b>{esc(q.get("id"))}</b> {md(q.get("driver"))}<br><span class="muted">{md(q.get("scenario"))}</span></td>{cells}</tr>'
        out.append(f'<h3>{L["quality"]}</h3><table class="stack"><thead><tr><th>{L["scenario"]}</th>{head}</tr></thead><tbody>{rows}</tbody></table>')
    out.append(f'<p class="muted scale">{L["size_scale"]}</p>')
    dec = o.get("decision") or {}
    cards = []
    for op in o.get("options", []):
        badges = ""
        if dec.get("chosen") == op.get("id"):
            badges += chip(L["chosen"] if dec.get("by") == "team" else L["assumed"], "chosen")
        elif op.get("recommended"):
            badges += chip(L["recommended"], "rec")
        ud = op.get("understanding_detail") or {}
        per = op.get("per_domain") or []
        cards.append(
            f'<article class="card option{" is-rec" if op.get("recommended") else ""}{" is-chosen" if dec.get("chosen") == op.get("id") else ""}" id="{esc(op.get("id"))}">'
            f'<header><span class="fid">{esc(op.get("id"))}</span><h3>{md(op.get("name"))}</h3>{badges}</header>'
            f'<p>{md(op.get("summary"))}</p>'
            f'<div class="sizes"><div><span class="lbl">{L["understanding"]}</span>{size_badge(op.get("understanding_cost"))}</div>'
            f'<div><span class="lbl">{L["implementation"]}</span>{size_badge(op.get("implementation_size"))}</div></div>'
            + (f'<p><b>{L["concepts"]}</b> {", ".join(esc(c) for c in ud.get("concepts", []))}</p>' if ud.get("concepts") else "")
            + (f'<p><b>{L["hops"]}</b> <code class="wrap">{esc(ud.get("indirections"))}</code></p>' if ud.get("indirections") else "")
            + (f'<p class="muted">{md(op.get("implementation_detail"))}</p>' if op.get("implementation_detail") else "")
            + (f'<p><b>{L["per_domain"]}</b></p><ul>' + "".join(f'<li>{esc(p.get("domain"))}{L["colon"]}{esc(p.get("style"))}</li>' for p in per) + "</ul>" if per else "")
            + f'<div class="two"><div><h4>{L["benefits"]}</h4>{ul(op.get("benefits"))}</div><div><h4>{L["drawbacks"]}</h4>{ul(op.get("drawbacks"))}</div></div>'
            + (f'<p><b>{L["signals"]}</b> {", ".join(md(s) for s in op.get("signals", []))}</p>' if op.get("signals") else "")
            + (f'<p><b>{L["addresses"]}</b> {" ".join(f"<a href=#{esc(a)}>{esc(a)}</a>" for a in op.get("addresses", []))}</p>' if op.get("addresses") else "")
            + (f'<p><b>{L["not_addresses"]}</b> {" ".join(f"<a href=#{esc(a)}>{esc(a)}</a>" for a in op.get("does_not_address", []))}</p>' if op.get("does_not_address") else "")
            + (f'<p><b>{L["tradeoffs"]}</b> {md(op.get("tradeoffs"))}</p>' if op.get("tradeoffs") else "")
            + (f'<p class="why"><b>{L["why"]}</b> {md(op.get("why"))}</p>' if op.get("why") else "")
            + "</article>")
    out.append('<div class="cards options">' + "".join(cards) + "</div>")
    if dec.get("note"):
        out.append(f'<p class="muted">{md(dec["note"])}</p>')
    if o.get("prerequisites"):
        out.append(f'<div class="callout decision"><h3>{L["prerequisites"]}</h3><ul>' + "".join(
            f'<li><strong>{md(x.get("title"))}</strong> {size_badge(x.get("size")) if x.get("size") in SIZES else ""}<br><span class="muted">{md(x.get("why"))}</span></li>'
            for x in o["prerequisites"]) + "</ul></div>")
    if o.get("opportunities"):
        out.append(f'<h3>{L["opportunities"]}</h3><ul>' + "".join(f'<li><strong>{md(x.get("pattern"))}</strong>{L["colon"]}{md(x.get("where"))} <span class="muted">({md(x.get("signal"))})</span></li>' for x in o["opportunities"]) + "</ul>")
    if o.get("rejected"):
        out.append(f'<h3>{L["rejected"]}</h3><ul>' + "".join(f'<li><strong>{md(x.get("style"))}</strong>{L["colon"]}{md(x.get("why"))}</li>' for x in o["rejected"]) + "</ul>")
    return "".join(out)


def steps_html(L, steps):
    items = []
    for st in steps or []:
        if isinstance(st, dict):
            body = md(st.get("do"))
            if st.get("moves"):
                body += "<ul>" + "".join(f'<li><code class="wrap">{esc(m.get("from"))}</code> → <code class="wrap">{esc(m.get("to"))}</code></li>' for m in st["moves"]) + "</ul>"
            if st.get("verify"):
                body += f'<br><span class="muted">{esc(L["verify"])}</span> <code class="wrap">{esc(st["verify"])}</code>'
            items.append(f"<li>{body}</li>")
        else:
            items.append(f"<li>{md(st)}</li>")
    return f'<ul class="checks">{"".join(items)}</ul>' if items else ""


def section_plan(L, p):
    out = []
    if p.get("sequencing_rationale"):
        out.append(f'<p><b>{L["sequencing"]}</b> {md(p["sequencing_rationale"])}</p>')
    out.append(f'<p class="muted scale">{L["size_scale"]}</p><ol class="timeline">')
    for ph in p.get("phases", []):
        out.append(
            f'<li class="phase{" stop" if ph.get("stop_point") else ""}" id="{esc(ph.get("id"))}"><div class="dot"></div><div class="pbody">'
            f'<header><span class="fid">{esc(ph.get("id"))}</span><h3>{md(ph.get("name"))}</h3>{size_badge(ph.get("size"))}'
            + (chip(L["status"].get(ph.get("status"), ph.get("status")), "st-" + esc((ph.get("status") or "").replace(" ", "-"))) if ph.get("status") else "")
            + '</header>'
            f'<p>{md(ph.get("goal"))}</p>'
            + (f'<p class="muted">{L["size"]} {esc(ph.get("size"))}{L["colon"]}{md(ph.get("size_rationale"))}</p>' if ph.get("size_rationale") else "")
            + (f'<p class="meta">{L["depends"]} {", ".join(esc(x) for x in ph.get("depends_on", []))}</p>' if ph.get("depends_on") else "")
            + (f'<p class="meta">{" ".join(f"<a href=#{esc(x)}>{esc(x)}</a>" for x in ph.get("findings", []))}</p>' if ph.get("findings") else "")
            + f'<details><summary>{L["steps"]} ({len(ph.get("steps", []))})</summary>{steps_html(L, ph.get("steps", []))}</details>'
            + (f'<h4>{L["exit"]}</h4>{ul(ph.get("exit_criteria"), "checks")}' if ph.get("exit_criteria") else "")
            + (f'<p><b>{L["rollback"]}</b> {md(ph.get("rollback"))}</p>' if ph.get("rollback") else "")
            + (f'<p><b>{L["risks"]}</b></p>{ul(ph.get("risks"))}' if ph.get("risks") else "")
            + (f'<p class="stopnote">{L["stop_point"]}</p>' if ph.get("stop_point") else "")
            + "</div></li>")
    out.append("</ol>")
    if p.get("assumptions"):
        out.append(f'<h3>{L["assumptions"]}</h3>' + ul(p["assumptions"]))
    if p.get("out_of_scope"):
        out.append(f'<h3>{L["out_of_scope"]}</h3>' + ul(p["out_of_scope"]))
    return "".join(out)


def section_academy(L, a):
    out = []
    mods = {m.get("id"): m for m in a.get("modules", [])}
    if a.get("path"):
        out.append(f'<h3>{L["path"]}</h3><ol class="milestones">' + "".join(
            f'<li><b>{md(s.get("when"))}</b> ' + ", ".join(f'<a href="#{esc(mid)}">{esc(mid)} {esc(mods.get(mid, {}).get("title", ""))}</a>' for mid in s.get("modules", [])) + "</li>"
            for s in a["path"]) + "</ol>")
    cards = []
    for m in a.get("modules", []):
        cards.append(
            f'<article class="card" id="{esc(m.get("id"))}"><header><span class="fid">{esc(m.get("id"))}</span><h3>{md(m.get("title"))}</h3>{chip(m.get("level", ""), "lvl")}</header>'
            f'<p class="muted">{esc(m.get("audience", ""))}{" · " + esc(m.get("duration")) if m.get("duration") else ""}</p>'
            f'<p>{md(m.get("why_here"))}</p>'
            + (f'<p><b>{L["concepts"]}</b> {", ".join(esc(c) for c in m.get("concepts", []))}</p>' if m.get("concepts") else "")
            + (f'<p><code class="wrap">{esc(m.get("file"))}</code></p>' if m.get("file") else "") + "</article>")
    out.append(f'<h3>{L["modules"]}</h3><div class="cards">' + "".join(cards) + "</div>")
    if a.get("reading"):
        out.append(f'<h3>{L["reading"]}</h3><ul>' + "".join(f'<li><strong>{md(r.get("title"))}</strong>, {esc(r.get("author", ""))}{L["colon"]}{md(r.get("why"))}</li>' for r in a["reading"]) + "</ul>")
    return "".join(out)


def section_guardrails(L, g):
    out = []
    if g.get("rules"):
        rows = "".join(
            f'<tr><td data-l="#">{esc(r.get("id"))}</td><td data-l="{esc(L["rules"])}">{md(r.get("rule"))}</td><td data-l="{esc(L["enforced_by"])}">{md(r.get("enforced_by"))}</td>'
            f'<td data-l="{esc(L["mode"])}">{md(r.get("mode", ""))}</td><td data-l="{esc(L["violations"])}">{esc(r.get("current_violations", ""))}</td></tr>'
            for r in g["rules"])
        out.append(f'<h3>{L["rules"]}</h3><table class="stack"><thead><tr><th>#</th><th>{L["rules"]}</th><th>{L["enforced_by"]}</th><th>{L["mode"]}</th><th>{L["violations"]}</th></tr></thead><tbody>{rows}</tbody></table>')
    if g.get("files"):
        out.append(f'<h3>{L["files"]}</h3><ul>' + "".join(f'<li><code class="wrap">{esc(f.get("path"))}</code> {md(f.get("purpose"))}</li>' for f in g["files"]) + "</ul>")
    return "".join(out)


def section_appendix(L, scan, domains):
    out = []
    if scan and scan.get("graph_sources"):
        out.append(f'<h3>{L["graph_sources"]}</h3><ul>' + "".join(f"<li><b>{esc(k)}</b>{L['colon']}{md(v)}</li>" for k, v in scan["graph_sources"].items()) + "</ul>")
    if scan and scan.get("build_units"):
        out.append(f'<details><summary>{L["units"]} ({len(scan["build_units"])})</summary><ul>' + "".join(
            f'<li><code class="wrap">{esc(u["name"])}</code> <span class="muted">{esc(u["kind"])}</span> → {esc(", ".join(u.get("deps", [])) or "-")}</li>' for u in scan["build_units"][:60]) + "</ul></details>")
    di = (scan or {}).get("di") or {}
    if di.get("bindings"):
        rows = "".join(f'<tr><td data-l="{esc(L["abstraction"])}"><code class="wrap">{esc(b["abstraction"])}</code></td><td data-l="{esc(L["implementation_h"])}"><code class="wrap">{esc(b["implementation_file"])}</code></td>'
                       f'<td data-l="{esc(L["registered"])}">{esc(b.get("registered_in") or b.get("kind"))}</td></tr>' for b in di["bindings"][:40])
        out.append(f'<h3>{L["di"]}</h3><table class="stack"><thead><tr><th>{L["abstraction"]}</th><th>{L["implementation_h"]}</th><th>{L["registered"]}</th></tr></thead><tbody>{rows}</tbody></table>')
    k = (scan or {}).get("knowledge") or {}
    if k and (k.get("islands_in_hotspots") or k.get("orphaned_files")):
        out.append(f'<h3>{L["knowledge"]}</h3><p class="muted">{esc(k.get("note", ""))}</p>')
        if k.get("islands_in_hotspots"):
            out.append(f'<p><b>{L["islands"]}</b></p><ul>' + "".join(f'<li><code class="wrap">{esc(i["path"])}</code> {esc(i["main_author"])} {int(i["main_share"] * 100)}\u00a0%</li>' for i in k["islands_in_hotspots"][:10]) + "</ul>")
        if k.get("orphaned_files"):
            out.append(f'<p><b>{L["orphaned"]}</b></p><ul>' + "".join(f'<li><code class="wrap">{esc(i["path"])}</code> ({esc(i["loc"])} loc)</li>' for i in k["orphaned_files"][:10]) + "</ul>")
    h = (scan or {}).get("dependency_hygiene") or {}
    if any(h.get(x) for x in ("same_job", "undeclared", "declared_unused")):
        out.append(f'<h3>{L["hygiene"]}</h3>')
        if h.get("same_job"):
            out.append(f'<p><b>{L["same_job"]}</b></p><ul>' + "".join(f'<li>{esc(d["job"])}{L["colon"]}{esc(", ".join(d["libraries"]))}</li>' for d in h["same_job"]) + "</ul>")
        if h.get("undeclared"):
            out.append(f'<p><b>{L["undeclared"]}</b></p><ul>' + "".join(f'<li><code>{esc(d["package"])}</code> <span class="muted">{esc(d["status"])}</span></li>' for d in h["undeclared"][:15]) + "</ul>")
        if h.get("declared_unused"):
            out.append(f'<p><b>{L["unused"]}</b> ' + ", ".join(f"<code>{esc(d['package'])}</code>" for d in h["declared_unused"][:20]) + "</p>")
    if scan and scan.get("routes"):
        groups = collections.Counter(route_resource(r["path"]) for r in scan["routes"])
        out.append(f'<h3>{L["routes"]}</h3><p>' + ", ".join(f"<code>{esc(g)}</code> {n}" for g, n in groups.most_common(30)) + "</p>")
    if scan:
        hs = scan.get("hotspots", [])[:15]
        if hs:
            rows = "".join(f'<tr><td data-l="{esc(L["file"])}"><code class="wrap">{esc(h["path"])}</code></td><td data-l="{esc(L["score"])}">{h["score"]}</td><td data-l="loc">{h["loc"]}</td>'
                           f'<td data-l="{esc(L["branches"])}">{h["branches"]}</td><td data-l="{esc(L["churn"])}">{h["churn"] if h["churn"] is not None else "-"}</td><td data-l="{esc(L["fan_in"])}">{h["fan_in"]}</td></tr>' for h in hs)
            out.append(f'<h3>{L["hotspots"]}</h3><table class="stack"><thead><tr><th>{L["file"]}</th><th>{L["score"]}</th><th>loc</th><th>{L["branches"]}</th><th>{L["churn"]}</th><th>{L["fan_in"]}</th></tr></thead><tbody>{rows}</tbody></table>')
        mods = scan.get("modules", [])[:25]
        if mods:
            rows = "".join(f'<tr><td data-l="module"><code class="wrap">{esc(m["name"])}</code></td><td data-l="loc">{m["loc"]}</td><td data-l="tests">{m["test_files"]}</td>'
                           f'<td data-l="Ca">{m["afferent"]}</td><td data-l="Ce">{m["efferent"]}</td><td data-l="I">{m["instability"] if m["instability"] is not None else "-"}</td></tr>' for m in mods)
            out.append(f'<h3>{L["module_table"]}</h3><table class="stack"><thead><tr><th>module</th><th>loc</th><th>tests</th><th>Ca</th><th>Ce</th><th>I</th></tr></thead><tbody>{rows}</tbody></table>')
        cyc = scan.get("module_cycles", [])
        if cyc:
            out.append(f'<h3>{L["cycles"]}</h3><ul>' + "".join(f'<li><code class="wrap">{esc(" → ".join(c.get("example") or c["modules"]))}</code></li>' for c in cyc[:15]) + "</ul>")
        if scan.get("limits"):
            out.append(f'<h3>{L["limits"]}</h3>' + ul(scan["limits"]))
    return "".join(out)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

CSS = r"""
:root{--bg:#f7f6f2;--surface:#fff;--ink:#1d1f23;--muted:#5d6370;--line:#e2e0d8;--accent:#2f5d8a;--accent-soft:#e6eef6;
--crit:#9b1c1c;--crit-soft:#fbe9e9;--high:#b4530f;--high-soft:#fcefe2;--med:#8a6a00;--med-soft:#faf3d9;--low:#3f6b4e;--low-soft:#e7f2ea;
--core:#2f5d8a;--supporting:#5f7f5a;--generic:#8a7a5d;--technical:#7a7f8a;--ok-soft:#e7f2ea;--code:#f0eee8;--shadow:0 1px 2px rgba(0,0,0,.05)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15171b;--surface:#1d2026;--ink:#e8e6e1;--muted:#a0a6b1;--line:#30343c;--accent:#7fb0e0;--accent-soft:#1f2c3a;
--crit:#f08a8a;--crit-soft:#3a1f22;--high:#f0a868;--high-soft:#3a2a1c;--med:#e3c55a;--med-soft:#33301c;--low:#8cc79f;--low-soft:#1d3125;
--core:#7fb0e0;--supporting:#9cc493;--generic:#c9b68f;--technical:#a6abb6;--ok-soft:#1d3125;--code:#262a31}}
:root[data-theme="dark"]{--bg:#15171b;--surface:#1d2026;--ink:#e8e6e1;--muted:#a0a6b1;--line:#30343c;--accent:#7fb0e0;--accent-soft:#1f2c3a;
--crit:#f08a8a;--crit-soft:#3a1f22;--high:#f0a868;--high-soft:#3a2a1c;--med:#e3c55a;--med-soft:#33301c;--low:#8cc79f;--low-soft:#1d3125;
--core:#7fb0e0;--supporting:#9cc493;--generic:#c9b68f;--technical:#a6abb6;--ok-soft:#1d3125;--code:#262a31}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;overflow-x:hidden}
a{color:var(--accent)}
code{font:0.88em/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--code);padding:.1em .35em;border-radius:4px;overflow-wrap:anywhere;word-break:break-word}
code.wrap{white-space:normal}
h1,h2,h3,h4{line-height:1.25;margin:1.4em 0 .5em}
h1{font-size:1.6rem;margin:0}
h2{font-size:1.35rem;margin-top:0}
h3{font-size:1.08rem}
h4{font-size:.95rem;color:var(--muted);margin:1em 0 .3em}
.wrapper{max-width:1100px;margin:0 auto;padding:0 16px}
header.top{padding:28px 0 18px;border-bottom:1px solid var(--line);background:var(--surface)}
header.top .kicker{color:var(--muted);font-size:.85rem;letter-spacing:.04em;text-transform:uppercase}
header.top .meta{color:var(--muted);font-size:.9rem;margin-top:6px;display:flex;flex-wrap:wrap;gap:4px 14px}
nav.tabs{position:sticky;top:0;z-index:10;background:var(--surface);border-bottom:1px solid var(--line)}
nav.tabs .wrapper{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
nav.tabs .wrapper::-webkit-scrollbar{display:none}
nav.tabs a{flex:0 0 auto;padding:12px 12px;color:var(--muted);text-decoration:none;font-weight:600;font-size:.92rem;border-bottom:3px solid transparent;white-space:nowrap}
nav.tabs a.on,nav.tabs a:hover{color:var(--ink);border-bottom-color:var(--accent)}
main{padding:24px 0 60px}
section.panel{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:22px 20px;margin:0 0 22px;box-shadow:var(--shadow);min-width:0}
.js section.panel{display:none}.js section.panel.on{display:block}
.headline{font-size:1.2rem;font-weight:600;margin:0 0 16px}
.muted{color:var(--muted)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:8px 0 6px}
.tile{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px}
.tile b{display:block;font-size:1.5rem;font-variant-numeric:tabular-nums}
.tile span{color:var(--muted);font-size:.85rem}
.callout{border-left:4px solid var(--accent);background:var(--accent-soft);padding:4px 16px 8px;border-radius:0 10px 10px 0;margin:18px 0}
.callout h3{margin-top:.8em}
.callout.decision{border-color:var(--high);background:var(--high-soft)}
.callout.ok{border-color:var(--low);background:var(--ok-soft)}
table{width:100%;border-collapse:collapse;font-size:.93rem;margin:6px 0 10px}
th,td{text-align:left;vertical-align:top;padding:9px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:.85rem}
.chip{display:inline-block;font-size:.76rem;font-weight:600;padding:2px 8px;border-radius:999px;background:var(--bg);border:1px solid var(--line);white-space:nowrap;vertical-align:middle}
.sev-critical.chip,.chip.lk-high{background:var(--crit-soft);color:var(--crit);border-color:transparent}
.sev-high.chip{background:var(--high-soft);color:var(--high);border-color:transparent}
.sev-medium.chip,.chip.lk-medium{background:var(--med-soft);color:var(--med);border-color:transparent}
.sev-low.chip,.chip.lk-low{background:var(--low-soft);color:var(--low);border-color:transparent}
.chip.rec{background:var(--accent-soft);color:var(--accent);border-color:transparent}
.chip.chosen{background:var(--accent);color:var(--surface);border-color:transparent;white-space:normal}
.chip.kind.k-core{color:var(--core)}.chip.kind.k-supporting{color:var(--supporting)}.chip.kind.k-generic{color:var(--generic)}.chip.kind.k-technical{color:var(--technical)}
.size{display:inline-flex;align-items:center;gap:6px;font-weight:700;vertical-align:middle}
.size b{min-width:1.6em}
.size .bars{display:inline-flex;gap:2px}
.size .bars i{width:10px;height:10px;border-radius:2px;background:var(--line)}
.size .bars i.on{background:var(--accent)}
.size-xl .bars i.on{background:var(--high)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));gap:14px;margin-top:12px}
.cards.options{grid-template-columns:repeat(auto-fill,minmax(min(100%,330px),1fr))}
.card{border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:var(--surface);min-width:0}
.card header{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px}
.card header h3,.card header h4{margin:0;flex:1 1 160px}
.card.dom{border-top:4px solid var(--technical)}
.card.dom.k-core{border-top-color:var(--core)}.card.dom.k-supporting{border-top-color:var(--supporting)}.card.dom.k-generic{border-top-color:var(--generic)}
.card.fuzzy{border-style:dashed}
.card.option.is-rec{border-color:var(--accent)}
.card.option.is-chosen{border-width:2px;border-color:var(--accent)}
.fid{font:600 .8rem ui-monospace,Menlo,monospace;color:var(--muted)}
.sizes{display:flex;flex-wrap:wrap;gap:10px 24px;background:var(--bg);border-radius:8px;padding:10px 12px;margin:10px 0}
.sizes .lbl{display:block;font-size:.78rem;color:var(--muted)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}
.two>div{min-width:0}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0}
.flt{font:inherit;font-size:.85rem;padding:5px 12px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer}
.flt.on{background:var(--ink);color:var(--surface);border-color:var(--ink)}
details{margin:6px 0}
summary{cursor:pointer}
.finding{border:1px solid var(--line);border-left:4px solid var(--line);border-radius:10px;margin:8px 0;background:var(--surface)}
.finding.sev-critical{border-left-color:var(--crit)}.finding.sev-high{border-left-color:var(--high)}.finding.sev-medium{border-left-color:var(--med)}.finding.sev-low{border-left-color:var(--low)}
.finding>summary{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px;padding:12px 14px;list-style:none}
.finding>summary::-webkit-details-marker{display:none}
.finding>summary::before{content:"▸";color:var(--muted);font-size:.8rem}
.finding[open]>summary::before{content:"▾"}
.ftitle{flex:1 1 220px;font-weight:600;min-width:0}
.fdom{font-size:.85rem;width:100%;padding-left:1.1rem}
.fbody{padding:0 16px 14px}
ul.evidence,ul.files{padding-left:1.1rem}
ul.evidence li,ul.files li{margin:4px 0}
ul.checks{list-style:none;padding-left:0}
ul.checks li{padding-left:1.6em;position:relative;margin:5px 0}
ul.checks li::before{content:"";position:absolute;left:0;top:.25em;width:1em;height:1em;border:1.5px solid var(--muted);border-radius:3px}
ol.timeline{list-style:none;padding:0;margin:10px 0;position:relative}
ol.timeline::before{content:"";position:absolute;left:9px;top:6px;bottom:6px;width:2px;background:var(--line)}
.phase{position:relative;padding-left:34px;margin:0 0 18px}
.phase .dot{position:absolute;left:2px;top:14px;width:16px;height:16px;border-radius:50%;background:var(--surface);border:3px solid var(--accent)}
.phase.stop .dot{background:var(--accent)}
.pbody{border:1px solid var(--line);border-radius:12px;padding:12px 16px;min-width:0}
.pbody header{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px}
.pbody header h3{margin:0;flex:1 1 180px}
.meta{font-size:.85rem;color:var(--muted)}
.stopnote{font-weight:600;color:var(--accent)}
ol.milestones{padding-left:1.2rem}
ol.milestones li{margin:6px 0}
dl.ctx dt{font-weight:600;margin-top:8px}
dl.ctx dd{margin:2px 0 0}
.mapfig{margin:14px 0}
.dmap{width:100%;height:auto;display:block}
.map-narrow{display:none}
@media (max-width:640px){.map-wide{display:none}.map-narrow{display:block}}
.dmap .node rect{fill:var(--surface);stroke:var(--technical);stroke-width:2}
.dmap .node.k-core rect{stroke:var(--core);stroke-width:3;fill:var(--accent-soft)}
.dmap .node.k-supporting rect{stroke:var(--supporting)}
.dmap .node.k-generic rect{stroke:var(--generic)}
.dmap .node.c-low rect{stroke-dasharray:6 4}
.dmap .nt{font:600 16px ui-sans-serif,system-ui,sans-serif;fill:var(--ink);text-anchor:middle}
.dmap .ns{font:12px ui-sans-serif,system-ui,sans-serif;fill:var(--muted);text-anchor:middle}
.dmap .edge{fill:none;stroke:var(--muted);stroke-width:1.6;opacity:.75}
.dmap .edge.mutual{stroke:var(--high);stroke-width:2.2;opacity:1}
.dmap .edge.runtime{stroke-dasharray:5 4}
.dmap .ah{fill:var(--muted)}.dmap .ahw{fill:var(--high)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.82rem;color:var(--muted);margin-top:8px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend .sw{width:14px;height:14px;border-radius:3px;border:2px solid var(--technical);display:inline-block}
.legend .sw.k-core{border-color:var(--core);background:var(--accent-soft)}.legend .sw.k-supporting{border-color:var(--supporting)}.legend .sw.k-generic{border-color:var(--generic)}
.legend .sw.dashed{border-style:dashed}
.legend .ln{width:22px;height:0;border-top:2px solid var(--muted);display:inline-block}
.legend .ln.mutual{border-top-color:var(--high)}
.legend .ln.dashed{border-top-style:dashed}
.dmap .appframe{fill:none;stroke:var(--line);stroke-width:2;stroke-dasharray:6 5}
.dmap .frame-label{font:600 13px ui-sans-serif,system-ui,sans-serif;fill:var(--muted)}
.dmap .nt.sm{font-size:14px}
.dmap .node.ext rect{fill:var(--bg);stroke:var(--muted);stroke-width:1.6}
.card.fine{border-left:4px solid var(--low)}
.fixsz{font-size:.78rem;color:var(--muted);display:inline-flex;align-items:center;gap:4px}
.fixsz .size .bars i{width:7px;height:7px}
.fit{display:inline-block;font-size:.8rem;font-weight:600;padding:2px 8px;border-radius:999px}
.fitp{background:var(--low-soft);color:var(--low)}.fitz{background:var(--bg);color:var(--muted)}.fitm{background:var(--crit-soft);color:var(--crit)}
.chip.t-better{background:var(--low-soft);color:var(--low)}.chip.t-worse{background:var(--crit-soft);color:var(--crit)}
.chip.st-done{background:var(--low-soft);color:var(--low)}.chip.st-in-progress{background:var(--accent-soft);color:var(--accent)}
.assume{margin-top:10px;font-size:.9rem;background:var(--med-soft);border-radius:8px;padding:6px 12px}
.assume ul{margin:6px 0}
footer{color:var(--muted);font-size:.85rem;padding:20px 0 40px}
.toolbar{display:flex;gap:8px;margin-top:12px}
.toolbar button{font:inherit;font-size:.85rem;padding:6px 12px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);cursor:pointer}
@media (max-width:640px){
 section.panel{padding:16px 14px;border-radius:12px}
 .two{grid-template-columns:1fr}
 table.stack thead{display:none}
 table.stack,table.stack tbody,table.stack tr,table.stack td{display:block;width:100%}
 table.stack tr{border:1px solid var(--line);border-radius:10px;margin:0 0 10px;padding:6px 10px}
 table.stack td{border:none;padding:4px 0}
 table.stack td::before{content:attr(data-l);display:block;font-size:.75rem;color:var(--muted);font-weight:600}
 h1{font-size:1.35rem}
}
@media print{
 nav.tabs,.toolbar,.filters{display:none!important}
 .js section.panel{display:block!important}
 section.panel{box-shadow:none;break-inside:auto}
 details{display:block}details>*{display:block}
 body{background:#fff}
}
"""

JS = r"""
document.documentElement.classList.add('js');
(function(){
 var tabs=[].slice.call(document.querySelectorAll('nav.tabs a'));
 var panels=[].slice.call(document.querySelectorAll('section.panel'));
 function show(id,scroll){
  var found=false;
  panels.forEach(function(p){var on=p.id===id;p.classList.toggle('on',on);if(on)found=true;});
  if(!found&&panels.length){panels[0].classList.add('on');id=panels[0].id;}
  tabs.forEach(function(t){var on=t.getAttribute('href')==='#'+id;t.classList.toggle('on',on);if(on&&t.scrollIntoView){t.scrollIntoView({block:'nearest',inline:'nearest'});}});
  if(scroll)window.scrollTo(0,0);
 }
 function route(){
  var h=decodeURIComponent(location.hash.slice(1));
  if(!h){show(panels.length?panels[0].id:'',false);return;}
  var el=document.getElementById(h);
  if(!el){show(panels[0].id,false);return;}
  var panel=el.closest('section.panel');
  if(!panel)return;
  show(panel.id,el===panel);
  if(el!==panel){if(el.tagName==='DETAILS')el.open=true;setTimeout(function(){el.scrollIntoView({block:'start'});},0);}
 }
 window.addEventListener('hashchange',route);route();
 [].slice.call(document.querySelectorAll('.filters')).forEach(function(f){
  f.addEventListener('click',function(e){
   var b=e.target.closest('.flt');if(!b)return;
   [].slice.call(f.querySelectorAll('.flt')).forEach(function(x){x.classList.toggle('on',x===b);});
   var sev=b.getAttribute('data-sev');
   [].slice.call(f.parentNode.querySelectorAll('.finding')).forEach(function(d){d.style.display=(sev==='all'||d.getAttribute('data-sev')===sev)?'':'none';});
  });
 });
 window.addEventListener('beforeprint',function(){[].slice.call(document.querySelectorAll('details')).forEach(function(d){d.setAttribute('data-was',d.open?'1':'0');d.open=true;});});
 window.addEventListener('afterprint',function(){[].slice.call(document.querySelectorAll('details')).forEach(function(d){d.open=d.getAttribute('data-was')==='1';});});
 var pb=document.getElementById('printbtn');if(pb)pb.addEventListener('click',function(){window.print();});
})();
"""


def mermaid(domains, lang):
    """Domain map and context view as Mermaid, for docs/architecture.md in the repo (GitHub renders it)."""
    if not domains or not domains.get("domains"):
        return None
    doms = domains["domains"]
    sid = lambda x: re.sub(r"\W", "_", str(x))
    t = {"fr": ("Carte des domaines", "Vue contexte", "Généré par re-arch, à mettre à jour à chaque audit"),
         "en": ("Domain map", "Context view", "Generated by re-arch, refresh at each audit")}[lang]
    out = [f"# {t[0]}", "", f"_{t[2]}_", "", "```mermaid", "flowchart TD"]
    for d in doms:
        shape = ("[[", "]]") if d.get("kind") == "core" else ("(", ")") if d.get("kind") == "generic" else ("[", "]")
        out.append(f'    {sid(d["id"])}{shape[0]}"{d.get("name", d["id"])}"{shape[1]}')
    seen = set()
    for d in doms:
        for x in d.get("depends_on", []):
            a, b = sid(d["id"]), sid(x.get("id"))
            if (b, a) in seen:
                continue
            mutual = any(y.get("id") == d["id"] for dd in doms if dd["id"] == x.get("id") for y in dd.get("depends_on", []))
            out.append(f"    {a} {'<-->' if mutual else '-->'} {b}")
            seen.add((a, b))
    out.append("```")
    systems = domains.get("external_systems") or []
    if systems:
        out += ["", f"## {t[1]}", "", "```mermaid", "flowchart LR", '    subgraph app["' + ("Application") + '"]']
        for d in doms:
            if d.get("kind") != "technical":
                out.append(f'        {sid(d["id"])}["{d.get("name", d["id"])}"]')
        out.append("    end")
        for x in systems:
            out.append(f'    {sid("ext_" + x["name"])}[("{x["name"]}")]')
            for u in x.get("used_by", []):
                out.append(f'    {sid(u)} --> {sid("ext_" + x["name"])}')
        out.append("```")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archi_dir", nargs="?", default=".re-arch")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    d = args.archi_dir
    data = {k: load(d, f"{k}.json") for k in ("meta", "scan", "domains", "findings", "options", "plan", "pitch", "guardrails", "academy", "diff")}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import validate as _v
        rep_ = _v.validate(d)
        if rep_.errors or rep_.warnings:
            print(f"validate: {len(rep_.errors)} error(s), {len(rep_.warnings)} warning(s); run validate.py for details", file=sys.stderr)
    except Exception as exc:  # validation must never block rendering
        print(f"validate skipped: {exc}", file=sys.stderr)
    meta = data["meta"] or {}
    lang = "fr" if str(meta.get("lang", "en")).lower().startswith("fr") else "en"
    L = LABELS[lang]
    project = meta.get("project") or os.path.basename(os.path.dirname(os.path.abspath(d)))

    sections = []
    summ = section_summary(L, data)
    if summ:
        sections.append(("summary", L["summary"], summ))
    if data["domains"]:
        sections.append(("domains", L["domains"], section_domains(L, data["domains"])))
    if data["findings"]:
        sections.append(("diagnosis", L["diagnosis"], section_diagnosis(L, data["findings"], data["domains"])))
    if data["options"]:
        sections.append(("options", L["options"], section_options(L, data["options"])))
    if data["plan"]:
        sections.append(("plan", L["plan"], section_plan(L, data["plan"])))
    if data["academy"]:
        sections.append(("academy", L["academy"], section_academy(L, data["academy"])))
    if data["guardrails"]:
        sections.append(("guardrails", L["guardrails"], section_guardrails(L, data["guardrails"])))
    app = section_appendix(L, data["scan"], data["domains"])
    if app:
        sections.append(("appendix", L["appendix"], app))
    if not sections:
        print("Nothing to render: no .re-arch/*.json found.", file=sys.stderr)
        sys.exit(2)

    metas = []
    if meta.get("date"):
        metas.append(f'{L["generated"]} {esc(meta["date"])}')
    if meta.get("scope"):
        metas.append(f'{L["scope"]}{L["colon"]}{esc(meta["scope"])}')
    head = meta.get("head") or (data["scan"] or {}).get("head")
    if head:
        metas.append(f'{L["commit"]} <code>{esc(head)}</code>')
    if meta.get("audience"):
        metas.append(f'{L["audience"]}{L["colon"]}{esc(", ".join(L.get(a, a) for a in meta["audience"]))}')

    assumptions = meta.get("assumptions") or []
    assumptions_html = (f'<details class="assume"><summary>{esc(L["assumptions_made"])} ({len(assumptions)})</summary>{ul(assumptions)}</details>' if assumptions else "")
    nav = "".join(f'<a href="#{sid}">{esc(title)}</a>' for sid, title, _ in sections)
    body = "".join(f'<section class="panel" id="{sid}" aria-label="{esc(title)}"><h2>{esc(title)}</h2>{content}</section>' for sid, title, content in sections)
    page = f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(L['title'])} · {esc(project)}</title>
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="wrapper">
<div class="kicker">{esc(L['title'])}</div>
<h1>{esc(project)}</h1>
<div class="meta">{''.join(f'<span>{m}</span>' for m in metas)}</div>
{assumptions_html}
<div class="toolbar"><button type="button" id="printbtn">{esc(L['print'])}</button></div>
</div></header>
<nav class="tabs" aria-label="sections"><div class="wrapper">{nav}</div></nav>
<main><div class="wrapper">{body}</div></main>
<footer><div class="wrapper">re-arch · {esc(meta.get('date', ''))}</div></footer>
<script>{JS}</script>
</body>
</html>
"""
    mm = mermaid(data["domains"], lang)
    if mm:
        open(os.path.join(d, "architecture.md"), "w", encoding="utf-8").write(mm)
    out = args.out or os.path.join(d, "report.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"report written to {out} ({len(page) // 1024} KB, sections: {', '.join(s[0] for s in sections)})")


if __name__ == "__main__":
    main()
