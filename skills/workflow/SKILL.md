---
name: workflow
description: Use when starting a feature, deciding which document to write, or closing work out. The pitch to research to decision to plan to implement to postmortem loop, what each document is for, and which step is safe to skip.
---

# Feature workflow

```
pitch  →  research  →  decision  →  plan  →  implement  →  postmortem
```

Each step produces a different artifact answering a different question. Skipping one is fine when the
question it answers is already settled. Skipping one because it feels slow is how the answer gets
invented later, under pressure, by whoever is holding the keyboard.

## 1. Pitch — what the work is for, and what would count as done

`docs/pitches/<feature>.md`, before anything is researched or built:

- the problem, and who has it
- the solution proposed, and the shape of the architecture it implies
- the interfaces and APIs it touches
- scope, both halves: what is in, and what is explicitly out
- the questions that need answering before this is buildable, which become step 2
- how it gets tested, and what success looks like

Get agreement on the pitch before moving on. A pitch is cheap to argue with; a half-built feature is
not.

**Work that exists because a client pays for it branches the whole tree**: `docs/clients/<client>/pitches/`,
and the same below for research, plans and postmortems. House work stays at the top level.

## 2. Research — what is actually true

For every non-trivial question the work depends on, write it down in `docs/research/<topic>/`, one directory per research with every source kept under `fetches/`.
The `research` skill does this end to end.
A research note is written to unblock a choice: it compares options, checks feasibility, does the math,
and ends in a verdict.

**Gate the assumptions that could sink the design.** Before building on one, write the probe that would
disprove it: what it costs, what "done" looks like, and what each answer changes. A probe result without
an independent oracle is an opinion: something other than the thing under test has to say whether the answer is right — a reference implementation, a checksum, the vendor's own tool.

⚠️ **A research note is not deleted when the decision changes.** It becomes the record of why the
decision used to be different.

Long-lived understanding that outlives this project goes in `docs/research/study/` instead. The test:
if the document stops being useful once the decision is made it is research, and if it still helps a
year from now on a different project it is study.

## 3. Decision — what was chosen, and what that closes off

Add an entry to the `## Decisions` section of `docs/architecture/ARCHITECTURE.md`: context, decision,
what it rules out. Dated, and **inserted at the top** — newest first, so the section reads in reverse
chronological order.

If a proposal needs an audience — a client, a team that has to approve it — write that document for
that audience. Do not pretend it is the record; the record is here.

⚠️ **A superseded decision stays, marked.** Knowing why an alternative lost is worth as much as knowing
why the winner won, and it stops the same argument reopening in three months.

## 4. Plan — in what order it gets built

`docs/plans/<feature>/slice-NN-<name>.md`. A plan is a directory of numbered vertical slices, each
small enough to ship, each ending in a command whose output is the pass or fail. See
`docs/plans/README.md`.

Get agreement on the plan before writing production code.

## 5. Implement

Follow the slices in order. Tests alongside the code, never as a follow-up.

**One green per session.** Every session ends with at least one binary thing that works: a passing test,
a bench number, an endpoint that answers. Then one line in `docs/DEVLOG.md` and a mark in
`docs/PROGRESS.md`.

**A new idea that does not fit the current slice goes to `docs/IDEAS.md`.** That is the whole
anti-scope-creep mechanism and it costs one line.

## 6. Postmortem

`docs/postmortem/<slug>.md` when something ships, and also when a measurement turns out to be wrong.
The second kind is worth more. The `postmortem` skill carries the shape and the
two habits that keep these honest.

Shape that earns its keep:

- what was claimed, and what is actually true, with numbers
- the mistakes in the order they were made
- what worked, and what did not
- **what changed so it cannot recur** — ideally a table of "was a manual step → is now a line of code"
- what is still open, and why

⚠️ **A measurement that is not instrumented is an opinion**, and concluding from absence is not
concluding. "No errors and memory free" rules memory out. It does not rule anything in.

## The two folders this loop does not produce

`roadmap/` answers "what is done and what is next". It is a view, rewritten rather than appended, so it
goes stale in silence and is worth re-deriving from the repo instead of editing in place. `product/`
holds per-feature product docs, which arrive from outside this loop entirely.

## What is safe to skip

| situation | start at |
|---|---|
| a pitch exists and still describes the work | 2 |
| the question is already answered in `docs/research/` | 3 |
| the decision is recorded and still holds | 4 |
| a plan exists and its slices still describe the work | 5 |
| typo, small refactor, obvious bugfix | 5, and no ceremony |

**Never start production code with an open question the work depends on**, and **"build X" is not
permission to start at 5**: with no pitch, the first artifact is the pitch, and the trivial change is
the exception. Everything else is a judgment about what is already settled.
