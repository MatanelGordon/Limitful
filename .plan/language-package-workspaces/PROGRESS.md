# Progress: language package workspaces

**Status:** executing
**Current phase:** Phase 2 — ori authors running

## Agents

- `p2-dotnet-go` — running in `sa/p2-dotnet-go`; owns `csharp/**`, `go/**`
- `p2-typescript` — running in `sa/p2-typescript`; owns `typescript/**`
- `p2-rust-python` — running in `sa/p2-rust-python`; owns `rust/**`, `python/**`

## Completed

- Repository and documentation conventions inspected.
- Target languages and package topology confirmed by the user.
- ADR-0001 and implementation plan written.
- Cross-model plan review: `VERDICT: ready`, no blockers.

## Problems

- The installed ori skill copy lacks its advertised helper scripts and review
  template. Fallback: live `ori auth`, OpenRouter's primary models API, and the
  documented review contract from `SKILL.md`.

## Resume here

Collect the three ori reports, inspect their status files and commits, then run a
different-model review against each worktree before merge.
