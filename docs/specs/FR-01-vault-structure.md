---
name: fr-01-vault-structure
description: Central vault folder layout, note schema, and templates — the Obsidian-compatible standard every agent writes to
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: []
---

# FR-01 — Vault structure & note schema

**Story:** As an agent (or human in Obsidian), I open one vault and find every project's
knowledge in a predictable place with predictable frontmatter, so I can navigate without
exploration.

## Layout (per B6 — proven in the author's setup, kept as-is)

```
<vault>/
  00 Maps/          Home.md (all-projects index)
  10 Projects/      <Project>/<Project> MOC.md, mirrored docs, code-notes/, human Notes.md
  20 Memory/        <Project>/<memory-name>.md (mirrored from platform memory dirs)
  30 Plans/         <Project>/ SRS, feature specs, tickets/, question queue
  40 Sessions/      <Project>/YYYY-MM-DD-<slug>.md (compact session journals)
  50 Decisions/     <Project>/ADR-NNN-<slug>.md
  90 Templates/     note templates for every type
```

## Note schema

Frontmatter on every note: `name` (kebab slug), `description` (one line — the query
payload), `project`, `type` (map|moc|memory|plan|spec|ticket|session|decision|doc|note),
`tags` (incl. machine-set `swarm/<type>`), plus type-specific fields (`date`, `status`,
`priority`, `requires`). Body links related notes with `[[wikilinks]]`.

## Acceptance criteria (EARS)

- The repo shall ship a `vault-template/` matching the layout above, with a template note
  per type in `90 Templates/`.
- WHEN `init` creates a vault (FR-03), the created tree shall match `vault-template/`.
- Every note type's template shall carry valid frontmatter that the query CLI (FR-03)
  parses without error.
- Human-owned files (`<Project> Notes.md`, anything without `generated: true`) shall never
  be overwritten or pruned by sync (FR-04).
- The vault shall render correctly in Obsidian (wikilinks resolve, graph connects) while
  remaining fully usable without it (NFR-C1).

## Edge cases

- Note names colliding across projects → project subfolders keep paths unique; `name:`
  uniqueness required only within a project.
- Frontmatter absent/malformed → readers treat the file as `type: note` with stem as name;
  never crash (mirrors current vault_query behavior).

## Notes

Tickets and specs live under `30 Plans/<Project>/` (B6: no new top-level folders).
