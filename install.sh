#!/usr/bin/env bash
# SwarmVault installer — human door. Idempotent: safe to re-run.
# Does: copy this repo to ~/.swarmvault, create the vault, print platform wiring.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${SWARMVAULT_INSTALL:-$HOME/.swarmvault}"
VAULT="${SWARMVAULT_VAULT:-$HOME/SwarmVault}"

command -v python3 >/dev/null || { echo "error: python3 (>=3.9) is required"; exit 1; }

if [ "$SRC" != "$DEST" ]; then
  mkdir -p "$DEST"
  cp -r "$SRC/scripts" "$SRC/skills" "$SRC/vault-template" "$DEST/"
  cp "$SRC/INSTALL.md" "$SRC/CREDITS.md" "$DEST/" 2>/dev/null || true
  [ -f "$SRC/LICENSE" ] && cp "$SRC/LICENSE" "$DEST/"
  [ -f "$SRC/README.md" ] && cp "$SRC/README.md" "$DEST/"
fi

python3 "$DEST/scripts/swarmvault.py" init --vault "$VAULT"

cat <<EOF

────────────────────────────────────────────────────────────
SwarmVault installed to $DEST — one manual step per platform:

  Claude Code : copy skills + hooks  → INSTALL.md §3a
  Codex       : paste AGENTS.md block → INSTALL.md §3b

Then, from any project root:
  python3 $DEST/scripts/swarmvault.py register
  python3 $DEST/scripts/swarmvault.py doctor

Tip: paste this to your agent and it does the wiring for you:
  "Read $DEST/INSTALL.md and finish integrating SwarmVault."
────────────────────────────────────────────────────────────
Note: your environment, packages, and vault data are yours to
audit. Isolation flags are cooperative, not a security boundary.
EOF
