# Research

**One directory per research, never a loose file.** A question worth answering is worth the sources
that answered it.

```
research/
├── <topic>/
│   ├── research.md      the question, the findings, the verdict
│   └── fetches/
│       └── <source>.md  one file per page actually read, quoted not summarised
└── study/               understanding that outlives this project
```

Date the directory as `YYYY-MM-DD-<topic>/` when the answer will age: a price, a rate limit, a vendor's
behaviour.

**Why keep the fetches.** The page changes, goes behind a paywall, or disappears, and then that file is
the only evidence the claim ever had. A source cited with no fetch file was not read.

**Tags carry the retrieval.** `research` or `fetch` for the kind, the topic slug on every file in the
directory so one query returns the set, and an `area/*` for the part of the system. Mark a superseded
note `status/superseded` and leave it — it is the record of why the decision used to be different.

**`research/` answers a question that was blocking a choice. `study/` explains how something works.**
The test: if it stops being useful once the decision is made it is research; if it still helps a year
from now on a different project it is study.

See the `research` skill.
