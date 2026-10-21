# Curated references

Pick one or two per module, never a bibliography dump. Prefer the chapter or article that answers the module's question.

## Refactoring and legacy code
- **Refactoring** (2nd ed.), Martin Fowler: catalog of small safe moves; "Bad smells in code" chapter for vocabulary.
- **Working Effectively with Legacy Code**, Michael Feathers: characterisation tests, seams, breaking dependencies to get code under test. The book for phase 0.
- **Tidy First?**, Kent Beck: small structural changes before behaviour changes; economics of when to tidy.
- **The Mikado Method**, Ellnestam and Brolund: safe order for large tangled changes.
- Martin Fowler's articles: "StranglerFigApplication", "BranchByAbstraction" (Paul Hammant), "ParallelChange" (Danilo Sato), "Feature Toggles" (Pete Hodgson).

## Code quality and design
- **Clean Code**, Robert C. Martin: naming, functions, readability. Read critically; some advice is debated (very short functions).
- **Patterns of Enterprise Application Architecture**, Martin Fowler: transaction script, table module, domain model, service layer, repository, unit of work; the vocabulary behind Laravel actions, Rails service objects and most "layered" codebases.
- **A Philosophy of Software Design**, John Ousterhout: deep modules, information hiding, complexity as the enemy; a good counterweight to over-layering.
- **Design Patterns** (GoF) for vocabulary; **Head First Design Patterns** as a gentler entry.
- **Domain Modeling Made Functional**, Scott Wlaschin: making illegal states unrepresentable with types (useful in TS, Kotlin, Rust, F#).

## Architecture
- **Clean Architecture**, Robert C. Martin: dependency rule, component principles (stability, abstractness).
- Alistair Cockburn, "Hexagonal Architecture" (original article, 2005) and **Hexagonal Architecture Explained** (Cockburn and Garrido de Paz, 2024).
- **Get Your Hands Dirty on Clean Architecture**, Tom Hombergs: hexagonal in Java/Spring, pragmatic, with shortcuts discussed.
- **Fundamentals of Software Architecture**, Mark Richards and Neal Ford: styles and trade-offs, architecture characteristics.
- **Building Evolutionary Architectures** (2nd ed.), Ford, Parsons, Kua, Sadalage: fitness functions.
- **Software Architecture: The Hard Parts**, Ford, Richards, Sadalage, Dehghani: decomposition, data ownership, modular monolith to services.
- Jimmy Bogard, "Vertical Slice Architecture" (talk and article).
- Simon Brown, "Modular Monoliths" talk; the C4 model for diagrams.

## Domain-driven design
- **Learning Domain-Driven Design**, Vlad Khononov: the most accessible entry; subdomain types (core, supporting, generic) drive investment.
- **Domain-Driven Design Distilled**, Vaughn Vernon: short overview.
- **Domain-Driven Design**, Eric Evans: the source; read after an introduction.
- **Implementing Domain-Driven Design**, Vaughn Vernon: aggregates design rules.
- Alberto Brandolini, **Introducing EventStorming**: workshop format to discover domains with business people.

## CQRS and event sourcing
- Greg Young's CQRS documents and talks; Martin Fowler's "CQRS" and "Event Sourcing" articles (including his warnings).
- **Versioning in an Event Sourced System**, Greg Young: the hard part teams discover late.

## Testing
- **Unit Testing Principles, Practices, and Patterns**, Vladimir Khorikov: what to test, mocks vs real collaborators, testing domain vs controllers.
- **Growing Object-Oriented Software, Guided by Tests**, Freeman and Pryce.
- **Test-Driven Development: By Example**, Kent Beck.

## Teams and delivery
- **Accelerate**, Forsgren, Humble, Kim: the delivery metrics (lead time, deployment frequency, change failure rate, time to restore) used in the pitch.
- **Team Topologies**, Skelton and Pais: aligning teams and boundaries (Conway's law).

## Ecosystem-specific starting points
- TS/Node: Khalil Stemmler's articles on DDD and clean architecture in TypeScript; Feature-Sliced Design documentation (feature-sliced.design) for frontends.
- PHP: Matthias Noback, **Advanced Web Application Architecture**; Brent Roose, **Laravel Beyond CRUD**.
- .NET: Microsoft's "Architecting Modern Web Applications with ASP.NET Core and Azure" e-book (clean architecture chapter); Milan Jovanović's and Jimmy Bogard's articles on vertical slices.
- Java: Tom Hombergs (above); Spring Modulith reference documentation.
- Go: Alex Edwards, **Let's Go Further** (project structure); the Go blog "Organizing a Go module".
- Rust: **Zero To Production in Rust**, Luca Palmieri (domain types, testing, structure of a backend).
- C++: John Lakos, **Large-Scale C++ Software Design** (physical design, levelization), and his newer **Large-Scale C++ Volume I**.
