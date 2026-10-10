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

- `rust/Cargo.toml` — workspace resolver v2, clippy lints configured, publish=false
- `rust/main/Cargo.toml` — limitful crate v0.0.0, edition 2021
- `rust/main/src/lib.rs` — doc-only lib with behavior-free test (`assert_eq!(2+2,4)`)
- `rust/Cargo.lock` — committed workspace lockfile
- `python/pyproject.toml` — uv workspace, members=["main"], ruff + pytest config
- `python/main/pyproject.toml` — limitful distribution v0.0.0, hatchling backend, Python>=3.11
- `python/main/src/limitful/__init__.py` — src-layout package with docstring
- `python/main/tests/` — scaffold tests (version check + import sanity)
- `python/uv.lock` — committed lockfile
- All critical-path tests pass (fmt, clippy, cargo test, uv sync/build/ruff/pytest)
- Commit 99ba97a on branch sa/p2-rust-python

# NEXT

- Root Makefile with per-language targets (owned by root agent in phase 3)
- Other language workspaces: csharp/, typescript/, go/

# BLOCKED

None.

# DECISIONS

1. Rust uses Cargo workspace with single member `main`; no benchmarks yet since the crate has no code. Benchmarks will be added when algorithms are implemented.
2. Rust lints: clippy all+pedantic at warn, correctness/suspicious at deny; rust_2018_idioms warn; doctests disabled until API exists.
3. Python uses `src/limitful` layout with tests colocated at `python/main/tests/` (flat, matching the critical-path `pytest main/tests` command).
4. Python dev deps: pytest managed via uv dependency-groups (dev); Ruff configured at both workspace and package level.
5. Both packages versioned at 0.0.0 with explicit non-publish intent while empty.
