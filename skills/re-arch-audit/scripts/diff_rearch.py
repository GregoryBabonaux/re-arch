#!/usr/bin/env python3
"""
diff_rearch.py: keep an audit alive between runs.

  python3 diff_rearch.py snapshot <repo>/.re-arch
      copy the current audit (*.json, *.md) to .re-arch/history/<date>_<head>/ before re-running it

  python3 diff_rearch.py compare <old_dir> <new_dir> [--out <new_dir>]
      compare two audits and write diff.json + diff.md:
      - findings RESOLVED / NEW / PERSISTING / REGRESSED (severity up) / IMPROVED (severity down)
      - plan phases done / in progress / not started (plan.json phases[].status)
      - metric deltas from the scan (cycles, mixed files, test ratio, hotspots, fix share, hygiene)

Findings are matched by id first (the diagnosis keeps ids stable in re-audit
mode), then by category + overlapping evidence files, then by title similarity.
"""
import argparse
import datetime
import difflib
import glob
import json
import os
import shutil
import subprocess
import sys

SEV = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def load(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except ValueError:
        return None


def snapshot(archi):
    scan = load(archi, "scan.json") or {}
    meta = load(archi, "meta.json") or {}
    head = scan.get("head") or meta.get("head") or "nohead"
    stamp = (meta.get("date") or datetime.date.today().isoformat()) + "_" + head
    dest = os.path.join(archi, "history", stamp)
    os.makedirs(dest, exist_ok=True)
    n = 0
    for f in glob.glob(os.path.join(archi, "*.json")) + glob.glob(os.path.join(archi, "*.md")):
        shutil.copy2(f, dest)
        n += 1
    print(f"snapshot of {n} files in {dest}")
    return dest


def evidence_files(f):
    return {e.get("file") for e in f.get("evidence", []) if e.get("file")}


def match_findings(old, new):
    pairs, used_old, used_new = [], set(), set()
    by_id_old = {f["id"]: f for f in old}
    for f in new:
        o = by_id_old.get(f["id"])
        if o and (o.get("category") == f.get("category") or evidence_files(o) & evidence_files(f)
                  or difflib.SequenceMatcher(None, o.get("title", ""), f.get("title", "")).ratio() > 0.5):
            pairs.append((o, f))
            used_old.add(o["id"])
            used_new.add(f["id"])
    for f in new:
        if f["id"] in used_new:
            continue
        best, score = None, 0
        for o in old:
            if o["id"] in used_old:
                continue
            s = 0
            if o.get("category") == f.get("category"):
                s += 1
            ov = evidence_files(o) & evidence_files(f)
            if ov:
                s += 1 + len(ov) / max(1, len(evidence_files(o) | evidence_files(f)))
            s += difflib.SequenceMatcher(None, o.get("title", ""), f.get("title", "")).ratio()
            if s > score:
                best, score = o, s
        if best and score >= 2.0:
            pairs.append((best, f))
            used_old.add(best["id"])
            used_new.add(f["id"])
    resolved = [o for o in old if o["id"] not in used_old]
    new_only = [f for f in new if f["id"] not in used_new]
    return pairs, resolved, new_only


def metric(scan, path, default=None):
    cur = scan
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def scan_metrics(scan):
    if not scan:
        return {}
    t = scan.get("totals", {})
    h = scan.get("dependency_hygiene") or {}
    return {
        "prod_loc": t.get("prod_loc"),
        "test_ratio": round(t["test_loc"] / t["prod_loc"], 2) if t.get("prod_loc") else None,
        "module_cycles": len(scan.get("module_cycles", [])),
        "file_cycles": len(scan.get("file_cycles", [])),
        "mixed_responsibility_files": len(scan.get("mixed_responsibilities", [])),
        "duplicated_blocks": len(scan.get("duplicates", [])),
        "fix_share": metric(scan, ["history", "fix_share"]),
        "libraries_doing_same_job": len(h.get("same_job", [])),
        "undeclared_dependencies": len(h.get("undeclared", [])),
        "possible_secrets": len(scan.get("possible_secrets", [])),
    }


# metrics where lower is better
LOWER_BETTER = {"module_cycles", "file_cycles", "mixed_responsibility_files", "duplicated_blocks", "fix_share",
                "libraries_doing_same_job", "undeclared_dependencies", "possible_secrets"}


def compare(old_dir, new_dir, out_dir):
    of, nf = load(old_dir, "findings.json") or {}, load(new_dir, "findings.json") or {}
    pairs, resolved, new_only = match_findings(of.get("findings", []), nf.get("findings", []))
    persisting, regressed, improved = [], [], []
    for o, n in pairs:
        entry = {"old_id": o["id"], "id": n["id"], "title": n.get("title"), "old_severity": o.get("severity"), "severity": n.get("severity")}
        d = SEV.get(n.get("severity"), 1) - SEV.get(o.get("severity"), 1)
        (regressed if d > 0 else improved if d < 0 else persisting).append(entry)
    om, nm = scan_metrics(load(old_dir, "scan.json")), scan_metrics(load(new_dir, "scan.json"))
    metrics = []
    for k in nm:
        a, b = om.get(k), nm.get(k)
        if a is None or b is None:
            continue
        trend = "same" if a == b else ("better" if (b < a) == (k in LOWER_BETTER) else "worse")
        if k in ("prod_loc",):
            trend = "info"
        metrics.append({"metric": k, "before": a, "after": b, "trend": trend})
    plan = load(new_dir, "plan.json") or load(old_dir, "plan.json") or {}
    phases = [{"id": p.get("id"), "name": p.get("name"), "status": p.get("status", "not started")} for p in plan.get("phases", [])]
    old_meta, new_meta = load(old_dir, "meta.json") or {}, load(new_dir, "meta.json") or {}
    res = {
        "from": {"date": old_meta.get("date"), "head": (load(old_dir, "scan.json") or {}).get("head")},
        "to": {"date": new_meta.get("date"), "head": (load(new_dir, "scan.json") or {}).get("head")},
        "findings": {
            "resolved": [{"id": o["id"], "title": o.get("title"), "severity": o.get("severity")} for o in resolved],
            "new": [{"id": f["id"], "title": f.get("title"), "severity": f.get("severity")} for f in new_only],
            "regressed": regressed, "improved": improved, "persisting": persisting,
        },
        "metrics": metrics,
        "phases": phases,
    }
    os.makedirs(out_dir, exist_ok=True)
    json.dump(res, open(os.path.join(out_dir, "diff.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    L = [f"# Progress since {res['from']['date'] or 'previous audit'} ({res['from']['head'] or '?'} -> {res['to']['head'] or '?'})", ""]
    F = res["findings"]
    L.append(f"Findings: {len(F['resolved'])} resolved, {len(F['new'])} new, {len(F['regressed'])} worse, {len(F['improved'])} better, {len(F['persisting'])} unchanged")
    L.append("")
    for label, key in (("Resolved", "resolved"), ("New", "new")):
        if F[key]:
            L.append(f"## {label}")
            L += [f"- {x['id']} ({x['severity']}) {x['title']}" for x in F[key]]
            L.append("")
    if F["regressed"]:
        L.append("## Worse")
        L += [f"- {x['id']} {x['title']}: {x['old_severity']} -> {x['severity']}" for x in F["regressed"]]
        L.append("")
    if metrics:
        L.append("## Metrics")
        L += [f"- {m['metric']}: {m['before']} -> {m['after']} ({m['trend']})" for m in metrics]
        L.append("")
    if phases:
        L.append("## Plan")
        L += [f"- {p['id']} {p['name']}: {p['status']}" for p in phases]
    open(os.path.join(out_dir, "diff.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"diff written to {out_dir}: {len(F['resolved'])} resolved, {len(F['new'])} new, {len(F['regressed'])} worse")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("archi")
    c = sub.add_parser("compare")
    c.add_argument("old")
    c.add_argument("new")
    c.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cmd == "snapshot":
        snapshot(a.archi)
    else:
        compare(a.old, a.new, a.out or a.new)


if __name__ == "__main__":
    main()
