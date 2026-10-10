# Organize language bindings as expandable package workspaces

**Status:** accepted

Each target language owns a top-level workspace that can grow beyond the core
binding. C# keeps `Limitful.Core` and future projects such as
`Limitful.OpenTelemetry` and `Limitful.RedisSynchronization` in one solution.
TypeScript, Rust, Go, and Python keep the primary `limitful` package under
`<language>/main`, with optional integration packages added as siblings.

This preserves each ecosystem's native package and workspace conventions while
keeping optional dependencies out of the main package.

## Constraints this creates

- The primary binding contains no OpenTelemetry, Redis-client, or framework
  dependency.
- Optional packages are siblings of `main`; they are not nested inside the main
  package.
- C# projects share `csharp/Limitful.sln` and use `Limitful.*` package names.
- Initial test tooling is xUnit v3 for C#, Vitest for TypeScript, the built-in
  Rust and Go harnesses, and pytest for Python. Scaffold-only packages do not add
  fake behavioral tests.
- No documentation-site project is created until its framework is decided.
