"""
Golden audit: a tiny repository plus a complete, valid .re-arch/ written by hand.
Used to test validate.py, render.py, check_render.py, diff_rearch.py and the
markdown generators, and as a reference example of the data contract.
"""
import json
import os
import shutil

REPO = {
    "package.json": '{"name":"tinyshop","dependencies":{"next":"14.2.3","@prisma/client":"5.14.0","stripe":"15.0.0"}}\n',
    "src/app/api/orders/route.ts": "import { prisma } from '@/lib/db'\nimport Stripe from 'stripe'\nexport async function POST(req: Request) {\n  const b = await req.json()\n  let total = 0\n  for (const i of b.items) total += i.price * i.qty\n  if (total > 100) total = total * 0.95\n  const o = await prisma.order.create({ data: { total } })\n  return Response.json(o)\n}\n",
    "src/app/checkout/page.tsx": "'use client'\nexport default function Checkout({ items }: any) {\n  let total = 0\n  for (const i of items) total += i.price * i.qty\n  if (total > 100) total = total * 0.95\n  return (<p>{total}</p>)\n}\n",
    "src/app/api/products/route.ts": "import { prisma } from '@/lib/db'\nexport async function GET() { return Response.json(await prisma.product.findMany()) }\n",
    "src/lib/db.ts": "import { PrismaClient } from '@prisma/client'\nexport const prisma = new PrismaClient()\n",
}

ARCHI = {
    "meta.json": {"project": "tinyshop", "date": "2026-10-19", "lang": "en", "scope": "whole repository", "audience": ["tech", "management"],
                  "team": "2 developers", "quality_drivers": ["Change pricing rules safely"], "mode": "full",
                  "assumptions": ["Nobody available: option O2 retained by default"]},
    "domains.json": {
        "method": "imports + co-change, reviewed in the code", "validated_by_team": False,
        "domains": [
            {"id": "orders", "name": "Orders", "kind": "core", "description": "Cart total, discount, order creation",
             "confidence": "high", "confidence_reason": "own entity, co-change between API and page",
             "files": ["src/app/api/orders/route.ts", "src/app/checkout/page.tsx"], "entities": ["Order"], "loc": 16,
             "depends_on": [{"id": "catalog", "kind": "shared-entity", "strength": 1, "note": "reads product prices"}]},
            {"id": "catalog", "name": "Catalog", "kind": "supporting", "description": "Product listing",
             "confidence": "medium", "confidence_reason": "single route and entity",
             "files": ["src/app/api/products/route.ts"], "entities": ["Product"], "loc": 2, "depends_on": []},
        ],
        "external_systems": [{"name": "Relational database", "kind": "database", "used_by": ["orders", "catalog"]},
                             {"name": "Stripe", "kind": "payment", "used_by": ["orders"]}],
        "shared": [{"path": "src/lib/db.ts", "role": "Prisma client"}],
        "fuzzy_zones": [{"title": "Discount rule", "detail": "computed in the API and in the page", "files": ["src/app/api/orders/route.ts", "src/app/checkout/page.tsx"]}],
    },
    "findings.json": {
        "metrics": {"prod_loc": 18, "test_ratio": 0.0, "module_cycles": 0, "mixed_files": 2},
        "strengths": ["One Prisma client shared by all routes"],
        "non_findings": [{"title": "Catalog route calls Prisma directly", "why": "read-only CRUD with no rule: a service layer would add nothing", "files": ["src/app/api/products/route.ts"]}],
        "open_questions": ["Is the 5% discount above 100 a permanent rule?"],
        "findings": [
            {"id": "F1", "title": "Discount rule duplicated between the order API and the checkout page", "category": "duplication",
             "severity": "high", "fix_size": "S", "debt_intent": "inadvertent-reckless", "domains": ["orders"],
             "evidence": [{"file": "src/app/api/orders/route.ts", "line": 7, "detail": "5% above 100"},
                          {"file": "src/app/checkout/page.tsx", "line": 5, "detail": "same rule client side"}],
             "impact_tech": "Two places to change, no test", "impact_business": "Displayed and charged totals can diverge",
             "recommendation": "One pure pricing function used by both, with unit tests"},
            {"id": "F2", "title": "No tests at all", "category": "testing", "severity": "medium", "fix_size": "M", "domains": ["orders"],
             "evidence": [{"file": "src", "detail": "no test file in the repository"}],
             "impact_tech": "Refactoring cannot be checked", "impact_business": "Regressions reach customers",
             "recommendation": "Characterisation tests on the order flow first"},
        ],
    },
    "options.json": {
        "context": {"domain_complexity": "One small core domain", "team": "2 developers", "constraints": ["Next.js stays"]},
        "quality_scenarios": [{"id": "Q1", "driver": "Change pricing safely", "scenario": "A discount change ships in one PR with a unit test", "assumed": False}],
        "options": [
            {"id": "O1", "name": "Targeted fixes in place", "styles": ["targeted"], "scope": "global", "summary": "Share the rule, add tests",
             "understanding_cost": "S", "understanding_detail": {"concepts": [], "indirections": "unchanged"}, "implementation_size": "S",
             "scenario_fit": {"Q1": "+"}, "tradeoffs": "No structure for the next rules", "benefits": ["Fast"], "drawbacks": ["Next rule lands anywhere"],
             "signals": ["F1", "tiny codebase"], "addresses": ["F1", "F2"], "does_not_address": [], "recommended": False, "why": ""},
            {"id": "O2", "name": "Server module for orders", "styles": ["layered", "feature-folders"], "scope": "global", "summary": "src/server/orders with pricing and service",
             "understanding_cost": "M", "understanding_detail": {"concepts": ["service", "pure function"], "indirections": "route -> service -> prisma"},
             "implementation_size": "S", "scenario_fit": {"Q1": "+"}, "tradeoffs": "One more folder", "benefits": ["Clear home for rules"], "drawbacks": ["Slightly more files"],
             "signals": ["F1", "orders is core"], "addresses": ["F1", "F2"], "does_not_address": [], "recommended": True, "why": "Cheap and gives rules a home"},
        ],
        "prerequisites": [],
        "rejected": [{"style": "Hexagonal", "why": "one database, one entry point, no adapter to swap"}],
        "opportunities": [],
        "decision": {"chosen": "O2", "by": "assumed", "note": "awaiting validation"},
    },
    "plan.json": {
        "target": "O2", "sequencing_rationale": "Tests first, then the shared rule",
        "assumptions": ["features keep shipping"], "out_of_scope": [],
        "phases": [
            {"id": "P0", "name": "Safety net", "status": "done", "goal": "Characterisation tests on POST /api/orders",
             "size": "S", "size_rationale": "one route, no contract change", "domains": ["orders"], "findings": ["F2"], "depends_on": [],
             "steps": [{"do": "Add characterisation tests for POST /api/orders", "verify": "npm test"}],
             "exit_criteria": ["Tests green in CI"], "rollback": "tests only", "risks": [], "stop_point": True},
            {"id": "P1", "name": "Share the pricing rule", "status": "not started", "goal": "One computeTotal used by API and page",
             "size": "S", "size_rationale": "one module, tested", "domains": ["orders"], "findings": ["F1"], "depends_on": ["P0"],
             "steps": [{"do": "Create src/server/orders/pricing.ts", "moves": [{"from": "src/app/api/orders/route.ts#total", "to": "src/server/orders/pricing.ts#computeTotal"}],
                        "verify": "grep -rn '0.95' src/app  # must print nothing"}],
             "exit_criteria": ["Rule exists once", "Unit tests on computeTotal"], "rollback": "revert the PR", "risks": [], "stop_point": True},
        ],
    },
    "pitch.json": {
        "headline": "Spend a few days making pricing safe", "situation": "Small shop app; one rule is written twice.",
        "risks": [{"risk": "Wrong totals", "consequence": "Refunds and disputes", "likelihood": "medium", "evidence": "F1"}],
        "options": [{"name": "Do nothing", "size": "-", "gain": "No effort", "risk": "Totals drift"},
                    {"name": "Option O2", "size": "S", "gain": "One rule, tested", "risk": "None significant"}],
        "recommendation": "O2", "investment": {"size": "S", "capacity": "one developer for a few days (range to calibrate)", "assumptions": ["P0 and P1, both S"]},
        "milestones": [{"when": "end of P1", "what": "Rule exists once", "indicator": "no pricing bug reported"}],
        "kpis": [{"name": "Pricing bugs", "baseline": "to measure", "target": "0"}],
        "decision_requested": "Approve two small phases", "glossary": [],
    },
    "academy.json": {
        "modules": [{"id": "A1", "title": "Characterisation tests", "audience": "all", "level": "foundation", "duration": "1h",
                     "why_here": "F2", "findings": ["F2"], "concepts": ["golden master"], "file": "academy/01-characterisation-tests.md"}],
        "path": [{"step": 1, "modules": ["A1"], "when": "before P0"}],
        "reading": [{"title": "Working Effectively with Legacy Code", "author": "Michael Feathers", "why": "seams"}],
    },
    "guardrails.json": {"target": "O2", "adoption": "frozen baseline",
                        "rules": [{"id": "R1", "rule": "Pricing lives in src/server/orders", "prevents": ["F1"], "enforced_by": "generic checker forbid_patterns", "mode": "baseline", "current_violations": 2, "tested": "generic checker run"}],
                        "hooks": [], "files": [{"path": "guardrails/AGENTS.md", "purpose": "rules for agents"}]},
}
EXTRA = {"academy/01-characterisation-tests.md": "# A1. Characterisation tests\n"}


def build(dest, with_git=True):
    if os.path.exists(dest):
        shutil.rmtree(dest)
    for rel, content in REPO.items():
        p = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(content)
    archi = os.path.join(dest, ".re-arch")
    os.makedirs(archi, exist_ok=True)
    for name, data in ARCHI.items():
        json.dump(data, open(os.path.join(archi, name), "w", encoding="utf-8"), indent=1)
    for rel, content in EXTRA.items():
        p = os.path.join(archi, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(content)
    return archi
