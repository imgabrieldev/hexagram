---
name: lint
description: Use when checking formatting, lint rules and types across a project, or before pushing. Detects the stack from the files that are actually present rather than being told, and reports per tool with file and line.
allowed-tools: Bash, Read, Glob
---

# lint

Run the format, lint and type checks for whatever this project actually is. Lint `$ARGUMENTS` if given,
otherwise everything — an empty `$ARGUMENTS` is the normal case when this fires on its own, and it
means the whole project.

⚠️ **This skill detects the stack. It is never filled in per project.** The version that shipped in the
old template opened with `## TODO: fill in with project-specific commands once stack is chosen`, and an
audit found it still saying exactly that in every project that had it, including a production service
with 32k lines and no linter at all. A placeholder that has to be filled in is a placeholder that never
gets filled in.

## 1. Detect, do not assume

```bash
ls -a | head -40
```

Then match on what is there. A project can be more than one of these:

| present | run |
|---|---|
| `pyproject.toml`, `ruff.toml`, `setup.cfg` | `ruff format --check .` · `ruff check .` · `mypy .` or `pyright` |
| `package.json` | its own `lint` / `format:check` / `typecheck` scripts first — read them before guessing |
| `Cargo.toml` | `cargo fmt --all -- --check` · `cargo clippy --all-targets --all-features -- -D warnings` |
| `go.mod` | `gofmt -l .` · `go vet ./...` · `golangci-lint run` if configured |
| `*.tf` | `tofu fmt -check -recursive` (or `terraform fmt`) · `tofu validate` per stack |
| `*.sh`, `.githooks/` | `shellcheck` on each, `bash -n` as the floor when shellcheck is absent |
| `*.md` and a `.vale.ini` | `vale` on the changed files |
| `Makefile` with a `lint` target | **that, first.** It is the project's own answer |

**Read the project's own scripts before inventing a command.** `package.json` naming its check
`typecheck` and you running `tsc --noEmit` instead is how the two drift.

⚠️ **`gofmt -l`, not `go fmt`.** The second rewrites files; the first lists what would change. A check
must not modify the tree.

⚠️ **A tool that is not installed is not a pass.** Report it as missing. `command -v` each one first and
say which checks did not run.

## 2. Never let a warning be free

```
npm run lint -- --max-warnings=0
cargo clippy … -- -D warnings
```

A warning that does not fail the build is not a warning, it is a comment. Where the project's own
script omits the flag, say so rather than silently adding it.

## 3. The house checks the tools will not catch

These are house rules, so no linter ships them. They are cheap greps and belong in the same run:

```bash
# layer violations — adjust the imports to the stack (the `architecture` skill)
! grep -rqnE '^\s*(import|from)\s+(sqlalchemy|fastapi|requests|boto3)\b' src/domain/
! grep -rqn 'from .adapters' src/application/
! grep -rqnE 'uuid4|random\.|datetime\.(now|utcnow)|time\.time' src/domain/
```

⚠️ **Wrap each in `! grep -q`.** A bare `grep` exits 1 when it finds nothing, so a CI step running it
raw **fails when clean and passes when dirty** — the exact inversion, and it looks like it is working.

## 4. Report

Per tool, in this order:

- **format** — how many files would change, and which
- **lint** — count, with `file:line` and the rule name for each
- **types** — count, with `file:line`
- **house greps** — which fired
- **did not run** — every tool that is not installed

Then one line: `all clean` or the total. **Never report "all clean" while a tool was missing** — say
`clean, but mypy is not installed`.

## When to run it

Before pushing, and before claiming work is done. It is cheap enough that the only reason to skip it is
that no tool is installed, which is itself the finding.
