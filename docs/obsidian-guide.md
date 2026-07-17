# Viewing your vault in Obsidian (optional)

The vault is plain markdown and works fully without Obsidian. Obsidian adds the graph
view, backlinks, and a pleasant reading/editing experience for the human in the loop.

## Setup (2 minutes)

1. Install [Obsidian](https://obsidian.md) (desktop, free).
2. **Open folder as vault** → pick your SwarmVault directory (default `~/SwarmVault`;
   `python3 ~/.swarmvault/scripts/swarmvault.py doctor` shows the path).
3. That's it. Start at `00 Maps/Home.md`.

## Worth turning on (all core, no community plugins required)

- **Graph view** — your projects' knowledge as a network; filter by `tag:#swarm/memory`
  or a `project/<name>` tag to see one project's brain.
- **Backlinks** — see every note that references the one you're reading.
- **Quick switcher** (Ctrl/Cmd-O) — jump to any note by name.

## Rules of the road

- Notes with `generated: true` in their frontmatter are **overwritten by sync** — don't
  hand-edit them. Your space: `<Project> Notes.md` (never touched) and any note without
  the flag.
- `<Project> Digest.md` — write or let a skill write an architecture digest here; sync
  links it from the MOC and preserves it.
- Community plugins are your call — but they run with your files; audit what you
  install (see the security note in the README).

## No Obsidian? No problem

Everything Obsidian shows is reachable from the CLI: `query --search`, `show <note>`,
and the MOC files themselves are plain readable markdown.
