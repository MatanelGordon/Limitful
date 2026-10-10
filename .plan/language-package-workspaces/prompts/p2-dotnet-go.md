# Task: Scaffold the C# and Go package workspaces

You are an autonomous coding subagent working in an isolated git worktree.
Implement this end to end. Do not ask questions; choose the most conventional
reversible option and report assumptions.

## Objective

The user's objective, verbatim:

> ok this is going to be the monorepo of the limitful project. I want you to
> create 5 different folders here - each one will represent the implementation
> of the library in a different language as stated in the docs. DO NOT IMPLEMENT
> THE LIBRARY JUST PREPARE THE BOILERPLATE TO DEVELOP IT. also, make a makefile
> that can help me manage it and dont make a boilerplate for the docs site just
> yet, I am still not sure how i want to do it
>
> Note that each language will have sub packages, it is not everything under one
> package. so for C# for example it will be called Limitful.Core (and in the
> future i will want to add Limitful.Opentelemetry or
> Limitful.RedisSynchronization) but in the other languages there will be
> limitful as the main package so its implementation will be stored in
> /<lang>/main/* and there will be other libraries next to main in the future.
> The idea here is to order the libraries the right way for future sub-package
> expension in all languages. In C#, it can be different projects but the same
> solution. in node, it can be a nested turborepo, in go you can use go packages
> as always, and in rust you do whatever you want.

## Context

Read `.plan/language-package-workspaces/plan.md` and
`.adr/0001-language-package-workspaces.md`. The repository is specification-only.
Create buildable scaffolds with no Limitful API or runtime behavior.

## Scope — what you own

- `csharp/**`
- `go/**`
- `.plan/language-package-workspaces/handoffs/p2-dotnet-go.md` in your worktree
- `/Users/matanelgordon/Desktop/Projects/Limitful/.plan/language-package-workspaces/agents/p2-dotnet-go.md` in the main tree (status only)

## Off-limits — other agents own these RIGHT NOW

- `typescript/**` (p2-typescript)
- `rust/**`, `python/**` (p2-rust-python)
- Root files, existing docs, `.adr/**`, and every other `.plan/**` path
- `docs/site/**` must remain untouched

## Required shape

- `csharp/Limitful.sln` contains solution folders for `src` and `tests`.
- The primary project is `csharp/src/Limitful.Core/Limitful.Core.csproj`, package
  ID `Limitful.Core`; future `Limitful.*` projects can be added beside it.
- Include a referenced `csharp/tests/Limitful.Core.Tests` test project and useful
  solution-wide build/package configuration. Do not add placeholder classes or
  fake always-passing tests.
- Use the installed .NET 8 SDK conventions and pin/roll forward safely with
  `global.json`.
- `go/go.mod` is the one module root. `go/main` declares `package limitful` and
  contains documentation/package scaffolding only. Future Go packages belong
  beside `main`.
- Empty packages must restore/build/test, but must not claim implemented behavior.

## Acceptance criteria

1. Both owned language roots exist and match ADR-0001.
2. C# builds `Limitful.Core` and discovers its test project with no library
   implementation types.
3. Go discovers `./main` as package name `limitful` with no exported behavior.
4. No file outside the allowlist is changed.

## Critical-path tests

```bash
dotnet restore csharp/Limitful.sln
dotnet build csharp/Limitful.sln --configuration Release --no-restore
dotnet test csharp/Limitful.sln --configuration Release --no-build
cd go && go test ./... && go vet ./...
```

Do not weaken a command to make it pass.

## Commit

Commit all work on the current branch with a conventional message. Finish with
no uncommitted changes.

## Handoff and progress reporting

Maintain the absolute status file listed in Scope, under 20 lines, using:
`STATUS: RUNNING|DONE|PARTIAL|BLOCKED`, `CHANGED:`, `TESTS:`, and `NOTES:`.

Before finishing, write the worktree file
`.plan/language-package-workspaces/handoffs/p2-dotnet-go.md` with these headings:
`# OBJECTIVE` (copy the Objective block above verbatim), `# DONE` (commit and test
evidence), `# NEXT`, `# BLOCKED`, and `# DECISIONS`. Rewrite it rather than
appending if you update it, and commit it with the scaffold.

## Output contract

Final message under 200 words, exactly:

```text
STATUS: DONE | PARTIAL | BLOCKED
CHANGED: <comma-separated paths>
TESTS: <commands and pass/fail>
NOTES: <up to three bullets>
QUESTION: <omit unless an assumption needs confirmation>
BLOCKED: <omit unless not done>
```
