# Task: Review the language package workspace plan

Read `.plan/language-package-workspaces/plan.md`, the repository documentation it
cites, and `.adr/0001-language-package-workspaces.md`. Do not modify any file.

Check only for execution-breaking flaws, in this priority order:

1. Ownership collisions between the three Phase 2 agents.
2. Acceptance criteria that are not objectively checkable.
3. Critical-path commands that do not match the proposed scaffold/tooling.
4. Missing or unanswered edge cases relevant to behavior-free scaffolding.
5. Contradictions with repository decisions or the user's requested package
   topology.
6. Context a fresh executor would still have to guess.

Output fewer than 300 words in exactly this form:

```text
VERDICT: ready | needs-changes
BLOCKERS:
1. <finding and exact fix, or "none">
NON-BLOCKING:
- <at most three items, or "none">
```
