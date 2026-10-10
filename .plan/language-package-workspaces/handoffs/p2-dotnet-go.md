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

- `csharp/global.json` — pins SDK to 8.0.404 with latestFeature rollForward
- `csharp/Limitful.sln` — solution with `src` and `tests` project entries; supports adding future `Limitful.*` projects beside `src/Limitful.Core`
- `csharp/src/Limitful.Core/Limitful.Core.csproj` — NET 8.0 class library; IsPackable=false; no implementation types
- `csharp/tests/Limitful.Core.Tests/Limitful.Core.Tests.csproj` — NET 8.0 test project referencing core; no tests written
- `go/go.mod` — module `github.com/limitful/go`, Go 1.21
- `go/main/doc.go` — package `limitful` with documentation-only placeholder
- Agent status written to `.plan/language-package-workspaces/agents/p2-dotnet-go.md`

Critical-path results:
```
$ dotnet restore csharp/Limitful.sln            → OK (restored 2 projects)
$ dotnet build   csharp/Limitful.sln --configuration Release --no-restore → OK (0 warnings, 0 errors)
$ dotnet test    csharp/Limitful.sln --configuration Release --no-build   → OK (no-test harness, exit 0)
$ cd go && go test ./...                         → OK (no test files)
$ cd go && go vet ./...                          → OK
```

# NEXT

Phase 3 (root integration): create root Makefile, .gitignore, .editorconfig, update README.md and docs.

# BLOCKED

None.

# DECISIONS

1. Pinned .NET SDK to 8.0.404 (installed version available in container) using `rollForward: latestFeature` to allow security patches.
2. Test project uses `../../src/Limitful.Core/Limitful.Core.csproj` — two-level parent relative path from `tests/` back to `csharp/`.
3. Go module path chosen as `github.com/limitful/go` following standard Go import-path conventions.
4. No placeholder classes, fake tests, or stub implementations added — empty packages must truly be empty.
5. Go `doc.go` used instead of an empty `.go` file to satisfy Go's requirement that source files belong to a package while remaining behavior-free.
