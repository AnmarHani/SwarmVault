# TUI & CLI interface guidance

The terminal is a UI. Help text, flags, exit codes, and error style ARE the design.

## CLI

**Conventions win.** `--help` on everything, useful in < 10 lines: usage, the 3–5 common
examples, then flags. `-h/--help`, `-v/--verbose`, `--version`, `--dry-run` where writes
happen. Subcommand style (`tool verb`) past ~4 operations.

**Errors are UX.** Message = what failed + why + the next command to try. Exit codes:
0 success, 1 expected failure, 2 usage error. Errors to stderr, data to stdout —
pipes must work (`--format json` for machines, pretty for humans; detect TTY).

**Progress & safety.** Long ops show progress; destructive ops confirm or require
`--force`; idempotent re-runs wherever possible; respect `NO_COLOR`, degrade without
color; never require interactivity in scripts (flags for everything).

## TUI

**Layout.** Panes with stable regions (status line, content, input); redraw without
flicker; handle resize. Density is fine; mystery is not — visible keybinding hints
(bottom line), `?` for the full map.

**Keys.** Arrow keys AND vim keys where the audience expects them; Esc backs out;
q quits with confirmation only if state would be lost; every action reachable without
a mouse.

**State.** Show mode/context clearly (what am I selecting? what happens on Enter?);
undo where destructive; preserve terminal state on exit (alt-screen discipline).
