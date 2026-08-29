---
name: board
allowed-tools: Bash, Read, Write, Glob
description: Use when picking up work and needing to know which slice is next and what proves it done, after finishing one so the board catches up, when a card was moved and the markdown should follow, or when this repo's pitches and plans should be shown as a kanban board. Syncs both directions and leaves the markdown in charge.
---

# board

Sync this repo's `docs/pitches/`, `docs/plans/` and `docs/superpowers/plans/` onto a kanban board.
Invoked as `/hexagram:board` — plugin skills are namespaced by the plugin they ship in.

This is a **view over the markdown, not a second source of truth**. The files decide; the board
follows.

**If you are an agent picking up work**, you do not need this skill to read the board — attach the MCP
server below and query it. Invoke this skill when the markdown and the board have to be reconciled:
after you change a `status:`, after a card was moved, or when a document has no card yet. The one field that travels the other way is `status:`, so that moving a card produces a diff
you can review instead of state stranded in a JSON file.

Step 4 of the loop in the `workflow` skill produces the slices this reads. **The board is optional and
the loop does not depend on it.**

## Prerequisite

```bash
cargo install kanban-cli kanban-mcp
```

That is the only one. The sync is stdlib Python 3 and targets the interpreter that ships with the OS
(3.9 on macOS), so there is nothing to install for it.

If `kanban` is not on `PATH`, every entry point here exits non-zero, says so, and **changes no file**.

**Not everyone has a Rust toolchain, and the line above assumes one.** `install.md` beside this file
is written to be executed rather than read — check first, ask before installing Rust, install, verify
against the binary:

```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/board/install.md"
```

`/hexagram:setup-machine` reports the same gap from the other direction: `kanban` is this plugin's one
`requires` entry, and the manifest carries the command that fixes it.

## First run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/board/sync.py" --init docs .kanban.json Work HEX
```

Creates `.kanban.json`, seeds TODO / Doing / Complete with the card prefix set **in the same call**,
and puts a **WIP limit of 1 on Doing** — see *Doing holds one card* below.

Cards are created in the column whose `default_status` matches, so the first sync already looks like a
board rather than one long TODO list.

⚠️ **Add `.kanban.json` to `.gitignore`.** It is derived, so losing it costs one command — and a
tracked JSON board is a merge conflict waiting to happen. `/hexagram:init-project` writes this line
already.

## Every run after

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/board/sync.py" docs .kanban.json Work
```

Reports `N created, N updated, N moved, N written, N linked`.

### What becomes a card

| document | card |
|---|---|
| `docs/pitches/*.md` | a parent card. `README.md` and the `archive/` `future/` subfolders are skipped |
| `docs/plans/<feature>/slice-*.md` | a child card of that feature's pitch |
| `docs/superpowers/plans/*.md` | a **top-level card**, no parent — a superpowers plan is one file with its tasks inside, so there is nothing for it to be a child of. `specs/` next door is not scanned: a spec is a design record, not work with a status |

| what it does | when |
|---|---|
| creates a card | a document has no `kanban:` key, **or** points at a card that no longer exists |
| moves a card | the file's `status:` changed and the file is newer |
| moves a card **between columns** | the card's column disagrees with its status. In kanban these are separate: setting a status does not place the card, and a board where everything sits in TODO is not a board. **A column with no `default_status` is left alone** — that is somewhere a human parked the card deliberately |
| writes the file | the card moved and the card is newer |
| links | a slice card is not yet a child of its pitch card |

Orphans and conflicts go to stderr and **nothing is ever deleted**. Two files claiming the same
`kanban:` uuid is reported and neither is written — copy-pasting a slice is how that happens.

A tie between the card's `updated_at` and the file's mtime goes to **the file**, deliberately: the
markdown is the source of truth, so where the evidence is ambiguous the tool yields.

## What lands in the frontmatter

```yaml
---
status: doing        # todo | doing | blocked | done. Absent reads as todo.
kanban: 8cabb3d6-…   # the card uuid, written by the sync. Do not edit it.
board: false         # optional. Keeps this document off the board entirely.
---
```

Pitches keep the `status: active` they already use, which maps to Doing on the board.

**`board: false` exists for one shape that otherwise appears twice.** A superpowers plan broken into
slices is on the board as itself *and* as its eight children, and the duplicate is noise no column
policy fixes. `no`, `skip` and `off` read the same way; anything unrecognised **keeps** the card, so a
typo cannot make work vanish silently.

⚠️ **It stops a card being created; it does not delete one.** Adding `board: false` to a document that
already synced leaves its card behind, and the run then reports it as an orphan — removing it is a
deliberate `kanban card delete`.

## Working the board as an agent

```bash
claude mcp add kanban -- kanban-mcp "$PWD/.kanban.json"
```

47 tools, roughly 8k tokens of schema. Read the board, move a card, then run the sync so the markdown
catches up and the move shows up in `git diff`.

⚠️ **Finding the next thing to do takes two calls.** `tool_list_cards` returns title, status and
priority but **not** the description, so the `Done when` is not in the list. Filter that list to
`Todo`, then `tool_get_card` the one you want — the description carries the file path and the command
that proves the slice finished.

## Doing holds one card

`--init` sets a **WIP limit of 1** on the Doing column, and that is the one practice here which is not
a preference. The Kanban Guide lists controlling work in progress among the mandatory practices —
*"Kanban system members must explicitly control the number of work items in a workflow from started to
finished"* — and the personal-kanban literature names what a board without one becomes: *"a prettier
task list"*, because four cards in Doing is not four tasks, it is four unresolved contexts.

One, because the audience is one person. And it is not imported ceremony: every hexagram repo already
carries the same rule in prose — *frozen scope per checkpoint*, *one green per session*, *one thing at
a time*. The limit only makes it mechanical, which is the same move the sync already makes for
`status:`.

The guide leaves the mechanism open — *"any way that Kanban system members deem appropriate"* — so this
is a default, not a law:

```bash
kanban .kanban.json column update "$COLUMN_ID" --clear-wip-limit
```

⚠️ **It is set at `--init` and never by the sync**, so a limit you changed later is never quietly
overwritten.

## What it will not do

Sprints, story points, due dates, and cards for research or postmortems are all deliberately absent —
see the pitch. Dropping estimation holds up on its own terms: counting finished items forecasts about
as well as pointing them, and for one developer estimation has nobody to coordinate with.

Cards are addressed **only by uuid**, never by the `PREFIX-N` identifier, which upstream corrupts if a
board's card prefix is changed after cards exist; a CI check enforces that rather than trusting it.

**There are no tags.** `kanban card create` has no such field, so grouping lives in the markdown —
frontmatter `tags:`, which the vault can already query — and reaches the board only through the `#`
heading a card takes its title from.
