---
name: fr-03-query-cli
description: The generalized query CLI — BM25 search, structured filters, note display, context injection, hook mode, plus init and register subcommands
project: SwarmVault
type: spec
status: draft-for-validation
priority: must
requires: [fr-01-vault-structure, fr-02-config-registry]
---

# FR-03 — Query CLI (`swarmvault` script)

**Story:** As an agent, one command answers "what does the vault know about X" with names +
descriptions — instead of Glob/Grep/Read sweeps — so context stays cheap (FR-21).

## Interface (per B7: proven CLI kept, generalized; init/register added)

```
swarmvault.py query --search "auth flow" [--project P] [--type T] [--tag G]
                    [--folder F] [--limit N] [--format list|json|paths]
swarmvault.py show <note-name-or-path>
swarmvault.py context <cwd>          # compact per-project context block
swarmvault.py hook                   # stdin {"cwd":...} → SessionStart hook JSON, always exit 0
swarmvault.py init [--vault PATH]    # create vault from template + config file
swarmvault.py register [--path P] [--name N] [--isolated] [--import-claude] [--repair]
```

Derived from the author's `vault_query.py` (BM25 with name/description/tag field boosting,
`claude/*`→`swarm/*` tag-wins type classification, context budget) — behavior preserved,
paths from FR-02, PyYAML replaced by a built-in minimal frontmatter parser (C-1).

## Acceptance criteria (EARS)

- WHEN invoked with `query --search`, results shall be BM25-ranked with name, description,
  and vault-relative path, in under 2 s at 5,000 notes (NFR-P1).
- WHEN invoked as `hook`, output shall be valid SessionStart hook JSON and the process shall
  exit 0 under all failure modes (NFR-R2).
- `context` output should stay within the configured character budget (NFR-P2 — a
  guideline, not a cap: when the essentials don't fit, exceed it rather than omit them;
  trim whole low-value sections first — oldest sessions before memory descriptions — and
  never cut mid-content). It shall include: MOC pointer, memory names + descriptions,
  current phase (from swarm-flow state note if present), recent sessions.
- Cross-project queries shall exclude `isolation: isolated` projects unless `--project`
  names them explicitly (NFR-S2).
- `init` shall create vault + config and print the three integration next-steps (hooks /
  AGENTS.md / manual).
- The frontmatter parser shall handle: scalar strings, quoted strings, integers, dates,
  inline and dashed lists, and one nesting level (`metadata:`) — the full range used by
  FR-01 templates — and fall back to type `note` on anything it cannot parse.

## Edge cases

- Empty vault → `query` prints "vault is empty; run swarm-init on a project" rather than
  nothing.
- `show` with an ambiguous stem across projects → list the candidates instead of guessing.
- Non-UTF8/binary file in vault tree → skipped silently.
