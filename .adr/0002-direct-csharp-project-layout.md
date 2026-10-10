# Place C# projects directly under the language root

**Status:** accepted

ADR-0001 establishes that C# packages are separate projects in one solution.
Those projects live directly under `csharp/` because the project is the package
boundary in this workspace; generic `src/` and `tests/` container directories
would obscure the sibling-package layout used for future integrations.

## Constraints this creates

- `Limitful.Core` and `Limitful.Core.Tests` are direct children of `csharp/`.
- Future package and test projects follow the same direct-sibling convention.
- The solution must not recreate virtual `src` or `tests` folders.
