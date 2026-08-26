# hexagram

One house style, installed once per machine instead of copied into every repo.

Named for the shape at the middle of it: a hexagon of ports and adapters with a deterministic core.
Checked free on npm and crates.io before adopting. ⚠️ A hexagram is strictly a six-pointed star rather
than a hexagon, so the name is evocative, not literal. Recorded here so nobody reopens it.

Rules copied into each new project drift, and a copy nobody opens governs nothing. A plugin fixes
that: install once, every repo gets the same version, change it in one place.

## Install

```bash
/plugin marketplace add imgabrieldev/hexagram
/plugin install hexagram@hexagram
```

Restart, and that is the whole setup. **You do not install updates.** A `SessionStart` hook fetches
and applies them in the background, at most once a day; the next session start says so and asks for a
restart. Turn it off with `HEXAGRAM_NO_SELF_UPDATE=1`.

Claude Code has its own path for this, and it is worth knowing why the hook is here anyway: marketplace
auto-update is a setting on **your** machine, not something a marketplace can ship — third-party
marketplaces default to off, and `marketplace.json` has no field to change that. It is also gated
behind Claude Code's own binary self-updater, so it stays inert inside the desktop app and on
package-manager installs even once you enable it. If you would rather the platform did the updating,
enable auto-update for this marketplace in `/plugin`, set `FORCE_AUTOUPDATE_PLUGINS=1` where the
self-updater is off, and set `HEXAGRAM_NO_SELF_UPDATE=1` so the two do not overlap.

There is nothing to release, either. `plugin.json` carries no `version` field on purpose, so the
plugin tracks the commit SHA and **a push is the release** — with a version pinned, every machine
sits on "already at the latest version" until someone remembers to bump it, which is the failure this
avoids.

One thing the update cannot reach, by design rather than oversight: a session already running keeps
the version it started with.

## What it carries

**Skills**, which load when the task matches rather than burning context every session:

| skill | |
|---|---|
| `architecture` | the Deterministic Hexagon. Canonical spec: <https://imgabriel.dev/architecture/> |
| `language` | everything that lands in a repo is English, and what counts as an exception |
| `testing` | what to test at which layer, and whether a test kills the mutant its name describes |
| `clean-code` | naming, function and file size, error handling |
| `diagrams` | C4, Excalidraw in an Obsidian vault, and who owns the file |
| `naming` | what a thing is called and where it lives; which renames are a data migration |
| `git` | committing, branching, submodule ordering, rewriting history |
| `terraform` | infrastructure as code, which does **not** use the hexagon |
| `workflow` | pitch → research → decision → plan → implement → postmortem |
| `research` | a decision depends on something you do not know yet |
| `postmortem` | something shipped, or a claim turned out wrong |
| `lint` | format, lint and type checks, stack detected not configured |
| `pitch` | `/hexagram:pitch` writes step 1 of the loop: the problem, the scope's out-list, and what would count as done |
| `init-project` | `/hexagram:init-project` scaffolds a repo with the parts that must live on disk |
| `setup-machine` | `/hexagram:setup-machine` brings a machine up to the house plugin set, then turns off the MCP servers this machine does not want |

**A hook** that refuses a commit carrying AI attribution, for commits made through Claude Code.

**A template** that `/hexagram:init-project` writes. ⚠️ It includes a `.mcp.json` declaring
[`@bitbonsai/mcpvault`](https://github.com/bitbonsai/mcpvault), a third-party MIT package fetched from
npm on first use to expose `docs/` as an Obsidian vault. Pin or remove it if you would rather not.
What lands: the docs vault, the `commit-msg` hook, the statusline, the
gitignore, and a `CLAUDE.md` that points at the skills instead of restating them.

## What it cannot carry, and why

- **A `CLAUDE.md`.** It only loads from the repo, from `~/.claude/`, or from managed policy. So
  `/hexagram:init-project` writes a small one that names the project and points here.
- **Rules that auto-load from a URL.** MCP *resources* and *prompts* are opt-in: the model has to
  reference them. An MCP server's *instructions* do load at session start, but briefly. Skills are the
  closest thing, and they beat a CLAUDE.md that loads every session whether the task needs it or not.
- **A git `commit-msg` hook, on its own.** A plugin cannot write to your git config, so installing one
  is never automatic — it happens because you run `/hexagram:init-project`, which copies the hook and
  sets `core.hooksPath` for that repo. You can also do it by hand, and not only per repo: `git config --global core.hooksPath ~/.githooks` covers every repo
  on the machine. ⚠️ It **replaces** `.git/hooks` rather than adding to it, and git warns about
  nothing — so machine-wide it silently disables any hook already sitting in a `.git/hooks` anywhere
  (lefthook and pre-commit install theirs there; husky is safe, it sets `core.hooksPath` in the repo's
  own config, which beats `--global`). It also defeats `init.templateDir`, whose seeded hooks land in
  `.git/hooks` and stop being read. Use one or the other, not both.
- **The statusline.** A plugin's `settings.json` only accepts `agent` and `subagentStatusLine`.

The plugin hook and the git hook are not redundant. The plugin one fires when Claude Code commits; the
git one fires no matter who commits. Only the second is enforcement.

## Layout

```
.claude-plugin/plugin.json        manifest
.claude-plugin/marketplace.json   so the repo is its own marketplace
skills/<name>/SKILL.md
hooks/hooks.json                  PreToolUse safety net
template/                         what /hexagram:init-project writes into a repo
```
