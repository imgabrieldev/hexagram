# Installing kanban

`/hexagram:board` drives the `kanban` binary from [kanban-rs](https://github.com/kanban-rs/kanban).
A Claude Code plugin is files in a cache, not a package manager, so this binary cannot ship with the
plugin — it is installed once per machine.

**This file is written to be executed by Claude on the reader's behalf.** Work it top to bottom.
Read the state before changing it, and install only what step 1 reported missing.

## What the board actually needs

| crate | binary | needed for |
|---|---|---|
| `kanban-cli` | `kanban` | the sync. **Required.** Without it `sync.py` exits 127 and writes nothing |
| `kanban-mcp` | `kanban-mcp` | letting Claude read and move cards over MCP. Optional |
| `kanban-server` | `kanban-server` | the REST server. **Not used by this skill** — do not install it for the board |

Versions 0.9.0 of the three are what every claim in the `board` skill was measured against.

## 1. Read the state first

```bash
for b in kanban kanban-mcp cargo; do
  printf '%-12s %s\n' "$b" "$(command -v "$b" || echo MISSING)"
done
```

If `kanban` resolves, **stop — there is nothing to install.** Say so and go back to what was asked.

## 2. If cargo is missing, ask before installing Rust

⚠️ **Do not run this without the person saying yes.** It is a remote script piped into a shell, it
writes `~/.cargo` and `~/.rustup`, and it edits their shell profile. That is a far larger change to
someone's machine than "show me my board" asked for, and it is theirs to approve.

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
```

If they would rather not have a Rust toolchain at all, that is a complete answer: **the board is
optional and the workflow loop does not depend on it.** Say that and stop.

## 3. Install the crates

```bash
cargo install kanban-cli kanban-mcp
```

This compiles from source and takes minutes, not seconds. Say so before starting it rather than
leaving a silent terminal.

Drop `kanban-mcp` if the person only wants the sync — the board works without it, and the MCP server
costs roughly 8k tokens of tool schema in every context window that loads it.

## 4. Verify against the binary, not against this file

```bash
kanban --version
```

If that prints a version, `/hexagram:board` will run.

⚠️ **A shell opened before step 2 will not see the binary.** rustup adds `~/.cargo/bin` to the
profile, and an already-running Claude Code session inherited the old `PATH`. If `kanban --version`
says "command not found" immediately after a successful install, the install is fine and the session
is stale — restart it, or `export PATH="$HOME/.cargo/bin:$PATH"` for the current one.

## Then

Back to the `board` skill for `--init`, which creates `.kanban.json` and seeds the columns.
