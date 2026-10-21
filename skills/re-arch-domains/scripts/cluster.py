#!/usr/bin/env python3
"""
re-arch-domains / cluster.py

Proposes candidate business domains from .re-arch/scan.json by clustering a
weighted, undirected file graph built from several independent signals:

  - static imports                (structure as written)
  - git co-change                 (structure as maintained, often the most honest signal
                                    in vibe-coded apps whose folders mean little)
  - shared data-model entities    (files that touch the same entity)
  - directory proximity           (weak prior, folders sometimes do mean something)

Technical hubs (db client, utils, config, UI kit...) connect everything and
would glue all domains together, so they are set aside and reported as
"shared/technical" instead of being clustered.

Clustering: Louvain modularity optimisation (deterministic node order).

Output:
  .re-arch/domains-candidates.json
  .re-arch/domains-candidates.md
These are candidates. A human (or the re-arch-domains skill reading the code)
names them, merges/splits them and assigns a confidence.
"""
import argparse
import collections
import json
import math
import os
import re

GENERIC_TOKENS = {
    "src", "app", "apps", "lib", "libs", "api", "index", "main", "route", "routes", "page", "pages",
    "controller", "controllers", "service", "services", "model", "models", "repository", "repositories",
    "handler", "handlers", "util", "utils", "helper", "helpers", "common", "shared", "core", "internal",
    "pkg", "cmd", "components", "component", "view", "views", "test", "tests", "spec", "types", "type",
    "dto", "dtos", "entity", "entities", "impl", "interface", "interfaces", "config", "http", "server",
    "client", "java", "main", "com", "org", "net", "io", "mod", "rs", "go", "ts", "tsx", "js", "jsx",
    "php", "cs", "cpp", "h", "hpp", "kt", "layout", "default", "base", "abstract", "manager", "store",
    "hooks", "hook", "use", "context", "provider", "module", "modules", "feature", "features", "domain",
    "infrastructure", "infra", "application", "presentation", "ui", "web", "public", "private", "new",
    "get", "post", "put", "delete", "list", "create", "update", "edit", "detail", "details", "id",
}
TECH_DIR_NAMES = {"utils", "util", "lib", "libs", "common", "shared", "helpers", "helper", "config", "configs",
                  "constants", "types", "middleware", "middlewares", "infra", "infrastructure", "db", "database",
                  "ui", "components", "hooks", "styles", "assets", "core", "kernel", "framework", "platform",
                  "lang", "locales", "locale", "i18n", "translations", "migrations", "seeders", "seeds", "factories"}
TOOLING_RE = re.compile(r"(^|/)(webpack|vite|rollup|babel|jest|vitest|playwright|cypress|tailwind|postcss|eslint|prettier|next|nuxt|svelte|astro|tsup|esbuild|karma|gulp|grunt|metro|drizzle|knexfile|ormconfig|commitlint|lint-staged|stylelint)[\w.\-]*\.(js|cjs|mjs|ts|cts|mts|json)$|\.config\.\w+$|(^|/)jest[\w.\-]*$|(^|/)setup(Tests)?\.\w+$", re.I)
ENTRY_NAMES = {"main", "program", "startup", "app", "server", "index", "hello", "bootstrap", "kernel", "application", "lib"}


def route_resource(path):
    segs = [x for x in path.split("/") if x and not x.startswith((":", "{", "<", "[")) and not re.match(r"^v\d+$|^api$|^admin$|^public$", x)]
    return segs[0].lower() if segs else "/"


def tokens_of(path):
    base = re.sub(r"\.[^.]+$", "", path)
    parts = re.split(r"[/_\-.\[\]()]+", base)
    out = []
    for p in parts:
        for t in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", p):
            t = t.lower()
            if len(t) > 2 and t not in GENERIC_TOKENS and not t.isdigit():
                out.append(t[:-1] if t.endswith("s") and not t.endswith("ss") and len(t) > 4 else t)
    return out


# ---------------------------------------------------------------------------
# Louvain (weighted, undirected)
# ---------------------------------------------------------------------------


def louvain(nodes, adj, resolution=1.0, max_passes=10):
    """adj: dict node -> dict neighbour -> weight (symmetric). Returns node -> community."""
    # current graph
    g_nodes = list(nodes)
    g_adj = {n: dict(adj.get(n, {})) for n in g_nodes}
    membership = {n: n for n in g_nodes}  # original node -> super node
    for _ in range(max_passes):
        m2 = sum(sum(nb.values()) for nb in g_adj.values())  # = 2m
        if m2 == 0:
            break
        k = {n: sum(g_adj[n].values()) for n in g_nodes}
        comm = {n: i for i, n in enumerate(g_nodes)}
        tot = collections.Counter({comm[n]: k[n] for n in g_nodes})
        improved = True
        moved_any = False
        while improved:
            improved = False
            for n in g_nodes:
                c_old = comm[n]
                links = collections.Counter()
                for nb, w in g_adj[n].items():
                    if nb != n:
                        links[comm[nb]] += w
                tot[c_old] -= k[n]
                best_c, best_gain = c_old, links.get(c_old, 0) - resolution * tot[c_old] * k[n] / m2
                for c, w in sorted(links.items()):
                    gain = w - resolution * tot[c] * k[n] / m2
                    if gain > best_gain + 1e-12:
                        best_c, best_gain = c, gain
                tot[best_c] += k[n]
                if best_c != c_old:
                    comm[n] = best_c
                    improved = True
                    moved_any = True
        if not moved_any:
            break
        # aggregate
        new_adj = collections.defaultdict(lambda: collections.defaultdict(float))
        for n in g_nodes:
            for nb, w in g_adj[n].items():
                new_adj[comm[n]][comm[nb]] += w
        for orig in membership:
            membership[orig] = comm[membership[orig]]
        g_nodes = sorted(set(comm.values()))
        g_adj = {n: dict(new_adj[n]) for n in g_nodes}
    return membership


def modularity(adj, membership):
    m2 = sum(sum(nb.values()) for nb in adj.values())
    if m2 == 0:
        return 0.0
    k = {n: sum(nb.values()) for n, nb in adj.items()}
    q = 0.0
    tot = collections.Counter()
    inside = collections.Counter()
    for n, nb in adj.items():
        tot[membership[n]] += k[n]
        for m, w in nb.items():
            if membership.get(m) == membership[n]:
                inside[membership[n]] += w
    for c in tot:
        q += inside[c] / m2 - (tot[c] / m2) ** 2
    return q


# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archi_dir", nargs="?", default=".re-arch")
    ap.add_argument("--w-import", type=float, default=1.0)
    ap.add_argument("--w-cochange", type=float, default=2.0)
    ap.add_argument("--w-entity", type=float, default=0.6)
    ap.add_argument("--w-dir", type=float, default=0.4)
    ap.add_argument("--w-runtime", type=float, default=0.8)
    ap.add_argument("--w-route", type=float, default=1.2)
    ap.add_argument("--hub-share", type=float, default=0.25, help="a non-entry file used by more than ~2x this share of modules is a technical hub")
    ap.add_argument("--resolution", type=float, default=1.0, help=">1 gives more, smaller domains")
    args = ap.parse_args()

    scan = json.load(open(os.path.join(args.archi_dir, "scan.json"), encoding="utf-8"))
    files = {f["path"]: f for f in scan["files"] if not f["test"]}
    n_files = len(files)

    # Technical hubs. Counted in distinct *modules* using a file rather than raw
    # fan-in: Go maps imports to every file of a package and would otherwise
    # make whole domains look like hubs.
    n_modules = len({f["module"] for f in files.values()})
    users_by_file = collections.defaultdict(set)
    for p, f in files.items():
        for t in f.get("imports", []):
            if t in files and files[t]["module"] != f["module"]:
                users_by_file[t].add(f["module"])
    hub_modules = max(3, math.ceil(args.hub_share * 2 * n_modules))
    technical = {}
    for p, f in files.items():
        dirs = {d.lower() for d in p.split("/")[:-1]}
        sig = f.get("signals", {})
        stem = os.path.splitext(p.rsplit("/", 1)[-1])[0].lower()
        reasons = []
        is_entry = stem in ("route", "routes", "page", "layout", "handler", "handlers", "main") or "controller" in stem or "endpoint" in stem
        if len(users_by_file[p]) >= hub_modules and not is_entry:
            reasons.append(f"used by {len(users_by_file[p])} modules")
        if dirs & TECH_DIR_NAMES and not is_entry and not sig.get("ui"):
            reasons.append("technical folder")
        out_mods = {files[t]["module"] for t in f.get("imports", []) if t in files and files[t]["module"] != f["module"]}
        if f["fan_in"] == 0 and len(out_mods) >= 3 and (stem in ENTRY_NAMES or "extension" in stem or "config" in stem):
            reasons.append("composition root / wiring")
        if TOOLING_RE.search(p) or (p.startswith("bootstrap/") and "/" not in p[len("bootstrap/"):]):
            reasons.append("build / tooling config")
        if reasons:
            technical[p] = reasons
    nodes = sorted(p for p in files if p not in technical)

    adj = collections.defaultdict(lambda: collections.defaultdict(float))
    evidence = collections.Counter()

    def add(a, b, w, kind):
        if a == b or a not in files or b not in files or a in technical or b in technical:
            return
        adj[a][b] += w
        adj[b][a] += w
        evidence[kind] += 1

    for p in nodes:
        for t in files[p].get("imports", []):
            add(p, t, args.w_import, "import")
        # dependency injection: consumer -> implementation the container injects
        for t in files[p].get("runtime_imports", []):
            add(p, t, args.w_runtime, "runtime")

    # routes: handlers serving the same resource (/invoices, /invoices/:id...) belong together.
    # Decisive in framework-convention layouts (Laravel, Rails-like, Spring MVC by layer)
    by_resource = collections.defaultdict(set)
    for r in scan.get("routes", []):
        if r.get("file") in files:
            by_resource[route_resource(r["path"])].add(r["file"])
    for res, fs in by_resource.items():
        fs = sorted(fs)
        if res == "/" or not 2 <= len(fs) <= 20:
            continue
        w = args.w_route / math.sqrt(len(fs) - 1)
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                add(fs[i], fs[j], w, "route")

    hist = scan.get("history") or {}
    for c in hist.get("cochange", []):
        w = args.w_cochange * c["strength"] * min(c["count"], 6) / 6
        add(c["a"], c["b"], w, "cochange")

    entity_files = {}
    for e in scan.get("entities", []):
        users = [p for p in e.get("used_in", []) if p in files and p not in technical]
        if 2 <= len(users) <= max(8, n_files // 4):  # an entity used everywhere carries no signal
            entity_files[e["name"]] = users
            w = args.w_entity / math.sqrt(len(users) - 1)
            for i in range(len(users)):
                for j in range(i + 1, len(users)):
                    add(users[i], users[j], w, "entity")

    by_dir = collections.defaultdict(list)
    for p in nodes:
        by_dir[os.path.dirname(p)].append(p)
    for d, ps in by_dir.items():
        if 2 <= len(ps) <= 30:
            w = args.w_dir / math.sqrt(len(ps) - 1)
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    add(ps[i], ps[j], w, "directory")

    for p in nodes:
        adj[p]  # isolated nodes still exist
    membership = louvain(nodes, adj, args.resolution)
    q = modularity(adj, membership)

    groups = collections.defaultdict(list)
    for p in nodes:
        groups[membership[p]].append(p)
    clusters = []
    singletons = []
    for cid, ps in groups.items():
        if len(ps) == 1 and not adj[ps[0]]:
            singletons.append(ps[0])
            continue
        inside = sum(w for p in ps for q2, w in adj[p].items() if membership.get(q2) == cid) / 2
        total = sum(w for p in ps for w in adj[p].values()) - inside
        cohesion = inside / total if total else 0.0
        terms = collections.Counter()
        for p in ps:
            terms.update(set(tokens_of(p)))
        ents = sorted({e for e, us in entity_files.items() if sum(1 for u in us if u in ps) >= max(1, len(us) / 2)})
        mods = collections.Counter(files[p]["module"] for p in ps)
        top_term_share = terms.most_common(1)[0][1] / len(ps) if terms else 0
        score = 0
        score += 1 if cohesion >= 0.6 else 0
        score += 1 if top_term_share >= 0.5 else 0
        score += 1 if len(ps) >= 3 else 0
        score += 1 if ents else 0
        confidence = "high" if score >= 3 else "medium" if score == 2 else "low"
        clusters.append({
            "files": sorted(ps), "size": len(ps), "loc": sum(files[p]["loc"] for p in ps),
            "cohesion": round(cohesion, 2), "top_terms": [t for t, _ in terms.most_common(6)],
            "entities": ents, "modules": dict(mods.most_common(6)), "confidence_hint": confidence,
            "signals": {
                k: sum(1 for p in ps if k in files[p].get("signals", {})) for k in ("http", "ui", "db", "external_io")
            },
        })
    clusters.sort(key=lambda c: -c["loc"])
    for i, c in enumerate(clusters, 1):
        c["id"] = f"C{i}"
    cid_of = {p: c["id"] for c in clusters for p in c["files"]}

    # Directed dependencies between clusters (imports only, the code-level direction)
    deps = collections.Counter()
    for p in nodes:
        for t in files[p].get("imports", []):
            a, b = cid_of.get(p), cid_of.get(t)
            if a and b and a != b:
                deps[(a, b)] += 1
    co = collections.Counter()
    for c in hist.get("cochange", []):
        a, b = cid_of.get(c["a"]), cid_of.get(c["b"])
        if a and b and a != b:
            co[tuple(sorted((a, b)))] += c["count"]
    tech_users = collections.Counter()
    for p in nodes:
        for t in files[p].get("imports", []):
            if t in technical and cid_of.get(p):
                tech_users[t] += 1

    out = {
        "modularity": round(q, 3),
        "edge_evidence": dict(evidence),
        "weights": {"import": args.w_import, "cochange": args.w_cochange, "entity": args.w_entity, "directory": args.w_dir,
                    "runtime": args.w_runtime, "route": args.w_route},
        "external_systems": scan.get("external_systems", []),
        "clusters": clusters,
        "dependencies": [{"from": a, "to": b, "imports": n} for (a, b), n in deps.most_common()],
        "cross_cochange": [{"a": a, "b": b, "file_pair_cochanges": n, "commits": n} for (a, b), n in co.most_common()],
        "technical": [{"path": p, "reasons": r, "used_by_files": tech_users.get(p, 0)} for p, r in sorted(technical.items())],
        "unclustered": sorted(singletons),
        "notes": [
            "Modularity above ~0.3 means the clusters are meaningfully separated; below that, the code has weak boundaries and the domains will need to be read from the code and the data model rather than the graph.",
            "Cross-cluster co-change means two candidate domains are changed together: either they are one domain, or a rule is duplicated across them.",
        ],
    }
    json.dump(out, open(os.path.join(args.archi_dir, "domains-candidates.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    L = [f"# Candidate domains\n", f"Modularity: {out['modularity']} (edges: {', '.join(f'{k} {v}' for k, v in evidence.items())})\n"]
    for c in clusters:
        L.append(f"## {c['id']}: terms {', '.join(c['top_terms'][:4]) or '-'} ({c['size']} files, {c['loc']} LOC, cohesion {c['cohesion']}, hint {c['confidence_hint']})")
        if c["entities"]:
            L.append(f"Entities: {', '.join(c['entities'])}  ")
        L.append(f"Modules: {', '.join(f'{m} ({n})' for m, n in c['modules'].items())}  ")
        L.append(f"Signals: {', '.join(f'{k} {v}' for k, v in c['signals'].items() if v) or '-'}  ")
        for p in c["files"][:25]:
            L.append(f"- {p}")
        if c["size"] > 25:
            L.append(f"- ... {c['size'] - 25} more")
        L.append("")
    L.append("## Dependencies between clusters (imports)\n")
    for d in out["dependencies"][:40]:
        L.append(f"- {d['from']} -> {d['to']} ({d['imports']})")
    if out["cross_cochange"]:
        L.append("\n## Co-change across clusters\n")
        for d in out["cross_cochange"][:20]:
            L.append(f"- {d['a']} <-> {d['b']} ({d['commits']} file-pair co-changes)")
    L.append("\n## Shared / technical (not clustered)\n")
    for t in out["technical"][:40]:
        L.append(f"- {t['path']} ({', '.join(t['reasons'])}, used by {t['used_by_files']} files)")
    if singletons:
        L.append("\n## Unclustered files (no link found)\n")
        for p in singletons[:40]:
            L.append(f"- {p}")
    L.append("\n## Notes\n")
    for n in out["notes"]:
        L.append(f"- {n}")
    open(os.path.join(args.archi_dir, "domains-candidates.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"{len(clusters)} candidate clusters, modularity {out['modularity']}, {len(technical)} technical files, {len(singletons)} unclustered")


if __name__ == "__main__":
    main()
