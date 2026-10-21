#!/usr/bin/env python3
"""
insights.py: higher-level signals for re-arch-scan.

  knowledge()          who knows what: main-author share per file, knowledge
                       islands in hotspots, code whose authors left. Authors are
                       pseudonymised (A1, A2...) in scan.json; the mapping stays in
                       a local file so reports can be shared without naming people.
  dependency_hygiene() libraries doing the same job, packages declared but never
                       imported, packages imported but never declared (phantom or
                       hallucinated dependencies, frequent in AI-generated code).
  routes()             HTTP routes and their handler files, per framework.
  external_systems()   databases, payment, email, queues, storage, LLM APIs... the
                       systems the application talks to (C4 context view).
"""
import collections
import json
import os
import re

# ---------------------------------------------------------------------------
# Knowledge distribution
# ---------------------------------------------------------------------------


def knowledge(history_raw, files_meta, hotspots, inactive_days=180):
    """history_raw: {"lines_by_author": {path: {author: lines}}, "last_ts_by_author": {author: ts}, "now": ts}"""
    if not history_raw or not history_raw.get("lines_by_author"):
        return None, {}
    now = history_raw["now"]
    last = history_raw["last_ts_by_author"]
    # pseudonyms by overall contribution, stable across runs of the same history
    total_by_author = collections.Counter()
    for per in history_raw["lines_by_author"].values():
        for a, n in per.items():
            total_by_author[a] += n
    alias = {a: f"A{i + 1}" for i, (a, _) in enumerate(total_by_author.most_common())}
    inactive = {a for a, ts in last.items() if now - ts > inactive_days * 86400}
    per_file = {}
    for p, per in history_raw["lines_by_author"].items():
        if p not in files_meta or files_meta[p]["test"]:
            continue
        tot = sum(per.values()) or 1
        main, n = max(per.items(), key=lambda x: x[1])
        per_file[p] = {
            "main_author": alias[main], "main_share": round(n / tot, 2), "authors": len(per),
            "main_inactive": main in inactive,
            "inactive_share": round(sum(v for a, v in per.items() if a in inactive) / tot, 2),
        }
    hot = [h["path"] for h in hotspots[:25]]
    meaningful = len(alias) >= 3
    islands = [{"path": p, **per_file[p]} for p in hot if p in per_file and per_file[p]["main_share"] >= 0.8 and per_file[p]["authors"] <= 2
               and files_meta[p]["loc"] >= 15] if meaningful else []
    orphaned = sorted(
        ({"path": p, "loc": files_meta[p]["loc"], **v} for p, v in per_file.items() if v["main_inactive"] and v["main_share"] >= 0.5 and files_meta[p]["loc"] >= 15),
        key=lambda x: -x["loc"])
    by_module = collections.defaultdict(lambda: collections.Counter())
    for p, v in per_file.items():
        m = files_meta[p].get("module", "?")
        by_module[m]["loc"] += files_meta[p]["loc"]
        if v["main_inactive"]:
            by_module[m]["orphan_loc"] += files_meta[p]["loc"]
        by_module[m][v["main_author"]] += files_meta[p]["loc"]
    modules = []
    for m, c in by_module.items():
        loc = c.pop("loc", 0) or 1
        orphan = c.pop("orphan_loc", 0)
        top_author, top_loc = (c.most_common(1) or [("-", 0)])[0]
        modules.append({"module": m, "orphan_share": round(orphan / loc, 2), "top_author": top_author,
                        "top_author_share": round(top_loc / loc, 2), "authors": len(c)})
    modules.sort(key=lambda x: (-x["orphan_share"], -x["top_author_share"]))
    if not meaningful:
        modules = [m for m in modules if m["orphan_share"] >= 0.5]
    out = {
        "authors": len(alias), "inactive_authors": len(inactive & set(alias)), "inactive_after_days": inactive_days,
        "islands_in_hotspots": islands[:20], "orphaned_files": orphaned[:30], "modules": modules[:40],
        "note": ("Authors are pseudonymised (A1 = largest contributor to the scanned production code; contributors who only touched tests, docs or config are not counted here). "
                 "The mapping is in authors-map.json, local only: do not publish it. If the repository is a fork or started from a template, part of this history belongs to upstream: check before reporting a risk."
                 + ("" if meaningful else " Fewer than 3 authors in the history: concentration is the normal state, so islands are not reported.")),
    }
    return out, {v: k for k, v in alias.items()}


# ---------------------------------------------------------------------------
# Dependency hygiene
# ---------------------------------------------------------------------------

# Libraries that do the same job. Two or more in use = one more thing to learn,
# configure and keep consistent; typical of prompt-by-prompt generation.
SAME_JOB = {
    "dates": ["moment", "date-fns", "dayjs", "luxon", "nesbot/carbon", "time", "chrono", "NodaTime"],
    "HTTP client": ["axios", "got", "node-fetch", "ky", "superagent", "undici", "request", "guzzlehttp/guzzle", "symfony/http-client", "reqwest", "ureq", "RestSharp", "Flurl.Http", "okhttp3", "retrofit2"],
    "validation": ["zod", "yup", "joi", "valibot", "class-validator", "ajv", "superstruct", "FluentValidation", "validator"],
    "state management": ["redux", "@reduxjs/toolkit", "zustand", "mobx", "jotai", "recoil", "valtio", "pinia", "vuex", "xstate"],
    "data fetching": ["@tanstack/react-query", "react-query", "swr", "@apollo/client", "urql"],
    "ORM / query builder": ["@prisma/client", "prisma", "typeorm", "sequelize", "drizzle-orm", "knex", "mongoose", "objection", "mikro-orm", "@mikro-orm/core", "kysely",
                            "gorm.io/gorm", "github.com/jmoiron/sqlx", "entgo.io/ent", "diesel", "sqlx", "sea-orm", "Dapper", "Microsoft.EntityFrameworkCore", "NHibernate"],
    "styling": ["styled-components", "@emotion/react", "@emotion/styled", "tailwindcss", "sass", "@mui/material", "@chakra-ui/react", "antd", "@mantine/core", "bootstrap"],
    "forms": ["react-hook-form", "formik", "@tanstack/react-form", "final-form", "react-final-form"],
    "logging": ["winston", "pino", "bunyan", "log4js", "loglevel", "monolog/monolog", "Serilog", "NLog", "log4net", "logrus", "go.uber.org/zap", "github.com/sirupsen/logrus", "github.com/rs/zerolog", "tracing", "log", "env_logger"],
    "test runner": ["jest", "vitest", "mocha", "ava", "jasmine"],
    "utility belt": ["lodash", "underscore", "ramda", "lodash-es", "radash"],
    "UUID / ids": ["uuid", "nanoid", "cuid", "@paralleldrive/cuid2", "ulid"],
    "auth": ["next-auth", "@auth/core", "passport", "@clerk/nextjs", "lucia", "jsonwebtoken", "jose", "@supabase/auth-helpers-nextjs"],
}
# imported only from config files or binaries: never "unused" just because no source file imports them
CONFIG_ONLY = re.compile(
    r"^(@types/|typescript$|eslint|prettier|@eslint|tailwindcss$|postcss|autoprefixer|@tailwindcss|vite$|@vitejs|webpack|babel|@babel|"
    r"next$|nuxt$|@nuxt|ts-node|tsx$|nodemon|husky|lint-staged|jest$|vitest$|@vitest|@playwright|playwright|cypress|@testing-library|"
    r"prisma$|drizzle-kit|concurrently|cross-env|dotenv-cli|rimraf|turbo$|nx$|@nx|lerna|@commitlint|sass$|less$|"
    r"@sveltejs|svelte$|@astrojs|astro$|react-dom$|@storybook|storybook|sharp$|pm2|serve$)")
NODE_BUILTINS = {"assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants", "crypto", "dgram", "dns", "domain",
                 "events", "fs", "http", "http2", "https", "inspector", "module", "net", "os", "path", "perf_hooks", "process", "punycode",
                 "querystring", "readline", "repl", "stream", "string_decoder", "sys", "timers", "tls", "trace_events", "tty", "url",
                 "util", "v8", "vm", "wasi", "worker_threads", "zlib", "fs/promises", "stream/promises", "test"}


def _js_manifests(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git", "dist", "build", ".next", "vendor") and not d.startswith(".")]
        if "package.json" in filenames:
            try:
                data = json.load(open(os.path.join(dirpath, "package.json"), encoding="utf-8"))
            except (ValueError, OSError):
                continue
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            out["" if rel == "." else rel] = {
                "name": data.get("name"),
                "deps": set((data.get("dependencies") or {}).keys()),
                "dev": set((data.get("devDependencies") or {}).keys()) | set((data.get("peerDependencies") or {}).keys()) | set((data.get("optionalDependencies") or {}).keys()),
            }
    return out


def dependency_hygiene(root, files_meta, workspace_names=()):
    findings = {"same_job": [], "declared_unused": [], "undeclared": []}
    used_names = collections.Counter()
    for f in files_meta.values():
        for e in f.get("externals", []):
            used_names[e] += 1
    # declared everywhere (all ecosystems we can read cheaply)
    declared = set()
    manifests = _js_manifests(root)
    for m in manifests.values():
        declared |= m["deps"] | m["dev"]
    for name in ("composer.json",):
        p = os.path.join(root, name)
        if os.path.exists(p):
            try:
                data = json.load(open(p, encoding="utf-8"))
                declared |= set((data.get("require") or {}).keys()) | set((data.get("require-dev") or {}).keys())
            except ValueError:
                pass
    gomod = os.path.join(root, "go.mod")
    go_required = set()
    if os.path.exists(gomod):
        go_required = set(re.findall(r"^\s*(?:require\s+)?([\w.\-]+\.[a-z]{2,}/[\w.\-/]+)\s+v[\w.\-+]+", open(gomod, encoding="utf-8").read(), re.M))
        declared |= go_required
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("target", ".git", "node_modules") and not d.startswith(".")]
        for fn in filenames:
            if fn == "Cargo.toml":
                text = open(os.path.join(dirpath, fn), encoding="utf-8", errors="replace").read()
                for sec in re.findall(r"^\[(?:dev-)?dependencies\]\s*\n(.*?)(?=^\[|\Z)", text, re.M | re.S):
                    declared |= set(re.findall(r"^([\w-]+)\s*=", sec, re.M))
            elif fn.endswith(".csproj"):
                text = open(os.path.join(dirpath, fn), encoding="utf-8", errors="replace").read()
                declared |= set(re.findall(r'PackageReference\s+Include="([^"]+)"', text))
    pool = declared | set(used_names)
    for job, libs in SAME_JOB.items():
        present = [l for l in libs if l in pool]
        # one ORM + its CLI is not a duplicate
        if job == "ORM / query builder" and set(present) <= {"@prisma/client", "prisma"}:
            continue
        if len(present) >= 2:
            findings["same_job"].append({"job": job, "libraries": present,
                                         "imported_by_files": {l: used_names.get(l, 0) for l in present}})
    # JS: declared but unused, imported but undeclared (per nearest package.json)
    if manifests:
        dirs = sorted(manifests, key=len, reverse=True)
        used_by_pkg = collections.defaultdict(set)
        files_by_ext = collections.defaultdict(list)
        for p, f in files_meta.items():
            if f["lang"] != "js":
                continue
            d = next((x for x in dirs if x == "" or p.startswith(x + "/")), None)
            if d is None:
                continue
            for e in f.get("externals", []):
                if e.startswith("node:") or e in NODE_BUILTINS:
                    continue
                used_by_pkg[d].add(e)
                files_by_ext[(d, e)].append(p)
        all_declared = set().union(*[m["deps"] | m["dev"] for m in manifests.values()])
        root_declared = manifests.get("", {"deps": set(), "dev": set()})
        for d, m in manifests.items():
            for e in sorted(used_by_pkg.get(d, ())):
                if e in m["deps"] or e in m["dev"] or e in workspace_names:
                    continue
                where = "declared in another package.json (phantom dependency through hoisting)" if e in all_declared else "declared nowhere (hallucinated import or missing install)"
                if e in root_declared["deps"] | root_declared["dev"]:
                    where = "declared only at the monorepo root"
                findings["undeclared"].append({"package": e, "manifest": (d + "/" if d else "") + "package.json", "status": where,
                                               "files": files_by_ext[(d, e)][:5]})
            for dep in sorted(m["deps"]):
                if dep in used_by_pkg.get(d, ()) or CONFIG_ONLY.search(dep) or dep in workspace_names:
                    continue
                # used from a sub-package or from a non-scanned file (config, scripts) is possible: candidates only
                if not any(dep in v for v in used_by_pkg.values()):
                    findings["declared_unused"].append({"package": dep, "manifest": (d + "/" if d else "") + "package.json"})
    # Go: imported modules missing from go.mod
    if go_required:
        for p, f in files_meta.items():
            if f["lang"] != "go":
                continue
            for e in f.get("externals", []):
                if "." in e.split("/")[0] and not any(e == r or e.startswith(r + "/") or r.startswith(e) for r in go_required):
                    findings["undeclared"].append({"package": e, "manifest": "go.mod", "status": "not in go.mod require", "files": [p]})
    findings["declared_unused"] = findings["declared_unused"][:40]
    findings["undeclared"] = findings["undeclared"][:40]
    return findings


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

ROUTE_PATTERNS = [
    ("express-like", "js", re.compile(r"\b(?:app|router|server|api|fastify|r)\.(get|post|put|patch|delete|all)\(\s*['\"`]([^'\"`]+)['\"`]")),
    ("nestjs", "js", re.compile(r"@(Get|Post|Put|Patch|Delete|All)\(\s*(?:['\"`]([^'\"`]*)['\"`])?\s*\)")),
    ("laravel", "php", re.compile(r"Route::(get|post|put|patch|delete|any|options|match|resource|apiResource|resources)\(\s*(?:\[[^\]]*\]\s*,\s*)?['\"]([^'\"]+)['\"]\s*,\s*(?:\[\s*\\?([\\\w]+)::class|\\?([\\\w]+)::class|['\"]([\\\w]+)(?:@\w+)?['\"])")),
    ("symfony", "php", re.compile(r"#\[Route\(\s*['\"]([^'\"]+)['\"](?:[^\]]*methods:\s*\[([^\]]*)\])?")),
    ("spring", "java", re.compile(r"@(Get|Post|Put|Patch|Delete|Request)Mapping\b(?:\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*\"([^\"]*)\")?")),
    ("aspnet", "csharp", re.compile(r"\[(?:Http(Get|Post|Put|Patch|Delete))(?:\(\s*\"([^\"]*)\"\s*\))?\]")),
    ("aspnet-minimal", "csharp", re.compile(r"\.Map(Get|Post|Put|Patch|Delete)\(\s*\"([^\"]+)\"")),
    ("go-http", "go", re.compile(r"\.(?:HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE|Get|Post|Put|Patch|Delete)\(\s*\"([^\"]+)\"")),
    ("axum", "rust", re.compile(r"\.route\(\s*\"([^\"]+)\"\s*,\s*(get|post|put|patch|delete)")),
    ("actix", "rust", re.compile(r"#\[(get|post|put|patch|delete)\(\s*\"([^\"]+)\"")),
]
CLASS_PREFIX = {
    "nestjs": re.compile(r"@Controller\(\s*['\"`]([^'\"`]*)['\"`]"),
    "spring": re.compile(r"@RequestMapping\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*\"([^\"]*)\"[^)]*\)\s*(?:@\w+[^\n]*\n\s*)*(?:public\s+)?(?:abstract\s+)?class"),
    "aspnet": re.compile(r"\[Route\(\s*\"([^\"]*)\"\s*\)\]"),
}


def _next_route(path):
    m = re.match(r"^(?:src/)?(?:app|pages)/(.*?)(?:/route|/page|/index)?\.(?:ts|tsx|js|jsx)$", path)
    if not m:
        return None
    segs = [s for s in m.group(1).split("/") if s and not (s.startswith("(") and s.endswith(")")) and not s.startswith("@")]
    segs = [":" + s.strip("[].") if s.startswith("[") else s for s in segs]
    return "/" + "/".join(segs)


def routes(files_meta, idx):
    out = []
    php_class = idx.get("php_class", {})
    short_php = collections.defaultdict(list)
    for fq, p in php_class.items():
        short_php[fq.rsplit("\\", 1)[-1]].append(p)
    for p, f in files_meta.items():
        if f["test"]:
            continue
        code, lang = f.get("_code") or "", f["lang"]
        if lang == "js" and re.search(r"(^|/)(app|pages)/", p) and re.search(r"(^|/)(route|page)\.(ts|tsx|js|jsx)$|(^|/)pages/api/", p):
            r = _next_route(p)
            if r is not None:
                methods = re.findall(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b|export\s+const\s+(GET|POST|PUT|PATCH|DELETE)\b", code)
                methods = [a or b for a, b in methods] or (["PAGE"] if "/page." in p or p.endswith(("page.tsx", "page.jsx")) else ["ANY"])
                for m in methods:
                    out.append({"method": m, "path": r, "file": p, "line": 1, "framework": "next.js"})
        for fw, flang, rx in ROUTE_PATTERNS:
            if flang != lang:
                continue
            prefix = ""
            if fw in CLASS_PREFIX:
                pm = CLASS_PREFIX[fw].search(code)
                prefix = ("/" + pm.group(1).strip("/")) if pm and pm.group(1) else ""
            for m in rx.finditer(code):
                g = m.groups()
                if fw in ("spring", "aspnet") and re.match(r"[^;{]*?\bclass\b", code[m.end():m.end() + 400]):
                    continue  # class-level mapping: already applied as prefix
                line = code.count("\n", 0, m.start()) + 1
                handler = p
                if fw == "laravel":
                    method, path = g[0].upper(), g[1]
                    cls = (g[2] or g[3] or g[4] or "").lstrip("\\")
                    cands = [php_class[cls]] if cls in php_class else short_php.get(cls.rsplit("\\", 1)[-1], [])
                    handler = cands[0] if len(cands) == 1 else p
                elif fw == "symfony":
                    path, method = g[0], (re.sub(r"['\"\s]", "", g[1] or "") or "ANY")
                elif fw in ("go-http",):
                    method, path = "ANY", g[0]
                elif fw == "axum":
                    path, method = g[0], g[1].upper()
                elif fw == "actix":
                    method, path = g[0].upper(), g[1]
                else:
                    method, path = (g[0] or "ANY").upper(), (g[1] or "")
                if fw in ("nestjs", "spring", "aspnet"):
                    path = (prefix + ("/" + path.strip("/") if path else "")) or "/"
                    path = path.replace("[controller]", re.sub(r"(Controller)?\.\w+$", "", os.path.basename(p)).lower())
                out.append({"method": method, "path": path if path.startswith("/") else "/" + path, "file": handler,
                            "declared_in": f"{p}:{line}", "line": line, "framework": fw})
    return out[:2000]


def route_resource(path):
    """Resource key used to group routes: first meaningful segment(s)."""
    segs = [s for s in path.split("/") if s and not s.startswith((":", "{", "<", "[")) and not re.match(r"^v\d+$|^api$|^admin$|^public$", s)]
    return segs[0].lower() if segs else "/"


# ---------------------------------------------------------------------------
# External systems
# ---------------------------------------------------------------------------

SYSTEMS = [
    # (regex on external name, system, kind)
    (r"^(@prisma/client|prisma|pg|postgres|mysql2?|mariadb|sqlite3|better-sqlite3|typeorm|sequelize|drizzle-orm|knex|kysely|@mikro-orm/.*|objection)$", "Relational database", "database"),
    (r"^(mongoose|mongodb)$", "MongoDB", "database"),
    (r"^(redis|ioredis|@upstash/redis)$|StackExchange|go-redis|^redis$", "Redis", "cache"),
    (r"^(stripe|@stripe/.*)$|^Stripe$|stripe-go|stripe_php|^async_stripe$", "Stripe", "payment"),
    (r"^(paypal.*|@paypal/.*|braintree|@adyen/.*|mollie.*)$", "Payment provider", "payment"),
    (r"^(nodemailer|@sendgrid/mail|resend|mailgun.*|postmark|@aws-sdk/client-ses|@react-email/.*)$|^SendGrid|^MailKit|lettre", "Email service", "email"),
    (r"^(twilio|@vonage/.*|messagebird)$|^Twilio", "SMS / telephony", "messaging"),
    (r"^(openai|@anthropic-ai/sdk|@google/generative-ai|langchain|@langchain/.*|ai|@ai-sdk/.*|cohere-ai|replicate)$|^OpenAI|^Anthropic|async_openai", "LLM API", "ai"),
    (r"^(@aws-sdk/client-s3|aws-sdk|@google-cloud/storage|@azure/storage-blob|minio|cloudinary|uploadthing)$|^Aws$|^Amazon|^Azure\.Storage|aws_sdk_s3", "Object storage / cloud", "storage"),
    (r"^(kafkajs|amqplib|bullmq|bull|@aws-sdk/client-sqs|nats|@google-cloud/pubsub|rabbitmq.*)$|^MassTransit|^RabbitMQ|^Confluent|kafka-go|^rdkafka$|^lapin$", "Message broker / queue", "queue"),
    (r"^(@supabase/supabase-js|@supabase/.*)$", "Supabase", "platform"),
    (r"^(firebase|firebase-admin)$", "Firebase", "platform"),
    (r"^(@clerk/.*|next-auth|@auth/.*|@auth0/.*|auth0|keycloak-js|@okta/.*)$", "Identity provider", "identity"),
    (r"^(@sentry/.*|sentry.*)$|^Sentry", "Error tracking", "observability"),
    (r"^(posthog-js|posthog-node|@segment/.*|mixpanel.*|@amplitude/.*)$", "Product analytics", "analytics"),
    (r"^(algoliasearch|@elastic/elasticsearch|meilisearch|typesense)$|^Elastic", "Search engine", "search"),
    (r"^(googleapis|@googleapis/.*|@microsoft/microsoft-graph-client|@slack/.*|@octokit/.*|hubspot.*|@hubspot/.*|salesforce.*|jsforce)$", "Third-party SaaS API", "saas"),
    (r"^(Microsoft\.EntityFrameworkCore|Dapper|Npgsql|MySqlConnector|Microsoft\.Data\.SqlClient|jakarta\.persistence|javax\.persistence|org\.springframework\.data|org\.hibernate|gorm\.io/.*|github\.com/jackc/pgx.*|github\.com/lib/pq|github\.com/go-sql-driver/mysql|sqlx|diesel|sea_orm|rusqlite|Illuminate|Doctrine)$", "Relational database", "database"),
]
SYSTEMS = [(re.compile(rx), name, kind) for rx, name, kind in SYSTEMS]


def external_systems(files_meta):
    found = {}
    for p, f in files_meta.items():
        if f["test"]:
            continue
        for e in f.get("externals", []):
            for rx, name, kind in SYSTEMS:
                if rx.search(e):
                    s = found.setdefault(name, {"name": name, "kind": kind, "packages": set(), "files": set()})
                    s["packages"].add(e)
                    s["files"].add(p)
                    break
        # direct HTTP calls to hard-coded hosts
        for host in re.findall(r"['\"`]https?://([a-z0-9.\-]+\.[a-z]{2,})(?:[/:'\"`])", f.get("_code") or ""):
            if host.startswith(("localhost", "127.", "example.", "schemas.", "www.w3.org", "json-schema.org")):
                continue
            name = "HTTP: " + host
            s = found.setdefault(name, {"name": name, "kind": "http", "packages": set(), "files": set()})
            s["files"].add(p)
    out = []
    for s in found.values():
        out.append({"name": s["name"], "kind": s["kind"], "packages": sorted(s["packages"])[:6], "files": sorted(s["files"])[:30], "file_count": len(s["files"])})
    out.sort(key=lambda x: (x["kind"] == "http", -x["file_count"]))
    return out[:40]
