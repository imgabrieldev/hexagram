---
name: language
description: >-
  Use before writing anything that lands in a repo: code, comments, docstrings, test names, docs, README, commit messages, branch names, resource names. Everything is English, and this covers what counts as an exception and how to sweep an existing repo.
---

# Language Rules

> **Everything that lands in the repo is written in English.**

The carve-outs below are not exceptions to that. A foreign-language string that is *quoted rather than
written* — a legacy screen's label, a line from someone else's source — is data being reported, and
reporting it accurately is what writing in English means here.

| | language |
|---|---|
| **all code** — identifier, comment, docstring, test description (`it(...)`, `describe(...)`) | English |
| **documentation** — `docs/`, README, DEVLOG, research, decision record, plan | English |
| **infra** — resource, bucket, secret path, module, variable | English |
| **repo and branch names** | English |
| **commit messages** | English |
| **data** — column names, enum values, provider slugs, partition keys | English |

"All code" means **every code file** — `.ts`, `.tsx`, `.astro`, `.py`, `.rs`, `.go`, `.mjs`, `.sh`, `Makefile`, config JSONC. No exception by file type and no exception by layer.

## Why

- **English is the universal language.** That is the whole of it, and it is decided at the workspace level rather than per project — a Brazilian-domain project does not get an opt-out, because the opt-out is what produced two spellings of the same idea across sibling repos.
- **One language removes a decision on every new line.** "Is this code or is this prose?" was the boundary that caused the most argument. There is no boundary now.
- **Documentation and comments leave the repo.** They become an issue, a pasted snippet, something read by someone who does not speak Portuguese. In English they stay legible.
- **Infra names have nowhere to hide.** A resource name is the only metadata that reaches a dashboard and an invoice on a provider with no tags. A single non-English noun dropped into an English pattern (`acme-billing-relatorios-prod`) reads as a typo forever.

## The chat is not the repo, and that is where the rule gets broken

The conversation has no language rule and does not need one. What has a rule is anything that **crosses from chat into the repo**.

⚠️ **The failure mode is not writing a Portuguese doc.** It is writing the doc in English and then proposing the commit message for it in the language of the conversation — the commit message is the last thing written and the easiest to forget. Same for a branch name typed mid-sentence.

## A quote is prose; a literal is data

The two look alike, and the difference is whether the foreign-language text is *something said* or *the artefact being described*.

| | |
|---|---|
| **translate** | anything said or written **by us** — a correction quoted in a DEVLOG entry or a decision record, a heading, a caption, a comment. Keep the attribution and the date; do not keep the original alongside |
| **keep byte-identical** | anything that **is** the thing being described — a legacy screen's literal labels, a string quoted out of someone else's source, a grep pattern that exists *to find* non-English names, a pt-BR search query used as an example of what a Brazilian user types. Translating these makes the document **wrong** |

When a kept literal is not already obvious, add a short English gloss in parentheses — a reader should never need the other language to follow the sentence. Foreign phrases in ordinary English use (*à la carte*) and proper nouns (São Paulo) are not foreign-language text for this purpose.

⚠️ **Gloss, do not infer.** A gloss states what the literal says. Anything beyond that is inference wearing translation's clothes, A gloss of `Saldo devedor` is "outstanding balance", not "outstanding balance, already overdue" — the second half is read off context the label never carried.

## Published history stays

Rewriting published history costs far more than it is worth — see the `git` skill. **The rule applies from the next commit onward.** Existing Portuguese commit messages, and postmortems that record what was true on the day they were written, stay as they are.

Renaming a doc to translate its filename is usually a bad trade too: shortest-form wiki-links resolve by file name, and the rename buys nothing a heading does not.

## Sweeping an existing repo

A retroactive sweep is a separate, deliberate job, not something to do in passing. What was learned running one:

- **Decide "quote vs literal" before dispatching anything.** It is the rule that makes the work tractable, and without it every ambiguous line becomes a fresh argument.
- **Reading beats grepping.** Placeholders, half-translated phrases and section headings often carry no accents, so no regex finds them. A word-boundary grep also produces false positives that inflate the count — `\bcom\b` matches `example.com`.
- ⚠️ **Consistency across slices is not delegable.** The same quoted sentence living in three files will come back rendered three different ways from three parallel workers. Reconciling them is the integrator's job, and it is the real cost of parallelising the sweep.
- **Verify what fails silently:** every fenced code block byte-identical to `HEAD` (they are copied source, and evidence), and no `[[note#heading]]` link anywhere before renaming a heading.

## Verification

```bash
# distinctly non-English markers in anything that lands in the repo
# (tune the word list to the language you are sweeping out; avoid short words
#  like "com" or "para" — they match hostnames and English text)
grep -rniE '\b(não|porque|também|então|nenhum|arquivo|pasta|ambiente|está)\b' \
  docs *.md Makefile --include="*" 2>/dev/null

# the last commit message
git log -1 --format=%B
```
