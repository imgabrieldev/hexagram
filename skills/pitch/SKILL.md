---
name: pitch
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Glob, WebSearch, WebFetch
description: Use when starting a piece of work, before it is researched or built. Writes the pitch that says what the problem is, what is proposed, what is explicitly out of scope, and what would count as done.
---

# pitch

Write the pitch for the work described in `$ARGUMENTS`. Invoked as `/hexagram:pitch` — plugin skills
are namespaced by the plugin they ship in.

This is step 1 of the loop in the `workflow` skill. It exists because a pitch is the cheapest place to
be wrong: arguing with a paragraph costs a paragraph, and arguing with a half-built feature costs the
build.

## Arguments

`$ARGUMENTS` is the feature, in the author's words. When it is empty, ask what the work is before
writing anything — a pitch invented from an empty prompt is a template with a filename.

## Where it lands

`docs/pitches/<slug>.md`, with `<slug>` kebab-case, derived from the feature name.

**Work that exists because a client pays for it branches the whole tree**:
`docs/clients/<client>/pitches/<slug>.md`, where `<client>` is that client's folder name under
`docs/clients/`. House work stays at the top level.

**Leave `kanban:` empty.** The `board` skill fills it with the card uuid on its first sync, and
nothing else should ever write it. A repo that does not use the board simply leaves it blank.

⚠️ **A new pitch is always born in the root of that folder with `status: active`**, because it is
being written now, about work that matters now. `future/` and `archive/` are where a pitch *moves*
later, never where it starts. If those folders exist, `docs/pitches/README.md` says what each one
means in this repo.

## The document

````markdown
---
tags:
  - pitch
  - <area or feature tags>
status: active
kanban:
---

# Pitch — <Feature Title>

## Problem

What is wrong today, and who it is wrong for.

## Solution

What gets built, at the level someone could argue with.

## Architecture

Components, data flow, integrations. The shape, not the code.

## Schema / Data Changes

Migrations, config, state affected. **Which of these are one-way** (see the `naming` skill: some
renames are a `git mv` and some are a data migration).

## Interfaces / APIs

| Method | Route / Entry point | Auth | Description |
|--------|---------------------|------|-------------|

## Scope

### In Scope
- [ ] ...

### Out of Scope
- ...

## Research Needed
- [ ] ...

## Testing Strategy

What proves it works, at which layer. See the `testing` skill.

## Success Criteria
- [ ] ...
````

## How to fill it

1. **Write the Problem section properly**, from what the author actually said. It is the only section
   whose absence makes the rest worthless.
2. Fill any other section the conversation already answers. **Leave the rest as the template** rather
   than inventing content — an invented scope is worse than an empty one, because it looks decided.
3. ⚠️ **Scope is two lists or it is one wish.** The out-list is what stops the work growing quietly
   between the pitch and the plan, so push for it even when the author only offered the in-list.
4. Every open question becomes a line under **Research Needed**, and those lines are what step 2 of
   the `workflow` loop consumes.
5. Link related notes with `[[wiki-links]]`, shortest form, no `.md`.
6. Report the path you wrote, and say what is still a template so the author knows what to fill.

**Get agreement on the pitch before moving on.** It is a proposal, not a record.
