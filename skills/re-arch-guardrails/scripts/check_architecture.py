#!/usr/bin/env python3
"""
check_architecture.py: language-agnostic architecture fitness function.

Runs scan.py (vendored next to this file, precise mode when the toolchain is
available) without git history, then checks the dependency graph against a
JSON rules file. Works in CI, in pre-commit hooks and in AI-agent hooks.

Adoption without a big bang (freeze / ratchet, as ArchUnit FreezingArchRule,
deptrac baselines or Sonar "clean as you code"):
  --baseline-write re-arch-baseline.json   record today's violations once
  --baseline re-arch-baseline.json         fail only on violations that are NOT in the
                                         baseline; fixed ones are reported so the
                                         baseline can shrink (--baseline-update)
Existing debt is tolerated, new debt fails from day one.

Output: --format text (humans, CI logs), json (tools), agent (short, actionable,
with the reason of each rule, for Claude Code / Cursor / Codex hooks).
--changed-only limits the report to files changed in git (working tree + index).

Exit codes: 0 no (new) violation, 1 (new) violations, 2 error.
--hook: for agent hooks (Claude Code Stop / PostToolUse): agent format on
stderr and exit code 2 on violations, which Claude Code feeds back to the
agent so it fixes the code in the same turn.

Rules file (architecture-rules.json). A file belongs to the FIRST layer whose
globs match (put specific layers before broad ones). A layer missing from
"allow" may import anything: list every layer, with [] for "nothing else".
{
  "layers": {                       # layer name -> list of path globs (* = one segment, ** = any depth)
    "web":    ["src/app/**"],
    "app":    ["src/modules/*/application/**"],
    "domain": ["src/modules/*/domain/**"],
    "infra":  ["src/modules/*/infrastructure/**"]
  },
  "allow": {                        # which other layers each layer may import (same layer always allowed)
    "web": ["app", "domain"], "app": ["domain"], "infra": ["app", "domain"], "domain": []
  },
  "forbid_external": {              # third-party packages a layer must not use (npm/Composer/crate names;
                                    # Java/.NET: up to 3 namespace segments, e.g. org.springframework.web)
    "domain": ["@prisma/client", "next", "stripe"]
  },
  "forbid_patterns": {              # regexes a layer's source must not contain (framework helpers, globals);
    "domain": ["\\bauth\\(\\)",          # a string, or {"id", "pattern", "why"} to tie it to a rule id and reason
               {"id": "R2", "pattern": "process\\.env", "why": "configuration is injected, read once in src/config.ts"},
               {"id": "R3", "pattern": "(?<![\\w\\\\])Auth::", "why": "use the acting user passed as a parameter"}]   # anchor facade names: JWTAuth:: must not match
  },
  "forbid_new_files": [             # legacy areas: existing files live in the baseline, any new file fails
    {"id": "R4", "glob": "app/RealWorld/**", "why": "new code goes to app/Domain/<domain>"}
  ],
  "public_api": {                   # code outside a matched folder may only import the listed files of it
    "src/modules/*": ["index.ts"]
  },
  "forbid_cycles": "modules",       # "modules", "files" or false
  "max_file_loc": 600,              # optional
  "why": {                          # optional reason shown to humans and agents; most specific wins:
                                    # "<kind>:<layer>" (e.g. "external:domain"), then "<layer>", then "<kind>"
    "domain": "Domain code stays free of frameworks so business rules can be tested alone (ADR 0001)",
    "public-api": "Modules talk through their index.ts so internals can change freely"
  }
}
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def glob_to_regex(g):
    out, i = "", 0
    while i < len(g):
        c = g[i]
        if g.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif g.startswith("**", i):
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile("^" + out + "$")


def git_changed(root):
    files = set()
    for cmd in (["git", "diff", "--name-only", "HEAD"], ["git", "diff", "--name-only", "--cached"], ["git", "ls-files", "--others", "--exclude-standard"]):
        try:
            r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=60)
            files |= {l.strip() for l in r.stdout.splitlines() if l.strip()}
        except OSError:
            pass
    return files


def shown(text):
    """Never echo something that looks like a secret into CI logs."""
    if re.search(r"[A-Za-z0-9_\-+/=]{16,}", text):
        return text[:4] + "…(masked)"
    return text[:60]


def check(rules, scan, root):
    layers = {name: [glob_to_regex(g) for g in globs] for name, globs in rules.get("layers", {}).items()}

    def layer_of(path):
        for name, rxs in layers.items():
            if any(rx.match(path) for rx in rxs):
                return name
        return None

    files = {f["path"]: f for f in scan["files"] if not f["test"]}
    out = []

    def v(kind, file, detail, target="", layer=None, line=None):
        out.append({"kind": kind, "file": file, "line": line, "target": target, "layer": layer, "detail": detail,
                    "fingerprint": "|".join([kind, file, target or "", layer or ""])})

    allow = rules.get("allow", {})
    for p, f in files.items():
        lp = layer_of(p)
        if lp is None:
            continue
        for t in f.get("imports", []):
            if t not in files:
                continue
            lt = layer_of(t)
            if lt is None or lt == lp:
                continue
            if lp in allow and lt not in allow[lp]:
                v("layer", p, f"{lp} imports {lt} ({t}); {lp} may only import {', '.join(allow[lp]) or 'nothing outside itself'}", t, lp)

    for layer, banned in rules.get("forbid_external", {}).items():
        for p, f in files.items():
            if layer_of(p) != layer:
                continue
            for ext in f.get("externals", []):
                if any(ext == b or ext.startswith(b + "/") or ext.startswith(b + ".") or ext.startswith(b + "\\") for b in banned):
                    v("external", p, f"{layer} uses {ext}", ext, layer)

    for layer, patterns in rules.get("forbid_patterns", {}).items():
        rxs = []
        for x in patterns:
            if isinstance(x, dict):
                rxs.append((re.compile(x["pattern"]), x.get("why", ""), x.get("id")))
            else:
                rxs.append((re.compile(x), "", None))
        for p in files:
            if layer_of(p) != layer:
                continue
            try:
                text = open(os.path.join(root, p), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for rx, pwhy, pid in rxs:
                for m in rx.finditer(text):  # every occurrence counts, so the baseline cannot hide a second one
                    v("pattern", p, f"{layer} contains `{shown(m.group(0))}`" + (f" [{pid}]" if pid else ""), pid or rx.pattern, layer, text.count("\n", 0, m.start()) + 1)
                    if pwhy:
                        out[-1]["why_override"] = pwhy

    for folder_glob, public in rules.get("public_api", {}).items():
        rx = glob_to_regex(folder_glob + "/**")
        root_rx = glob_to_regex(folder_glob)
        for p, f in files.items():
            for t in f.get("imports", []):
                if not rx.match(t):
                    continue
                parts = t.split("/")
                owner = next(("/".join(parts[:i]) for i in range(1, len(parts)) if root_rx.match("/".join(parts[:i]))), None)
                if owner is None or p.startswith(owner + "/"):
                    continue
                inner = t[len(owner) + 1:]
                if not any(glob_to_regex(pub).match(inner) for pub in public):
                    v("public-api", p, f"imports {t}; only {', '.join(public)} of {owner} are public", t, layer_of(p))

    mode = rules.get("forbid_cycles", False)
    if mode == "modules":
        for c in scan.get("module_cycles", []):
            path = c.get("example") or c["modules"]
            v("cycle", path[0], "module cycle " + " -> ".join(path), "|".join(sorted(c["modules"])))
    elif mode == "files":
        for c in scan.get("file_cycles", []):
            path = c.get("example") or c["files"]
            v("cycle", path[0], "file cycle " + " -> ".join(path), "|".join(sorted(c["files"])))

    # folders frozen by the target architecture: existing files tolerated through the baseline, new ones fail
    for rule in rules.get("forbid_new_files", []):
        rx = glob_to_regex(rule["glob"] if isinstance(rule, dict) else rule)
        for p in files:
            if rx.match(p):
                v("frozen-folder", p, f"file in a frozen area ({rule.get('glob') if isinstance(rule, dict) else rule})"
                  + (f" [{rule.get('id')}]" if isinstance(rule, dict) and rule.get("id") else ""), "", None)
                if isinstance(rule, dict) and rule.get("why"):
                    out[-1]["why_override"] = rule["why"]

    max_loc = rules.get("max_file_loc")
    if max_loc:
        for p, f in files.items():
            if f["loc"] > max_loc:
                v("size", p, f"{f['loc']} lines (max {max_loc})")
    return out


def compare(violations, baseline):
    """Count-aware comparison: a fingerprint present 3 times in the baseline tolerates 3 occurrences."""
    allowed = collections.Counter(baseline.get("fingerprints", {}))
    seen = collections.Counter()
    new = []
    for x in violations:
        seen[x["fingerprint"]] += 1
        if seen[x["fingerprint"]] > allowed.get(x["fingerprint"], 0):
            new.append(x)
    fixed = sum(max(0, n - seen.get(fp, 0)) for fp, n in allowed.items())
    return new, fixed, seen


def main():
    ap = argparse.ArgumentParser(description="Architecture fitness function")
    ap.add_argument("rules")
    ap.add_argument("--root", default=".")
    ap.add_argument("--warn", action="store_true", help="report but exit 0")
    ap.add_argument("--scan", default=None, help="reuse an existing scan.json instead of scanning")
    ap.add_argument("--precise", choices=["auto", "off"], default="auto")
    ap.add_argument("--baseline", default=None, help="fail only on violations absent from this baseline")
    ap.add_argument("--baseline-write", default=None, help="record current violations as the accepted baseline")
    ap.add_argument("--baseline-update", action="store_true", help="with --baseline: rewrite it, shrinking only (fixed violations leave it, new ones never enter)")
    ap.add_argument("--format", choices=["text", "json", "agent"], default="text")
    ap.add_argument("--changed-only", action="store_true", help="report only violations in files changed in git")
    ap.add_argument("--hook", action="store_true",
                    help="agent hook mode (Claude Code Stop/PostToolUse): agent format on stderr, exit 2 on violations so the agent must fix them")
    args = ap.parse_args()

    try:
        rules = json.load(open(args.rules, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read rules: {exc}", file=sys.stderr)
        sys.exit(2)
    if args.scan:
        scan = json.load(open(args.scan, encoding="utf-8"))
    else:
        tmp = tempfile.mkdtemp(prefix="re-arch-check-")
        cmd = [sys.executable, os.path.join(HERE, "scan.py"), args.root, "--out", tmp, "--no-git", "--precise", args.precise]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr or r.stdout, file=sys.stderr)
            sys.exit(2)
        scan = json.load(open(os.path.join(tmp, "scan.json"), encoding="utf-8"))

    violations = check(rules, scan, args.root)
    why = rules.get("why", {})
    for x in violations:
        x["why"] = (x.pop("why_override", "") or why.get(f"{x['kind']}:{x['layer']}") or why.get(x["layer"] or "")
                    or why.get(x["kind"]) or "")

    if args.baseline_write:
        fps = collections.Counter(x["fingerprint"] for x in violations)
        json.dump({"note": "Accepted architecture debt. New violations fail; fixed ones should be removed with --baseline-update.",
                   "fingerprints": dict(sorted(fps.items()))}, open(args.baseline_write, "w", encoding="utf-8"), indent=1)
        print(f"baseline written: {len(violations)} violation(s) accepted in {args.baseline_write}")
        sys.exit(0)

    fixed = 0
    reported = violations
    if args.baseline:
        try:
            base = json.load(open(args.baseline, encoding="utf-8"))
        except (OSError, ValueError):
            base = {"fingerprints": {}}
        reported, fixed, seen = compare(violations, base)
        if args.baseline_update:
            shrunk = {fp: min(n, seen.get(fp, 0)) for fp, n in base.get("fingerprints", {}).items() if seen.get(fp, 0) > 0}
            base["fingerprints"] = dict(sorted(shrunk.items()))
            json.dump(base, open(args.baseline, "w", encoding="utf-8"), indent=1)
    if args.changed_only:
        changed = git_changed(args.root)
        reported = [x for x in reported if x["file"] in changed or x["target"] in changed]

    label = "new " if args.baseline else ""
    if args.hook:
        args.format = "agent"
        # Claude Code passes the event as JSON on stdin; on a Stop event that was already
        # sent back once (stop_hook_active), report without blocking again to avoid loops.
        event = {}
        try:
            import select
            if not sys.stdin.isatty() and select.select([sys.stdin], [], [], 0.5)[0]:
                raw = sys.stdin.read()
                event = json.loads(raw) if raw.strip().startswith("{") else {}
        except (OSError, ValueError, ImportError):
            event = {}
        if event.get("stop_hook_active") and reported:
            print(f"Architecture check: {len(reported)} violation(s) still open; they will fail CI.", file=sys.stderr)
            sys.exit(0)
        sys.stdout = sys.stderr
    if args.format == "json":
        print(json.dumps({"violations": reported, "fixed_since_baseline": fixed, "total_current": len(violations)}, indent=1))
    elif args.format == "agent":
        if reported:
            print(f"Architecture check: {len(reported)} {label}violation(s). Fix them before finishing (move the code, do not silence the rule):")
            for x in reported[:20]:
                where = f"{x['file']}:{x['line']}" if x.get("line") else x["file"]
                print(f"- {where}: {x['detail']}" + (f". Why: {x['why']}" if x["why"] else ""))
            if len(reported) > 20:
                print(f"- ... {len(reported) - 20} more")
        else:
            hint = "baseline updated" if args.baseline_update else "run with --baseline-update to shrink the baseline"
            print("Architecture check: OK" + (f" ({fixed} baseline violation(s) fixed, {hint})" if fixed else ""))
    else:
        for x in reported:
            where = f"{x['file']}:{x['line']}" if x.get("line") else x["file"]
            print(f"[{x['kind']}] {where}: {x['detail']}" + (f" ({x['why']})" if x["why"] else ""))
        print(f"{len(reported)} {label}architecture violation(s)" + (f", {len(violations)} in total, {fixed} fixed since baseline" if args.baseline else ""))
    if args.hook:
        sys.exit(2 if reported else 0)
    sys.exit(0 if (args.warn or not reported) else 1)


if __name__ == "__main__":
    main()
