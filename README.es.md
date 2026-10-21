# re-arch

[English](README.md) | [Français](README.fr.md) | **Español** | [Deutsch](README.de.md) | [Português](README.pt-BR.md) | [Italiano](README.it.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

Un conjunto de skills para agentes que audita la arquitectura de una aplicación existente, propone arquitecturas objetivo dimensionadas según lo que cuesta entenderlas y construirlas, planifica el refactoring, presenta el caso a la dirección, encuadra a los agentes de programación con IA y la CI en torno al objetivo elegido, y genera material de formación basado en el propio código del equipo. Pensado para cualquier codebase, y en especial para las vibe-coded o generadas por IA.

Ecosistemas soportados: JavaScript / TypeScript, PHP, .NET (C#), Java / Kotlin, C / C++, Go, Rust.

## Qué obtienes

Ejecuta `re-arch-audit` sobre un repositorio y obtienes, en `.re-arch/`:

- un **mapa de dominios** de la aplicación (áreas de negocio, dependencias, sistemas externos como vista de contexto C4, zonas difusas, nivel de confianza por dominio), incluso cuando la estructura de carpetas no significa nada;
- un **diagnóstico** en el que cada hallazgo cita archivos y líneas, con su impacto para el equipo y para el negocio y su tamaño de corrección, además de las fortalezas que conviene conservar, **lo que parece malo pero está bien**, y preguntas abiertas para los mantenedores;
- **de 2 a 4 opciones objetivo** (desde "refactoring dirigido, misma estructura" hasta capas, vertical slices, monolito modular, clean / hexagonal, CQRS o event sourcing cuando el código lo justifica), cada una dimensionada en **coste de comprensión** y **tamaño de implementación** (S, M, L, XL), evaluada frente a los **escenarios de calidad** del negocio, posiblemente distinta por dominio, junto con los estilos considerados y descartados;
- un **plan de refactoring por fases** en tallas de camiseta con criterios explícitos: primero una red de seguridad de tests de caracterización, pasos con un comando `verify`, puertas de salida, rollback, puntos de parada y cobertura de todos los hallazgos críticos y altos;
- un **pitch para la dirección**: riesgos, opciones incluida la de no hacer nada, inversión como rango de capacidad con su derivación, hitos, indicadores, decisión solicitada;
- **guardrails**: AGENTS.md en la raíz y por dominio, un skill de proyecto que indica a los agentes dónde va el código nuevo, un **hook de agente** que ejecuta la comprobación de arquitectura en el propio turno del agente, fitness functions para la CI adoptadas con una **baseline congelada** (herramientas nativas por ecosistema más un checker independiente del lenguaje), un ADR (MADR 4), una checklist de revisión;
- una **academia**: un itinerario de aprendizaje alineado con el plan, módulos anclados en archivos reales del repo (antes/después, katas, preguntas de revisión), lecturas seleccionadas;
- un **informe HTML responsive** que lo reúne todo, validado contra el contrato de datos y comprobado a ancho de móvil, imprimible en PDF, más diagramas Mermaid para la documentación del repo;
- un **bundle [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) (OKF v0.2)** con el conocimiento de arquitectura (sistema, dominios, sistemas externos, decisión, reglas, roadmap, historial), para hacer commit en `docs/architecture/okf/` destinado a personas, agentes de programación y catálogos de conocimiento; los campos de confianza indican lo que el equipo ha validado, y el contenido sensible queda fuera;
- **re-auditorías** que muestran lo que se ha resuelto, lo que es nuevo y cómo han evolucionado las métricas.

## Skills

| Skill | Rol | Scripts |
|---|---|---|
| `re-arch-audit` | orquestador, checkpoints para validar dominios y elegir opción, modo re-auditoría | `diff_rearch.py` |
| `re-arch-scan` | grafo de dependencias (de nivel compilador cuando es posible), cableado DI, unidades de build, acoplamiento, ciclos, hotspots, co-change, distribución del conocimiento, duplicación, modelo de datos, rutas, sistemas externos, higiene de dependencias, secretos | `scan.py`, `precise.py`, `di.py`, `insights.py`, `ts_resolve.js`, `php_refs.php` |
| `re-arch-domains` | dominios de negocio a partir de imports + DI + co-change + modelo de datos + rutas | `cluster.py` (Louvain) |
| `re-arch-diagnose` | hallazgos con evidencias, severidad y tamaño de corrección; catálogo de smells con listas de "no señalar" | |
| `re-arch-options` | arquitecturas objetivo, dimensionado en dos ejes, escenarios de calidad, tabla de racionalización, catálogo de estilos, idioms por ecosistema | |
| `re-arch-plan` | plan por fases, pasos verificables, puertas de salida, técnicas incrementales | `plan_to_md.py` |
| `re-arch-pitch` | caso para la dirección | `pitch_to_md.py` |
| `re-arch-guardrails` | reglas para agentes, skill de proyecto, hooks de agente, fitness functions con baseline, ADR | `check_architecture.py` (+ scanner incluido) |
| `re-arch-academy` | material de formación sobre el propio código del equipo | |
| `re-arch-report` | informe HTML, validación del contrato, comprobación de renderizado, exportación Mermaid y OKF | `render.py`, `validate.py`, `check_render.py`, `to_okf.py` |

Cada skill funciona también por separado. Intercambian datos mediante archivos JSON en `.re-arch/`; el contrato está en `skills/re-arch-audit/references/contract.md` y lo aplica `validate.py`.

## ¿Qué precisión tiene el grafo de dependencias?

El scan usa las herramientas propias del lenguaje cuando están disponibles y lo indica en su sección "Graph sources"; si no, recurre a la resolución por regex.

| Ecosistema | Fuente precisa | Requiere |
|---|---|---|
| C/C++ | `compile_commands.json` (`-I`/`-D` reales) + árbol de includes del preprocesador | una base de datos de compilación (CMake `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, `bear`), un compilador |
| Go | `go list` (build tags, rutas de módulo exactas) | toolchain de Go |
| Rust | `cargo metadata` (grafo de crates, `use` entre crates) | Cargo |
| Java/Kotlin | `jdeps` sobre las clases compiladas | un JDK y un proyecto compilado |
| .NET | grafo de ProjectReference de los `.csproj` (descarta aristas imposibles) | nada |
| JS/TS | el propio resolver de módulos de TypeScript | `typescript` en el repo, o `--fetch-tools` |
| PHP | tokenizer de PHP con resolución completa de nombres | un binario `php` |

La inyección de dependencias se resuelve por separado (registros de .NET, providers de NestJS/Angular, bindings y facades de Laravel, servicios de Symfony, `@Bean` de Spring, Google Wire, implementaciones únicas) en **aristas de runtime**, separadas de los imports: las reglas de capas usan los imports, el acoplamiento y los dominios usan ambos. La reflexión y el escaneo basado en convenciones siguen siendo invisibles, y cada informe lo indica.

## Decisiones de diseño

- **Evidencias antes que opiniones**: primero se ejecuta un scan determinista; los hallazgos apuntan al código, y el diagnóstico muestra lo que ha decidido no señalar.
- **Ninguna arquitectura por defecto**: siempre hay una opción ligera sobre la mesa, cada opción debe justificarse con señales del código y evaluarse frente a escenarios de calidad, y clean, hexagonal y onion son una opción, no niveles de calidad. "Mantener la arquitectura actual" es un resultado legítimo.
- **El coste es visible**: coste de comprensión junto al tamaño de implementación.
- **Tallas, no días**: tallas de camiseta con criterios explícitos; XL significa "divídelo"; la dirección recibe rangos de capacidad con su derivación.
- **Dos públicos**: el equipo técnico recibe evidencias y pasos verificables, la dirección recibe riesgos y decisiones.
- **Un refactoring que perdura**: fitness functions con baseline congelada, hooks de agente, reglas para agentes por dominio, formación sobre el repo, re-auditorías.
- **Las personas no son hallazgos**: la concentración de conocimiento se reporta con seudónimos (`A1`, `A2`), y la correspondencia se queda en local.

## Requisitos

- Python 3.8+ (solo biblioteca estándar para el núcleo).
- Opcional, para el modo preciso: las toolchains de los lenguajes indicadas arriba; Node para el resolver de TypeScript.
- Opcional: Playwright + Chromium para comprobar el renderizado del informe (`pip install playwright && python -m playwright install chromium`).
- Opcional: historial git en el repo auditado (co-change, hotspots, conocimiento; evita los shallow clones).

## Instalación

Copia las carpetas de `skills/` en el directorio de skills de tu agente (por ejemplo `~/.claude/skills/` o `<repo>/.claude/skills/`), o sube los paquetes `.skill`. Después pide una auditoría de arquitectura de un repositorio, o invoca `/re-arch-audit`.

## Desarrollo

- `python3 tests/test_suite.py -v`: 34 tests sobre repositorios de fixture por ecosistema. Cada fixture planta trampas en las que falla la capa regex (includes calculados por macros, colisiones de directorios de include, `use` entre crates, nombres cualificados inline, colisiones de namespace entre proyectos, build tags, referencias PHP en el mismo namespace) y comprueba que la capa precisa y la extracción de DI las resuelven correctamente; además, baseline y hooks del checker, validación del contrato, renderizado a ancho de móvil, diffs de re-auditoría, exportación OKF (conformidad, campos de confianza, historial del log, nada sensible). Los tests que dependen de una toolchain se omiten cuando falta la toolchain.
- `python3 tools/sync.py` tras modificar el scanner (el skill de guardrails incluye una copia); `--check` en la CI.
- `evals/`: evals end-to-end (`evals.json`, calificados por `evals/grade.py`), incluido un repositorio sano en el que la respuesta correcta es "no pasar a hexagonal", y consultas de activación para las descripciones de los skills (`triggers.json`).
- `.github/workflows/tests.yml` lo ejecuta todo.
