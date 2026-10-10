# OBJECTIVE

ok this is going to be the monorepo of the limitful project. I want you to
create 5 different folders here - each one will represent the implementation
of the library in a different language as stated in the docs. DO NOT IMPLEMENT
THE LIBRARY JUST PREPARE THE BOILERPLATE TO DEVELOP IT. also, make a makefile
that can help me manage it and dont make a boilerplate for the docs site just
yet, I am still not sure how i want to do it

Note that each language will have sub packages, it is not everything under one
package. so for C# for example it will be called Limitful.Core (and in the
future i will want to add Limitful.Opentelemetry or
Limitful.RedisSynchronization) but in the other languages there will be
limitful as the main package so its implementation will be stored in
/<lang>/main/* and there will be other libraries next to main in the future.
The idea here is to order the libraries the right way for future sub-package
expansion in all languages. In C#, it can be different projects but the same
solution. in node, it can be a nested turborepo, in go you can use go packages
as always, and in rust you do whatever you want.

# DONE

- Added native generated-artifact, coverage, test-result, IDE, and temporary-file ignores under `csharp/` and `go/` without ignoring source, lock, or configuration files.
- `csharp/Limitful.sln` organizes `Limitful.Core` and `Limitful.Core.Tests` under visible `src` and `tests` solution folders.
- Added `csharp/Directory.Build.props` for shared .NET 8, nullable, implicit-using, and C# 12 settings, plus `csharp/Directory.Packages.props` for centrally managed test dependencies.
- Kept `Limitful.Core` empty, non-packable, non-publishable, and at version `0.0.0`.
- Configured `Limitful.Core.Tests` as a real xUnit v3 test project with `IsTestProject=true`, private test dependencies, and the verified stable NuGet versions: `xunit.v3` 4.0.2, `xunit.runner.visualstudio` 4.0.1, `Microsoft.NET.Test.Sdk` 18.10.1, and `coverlet.collector` 10.1.0. No fake test source was added.
- Corrected the Go module path to `github.com/MatanelGordon/Limitful/go` and described the package neutrally as load-leveling utilities.

Critical-path results (all commands exited successfully):
```
$ dotnet restore csharp/Limitful.sln → OK (2 projects restored)
$ dotnet build csharp/Limitful.sln --configuration Release --no-restore → OK (0 warnings, 0 errors)
$ dotnet test csharp/Limitful.sln --configuration Release --no-build → OK (no test source, no tests discovered; fake tests intentionally omitted)
$ cd go && go test ./... → OK (no test files)
$ cd go && go vet ./... → OK
```

`dotnet list package --include-transitive` confirmed all four requested direct package versions resolve exactly. The follow-up changes are included in the second green commit on this worktree branch.

# NEXT

Phase 3 (root integration): create root Makefile, .gitignore, .editorconfig, update README.md and docs.

# BLOCKED

None.

# DECISIONS

1. Pinned .NET SDK to 8.0.404 (installed version available in container) using `rollForward: latestFeature` to allow security patches.
2. Test project uses `../../src/Limitful.Core/Limitful.Core.csproj` — two-level parent relative path from `tests/` back to `csharp/`.
3. Central package version management keeps test dependency versions in one place; each test-only package reference uses `PrivateAssets=all`.
4. The empty core remains at version `0.0.0` and is not packable or publishable until it contains a real implementation.
5. Go module path follows the repository's actual GitHub location, `github.com/MatanelGordon/Limitful/go`.
6. No placeholder classes or fake tests were added; Go uses the native `testing`/`go test` harness when real tests are introduced.
