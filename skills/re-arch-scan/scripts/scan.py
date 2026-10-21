#!/usr/bin/env python3
"""
re-arch-scan: deterministic structural scan of a codebase.

Standard library only, so it runs anywhere Python 3.8+ is available.
Ecosystems: JavaScript/TypeScript, PHP, .NET (C#), Java (+Kotlin best effort),
C/C++, Go, Rust.

Produces:
  <out>/scan.json          full machine-readable data
  <out>/scan-summary.md    compact digest meant to be read by the model / humans

Everything here is a heuristic based on regular expressions and the file
tree. It is good at "where are the dependencies, cycles, hotspots and mixed
responsibilities", not at semantic precision. The summary states its own
limits so downstream steps do not over-trust it.
"""
import argparse
import collections
import datetime
import fnmatch
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import precise  # compiler-grade sources (optional)
except Exception:  # pragma: no cover
    precise = None
try:
    import di  # dependency-injection wiring (optional)
except Exception:  # pragma: no cover
    di = None
import insights

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LANG_BY_EXT = {
    ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
    ".ts": "js", ".tsx": "js", ".mts": "js", ".cts": "js",
    ".vue": "js", ".svelte": "js",
    ".php": "php",
    ".cs": "csharp",
    ".java": "java", ".kt": "java", ".kts": "java",
    ".c": "cpp", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
    ".h": "cpp", ".hh": "cpp", ".hpp": "cpp", ".hxx": "cpp", ".ipp": "cpp",
    ".go": "go",
    ".rs": "rust",
}

ECOSYSTEM_MARKERS = {
    "js": ["package.json", "tsconfig.json", "deno.json"],
    "php": ["composer.json"],
    "csharp": ["*.csproj", "*.sln", "*.slnx", "Directory.Build.props"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"],
    "cpp": ["CMakeLists.txt", "meson.build", "Makefile", "conanfile.txt", "conanfile.py", "vcpkg.json", "*.vcxproj"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
}

DEFAULT_EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build", "out", "target",
    "bin", "obj", ".next", ".nuxt", ".svelte-kit", ".output", "coverage", ".turbo",
    ".cache", ".idea", ".vscode", "__pycache__", ".gradle", ".mvn", "cmake-build-debug",
    "cmake-build-release", "third_party", "thirdparty", "external", "deps", ".re-arch",
    "storage", "bootstrap/cache", "public/build", "packages/.pnpm", ".venv", "venv",
    "Pods", "DerivedData", ".angular", ".expo", "generated", "__generated__",
    "public/js", "public/css", "public/vendor", "public/assets", "static/js", "wwwroot/lib", "wwwroot/dist",
}

GENERATED_FILE_PATTERNS = [
    "*.min.js", "*.bundle.js", "*.d.ts", "*.g.cs", "*.designer.cs", "*.Designer.cs",
    "*.pb.go", "*_gen.go", "*.generated.*", "*Migrations/*.cs", "*.lock",
]

TEST_PATTERNS = [
    "*.test.*", "*.spec.*", "*_test.go", "*Test.java", "*Tests.java", "*IT.java",
    "*Test.kt", "*Tests.cs", "*Test.cs", "*Test.php", "*_test.cpp", "*_test.cc",
    "test_*.cpp", "*_tests.rs", "*test_helper*", "*TestHelper*", "*testhelper*", "*.stories.*",
]
TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "e2e", "testing", "integration-tests", "testutil",
                  "testutils", "testdata", "__mocks__", "playwright", "cypress", "storybook"}

# Configuration, translations, migrations, seeders: real code but not application
# structure. Counted apart so they do not dominate LOC, modules or clusters.
SUPPORT_RE = re.compile(
    r"(^|/)(config|configs|resources/lang|lang|locales?|i18n|translations|database/migrations|migrations|"
    r"database/seeders|database/seeds|seeders|seeds|database/factories|db/migrate|alembic)/", re.I)

MAX_FILE_BYTES = 1_500_000

# Branching keywords used as a cyclomatic complexity proxy.
BRANCH_RE = re.compile(
    r"\b(if|for|foreach|while|case|catch|except|elif|elseif|when|match|select)\b|&&|\|\||\?\?|\?(?!\.)"
)

# Responsibility signals. Each value is a list of regexes; a file "has" the
# signal when any regex matches. Kept deliberately broad: the diagnose step
# reads the evidence before concluding anything.
SIGNALS = {
    "db": [
        r"\bprisma\.\w+\.(find|create|update|delete|upsert|count|aggregate)",
        r"\bmongoose\b|\.model\(\s*['\"]", r"\bknex\b|\bsequelize\b|\btypeorm\b|getRepository\(",
        r"\bdrizzle\b|\.from\(\s*['\"]\w+['\"]\s*\)\.(select|insert|update|delete)",
        r"\bsupabase\.from\(", r"\bdb\.(query|execute|select|insert|collection)\(",
        r"\b(SELECT|INSERT|UPDATE|DELETE)\s+.{0,80}\b(FROM|INTO|SET)\b",
        r"\bnew\s+PDO\b|\bDB::(table|select|insert|statement)|->createQueryBuilder\(|\bEntityManager",
        r"::where\(|::find\(|::create\(|\$this->db->|wpdb",
        r"\bDbContext\b|\bDbSet<|\.SaveChanges(Async)?\(|SqlConnection|Dapper|\.FromSqlRaw",
        r"\bJdbcTemplate\b|\bEntityManager\b|@Query\(|extends\s+(Jpa|Crud)Repository|\bSession\.(get|save)",
        r"\bgorm\.|\*sql\.DB\b|\bsqlx\.|\bpgx\.|\.QueryRow(Context)?\(|\.Exec(Context)?\(",
        r"\bdiesel::|\bsqlx::query|\bsea_orm::|rusqlite",
        r"sqlite3_|PQexec|mysql_query|QSqlQuery",
    ],
    "http": [
        r"\b(req|request)\.(body|params|query|headers)\b", r"\bres\.(status|json|send|render)\(",
        r"\bNextResponse\b|\bNextRequest\b|export\s+(async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b",
        r"\b(app|router)\.(get|post|put|patch|delete)\(\s*['\"`]", r"@(Get|Post|Put|Patch|Delete|Controller)\(",
        r"\$request->|Request\s+\$request|Route::(get|post|put|patch|delete)|#\[Route\(|@Route\(",
        r"\[(HttpGet|HttpPost|HttpPut|HttpDelete|ApiController|Route)\b|\bControllerBase\b|MapGet\(|MapPost\(",
        r"@(RestController|Controller|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping)\b",
        r"http\.ResponseWriter|\*http\.Request|gin\.Context|echo\.Context|fiber\.Ctx",
        r"\baxum::|\bactix_web::|\brocket::|HttpResponse::|#\[(get|post|put|delete)\(",
    ],
    "ui": [
        r"return\s*\(\s*<[A-Za-z]", r"</[A-Za-z][\w.]*>", r"\buseState\(|\buseEffect\(",
        r"<template>|@Component\(|\bdefineComponent\(", r"\.blade\.php|@extends\(|render\(\s*['\"]\w+",
        r"\bView\(\)|@Html\.|\bRazor\b", r"\bJFrame\b|\bQWidget\b|\bImGui::",
    ],
    "external_io": [
        r"\bfetch\(\s*['\"`]https?:", r"\baxios\.(get|post|put|delete|create)\b", r"\bnew\s+HttpClient\b|\bHttpClient\.",
        r"\bGuzzle|Http::(get|post)|curl_init\(", r"\bRestTemplate\b|\bWebClient\b|\bOkHttp",
        r"http\.(Get|Post|NewRequest)\(", r"\breqwest::", r"\bstripe\.|\bnew\s+Stripe\b|\bopenai\.|\bS3Client\b|\bnodemailer\b|\bsendgrid\b",
        r"\bfs\.(readFile|writeFile)|File\.(ReadAll|WriteAll)|file_put_contents|os\.(ReadFile|WriteFile)|std::fs::",
    ],
    "env_config": [
        r"\bprocess\.env\.", r"\bimport\.meta\.env\.", r"\bgetenv\(|\$_ENV\[|\benv\(\s*['\"]",
        r"Environment\.GetEnvironmentVariable|IConfiguration\[", r"System\.getenv\(|@Value\(\s*\"\$\{",
        r"os\.Getenv\(", r"std::env::var\(", r"\bstd::getenv\(",
    ],
    "global_state": [
        r"^\s*(let|var)\s+\w+\s*=\s*(\[|\{|new\s+Map)", r"\bglobal\s+\$\w+|\$GLOBALS\[",
        r"\bpublic\s+static\s+(?!readonly|final|class|void|async|\w+\s*\()\w[\w<>,\s]*\s+\w+\s*(=|;)",
        r"^var\s+\w+\s*=\s*(make\(|map\[|\[\])", r"\bstatic\s+mut\b|lazy_static!|OnceCell", r"^\s*static\s+(?!const)[\w:<>]+\s+\w+\s*(=|;)",
    ],
}
SIGNALS = {k: [re.compile(p, re.MULTILINE) for p in v] for k, v in SIGNALS.items()}

DEFAULT_SECRET_RE = re.compile(
    r"(?i)(?:env\.|getenv\(|env\(|\[)['\"]?\w*(secret|token|key|password|passwd|jwt)\w*['\"]?\]?\)?\s*(?:\|\||\?\?|\bor\b|,)\s*['\"][^'\"]{3,}['\"]")
PROD_RISK_PATTERNS = [
    ("management endpoints fully exposed", re.compile(r"management\.endpoints\.web\.exposure\.include\s*[=:]\s*['\"]?\*")),
    ("SQL init / seed data always run", re.compile(r"spring\.sql\.init\.mode\s*[=:]\s*always")),
    ("debug mode on", re.compile(r"(?m)^\s*(APP_DEBUG\s*=\s*true|DEBUG\s*=\s*True)\b")),
    ("CORS open to any origin", re.compile(r"(Access-Control-Allow-Origin['\"]?\s*[:,]\s*['\"]\*|origin:\s*['\"]\*['\"]|AllowAnyOrigin\(\))")),
]
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|password|passwd|token|private[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-\/+=]{12,}['\"]"
    r"|sk_live_[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC )?PRIVATE KEY-----"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def rel(path, root):
    return os.path.relpath(path, root).replace(os.sep, "/")


def matches_any(path, patterns):
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(path, p) for p in patterns)


def is_test_file(path):
    parts = path.lower().split("/")
    if any(p in TEST_DIR_NAMES for p in parts[:-1]):
        return True
    return matches_any(path, TEST_PATTERNS)


def read_text(path):
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def strip_comments(text, lang):
    """Rough comment removal so commented-out imports do not count."""
    if lang in ("js", "php", "csharp", "java", "cpp", "go", "rust"):
        text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.DOTALL)
        text = re.sub(r"(?m)(^|[^:\"'])//.*$", r"\1", text)
    if lang == "php":
        text = re.sub(r"(?m)^\s*#(?!\[).*$", "", text)
    return text


def count_loc(text):
    return sum(1 for line in text.splitlines() if line.strip())


def git(root, *args):
    try:
        out = subprocess.run(
            ["git", "-C", root] + list(args), capture_output=True, text=True, timeout=180
        )
        if out.returncode != 0:
            return None
        return out.stdout
    except (OSError, subprocess.TimeoutExpired):
        return None


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def detect_ecosystems(root):
    found = collections.Counter()
    manifests = collections.defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDED_DIRS and not d.startswith(".")]
        depth = rel(dirpath, root).count("/")
        if depth > 6:
            dirnames[:] = []
        for eco, markers in ECOSYSTEM_MARKERS.items():
            for m in markers:
                for f in filenames:
                    if fnmatch.fnmatch(f, m):
                        found[eco] += 1
                        manifests[eco].append(rel(os.path.join(dirpath, f), root))
    return found, manifests


def collect_files(root, extra_excludes):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        reldir = rel(dirpath, root)
        keep = []
        for d in dirnames:
            sub = (reldir + "/" + d) if reldir != "." else d
            if d in DEFAULT_EXCLUDED_DIRS or d.startswith(".") or sub in DEFAULT_EXCLUDED_DIRS:
                continue
            if any(fnmatch.fnmatch(sub, p) for p in extra_excludes):
                continue
            keep.append(d)
        dirnames[:] = keep
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext not in LANG_BY_EXT:
                continue
            path = os.path.join(dirpath, f)
            r = rel(path, root)
            if matches_any(r, GENERATED_FILE_PATTERNS) or any(fnmatch.fnmatch(r, p) for p in extra_excludes):
                continue
            files.append((r, LANG_BY_EXT[ext], path))
    return files


# ---------------------------------------------------------------------------
# Import extraction and resolution, per ecosystem
# ---------------------------------------------------------------------------

JS_IMPORT_RES = [
    re.compile(r"""(?:^|[\s;])import\s+(?:type\s+)?(?:[\w*{}\s,$]+\s+from\s+)?['"]([^'"]+)['"]""", re.M),
    re.compile(r"""(?:^|[\s;])export\s+(?:type\s+)?(?:\*|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]""", re.M),
    re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)"""),
]
JS_EXTS = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte"]


def load_js_aliases(root):
    """Read tsconfig/jsconfig 'paths' (first level, with baseUrl)."""
    aliases = []
    for name in ("tsconfig.json", "jsconfig.json", "tsconfig.base.json", "tsconfig.app.json"):
        p = os.path.join(root, name)
        text = read_text(p)
        if not text:
            continue
        text = re.sub(r"//.*", "", text)
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r",(\s*[}\]])", r"\1", text)
        try:
            cfg = json.loads(text)
        except ValueError:
            continue
        co = cfg.get("compilerOptions", {})
        base = co.get("baseUrl", ".")
        for key, targets in (co.get("paths") or {}).items():
            if not targets:
                continue
            prefix = key.rstrip("*")
            target = os.path.normpath(os.path.join(base, targets[0].rstrip("*"))).replace(os.sep, "/")
            if target == ".":
                target = ""
            aliases.append((prefix, target))
    # Common conventions when no tsconfig paths are declared.
    if not any(a[0] in ("@/", "~/") for a in aliases):
        if os.path.isdir(os.path.join(root, "src")):
            aliases += [("@/", "src/"), ("~/", "src/")]
        else:
            aliases += [("@/", ""), ("~/", "")]
    return aliases


WORKSPACES = {}  # npm package name -> (dir, entry file or None)


def load_js_workspaces(root):
    """Map monorepo package names (package.json "name") to their folders so
    '@acme/lib/x' resolves to packages/lib/... instead of looking external."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDED_DIRS and not d.startswith(".")]
        if rel(dirpath, root).count("/") > 5:
            dirnames[:] = []
        if "package.json" not in filenames or dirpath == root:
            continue
        try:
            pkg = json.loads(read_text(os.path.join(dirpath, "package.json")) or "{}")
        except ValueError:
            continue
        name = pkg.get("name")
        if not name or not isinstance(name, str):
            continue
        entry = None
        exp = pkg.get("exports")
        if isinstance(exp, str):
            entry = exp
        elif isinstance(exp, dict):
            dot = exp.get(".")
            if isinstance(dot, str):
                entry = dot
            elif isinstance(dot, dict):
                entry = dot.get("import") or dot.get("default") or dot.get("types") if all(isinstance(v, str) for v in dot.values()) else None
        entry = entry or pkg.get("module") or pkg.get("main") or pkg.get("types")
        d = rel(dirpath, root)
        WORKSPACES[name] = (d, os.path.normpath(os.path.join(d, entry)).replace(os.sep, "/") if isinstance(entry, str) else None)


def _try_js(base, file_set):
    if base in file_set:
        return base
    stem = re.sub(r"\.(js|jsx|mjs|cjs)$", "", base)
    for ext in JS_EXTS:
        if stem + ext in file_set:
            return stem + ext
    for ext in JS_EXTS:
        if base + "/index" + ext in file_set:
            return base + "/index" + ext
    return None


def resolve_js(spec, from_file, file_set, aliases):
    if WORKSPACES and not spec.startswith("."):
        for name in sorted(WORKSPACES, key=len, reverse=True):
            if spec == name or spec.startswith(name + "/"):
                d, entry = WORKSPACES[name]
                rest = spec[len(name):].lstrip("/")
                cands = [d + "/" + rest, d + "/src/" + rest] if rest else ([entry] if entry else []) + [d + "/index", d + "/src/index"]
                for c in cands:
                    hit = _try_js(c.lstrip("/"), file_set) if c else None
                    if hit:
                        return hit
                    # dist/ entry pointing at built output: map back to src
                    if c and "/dist/" in c:
                        hit = _try_js(c.replace("/dist/", "/src/").lstrip("/"), file_set)
                        if hit:
                            return hit
                break
    candidates = []
    if spec.startswith("."):
        base = os.path.normpath(os.path.join(os.path.dirname(from_file), spec)).replace(os.sep, "/")
        candidates.append(base)
    else:
        for prefix, target in aliases:
            if spec.startswith(prefix):
                candidates.append((target.rstrip("/") + "/" + spec[len(prefix):]).lstrip("/"))
    for base in candidates:
        if base in file_set:
            return base
        stem = re.sub(r"\.(js|jsx|mjs|cjs)$", "", base)
        for ext in JS_EXTS:
            if stem + ext in file_set:
                return stem + ext
        for ext in JS_EXTS:
            if base + "/index" + ext in file_set:
                return base + "/index" + ext
    return None


def js_external_name(spec):
    if spec.startswith(".") or spec.startswith("@/") or spec.startswith("~/"):
        return None
    if any(spec == n or spec.startswith(n + "/") for n in WORKSPACES):
        return None  # internal package, unresolved file
    if spec.startswith("node:"):
        return spec
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") else parts[0]


PHP_NS_RE = re.compile(r"^\s*namespace\s+([\w\\]+)\s*[;{]", re.M)
PHP_CLASS_RE = re.compile(r"^\s*(?:final\s+|abstract\s+|readonly\s+)*(?:class|interface|trait|enum)\s+(\w+)", re.M)
PHP_USE_RE = re.compile(r"^\s*use\s+(?!function\b|const\b)([\w\\]+)(?:\s+as\s+\w+)?\s*;", re.M)
PHP_USE_GROUP_RE = re.compile(r"^\s*use\s+([\w\\]+)\\\{([^}]+)\}\s*;", re.M)
PHP_REQ_RE = re.compile(r"\b(?:require|include)(?:_once)?\s*\(?\s*(?:__DIR__\s*\.\s*)?['\"]([^'\"]+)['\"]")

CS_NS_RE = re.compile(r"^\s*namespace\s+([\w.]+)", re.M)
CS_USING_RE = re.compile(r"^\s*(?:global\s+)?using\s+(?:static\s+)?(?!\w+\s*=)([\w.]+)\s*;", re.M)
CS_TYPE_RE = re.compile(r"\b(?:class|interface|record|struct|enum)\s+(\w+)")

JAVA_PKG_RE = re.compile(r"^\s*package\s+([\w.]+)", re.M)
JAVA_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+?)(\.\*)?\s*;?\s*$", re.M)

CPP_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]', re.M)

GO_IMPORT_BLOCK_RE = re.compile(r"^import\s*\((.*?)\)", re.M | re.S)
GO_IMPORT_LINE_RE = re.compile(r'^import\s+(?:[\w.]+\s+)?"([^"]+)"', re.M)
GO_SPEC_RE = re.compile(r'(?:[\w.]+\s+)?"([^"]+)"')

RUST_USE_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?use\s+([^;]+);", re.M)
RUST_MOD_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+(\w+)\s*;", re.M)


def build_indexes(files_meta, root):
    """Per-language symbol indexes used for resolution."""
    idx = {
        "php_class": {}, "cs_ns": collections.defaultdict(set), "cs_type": {},
        "java_class": {}, "java_pkg": collections.defaultdict(set),
        "basename": collections.defaultdict(list), "go_module": None, "go_mods": [],
        "rust_crates": [],
    }
    for f in files_meta.values():
        idx["basename"][f["path"].rsplit("/", 1)[-1]].append(f["path"])
        text = f.get("_text") or ""
        lang = f["lang"]
        if lang == "php":
            ns = PHP_NS_RE.search(text)
            ns = ns.group(1) if ns else ""
            for cls in PHP_CLASS_RE.findall(text):
                idx["php_class"][(ns + "\\" + cls).lstrip("\\")] = f["path"]
        elif lang == "csharp":
            for ns in CS_NS_RE.findall(text):
                idx["cs_ns"][ns].add(f["path"])
                for t in CS_TYPE_RE.findall(text):
                    idx["cs_type"][ns + "." + t] = f["path"]
        elif lang == "java":
            pkg = JAVA_PKG_RE.search(text)
            pkg = pkg.group(1) if pkg else ""
            cls = os.path.splitext(f["path"].rsplit("/", 1)[-1])[0]
            idx["java_class"][(pkg + "." + cls).lstrip(".")] = f["path"]
            idx["java_pkg"][pkg].add(f["path"])
    # go.mod files (possibly several in a monorepo)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDED_DIRS and not d.startswith(".")]
        if "go.mod" in filenames:
            text = read_text(os.path.join(dirpath, "go.mod")) or ""
            m = re.search(r"^module\s+(\S+)", text, re.M)
            if m:
                idx["go_mods"].append((m.group(1), rel(dirpath, root)))
        if "Cargo.toml" in filenames:
            idx["rust_crates"].append(rel(dirpath, root))
    idx["go_mods"].sort(key=lambda x: -len(x[0]))
    return idx


def extract_imports(f, file_set, idx, aliases, root, go_pkg_files):
    """Return (internal_targets:set, externals:set)."""
    text = f.get("_code") or ""
    lang = f["lang"]
    internal, external = set(), set()
    path = f["path"]

    if lang == "js":
        for rx in JS_IMPORT_RES:
            for spec in rx.findall(text):
                tgt = resolve_js(spec, path, file_set, aliases)
                if tgt:
                    internal.add(tgt)
                else:
                    ext = js_external_name(spec)
                    if ext:
                        external.add(ext)

    elif lang == "php":
        names = list(PHP_USE_RE.findall(text))
        for prefix, group in PHP_USE_GROUP_RE.findall(text):
            for item in group.split(","):
                item = item.strip().split(" as ")[0].strip()
                if item:
                    names.append(prefix + "\\" + item)
        for n in names:
            tgt = idx["php_class"].get(n.lstrip("\\"))
            if tgt:
                internal.add(tgt)
            else:
                external.add(n.split("\\")[0])
        # same-namespace classes need no `use`; inline qualified names (\\App\\X::find) neither
        ns_m = PHP_NS_RE.search(text)
        own_ns = ns_m.group(1) if ns_m else ""
        imported_short = {n.rsplit("\\", 1)[-1] for n in names}
        for full, tgt in idx["php_class"].items():
            if tgt == path:
                continue
            short = full.rsplit("\\", 1)[-1]
            if full.rsplit("\\", 1)[0] == own_ns and short not in imported_short and (re.search(r"\bnew\s+" + re.escape(short) + r"\b", text) or re.search(r"(?<![\\$\w>])" + re.escape(short) + r"\b(?!\s*\()", text)):
                internal.add(tgt)
        for q in re.findall(r"\\?((?:[A-Z]\w*\\)+[A-Z]\w*)(?=\s*(?:::|\(|\s+\$|\)|,))", text):
            tgt = idx["php_class"].get(q.lstrip("\\"))
            if tgt and tgt != path:
                internal.add(tgt)
        for spec in PHP_REQ_RE.findall(text):
            base = os.path.normpath(os.path.join(os.path.dirname(path), spec.lstrip("/"))).replace(os.sep, "/")
            if base in file_set:
                internal.add(base)

    elif lang == "csharp":
        own_ns = set(CS_NS_RE.findall(text))
        for ns in CS_USING_RE.findall(text):
            if ns in idx["cs_ns"]:
                # Namespace-level dependency: link to files of that namespace
                # that declare a type actually referenced in this file.
                hits = [
                    p for (full, p) in idx["cs_type"].items()
                    if full.rsplit(".", 1)[0] == ns and re.search(r"\b" + re.escape(full.rsplit(".", 1)[1]) + r"\b", text)
                ]
                internal.update(hits or list(idx["cs_ns"][ns])[:3])
            elif ns in idx["cs_type"]:
                internal.add(idx["cs_type"][ns])
            else:
                external.add(ns.split(".")[0])
        # same-namespace references (no using needed in C#)
        for ns in own_ns:
            for full, p in idx["cs_type"].items():
                if p != path and full.rsplit(".", 1)[0] == ns and re.search(r"\b" + re.escape(full.rsplit(".", 1)[1]) + r"\b", text):
                    internal.add(p)

    elif lang == "java":
        pkg = JAVA_PKG_RE.search(text)
        pkg = pkg.group(1) if pkg else ""
        for name, star in JAVA_IMPORT_RE.findall(text):
            if star:
                if name in idx["java_pkg"]:
                    internal.update(idx["java_pkg"][name])
                else:
                    external.add(".".join(name.split(".")[:3]))
                continue
            tgt = idx["java_class"].get(name)
            if not tgt:
                # static import of a member: drop the last segment
                tgt = idx["java_class"].get(name.rsplit(".", 1)[0])
            if tgt:
                internal.add(tgt)
            else:
                external.add(".".join(name.split(".")[:3]))
        for p in idx["java_pkg"].get(pkg, ()):  # same package, implicit
            if p != path:
                cls = os.path.splitext(p.rsplit("/", 1)[-1])[0]
                if re.search(r"\b" + re.escape(cls) + r"\b", text):
                    internal.add(p)

    elif lang == "cpp":
        for kind, spec in CPP_INCLUDE_RE.findall(text):
            cand = os.path.normpath(os.path.join(os.path.dirname(path), spec)).replace(os.sep, "/")
            if cand in file_set:
                internal.add(cand)
                continue
            matches = [p for p in idx["basename"].get(spec.rsplit("/", 1)[-1], []) if p.endswith(spec)]
            if matches:
                internal.add(sorted(matches, key=len)[0])
            elif kind == "<":
                external.add(spec.split("/")[0])

    elif lang == "go":
        specs = GO_IMPORT_LINE_RE.findall(text)
        for block in GO_IMPORT_BLOCK_RE.findall(text):
            specs += GO_SPEC_RE.findall(block)
        for spec in specs:
            hit = False
            for mod, moddir in idx["go_mods"]:
                if spec == mod or spec.startswith(mod + "/"):
                    sub = spec[len(mod):].lstrip("/")
                    d = "/".join(x for x in (moddir if moddir != "." else "", sub) if x)
                    targets = go_pkg_files.get(d, [])
                    internal.update(targets)
                    hit = True
                    break
            if not hit:
                external.add(spec if "." not in spec.split("/")[0] else "/".join(spec.split("/")[:3]))

    elif lang == "rust":
        crate_root = None
        for c in sorted(idx["rust_crates"], key=len, reverse=True):
            if c == "." or path.startswith(c + "/"):
                crate_root = "" if c == "." else c + "/"
                break
        src = (crate_root or "") + "src/"
        here_dir = os.path.dirname(path)
        stem = os.path.splitext(path.rsplit("/", 1)[-1])[0]
        for m in RUST_MOD_RE.findall(text):
            mod_dir = here_dir if stem in ("mod", "lib", "main") else here_dir + "/" + stem
            for cand in (mod_dir + "/" + m + ".rs", mod_dir + "/" + m + "/mod.rs"):
                cand = cand.lstrip("/")
                if cand in file_set:
                    internal.add(cand)
        for use in RUST_USE_RE.findall(text):
            use = re.sub(r"\s+", "", use)
            head = use.split("::")[0]
            if head in ("crate", "self", "super"):
                segs = [s for s in re.split(r"::|\{|\}|,", use)[1:] if s and s != "*" and s != "self"]
                # try the longest module path that exists
                for n in range(len(segs), 0, -1):
                    base = src + "/".join(segs[:n])
                    hit = next((c for c in (base + ".rs", base + "/mod.rs") if c in file_set), None)
                    if hit:
                        internal.add(hit)
                        break
            elif head not in ("std", "core", "alloc"):
                external.add(head)

    internal.discard(path)
    return internal, external


# ---------------------------------------------------------------------------
# Graph algorithms
# ---------------------------------------------------------------------------


def tarjan_scc(nodes, edges):
    """Iterative Tarjan. edges: dict node -> iterable of nodes."""
    index, low, on_stack, stack, sccs = {}, {}, set(), [], []
    counter = [0]
    for start in nodes:
        if start in index:
            continue
        work = [(start, iter(edges.get(start, ())))]
        index[start] = low[start] = counter[0]
        counter[0] += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(edges.get(nxt, ()))))
                    advanced = True
                    break
                elif nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1:
                    sccs.append(sorted(comp))
    return sccs


def shortest_cycle_in(comp, edges):
    """A representative cycle inside an SCC, for human-readable evidence."""
    comp_set = set(comp)
    best = None
    for start in comp[:30]:
        prev = {start: None}
        queue = collections.deque([start])
        found = None
        while queue and not found:
            n = queue.popleft()
            for m in edges.get(n, ()):
                if m not in comp_set:
                    continue
                if m == start:
                    found = n
                    break
                if m not in prev:
                    prev[m] = n
                    queue.append(m)
        if found is not None:
            path = [found]
            while prev[path[-1]] is not None:
                path.append(prev[path[-1]])
            path = list(reversed(path)) + [start]
            if best is None or len(path) < len(best):
                best = path
    return best


# ---------------------------------------------------------------------------
# Modules (aggregation of files into units)
# ---------------------------------------------------------------------------

SOURCE_ROOTS = ["src/main/java", "src/main/kotlin", "src", "app", "lib", "internal", "pkg", "cmd", "packages", "apps", "modules", "source", "Sources"]


def adaptive_modules(files_meta, max_share=0.35, max_depth=5, unit_of=None):
    """Start at depth 1 and split any module holding more than `max_share`
    of production LOC into its subdirectories, so a framework folder like
    src/app does not swallow the whole application. When build units exist
    (projects, crates, Maven/Gradle modules, workspace packages), they are the
    first level: a module is a unit, split further only if it is too big."""
    prod = {p: f for p, f in files_meta.items() if not f["test"]}
    total = sum(f["loc"] for f in prod.values()) or 1
    if unit_of:
        assign = {p: unit_of.get(p) or module_of(p, 1) for p in files_meta}
    else:
        assign = {p: module_of(p, 1) for p in files_meta}
    depth_of = collections.defaultdict(lambda: 1)
    changed = True
    while changed:
        changed = False
        loc = collections.Counter()
        for p, f in prod.items():
            loc[assign[p]] += f["loc"]
        for mod, l in loc.items():
            d = depth_of[mod]
            if l / total <= max_share or d >= max_depth:
                continue
            members = [p for p in files_meta if assign[p] == mod]
            if unit_of and unit_of.get(members[0]) == mod:
                # split a unit by its own subfolders, below the unit's common source dir
                common = os.path.commonpath([os.path.dirname(x) or "." for x in members])
                sub = {}
                for p in members:
                    relp = os.path.relpath(p, common) if common not in ("", ".") else p
                    parts = relp.replace(os.sep, "/").split("/")[:-1]
                    sub[p] = mod + ("/" + "/".join(parts[:d]) if parts else "")
            else:
                nd = d + 1
                sub = {p: module_of(p, nd) for p in members}
                # single-branch levels (org/acme/app/...): keep descending until the tree branches
                while len(set(sub.values())) < 2 and nd < max_depth + 4:
                    nd += 1
                    sub = {p: module_of(p, nd) for p in members}
                d = nd - 1
            for p, m in sub.items():
                assign[p] = m
                depth_of[m] = d + 1
            changed = True
    return assign


def module_of(path, depth):
    """Module = first `depth` directories below the detected source root."""
    parts = path.split("/")[:-1]
    if not parts:
        return "(root)"
    joined = "/".join(parts)
    for sr in SOURCE_ROOTS:
        if joined == sr or joined.startswith(sr + "/"):
            sr_parts = sr.split("/")
            rest = parts[len(sr_parts):]
            # Java: skip reverse-domain package prefix (com/acme/app/...)
            skipped = []
            if sr.startswith("src/main") and len(rest) > 3:
                skipped, rest = rest[:2], rest[2:]
            if not rest:
                return sr
            return "/".join(sr_parts + skipped + rest[:depth])
    return "/".join(parts[:depth])


# ---------------------------------------------------------------------------
# Data model extraction (entities) for the domains step
# ---------------------------------------------------------------------------

ENTITY_PATTERNS = [
    ("prisma", re.compile(r"^model\s+(\w+)\s*\{", re.M)),
    ("sql", re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(?:\w+[`\"\]]?\.)?[`\"\[]?(\w+)", re.I)),
    ("mongoose", re.compile(r"mongoose\.model\(\s*['\"](\w+)['\"]|model\(\s*['\"](\w+)['\"]\s*,\s*\w+Schema")),
    ("typeorm/jpa", re.compile(r"@Entity\b[^\n]*\n(?:\s*@[^\n]*\n)*\s*(?:export\s+)?(?:public\s+)?(?:abstract\s+)?class\s+(\w+)")),
    ("efcore", re.compile(r"\bDbSet<(\w+)>")),
    ("eloquent", re.compile(r"class\s+(\w+)\s+extends\s+(?:Model|Authenticatable|Pivot)\b")),
    ("doctrine", re.compile(r"#\[ORM\\Entity[^\]]*\]\s*(?:#\[[^\]]*\]\s*)*(?:final\s+)?class\s+(\w+)")),
    ("gorm", re.compile(r"type\s+(\w+)\s+struct\s*\{[^}]*gorm\.Model", re.S)),
    ("diesel", re.compile(r"table!\s*\{\s*(\w+)")),
    ("drizzle", re.compile(r"(?:pgTable|mysqlTable|sqliteTable)\(\s*['\"](\w+)['\"]")),
    ("sequelize", re.compile(r"sequelize\.define\(\s*['\"](\w+)['\"]|class\s+(\w+)\s+extends\s+Model\s*\{")),
]
ENTITY_LANGS = {"sequelize": {"js"}, "mongoose": {"js"}, "typeorm/jpa": {"js", "java"}, "efcore": {"csharp"},
                "eloquent": {"php"}, "doctrine": {"php"}, "gorm": {"go"}, "diesel": {"rust"}, "drizzle": {"js"}}
SCHEMA_FILES = ("schema.prisma",)


def extract_entities(files_meta, root):
    entities = collections.OrderedDict()
    extra = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDED_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn in SCHEMA_FILES or fn.endswith(".sql"):
                extra.append(rel(os.path.join(dirpath, fn), root))
    sources = [(p, read_text(os.path.join(root, p)) or "", None) for p in extra]
    sources += [(f["path"], f.get("_text") or "", f["lang"]) for f in files_meta.values()]
    blocks = collections.defaultdict(list)  # entity key -> definition snippets
    for path, text, lang in sources:
        hits = []
        for kind, rx in ENTITY_PATTERNS:
            if lang and kind in ENTITY_LANGS and lang not in ENTITY_LANGS[kind]:
                continue
            if lang and kind == "prisma":
                continue
            for m in rx.finditer(text):
                name = next((g for g in m.groups() if g), None)
                if not name or name.lower() in ("migrations", "schema_migrations"):
                    continue
                hits.append((m.start(), kind, name))
        hits.sort()
        for i, (pos, kind, name) in enumerate(hits):
            key = name.lower()
            if kind == "sql" and key.endswith("s") and not key.endswith("ss"):
                key = key[:-1]
            e = entities.setdefault(key, {"name": name, "kinds": set(), "files": set()})
            e["kinds"].add(kind)
            e["files"].add(path)
            # definition block: up to the next entity in the same file, capped
            end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
            if kind == "efcore":  # DbSet<X> lines carry no structure
                continue
            blocks[key].append(text[pos:min(end, pos + 4000)])
    names = {k: v["name"] for k, v in entities.items()}
    ident_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

    def forms(n):
        lc = n[0].lower() + n[1:]
        return {n, n + "s", n + "es", lc, lc + "s", lc + "es"}

    entity_forms = {k: forms(n) for k, n in names.items()}
    for k, e in entities.items():
        refs = set()
        for b in blocks.get(k, []):
            toks = set(ident_re.findall(b[len(e["name"]) + 1:]))
            for k2, fs in entity_forms.items():
                if k2 != k and (fs & toks):
                    refs.add(names[k2])
        e["references"] = sorted(refs)[:15]
    file_tokens = {p: set(ident_re.findall(f["_code"])) for p, f in files_meta.items() if f.get("_code")}
    for k, e in entities.items():
        fs = entity_forms[k]
        e["used_in"] = sorted(p for p, toks in file_tokens.items() if fs & toks)[:200]
        e["kinds"] = sorted(e["kinds"])
        e["files"] = sorted(e["files"])
    return list(entities.values())


# ---------------------------------------------------------------------------
# Git history
# ---------------------------------------------------------------------------


FIX_RE = re.compile(r"(?i)^(fix|hotfix|bugfix|revert)\b|\b(fix(es|ed)?|bug|hotfix|regression|broken|corrige[rsz]?|correctif)\b")


TICKET_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b|\(#(\d{1,6})\)|\b(?:fixes|closes|refs?|resolves)\s+#(\d{1,6})", re.I)


def git_history(root, file_set, since, max_commits, bulk_threshold):
    """Commits with per-file line counts (numstat). Author ids use %aE so .mailmap is honoured."""
    if git(root, "rev-parse", "--is-inside-work-tree") is None:
        return None
    top = (git(root, "rev-parse", "--show-toplevel") or "").strip()
    prefix = rel(os.path.abspath(root), top) if top else "."
    prefix = "" if prefix == "." else prefix + "/"
    fmt = "--format=@@@%H|%aE|%at|%s"
    log = git(root, "log", "--no-merges", "--no-renames", "--since=" + since, "-n", str(max_commits), "--numstat", fmt)
    if log is None:
        return None
    window_note = None
    if not log.strip():
        # inactive repo: the window is empty but history exists, take the last commits instead
        log = git(root, "log", "--no-merges", "--no-renames", "-n", str(min(max_commits, 500)), "--numstat", fmt)
        if not log or not log.strip():
            return None
        window_note = f"no commit since {since}; used the last {min(max_commits, 500)} commits instead (repository inactive since then)"
        since = "last commits (fallback)"
    commits = []
    current = None
    for line in log.splitlines():
        if line.startswith("@@@"):
            h, author, ts, subject = (line[3:].split("|", 3) + [""])[:4]
            t = TICKET_RE.search(subject)
            ticket = (t.group(1) or t.group(2) or t.group(3)).upper() if t else None
            current = {"author": author.lower(), "ts": int(ts), "files": [], "lines": {}, "fix": bool(FIX_RE.search(subject)), "ticket": ticket}
            commits.append(current)
        elif line.strip() and current is not None:
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            added, deleted, p = parts
            if prefix and p.startswith(prefix):
                p = p[len(prefix):]
            if p in file_set:
                current["files"].append(p)
                n = (int(added) if added.isdigit() else 0) + (int(deleted) if deleted.isdigit() else 0)
                current["lines"][p] = current["lines"].get(p, 0) + max(n, 1)
    churn = collections.Counter()
    fix_churn = collections.Counter()
    authors = collections.defaultdict(set)
    lines_by_author = collections.defaultdict(collections.Counter)
    last_ts_by_author = {}
    last_touch = {}
    pair = collections.Counter()
    bulk = 0
    for c in commits:
        last_ts_by_author[c["author"]] = max(last_ts_by_author.get(c["author"], 0), c["ts"])
        fs = sorted(set(c["files"]))
        for p in fs:
            churn[p] += 1
            if c["fix"]:
                fix_churn[p] += 1
            authors[p].add(c["author"])
            lines_by_author[p][c["author"]] += c["lines"].get(p, 1)
            last_touch[p] = max(last_touch.get(p, 0), c["ts"])
    # change sets: commits sharing a ticket id are one logical change (agents often
    # split a change into many small commits); other commits stand alone
    sets = collections.defaultdict(set)
    for i, c in enumerate(commits):
        sets[("T", c["ticket"]) if c["ticket"] else ("C", i)].update(c["files"])
    ticket_sets = sum(1 for k in sets if k[0] == "T")
    for key, fs in sets.items():
        fs = sorted(fs)
        if len(fs) > bulk_threshold:
            bulk += 1
            continue  # formatting / mass rename commits pollute co-change
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                pair[(fs[i], fs[j])] += 1
    cochange = []
    for (a, b), n in pair.items():
        if n < 2:
            continue
        support = n / max(1, min(churn[a], churn[b]))
        cochange.append({"a": a, "b": b, "count": n, "strength": round(min(support, 1.0), 2)})
    cochange.sort(key=lambda x: (-x["count"], -x["strength"]))
    first = min((c["ts"] for c in commits), default=None)
    return {
        "commits_analyzed": len(commits),
        "window_note": window_note,
        "bulk_commits_ignored_for_cochange": bulk,
        "ticket_change_sets": ticket_sets,
        "since": since,
        "first_commit_ts": first,
        "contributors": len({c["author"] for c in commits}),
        "fix_commits": sum(1 for c in commits if c["fix"]),
        "fix_share": round(sum(1 for c in commits if c["fix"]) / len(commits), 2) if commits else None,
        "top_fixed_files": [{"path": p, "fix_commits": n, "commits": churn[p]} for p, n in fix_churn.most_common(15)],
        "churn": dict(churn),
        "authors": {p: len(a) for p, a in authors.items()},
        "last_touch": last_touch,
        "cochange": cochange[:2000],
        "_raw": {"lines_by_author": {p: dict(v) for p, v in lines_by_author.items()}, "last_ts_by_author": last_ts_by_author,
                 "now": max((c["ts"] for c in commits), default=0)},
    }


# ---------------------------------------------------------------------------
# Duplication (cheap): identical normalized blocks of N lines across files
# ---------------------------------------------------------------------------


IMPORT_LINE_RE = re.compile(r"^(import|export \* from|export \{[^}]*\} from|use |using |#include|#import|require|package |from \S+ import|const \w+ = require|extern crate|mod \w+;|namespace )")


def find_duplicates(files_meta, window=4, max_report=60):
    seen = collections.defaultdict(list)
    for p, f in files_meta.items():
        if f["test"]:
            continue
        lines = [re.sub(r"\s+", " ", l.strip()) for l in (f.get("_code") or "").splitlines()]
        lines = [(i, l) for i, l in enumerate(lines, 1) if len(l) > 3 and l not in ("{", "}", "});", ");", "end", "]")
                 and not IMPORT_LINE_RE.match(l)]
        for k in range(0, max(0, len(lines) - window + 1)):
            chunk = "\n".join(l for _, l in lines[k:k + window])
            if len(chunk) < 100:
                continue
            seen[hash(chunk)].append((p, lines[k][0]))
    groups = []
    for occ in seen.values():
        files = {}
        for p, line in occ:
            files.setdefault(p, line)
        if len(files) > 1:
            groups.append(sorted(files.items()))
    # merge overlapping windows: keep one entry per file pair set
    uniq = {}
    for g in groups:
        key = tuple(p for p, _ in g)
        uniq.setdefault(key, g)
    pairs = collections.Counter()
    for key in uniq:
        pairs[key] += 1
    out = []
    for key, n in pairs.most_common(max_report):
        out.append({"files": [{"path": p, "line": l} for p, l in uniq[key]], "blocks": n})
    # distinctive single statements copied across files (a business formula re-typed in two places):
    # long enough, with arithmetic or comparison, not an import, not a call-only line
    line_seen = collections.defaultdict(dict)
    for p, f in files_meta.items():
        if f["test"]:
            continue
        for i, raw in enumerate((f.get("_code") or "").splitlines(), 1):
            l = re.sub(r"\s+", " ", raw.strip())
            if len(l) < 30 or IMPORT_LINE_RE.match(l) or not re.search(r"[*/+\-<>]=?\s*[\w(]", l) or not re.search(r"\d|[*/]", l):
                continue
            line_seen[l].setdefault(p, i)
    singles = [{"files": [{"path": p, "line": ln} for p, ln in sorted(v.items())], "blocks": 1, "statement": k[:120]}
               for k, v in line_seen.items() if len(v) > 1]
    singles.sort(key=lambda x: -len(x["statement"]))
    covered = {tuple(sorted(x["path"] for x in d["files"])) for d in out}
    out += [d for d in singles if tuple(sorted(x["path"] for x in d["files"])) not in covered][:30]
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description="Structural scan for architecture audits")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out", default=None, help="output dir (default <root>/.re-arch)")
    ap.add_argument("--module-depth", default="auto", help="'auto' (split big modules) or an integer: directories below source root that define a module")
    ap.add_argument("--exclude", action="append", default=[], help="glob to exclude (repeatable)")
    ap.add_argument("--since", default="18 months ago", help="git history window")
    ap.add_argument("--max-commits", type=int, default=5000)
    ap.add_argument("--bulk-threshold", type=int, default=40, help="commits touching more files are ignored for co-change")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--include-tests-in-graph", action="store_true")
    ap.add_argument("--precise", choices=["auto", "off"], default="auto",
                    help="auto: use compiler-grade sources when available (compile_commands.json, go list, cargo metadata, jdeps, TypeScript resolver, PHP tokenizer, .csproj graph); off: regex only")
    ap.add_argument("--allow-build", action="store_true",
                    help="allow steps that run the project's build scripts (CMake configure, Maven/Gradle compile). Ask the repository owner first.")
    ap.add_argument("--fetch-tools", action="store_true",
                    help="allow downloading analysis tools from the package registry (typescript for the JS/TS resolver). Never runs repository code.")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    out = os.path.abspath(args.out or os.path.join(root, ".re-arch"))
    os.makedirs(out, exist_ok=True)

    eco_counts, manifests = detect_ecosystems(root)
    files = collect_files(root, args.exclude)
    if not files:
        print("No source files found for supported ecosystems.", file=sys.stderr)
        sys.exit(2)

    files_meta = {}
    support = collections.Counter()
    support_loc = collections.Counter()
    for r, lang, full in files:
        m = SUPPORT_RE.search(r)
        if m and not is_test_file(r):
            text = read_text(full) or ""
            support[m.group(2).lower()] += 1
            support_loc[m.group(2).lower()] += count_loc(text)
            continue
        text = read_text(full)
        if text is None:
            continue
        code = strip_comments(text, lang)
        files_meta[r] = {
            "path": r, "lang": lang, "loc": count_loc(text), "test": is_test_file(r),
            "branches": len(BRANCH_RE.findall(code)), "_text": text, "_code": code,
        }
    file_set = set(files_meta)
    aliases = load_js_aliases(root)
    if eco_counts.get("js"):
        load_js_workspaces(root)
    idx = build_indexes(files_meta, root)
    go_pkg_files = collections.defaultdict(list)
    for p, f in files_meta.items():
        if f["lang"] == "go" and not f["test"]:
            go_pkg_files[os.path.dirname(p)].append(p)

    prec = None
    if precise and args.precise == "auto":
        class Ctx:
            pass
        ctx = Ctx()
        ctx.root, ctx.files_meta, ctx.file_set, ctx.idx = root, files_meta, file_set, idx
        ctx.allow_build, ctx.fetch_tools = args.allow_build, args.fetch_tools
        ctx.js_fallback = lambda spec, frm: resolve_js(spec, frm, file_set, aliases)
        ctx.js_is_workspace = lambda spec: any(spec == n or spec.startswith(n + "/") for n in WORKSPACES)
        prec = precise.run(ctx)

    edges = {}
    externals = collections.Counter()
    for p, f in files_meta.items():
        if prec and p in prec.imports:
            internal, ext = prec.imports[p]
            internal = {t for t in internal if t in file_set and t != p}
        else:
            internal, ext = extract_imports(f, file_set, idx, aliases, root, go_pkg_files)
        f["imports"] = sorted(internal)
        f["externals"] = sorted(ext)
        externals.update(ext)
        if f["test"] and not args.include_tests_in_graph:
            continue
        edges[p] = [t for t in internal if args.include_tests_in_graph or not files_meta[t]["test"]]
        # signals
        sig = {}
        is_ui_file = p.endswith((".tsx", ".jsx", ".vue", ".svelte", ".astro", ".blade.php", ".cshtml", ".razor", ".html.twig", ".erb"))
        for name, rxs in SIGNALS.items():
            if name == "ui" and f["lang"] == "js" and not is_ui_file and not re.search(r"\buse(State|Effect)\(|defineComponent\(|@Component\(", f["_code"]):
                continue  # markup inside strings (email templates) in a server file is not a UI layer
            hits = []
            for rx in rxs:
                m = rx.search(f["_code"])
                if m:
                    line = f["_code"].count("\n", 0, m.start()) + 1
                    hits.append({"line": line, "match": m.group(0)[:80]})
                    break
            if hits:
                sig[name] = hits[0]
        f["signals"] = sig
        sm = SECRET_RE.search(f["_text"])
        if sm:
            f["possible_secret_line"] = f["_text"].count("\n", 0, sm.start()) + 1
        dm = DEFAULT_SECRET_RE.search(f["_code"])
        if dm:
            f["default_secret_line"] = f["_code"].count("\n", 0, dm.start()) + 1

    pruned = precise.prune_undeclared(prec, files_meta, edges) if prec else []
    if pruned:
        for p, t in pruned:
            if t in files_meta[p]["imports"]:
                files_meta[p]["imports"].remove(t)
    phantom = precise.undeclared_workspace_deps(prec, edges) if prec else []

    # dependency injection wiring: runtime edges, kept apart from source imports
    di_info = di.extract(root, files_meta, file_set, idx) if di else None
    runtime_edges = {}
    if di_info:
        for p, ts in di_info["runtime_edges"].items():
            if p in edges:
                runtime_edges[p] = sorted(t for t in ts if t not in edges.get(p, []) and not files_meta[t]["test"])
        for p, ts in runtime_edges.items():
            files_meta[p]["runtime_imports"] = ts

    # files loaded by the framework or the package manager, not imported: never "unused"
    autoloaded = set()
    cj = os.path.join(root, "composer.json")
    if os.path.exists(cj):
        try:
            cdata = json.load(open(cj, encoding="utf-8"))
            for sec in ("autoload", "autoload-dev"):
                autoloaded |= {x.replace("\\", "/").lstrip("./") for x in (cdata.get(sec) or {}).get("files", [])}
        except ValueError:
            pass
    for p in autoloaded:
        if p in files_meta:
            files_meta[p]["entry_point"] = "composer autoload.files"

    fan_in = collections.Counter()
    for p, ts in edges.items():
        for t in ts:
            fan_in[t] += 1
    for p, f in files_meta.items():
        f["fan_out"] = len(edges.get(p, ()))
        f["fan_in"] = fan_in.get(p, 0)

    # modules
    mod_files = collections.defaultdict(list)
    unit_of = prec.unit_of if prec else {}
    if str(args.module_depth) == "auto":
        assign = adaptive_modules(files_meta, unit_of=unit_of if len(set(unit_of.values())) >= 2 else None)
    else:
        assign = {p: module_of(p, int(args.module_depth)) for p in files_meta}
    for p, f in files_meta.items():
        f["module"] = assign[p]
        mod_files[f["module"]].append(p)
    mod_edges = collections.defaultdict(collections.Counter)
    for p, ts in edges.items():
        for t in ts:
            a, b = files_meta[p]["module"], files_meta[t]["module"]
            if a != b:
                mod_edges[a][b] += 1
    mod_runtime = collections.defaultdict(collections.Counter)
    for p, ts in runtime_edges.items():
        for t in ts:
            a, b = files_meta[p]["module"], files_meta[t]["module"]
            if a != b:
                mod_runtime[a][b] += 1
    modules = []
    for m, ps in mod_files.items():
        prod = [p for p in ps if not files_meta[p]["test"]]
        tests = [p for p in ps if files_meta[p]["test"]]
        ce = len(mod_edges.get(m, {}))
        ca = sum(1 for other, tgts in mod_edges.items() if m in tgts)
        sig_counts = collections.Counter()
        for p in prod:
            for s in files_meta[p].get("signals", {}):
                sig_counts[s] += 1
        modules.append({
            "name": m, "files": len(prod), "test_files": len(tests),
            "loc": sum(files_meta[p]["loc"] for p in prod),
            "test_loc": sum(files_meta[p]["loc"] for p in tests),
            "efferent": ce, "afferent": ca,
            "instability": round(ce / (ca + ce), 2) if (ca + ce) else None,
            "depends_on": dict(mod_edges.get(m, {})),
            "runtime_depends_on": dict(mod_runtime.get(m, {})),
            "signals": dict(sig_counts),
        })
    modules.sort(key=lambda x: -x["loc"])

    file_cycles = tarjan_scc(sorted(edges), edges)
    file_cycles_out = [
        {"size": len(c), "files": c[:40], "example": shortest_cycle_in(c, edges)} for c in sorted(file_cycles, key=len, reverse=True)
    ]
    medges = {a: list(b) for a, b in mod_edges.items()}
    mod_cycles = tarjan_scc(sorted(mod_files), medges)
    mod_cycles_out = [{"size": len(c), "modules": c, "example": shortest_cycle_in(c, medges)} for c in mod_cycles]

    history = None if args.no_git else git_history(root, file_set, args.since, args.max_commits, args.bulk_threshold)
    if history:
        for p, f in files_meta.items():
            f["churn"] = history["churn"].get(p, 0)
            f["authors"] = history["authors"].get(p, 0)

    # mixed responsibilities: a production file carrying 2+ of http/ui, db, external_io
    mixed = []
    for p, f in files_meta.items():
        if f["test"]:
            continue
        s = f.get("signals", {})
        layers = [k for k in ("http", "ui", "db", "external_io") if k in s]
        entry = ("http" in s or "ui" in s)
        if len(layers) >= 2 and (entry and ("db" in s or "external_io" in s)):
            mixed.append({"path": p, "signals": {k: s[k] for k in layers}, "loc": f["loc"], "branches": f["branches"]})
    mixed.sort(key=lambda x: -(x["loc"] + 5 * x["branches"]))

    prod_files = [f for f in files_meta.values() if not f["test"]]
    max_churn = max((f.get("churn", 0) for f in prod_files), default=0) or 1
    max_br = max((f["branches"] for f in prod_files), default=0) or 1
    for f in prod_files:
        f["hotspot_score"] = round((f.get("churn", 0) / max_churn) * 0.5 + (f["branches"] / max_br) * 0.5, 3) if history else round(f["branches"] / max_br, 3)
    hotspots = sorted(prod_files, key=lambda f: -f["hotspot_score"])[:25]

    prod_risks = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDED_DIRS and not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith((".properties", ".yml", ".yaml", ".env", ".json", ".ts", ".js", ".cs", ".py", ".toml")) and fn not in (".env",):
                continue
            pth = os.path.join(dirpath, fn)
            if os.path.getsize(pth) > 300000:
                continue
            txt = read_text(pth) or ""
            for label, rx in PROD_RISK_PATTERNS:
                m = rx.search(txt)
                if m:
                    prod_risks.append({"risk": label, "path": rel(pth, root), "line": txt.count("\n", 0, m.start()) + 1})
    duplicates = find_duplicates(files_meta)
    entities = extract_entities(files_meta, root)
    workspace_names = {u["name"] for u in (prec.units if prec else []) if u["kind"] == "npm-package"} | set(WORKSPACES)
    hygiene = insights.dependency_hygiene(root, files_meta, workspace_names)
    route_list = insights.routes(files_meta, idx)
    systems = insights.external_systems(files_meta)
    know, author_map = insights.knowledge((history or {}).get("_raw"), files_meta, [{"path": f["path"]} for f in hotspots])
    if author_map:
        with open(os.path.join(out, "authors-map.json"), "w", encoding="utf-8") as fh:
            json.dump(author_map, fh, indent=1)
        if os.path.isdir(os.path.join(root, ".git")):
            gi = os.path.join(out, ".gitignore")
            if not os.path.exists(gi):
                open(gi, "w").write("# local only: maps pseudonyms to real authors\nauthors-map.json\n")


    test_files = [f for f in files_meta.values() if f["test"]]
    langs = collections.Counter(f["lang"] for f in prod_files)
    loc_by_lang = collections.Counter()
    for f in prod_files:
        loc_by_lang[f["lang"]] += f["loc"]

    sources = dict(prec.sources) if prec else {}
    limits = []
    if langs.get("cpp") and "cpp" not in sources:
        limits.append("C/C++: includes resolved by relative path and basename only; build-system include dirs, macros and conditional compilation are ignored. Treat the C++ graph as indicative.")
    if langs.get("csharp") and "csharp" not in sources:
        limits.append(".NET: dependencies inferred from namespaces and referenced type names, not from the compiler. Project references (.csproj) are listed in manifests, check them for the real assembly graph.")
    if langs.get("java") and "java" not in sources:
        limits.append("Java/Kotlin: fully qualified imports and same-package references; reflection, Spring component scanning and DI wiring are invisible.")
    if langs.get("js") and "js" not in sources:
        limits.append("JS/TS: relative imports and tsconfig path aliases; dynamic imports with computed paths, barrel re-exports and framework file-based routing are partially visible.")
    if langs.get("php") and "php" not in sources:
        limits.append("PHP: class map built from namespace + class declarations; service container wiring, facades and string-based class references are invisible.")
    if langs.get("go") and "go" not in sources:
        limits.append("Go: package-level imports mapped to all non-test files of the package (Go's own unit of dependency). Go forbids import cycles between packages, so a reported Go cycle means non-compiling code or a parsing miss: check it.")
    if langs.get("rust") and "rust" not in sources:
        limits.append("Rust: `mod` declarations and `use crate::/self::/super::` paths; macros and re-exports are approximated.")
    if langs.get("csharp") and "csharp" in sources:
        limits.append(".NET: type references inferred from namespaces and type names; cross-project edges checked against the compiler-enforced project graph. Reflection and convention-based DI registration (assembly scanning) stay partly invisible.")
    if langs.get("java") and "java" in sources:
        limits.append("Java/Kotlin: class-level graph from bytecode (jdeps), exact for compiled code; reflection and component scanning without type references stay invisible.")
    if langs.get("cpp") and sources.get("cpp", "").startswith(("include dirs parsed", "conventional")):
        limits.append("C/C++: no compile_commands.json, so per-target flags and macros are not applied. Generate it for an exact graph (cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON, bear -- make, or --allow-build).")
    if di_info and di_info["bindings"]:
        limits.append("Dependency injection: registrations found in code are turned into runtime edges (kept apart from imports); container configuration loaded dynamically or by convention scanning is not resolved.")
    if not history:
        limits.append("No git history available: churn, hotspots by change frequency and co-change coupling are missing.")
    limits.append("Responsibility signals (db, http, ui, external_io...) are regex heuristics. Open the cited line before stating a finding.")

    # strip private keys
    files_out = []
    for p in sorted(files_meta):
        f = {k: v for k, v in files_meta[p].items() if not k.startswith("_")}
        files_out.append(f)

    scan = {
        "tool": "re-arch-scan", "version": "1.1",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "root": root,
        "head": (git(root, "rev-parse", "--short", "HEAD") or "").strip() or None,
        "ecosystems": dict(eco_counts), "manifests": {k: v[:30] for k, v in manifests.items()},
        "module_depth": args.module_depth,
        "totals": {
            "prod_files": len(prod_files), "test_files": len(test_files),
            "prod_loc": sum(f["loc"] for f in prod_files), "test_loc": sum(f["loc"] for f in test_files),
            "loc_by_lang": dict(loc_by_lang), "internal_edges": sum(len(v) for v in edges.values()),
        },
        "support_files": {k: {"files": support[k], "loc": support_loc[k]} for k in support},
        "graph_sources": {k: (sources.get(k) or "regex heuristics") for k in langs},
        "build_units": [{k: v for k, v in u.items() if k != "srcs"} for u in (prec.units if prec else [])],
        "undeclared_cross_unit_edges_dropped": len(pruned),
        "undeclared_workspace_deps": phantom,
        "precision_notes": prec.notes if prec else ["precise mode off: regex resolution only"],
        "not_compiled": sorted(prec.not_compiled)[:200] if prec else [],
        "di": ({"bindings": di_info["bindings"][:300], "frameworks": di_info["frameworks"],
                "runtime_edges": sum(len(v) for v in runtime_edges.values()), "notes": di_info["notes"]} if di_info else None),
        "top_externals": externals.most_common(40),
        "modules": modules,
        "file_cycles": file_cycles_out,
        "module_cycles": mod_cycles_out,
        "mixed_responsibilities": mixed[:80],
        "hotspots": [{"path": f["path"], "score": f["hotspot_score"], "loc": f["loc"], "branches": f["branches"], "churn": f.get("churn"), "fan_in": f["fan_in"], "fan_out": f["fan_out"]} for f in hotspots],
        "duplicates": duplicates,
        "entities": entities,
        "history": ({k: v for k, v in history.items() if k not in ("churn", "authors", "last_touch", "_raw")} if history else None),
        "knowledge": know,
        "dependency_hygiene": hygiene,
        "routes": route_list,
        "external_systems": systems,
        "possible_secrets": [{"path": f["path"], "line": f["possible_secret_line"]} for f in files_out if f.get("possible_secret_line")],
        "default_secret_fallbacks": [{"path": f["path"], "line": f["default_secret_line"]} for f in files_out if f.get("default_secret_line")],
        "production_risks": prod_risks,
        "limits": limits,
        "files": files_out,
    }
    with open(os.path.join(out, "scan.json"), "w", encoding="utf-8") as fh:
        json.dump(scan, fh, indent=1, ensure_ascii=False)

    write_summary(scan, os.path.join(out, "scan-summary.md"))
    print(f"scan.json and scan-summary.md written to {out}")
    print(f"{len(prod_files)} production files, {len(test_files)} test files, {scan['totals']['internal_edges']} internal dependencies, "
          f"{len(file_cycles_out)} file cycles, {len(mod_cycles_out)} module cycles, {len(mixed)} files with mixed responsibilities")


def write_summary(s, path):
    t = s["totals"]
    L = []
    L.append(f"# Scan summary ({s['generated_at']}, HEAD {s['head'] or 'n/a'})\n")
    L.append(f"Ecosystems detected (build manifests found): {', '.join(f'{k} ({v})' for k, v in s['ecosystems'].items()) or 'none (extension-based only)'}  ")
    L.append(f"Production: {t['prod_files']} files, {t['prod_loc']} LOC ({', '.join(f'{k} {v}' for k, v in t['loc_by_lang'].items())})  ")
    ratio = (t["test_loc"] / t["prod_loc"]) if t["prod_loc"] else 0
    L.append(f"Tests: {t['test_files']} files, {t['test_loc']} LOC (test/prod LOC ratio {ratio:.2f})  ")
    L.append(f"Internal dependencies: {t['internal_edges']}  ")
    if s.get("support_files"):
        L.append("Left out of the analysis (config, translations, migrations, seeders): " + ", ".join(f"{k} {v['files']} files / {v['loc']} LOC" for k, v in s["support_files"].items()) + "  ")
    if s["history"]:
        h = s["history"]
        L.append(f"Git (all files): {h['commits_analyzed']} commits {('(' + h['since'] + ')') if h.get('window_note') else 'since ' + h['since']}, {h['contributors']} contributors, {h['bulk_commits_ignored_for_cochange']} bulk commits ignored for co-change  ")
        if h.get("ticket_change_sets"):
            L.append(f"Commits grouped by ticket id for co-change: {h['ticket_change_sets']} tickets  ")
        if h.get("window_note"):
            L.append(f"Note: {h['window_note']}  ")
        if h.get("fix_share") is not None:
            L.append(f"Fix commits (subject mentions fix/bug/hotfix/revert): {h['fix_commits']} ({int(h['fix_share'] * 100)}%)  ")
            if h.get("top_fixed_files"):
                L.append("Most fixed files: " + ", ".join(f"{x['path']} ({x['fix_commits']}/{x['commits']})" for x in h["top_fixed_files"][:8]))
        L.append("")
    else:
        L.append("Git: no history\n")

    if s.get("graph_sources"):
        L.append("## Graph sources (how dependencies were resolved)\n")
        for k, v in s["graph_sources"].items():
            L.append(f"- {k}: {v}")
        for n in s.get("precision_notes", [])[:12]:
            L.append(f"- note: {n}")
        if s.get("undeclared_cross_unit_edges_dropped"):
            L.append(f"- {s['undeclared_cross_unit_edges_dropped']} heuristic edges dropped: they crossed build units without a declared dependency (the compiler would reject them)")
        L.append("")
    if s.get("build_units"):
        L.append(f"## Build units ({len(s['build_units'])})\n")
        for u in s["build_units"][:40]:
            L.append(f"- {u['name']} [{u['kind']}] {u['dir'] or '.'} -> {', '.join(u['deps']) or '-'}")
        if s.get("undeclared_workspace_deps"):
            L.append("\nWorkspace imports not declared in package.json (phantom dependencies):")
            for d in s["undeclared_workspace_deps"][:15]:
                L.append(f"- {d['from']} -> {d['to']} ({d['imports']} imports)")
        L.append("")
    if s.get("di") and s["di"]["bindings"]:
        d = s["di"]
        L.append(f"## Dependency injection ({len(d['bindings'])} bindings, {d['runtime_edges']} runtime edges)\n")
        L.append("Runtime edges link consumers of an abstraction to the implementation the container injects. They are kept apart from imports.\n")
        for b in d["bindings"][:30]:
            where = f" (registered in {b['registered_in']})" if b.get("registered_in") else ""
            L.append(f"- [{b['kind']}] {b['abstraction']} -> {b['implementation']} ({b['implementation_file']}){where}")
        for n in d.get("notes", [])[:8]:
            L.append(f"- note: {n}")
        L.append("")
    L.append("## Modules (by LOC)\n")
    L.append("| module | files | LOC | tests | Ca | Ce | I | signals |")
    L.append("|---|---|---|---|---|---|---|---|")
    for m in s["modules"][:40]:
        sig = ", ".join(f"{k}:{v}" for k, v in sorted(m["signals"].items()))
        L.append(f"| {m['name']} | {m['files']} | {m['loc']} | {m['test_files']} | {m['afferent']} | {m['efferent']} | {m['instability'] if m['instability'] is not None else '-'} | {sig} |")
    L.append("")
    L.append("Ca = modules depending on it, Ce = modules it depends on, I = Ce/(Ca+Ce) (0 stable, 1 unstable).\n")

    L.append("## Module dependencies\n")
    for m in s["modules"][:40]:
        if m["depends_on"]:
            deps = ", ".join(f"{k} ({v})" for k, v in sorted(m["depends_on"].items(), key=lambda x: -x[1]))
            L.append(f"- {m['name']} -> {deps}")
        if m.get("runtime_depends_on"):
            rdeps = ", ".join(f"{k} ({v})" for k, v in sorted(m["runtime_depends_on"].items(), key=lambda x: -x[1]))
            L.append(f"  - at runtime (DI) -> {rdeps}")
    L.append("")

    L.append(f"## Cycles\n\nModule cycles: {len(s['module_cycles'])}")
    for c in s["module_cycles"][:10]:
        L.append(f"- {' -> '.join(c['example'] or c['modules'])}")
    L.append(f"\nFile cycles: {len(s['file_cycles'])}")
    for c in s["file_cycles"][:10]:
        members = ", ".join(c["files"][:8]) + (" ..." if c["size"] > 8 else "")
        L.append(f"- {c['size']} files in a cycle ({members}); shortest loop: {' -> '.join(c['example'] or c['files'][:6])}")
    L.append("")

    L.append(f"## Mixed responsibilities ({len(s['mixed_responsibilities'])} files)\n")
    L.append("Entry point (http/ui) in the same file as persistence or external I/O. Verify each before reporting.\n")
    for m in s["mixed_responsibilities"][:25]:
        sig = "; ".join(f"{k} L{v['line']} `{v['match']}`" for k, v in m["signals"].items())
        L.append(f"- {m['path']} ({m['loc']} LOC, {m['branches']} branches): {sig}")
    L.append("")

    L.append("## Hotspots (change frequency x complexity proxy)\n")
    L.append("| file | score | LOC | branches | churn | fan-in | fan-out |")
    L.append("|---|---|---|---|---|---|---|")
    for h in s["hotspots"][:20]:
        L.append(f"| {h['path']} | {h['score']} | {h['loc']} | {h['branches']} | {h['churn'] if h['churn'] is not None else '-'} | {h['fan_in']} | {h['fan_out']} |")
    L.append("")

    if s["duplicates"]:
        L.append(f"## Duplicated blocks ({len(s['duplicates'])} groups)\n")
        for d in s["duplicates"][:20]:
            what = f"same statement `{d['statement'][:70]}`" if d.get("statement") else f"{d['blocks']} block(s)"
            L.append(f"- {what}: " + ", ".join(f"{f['path']}:{f['line']}" for f in d["files"]))
        L.append("")

    if s["entities"]:
        L.append(f"## Data model ({len(s['entities'])} entities)\n")
        for e in s["entities"][:60]:
            L.append(f"- {e['name']} [{', '.join(e['kinds'])}] refs: {', '.join(e['references']) or '-'}; used in {len(e['used_in'])} files")
        L.append("")

    if s["history"] and s["history"]["cochange"]:
        L.append("## Strongest co-change pairs\n")
        for c in s["history"]["cochange"][:20]:
            L.append(f"- {c['a']} <-> {c['b']} ({c['count']} commits, strength {c['strength']})")
        L.append("")

    k = s.get("knowledge")
    if k:
        L.append(f"## Knowledge distribution ({k['authors']} authors, {k['inactive_authors']} inactive for {k['inactive_after_days']}+ days)\n")
        L.append(k["note"] + "\n")
        if k["islands_in_hotspots"]:
            L.append("Knowledge islands in hotspots (one author wrote 80%+ of a busy file):")
            for i in k["islands_in_hotspots"][:10]:
                L.append(f"- {i['path']}: {i['main_author']} {int(i['main_share'] * 100)}%" + (" (inactive)" if i["main_inactive"] else ""))
        if k["orphaned_files"]:
            L.append("\nCode mainly written by inactive authors:")
            for o in k["orphaned_files"][:10]:
                L.append(f"- {o['path']} ({o['loc']} LOC, {o['main_author']} {int(o['main_share'] * 100)}%)")
        risky = [m for m in k["modules"] if m["orphan_share"] >= 0.5 or m["top_author_share"] >= 0.8]
        if risky:
            L.append("\nModules with concentrated or lost knowledge:")
            for m in risky[:10]:
                L.append(f"- {m['module']}: top author {m['top_author']} {int(m['top_author_share'] * 100)}%, orphaned {int(m['orphan_share'] * 100)}%")
        L.append("")
    h = s.get("dependency_hygiene") or {}
    if any(h.get(x) for x in ("same_job", "undeclared", "declared_unused")):
        L.append("## Dependency hygiene\n")
        for d in h.get("same_job", []):
            L.append(f"- several libraries for {d['job']}: " + ", ".join(f"{l} ({n} files)" for l, n in d["imported_by_files"].items()))
        for d in h.get("undeclared", [])[:15]:
            L.append(f"- imported but not declared: {d['package']} in {d['manifest']} ({d['status']}), e.g. {', '.join(d['files'][:2])}")
        if h.get("declared_unused"):
            L.append("- declared but never imported by scanned code (candidates, check scripts and config): " + ", ".join(f"{d['package']}" for d in h["declared_unused"][:20]))
        L.append("")
    if s.get("external_systems"):
        L.append("## External systems\n")
        for x in s["external_systems"][:20]:
            L.append(f"- {x['name']} [{x['kind']}] used in {x['file_count']} files" + (f" via {', '.join(x['packages'][:3])}" if x["packages"] else ""))
        L.append("")
    if s.get("routes"):
        groups = collections.Counter(insights.route_resource(r["path"]) for r in s["routes"])
        L.append(f"## HTTP routes ({len(s['routes'])})\n")
        L.append("By resource: " + ", ".join(f"{k} ({v})" for k, v in groups.most_common(25)) + "\n")
        for r in s["routes"][:25]:
            L.append(f"- {r['method']} {r['path']} -> {r['file']}")
        L.append("")
    if s.get("default_secret_fallbacks") or s.get("production_risks"):
        L.append("## Production-readiness signals\n")
        for p in s.get("default_secret_fallbacks", [])[:10]:
            L.append(f"- secret with a hard-coded default value: {p['path']}:{p['line']} (anyone can forge tokens if the variable is missing)")
        for p in s.get("production_risks", [])[:15]:
            L.append(f"- {p['risk']}: {p['path']}:{p['line']} (check which profile/environment it applies to)")
        L.append("")
    if s["possible_secrets"]:
        L.append("## Possible hard-coded secrets\n")
        for p in s["possible_secrets"][:20]:
            L.append(f"- {p['path']}:{p['line']}")
        L.append("")

    L.append("## Top external dependencies\n")
    L.append(", ".join(f"{n} ({c})" for n, c in s["top_externals"][:30]))
    L.append("\n## Limits of this scan\n")
    for l in s["limits"]:
        L.append(f"- {l}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
