# Task: Scaffold the nested TypeScript Turborepo workspace

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
`.adr/0001-language-package-workspaces.md`. This root is a nested npm/Turborepo
workspace, not the repository's global package manager.

## Scope — what you own

- `typescript/**`
- `.plan/language-package-workspaces/handoffs/p2-typescript.md` in your worktree
- `/Users/matanelgordon/Desktop/Projects/Limitful/.plan/language-package-workspaces/agents/p2-typescript.md` in the main tree (status only)

## Off-limits — other agents own these RIGHT NOW

- `csharp/**`, `go/**` (p2-dotnet-go)
- `rust/**`, `python/**` (p2-rust-python)
- Root files, existing docs, `.adr/**`, and every other `.plan/**` path
- `docs/site/**` must remain untouched

## Required shape

- `typescript/` is a private npm workspace root with Turborepo configuration and
  a committed npm lockfile.
- Workspace membership naturally accepts `main` and future sibling packages.
- `typescript/main` is the private `limitful` package at version `0.0.0`, ready
  to emit ESM JavaScript and declarations from `src` to `dist`.
- The source entry point is behavior-free (an empty export is acceptable).
- Provide build, test, lint/typecheck, format-check, format, and clean scripts.
- Use the live versions already recorded during foundation research: Turbo
  2.11.7, TypeScript 7.0.2, Prettier 3.9.10, and Vitest 5.0.3, or compatible
  locked patch releases if npm resolves them.
- Tests must pass with no behavior tests yet (Vitest's explicit no-test mode is
  acceptable); do not add fake assertions.

## Acceptance criteria

1. `npm --prefix typescript ci` recognizes exactly the main workspace today.
2. The main package builds JavaScript and declarations without runtime behavior.
3. Future sibling workspaces require no directory migration of `main`.
4. No file outside the allowlist is changed.

## Critical-path tests

```bash
npm --prefix typescript install
npm --prefix typescript run build
npm --prefix typescript run test
npm --prefix typescript run lint
npm --prefix typescript run format:check
npm --prefix typescript ci
```

Do not weaken a command to make it pass.

## Commit

Commit all work on the current branch with a conventional message. Finish with
no uncommitted changes.

## Handoff and progress reporting

Maintain the absolute status file listed in Scope, under 20 lines, using:
`STATUS: RUNNING|DONE|PARTIAL|BLOCKED`, `CHANGED:`, `TESTS:`, and `NOTES:`.

Before finishing, write the worktree file
`.plan/language-package-workspaces/handoffs/p2-typescript.md` with these headings:
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
