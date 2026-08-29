---
name: board
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Glob
description: Use when you want this repo's pitches and plan slices shown as a kanban board, or when a card was moved and the markdown should catch up. Syncs both directions and leaves the markdown in charge.
---

# board

Sync this repo's `docs/pitches/`, `docs/plans/` and `docs/superpowers/plans/` onto a kanban board.
Invoked as `/hexagram:board` — plugin skills are namespaced by the plugin they ship in.

This is a **view over the markdown, not a second source of truth**. The files decide; the board
follows. The one field that travels the other way is `status:`, so that moving a card produces a diff
you can review instead of state stranded in a JSON file.

Step 4 of the loop in the `workflow` skill produces the slices this reads. **The board is optional and
the loop does not depend on it.**

## Prerequisite

```bash
cargo install kanban-cli kanban-mcp
```

That is the only one. The sync is stdlib Python 3 and targets the interpreter that ships with the OS
(3.9 on macOS), so there is nothing to install for it.

If `kanban` is not on `PATH`, every entry point here exits non-zero, says this, and **changes no file**.

## First run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/board/sync.py" --init docs .kanban.json Work HEX
```

Creates `.kanban.json` and seeds TODO / Doing / Complete, with the card prefix set **in the same call**.

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
---
```

Pitches keep the `status: active` they already use, which maps to Doing on the board.

## Letting Claude work the board

```bash
claude mcp add kanban -- kanban-mcp "$PWD/.kanban.json"
```

47 tools, roughly 8k tokens of schema. Read the board, move a card, then run the sync so the markdown
catches up and the move shows up in `git diff`.

⚠️ **Finding the next thing to do takes two calls.** `tool_list_cards` returns title, status and
priority but **not** the description, so the `Done when` is not in the list. Filter that list to
`Todo`, then `tool_get_card` the one you want — the description carries the file path and the command
that proves the slice finished.

## What it will not do

Sprints, story points, due dates, WIP limits, and cards for research or postmortems are all
deliberately absent — see the pitch. Cards are addressed **only by uuid**, never by the `PREFIX-N`
identifier, which upstream corrupts if a board's card prefix is changed after cards exist; a CI check
enforces that rather than trusting it.
