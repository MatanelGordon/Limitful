# Limitful for C#

`Limitful.sln` owns direct sibling projects:

- `Limitful.Core` — the primary package.
- `Limitful.Core.Tests` — its xUnit test project.

`Limitful.Core` builds for both `net8.0` and `netstandard2.0`. The test project
targets `net8.0`, because .NET Standard defines an API surface rather than a
runnable application framework. Shared core code must compile against the
`netstandard2.0` API surface; target-specific code must be isolated with the
SDK's target-framework conditions.

Future packages belong beside them, for example `Limitful.OpenTelemetry` and
`Limitful.RedisSynchronization`. Do not introduce shared `src` or `tests`
container directories.
