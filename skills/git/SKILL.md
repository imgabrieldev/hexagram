---
name: git
description: Use when committing, branching, pushing, working with submodules, or rewriting history. The commit-message policy and why it is enforced by a hook rather than by prose, plus the submodule ordering that breaks a fresh clone when you get it backwards.
---

# Git

## A commit carries no AI signature

**Never end a commit message with `Co-Authored-By:`**, and never add any other marker that an AI wrote
it: no "Generated with", no robot emoji, no tool name in the trailer.

This **overrides the harness default**, which asks for the trailer.

**Why it weighs more than it looks:** the trailer creates no GitHub *contributor* — that list is
computed from author and committer, not from trailers — but the **commit page renders the co-author as
a linked profile anyway**. That is visible, permanent, and not undone by rewriting history alone:
rewritten commits stay reachable by SHA in cached views until the host purges them, which is why the
cheap-looking fix is often recreating the repository.

⚠️ **This rule is not enforced by being written here.** A rule in a file applies only where the file
was copied. What enforces it is `.githooks/commit-msg`, wired with `git config core.hooksPath
.githooks` — or `--global` pointing at a shared directory, which covers every repo on the machine at
once. It strips the trailer no matter who commits. The plugin's
`PreToolUse` hook is a second net and covers only commits made through Claude Code.

If a commit deserves credit, the credit is its author's. A **human** co-author trailer is untouched.

## Who changes what

Set this per project, in `CLAUDE.md`, and keep it explicit. A reasonable default:

| | |
|---|---|
| **without asking** | `docs/`, `CLAUDE.md`, `README.md` |
| **only when asked** | anything inside an application or library — not just source, but generated files, lockfiles, CI and config too · infrastructure code · repository operations (create, transfer, rename, delete, move a folder, add or remove a submodule) |

The boundary is about **acting unasked**, not about capability. When a restructuring, an infra change or
a repo operation is requested, doing it is welcome.

**Merging and pushing are the owner's call.** Never do either unasked.

## Submodules

Two orderings are not optional:

1. **Commit in the submodule first, then bump the pointer in the umbrella.** A pointer bump without the
   commit underneath is a dangling gitlink.
2. **Push the submodule before the umbrella.** Push the umbrella first and its gitlink names a commit
   that exists only on your machine, so a fresh `clone --recursive` breaks.

```bash
git -C "$sub" push origin main   # first
git add "$sub" && git commit
git push origin main              # then
```

Check whether a clone would resolve:

```bash
sha=$(git ls-tree origin/main "$sub" | awk '{print $3}')
git -C "$sub" fetch -q origin
git -C "$sub" merge-base --is-ancestor "$sha" origin/main \
  && echo ok || echo "MISSING: $sha is not on the submodule's remote"
```

⚠️ **Reachable, not equal.** Comparing the gitlink to the remote's *tip* fails on any umbrella that
deliberately pins an older commit, which clones perfectly. And always print on failure: silence is
indistinguishable from a typo in the path.

**Moving a submodule is `git mv`** — it rewrites `.gitmodules` and the gitlink together. Follow with
`git submodule sync`. Never hand-edit `.gitmodules` for a move; use `git submodule set-url` to change a
remote.

⚠️ **A submodule whose history is large and generated wants `shallow = true`** in `.gitmodules`, or
every clone drags the whole thing along.

⚠️ **A private submodule needs a token in CI.** The default checkout credential does not reach a second
private repo, and the failure reads as a missing directory rather than a permission error.

## Rewriting published history

Force-push only on an explicit request, and say plainly what it destroys first. Prefer
`--force-with-lease` over `--force`.

If a submodule's history is rewritten, **every gitlink in the umbrella that references it must be
remapped**, not just the tip, or checking out an older umbrella commit and running `submodule update`
fails. `filter-branch` leaves the old refs under `refs/original/`, so the old-to-new map is:

```bash
paste <(git rev-list --reverse refs/original/refs/heads/main) <(git rev-list --reverse main)
```

⚠️ **That map is only correct if the rewrite preserved the commit count.** With `--prune-empty` or a
path filter that empties commits the two lists differ in length and `paste` misaligns from the first
dropped commit onward, producing a map that looks right and remaps every later gitlink wrong. Prefer
`git filter-repo`, which writes an exact old-to-new map to `.git/filter-repo/commit-map`.

## Branches

`<type>/<slug>`, where `<type>` is one of `docs`, `feat`, `chore`, `fix`. This is the **branch**
taxonomy; commit subjects use `<area>` instead (below). Branch before working on a default branch.

## Commit messages

`<area>: <what changed>`, lowercase, no trailing period. English, like everything else that lands in
the repo. The subject says what changed; the body says why, and why not the alternative.

⚠️ **The commit message is the last thing written and the easiest to write in the language of the
conversation.** That is the specific way the language rule gets broken.
