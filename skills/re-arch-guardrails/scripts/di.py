#!/usr/bin/env python3
"""
di.py: dependency-injection wiring for re-arch-scan.

With DI, a consumer imports an abstraction (interface, abstract class, token)
and the container decides which implementation runs. The import graph sees
consumer -> abstraction, never consumer -> implementation. This module finds
the bindings and returns "runtime" edges consumer -> implementation, which the
scan keeps separate from source imports:
  - source imports drive layering rules (the dependency rule is about source code);
  - runtime edges complete coupling, clusters and hotspots (what actually runs together).

Bindings found:
  explicit             .NET (AddScoped/AddTransient/AddSingleton<I,T>, typeof, Autofac As<I>, AddHttpClient<I,T>)
                       NestJS / Angular ({ provide: X, useClass: Y }, string tokens + @Inject('X'))
                       Laravel (bind/singleton/scoped I::class => T::class, closures returning new T,
                                $bindings/$singletons arrays, when()->needs()->give(), facades -> accessor)
                       Symfony (services.yaml aliases and class:)
                       Spring (@Bean methods returning new T for type I)
                       Go (wire.Bind(new(I), new(*T)))
  single-implementation an abstraction with exactly one non-test implementation in the repo
                       (autowiring in Spring, Symfony, .NET scanners, Nest abstract-class tokens...)
Go interfaces are structural, so the single-implementation rule is not applied to Go.
"""
import collections
import os
import re

MOCK_RE = re.compile(r"(?i)(mock|fake|stub|dummy|spy|test|inmemory|in_memory|noop)")

DECL = {
    "js": [
        (re.compile(r"\binterface\s+([A-Z]\w*)"), "interface"),
        (re.compile(r"\babstract\s+class\s+([A-Z]\w*)"), "abstract"),
        (re.compile(r"\bclass\s+([A-Z]\w*)"), "class"),
    ],
    "java": [
        (re.compile(r"\binterface\s+([A-Z]\w*)"), "interface"),
        (re.compile(r"\babstract\s+class\s+([A-Z]\w*)"), "abstract"),
        (re.compile(r"\b(?:sealed\s+|open\s+|data\s+)?class\s+([A-Z]\w*)"), "class"),
    ],
    "csharp": [
        (re.compile(r"\binterface\s+(I[A-Z]\w*|[A-Z]\w*)"), "interface"),
        (re.compile(r"\babstract\s+(?:partial\s+)?class\s+([A-Z]\w*)"), "abstract"),
        (re.compile(r"\b(?:sealed\s+|partial\s+|static\s+)*class\s+([A-Z]\w*)"), "class"),
        (re.compile(r"\brecord\s+(?:class\s+|struct\s+)?([A-Z]\w*)"), "class"),
    ],
    "php": [
        (re.compile(r"^\s*interface\s+(\w+)", re.M), "interface"),
        (re.compile(r"^\s*abstract\s+class\s+(\w+)", re.M), "abstract"),
        (re.compile(r"^\s*(?:final\s+|readonly\s+)*class\s+(\w+)", re.M), "class"),
        (re.compile(r"^\s*trait\s+(\w+)", re.M), "trait"),
    ],
    "rust": [
        (re.compile(r"\btrait\s+([A-Z]\w*)"), "interface"),
        (re.compile(r"\b(?:struct|enum)\s+([A-Z]\w*)"), "class"),
    ],
    "cpp": [
        (re.compile(r"\b(?:class|struct)\s+(?:\w+\s+)?([A-Z]\w*)\s*(?::[^{;]*)?\{"), "class"),
    ],
    "go": [
        (re.compile(r"^type\s+([A-Z]\w*)\s+interface\b", re.M), "interface"),
        (re.compile(r"^type\s+([A-Z]\w*)\s+struct\b", re.M), "class"),
    ],
}

IMPL = {
    "js": re.compile(r"\bclass\s+([A-Z]\w*)(?:<[^>{]*>)?(?:\s+extends\s+([\w.]+)(?:<[^>{]*>)?)?(?:\s+implements\s+([\w.,\s<>]+?))?\s*\{"),
    "java": re.compile(r"\bclass\s+([A-Z]\w*)(?:<[^>{]*>)?(?:\([^)]*\))?(?:\s+extends\s+([\w.]+)(?:<[^>{]*>)?)?(?:\s+implements\s+([\w.,\s<>]+?))?(?:\s*:\s*([\w.,\s<>()]+?))?\s*\{"),
    "csharp": re.compile(r"\b(?:class|record)\s+([A-Z]\w*)(?:<[^>{:]*>)?(?:\([^)]*\))?\s*:\s*([\w.,\s<>]+?)\s*(?:where\b[^{]*)?\{"),
    "php": re.compile(r"^\s*(?:final\s+|abstract\s+|readonly\s+)*class\s+(\w+)(?:\s+extends\s+([\\\w]+))?(?:\s+implements\s+([\\\w,\s]+?))?\s*\{", re.M),
    "rust": re.compile(r"\bimpl(?:<[^>]*>)?\s+([\w:]+)(?:<[^>]*>)?\s+for\s+([\w:]+)"),
    "cpp": re.compile(r"\b(?:class|struct)\s+(?:\w+\s+)?([A-Z]\w*)\s*(?:final\s*)?:\s*([^{;]+)\{"),
}

PURE_VIRTUAL_RE = re.compile(r"virtual[^;{}]*=\s*0\s*;")

# --- explicit registrations ---------------------------------------------------
DOTNET_GENERIC = re.compile(r"\.(?:Add|TryAdd)(Scoped|Transient|Singleton|HttpClient)\s*<\s*([\w.]+)(?:<[^>]*>)?\s*,\s*([\w.]+)(?:<[^>]*>)?\s*>")
DOTNET_TYPEOF = re.compile(r"\.(?:Add|TryAdd)(Scoped|Transient|Singleton)\s*\(\s*typeof\(\s*([\w.]+)(?:<[^>]*>)?\s*\)\s*,\s*typeof\(\s*([\w.]+)(?:<[^>]*>)?\s*\)")
AUTOFAC = re.compile(r"RegisterType<\s*([\w.]+)\s*>\s*\(\s*\)(?:\s*\.\w+\([^)]*\))*?\s*\.As<\s*([\w.]+)\s*>")
NEST = re.compile(r"provide\s*:\s*([A-Z]\w*|'[^']+'|\"[^\"]+\"|Symbol\([^)]*\))\s*,\s*use(Class|Existing)\s*:\s*([A-Z]\w*)")
NEST_INJECT = re.compile(r"@Inject\(\s*('[^']+'|\"[^\"]+\"|[A-Z_][\w]*)\s*\)")
LARAVEL_BIND = re.compile(r"->\s*(bind|singleton|scoped|bindIf|singletonIf|instance)\s*\(\s*\\?([\\\w]+)::class\s*,\s*\\?([\\\w]+)::class")
LARAVEL_CLOSURE = re.compile(r"->\s*(bind|singleton|scoped)\s*\(\s*\\?([\\\w]+)::class\s*,\s*(?:static\s+)?(?:function|fn)\b[^;]*?new\s+\\?([\\\w]+)", re.S)
LARAVEL_ARRAY = re.compile(r"\$(?:bindings|singletons)\s*=\s*\[(.*?)\];", re.S)
LARAVEL_PAIR = re.compile(r"\\?([\\\w]+)::class\s*=>\s*\\?([\\\w]+)::class")
LARAVEL_GIVE = re.compile(r"->needs\(\s*\\?([\\\w]+)::class\s*\)\s*->give\(\s*\\?([\\\w]+)::class")
FACADE = re.compile(r"class\s+(\w+)\s+extends\s+\\?(?:Illuminate\\Support\\Facades\\)?Facade\b.*?getFacadeAccessor\s*\(\s*\)\s*(?::\s*string\s*)?\{\s*return\s+(?:\\?([\\\w]+)::class|'([^']+)'|\"([^\"]+)\")", re.S)
LARAVEL_STRING_BIND = re.compile(r"->\s*(?:bind|singleton|scoped)\s*\(\s*'([^']+)'\s*,\s*(?:\\?([\\\w]+)::class|(?:static\s+)?(?:function|fn)\b[^;]*?new\s+\\?([\\\w]+))", re.S)
SPRING_BEAN = re.compile(r"@Bean\b[^\n]*\n(?:\s*@[^\n]*\n)*\s*(?:public\s+|protected\s+)?(?:fun\s+\w+\([^)]*\)\s*:\s*([\w.]+)|([\w.]+)(?:<[^>]*>)?\s+\w+\s*\([^)]*\))[^{]*\{[^}]*?(?:return\s+)?new\s+([\w.]+)|@Bean\b[^\n]*\n\s*fun\s+\w+\([^)]*\)\s*:\s*([\w.]+)\s*=\s*([A-Z]\w*)\(")
WIRE_BIND = re.compile(r"wire\.Bind\(\s*new\(\s*([\w.]+)\s*\)\s*,\s*new\(\s*\*?([\w.]+)\s*\)\s*\)")
SYMFONY_ALIAS = re.compile(r"^\s{2,}['\"]?([A-Z][\w\\]+)['\"]?\s*:\s*['\"]@([A-Z][\w\\]+)['\"]", re.M)
SYMFONY_CLASS = re.compile(r"^\s{2,}['\"]?([A-Z][\w\\]+)['\"]?\s*:\s*\n\s{4,}(?:class|alias)\s*:\s*['\"]?@?([A-Z][\w\\]+)", re.M)


def short(name):
    return re.split(r"[\\.:]", name.strip())[-1] if name else name


def extract(root, files_meta, file_set, idx):
    decls = collections.defaultdict(list)      # short -> [(file, kind, lang)]
    impls = collections.defaultdict(set)       # abstraction short -> {(impl_short, file)}
    for p, f in files_meta.items():
        lang, code = f["lang"], f.get("_code") or ""
        for rx, kind in DECL.get(lang, []):
            for m in rx.finditer(code):
                name = m.group(1)
                decls[name].append((p, kind, lang))
        if lang == "cpp":
            for m in IMPL["cpp"].finditer(code):
                for base in re.findall(r"(?:public|protected|private)?\s*(?:virtual\s+)?([A-Z]\w*)", m.group(2)):
                    impls[base].add((m.group(1), p))
            if PURE_VIRTUAL_RE.search(code):
                for m in re.finditer(r"\b(?:class|struct)\s+([A-Z]\w*)\s*(?::[^{;]*)?\{", code):
                    decls[m.group(1)].append((p, "interface", "cpp"))
            continue
        rx = IMPL.get(lang)
        if not rx:
            continue
        for m in rx.finditer(code):
            if lang == "rust":
                trait, typ = short(m.group(1)), short(m.group(2))
                impls[trait].add((typ, p))
                continue
            cls = m.group(1)
            bases = []
            for g in m.groups()[1:]:
                if g:
                    bases += [short(re.sub(r"<.*", "", b.strip()).replace("()", "")) for b in g.split(",") if b.strip()]
            for b in bases:
                if b and b != cls:
                    impls[b].add((cls, p))

    # files where each declared name lives, by kind
    def files_of(name, lang=None, kinds=None):
        out = [d for d in decls.get(short(name), []) if (lang is None or d[2] == lang or (lang in ("js",) and d[2] == "js")) and (kinds is None or d[1] in kinds)]
        return out

    abstractions = {n for n, ds in decls.items() if any(k in ("interface", "abstract", "trait") for _, k, _ in ds)}

    bindings = []
    frameworks = set()
    notes = []

    def add(framework, iface, impl, where_file, where_line, kind="explicit", token=None):
        iface_s, impl_s = short(iface), short(impl)
        lang = files_meta[where_file]["lang"] if where_file in files_meta else None
        fq_index = {"php": idx.get("php_class", {}), "java": idx.get("java_class", {}), "csharp": idx.get("cs_type", {})}.get(lang, {})

        def exact(name):
            n = name.lstrip("\\")
            return fq_index.get(n) if ("\\" in n or "." in n) else None

        impl_files = [exact(impl)] if exact(impl) else [d[0] for d in files_of(impl_s, lang if lang != "cpp" else None, {"class", "abstract"})]
        iface_files = ([exact(iface)] if exact(iface) else [d[0] for d in files_of(iface_s, lang if lang != "cpp" else None)]) if not token else []
        if len(impl_files) > 1 and where_file in files_meta:
            imported = set(files_meta[where_file].get("imports", []))
            narrowed = [x for x in impl_files if x in imported]
            impl_files = narrowed or impl_files
        if len(impl_files) != 1:
            if impl_files:
                notes.append(f"ambiguous implementation {impl_s} for {iface_s} registered in {where_file}: {len(impl_files)} candidates")
            return
        frameworks.add(framework)
        bindings.append({
            "framework": framework, "kind": kind, "abstraction": iface.lstrip("\\") if (token or iface_s == impl_s or not iface_files) else iface_s,
            "implementation": impl.lstrip("\\") if iface_s == impl_s else impl_s,
            "abstraction_file": iface_files[0] if len(iface_files) == 1 else None,
            "implementation_file": impl_files[0], "registered_in": f"{where_file}:{where_line}" if where_file else None,
            "token": token,
        })

    def line_of(code, pos):
        return code.count("\n", 0, pos) + 1

    for p, f in files_meta.items():
        if f["test"]:
            continue
        code, lang = f.get("_code") or "", f["lang"]
        if lang == "csharp":
            for m in DOTNET_GENERIC.finditer(code):
                add(".NET DI", m.group(2), m.group(3), p, line_of(code, m.start()))
            for m in DOTNET_TYPEOF.finditer(code):
                add(".NET DI", m.group(2), m.group(3), p, line_of(code, m.start()))
            for m in AUTOFAC.finditer(code):
                add("Autofac", m.group(2), m.group(1), p, line_of(code, m.start()))
        elif lang == "js":
            for m in NEST.finditer(code):
                tok = m.group(1)
                is_string = tok[0] in "'\"" or tok.startswith("Symbol")
                add("NestJS/Angular providers", tok.strip("'\"") if is_string else tok, m.group(3), p, line_of(code, m.start()),
                    token=tok.strip("'\"") if is_string else None)
        elif lang == "php":
            for rx in (LARAVEL_BIND, LARAVEL_CLOSURE):
                for m in rx.finditer(code):
                    add("Laravel container", m.group(2), m.group(3), p, line_of(code, m.start()))
            for m in LARAVEL_GIVE.finditer(code):
                add("Laravel container", m.group(1), m.group(2), p, line_of(code, m.start()))
            for arr in LARAVEL_ARRAY.finditer(code):
                for m in LARAVEL_PAIR.finditer(arr.group(1)):
                    add("Laravel container", m.group(1), m.group(2), p, line_of(code, arr.start()))
        elif lang == "java":
            for m in SPRING_BEAN.finditer(code):
                iface = m.group(1) or m.group(2) or m.group(4)
                impl = m.group(3) or m.group(5)
                if iface and impl and short(iface) != short(impl):
                    add("Spring @Bean", iface, impl, p, line_of(code, m.start()))
        elif lang == "go":
            for m in WIRE_BIND.finditer(code):
                add("Google Wire", m.group(1), m.group(2), p, line_of(code, m.start()))

    # Laravel facades -> accessor class (direct or through a string binding)
    string_binds = {}
    for p, f in files_meta.items():
        if f["lang"] != "php":
            continue
        code = f.get("_code") or ""
        for m in LARAVEL_STRING_BIND.finditer(code):
            string_binds[m.group(1)] = (m.group(2) or m.group(3), p, line_of(code, m.start()))
    for p, f in files_meta.items():
        if f["lang"] != "php":
            continue
        code = f.get("_code") or ""
        for m in FACADE.finditer(code):
            facade, cls, key = m.group(1), m.group(2), m.group(3) or m.group(4)
            target = cls or (string_binds.get(key) or (None,))[0]
            if target:
                add("Laravel facade", facade, target, p, line_of(code, m.start()), kind="facade")

    # Symfony YAML service definitions
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("vendor", "node_modules", ".git", "var")]
        for fn in filenames:
            if fn.startswith("services") and fn.endswith((".yaml", ".yml")):
                path = os.path.join(dirpath, fn)
                rp = os.path.relpath(path, root).replace(os.sep, "/")
                try:
                    text = open(path, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for rx in (SYMFONY_ALIAS, SYMFONY_CLASS):
                    for m in rx.finditer(text):
                        iface, impl = m.group(1), m.group(2)
                        if short(iface) != short(impl):
                            impl_files = [d[0] for d in files_of(impl, "php", {"class"})]
                            iface_files = [d[0] for d in files_of(iface, "php")]
                            if len(impl_files) == 1:
                                frameworks.add("Symfony services")
                                bindings.append({"framework": "Symfony services", "kind": "explicit", "abstraction": short(iface),
                                                 "implementation": short(impl), "abstraction_file": iface_files[0] if len(iface_files) == 1 else None,
                                                 "implementation_file": impl_files[0], "registered_in": f"{rp}:{text.count(chr(10), 0, m.start()) + 1}", "token": None})

    explicit = {(b["abstraction"]) for b in bindings}

    # single implementation (autowiring)
    for name in sorted(abstractions):
        if name in explicit:
            continue
        ds = decls[name]
        langs = {d[2] for d in ds}
        if langs & {"go"}:
            continue
        cands = {(cls, fp) for cls, fp in impls.get(name, set()) if not files_meta[fp]["test"] and not MOCK_RE.search(cls) and not MOCK_RE.search(fp)}
        cands = {c for c in cands if any(k in ("class",) for _, k, _ in decls.get(c[0], [("", "class", "")]))}
        if len(cands) == 1:
            cls, fp = next(iter(cands))
            iface_files = [d[0] for d in ds if d[1] in ("interface", "abstract", "trait")]
            if iface_files and fp != iface_files[0]:
                frameworks.add("single implementation")
                bindings.append({"framework": "inferred", "kind": "single-implementation", "abstraction": name, "implementation": cls,
                                 "abstraction_file": iface_files[0], "implementation_file": fp, "registered_in": None, "token": None})

    # runtime edges: consumers of the abstraction get an edge to the implementation
    runtime = collections.defaultdict(set)
    word_cache = {}

    def words(p):
        if p not in word_cache:
            word_cache[p] = set(re.findall(r"[A-Za-z_]\w*", files_meta[p].get("_code") or ""))
        return word_cache[p]

    importers = collections.defaultdict(set)
    for p, f in files_meta.items():
        for t in f.get("imports", []):
            importers[t].add(p)
    for b in bindings:
        impl_f = b["implementation_file"]
        if b["token"]:
            tok = b["token"]
            consumers = [p for p, f in files_meta.items() if not f["test"] and tok in (f.get("_code") or "") and NEST_INJECT.search(f.get("_code") or "")]
        else:
            af = b["abstraction_file"]
            if af:
                consumers = [p for p in importers.get(af, set()) if short(b["abstraction"]) in words(p)]
            elif re.search(r"[\\.]", b["abstraction"]):
                # abstraction from a framework or library: consumers reference its qualified name
                q = b["abstraction"]
                consumers = [p for p, f in files_meta.items() if q in (f.get("_code") or "")]
            else:
                consumers = []
            if af:
                consumers += [p for p in files_meta if p not in importers.get(af, set()) and files_meta[p]["lang"] in ("csharp", "java", "php")
                              and os.path.dirname(p) == os.path.dirname(af) and b["abstraction"] in words(p)]
        reg = (b["registered_in"] or "").split(":")[0]
        for c in consumers:
            if c in (impl_f, b["abstraction_file"], reg) or files_meta[c]["test"]:
                continue
            runtime[c].add(impl_f)
    return {"bindings": bindings, "frameworks": sorted(frameworks), "runtime_edges": runtime, "notes": sorted(set(notes))[:30]}
