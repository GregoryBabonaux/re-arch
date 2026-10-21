#!/usr/bin/env python3
"""
re-arch test-suite.  Run:  python3 tests/test_suite.py  [-v]

Precise-mode tests run only when the toolchain is present (cmake + a C++
compiler, cargo, javac + jdeps, go, node, php) and are skipped otherwise, so
the suite also runs on a bare Python install.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings

warnings.simplefilter("ignore", ResourceWarning)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SK = os.path.join(ROOT, "skills")
SCAN = os.path.join(SK, "re-arch-scan", "scripts", "scan.py")
CLUSTER = os.path.join(SK, "re-arch-domains", "scripts", "cluster.py")
CHECK = os.path.join(SK, "re-arch-guardrails", "scripts", "check_architecture.py")
VALIDATE = os.path.join(SK, "re-arch-report", "scripts", "validate.py")
RENDER = os.path.join(SK, "re-arch-report", "scripts", "render.py")
CHECK_RENDER = os.path.join(SK, "re-arch-report", "scripts", "check_render.py")
DIFF = os.path.join(SK, "re-arch-audit", "scripts", "diff_rearch.py")
PLAN_MD = os.path.join(SK, "re-arch-plan", "scripts", "plan_to_md.py")
PITCH_MD = os.path.join(SK, "re-arch-pitch", "scripts", "pitch_to_md.py")
TO_OKF = os.path.join(SK, "re-arch-report", "scripts", "to_okf.py")
sys.path.insert(0, HERE)
import fixtures  # noqa: E402
import golden  # noqa: E402

TMP = tempfile.mkdtemp(prefix="re-arch-tests-")


def run(*cmd, cwd=None, check=True, stdin=None):
    r = subprocess.run([sys.executable] + list(cmd), cwd=cwd, capture_output=True, text=True, input=stdin)
    if check and r.returncode != 0:
        raise AssertionError(f"{' '.join(cmd)} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


def scan(repo, *extra, mode="auto"):
    out = os.path.join(repo, ".re-arch-" + mode)
    run(SCAN, repo, "--out", out, "--precise", mode, *extra)
    return json.load(open(os.path.join(out, "scan.json")))


def imports(s, path):
    return set(next(f for f in s["files"] if f["path"] == path)["imports"])


def runtime(s, path):
    return set(next(f for f in s["files"] if f["path"] == path).get("runtime_imports", []))


def fixture(name):
    return fixtures.build(name, os.path.join(TMP, name))


class PreciseMode(unittest.TestCase):
    @unittest.skipUnless(fixtures.has("cmake") and (fixtures.has("clang++") or fixtures.has("g++")), "cmake + C++ compiler")
    def test_cpp_compile_commands(self):
        d = fixture("cpp-cmake")
        self.assertTrue(fixtures.prepare_cpp(d))
        off, on = scan(d, mode="off"), scan(d)
        eng = "src/core/engine.cpp"
        self.assertIn("src/legacy/log.hpp", imports(off, eng), "regex picks the wrong log.hpp (trap)")
        self.assertIn("include/eng/util/log.hpp", imports(on, eng))
        self.assertNotIn("src/legacy/log.hpp", imports(on, eng))
        self.assertIn("include/eng/platform/linux.hpp", imports(on, eng), "macro-computed include")
        self.assertIn("compile_commands.json", on["graph_sources"]["cpp"])
        self.assertEqual({u["name"] for u in on["build_units"]}, {"core", "net", "app"})

    @unittest.skipUnless(fixtures.has("cargo"), "cargo")
    def test_rust_cross_crate(self):
        d = fixture("rust-ws")
        off, on = scan(d, mode="off"), scan(d)
        self.assertNotIn("crates/domain/src/orders.rs", imports(off, "crates/infra/src/repo.rs"))
        self.assertIn("crates/domain/src/orders.rs", imports(on, "crates/infra/src/repo.rs"))
        self.assertIn("crates/infra/src/repo.rs", imports(on, "crates/app/src/main.rs"))
        units = {u["name"]: u["deps"] for u in on["build_units"]}
        self.assertEqual(units["shop-infra"], ["shop-domain"])

    @unittest.skipUnless(fixtures.has("javac") and fixtures.has("jdeps"), "javac + jdeps")
    def test_java_jdeps(self):
        d = fixture("java-multi")
        self.assertTrue(fixtures.prepare_java(d))
        off, on = scan(d, mode="off"), scan(d)
        ctl = "web/src/main/java/com/acme/web/OrderController.java"
        money = "core/src/main/java/com/acme/core/Money.java"
        self.assertNotIn(money, imports(off, ctl), "inline qualified name invisible to regex (trap)")
        self.assertIn(money, imports(on, ctl))
        self.assertIn("jdeps", on["graph_sources"]["java"])
        self.assertNotIn("shop-parent", {u["name"] for u in on["build_units"]}, "aggregator POM is not a unit")

    def test_dotnet_project_graph_prunes_false_edge(self):
        d = fixture("dotnet-sln")
        off, on = scan(d, mode="off"), scan(d)
        self.assertIn("src/Shop.Api/OrderValidator.cs", imports(off, "src/Shop.Domain/Order.cs"), "namespace collision (trap)")
        self.assertNotIn("src/Shop.Api/OrderValidator.cs", imports(on, "src/Shop.Domain/Order.cs"))
        self.assertEqual(on["undeclared_cross_unit_edges_dropped"], 1)

    @unittest.skipUnless(fixtures.has("go"), "go toolchain")
    def test_go_build_tags(self):
        d = fixture("go-tags")
        off, on = scan(d, mode="off"), scan(d)
        self.assertIn("internal/store/store_windows.go", imports(off, "internal/orders/orders.go"))
        self.assertNotIn("internal/store/store_windows.go", imports(on, "internal/orders/orders.go"))
        self.assertIn("internal/store/store_windows.go", on["not_compiled"])

    @unittest.skipUnless(fixtures.has("php"), "php")
    def test_php_tokenizer_same_namespace(self):
        d = fixture("php-laravel")
        on = scan(d)
        self.assertIn("app/Billing/InvoiceNumbering.php", imports(on, "app/Billing/Checkout.php"))
        self.assertIn("PHP tokenizer", on["graph_sources"]["php"])

    def test_php_regex_fallback_same_namespace(self):
        d = fixture("php-laravel")
        off = scan(d, mode="off")
        self.assertIn("app/Billing/InvoiceNumbering.php", imports(off, "app/Billing/Checkout.php"), "new X() in same namespace")

    @unittest.skipUnless(fixtures.has("node"), "node")
    def test_ts_resolver_and_workspaces(self):
        d = fixture("ts-monorepo")
        os.makedirs(os.path.join(d, "node_modules/@acme"), exist_ok=True)
        os.symlink(os.path.join(d, "packages/core"), os.path.join(d, "node_modules/@acme/core"))
        on = scan(d, "--fetch-tools")
        self.assertIn("packages/core/src/shared/money.ts", imports(on, "packages/core/src/orders/order.ts"), "tsconfig extends + paths")
        self.assertIn("packages/core/src/orders/index.ts", imports(on, "packages/api/src/orders.controller.ts"), "package exports")


class DependencyInjection(unittest.TestCase):
    def test_dotnet_registration(self):
        on = scan(fixture("dotnet-sln"))
        b = [(x["abstraction"], x["implementation"]) for x in on["di"]["bindings"]]
        self.assertIn(("IOrderRepository", "SqlOrderRepository"), b)
        self.assertIn("src/Shop.Infrastructure/SqlOrderRepository.cs", runtime(on, "src/Shop.Api/OrdersController.cs"))

    def test_nest_providers_and_tokens(self):
        on = scan(fixture("ts-monorepo"), mode="off")
        b = {x["abstraction"]: x for x in on["di"]["bindings"]}
        self.assertEqual(b["OrderRepository"]["implementation"], "PrismaOrderRepository")
        self.assertEqual(b["MAILER"]["token"], "MAILER")
        self.assertIn("packages/api/src/mailer.ts", runtime(on, "packages/api/src/orders.controller.ts"))

    def test_laravel_container_and_facade(self):
        on = scan(fixture("php-laravel"), mode="off")
        kinds = {(x["abstraction"], x["implementation"], x["kind"]) for x in on["di"]["bindings"]}
        self.assertIn(("PaymentGateway", "StripeGateway", "explicit"), kinds)
        self.assertIn(("Numbering", "InvoiceNumbering", "facade"), kinds)
        self.assertIn("app/Billing/StripeGateway.php", runtime(on, "app/Billing/Checkout.php"))

    def test_spring_bean_and_single_implementation(self):
        on = scan(fixture("java-multi"), mode="off")
        kinds = {(x["abstraction"], x["implementation"], x["kind"]) for x in on["di"]["bindings"]}
        self.assertIn(("OrderRepository", "JdbcOrderRepository", "explicit"), kinds)
        self.assertIn(("Notifier", "EmailNotifier", "single-implementation"), kinds)


class Insights(unittest.TestCase):
    def test_knowledge_pseudonymised(self):
        d = fixture("go-tags")
        env = dict(os.environ, GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
        for i, who in enumerate(["alice@x", "bob@x", "carol@x", "alice@x", "alice@x"]):
            open(os.path.join(d, "internal/orders/orders.go"), "a").write(f"// {i}\n")
            subprocess.run(["git", "commit", "-qam", f"JIRA-{i % 2} change", f"--author=A <{who}>"], cwd=d, check=True, env=env)
        s = scan(d, mode="off")
        dumped = json.dumps({k: v for k, v in s.items() if k != "root"})
        self.assertNotIn("alice@x", dumped, "no real author identity in scan.json")
        self.assertTrue(os.path.exists(os.path.join(d, ".re-arch-off", "authors-map.json")))
        self.assertGreaterEqual(s["history"]["ticket_change_sets"], 2)

    def test_dependency_hygiene_and_systems(self):
        d = fixture("ts-monorepo")
        p = os.path.join(d, "packages/api/src/dates.ts")
        open(p, "w").write("import moment from 'moment'\nimport { format } from 'date-fns'\nexport const f = (d: Date) => format(d, 'y') + moment(d)\n")
        s = scan(d, mode="off")
        jobs = {x["job"] for x in s["dependency_hygiene"]["same_job"]}
        self.assertIn("dates", jobs)
        undeclared = {x["package"] for x in s["dependency_hygiene"]["undeclared"]}
        self.assertIn("moment", undeclared, "imported but declared nowhere")

    def test_duplicated_statement(self):
        d = fixture("ts-monorepo")
        open(os.path.join(d, "packages/api/src/a.ts"), "w").write("export function t(lines: any[]) {\n  let ht = 0\n  for (const l of lines) { ht += l.qty * l.unitPrice * 1.2 }\n  return ht\n}\n")
        open(os.path.join(d, "packages/core/src/b.ts"), "w").write("export const preview = (items: any[], show: boolean) => {\n  let ht = 0\n  for (const l of lines) { ht += l.qty * l.unitPrice * 1.2 }\n  return show ? ht : null\n}\n")
        s = scan(d, mode="off")
        self.assertTrue(any(x.get("statement", "").startswith("for (const l of lines)") for x in s["duplicates"]), "a formula re-typed in two otherwise different files")

    def test_routes(self):
        s = scan(fixture("ts-monorepo"), mode="off")
        self.assertTrue(any(r["path"] == "/orders" and r["method"] == "POST" for r in s["routes"]))


class Checker(unittest.TestCase):
    RULES = {"layers": {"domain": ["src/Shop.Domain/**"], "infra": ["src/Shop.Infrastructure/**"], "api": ["src/Shop.Api/**"]},
             "allow": {"domain": [], "infra": ["domain"], "api": ["domain", "infra"]},
             "forbid_external": {"domain": ["Microsoft"]},
             "forbid_patterns": {"api": ["new\\s+Sql\\w+Repository"]},
             "why": {"domain": "Domain stays framework-free"}}

    def setUp(self):
        self.d = fixture("dotnet-sln")
        self.rules = os.path.join(self.d, "rules.json")
        json.dump(self.RULES, open(self.rules, "w"))

    def test_clean_then_violation(self):
        self.assertEqual(run(CHECK, self.rules, "--root", self.d, check=False).returncode, 0)
        open(os.path.join(self.d, "src/Shop.Api/Bad.cs"), "w").write("namespace Shop.Api; class Bad { object r = new SqlOrderRepository(); }\n")
        r = run(CHECK, self.rules, "--root", self.d, check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("[pattern]", r.stdout)

    def test_baseline_ratchet_and_hook(self):
        audit = os.path.join(self.d, "src/Shop.Domain/Audit.cs")
        open(audit, "w").write("using Microsoft.Extensions.Logging;\nnamespace Shop;\npublic class Audit {}\n")
        base = os.path.join(self.d, "base.json")
        run(CHECK, self.rules, "--root", self.d, "--baseline-write", base)
        self.assertEqual(run(CHECK, self.rules, "--root", self.d, "--baseline", base, check=False).returncode, 0, "existing debt tolerated")
        open(os.path.join(self.d, "src/Shop.Domain/Cache.cs"), "w").write("using Microsoft.Extensions.Caching;\nnamespace Shop;\npublic class C {}\n")
        self.assertEqual(run(CHECK, self.rules, "--root", self.d, "--baseline", base, check=False).returncode, 1, "new debt fails")
        h = run(CHECK, self.rules, "--root", self.d, "--baseline", base, "--hook", check=False)
        self.assertEqual(h.returncode, 2)
        self.assertIn("Why: Domain stays framework-free", h.stderr)
        h2 = run(CHECK, self.rules, "--root", self.d, "--baseline", base, "--hook", check=False, stdin='{"stop_hook_active": true}')
        self.assertEqual(h2.returncode, 0, "no infinite Stop loop")
        os.remove(os.path.join(self.d, "src/Shop.Domain/Cache.cs"))
        os.remove(audit)
        run(CHECK, self.rules, "--root", self.d, "--baseline", base, "--baseline-update")
        self.assertEqual(json.load(open(base))["fingerprints"], {}, "baseline only shrinks")


    def test_secret_masked_and_frozen_folder(self):
        rules = dict(self.RULES)
        rules["forbid_patterns"] = {"api": [{"id": "R9", "pattern": "sk_live_[A-Za-z0-9]+", "why": "secrets come from the vault"}]}
        rules["forbid_new_files"] = [{"id": "R4", "glob": "src/Shop.Api/Legacy/**", "why": "new code goes to the modules"}]
        json.dump(rules, open(self.rules, "w"))
        open(os.path.join(self.d, "src/Shop.Api/Keys.cs"), "w").write('namespace Shop.Api; class K { string k = "sk_' + 'live_ABCDEFGHIJKLMNOPQRSTUV"; }\n')
        os.makedirs(os.path.join(self.d, "src/Shop.Api/Legacy"), exist_ok=True)
        open(os.path.join(self.d, "src/Shop.Api/Legacy/Old.cs"), "w").write("namespace Shop.Api; class Old {}\n")
        r = run(CHECK, self.rules, "--root", self.d, check=False)
        self.assertNotIn("ABCDEFGHIJKLMNOP", r.stdout, "secret never echoed")
        self.assertIn("[R9]", r.stdout)
        self.assertIn("secrets come from the vault", r.stdout)
        self.assertIn("[frozen-folder]", r.stdout)

    def test_hook_does_not_block_without_stdin(self):
        p = subprocess.Popen([sys.executable, CHECK, self.rules, "--root", self.d, "--hook"], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            p.wait(timeout=60)  # stdin left open and empty, as an agent shell does
        finally:
            p.kill()
        self.assertEqual(p.returncode, 0)


class DomainsClustering(unittest.TestCase):
    def test_cluster_runs_and_uses_runtime_edges(self):
        d = fixture("dotnet-sln")
        scan(d)
        run(CLUSTER, os.path.join(d, ".re-arch-auto"))
        c = json.load(open(os.path.join(d, ".re-arch-auto", "domains-candidates.json")))
        self.assertIn("runtime", c["edge_evidence"])


class Contract(unittest.TestCase):
    def setUp(self):
        self.d = os.path.join(TMP, "golden")
        self.archi = golden.build(self.d)

    def test_golden_is_valid(self):
        r = run(VALIDATE, self.archi, check=False)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("0 error(s)", r.stdout)

    def mutate(self, name, fn):
        data = copy.deepcopy(golden.ARCHI[name])
        fn(data)
        json.dump(data, open(os.path.join(self.archi, name), "w"))
        return run(VALIDATE, self.archi, check=False)

    def test_rejects_missing_light_option(self):
        def f(o):
            o["options"][0]["styles"] = ["hexagonal"]
            o["options"][0]["understanding_cost"] = "L"
            o["options"][1]["styles"] = ["clean"]
            o["options"][1]["understanding_cost"] = "L"
        r = self.mutate("options.json", f)
        self.assertIn("no light option", r.stdout)
        self.assertIn("one option with different vocabularies", r.stdout)

    def test_rejects_unscheduled_high_finding(self):
        r = self.mutate("plan.json", lambda p: p["phases"][1].update(findings=[]))
        self.assertIn("F1 (high) is neither in a phase", r.stdout)

    def test_rejects_bad_evidence_line(self):
        r = self.mutate("findings.json", lambda f: f["findings"][0]["evidence"][0].update(line=999))
        self.assertIn("beyond end of", r.stdout)

    def test_rejects_unknown_style_and_missing_do_nothing(self):
        r = self.mutate("options.json", lambda o: o["options"][1]["styles"].append("rich-domain-light"))
        self.assertIn("rich-domain-light", r.stdout)
        r = self.mutate("pitch.json", lambda p: p["options"].pop(0))
        self.assertIn("no 'do nothing' option", r.stdout)


class ReportAndTools(unittest.TestCase):
    def setUp(self):
        self.d = os.path.join(TMP, "golden-report")
        self.archi = golden.build(self.d)
        run(SCAN, self.d, "--out", self.archi, "--precise", "off", "--no-git")

    def test_render_and_markdown(self):
        run(RENDER, self.archi)
        html = open(os.path.join(self.archi, "report.html"), encoding="utf-8").read()
        for needle in ("Looks bad but is fine", "Quality scenarios", "Context view (C4)", "Questions for the maintainers", "How dependencies were resolved"):
            self.assertIn(needle, html)
        self.assertNotIn("—", html, "no em dash in generated labels")
        mm = open(os.path.join(self.archi, "architecture.md"), encoding="utf-8").read()
        self.assertIn("```mermaid", mm)
        run(PLAN_MD, self.archi)
        run(PITCH_MD, self.archi)
        self.assertIn("grep -rn", open(os.path.join(self.archi, "plan.md")).read())
        self.assertIn("Do nothing", open(os.path.join(self.archi, "pitch.md")).read())

    def test_render_on_phone(self):
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest("playwright")
        run(RENDER, self.archi)
        r = run(CHECK_RENDER, os.path.join(self.archi, "report.html"), check=False)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_reaudit_diff(self):
        old = os.path.join(TMP, "golden-old")
        if os.path.exists(old):
            shutil.rmtree(old)
        shutil.copytree(self.archi, old)
        f = json.load(open(os.path.join(self.archi, "findings.json")))
        f["findings"] = [x for x in f["findings"] if x["id"] != "F1"]
        f["findings"].append({"id": "F3", "title": "New issue", "category": "coupling", "severity": "low", "domains": [],
                              "evidence": [{"file": "src/lib/db.ts", "line": 1, "detail": "x"}], "impact_tech": "x", "impact_business": "x", "recommendation": "x"})
        json.dump(f, open(os.path.join(self.archi, "findings.json"), "w"))
        run(DIFF, "compare", old, self.archi)
        diff = json.load(open(os.path.join(self.archi, "diff.json")))
        self.assertEqual([x["id"] for x in diff["findings"]["resolved"]], ["F1"])
        self.assertEqual([x["id"] for x in diff["findings"]["new"]], ["F3"])
        run(RENDER, self.archi)
        self.assertIn("Progress since the previous audit", open(os.path.join(self.archi, "report.html")).read())


class OKFExport(unittest.TestCase):
    """to_okf.py writes an OKF v0.2 bundle: conformant, linked, without sensitive content."""

    def setUp(self):
        self.d = os.path.join(TMP, "golden-okf")
        self.archi = golden.build(self.d)
        self.okf = os.path.join(self.archi, "okf")
        f = json.load(open(os.path.join(self.archi, "findings.json")))
        f["findings"].append({"id": "F9", "title": "Stripe secret key committed", "category": "config-security", "severity": "critical",
                              "fix_size": "S", "domains": ["orders"], "evidence": [{"file": "src/lib/db.ts", "line": 1, "detail": "sk_" "live_abcdef123456"}],
                              "impact_tech": "x", "impact_business": "x", "recommendation": "rotate"})
        f["strengths"].append("Former key sk_" "live_zzzzzz999999 was rotated")
        json.dump(f, open(os.path.join(self.archi, "findings.json"), "w"))
        p = json.load(open(os.path.join(self.archi, "plan.json")))
        p["phases"].append({"id": "P2", "name": "Security", "status": "not started", "goal": "Close the unsigned webhook hole", "size": "S",
                            "findings": ["F9"], "domains": ["orders"], "steps": [], "exit_criteria": ["unsigned webhook call returns 400"]})
        json.dump(p, open(os.path.join(self.archi, "plan.json"), "w"))
        d = json.load(open(os.path.join(self.archi, "domains.json")))
        d["shared"][0]["role"] = "Prisma client, and the hard-coded API key"
        json.dump(d, open(os.path.join(self.archi, "domains.json"), "w"))

    def fm(self, rel):
        """Frontmatter as a dict with PyYAML, else the raw block (CI runners may not have PyYAML)."""
        txt = open(os.path.join(self.okf, rel), encoding="utf-8").read()
        self.assertTrue(txt.startswith("---\n"), rel)
        block = txt.split("---\n")[1]
        try:
            import yaml
        except ImportError:
            return block
        return yaml.safe_load(block)

    def test_bundle_conformant_and_clean(self):
        r = run(TO_OKF, self.archi)
        self.assertIn("1 security finding(s) left out", r.stdout)
        self.assertEqual(run(TO_OKF, "--check", self.okf).returncode, 0)
        for rel in ("system.md", "domains/orders.md", "domains/catalog.md", "external-systems/stripe.md",
                    "decisions/0001-target-architecture.md", "rules/r1.md", "plan/roadmap.md", "log.md"):
            self.assertTrue(os.path.exists(os.path.join(self.okf, rel)), rel)
        self.assertIn("okf_version", open(os.path.join(self.okf, "index.md")).read())
        self.assertNotIn("---", open(os.path.join(self.okf, "domains", "index.md")).read(), "sub-indexes carry no frontmatter")
        orders = open(os.path.join(self.okf, "domains", "orders.md")).read()
        for needle in ("(/domains/catalog.md)", "(/rules/r1.md)", "(/external-systems/stripe.md)", "**F1**", "[P1](/plan/roadmap.md)"):
            self.assertIn(needle, orders)
        everything = "".join(open(os.path.join(r_, f), encoding="utf-8").read() for r_, _, fs in os.walk(self.okf) for f in fs)
        self.assertNotIn("sk_live_", everything)
        self.assertNotIn("F9", everything)
        self.assertNotIn("unsigned", everything, "open security phases are described generically")
        self.assertNotIn("API key", everything, "where a secret lives is not exported")
        self.assertIn("Prisma client", everything)
        self.assertNotIn("A1", everything.replace("A1.", ""), "no knowledge-distribution pseudonyms")
        fm = self.fm("domains/orders.md")
        if isinstance(fm, dict):
            self.assertEqual(fm["type"], "Business Domain")
            self.assertEqual(fm["status"], "draft")
            self.assertNotIn("verified", fm, "an unvalidated map is unverified")
            self.assertTrue(str(fm["generated"]["by"]).startswith("re-arch/"))
        else:
            for needle in ('type: "Business Domain"', 'status: "draft"', 'generated: { by: "re-arch/'):
                self.assertIn(needle, fm)
            self.assertNotIn("verified:", fm, "an unvalidated map is unverified")

    def test_team_validation_and_log_history(self):
        run(TO_OKF, self.archi)
        d = json.load(open(os.path.join(self.archi, "domains.json")))
        d["validated_by_team"] = True
        json.dump(d, open(os.path.join(self.archi, "domains.json"), "w"))
        o = json.load(open(os.path.join(self.archi, "options.json")))
        o["decision"]["by"] = "team"
        json.dump(o, open(os.path.join(self.archi, "options.json"), "w"))
        m = json.load(open(os.path.join(self.archi, "meta.json")))
        m["date"] = "2026-12-01"
        json.dump(m, open(os.path.join(self.archi, "meta.json"), "w"))
        json.dump({"from": {"head": "a1"}, "to": {"head": "b2"}, "findings": {"resolved": [{"id": "F1"}], "new": [], "regressed": [], "improved": [], "persisting": []},
                   "metrics": [], "phases": [{"id": "P0", "status": "done"}, {"id": "P1", "status": "done"}]},
                  open(os.path.join(self.archi, "diff.json"), "w"))
        run(TO_OKF, self.archi)
        self.assertEqual(run(TO_OKF, "--check", self.okf).returncode, 0)
        log = open(os.path.join(self.okf, "log.md")).read()
        self.assertLess(log.index("## 2026-12-01"), log.index("## 2026-10-19"), "newest first, history kept")
        self.assertIn("1 resolved", log)
        dec = open(os.path.join(self.okf, "decisions", "0001-target-architecture.md")).read()
        self.assertIn("human:", dec)
        self.assertIn('adr_status: "accepted"', dec)

    def test_check_rejects_nonconformant(self):
        bad = os.path.join(TMP, "okf-bad")
        if os.path.exists(bad):
            shutil.rmtree(bad)
        os.makedirs(bad)
        open(os.path.join(bad, "x.md"), "w").write("---\ntitle: no type\n---\nbody\n")
        open(os.path.join(bad, "log.md"), "w").write("# Log\n\n## yesterday\n* x\n")
        r = run(TO_OKF, "--check", bad, check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no non-empty 'type'", r.stdout)
        self.assertIn("not YYYY-MM-DD", r.stdout)


class Packaging(unittest.TestCase):
    def test_vendored_scanner_in_sync(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sync.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_skill_frontmatter(self):
        for name in os.listdir(SK):
            text = open(os.path.join(SK, name, "SKILL.md"), encoding="utf-8").read()
            self.assertTrue(text.startswith("---\nname: " + name + "\n"), name)
            desc = text.split("\n")[2]
            self.assertTrue(desc.startswith("description: "), name)
            self.assertLessEqual(len(desc) - len("description: "), 1024, name)
            self.assertNotIn(": ", desc[len("description: "):], f"unquoted ': ' breaks the YAML frontmatter of {name}")
            self.assertNotIn("—", text, f"em dash in {name}/SKILL.md")


if __name__ == "__main__":
    try:
        prog = unittest.main(verbosity=2 if "-v" in sys.argv else 1, exit=False, warnings="ignore")
        ok = prog.result.wasSuccessful()
        if os.environ.get("GITHUB_ACTIONS"):
            # one annotation per failure, readable in the run summary and through the API
            for test, tb in prog.result.failures + prog.result.errors:
                tail = "\n".join(tb.strip().splitlines()[-12:])
                print(f"::error title={test.id()}::" + tail.replace("%", "%25").replace("\r", "").replace("\n", "%0A"))
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(0 if ok else 1)
