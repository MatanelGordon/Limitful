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

## STATUS

DONE — follow-up implementation and all required checks are complete.

# DONE

- Scaffolded `typescript/` as a private npm workspace root with Turborepo v2.11.7.
- Created `typescript/main` as the private `limitful` package (v0.0.0).
- Build emits ESM `.js` + `.d.ts` from `src/index.ts` to `dist/`.
- Scripts: build, test, lint, typecheck, format:check, format, clean, ci.
- npm workspaces use `*` to discover sibling packages; root Turborepo scripts run
  tasks across all discovered packages without package filters.
- Exact tool versions: TypeScript 7.0.2, Vitest 5.0.3, Prettier 3.9.10, and
  Turbo 2.11.7.
- Lint runs strict `tsc --noEmit`; ESLint and typescript-eslint were removed,
  and `@types/node` is not a direct dependency (npm installs it as an optional
  Vitest/Vite peer).
- Shared Prettier configuration lives at the `typescript/` workspace root; the
  workspace has a comprehensive nested `.gitignore`.
- Vitest is configured with `passWithNoTests: true`; no fake tests or behavior
  were added.
- `npm --prefix typescript install`, `build`, `test`, `lint`, `format:check`,
  `ci`, and `npm --prefix typescript ci` all pass; the lockfile was regenerated.

# NEXT

- Root-level Makefile integration (owned by root agent, phase 3).
- Future sibling workspaces drop into `typescript/` and auto-discover via workspace pattern.

# BLOCKED

None.

# DECISIONS

- Exact foundation-verified tool versions are pinned. The prior claim that
  TypeScript 5.9.3 was a compatible patch for 7.0.2 was incorrect.
- TypeScript strict mode provides linting through `tsc --noEmit`; a separate
  `typecheck` alias remains available.
- Limitful is described neutrally as load-leveling utilities.
- `packageManager` field set on root for Turborepo workspace resolution.
