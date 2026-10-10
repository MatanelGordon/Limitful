# Target .NET 8 and .NET Standard 2.0 from Limitful.Core

**Status:** accepted

`Limitful.Core` multi-targets `net8.0` and `netstandard2.0`. This gives modern
.NET consumers a framework-specific assembly while retaining a broad fallback
contract for runtimes that implement .NET Standard 2.0.

## Constraints this creates

- Every unguarded core source file must compile against the `netstandard2.0` API
  surface.
- Framework-specific implementations use MSBuild conditions or the generated
  `NET8_0` and `NETSTANDARD2_0` compilation symbols without changing the public
  API unintentionally.
- `Limitful.Core.Tests` targets runnable `net8.0`; it does not target .NET
  Standard directly.
- Builds must verify both core target frameworks, even when tests execute only
  on .NET 8.
