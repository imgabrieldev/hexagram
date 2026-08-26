# Docs

This folder is an **Obsidian vault**. Open it directly (`File → Open vault → docs/`). `[[wiki-links]]`
resolve in Obsidian and through the `obsidian` MCP server declared in `.mcp.json`.

| folder | |
|---|---|
| `pitches/` | what a piece of work is for, written before it is researched or built |
| `architecture/` | the shape as built. `ARCHITECTURE.md` records what already holds and carries the decision log; `diagrams/` holds the pictures |
| `research/` | what is true, with sources. Add `study/` for understanding that outlives this project |
| `plans/` | one directory per feature, numbered vertical slices |
| `postmortem/` | what shipped, and what a wrong measurement cost |
| `roadmap/` | what is done and what is next |
| `product/` | per-feature product docs |

Plus three files at the root of this folder once work starts: `DEVLOG.md` (one line per session, only when something
went green), `PROGRESS.md` (the state), and `IDEAS.md` (parked, so they stop leaking into the current
slice).

## Conventions

- `[[wiki-links]]` in shortest form, no `.md`. Moving a note between folders breaks nothing.
- Frontmatter tags for cross-cutting search (`tags: [area/infra, status/active]`).
- A new note goes in the folder that matches its kind. If two fit, it is probably two notes.
- **Everything is in English.** See the `language` skill.
