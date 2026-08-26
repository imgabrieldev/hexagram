---
name: naming
description: Use when deciding what to call something or where it lives - a folder, a repo, a cloud resource, a state key, a secret path, a hostname, or a slug that ends up in a database row or a partition key. Some renames are a git mv and some are a data migration; this is how to tell which before you choose.
---

# Naming and boundaries

## The rule that hurts if you get it wrong

> **A slug that crosses the repo boundary is data, not a folder name.**

When the same literal appears in a code module, in a database row, in an object-storage partition and
in an API response, renaming it is a **data migration**, not a `git mv`. It is the only naming decision
with this asymmetry: getting it right costs nothing, and every later change costs a backfill of every store that holds the literal. Some renames further down are expensive too; none is expensive on the *first* write.

**Pick those once, before the first write, and never again.** Everything else on this page is cheap to
change later.

## The path composes the name

Every path segment becomes a name segment, and the owner goes in front, in the repo name and in the
resource name alike.

```
apps/<owner>/<project>       →  <owner>-<project>       →  <owner>-<project>-<resource>-<env>
apps/<group>/<name>          →  <owner>-<group>-<name>  →  <owner>-<group>-<name>-<resource>-<env>
```

**One `<project>` should resolve four things.** If it does not, the name is wrong:

```
PROJECT=<project>                  # owner branch
  APP_DIR  = apps/<owner>/<project>
  STACK    = infra/environments/<owner>/<project>
  resource = <owner>-<project>-<resource>-<env>
  state    = <owner>/<project>-<env>.tfstate

PROJECT=<group>-<leaf>             # group branch
  APP_DIR  = apps/<group>/<leaf>
  STACK    = infra/environments/<group>/<leaf>
  resource = <owner>-<group>-<leaf>-<resource>-<env>
  state    = <owner>/<group>-<leaf>-<env>.tfstate
```

The owner prefixes the *name* in both branches even where it is absent from the path. That is
deliberate: the owner is who the thing belongs to, and a resource name has to say so wherever it is
read.

**`infra/environments/` mirrors `apps/`, segment for segment.** Not flattened. The owner or the group
keeps its segment on both sides, so one lookup resolves both trees, and the day a second owner appears
nothing has to be reorganised.

**A stack under neither an owner nor a group is not a project.** Bootstrap stacks, account-wide stacks
and shared certificates have no environment and no app directory. They stay out of the root `Makefile` that drives the stacks, and get
run directly.

**The second segment may change axis, and that is fine.** In one branch it is the owner, in another it
is a category. Both compose the same way. Keep the group **singular** (`client/`, not `clients/`) so it
enters the composition without a translation step.

## Resource names

```
<owner>-<project>-<resource>-<env>
```

**Why the environment goes in the name, even where tags exist:** the name is what shows up *before* the
tag everywhere that matters when things go wrong. A console dropdown, a log line, a bucket listing, a
plan message. A tag is something you filter by after having already clicked. And a bucket name is
globally unique on some providers, so without the environment in the name staging and production do not
coexist even in theory.

⚠️ **Some providers have no tags at all.** There the name is the only metadata that reaches the
dashboard and the invoice. Either the environment is in the name or it does not exist.

**Why the owner prefix:** accounts get shared. In a list of workers or buckets, the prefix is what
separates yours from everything else, and it does it for free, in alphabetical order.

**Infra names are English**, including the `<resource>` segment, even when the domain is not.

## Repo names

`<owner>-<project>`, and **the organisation does not replace the owner.** A repo name travels alone all
the time: a search result, a clone URL, the directory left behind by `git clone`, a line in
`.gitmodules`. A repo called `web` says nothing outside its org.

**The exception is a public package.** There the name published to a registry *is* the public identity,
and a house prefix leaks internal structure to strangers. Those go bare.

**A fork keeps the upstream name** until it grows a purpose of its own here. When it does, it enters the
pattern, and it is named for its **function**, never for the relationship: `catalog`, not `mirror` or
`fork`. That it is a fork the badge already says; to filter, use a topic.

## No acronyms

An acronym passes only when it is an industry standard: `id`, `api`, `sql`, `html`, `rest`. A
project-local acronym needs a glossary, and cryptic abbreviation is already forbidden by the
`clean-code` skill.

Three things make it worse than it looks:

1. **Acronyms collide, and often inside your own domain.** Check before adopting one, the way you would
   check a package name.
2. **Measure the length before assuming it is the problem.** Most limits are generous, but GCP project IDs cap at 30 characters and Azure storage accounts at 24 with no hyphens permitted at all, which breaks a hyphen-joined scheme outright. Most limits are far above what the
   full name costs.
3. **Two spellings cost more than they save.** "Acronym here, full name there" becomes a decision on
   every new line and diverges on its own. One literal is what makes `grep` work.

**The rule is about the identifier.** The acronym is fine in prose: a title, running text, a commit
message.

## Reserved words

A project slug must never look like a resource. Reserve at least:

```
api  admin  auth  app  docs  assets  static  cdn  mail  status  www  raw
```

## Slug format

A slug that reaches a resource name or a hostname must be `kebab-case`: underscores are illegal in
bucket names and DNS labels. **Store one canonical `kebab-case` literal** and convert to `snake_case`
at the code boundary that needs an identifier; the conversion is mechanical and is not a second name.
The rule below is the older, weaker form and applies only to a slug that never leaves the codebase.

`snake_case` when the slug is both a code identifier and a partition value, because a hyphen breaks the
first. `kebab-case` for anything that lives only in a URL or a resource name. Pick per slug and write
down which, because the two are not interchangeable once written.

Strip punctuation from the source name. A dot is a path separator in almost everything.

## Documented exceptions

Every naming scheme needs a short list of things that are deliberately outside it. Write yours down,
with the reason, or somebody will "fix" them:

1. **The umbrella repo** (the owner-named repo holding `apps/` and `infra/`, often with projects as submodules) — it *is* the owner, so there is no project to append.
2. **Hostnames** — user-facing, no prefix.
3. **A state bucket** — a globally unique name holding the state itself; renaming is a backend
   migration, not an apply.
4. **A validated certificate** — renaming in IaC is destroy plus create.
5. **A stack with no application** — infrastructure *about* other projects rather than *of* one.

## Verification

```bash
# nothing loose at the root of apps/
ls -d apps/*/ | grep -vE '^apps/(<owner>|<group>)/$'          # must be empty

# no acronym where the full name belongs
grep -rn '"<acronym>-' infra/ --include="*.tf"                # must be empty

# no non-English noun in a resource name
grep -rnE '"<owner>-[a-z0-9-]*-(<word-one>|<word-two>)-' infra/ --include="*.tf"   # must be empty
```
