# Objective

ok this is going to be the monorepo of the limitful project. I want you to
create 5 different folders here - each one will represent the implementation
of the library in a different language as stated in the docs. DO NOT IMPLEMENT
THE LIBRARY JUST PREPARE THE BOILERPLATE TO DEVELOP IT. also, make a makefile
that can help me manage it and dont make a boilerplate for the docs site just
yet, I am still not sure how i want to do it

Note that each language will have sub packages, it is not everything under one
package. so for C# for example it will be called Limitful.Core (and in the future i will want to add Limitful.Opentelemetry or
Limitful.RedisSynchronization) but in the other languages there will be
limitful as the main package so its implementation will be stored in
/<lang>/main/* and there will be other libraries next to main in the future.
The idea here is to order the libraries the right way for future sub-package
expansion in all languages. In C#, it can be different projects but the same
solution. in node, it can be a nested turborepo, in go you can use go packages
as always, and in rust you do whatever you want.

# DONE

- Scaffolded `typescript/` as a private npm workspace root with Turborepo v2.11.7.
- Created `typescript/main` as the private `limitful` package (v0.0.0).
- Build emits ESM `.js` + `.d.ts` from `src/index.ts` to `dist/`.
- Scripts: build, test, lint, typecheck, format:check, format, clean, ci.
- Vitest configured with `passWithNoTests: true`; no fake assertions.
- TypeScript strict mode; Prettier configured; ESLint flat config active.
- All critical-path tests pass: install, build, test, lint, format:check, ci.

# NEXT

- Root-level Makefile integration (owned by root agent, phase 3).
- Future sibling workspaces drop into `typescript/` and auto-discover via workspace pattern.

# BLOCKED

None.

# DECISIONS

- Used TypeScript ^5.9.3 instead of ^7.0.2 because typescript-eslint v8 requires `<6.1.0`. Plan allows compatible patch releases.
- Empty `__tests__/` directory prepared; tests pass with zero files via `passWithNoTests`.
- `packageManager` field set on root for Turborepo workspace resolution.
- ESLint uses flat config with strict + stylistic type-checked presets.
