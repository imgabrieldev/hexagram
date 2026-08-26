---
name: postmortem
description: Use when anything is finished and worth a record - a plan or slice completed, a bug fixed, an incident closed, a migration done, or a claim that turned out wrong. Writes what it cost to learn, tagged so it is findable when the same thing happens again.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# postmortem

Write the record for `$ARGUMENTS` into `docs/postmortem/<slug>.md`.

⚠️ **`$ARGUMENTS` is empty when this skill fires on its own** rather than being typed as a slash
command — the sentence above then has its object missing. When it is empty, take the subject from
the conversation instead, and if that is not clear either, ask for it in one line before writing
anything. (`${ARGUMENTS:-…}` does not help: the harness substitutes the bare name, not the brace
form.)


**Everything that is already in the past belongs here**, not only outages:

| kind | tag | when |
|---|---|---|
| a plan or a slice finished | `kind/plan` | the checkpoints are green and the thing runs |
| a bug fixed | `kind/bugfix` | especially one that took a while to find |
| an incident | `kind/incident` | something broke in front of someone |
| a migration or a move | `kind/migration` | data moved, a service moved, a rename landed |
| **a claim that was wrong** | `kind/wrong-claim` | you asserted something, acted on it, and it was false |

⚠️ **The last one is the one people skip, and it is worth the most.** Shipped code explains itself; a
wrong measurement leaves nothing behind unless you write it down, and it is exactly the mistake that
repeats.

## Tags, so this is findable when it recurs

The point of a postmortem is being found by the person about to make the same mistake. That only
happens if it is tagged for the situation, not for the feature.

```yaml
---
tags:
  - postmortem
  - kind/bugfix              # from the table above
  - area/infra               # the part of the system
  - <topic>                  # the thing itself: dns, submodules, cold-start
closed: YYYY-MM-DD
cost: "a day"                # optional, and worth it when it was real
---
```

⚠️ **Tag the failure mode, not just the component.** `area/infra` finds it when you are working on
infra. `dns` finds it when the next thing is a DNS problem, which is when you actually need it.

## Before writing, gather what is true

Do not write this from memory. Memory is what produced the wrong claim in the first place.

```bash
git log --oneline -20                    # what actually landed, and when
git diff --stat "$before"..HEAD          # the size of it
```

Re-run the tests and quote the real numbers. **A count carried over from another document is how a
postmortem becomes fiction** — if the suite says 626 today, say 626 today, not what the roadmap said
last week.

## The shape

```markdown
---
tags: [postmortem, kind/…, area/…, <topic>]
closed: YYYY-MM-DD
---

# <what this is about>

> Closed YYYY-MM-DD · <repo>@<sha> · plan: [[…]] · follows [[…]]

## What was claimed, or what was planned
## What is actually true
## The mistakes, in the order they were made
## What worked
## What did not
## What changed so it cannot recur
## Still open
```

For the wrong-claim kind, head it with the verdict and the price, because that is what a reader scans
for:

```markdown
> Claim: false · Cost: <instances, hours, a day — what it actually cost>
```

## The section that earns the document

**"What changed so it cannot recur" is the only part with leverage.** Everything above it is history.
Write it as a table, because the useful form is a pairing:

| was | is now |
|---|---|
| an SSH command somebody ran by hand | a line in the provisioning template |
| a rule written in a doc | a hook that runs |
| a number quoted between documents | a command in the checklist |
| a path written out by hand | a path derived from the script's own location |

⚠️ **If that table is empty, the postmortem is not finished.** A retrospective with no change behind it
is a diary entry, and the same thing happens again.

## Two habits that keep these honest

⚠️ **Concluding from absence is not concluding.** "No errors and memory free" rules memory out. It does
not rule anything in. Say which it is.

⚠️ **A measurement that is not instrumented is an opinion.** If a finding rests on watching something
and forming an impression, say so, and say what instrumenting it would have cost.

**Record the episode you cannot explain rather than tidying it away.** An anomaly with no model is an
operational fact: it happened, it can happen again, and forcing it to fit the model is how the next
person trusts a model that does not hold.

## For a plan or a slice, specifically

The plan already said what would be built. The postmortem says what building it taught, which is a
different document — so do not restate the plan:

- **which checkpoints moved, and which quietly did not**
- **what the plan got wrong**, since a plan written before the work always gets something wrong
- **what was discovered that no checkpoint asked for** — usually the most valuable part
- the decisions that were born during the work and belong in `ARCHITECTURE.md` instead

## When it closes a pitch, the pitch moves with it

A postmortem that ends a piece of work started by a pitch takes the pitch with it, so the pair reads
as one thing a year later:

1. Write the postmortem as `<slug>.md` in the `postmortem/` folder.
2. **Move the pitch beside it** as `pitch-<slug>.md`, and link it from the postmortem with
   `[[pitch-<slug>]]`. The pitch is what was promised; the postmortem is what happened. Separated,
   the first one reads as a plan that is still live.
3. Re-point the `[[wiki-links]]` that named the pitch where it used to be.

## Where it goes

`docs/postmortem/<slug>.md`. Link it from the plan or the decision record it closes, and from the
roadmap if it changed what comes next. See the `workflow` skill for how it sits in the loop.

⚠️ **A postmortem stays in the same branch as the work it closes.** Where a repo separates client work
under `docs/clients/<client>/`, the postmortem for a client pitch goes in
`docs/clients/<client>/postmortem/` and **never** in the house folder.
