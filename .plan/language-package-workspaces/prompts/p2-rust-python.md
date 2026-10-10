# Task: Scaffold the Rust and Python package workspaces

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
`.adr/0001-language-package-workspaces.md`. Both workspaces must support future
sibling packages without implementing any Limitful behavior now.

## Scope — what you own

- `rust/**`
- `python/**`
- `.plan/language-package-workspaces/handoffs/p2-rust-python.md` in your worktree
- `/Users/matanelgordon/Desktop/Projects/Limitful/.plan/language-package-workspaces/agents/p2-rust-python.md` in the main tree (status only)

## Off-limits — other agents own these RIGHT NOW

- `csharp/**`, `go/**` (p2-dotnet-go)
- `typescript/**` (p2-typescript)
- Root files, existing docs, `.adr/**`, and every other `.plan/**` path
- `docs/site/**` must remain untouched

## Required shape

- `rust/Cargo.toml` is a Cargo workspace with the `limitful` crate at
  `rust/main`; future crates belong beside `main`.
- The Rust crate is version `0.0.0`, non-publishable while empty, and contains
  only crate documentation/behavior-free entry scaffolding. Commit a workspace
  lockfile if Cargo's standard workspace flow produces one.
- `python/pyproject.toml` is a uv workspace with the `limitful` distribution at
  `python/main`; future distributions belong beside `main`.
- Use a modern `src/limitful` layout, Python >=3.11, uv's build backend, pytest,
  and Ruff. Keep the distribution version `0.0.0` and non-publishable in intent.
- A packaging/import smoke test is allowed; do not test or implement Limitful
  behavior. Commit `uv.lock`.

## Acceptance criteria

1. Cargo and uv each discover exactly the main package today.
2. Both primary packages build and test with no Limitful runtime/API behavior.
3. Future sibling packages require no directory migration of `main`.
4. No file outside the allowlist is changed.

## Critical-path tests

```bash
cargo fmt --manifest-path rust/Cargo.toml --all -- --check
cargo clippy --manifest-path rust/Cargo.toml --workspace --all-targets -- -D warnings
cargo test --manifest-path rust/Cargo.toml --workspace
uv --directory python sync --all-packages
uv --directory python build --package limitful
uv --directory python run --package limitful ruff check main
uv --directory python run --package limitful ruff format --check main
uv --directory python run --package limitful pytest main/tests
```

Do not weaken a command to make it pass.

## Commit

Commit all work on the current branch with a conventional message. Finish with
no uncommitted changes.

## Handoff and progress reporting

Maintain the absolute status file listed in Scope, under 20 lines, using:
`STATUS: RUNNING|DONE|PARTIAL|BLOCKED`, `CHANGED:`, `TESTS:`, and `NOTES:`.

Before finishing, write the worktree file
`.plan/language-package-workspaces/handoffs/p2-rust-python.md` with these headings:
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
