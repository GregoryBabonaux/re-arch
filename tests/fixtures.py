"""
Fixture repositories for the re-arch test-suite.

Each fixture is a dict {relative path: content} plus an optional scripted git
history. Every fixture plants traps the regex layer gets wrong on purpose, so
the tests prove what the precise layer and the DI extraction add.
"""
import os
import shutil
import subprocess

FIXTURES = {}

# ---------------------------------------------------------------------------
# C++ / CMake: macro-computed include, include-dir collision, angle-bracket internal headers
# ---------------------------------------------------------------------------
FIXTURES["cpp-cmake"] = {
    "CMakeLists.txt": """cmake_minimum_required(VERSION 3.16)
project(eng CXX)
set(CMAKE_CXX_STANDARD 17)
add_library(core src/core/engine.cpp)
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/include/eng/util)
target_compile_definitions(core PRIVATE ENG_PLATFORM_HEADER="eng/platform/linux.hpp")
add_library(net src/net/client.cpp)
target_include_directories(net PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(net PUBLIC core)
add_executable(app src/main.cpp)
target_link_libraries(app PRIVATE net)
""",
    "include/eng/core/engine.hpp": "#pragma once\nnamespace eng { int run(); }\n",
    "include/eng/net/client.hpp": "#pragma once\n#include \"eng/core/engine.hpp\"\nnamespace eng { int send(); }\n",
    "include/eng/platform/linux.hpp": "#pragma once\nnamespace eng { inline int platform() { return 1; } }\n",
    "include/eng/util/log.hpp": "#pragma once\nnamespace eng { inline void log() {} }\n",
    "src/legacy/log.hpp": "#pragma once\n// legacy logger with the same file name: must NOT be picked\nnamespace legacy { inline void log() {} }\n",
    "src/legacy/old.cpp": "#include \"log.hpp\"\nint old() { legacy::log(); return 0; }\n",
    "src/core/engine.cpp": "#include \"eng/core/engine.hpp\"\n#include ENG_PLATFORM_HEADER\n#include \"log.hpp\"\n#include <vector>\nnamespace eng { int run() { log(); return platform(); } }\n",
    "src/net/client.cpp": "#include <eng/net/client.hpp>\nnamespace eng { int send() { return run(); } }\n",
    "src/main.cpp": "#include \"eng/net/client.hpp\"\nint main() { return eng::send(); }\n",
}

# ---------------------------------------------------------------------------
# Rust workspace: cross-crate `use`, nested modules, path dependencies
# ---------------------------------------------------------------------------
FIXTURES["rust-ws"] = {
    "Cargo.toml": "[workspace]\nmembers = [\"crates/domain\", \"crates/infra\", \"crates/app\"]\nresolver = \"2\"\n",
    "crates/domain/Cargo.toml": "[package]\nname = \"shop-domain\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[lib]\nname = \"shop_domain\"\npath = \"src/lib.rs\"\n",
    "crates/domain/src/lib.rs": "pub mod orders;\npub mod money;\n",
    "crates/domain/src/orders.rs": "use crate::money::Money;\npub struct Order { pub total: Money }\npub trait OrderRepository { fn save(&self, o: &Order); }\n",
    "crates/domain/src/money.rs": "#[derive(Clone, Copy)]\npub struct Money(pub i64);\n",
    "crates/infra/Cargo.toml": "[package]\nname = \"shop-infra\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[dependencies]\nshop-domain = { path = \"../domain\" }\n",
    "crates/infra/src/lib.rs": "pub mod repo;\n",
    "crates/infra/src/repo.rs": "use shop_domain::orders::{Order, OrderRepository};\npub struct SqlRepo;\nimpl OrderRepository for SqlRepo { fn save(&self, _o: &Order) {} }\n",
    "crates/app/Cargo.toml": "[package]\nname = \"shop-app\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[dependencies]\nshop-domain = { path = \"../domain\" }\nshop-infra = { path = \"../infra\" }\n",
    "crates/app/src/main.rs": "use shop_infra::repo::SqlRepo;\nuse shop_domain::orders::OrderRepository;\nfn main() { let r = SqlRepo; let _ = &r as &dyn OrderRepository; }\n",
}

# ---------------------------------------------------------------------------
# Java multi-module Maven: inline fully-qualified reference, @Bean wiring, single implementation
# ---------------------------------------------------------------------------
FIXTURES["java-multi"] = {
    "pom.xml": """<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>com.acme</groupId><artifactId>shop-parent</artifactId><version>1</version><packaging>pom</packaging>
<modules><module>core</module><module>web</module></modules></project>""",
    "core/pom.xml": """<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<parent><groupId>com.acme</groupId><artifactId>shop-parent</artifactId><version>1</version></parent><artifactId>core</artifactId></project>""",
    "web/pom.xml": """<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<parent><groupId>com.acme</groupId><artifactId>shop-parent</artifactId><version>1</version></parent><artifactId>web</artifactId>
<dependencies><dependency><groupId>com.acme</groupId><artifactId>core</artifactId><version>1</version></dependency></dependencies></project>""",
    "core/src/main/java/com/acme/core/Bean.java": "package com.acme.core;\npublic @interface Bean {}\n",
    "core/src/main/java/com/acme/core/Money.java": "package com.acme.core;\npublic final class Money { public static Money of(long c) { return new Money(); } }\n",
    "core/src/main/java/com/acme/core/Order.java": "package com.acme.core;\npublic class Order { public Money total; }\n",
    "core/src/main/java/com/acme/core/OrderRepository.java": "package com.acme.core;\npublic interface OrderRepository { void save(Order o); }\n",
    "core/src/main/java/com/acme/core/infra/JdbcOrderRepository.java": "package com.acme.core.infra;\nimport com.acme.core.Order;\nimport com.acme.core.OrderRepository;\npublic class JdbcOrderRepository implements OrderRepository { public void save(Order o) {} }\n",
    "core/src/main/java/com/acme/core/Notifier.java": "package com.acme.core;\npublic interface Notifier { void send(String m); }\n",
    "core/src/main/java/com/acme/core/infra/EmailNotifier.java": "package com.acme.core.infra;\nimport com.acme.core.Notifier;\npublic class EmailNotifier implements Notifier { public void send(String m) {} }\n",
    "web/src/main/java/com/acme/web/AppConfig.java": """package com.acme.web;
import com.acme.core.Bean;
import com.acme.core.OrderRepository;
import com.acme.core.infra.JdbcOrderRepository;
public class AppConfig {
    @Bean
    public OrderRepository orderRepository() {
        return new JdbcOrderRepository();
    }
}
""",
    "web/src/main/java/com/acme/web/OrderController.java": """package com.acme.web;
import com.acme.core.Order;
import com.acme.core.OrderRepository;
import com.acme.core.Notifier;
public class OrderController {
    private final OrderRepository repo;
    private final Notifier notifier;
    public OrderController(OrderRepository repo, Notifier notifier) { this.repo = repo; this.notifier = notifier; }
    public void create() {
        Order o = new Order();
        o.total = com.acme.core.Money.of(100);
        repo.save(o);
        notifier.send("created");
    }
}
""",
}

# ---------------------------------------------------------------------------
# .NET multi-project: lazy shared namespace (false positive the project graph must drop), DI
# ---------------------------------------------------------------------------
FIXTURES["dotnet-sln"] = {
    "src/Shop.Domain/Shop.Domain.csproj": '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>\n',
    "src/Shop.Infrastructure/Shop.Infrastructure.csproj": '<Project Sdk="Microsoft.NET.Sdk"><ItemGroup><ProjectReference Include="..\\Shop.Domain\\Shop.Domain.csproj" /><PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" /></ItemGroup></Project>\n',
    "src/Shop.Api/Shop.Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"><ItemGroup><ProjectReference Include="..\\Shop.Domain\\Shop.Domain.csproj" /><ProjectReference Include="..\\Shop.Infrastructure\\Shop.Infrastructure.csproj" /></ItemGroup></Project>\n',
    "src/Shop.Domain/Order.cs": "namespace Shop;\npublic class Order\n{\n    public decimal Total { get; set; }\n    // validated by OrderValidator in the API layer\n    public string Describe() => \"OrderValidator ok\";\n}\n",
    "src/Shop.Domain/IOrderRepository.cs": "namespace Shop;\npublic interface IOrderRepository { void Save(Order o); }\n",
    "src/Shop.Infrastructure/SqlOrderRepository.cs": "using Microsoft.EntityFrameworkCore;\nnamespace Shop.Infrastructure;\npublic class SqlOrderRepository : IOrderRepository\n{\n    public void Save(Shop.Order o) { }\n}\n",
    "src/Shop.Api/OrderValidator.cs": "namespace Shop;\npublic class OrderValidator { public bool Ok(Order o) => o.Total > 0; }\n",
    "src/Shop.Api/OrdersController.cs": "using Shop;\nnamespace Shop.Api;\npublic class OrdersController\n{\n    private readonly IOrderRepository _repo;\n    public OrdersController(IOrderRepository repo) { _repo = repo; }\n    public void Post(Order o) { if (new OrderValidator().Ok(o)) _repo.Save(o); }\n}\n",
    "src/Shop.Api/Program.cs": "using Shop;\nusing Shop.Infrastructure;\nvar builder = WebApplication.CreateBuilder(args);\nbuilder.Services.AddScoped<IOrderRepository, SqlOrderRepository>();\nvar app = builder.Build();\napp.Run();\n",
}

# ---------------------------------------------------------------------------
# Go: build tags, multi-package module
# ---------------------------------------------------------------------------
FIXTURES["go-tags"] = {
    "go.mod": "module example.com/shop\n\ngo 1.21\n",
    "cmd/api/main.go": "package main\n\nimport \"example.com/shop/internal/orders\"\n\nfunc main() { orders.Place() }\n",
    "internal/orders/orders.go": "package orders\n\nimport \"example.com/shop/internal/store\"\n\nfunc Place() { store.Save() }\n",
    "internal/store/store_linux.go": "//go:build linux\n\npackage store\n\nimport \"example.com/shop/internal/pg\"\n\nfunc Save() { pg.Exec() }\n",
    "internal/store/store_windows.go": "//go:build windows\n\npackage store\n\nimport \"example.com/shop/internal/mssql\"\n\nfunc Save() { mssql.Exec() }\n",
    "internal/pg/pg.go": "package pg\n\nfunc Exec() {}\n",
    "internal/mssql/mssql.go": "package mssql\n\nfunc Exec() {}\n",
}

# ---------------------------------------------------------------------------
# TS monorepo: tsconfig "extends" paths, package "exports", NestJS providers with tokens
# ---------------------------------------------------------------------------
FIXTURES["ts-monorepo"] = {
    "package.json": '{"name":"acme","private":true,"workspaces":["packages/*"]}\n',
    "tsconfig.base.json": '{"compilerOptions":{"baseUrl":".","module":"ESNext","moduleResolution":"Bundler","paths":{"#shared/*":["packages/core/src/shared/*"]}}}\n',
    "packages/core/package.json": '{"name":"@acme/core","version":"1.0.0","exports":{"./orders":"./src/orders/index.ts"}}\n',
    "packages/core/tsconfig.json": '{"extends":"../../tsconfig.base.json"}\n',
    "packages/core/src/orders/index.ts": "export { OrderRepository } from './order-repository';\nexport { Order } from './order';\n",
    "packages/core/src/orders/order.ts": "import { money } from '#shared/money';\nexport class Order { total = money(0); }\n",
    "packages/core/src/orders/order-repository.ts": "import { Order } from './order';\nexport abstract class OrderRepository { abstract save(o: Order): Promise<void>; }\n",
    "packages/core/src/shared/money.ts": "export const money = (n: number) => n;\n",
    "packages/api/package.json": '{"name":"@acme/api","version":"1.0.0","dependencies":{"@nestjs/common":"10.0.0"}}\n',
    "packages/api/tsconfig.json": '{"extends":"../../tsconfig.base.json"}\n',
    "packages/api/src/prisma-order-repository.ts": "import { Order, OrderRepository } from '@acme/core/orders';\nexport class PrismaOrderRepository extends OrderRepository { async save(o: Order) {} }\n",
    "packages/api/src/mailer.ts": "export class SmtpMailer { send(to: string) {} }\n",
    "packages/api/src/app.module.ts": """import { Module } from '@nestjs/common';
import { OrderRepository } from '@acme/core/orders';
import { PrismaOrderRepository } from './prisma-order-repository';
import { SmtpMailer } from './mailer';
import { OrdersController } from './orders.controller';
@Module({
  controllers: [OrdersController],
  providers: [
    { provide: OrderRepository, useClass: PrismaOrderRepository },
    { provide: 'MAILER', useClass: SmtpMailer },
  ],
})
export class AppModule {}
""",
    "packages/api/src/orders.controller.ts": """import { Controller, Inject, Post } from '@nestjs/common';
import { Order, OrderRepository } from '@acme/core/orders';
@Controller('orders')
export class OrdersController {
  constructor(private readonly repo: OrderRepository, @Inject('MAILER') private readonly mailer: any) {}
  @Post() async create() { await this.repo.save(new Order()); this.mailer.send('x'); }
}
""",
}

# ---------------------------------------------------------------------------
# PHP / Laravel-like: same-namespace references, ::class strings, container bindings, facade
# ---------------------------------------------------------------------------
FIXTURES["php-laravel"] = {
    "composer.json": '{"autoload":{"psr-4":{"App\\\\":"app/"}}}\n',
    "app/Billing/PaymentGateway.php": "<?php\nnamespace App\\Billing;\ninterface PaymentGateway { public function charge(int $cents): string; }\n",
    "app/Billing/StripeGateway.php": "<?php\nnamespace App\\Billing;\nclass StripeGateway implements PaymentGateway { public function charge(int $cents): string { return 'ok'; } }\n",
    "app/Billing/InvoiceNumbering.php": "<?php\nnamespace App\\Billing;\nclass InvoiceNumbering { public function next(): string { return 'F-1'; } }\n",
    "app/Billing/Checkout.php": "<?php\nnamespace App\\Billing;\nclass Checkout\n{\n    public function __construct(private PaymentGateway $gateway) {}\n    public function run(): string { $n = (new InvoiceNumbering())->next(); return $this->gateway->charge(100) . $n; }\n}\n",
    "app/Providers/AppServiceProvider.php": "<?php\nnamespace App\\Providers;\nuse App\\Billing\\PaymentGateway;\nuse App\\Billing\\StripeGateway;\nclass AppServiceProvider\n{\n    public function register(): void\n    {\n        $this->app->singleton(PaymentGateway::class, StripeGateway::class);\n        $this->app->bind('numbering', fn () => new \\App\\Billing\\InvoiceNumbering());\n    }\n}\n",
    "app/Facades/Numbering.php": "<?php\nnamespace App\\Facades;\nclass Numbering extends Facade\n{\n    protected static function getFacadeAccessor() { return 'numbering'; }\n}\n",
    "app/Http/Controllers/CheckoutController.php": "<?php\nnamespace App\\Http\\Controllers;\nuse App\\Facades\\Numbering;\nclass CheckoutController\n{\n    public function store(\\App\\Billing\\Checkout $checkout) { return $checkout->run() . Numbering::next(); }\n}\n",
}


def build(name, dest):
    """Write fixture `name` into `dest` and create its git repository."""
    files = FIXTURES[name]
    if os.path.exists(dest):
        shutil.rmtree(dest)
    for rel, content in files.items():
        p = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=dest, check=True, env=env)
    return dest


def has(tool):
    return shutil.which(tool) is not None


def prepare_cpp(dest):
    """Generate compile_commands.json with CMake (our own fixture, safe to configure)."""
    if not has("cmake"):
        return False
    b = os.path.join(dest, "build")
    r = subprocess.run(["cmake", "-S", dest, "-B", b, "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"], capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(os.path.join(b, "compile_commands.json"))


def prepare_java(dest):
    """Compile both modules with javac into target/classes (what `mvn compile` would produce)."""
    if not has("javac"):
        return False
    core_src = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(dest, "core/src")) for f in fs if f.endswith(".java")]
    web_src = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(dest, "web/src")) for f in fs if f.endswith(".java")]
    core_out, web_out = os.path.join(dest, "core/target/classes"), os.path.join(dest, "web/target/classes")
    os.makedirs(core_out, exist_ok=True)
    os.makedirs(web_out, exist_ok=True)
    r1 = subprocess.run(["javac", "-d", core_out] + core_src, capture_output=True, text=True)
    r2 = subprocess.run(["javac", "-cp", core_out, "-d", web_out] + web_src, capture_output=True, text=True)
    return r1.returncode == 0 and r2.returncode == 0
