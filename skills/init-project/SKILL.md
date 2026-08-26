---
name: init-project
disable-model-invocation: true
description: Use when starting a brand new project or repo, or when adopting the house style in an existing one. Writes the parts that have to live on disk - the docs vault, the commit-msg hook, the statusline, the gitignore - and wires the per-repo config a plugin cannot reach.
---

# init-project

Scaffold a repo with the house style. Invoked as `/hexagram:init-project` — plugin skills are
namespaced by the plugin they ship in.

**The rules are not copied.** They are skills in this plugin, installed once per machine, and a project
picks up whatever version is installed. What this skill writes is only what genuinely has to be on
disk: the vault, the hook, the statusline, the ignore file, and a `CLAUDE.md` that points here.

## Arguments

`$ARGUMENTS` is an optional project name; when it is empty, fall back to the directory's basename in
the shell. (`${ARGUMENTS:-…}` does not work — the harness substitutes `$ARGUMENTS`, not the
default-value form.)

## 1. Preflight — what is already standing

**Run this every time, including on a directory you have scaffolded before.** The whole point is that a
second run reports and changes nothing. Report the result before touching a file.

```bash
PROJECT_DIR="$(pwd)"

# the machine
for t in git jq npx; do command -v "$t" >/dev/null 2>&1 || echo "MISSING: $t"; done

# this plugin: installed, or only loaded for this session?
claude plugin list 2>/dev/null | grep -q 'hexagram' && echo "plugin: installed" || echo "plugin: not installed (running from --plugin-dir?)"

# the repo
if git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  [ -z "$(git -C "$PROJECT_DIR" rev-parse --show-prefix)" ] \
    && echo "repo: root" \
    || echo "repo: SUBDIRECTORY of $(git -C "$PROJECT_DIR" rev-parse --show-toplevel)"
  git -C "$PROJECT_DIR" rev-parse HEAD >/dev/null 2>&1 || echo "repo: no commits yet (unborn branch)"
  echo "hooksPath: $(git -C "$PROJECT_DIR" config --get core.hooksPath || echo '(unset)')"
  echo "identity:  $(git -C "$PROJECT_DIR" config --get user.email || echo '(inherits global)')"
else
  echo "repo: none — git init has to happen before the hook can be wired"
fi

# the scaffold
for f in .claude/settings.json .githooks/commit-msg .gitignore .mcp.json CLAUDE.md docs; do
  [ -e "$PROJECT_DIR/$f" ] && echo "exists: $f"
done
```

What each answer changes:

| finding | what it means |
|---|---|
| `MISSING: jq` | the statusline exits silently without it. Say so; do not install it for them |
| `MISSING: npx` | the vault MCP in `.mcp.json` cannot start. The scaffold still works; the MCP will not |
| `plugin: not installed` | the skills are loaded for this session only, so the `CLAUDE.md` this writes will point at skills the next session does not have. Flag it, offer to continue anyway |
| `repo: SUBDIRECTORY` | **stop.** Step 5 would repoint the *ancestor's* hooks. See the guard there |
| `repo: no commits yet` | fine, and expected. The hook only needs wiring, not a commit |
| `hooksPath` already set | **stop and ask.** Overwriting it silently disables whatever it points at |
| `identity: (inherits global)` | worth reporting: a personal repo inheriting a work address is a common and invisible mistake |
| `exists:` anything | go to step 3 and decide merge, overwrite or abort |

⚠️ **Report before acting, and stop on the two `stop` rows.** Everything else is information the person
running this wants regardless of whether anything gets written.

## 2. Resolve

```bash
PROJECT_DIR="$(pwd)"
PROJECT_NAME="$ARGUMENTS"; [ -n "$PROJECT_NAME" ] || PROJECT_NAME="$(basename "$PROJECT_DIR")"
TEMPLATE="${CLAUDE_PLUGIN_ROOT}/template"
```

## 3. Look before writing

Check what already exists:

```bash
ls -a "$PROJECT_DIR" | grep -E '^(\.claude|\.githooks|docs|CLAUDE\.md|\.mcp\.json|\.gitignore)$'
```

If anything is there, list it and ask: **abort**, **overwrite**, or **merge** (only write what is
missing). Default to merge. Never overwrite a `CLAUDE.md` or a `docs/` that has real content in it.

## 4. Copy

```bash
cp -Rn "$TEMPLATE/." "$PROJECT_DIR/" || true   # -n = merge; exits 1 when it skips, which is normal
```

The `.` on the source is required, or the dotfiles (`.claude/`, `.githooks/`, `.mcp.json`,
`docs/.obsidian/`) are silently left behind.

What lands:

```
.claude/settings.json       hooks + statusline
.claude/statusline.sh
.githooks/commit-msg        strips AI attribution from commit messages
.gitignore                  stack-agnostic, trim it once the stack is known
.mcp.json                   obsidian MCP → ./docs
CLAUDE.md                   project facts, and a pointer to this plugin
docs/                       the vault: architecture, research, plans, postmortem, roadmap, product
```

## 5. Substitute

`{{PROJECT_NAME}}` is the only placeholder, in exactly two files: `CLAUDE.md` and
`docs/architecture/ARCHITECTURE.md`. Both are markdown, so no escaping applies.

⚠️ **Do not use `sed -i ''`.** That form is BSD-only; on GNU sed the empty string is consumed as the
script and nothing is substituted, silently leaving `{{PROJECT_NAME}}` in the files. Write through a
temp file instead, and do it in one block so the variables are still set:

```bash
PROJECT_DIR="$(pwd)"
PROJECT_NAME="$ARGUMENTS"; [ -n "$PROJECT_NAME" ] || PROJECT_NAME="$(basename "$PROJECT_DIR")"
for f in CLAUDE.md docs/architecture/ARCHITECTURE.md; do
  sed "s|{{PROJECT_NAME}}|$PROJECT_NAME|g" "$PROJECT_DIR/$f" > "$PROJECT_DIR/$f.tmp" \
    && mv "$PROJECT_DIR/$f.tmp" "$PROJECT_DIR/$f"
done
```

⚠️ **Each Bash call is a fresh shell.** Variables set in an earlier step are gone, so every block that
needs `$PROJECT_DIR` recomputes it. An empty `$PROJECT_DIR` would make step 3 copy the template into
the filesystem root.

⚠️ **There is no `{{PROJECT_DIR}}`, and reintroducing one is a regression.** Hooks read
`$CLAUDE_PROJECT_DIR`; the statusline reads `.workspace.project_dir` from the JSON it already gets on
stdin. Both survive the project being moved, renamed or cloned to another machine. A baked-in absolute
path does not: it breaks the moment the repo is cloned, moved or renamed.

Verify:

```bash
grep -rn '{{PROJECT_' "$PROJECT_DIR/.claude" "$PROJECT_DIR/CLAUDE.md" "$PROJECT_DIR/docs"   # empty
```

## 6. Make it executable, and wire git

```bash
chmod +x "$PROJECT_DIR/.claude/statusline.sh" "$PROJECT_DIR/.githooks/commit-msg"
```

**The hook needs one `git config`, and this is the step people forget.** Git does not version
`.git/hooks`, so what gets versioned is the *path*.

⚠️ **Check for existing hooks BEFORE setting it.** `core.hooksPath` *replaces* `.git/hooks` rather than
adding to it, so a repo that already has one would silently lose it:

```bash
PROJECT_DIR="$(pwd)"
git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1 || { echo "not a repo yet"; exit 0; }

# rev-parse --git-dir succeeds in any SUBDIRECTORY of a repo too. Setting the config
# there hits the ancestor, and a relative core.hooksPath resolves at that repo's root,
# so the hook you just copied is inert and the ancestor's own hooks stop being read.
[ -z "$(git -C "$PROJECT_DIR" rev-parse --show-prefix)" ] || {
  echo "$PROJECT_DIR sits inside the repo at $(git -C "$PROJECT_DIR" rev-parse --show-toplevel)"
  echo "core.hooksPath is per-repo and resolves at that root. Run 'git init' here first."
  exit 1; }
HOOKS="$(git -C "$PROJECT_DIR" rev-parse --git-path hooks)"
# Already pointed here by an earlier run? That is a no-op, not a conflict. Without this test the
# second run of this skill aborts on its own first run, which trains you to click past the one
# warning that matters.
if [ "$(git -C "$PROJECT_DIR" config --get core.hooksPath)" = ".githooks" ]; then
  echo "core.hooksPath already .githooks — nothing to do"
else
  find "$HOOKS" -type f ! -name '*.sample' 2>/dev/null | grep . && { echo "existing hooks — ask first"; exit 1; }
  git -C "$PROJECT_DIR" config core.hooksPath .githooks
fi
```

`rev-parse --git-path` is used rather than `$PROJECT_DIR/.git/hooks` because in a worktree or a
submodule `.git` is a file, not a directory.

If the directory is not a repo yet, say so in the report: this has to run after `git init`, or the hook
is inert.

**A plugin cannot set this for you, but you can set it once per machine:**
`git config --global core.hooksPath ~/.githooks` applies to every repo. ⚠️ It **replaces**
`.git/hooks` rather than adding to it and git warns about nothing, so machine-wide it silently
disables any hook already installed there by another tool. It also defeats `init.templateDir`, whose
seeded hooks land in `.git/hooks` and stop being read. The per-repo form above is for a repo that
wants its own.

## 7. Report

- name, path, files written
- whether `core.hooksPath` was set, or that it still needs `git init` first
- **what came from the plugin rather than from disk**: architecture, naming, git, language, testing,
  clean-code, diagrams, workflow, terraform,
  setup-machine, research, postmortem, lint. Say this explicitly, because the absence of a
  `.claude/rules/` directory is what a returning reader will find surprising.
- next steps: fill the stack line in `CLAUDE.md`, fill `docs/architecture/ARCHITECTURE.md` once there is
  code to record, and trim `.gitignore` to the stack.

## Notes

- **The vault root.** `docs/` carries its own `.obsidian/`, so open `docs/` as the vault. If the project
  later wants the repo root instead (to get `[[links]]` into `CLAUDE.md` and the plans), move
  `.obsidian/` up and say so in `CLAUDE.md`. Pick one. Two vault roots over the same notes is how the
  Excalidraw plugin ends up installed in the vault that does not hold the diagrams.
- **`.claude/settings.local.json` is gitignored and stays that way.** Allow-rules accumulate by
  clicking, and a rule allowlisting a command that contains a token puts that token in the repo.
- An umbrella repo with sub-projects wants more than this: a `Makefile` driver, `infra/environments/`
  mirroring `apps/`, and the naming rules that make one `PROJECT` resolve app directory, stack,
  resource name and state key together. Ask for it and it gets scaffolded separately.
