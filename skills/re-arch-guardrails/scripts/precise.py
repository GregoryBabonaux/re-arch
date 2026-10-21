#!/usr/bin/env python3
"""
precise.py: compiler-grade dependency sources for re-arch-scan.

Each adapter replaces the regex resolution for the files it covers, when the
information or the tool is available, and says so. Nothing here executes code
from the audited repository unless `allow_build` is set (configure/compile
steps run the project's build scripts, so the skill asks the person first).

Adapters (in order):
  build units   .csproj ProjectReference, Cargo.toml / cargo metadata, Maven
                modules, Gradle subprojects, npm/pnpm workspaces, CMake targets
  C/C++         compile_commands.json (real -I/-D per file) + preprocessor -H
                tree when a compiler is available; CMakeLists include dirs
                otherwise
  Go            go list -e -json (exact package mapping, build tags, std)
  Rust          crate roots and cross-crate `use` from cargo metadata
  Java/Kotlin   jdeps on compiled classes when present
  JS/TS         TypeScript's own module resolution (repo's typescript package)
  PHP           PHP tokenizer: every class name reference, resolved with
                namespace and `use` rules (needs a php binary)

Every adapter is optional and fails soft: on any error it reports a note and
the regex result stays in place.
"""
import collections
import concurrent.futures
import fnmatch
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None

SKIP_DIRS = {".git", "node_modules", "vendor", "target", "bin", "obj", "dist", ".next", ".venv", "venv", "__pycache__"}
HERE = os.path.dirname(os.path.abspath(__file__))


class Result:
    def __init__(self):
        self.imports = {}            # path -> (set(internal), set(external))  override regex
        self.units = []              # build units
        self.unit_of = {}            # path -> unit name
        self.enforced_units = False  # True when the compiler forbids undeclared cross-unit deps
        self.sources = {}            # lang -> description of the graph source
        self.notes = []              # what was tried and why it fell back
        self.std_externals = set()   # externals to drop (language standard library)
        self.not_compiled = set()    # files excluded by build configuration (Go build tags...)


def _run(cmd, cwd, timeout=300, env=None, input_text=None):
    try:
        e = dict(os.environ)
        if env:
            e.update(env)
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=e, input=input_text)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", str(exc)


def _walk(root, names=None, patterns=None, max_depth=8):
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".") and depth < max_depth]
        for f in filenames:
            if (names and f in names) or (patterns and any(fnmatch.fnmatch(f, p) for p in patterns)):
                yield os.path.join(dirpath, f)


def _rel(p, root):
    return os.path.relpath(p, root).replace(os.sep, "/")


def _nearest_unit(path, unit_dirs):
    """unit_dirs: list of (dir, name) sorted by dir length desc."""
    for d, name in unit_dirs:
        if d == "" or path == d or path.startswith(d + "/"):
            return name
    return None


def _closure(units):
    deps = {u["name"]: set(u["deps"]) for u in units}
    out = {}
    for u in deps:
        seen, stack = set(), list(deps[u])
        while stack:
            x = stack.pop()
            if x in seen or x not in deps:
                continue
            seen.add(x)
            stack.extend(deps[x])
        out[u] = seen
    return out


# ---------------------------------------------------------------------------
# Build units
# ---------------------------------------------------------------------------


def units_dotnet(ctx, res):
    projs = list(_walk(ctx.root, patterns=["*.csproj", "*.fsproj", "*.vbproj"]))
    if not projs:
        return
    units = []
    by_path = {}
    for p in projs:
        try:
            tree = ET.parse(p)
        except ET.ParseError as exc:
            res.notes.append(f".NET: could not parse {_rel(p, ctx.root)} ({exc})")
            continue
        root_el = tree.getroot()
        for el in root_el.iter():
            if "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]
        name = os.path.splitext(os.path.basename(p))[0]
        an = root_el.find(".//AssemblyName")
        if an is not None and (an.text or "").strip() and "$(" not in an.text:
            name = an.text.strip()
        refs = [r.get("Include", "").replace("\\", "/") for r in root_el.iter("ProjectReference")]
        pkgs = [r.get("Include") for r in root_el.iter("PackageReference") if r.get("Include")]
        d = _rel(os.path.dirname(p), ctx.root)
        u = {"name": name, "kind": "dotnet-project", "dir": "" if d == "." else d, "manifest": _rel(p, ctx.root),
             "deps_paths": [os.path.normpath(os.path.join(os.path.dirname(p), r)) for r in refs if r], "packages": pkgs,
             "sdk": root_el.get("Sdk", "")}
        units.append(u)
        by_path[os.path.normpath(p)] = name
    for u in units:
        u["deps"] = sorted({by_path[x] for x in u.pop("deps_paths") if x in by_path})
    res.units += units
    res.enforced_units = True
    res.sources["csharp"] = "type references (namespaces, using) constrained by the project graph (.csproj ProjectReference, exact)"


def _toml(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    if tomllib:
        try:
            return tomllib.loads(text)
        except Exception:
            pass
    # minimal fallback: package name, lib path, path dependencies, workspace members
    data = {"package": {}, "dependencies": {}, "workspace": {}}
    m = re.search(r"^\[package\][^\[]*?^name\s*=\s*\"([^\"]+)\"", text, re.M | re.S)
    if m:
        data["package"]["name"] = m.group(1)
    m = re.search(r"^\[lib\][^\[]*?^path\s*=\s*\"([^\"]+)\"", text, re.M | re.S)
    if m:
        data["lib"] = {"path": m.group(1)}
    for m in re.finditer(r"^([\w-]+)\s*=\s*\{[^}]*path\s*=\s*\"([^\"]+)\"", text, re.M):
        data["dependencies"][m.group(1)] = {"path": m.group(2)}
    m = re.search(r"members\s*=\s*\[([^\]]*)\]", text, re.S)
    if m:
        data["workspace"]["members"] = re.findall(r"\"([^\"]+)\"", m.group(1))
    return data


def units_rust(ctx, res):
    manifests = list(_walk(ctx.root, names={"Cargo.toml"}))
    if not manifests:
        return
    crates = {}
    meta_ok = False
    if shutil.which("cargo"):
        # cargo metadata reads manifests only; --no-deps --offline avoids network and build scripts
        top = sorted(manifests, key=lambda p: p.count(os.sep))[0]
        code, out, err = _run(["cargo", "metadata", "--no-deps", "--format-version", "1", "--offline"], os.path.dirname(top), 120)
        if code == 0:
            try:
                meta = json.loads(out)
                for pkg in meta.get("packages", []):
                    mdir = os.path.dirname(pkg["manifest_path"])
                    lib = next((t for t in pkg.get("targets", []) if "lib" in t.get("kind", []) or "proc-macro" in t.get("kind", [])), None)
                    roots = [t["src_path"] for t in pkg.get("targets", []) if set(t.get("kind", [])) & {"lib", "bin", "proc-macro"}]
                    crates[pkg["name"]] = {
                        "dir": mdir, "lib": lib["src_path"] if lib else None,
                        "lib_name": (lib["name"] if lib else pkg["name"]).replace("-", "_"),
                        "roots": roots,
                        "deps": [(d.get("rename") or d["name"]) for d in pkg.get("dependencies", []) if d.get("path")],
                        "dep_names": {(d.get("rename") or d["name"]).replace("-", "_"): d["name"] for d in pkg.get("dependencies", []) if d.get("path")},
                    }
                meta_ok = bool(crates)
            except (ValueError, KeyError) as exc:
                res.notes.append(f"Rust: cargo metadata output unreadable ({exc})")
        else:
            res.notes.append("Rust: cargo metadata failed, Cargo.toml parsed directly (" + (err.strip().splitlines() or ["?"])[-1][:160] + ")")
    if not crates:
        for m in manifests:
            data = _toml(m)
            pkg = data.get("package") or {}
            if not pkg.get("name"):
                continue
            mdir = os.path.dirname(m)
            lib_path = (data.get("lib") or {}).get("path") or ("src/lib.rs" if os.path.exists(os.path.join(mdir, "src/lib.rs")) else None)
            roots = [os.path.join(mdir, x) for x in ("src/lib.rs", "src/main.rs") if os.path.exists(os.path.join(mdir, x))]
            if lib_path:
                roots.append(os.path.join(mdir, lib_path))
            deps = {k: v for k, v in (data.get("dependencies") or {}).items() if isinstance(v, dict) and v.get("path")}
            crates[pkg["name"]] = {
                "dir": mdir, "lib": os.path.join(mdir, lib_path) if lib_path else None,
                "lib_name": pkg["name"].replace("-", "_"), "roots": sorted(set(roots)),
                "deps": [v.get("package", k) for k, v in deps.items()],
                "dep_names": {k.replace("-", "_"): v.get("package", k) for k, v in deps.items()},
            }
    for name, c in crates.items():
        d = _rel(c["dir"], ctx.root)
        res.units.append({"name": name, "kind": "rust-crate", "dir": "" if d == "." else d,
                          "manifest": (d + "/" if d != "." else "") + "Cargo.toml", "deps": sorted(set(c["deps"]) & set(crates))})
    res.enforced_units = True
    ctx.rust_crates = crates
    res.sources["rust"] = ("cargo metadata" if meta_ok else "Cargo.toml") + " crate graph (exact) + module paths (`mod`, `use`)"


def units_java(ctx, res):
    poms = list(_walk(ctx.root, names={"pom.xml"}))
    settings = [p for p in _walk(ctx.root, names={"settings.gradle", "settings.gradle.kts"}, max_depth=3)]
    units = []
    if poms:
        arts = {}
        for p in poms:
            try:
                tree = ET.parse(p)
            except ET.ParseError:
                continue
            r = tree.getroot()
            for el in r.iter():
                if "}" in el.tag:
                    el.tag = el.tag.split("}", 1)[1]
            aid = r.find("artifactId")
            if aid is None:
                continue
            if (r.findtext("packaging") or "").strip() == "pom":
                continue  # aggregator / parent POM: no sources of its own
            deps = [d.findtext("artifactId") for d in r.findall("./dependencies/dependency")]
            arts[aid.text.strip()] = (p, [x.strip() for x in deps if x])
        for aid, (p, deps) in arts.items():
            d = _rel(os.path.dirname(p), ctx.root)
            units.append({"name": aid, "kind": "maven-module", "dir": "" if d == "." else d, "manifest": _rel(p, ctx.root),
                          "deps": sorted(x for x in deps if x in arts and x != aid)})
    elif settings:
        s = settings[0]
        base = os.path.dirname(s)
        text = open(s, encoding="utf-8", errors="replace").read()
        names = []
        for m in re.finditer(r"include\s*\(?([^)\n]+)\)?", text):
            names += re.findall(r"[\"']:?([\w\-:.]+)[\"']", m.group(1))
        dirs = {}
        for n in names:
            dirs[n.split(":")[-1]] = os.path.join(base, n.replace(":", "/"))
        for n, d in dirs.items():
            deps = set()
            for bf in ("build.gradle", "build.gradle.kts"):
                bp = os.path.join(d, bf)
                if os.path.exists(bp):
                    bt = open(bp, encoding="utf-8", errors="replace").read()
                    deps |= {x.split(":")[-1] for x in re.findall(r"project\(\s*(?:path\s*[:=]\s*)?[\"']:?([\w\-:.]+)[\"']", bt)}
                    deps |= {x.replace(".", "-") for x in re.findall(r"projects\.([\w.]+)", bt)}
            rd = _rel(d, ctx.root)
            units.append({"name": n, "kind": "gradle-project", "dir": "" if rd == "." else rd,
                          "manifest": _rel(s, ctx.root), "deps": sorted(x for x in deps if x in dirs and x != n)})
    if len(units) > 1:
        res.units += units
        res.enforced_units = True


def units_js(ctx, res):
    pkgs = {}
    for p in _walk(ctx.root, names={"package.json"}, max_depth=5):
        if os.path.dirname(p) == ctx.root:
            continue
        try:
            data = json.load(open(p, encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if isinstance(data.get("name"), str):
            alldeps = {}
            for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                if isinstance(data.get(k), dict):
                    alldeps.update(data[k])
            pkgs[data["name"]] = (p, alldeps)
    if len(pkgs) < 2:
        return
    for name, (p, deps) in pkgs.items():
        d = _rel(os.path.dirname(p), ctx.root)
        res.units.append({"name": name, "kind": "npm-package", "dir": d, "manifest": _rel(p, ctx.root),
                          "deps": sorted(x for x in deps if x in pkgs and x != name)})
    # not enforced: hoisted node_modules let undeclared workspace imports work (phantom dependencies)


CMAKE_TARGET_RE = re.compile(r"\badd_(library|executable)\s*\(\s*([\w\-.:]+)([^)]*)\)", re.I | re.S)
CMAKE_LINK_RE = re.compile(r"\btarget_link_libraries\s*\(\s*([\w\-.:]+)([^)]*)\)", re.I | re.S)
CMAKE_INC_RE = re.compile(r"\b(?:target_)?include_directories\s*\(([^)]*)\)", re.I | re.S)


def _cmake_subst(token, cdir, root):
    t = token.strip().strip('"')
    for var in ("${CMAKE_CURRENT_SOURCE_DIR}", "${CMAKE_CURRENT_LIST_DIR}"):
        t = t.replace(var, cdir)
    for var in ("${PROJECT_SOURCE_DIR}", "${CMAKE_SOURCE_DIR}"):
        t = t.replace(var, root)
    if "${" in t or "$<" in t:
        return None
    return os.path.normpath(t if os.path.isabs(t) else os.path.join(cdir, t))


def units_cmake(ctx, res):
    lists = list(_walk(ctx.root, names={"CMakeLists.txt"}))
    if not lists:
        return
    targets, inc_dirs = {}, set()
    for cl in lists:
        cdir = os.path.dirname(cl)
        text = re.sub(r"#[^\n]*", "", open(cl, encoding="utf-8", errors="replace").read())
        for m in CMAKE_TARGET_RE.finditer(text):
            name = m.group(2)
            if name.upper().startswith("${"):
                continue
            srcs = []
            for tok in m.group(3).split():
                if tok.upper() in ("STATIC", "SHARED", "MODULE", "INTERFACE", "OBJECT", "ALIAS", "IMPORTED", "GLOBAL", "WIN32", "MACOSX_BUNDLE", "EXCLUDE_FROM_ALL"):
                    continue
                path = _cmake_subst(tok, cdir, ctx.root)
                if path and os.path.isfile(path):
                    srcs.append(_rel(path, ctx.root))
            targets[name] = {"dir": cdir, "srcs": srcs, "deps": set(), "kind": m.group(1).lower()}
        for m in CMAKE_LINK_RE.finditer(text):
            if m.group(1) in targets:
                targets[m.group(1)]["deps"] |= {t for t in m.group(2).split() if t not in ("PUBLIC", "PRIVATE", "INTERFACE")}
        for m in CMAKE_INC_RE.finditer(text):
            for tok in m.group(1).split():
                if tok.upper() in ("PUBLIC", "PRIVATE", "INTERFACE", "SYSTEM", "BEFORE", "AFTER"):
                    continue
                path = _cmake_subst(tok, cdir, ctx.root)
                if path and os.path.isdir(path):
                    inc_dirs.add(path)
    ctx.cmake_include_dirs = sorted(inc_dirs)
    if len(targets) > 1:
        for name, t in targets.items():
            d = _rel(t["dir"], ctx.root)
            res.units.append({"name": name, "kind": "cmake-" + t["kind"], "dir": "" if d == "." else d,
                              "manifest": (d + "/" if d != "." else "") + "CMakeLists.txt", "srcs": t["srcs"],
                              "deps": sorted(x for x in t["deps"] if x in targets and x != name)})


# ---------------------------------------------------------------------------
# C / C++
# ---------------------------------------------------------------------------

INCLUDE_LINE_RE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]', re.M)
KEEP_FLAG_RE = re.compile(r"^(-I|-isystem|-iquote|-idirafter|-D|-U|-std=|-include|--sysroot|-nostdinc|-x$|-f(no-)?(exceptions|rtti|char8_t)$|-m\d\d$)")
PAIRED = {"-I", "-isystem", "-iquote", "-idirafter", "-D", "-U", "-include", "-x", "--sysroot"}


def _find_compile_commands(root):
    found = []
    for pat in ("compile_commands.json", "build/compile_commands.json", "*/compile_commands.json",
                "*/*/compile_commands.json", "out/build/*/compile_commands.json", "cmake-build-*/compile_commands.json"):
        found += glob.glob(os.path.join(root, pat))
    found = [f for f in found if "node_modules" not in f]
    return sorted(set(found), key=lambda f: (-os.path.getsize(f), f))


def _parse_cc_entry(e):
    args = e.get("arguments") or shlex.split(e.get("command", ""))
    d = e.get("directory", "")
    f = e.get("file", "")
    f = os.path.normpath(f if os.path.isabs(f) else os.path.join(d, f))
    flags, quote, angle, i = [], [], [], 1

    def absdir(v):
        return os.path.normpath(v if os.path.isabs(v) else os.path.join(d, v))

    while i < len(args):
        a = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else None
        if a in ("-o", "-MF", "-MT", "-MQ"):
            i += 2
            continue
        m = re.match(r"^(-I|-isystem|-iquote|-idirafter|-D|-U|-include|--sysroot)(=?)(.*)$", a)
        if m:
            opt, val = m.group(1), m.group(3)
            if not val and nxt is not None:
                val = nxt
                i += 1
            i += 1
            if opt in ("-I", "-isystem", "-idirafter"):
                angle.append(absdir(val))
                flags += [opt, absdir(val)]
            elif opt == "-iquote":
                quote.append(absdir(val))
                flags += [opt, absdir(val)]
            elif opt == "-include":
                flags += [opt, absdir(val)]
            else:
                flags.append(opt + ("=" if opt == "--sysroot" else "") + val)
            continue
        if re.match(r"^(-std=|-nostdinc|-f(no-)?(exceptions|rtti|char8_t)$|-m(32|64)$)", a):
            flags.append(a)
        i += 1
    return {"file": f, "dir": d, "compiler": args[0] if args else None, "flags": flags, "quote": quote, "angle": angle}


def _resolve_include(spec, kind, from_abs, quote_dirs, angle_dirs):
    cands = []
    if kind == '"':
        cands.append(os.path.dirname(from_abs))
        cands += quote_dirs
    cands += angle_dirs
    for d in cands:
        p = os.path.normpath(os.path.join(d, spec))
        if os.path.isfile(p):
            return p
    return None


def _preprocessor_tree(entry, compiler, root):
    """Run the preprocessor with -H and return (edges abs->abs set, externals set). Executes no repo code."""
    if not compiler:
        return None
    x = []
    if entry["file"].endswith((".c",)):
        x = ["-x", "c"]
    cmd = [compiler] + x + entry["flags"] + ["-E", "-H", "-o", os.devnull, entry["file"]]
    code, out, err = _run(cmd, entry["dir"] or root, timeout=90)
    if code == -1:
        return None
    edges, ext = set(), set()
    stack = [os.path.normpath(entry["file"])]
    for line in err.splitlines():
        m = re.match(r"^(\.+) (.+)$", line)
        if not m:
            continue
        depth = len(m.group(1))
        path = os.path.normpath(m.group(2) if os.path.isabs(m.group(2)) else os.path.join(entry["dir"] or root, m.group(2)))
        del stack[depth:]
        parent = stack[-1] if stack else None
        stack.append(path)
        if parent is None:
            continue
        inside = path.startswith(root + os.sep) and "/node_modules/" not in path
        if inside:
            edges.add((parent, path))
        elif parent.startswith(root + os.sep):
            ext.add((parent, path))
    return edges, ext


def _ext_name(header_abs):
    parts = header_abs.replace(os.sep, "/").split("/")
    for marker in ("include", "Headers", "Frameworks"):
        if marker in parts:
            i = len(parts) - 1 - parts[::-1].index(marker)
            if i + 1 < len(parts):
                return parts[i + 1].split(".")[0]
    return parts[-1]


def adapter_cpp(ctx, res, max_tu=4000):
    cfiles = [p for p, f in ctx.files_meta.items() if f["lang"] == "cpp"]
    if not cfiles:
        return
    ccs = _find_compile_commands(ctx.root)
    entries = []
    if not ccs and ctx.allow_build and shutil.which("cmake") and os.path.exists(os.path.join(ctx.root, "CMakeLists.txt")):
        bdir = tempfile.mkdtemp(prefix="re-arch-cmake-")
        code, out, err = _run(["cmake", "-S", ctx.root, "-B", bdir, "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"], ctx.root, 600)
        if code == 0 and os.path.exists(os.path.join(bdir, "compile_commands.json")):
            ccs = [os.path.join(bdir, "compile_commands.json")]
            res.notes.append("C/C++: compile_commands.json generated by a CMake configure step in a temporary build dir (--allow-build)")
        else:
            res.notes.append("C/C++: CMake configure failed, falling back to parsed include dirs (" + (err.strip().splitlines() or ["?"])[-1][:200] + ")")
    for cc in ccs[:3]:
        try:
            entries += [_parse_cc_entry(e) for e in json.load(open(cc, encoding="utf-8"))]
        except (ValueError, OSError) as exc:
            res.notes.append(f"C/C++: unreadable {cc} ({exc})")
    root = os.path.realpath(ctx.root)
    by_file = {}
    for e in entries:
        e["file"] = os.path.realpath(e["file"])
        if e["file"].startswith(root + os.sep):
            by_file.setdefault(_rel(e["file"], root), e)
    union_angle = []
    for e in entries:
        for d in e["angle"]:
            if d not in union_angle:
                union_angle.append(d)
    union_angle += [d for d in getattr(ctx, "cmake_include_dirs", []) if d not in union_angle]
    # conventional include roots as a last resort
    for d in ("include", "src", "inc", "source"):
        p = os.path.join(root, d)
        if os.path.isdir(p) and p not in union_angle:
            union_angle.append(p)
    compiler = None
    for c in ("clang++", "g++", "clang", "gcc", "c++", "cc"):
        if shutil.which(c):
            compiler = shutil.which(c)
            break
    # 1. header/source resolution with real include dirs
    for p in cfiles:
        f = ctx.files_meta[p]
        e = by_file.get(p)
        quote = e["quote"] if e else []
        angle = (e["angle"] if e else []) + [d for d in union_angle if not e or d not in e["angle"]]
        internal, external = set(), set()
        absf = os.path.join(root, p)
        for kind, spec in INCLUDE_LINE_RE.findall(f["_code"]):
            hit = _resolve_include(spec, kind, absf, quote, angle)
            if hit and os.path.realpath(hit).startswith(root + os.sep):
                rp = _rel(os.path.realpath(hit), root)
                if rp in ctx.file_set and rp != p:
                    internal.add(rp)
                    continue
            if kind == "<":
                external.add(spec.split("/")[0].split(".")[0])
            elif not hit:
                # unresolved quoted include: keep the old basename heuristic
                cands = [q for q in ctx.file_set if q.endswith("/" + spec) or q == spec]
                if len(cands) == 1:
                    internal.add(cands[0])
        res.imports[p] = (internal, external)
    # 2. preprocessor tree for translation units: adds macro-computed includes and confirms the rest
    tus = [e for k, e in by_file.items() if k in ctx.file_set]
    done = 0
    if tus and compiler and len(tus) <= max_tu:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 2))) as pool:
            for out in pool.map(lambda e: _preprocessor_tree(e, compiler, root), tus):
                if not out:
                    continue
                done += 1
                edges, ext = out
                for a, b in edges:
                    ra, rb = _rel(a, root), _rel(os.path.realpath(b), root)
                    if ra in res.imports and rb in ctx.file_set and ra != rb:
                        res.imports[ra][0].add(rb)
                for a, b in ext:
                    ra = _rel(a, root)
                    if ra in res.imports:
                        name = _ext_name(b)
                        if not name.startswith(("bits", "__")):
                            res.imports[ra][1].add(name)
    elif tus and len(tus) > max_tu:
        res.notes.append(f"C/C++: {len(tus)} translation units, preprocessor pass skipped above {max_tu} (include dirs still exact)")
    if entries:
        src = f"compile_commands.json ({len(by_file)} files with exact -I/-D)"
        if done:
            src += f" + preprocessor include tree ({done} translation units, {os.path.basename(compiler)} -E -H)"
        res.sources["cpp"] = src
    elif getattr(ctx, "cmake_include_dirs", None):
        res.sources["cpp"] = f"include dirs parsed from CMakeLists ({len(ctx.cmake_include_dirs)}); no compile_commands.json, so macros and per-target flags are not applied"
        res.notes.append("C/C++: generate compile_commands.json (cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON, bear -- make, or --allow-build) for an exact graph")
    else:
        res.sources["cpp"] = "conventional include roots (include/, src/); no build information found"


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------

GO_SPEC_LINE_RE = re.compile(r'^import\s+(?:[\w.]+\s+)?"([^"]+)"', re.M)
GO_BLOCK_RE = re.compile(r"^import\s*\((.*?)\)", re.M | re.S)
GO_INNER_RE = re.compile(r'(?:[\w.]+\s+)?"([^"]+)"')


def adapter_go(ctx, res):
    gfiles = [p for p, f in ctx.files_meta.items() if f["lang"] == "go"]
    if not gfiles or not shutil.which("go"):
        if gfiles:
            res.notes.append("Go: no go toolchain, module paths from go.mod (build tags not evaluated)")
        return
    mods = [os.path.dirname(p) for p in _walk(ctx.root, names={"go.mod"})]
    pkgs = {}
    std = set()
    env = {"GOTOOLCHAIN": "local", "GOPROXY": "off", "GOFLAGS": "-mod=mod", "GOWORK": "off", "CGO_ENABLED": "0"}
    for md in mods:
        code, out, err = _run(["go", "list", "-e", "-json", "./..."], md, 300, env)
        if code not in (0, 1) or not out.strip():
            res.notes.append(f"Go: go list failed in {_rel(md, ctx.root) or '.'} (" + (err.strip().splitlines() or ["?"])[-1][:160] + ")")
            continue
        dec = json.JSONDecoder()
        i = 0
        while i < len(out):
            while i < len(out) and out[i].isspace():
                i += 1
            if i >= len(out):
                break
            obj, i = dec.raw_decode(out, i)
            d = obj.get("Dir")
            if not d:
                continue
            rd = _rel(d, ctx.root)
            files = obj.get("GoFiles", []) + obj.get("CgoFiles", [])
            pkgs[obj["ImportPath"]] = {"dir": rd, "files": [(rd + "/" if rd != "." else "") + f for f in files]}
            for f in obj.get("IgnoredGoFiles", []):
                res.not_compiled.add((rd + "/" if rd != "." else "") + f)
            for imp in obj.get("Imports", []) + obj.get("TestImports", []) + obj.get("XTestImports", []):
                if "." not in imp.split("/")[0]:
                    std.add(imp)
    if not pkgs:
        return
    for p in gfiles:
        code = ctx.files_meta[p]["_code"]
        specs = GO_SPEC_LINE_RE.findall(code)
        for b in GO_BLOCK_RE.findall(code):
            specs += GO_INNER_RE.findall(b)
        internal, external = set(), set()
        for s in specs:
            if s in pkgs:
                internal.update(f for f in pkgs[s]["files"] if f in ctx.file_set and f != p)
            elif s in std or "." not in s.split("/")[0]:
                continue  # standard library
            else:
                external.add("/".join(s.split("/")[:3]))
        res.imports[p] = (internal, external)
    res.sources["go"] = f"go list ({len(pkgs)} packages, exact import paths, build tags applied, standard library excluded)"
    if res.not_compiled:
        res.notes.append(f"Go: {len(res.not_compiled)} files excluded by build constraints for this platform")


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------

RUST_USE_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?use\s+([^;]+);", re.M)
RUST_MOD_RE = re.compile(r"^\s*(?:#\[[^\]]*\]\s*)*(?:pub(?:\([^)]*\))?\s+)?mod\s+(\w+)\s*;", re.M)
RUST_PATH_ATTR_RE = re.compile(r"#\[path\s*=\s*\"([^\"]+)\"\]\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+(\w+)\s*;")
RUST_INLINE_PATH_RE = re.compile(r"\b(crate|super|self|[a-z_][a-z0-9_]*)::([a-z_][a-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*)")


def _expand_use(use):
    """Expand a use tree `a::{b, c::{d, e}}` into flat paths."""
    use = re.sub(r"\s+", "", use)
    out = []

    def rec(prefix, s):
        if "{" not in s:
            for part in s.split(","):
                if part:
                    out.append(prefix + part.split(" as ")[0])
            return
        i = s.index("{")
        head = s[:i]
        depth, j = 0, i
        for j in range(i, len(s)):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    break
        inner = s[i + 1:j]
        items, depth, cur = [], 0, ""
        for ch in inner:
            if ch == "," and depth == 0:
                items.append(cur)
                cur = ""
                continue
            depth += ch == "{"
            depth -= ch == "}"
            cur += ch
        items.append(cur)
        for it in items:
            rec(prefix + head, it)

    rec("", use)
    return [o.replace("::self", "") for o in out]


def adapter_rust(ctx, res):
    crates = getattr(ctx, "rust_crates", None)
    rfiles = [p for p, f in ctx.files_meta.items() if f["lang"] == "rust"]
    if not crates or not rfiles:
        return
    root = os.path.realpath(ctx.root)
    lib_roots = {}
    for name, c in crates.items():
        if c["lib"]:
            lib_roots[c["lib_name"]] = os.path.dirname(os.path.realpath(c["lib"]))
    # crate root dir for each file: nearest target src_path directory
    target_dirs = sorted({os.path.dirname(os.path.realpath(r)) for c in crates.values() for r in c["roots"]}, key=len, reverse=True)
    crate_of_dir = {}
    for name, c in crates.items():
        for r in c["roots"]:
            crate_of_dir[os.path.dirname(os.path.realpath(r))] = name

    def module_file(base_dir, segs):
        for n in range(len(segs), 0, -1):
            base = os.path.join(base_dir, *segs[:n])
            for cand in (base + ".rs", os.path.join(base, "mod.rs")):
                rp = _rel(cand, root)
                if rp in ctx.file_set:
                    return rp
        return None

    for p in rfiles:
        absf = os.path.join(root, p)
        croot = next((d for d in target_dirs if absf.startswith(d + os.sep)), None)
        if croot is None:
            continue
        cname = crate_of_dir.get(croot)
        dep_names = crates[cname]["dep_names"] if cname else {}
        code = ctx.files_meta[p]["_code"]
        here = os.path.dirname(absf)
        stem = os.path.splitext(os.path.basename(absf))[0]
        mod_dir = here if stem in ("mod", "lib", "main") or here == croot and stem in ("lib", "main") else os.path.join(here, stem)
        internal, external = set(), set()
        for path_attr, m in RUST_PATH_ATTR_RE.findall(code):
            rp = _rel(os.path.normpath(os.path.join(here, path_attr)), root)
            if rp in ctx.file_set:
                internal.add(rp)
        for m in RUST_MOD_RE.findall(code):
            for cand in (os.path.join(mod_dir, m + ".rs"), os.path.join(mod_dir, m, "mod.rs")):
                rp = _rel(cand, root)
                if rp in ctx.file_set:
                    internal.add(rp)
        local_mods = set(RUST_MOD_RE.findall(code)) | {m for _, m in RUST_PATH_ATTR_RE.findall(code)}
        paths = []
        for u in RUST_USE_RE.findall(code):
            paths += [(x, True) for x in _expand_use(u)]
        paths += [("::".join(x), False) for x in RUST_INLINE_PATH_RE.findall(code)]
        for path, from_use in paths:
            segs = [s_ for s_ in path.split("::") if s_ and s_ != "*"]
            if not segs:
                continue
            head = segs[0]
            hit = None
            if head == "crate":
                hit = module_file(croot, segs[1:])
            elif head in ("super", "self"):
                base = mod_dir if head == "self" else os.path.dirname(mod_dir)
                rest = segs[1:]
                while rest and rest[0] == "super":
                    base, rest = os.path.dirname(base), rest[1:]
                hit = module_file(base, rest)
            elif head in local_mods:
                hit = module_file(mod_dir, segs)
            elif head in lib_roots and head != crates.get(cname, {}).get("lib_name"):
                hit = module_file(lib_roots[head], segs[1:])
                if not hit:
                    lib = _rel(os.path.join(lib_roots[head], "lib.rs"), root)
                    hit = lib if lib in ctx.file_set else None
            elif from_use and head not in ("std", "core", "alloc") and re.match(r"^[a-z_][a-z0-9_]*$", head):
                external.add(head)
            if hit and hit != p:
                internal.add(hit)
        res.imports[p] = (internal, {e for e in external if e not in lib_roots})


# ---------------------------------------------------------------------------
# Java / Kotlin (jdeps)
# ---------------------------------------------------------------------------

CLASS_DIRS = ("target/classes", "build/classes/java/main", "build/classes/kotlin/main", "build/tmp/kotlin-classes/main",
              "out/production/classes", "bin/main")


def adapter_java(ctx, res):
    jfiles = [p for p, f in ctx.files_meta.items() if f["lang"] == "java"]
    if not jfiles:
        return
    jdeps = shutil.which("jdeps")
    unit_dirs = [os.path.join(ctx.root, u["dir"]) for u in res.units if u["kind"] in ("maven-module", "gradle-project")] or [ctx.root]
    if ctx.allow_build and not any(os.path.isdir(os.path.join(d, c)) for d in unit_dirs for c in CLASS_DIRS):
        if os.path.exists(os.path.join(ctx.root, "pom.xml")) and shutil.which("mvn"):
            _run(["mvn", "-q", "-o", "-DskipTests", "compile"], ctx.root, 1200)
        elif os.path.exists(os.path.join(ctx.root, "gradlew")):
            _run(["./gradlew", "--offline", "-q", "classes"], ctx.root, 1200)
    class_dirs = [os.path.join(d, c) for d in unit_dirs for c in CLASS_DIRS if os.path.isdir(os.path.join(d, c))]
    if not jdeps or not class_dirs:
        if not class_dirs:
            res.notes.append("Java/Kotlin: no compiled classes found (target/classes, build/classes); build the project (or pass --allow-build) for an exact jdeps graph")
        return
    code, out, err = _run([jdeps, "-verbose:class", "-filter:none", "--multi-release", "base"] + class_dirs, ctx.root, 600)
    if code != 0 or not out:
        code, out, err = _run([jdeps, "-verbose:class", "-filter:none"] + class_dirs, ctx.root, 600)
    if not out:
        res.notes.append("Java/Kotlin: jdeps produced no output (" + (err.strip().splitlines() or ["?"])[-1][:160] + ")")
        return
    cls_index = ctx.idx.get("java_class", {})

    def to_file(fqn):
        base = fqn.split("$")[0]
        if base in cls_index:
            return cls_index[base]
        if base.endswith("Kt") and base[:-2] in cls_index:
            return cls_index[base[:-2]]
        pkg, _, simple = base.rpartition(".")
        if simple.endswith("Kt"):
            stem = simple[:-2]
            for p in ctx.files_meta:
                if p.endswith("/" + stem + ".kt") and ctx.files_meta[p]["_code"].find("package " + pkg) >= 0:
                    return p
        return None

    seen = collections.defaultdict(lambda: (set(), set()))
    n = 0
    for line in out.splitlines():
        m = re.match(r"^\s+(\S+)\s+->\s+(\S+)\s+(\S+)", line)
        if not m:
            continue
        src, dst, where = m.groups()
        fs = to_file(src)
        if not fs:
            continue
        fd = to_file(dst)
        if fd and fd != fs:
            seen[fs][0].add(fd)
            n += 1
        elif not fd and not dst.startswith(("java.", "javax.", "jdk.", "sun.", "kotlin.")):
            seen[fs][1].add(".".join(dst.split(".")[:2]))
    for p, v in seen.items():
        res.imports[p] = v
    res.sources["java"] = f"jdeps on compiled classes ({len(seen)} source files mapped, {n} class-level references)"


# ---------------------------------------------------------------------------
# JS / TS via TypeScript's resolver
# ---------------------------------------------------------------------------


def _find_typescript(ctx):
    for base in [ctx.root] + [os.path.join(ctx.root, u["dir"]) for u in getattr(ctx, "js_units", [])]:
        p = os.path.join(base, "node_modules", "typescript", "lib", "typescript.js")
        if os.path.exists(p):
            return p
    cache = os.path.join(os.path.expanduser("~"), ".cache", "re-arch-scan", "node_modules", "typescript", "lib", "typescript.js")
    if os.path.exists(cache):
        return cache
    if ctx.fetch_tools and shutil.which("npm"):
        target = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(cache))))
        os.makedirs(target, exist_ok=True)
        code, out, err = _run(["npm", "install", "--prefix", target, "--no-audit", "--no-fund", "--silent", "typescript@5"], target, 300)
        if code == 0 and os.path.exists(cache):
            return cache
    return None


def adapter_js(ctx, res):
    jfiles = [p for p, f in ctx.files_meta.items() if f["lang"] == "js"]
    if not jfiles or not shutil.which("node"):
        return
    ctx.js_units = [u for u in res.units if u["kind"] == "npm-package"]
    ts = _find_typescript(ctx)
    if not ts:
        res.notes.append("JS/TS: typescript package not found in the repo (run the install first, or pass --fetch-tools) so resolution uses tsconfig paths and workspaces parsed by the scanner")
        return
    script = os.path.join(HERE, "ts_resolve.js")
    payload = json.dumps({"root": os.path.realpath(ctx.root), "files": [os.path.join(os.path.realpath(ctx.root), p) for p in jfiles], "typescript": ts})
    code, out, err = _run(["node", script], ctx.root, 900, input_text=payload)
    if code != 0:
        res.notes.append("JS/TS: TypeScript resolver failed (" + (err.strip().splitlines() or ["?"])[-1][:200] + ")")
        return
    data = json.loads(out)
    root = os.path.realpath(ctx.root)
    resolved = 0
    for absf, items in data["files"].items():
        p = _rel(absf, root)
        if p not in ctx.files_meta:
            continue
        internal, external = set(), set()
        for spec, target in items:
            if target:
                t = os.path.realpath(target)
                rp = _rel(t, root)
                if t.startswith(root + os.sep) and "/node_modules/" not in t:
                    if rp in ctx.file_set:
                        internal.add(rp)
                        resolved += 1
                        continue
                    # .d.ts or dist build of a workspace package: map back to sources
                    alt = re.sub(r"/dist/", "/src/", rp)
                    alt = re.sub(r"\.d\.(c|m)?ts$", "", alt)
                    hit = next((alt + e for e in (".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx") if alt + e in ctx.file_set), None)
                    if hit:
                        internal.add(hit)
                        resolved += 1
                        continue
            if not target and getattr(ctx, "js_fallback", None):
                # not resolvable by TypeScript here (workspace not installed, custom alias): scanner's own resolution
                hit = ctx.js_fallback(spec, p)
                if hit:
                    internal.add(hit)
                    continue
                if ctx.js_is_workspace(spec):
                    continue
            if spec.startswith((".", "/")):
                continue  # relative import that does not resolve: asset or missing file
            if spec.startswith("node:") or spec in data.get("builtins", []):
                continue
            parts = spec.split("/")
            external.add("/".join(parts[:2]) if spec.startswith("@") else parts[0])
        if p in ctx.file_set:
            res.imports[p] = (internal - {p}, external)
    res.sources["js"] = f"TypeScript module resolution ({os.path.relpath(ts, ctx.root) if ts.startswith(ctx.root) else 'typescript ' + data.get('version', '')}, tsconfig per file, workspaces via node_modules)"


# ---------------------------------------------------------------------------
# PHP via the PHP tokenizer
# ---------------------------------------------------------------------------


def adapter_php(ctx, res):
    pfiles = [p for p, f in ctx.files_meta.items() if f["lang"] == "php"]
    if not pfiles:
        return
    if not shutil.which("php"):
        res.notes.append("PHP: no php binary, class references resolved by regex (use statements, same namespace, inline names)")
        return
    script = os.path.join(HERE, "php_refs.php")
    root = os.path.realpath(ctx.root)
    payload = json.dumps([os.path.join(root, p) for p in pfiles])
    code, out, err = _run(["php", "-d", "memory_limit=1G", "-d", "error_reporting=0", script], ctx.root, 900, input_text=payload)
    if code != 0 or not out.strip().startswith("{"):
        res.notes.append("PHP: tokenizer pass failed (" + ((err or out).strip().splitlines() or ["?"])[-1][:200] + ")")
        return
    data = json.loads(out)
    cls_index = ctx.idx.get("php_class", {})
    lower_index = {k.lower(): v for k, v in cls_index.items()}
    for absf, refs in data.items():
        p = _rel(absf, root)
        if p not in ctx.files_meta:
            continue
        internal, external = set(), set()
        for name, from_use in refs:
            t = cls_index.get(name) or lower_index.get(name.lower())
            if t and t != p:
                internal.add(t)
            elif not t and from_use and "\\" in name:
                external.add(name.split("\\")[0])
        res.imports[p] = (internal, external)
    res.sources["php"] = "PHP tokenizer (every class name reference resolved with namespace and use rules, incl. same-namespace and ::class)"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(ctx):
    res = Result()
    steps = [units_dotnet, units_rust, units_java, units_js, units_cmake,
             adapter_cpp, adapter_go, adapter_rust, adapter_java, adapter_js, adapter_php]
    for step in steps:
        try:
            step(ctx, res)
        except Exception as exc:  # an adapter must never break the scan
            res.notes.append(f"{step.__name__} skipped after an error: {type(exc).__name__}: {exc}")
    # unit membership: explicit sources (CMake) first, then nearest unit directory
    unit_dirs = sorted(((u["dir"], u["name"]) for u in res.units), key=lambda x: -len(x[0]))
    explicit = {}
    for u in res.units:
        for s in u.get("srcs", []):
            explicit.setdefault(s, u["name"])
    for p in ctx.files_meta:
        name = explicit.get(p) or _nearest_unit(p, unit_dirs)
        if name:
            res.unit_of[p] = name
    return res


def prune_undeclared(res, files_meta, edges):
    """Drop file edges that cross enforced build units without a declared
    (transitive) dependency: the compiler would reject them, so they are
    resolution errors of the heuristic layer. Returns the dropped edges."""
    if not res.enforced_units or not res.units:
        return []
    closure = _closure(res.units)
    enforced_kinds = {"dotnet-project", "rust-crate", "maven-module", "gradle-project"}
    kind = {u["name"]: u["kind"] for u in res.units}
    dropped = []
    for p, ts in edges.items():
        ua = res.unit_of.get(p)
        if not ua or kind.get(ua) not in enforced_kinds:
            continue
        keep = []
        for t in ts:
            ub = res.unit_of.get(t)
            if ub and ub != ua and kind.get(ub) in enforced_kinds and ub not in closure.get(ua, set()):
                dropped.append((p, t))
            else:
                keep.append(t)
        edges[p] = keep
    return dropped


def undeclared_workspace_deps(res, edges):
    """JS workspaces: imports of another workspace package not declared in package.json (phantom dependencies)."""
    units = {u["name"]: u for u in res.units if u["kind"] == "npm-package"}
    if not units:
        return []
    out = collections.Counter()
    for p, ts in edges.items():
        ua = res.unit_of.get(p)
        if ua not in units:
            continue
        for t in ts:
            ub = res.unit_of.get(t)
            if ub in units and ub != ua and ub not in units[ua]["deps"]:
                out[(ua, ub)] += 1
    return [{"from": a, "to": b, "imports": n} for (a, b), n in out.most_common()]
