# INSTALL.md — written for agents

You are an AI coding agent asked to integrate SwarmVault. Follow these steps exactly, in
order. Ask the user only the questions marked **ASK**. Every step has a verification —
do not proceed past a failed one; use the remedies at the bottom.

Humans: `./install.sh` does steps 1–3, then prints your per-platform steps. Manual path:
this file, ignoring the "you are an agent" framing.

## 1. Get the code to its home

If you are already reading this inside a local clone, use it; otherwise:

```bash
git clone https://github.com/AnmarHani/swarmvault ~/.swarmvault
```

If the clone lives elsewhere, copy it: `cp -r <clone> ~/.swarmvault`.
**Verify:** `python3 ~/.swarmvault/scripts/swarmvault.py --help` prints the subcommand list.

## 2. Create the vault

**ASK the user:** "Where should the vault live? Default `~/SwarmVault` — it will hold
knowledge for ALL your projects." Then:

```bash
python3 ~/.swarmvault/scripts/swarmvault.py init --vault <chosen-path>
```

**Verify:** the command prints `vault ready:` and the folder contains `00 Maps` …
`90 Templates` and `registry.json`.

## 3. Platforms

**ASK the user:** "Which platforms should I wire — Claude Code, Codex, or both?" and
"Skills globally (all projects) or per-project?"

### 3a. Claude Code

Skills — copy (or symlink) the catalog:

```bash
mkdir -p ~/.claude/skills && cp -r ~/.swarmvault/skills/* ~/.claude/skills/
# per-project instead: <project>/.claude/skills/
```

Hooks — merge into `~/.claude/settings.json` (or the project's
`.claude/settings.json`). **If a `hooks` key already exists, append to its arrays — never
replace it; show the user a diff before writing.**

```json
{
  "hooks": {
    "SessionStart": [
      {"hooks": [{"type": "command",
        "command": "python3 ~/.swarmvault/scripts/swarmvault.py hook"}]}
    ],
    "SessionEnd": [
      {"hooks": [{"type": "command",
        "command": "python3 ~/.swarmvault/scripts/swarmvault.py sync --quiet"}]}
    ]
  }
}
```

**Verify:** `python3 -c "import json;json.load(open('$HOME/.claude/settings.json'))"`
exits clean; `ls ~/.claude/skills/swarm-flow` shows SKILL.md.

### 3b. Codex

Append this block to the project's `AGENTS.md` (create the file if absent). The fence
markers make re-runs idempotent: **if the markers already exist, replace the block
between them; never touch anything outside them.**

```markdown
<!-- swarmvault:begin -->
## SwarmVault

This project uses SwarmVault — a shared knowledge vault + SDLC skills. The CLI:
`python3 ~/.swarmvault/scripts/swarmvault.py`.

- **Session start:** run `... context .` and treat the output as prior project knowledge.
- **Before each phase of work**, read the matching skill file below.
- **Session end:** run `... sync --quiet`, and journal a session note per swarm-vault.
- Memory notes go in `.swarm/memory/` in this repo (mirrored to the vault by sync).

| Skill | When | File |
|---|---|---|
| swarm-vault | always — the vault contract | ~/.swarmvault/skills/swarm-vault/SKILL.md |
| swarm-flow | "continue the project" / what's next | ~/.swarmvault/skills/swarm-flow/SKILL.md |
| swarm-spec | requirements | ~/.swarmvault/skills/swarm-spec/SKILL.md |
| swarm-design | architecture | ~/.swarmvault/skills/swarm-design/SKILL.md |
| swarm-design-ui | UI/UX | ~/.swarmvault/skills/swarm-design-ui/SKILL.md |
| swarm-implement | build/tickets | ~/.swarmvault/skills/swarm-implement/SKILL.md |
| swarm-orchestrate | optional autonomous dispatch/supervisor | ~/.swarmvault/skills/swarm-orchestrate/SKILL.md |
| swarm-review | milestone review | ~/.swarmvault/skills/swarm-review/SKILL.md |
| swarm-debug | any bug | ~/.swarmvault/skills/swarm-debug/SKILL.md |
| swarm-init / swarm-migrate | onboarding projects | ~/.swarmvault/skills/…/SKILL.md |
| swarm-skill-forge | authoring skills | ~/.swarmvault/skills/swarm-skill-forge/SKILL.md |
<!-- swarmvault:end -->
```

**Verify:** the file contains exactly one `swarmvault:begin` marker.

## 4. Register the current project (offer it)

**ASK:** "Register this project in the vault now?" If yes — from the project root:

```bash
python3 ~/.swarmvault/scripts/swarmvault.py register            # add --isolated to hide
python3 ~/.swarmvault/scripts/swarmvault.py sync --quiet
```

## 5. Optional: autonomy & usage-limit continuation (off by default)

**ASK:** "Do you want the optional local orchestrator? It can run several Claude Code / Codex
workers in parallel and keep going across usage-limit resets. It's disabled by default and
never required — say no and everything still works manually."

If **no**, skip to §6 (this is genuinely optional).

If **yes**, **ASK:** "How many agents of each platform should run, which model tier, and may
they edit code?" Then, from the project root, configure per platform and start:

```bash
python3 ~/.swarmvault/scripts/swarmvault.py supervisor configure --project <P> --platform claude-code --max-workers <N> --model <model> --allow-write
python3 ~/.swarmvault/scripts/swarmvault.py supervisor configure --project <P> --platform codex --max-workers <N> --model <model> --allow-write
python3 ~/.swarmvault/scripts/swarmvault.py supervisor enable  --project <P>
python3 ~/.swarmvault/scripts/swarmvault.py supervisor start   --project <P>
```

Omit `--allow-write` for read-only workers. Beyond the two verified platforms you can configure
best-effort adapters (`gemini`, `opencode`, `droid`, `cursor`, `copilot` — verify their flags)
or wire any other CLI agent with `--platform <name> --launch-cmd '<cmd> {cwd} {prompt}'`. Give a
platform per-kind models with `--models 'design=…,coding=…'` so big tasks get the right model;
the orchestrator assigns by task size and each platform's remaining usage. Watch the whole swarm
from this CLI with `board --project <P>` (add `--watch 5`), and on long tasks `checkpoint` a
safe state before compacting. See [swarm-orchestrate](skills/swarm-orchestrate/SKILL.md).
**Usage-limit continuation works with or without the supervisor:** near a provider limit an agent will ask (in-session) whether to resume after
the reset — until the project finishes or a point you name — and, if you agree, schedule the
wake and record it via `plan-continue`. See [swarm-orchestrate](skills/swarm-orchestrate/SKILL.md).

**Verify:** `python3 ~/.swarmvault/scripts/swarmvault.py supervisor status --project <P>`
reports `enabled` (and a PID if started).

## 6. Final verification

```bash
python3 ~/.swarmvault/scripts/swarmvault.py doctor
```

Expected: ✓ config, ✓ vault, ✓ folders, ✓ registry; ✓ current project if step 4 ran.
Show the user the disclaimer (also in README): *environment, packages, and vault data are
the user's responsibility to audit; isolation is cooperative, not a security boundary.*
Point them at `/swarm-flow` (or "continue project X") to start.

## Remedies

- `--help` fails → wrong python (`python3 --version` ≥ 3.9) or wrong path — re-check step 1.
- `init` "not set up" loops → `$SWARMVAULT_HOME` points somewhere stale; unset it or
  re-run init.
- doctor ✗ current project → run step 4 from the project root (marker + registry entry).
- settings.json parse error → you broke the merge; restore the backup you made (make one)
  and merge again.
- Moved a project later → `swarmvault.py register --repair` from its new root.
