---
name: research
description: Use when a decision depends on something you do not know yet - whether a library does X, what a limit actually is, what something costs, how the industry solves this. Searches in English, keeps every source fetched as its own file, and writes the aggregate that unblocks the choice. Never asks permission to search.
allowed-tools: WebSearch, WebFetch, Read, Write, Bash, Glob, Grep
---

# research

Answer the question in `$ARGUMENTS` well enough to decide, and leave every source behind.

⚠️ **`$ARGUMENTS` is empty when this skill fires on its own** rather than being typed as a slash
command — the sentence above then has its object missing. When it is empty, take the subject from
the conversation instead, and if that is not clear either, ask for it in one line before writing
anything. (`${ARGUMENTS:-…}` does not help: the harness substitutes the bare name, not the brace
form.)


**Never ask permission to search.** The question was asked; searching is the answer to it.

## English, both halves

**Search in English, and write in English.** Not a style preference: the primary sources — the docs, the
changelog, the issue thread, the RFC, the source itself — are in English, and a translated
intermediary is a source with an extra author between you and the fact.

Search in another language only when the answer genuinely lives there: a local regulation, a
local-market price, a vendor that documents in one language. Say so in the note when it happens, and
**the note is still written in English** with the foreign literal quoted, not translated. See the
`language` skill for what to keep byte-identical.

## The shape on disk

**One directory per research, never a loose file.** A question worth researching is worth the sources
that answered it, and a single `.md` throws them away the moment the page changes.

```
docs/research/<topic>/
├── research.md          the aggregate: the question, the findings, the verdict
└── fetches/
    ├── <source-slug>.md one file per page actually read
    └── …
```

`<topic>` is a kebab-case slug in English, and it is what the whole thing is called from then on. Date
it as `YYYY-MM-DD-<topic>/` when the answer will age — a price, a limit, a vendor's behaviour.

**Research done because a client pays for the work branches with everything else**:
`docs/clients/<client>/research/<topic>/`, where a repo separates client work that way. See the
`workflow` skill.

⚠️ **A fetch file is a record, not a summary.** Keep what the page actually said, quoted. The reason to
keep it is that the page will change, be paywalled, or disappear, and then this file is the only
evidence the claim ever had.

### One fetch file per source

```markdown
---
tags: [fetch, <topic>]
source: https://…
fetched: YYYY-MM-DD
kind: primary | secondary | vendor | forum
---

# <page title>

> Fetched YYYY-MM-DD · <one line on what this source is and why it was read>

## What it says

<the relevant passages, quoted rather than paraphrased>

## What it does not say

<the thing you hoped it would settle and it did not>
```

**`kind` is worth the field.** A vendor's own pricing page and a forum answer are both evidence, and
they are not the same weight. Recording which is which is what lets a later reader re-weigh your
conclusion without re-doing the work.

### The aggregate

```markdown
---
tags: [research, <area>, <topic>]
status: active | superseded
decided: YYYY-MM-DD
---

# <the question, written as a question>

> Verdict in one line.

## What was blocking
## Findings
## Verdict
## What this does not establish
## Sources
- [Title](URL) — `fetches/<slug>.md` — what it actually supports
```

Every entry under Sources points at its fetch file. **A source cited without a fetch file was not
read**, and saying so is more useful than implying otherwise.

## Tags, so this is findable a year later

| tag | |
|---|---|
| `research` / `fetch` | what kind of file this is. Every file gets one |
| `<topic>` | the directory slug, on every file in the directory, so one query returns the whole set |
| `<area>` | the part of the system it touches: `area/infra`, `area/data`, `area/frontend` |
| `status/superseded` | added when a later research replaces this one. **The file stays** |

⚠️ **A research note is never deleted when the decision changes.** It becomes the record of why the
decision used to be different. Mark it superseded, link forward to what replaced it, leave it.

## Method

1. **Break the question into 2–5 specific queries.** One broad query returns the aggregators; specific
   ones return the docs.
2. **Run them in parallel**, then fetch the pages worth reading in full — and write each one into
   `fetches/` as you go, not at the end.
3. **Prefer primary sources.** Official docs, changelogs, the source itself. A blog post citing a doc is
   worth less than the doc.
4. **Cross-check anything load-bearing** against a second independent source, or against a measurement.
5. **Measure rather than cite where you can.** A number you produced beats a number you found, and it is
   the only kind that is true of *your* setup.

⚠️ **Say which numbers are measured and which are estimated.** A table where the reader cannot tell is
worse than no table.

⚠️ **Record what you could not establish.** "No primary source found for X" is a finding, and it saves
the next person the same dead end.

**Go looking for the strongest case against your own conclusion** when the answer matters. If you
cannot find one, say you looked. If you can, the note is better for carrying it, and sometimes the
verdict changes.

## Where it connects

Link the aggregate from whatever it unblocked — the decision record, the plan, the roadmap — with a
`[[wiki-link]]`. Research nobody can reach from the work it enabled gets redone by the next person who
needs it.

⚠️ **If the note stops being useful once the decision is made, it is research. If it will still be
useful a year from now on a different project, it is `docs/research/study/` instead.** Same shape,
different shelf. See the `workflow` skill.
