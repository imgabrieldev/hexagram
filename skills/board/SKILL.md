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

Reports `N created, N updated, N moved, N written`.

### What becomes a card

| document | card |
|---|---|
| `docs/pitches/*.md` | **no card.** It is an epic — a grouping, not work — and it reaches the board as a `[label]` on its slices' titles. `README.md` and the `archive/` `future/` subfolders are skipped |
| `docs/plans/<feature>/slice-*.md` | a card, titled `[epic] Slice 2 — Rate limiting` |
| `docs/superpowers/plans/*.md` | a **top-level card**, no parent — a superpowers plan is one file with its tasks inside, so there is nothing for it to be a child of. `specs/` next door is not scanned: a spec is a design record, not work with a status |

| what it does | when |
|---|---|
| creates a card | a document has no `kanban:` key, **or** points at a card that no longer exists |
| retitles a card | the card's title differs from the document's heading. **One direction only** — `status:` is the sole field that travels back, so a title edited in the tool is drift and the document wins. This is what carries an epic label onto a board that already exists |
| moves a card | the file's `status:` changed and the file is newer |
| moves a card **between columns** | the card's column disagrees with its status. In kanban these are separate: setting a status does not place the card, and a board where everything sits in TODO is not a board. **A column with no `default_status` is left alone** — that is somewhere a human parked the card deliberately |
| writes the file | the card moved and the card is newer |

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

## An epic is a label, not a card

⚠️ **A pitch used to become a card**, carrying `status: active` into Doing, and everything awkward
about the board came from there: a WIP limit could not be set because the epic held the only slot, the
renderer needed an `EPIC` badge meaning *"do not read this as work in progress"*, and a repo's
Definition of Workflow had to write down that the epic does not count. Three patches for one mistake.

An epic is not work. It is a grouping, it already lives in a file, and it stays there. Its slices name
it in their own titles:

```
[checkout] Slice 2 — Rate limiting
```

The label is the **feature directory name** by default — the same name that already joins a pitch to
its slices. A directory named for a document is often too long to sit in every card title, so the
pitch can shorten it:

```yaml
---
status: active
epic: checkout       # optional. Defaults to the directory name.
---
```

The sync will not apply a label twice, so a title that already carries one is left alone. A slice in a
directory with no pitch keeps its own title — grouping is optional, and an ungrouped card is not
broken.

**Card relations are gone with it.** There is no parent to link to, so a sync is now **one pass**
rather than two: the second existed only because a pass that creates cards cannot also link them.

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

`show.py --next` does exactly that in one command, and is the faster route when you are at a terminal
rather than holding the MCP server open.

## Looking at it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/board/show.py" .kanban.json Work
```

Columns of cards, sized to the terminal. An **epic is marked** — a card with children — because
without that a Doing holding one epic and one task reads as two things in progress, which is the
opposite of what it means.

```
TODO · 1                     DOING · 2                    COMPLETE · 1
──────────────────────────   ──────────────────────────   ──────────────────────────
╭────────────────────────╮   ╭────────────────────────╮   ╭────────────────────────╮
│ ACME-3                 │   │ ACME-1            EPIC │   │ ACME-4                 │
│ Slice 2                │   │ Public API             │   │ Slice 3                │
│ Rate limiting          │   ╰────────────────────────╯   │ Health check           │
╰────────────────────────╯   ╭────────────────────────╮   ╰────────────────────────╯
                             │ ACME-2                 │
                             │ Slice 1                │
                             │ Auth endpoint with     │
                             │ token refresh          │
                             ╰────────────────────────╯
```

And the next thing to pick up, with what proves it done:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/board/show.py" .kanban.json Work --next
```

```
ACME-3  Slice 2 — Rate limiting

docs/plans/api/slice-2-rate.md

Done when: 429 after N requests
```

⚠️ **It only draws.** Moving a card stays a `status:` edit plus a sync, so a move lands in
`git diff` — a renderer that could also write would quietly become the second source of truth this
skill exists to avoid. A test asserts it never calls a writing subcommand.

`PREFIX-N` appears here and **only** here, for display. Cards are still addressed by uuid everywhere
else, for the renumbering reason below.

## Doing holds one card

Limiting work in progress is the one practice here that is not a preference. The Kanban Guide lists
it among the mandatory practices — *"Kanban system members must explicitly control the number of work
items in a workflow from started to finished"* — and the personal-kanban literature names what a
board without one becomes: *"a prettier task list"*, because four cards in Doing is not four tasks,
it is four unresolved contexts.

`--init` sets `--wip-limit 1` on Doing. One, because the audience is one person.

⚠️ **This was set, reverted, and only works because epics left the board.** While a pitch became a
card it sat in Doing, `kanban` counts cards rather than kinds, and the epic held the only slot — so
every task that wanted Doing was rejected at creation. The fix was never a bigger number; it was that
an epic is not work. With only tasks on the board, the cap means what it says.

Exceeding it is a real refusal, and the sync now says so instead of printing the tail of a card
description. The limit is set at init and never by the sync, so one you change later is never quietly
overwritten:

```bash
kanban .kanban.json column update "$COLUMN_ID" --clear-wip-limit
```

## Blocked keeps its column, and that is deliberate

`status: blocked` never moves a card. **A Blocked column is a widely-documented anti-pattern**: it
becomes a dumping ground, items go out of sight and out of mind, and — the argument that settles it —
it *"artificially allows you to raise your WIP limits and thus defeats the entire point of having
them"*. The practice instead is to leave the item where it is and mark it, keeping the blockage
visible inside the stage it happened in.

So a blocked card stays put and reports `Blocked` in its status. ⚠️ **On a board read by columns it
therefore looks like whatever column it sits in**, and a card blocked before it was ever started is
indistinguishable from one not yet picked up. Record the reason where a reader will find it — the
document, or the repo's log — because the board will not carry it.

## What it will not do

Sprints, story points, due dates, and cards for research or postmortems are all deliberately absent —
see the pitch. Dropping estimation holds up on its own terms: counting finished items forecasts about
as well as pointing them, and for one developer estimation has nobody to coordinate with.

Cards are addressed **only by uuid**, never by the `PREFIX-N` identifier, which upstream corrupts if a
board's card prefix is changed after cards exist; a CI check enforces that rather than trusting it.

**There are no tags.** `kanban card create` has no such field, so grouping lives in the markdown —
frontmatter `tags:`, which the vault can already query — and reaches the board only through the `#`
heading a card takes its title from.
