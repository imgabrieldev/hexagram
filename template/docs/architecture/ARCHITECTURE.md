---
tags:
  - architecture
  - status/active
---

# Architecture — {{PROJECT_NAME}}

> **This file records what already holds in the code, so nobody re-decides it per feature.**
>
> It is not a rules file and it is not aspirational. The house style lives in the `hexagram`
> plugin and in <https://imgabriel.dev/architecture/>. What goes here is this project: the shape
> that is actually built, when each piece was decided, where it diverges from the house style and
> why, and what is still wrong.
>
> Delete this quote block once the file has real content.

## How to keep this file

Four habits, and they are the whole point of the format:

- **Record, do not prescribe.** Present tense, about the code as it stands. "Driven adapters group by
  resource" beats "driven adapters should group by resource."
- **Date every decision.** `Decided YYYY-MM-DD.` A reader needs to know whether a line predates the
  thing they are looking at.
- **Declare divergence from the house style, with the reason.** A divergence stated is a decision. A
  divergence unstated is a bug somebody will helpfully fix.
- **End with your own gaps.** A file that lists its own violations gets trusted. One that does not gets
  read once.

---

## The shape

*What the tree looks like and what each directory is for. Only what exists.*

```
(empty until there is code to describe)
```

## Ports

*One line per port: the conversation it names, its adapters, and why it exists. The interesting entry
is the port somebody will want to split or merge, with the reason it stayed as it is.*

| port | conversation | adapters |
|---|---|---|
| | | |

## Decisions

*Context, decision, and what it rules out. Newest first. A superseded entry stays, marked.*

### D1 — `<title>`

**Context.**

**Decision.** Decided YYYY-MM-DD.

**Rules out.**

## Divergences from the house style

*Where this project does something the house style says not to, and the argument. If the argument is
good enough, it belongs upstream in the plugin instead of here.*

| what | house style says | here | why |
|---|---|---|---|
| | | | |

## Known gaps

*The violations that exist right now. Being honest here is what makes the rest of the file credible.*

- [ ]
