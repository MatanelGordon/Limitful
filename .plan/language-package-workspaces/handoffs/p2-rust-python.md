# OBJECTIVE

ok this is going to be the monorepo of the limitful project. I want you to
create 5 different folders here - each one will represent the implementation
of the library in a different language as stated in the docs. DO NOT IMPLEMENT
THE LIBRARY JUST PREPARE THE BOILERPLATE TO DEVELOP IT. also, make a makefile
that can help me manage it and dont make a boilerplate for the docs site just
yet, I am still not sure how i want to do it

Note that each language will have sub packages, it is not everything under one
package. so for C# for example it will be called Limitful.Core (and in the future i will want to add Limitful.Opentelemetry or
Limitful.RedisSynchronization) but in the other languages there will be limitful as the main package so its implementation will be stored in
/<lang>/main/* and there will be other libraries next to main in the future.
The idea here is to order the libraries the right way for future sub-package
expansion in all languages. In C#, it can be different projects but the same
solution. in node, it can be a nested turborepo, in go you can use go packages
as always, and in rust you do whatever you want.

# DONE

- Commit: this handoff and the Rust/Python follow-up are committed together on `sa/p2-rust-python`.
- Cargo and uv member globs discover a temporary sibling package; current workspaces contain only `limitful`.
- Rust uses Cargo's empty native test harness; the placeholder test and disabled doctests are removed.
- Python is a virtual uv workspace; `limitful` uses `uv_build`, pytest 9.1.1, and Ruff 0.15.9.
- Only one package-import smoke test remains under `python/main/tests`; built sdist and wheel contain no package tests.
- `python/uv.lock` is regenerated; Rust/Python descriptions no longer claim unsupported coordination behavior.
- All required fmt, clippy, cargo test, uv sync/build, Ruff check/format, and pytest commands pass.

# NEXT

- Root Makefile and other language workspaces remain with their assigned owners.

# BLOCKED

None.

# DECISIONS

1. Cargo and uv use sibling-directory globs while excluding workspace output directories (`target`, `dist`, and `.venv`).
2. The uv root contains workspace and shared-tool configuration only; package metadata and `uv_build` live in `python/main`.
3. pytest and Ruff are pinned in the member's `dev` group to the requested versions.
4. The only test is a package-import smoke test; no Limitful behavior is implemented or tested.
5. Rust documentation states only that the package is a scaffold with no implementation or public API.
