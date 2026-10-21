# Fitness functions per ecosystem

Starting points to adapt to the actual paths, packages and namespaces of the repo. Tool syntax changes between major versions: check the version present in the repo (lock files, build files) or the one you add, and run the config before handing it over.

## Contents
- Generic checker (all languages)
- JavaScript / TypeScript: dependency-cruiser, eslint-plugin-boundaries, Nx
- PHP: deptrac, Pest arch, PHPArkitect
- .NET: project references, NetArchTest, ArchUnitNET
- Java / Kotlin: ArchUnit, Spring Modulith
- Go: internal/, depguard, go-arch-lint
- Rust: workspace crates, cargo-deny
- C / C++: CMake targets, generic checker, include-what-you-use

---

## Generic checker (all languages)

`scripts/check_architecture.py` + `scripts/scan.py`, standard-library Python. Rules file:

```json
{
  "layers": {
    "web":    ["src/app/**"],
    "app":    ["src/modules/*/application/**"],
    "domain": ["src/modules/*/domain/**"],
    "infra":  ["src/modules/*/infrastructure/**"]
  },
  "allow": {"web": ["app", "domain"], "app": ["domain"], "infra": ["app", "domain"], "domain": []},
  "forbid_external": {"domain": ["@prisma/client", "next", "stripe"]},
  "public_api": {"src/modules/*": ["index.ts"]},
  "forbid_cycles": "modules",
  "max_file_loc": 600
}
```
`*` matches one path segment, `**` any depth. External names are what the scan reports: npm package names, Composer vendor (first namespace segment), Java/.NET first two namespace segments, Go module paths, Rust crate names, C++ angle-bracket include first segment.

Adoption with a frozen baseline (existing violations tolerated, new ones fail):
```bash
python3 tools/re-arch/check_architecture.py tools/re-arch/architecture-rules.json --root . --baseline-write tools/re-arch/re-arch-baseline.json   # once
python3 tools/re-arch/check_architecture.py tools/re-arch/architecture-rules.json --root . --baseline tools/re-arch/re-arch-baseline.json          # CI
python3 tools/re-arch/check_architecture.py tools/re-arch/architecture-rules.json --root . --baseline tools/re-arch/re-arch-baseline.json --baseline-update   # after fixes: shrink
```
Formats: `--format text|json|agent`; `--hook` for agent hooks (exit 2, stderr); `--changed-only` to report only files changed in git.

## JavaScript / TypeScript

**dependency-cruiser** (`npm i -D dependency-cruiser`, config `.dependency-cruiser.cjs`):
```js
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    { name: 'no-circular', severity: 'error', from: {}, to: { circular: true } },
    {
      name: 'domain-is-pure', severity: 'error',
      comment: 'Domain code must not depend on framework, transport or persistence',
      from: { path: '^src/modules/[^/]+/domain/' },
      to: { path: ['^src/app/', '^src/modules/[^/]+/(infrastructure|application)/', 'node_modules/(next|@prisma/client|stripe)/'] }
    },
    {
      name: 'modules-through-public-api', severity: 'error',
      comment: 'Other modules may only import a module through its index.ts',
      from: { path: '^src/modules/([^/]+)/' },
      to: { path: '^src/modules/[^/]+/', pathNot: ['^src/modules/$1/', '^src/modules/[^/]+/index\\.ts$'] }
    },
    {
      name: 'no-db-in-routes', severity: 'warn',
      comment: 'Route handlers call services, not the database client',
      from: { path: '^src/app/' },
      to: { path: ['^src/lib/db\\.ts$', 'node_modules/@prisma/client/'] }
    }
  ],
  options: { doNotFollow: { path: 'node_modules' }, tsConfig: { fileName: 'tsconfig.json' } }
};
```
Run: `npx depcruise src --config .dependency-cruiser.cjs`. It needs `typescript` installed to parse `.ts`/`.tsx` files; without it, it reports "0 modules cruised" and passes: check that the module count is above zero (and fail the CI job otherwise). Graph for the report or docs: `npx depcruise src --include-only '^src' --output-type dot | dot -T svg > deps.svg`. Freeze existing violations with a baseline (`npx depcruise src --config .dependency-cruiser.cjs --output-type baseline > .dependency-cruiser-known-violations.json`, then run with `--ignore-known`) rather than downgrading rules to `warn`: new violations then fail from day one.

**eslint-plugin-boundaries**: same idea inside ESLint (elements by pattern, `boundaries/element-types` rule), useful when the team prefers feedback in the editor.

**Nx**: tags on projects and `@nx/enforce-module-boundaries` with `depConstraints` in monorepos.

**Cycles only, quick**: `npx madge --circular --extensions ts,tsx src`.

## PHP

**deptrac** (`composer require --dev deptrac/deptrac`, file `deptrac.yaml`):
```yaml
deptrac:
  paths:
    - ./src
  layers:
    - name: Domain
      collectors:
        - type: directory
          value: src/.*/Domain/.*
    - name: Application
      collectors:
        - type: directory
          value: src/.*/Application/.*
    - name: Infrastructure
      collectors:
        - type: directory
          value: src/.*/Infrastructure/.*
    - name: Http
      collectors:
        - type: directory
          value: src/.*/Http/.*
  ruleset:
    Domain: ~
    Application:
      - Domain
    Infrastructure:
      - Domain
      - Application
    Http:
      - Application
      - Domain
```
Run: `vendor/bin/deptrac analyse`. Use a baseline (`--formatter=baseline`) to accept existing violations and block new ones. Laravel apps: paths under `app/`.

**Pest arch tests** (Laravel teams often already use Pest). For facades in the generic checker's `forbid_patterns`, anchor names (`(?<![\w\\])Auth::`) so `JWTAuth::` does not match:
```php
arch('domain is framework-free')
    ->expect('App\Domain')
    ->not->toUse(['Illuminate', 'App\Http']);

arch('controllers do not use the query builder directly')
    ->expect('App\Http\Controllers')
    ->not->toUse('Illuminate\Support\Facades\DB');

arch('no debugging statements')
    ->expect(['dd', 'dump', 'var_dump'])
    ->not->toBeUsed();
```

**PHPArkitect**: rule-based alternative with a fluent PHP config.

## .NET (C#)

**Project references** are the first enforcement: `Domain.csproj` references nothing; `Application` references `Domain`; `Infrastructure` references both; `Api` references `Application` and `Infrastructure` (composition root). The compiler then forbids the wrong direction.

**NetArchTest.Rules** (xUnit test project):
```csharp
using NetArchTest.Rules;
using Xunit;

public class ArchitectureTests
{
    [Fact]
    public void Domain_does_not_depend_on_infrastructure_or_ef()
    {
        var result = Types.InAssembly(typeof(Shop.Domain.Order).Assembly)
            .That().ResideInNamespace("Shop.Domain")
            .ShouldNot().HaveDependencyOnAny("Shop.Infrastructure", "Shop.Api", "Microsoft.EntityFrameworkCore")
            .GetResult();
        Assert.True(result.IsSuccessful, string.Join(", ", result.FailingTypeNames ?? []));
    }

    [Fact]
    public void Controllers_do_not_use_DbContext()
    {
        var result = Types.InAssembly(typeof(Program).Assembly)
            .That().HaveNameEndingWith("Controller")
            .ShouldNot().HaveDependencyOn("Microsoft.EntityFrameworkCore")
            .GetResult();
        Assert.True(result.IsSuccessful);
    }
}
```
(`[]` collection expression needs C# 12; use `new string[0]` before.)

**ArchUnitNET**: port of ArchUnit with a richer API (layers, slices, cycles).

## Java / Kotlin

**ArchUnit** (JUnit 5, `com.tngtech.archunit:archunit-junit5`):
```java
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.Architectures.layeredArchitecture;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

@AnalyzeClasses(packages = "com.acme.shop")
class ArchitectureTest {

    @ArchTest
    static final ArchRule layers = layeredArchitecture().consideringOnlyDependenciesInLayers()
        .layer("Web").definedBy("..web..")
        .layer("Application").definedBy("..application..")
        .layer("Domain").definedBy("..domain..")
        .layer("Persistence").definedBy("..persistence..")
        .whereLayer("Web").mayNotBeAccessedByAnyLayer()
        .whereLayer("Application").mayOnlyBeAccessedByLayers("Web")
        .whereLayer("Persistence").mayNotBeAccessedByAnyLayer()
        .whereLayer("Domain").mayOnlyBeAccessedByLayers("Application", "Persistence", "Web");

    @ArchTest
    static final ArchRule domainIsPure = noClasses().that().resideInAPackage("..domain..")
        .should().dependOnClassesThat().resideInAnyPackage("org.springframework..", "jakarta.persistence..");

    @ArchTest
    static final ArchRule featuresFreeOfCycles = slices().matching("com.acme.shop.(*)..").should().beFreeOfCycles();
}
```
Existing violations: `FreezingArchRule.freeze(rule)` records them and fails only on new ones.

**Spring Modulith** (modular monolith on Spring Boot): top-level packages under the application package are modules; internals in sub-packages are private.
```java
@Test
void verifiesModularStructure() {
    ApplicationModules.of(ShopApplication.class).verify();
}
```

## Go

- **`internal/`**: a package under `a/internal/` can only be imported from `a/...`. Put each domain's private code under its own `internal/` (`internal/orders/internal/pricing`), enforced by the compiler.
- **depguard** via golangci-lint (v1 config shown; v2 moves settings under `linters.settings`):
```yaml
linters:
  enable: [depguard]
linters-settings:
  depguard:
    rules:
      domain:
        files: ["**/internal/*/domain/**"]
        deny:
          - pkg: "database/sql"
            desc: "domain code must not touch the database"
          - pkg: "net/http"
            desc: "domain code must not depend on transport"
```
- **go-arch-lint** (`.go-arch-lint.yml`): components by path and allowed dependencies between them; check the schema of the installed version (`go-arch-lint check`).
- Cycles: impossible between packages (compile error), so watch package size instead (`max_file_loc` and module LOC in the generic checker).

## Rust

- **Workspace crates** as boundaries:
```toml
# Cargo.toml (workspace root)
[workspace]
members = ["crates/domain", "crates/application", "crates/adapter-db", "crates/adapter-http", "crates/server"]
resolver = "2"
```
`crates/domain/Cargo.toml` lists no I/O crate (no sqlx, axum, reqwest): the compiler then rejects any such use in the domain. `server` is the composition root.
- **cargo-deny** to restrict which crate may pull an infrastructure dependency (`deny.toml`):
```toml
[bans]
deny = [
  { name = "sqlx", wrappers = ["adapter-db"] },
  { name = "axum", wrappers = ["adapter-http", "server"] },
]
```
Run: `cargo deny check bans`.
- Inside a crate: private modules and `pub(crate)`; `cargo modules structure` to inspect.

## C / C++

- **CMake targets** as boundaries:
```cmake
add_library(domain STATIC src/domain/order.cpp src/domain/pricing.cpp)
target_include_directories(domain PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include/domain)
target_compile_features(domain PUBLIC cxx_std_20)
# domain links nothing infrastructural

add_library(infra_db STATIC src/infra/db/order_repository.cpp)
target_link_libraries(infra_db PRIVATE domain SQLite::SQLite3)

add_executable(app src/main.cpp)
target_link_libraries(app PRIVATE domain infra_db)
```
A domain source including a database header then fails to compile because the include path is not visible to the `domain` target.
- **Generic checker** on includes (layers by folder, `forbid_external` with angle-bracket include roots such as `sqlite3.h`, `QtNetwork`, `boost`).
- **include-what-you-use** and clang-tidy (`misc-include-cleaner`) to keep headers honest; pimpl and forward declarations to reduce coupling.
