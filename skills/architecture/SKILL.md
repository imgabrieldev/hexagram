---
name: architecture
description: Use when writing or reviewing application code and a structural question comes up - where a file goes, whether a dependency needs a port, how many ports, how a use case gets its dependencies, what belongs in a shared library, or whether the core can be replayed. The Deterministic Hexagon.
---

# The Deterministic Hexagon

**Canonical spec: <https://imgabriel.dev/architecture/>. Read it once.** This skill is the enforced
summary: the invariants, the checks, and where a project records its own decisions.

⚠️ **That page returns 403 to an agent fetcher and 200 to a browser.** Cloudflare bot management
blocks the `ClaudeBot` and `Claude-User` signatures, so a plain fetch fails and the failure looks
like the page is gone rather than like a block. Fetch it with a browser User-Agent instead:

```bash
curl -sL -A 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/126.0 Safari/537.36' \
  https://imgabriel.dev/architecture/
```

If that also fails, **work from this skill and say you could not reach the canonical text** —
do not present the summary as if it were the spec.

> **Scope:** application code. Infrastructure follows Terraform module organization, not the hexagon.

## The one rule

Source dependencies point inward.

```
bin -> adapters -> application -> ports -> domain
```

Read `->` as "depends on". The domain is innermost and depends on nothing; ports depend on it, because
ports speak domain types.

The domain imports nothing outward. A driven adapter implements a contract the core owns. **Any change
that makes an arrow point outward is wrong**, whatever else it improves.

## Layout

```
domain/        pure. entities, value objects, rules, errors. stdlib only.
ports/
  driven/      what the app asks of the world: Store, Clock, Rng
  driving/     the use case API, only once two entry points share it
application/   use cases, one per operation. orchestrates domain and ports.
adapters/
  driving/     the world drives the app: http/, cli/     (group by INTERFACE)
  driven/      the app drives the world: store/postgres/ (group by RESOURCE)
bin/           composition root: builds adapters, injects, runs. NO logic.
```

**Four layers, always** — domain, ports, application, adapters — plus the composition root. They are
cheap, and uniformity is what a house style is for.

**Vocabulary: driving and driven**, everywhere. Never mix in input/output, primary/secondary or
inbound/outbound. Half the confusion with this pattern comes from three vocabularies in one repo.

**The grouping is asymmetric on purpose.** Driving groups by interface, because that is how the world
arrives. Driven groups by resource, so the second implementation lands beside the first.

## Ports

**Whether a driven dependency gets a port: always, from its first use.** A database, an HTTP API, a queue, the
filesystem, the clock. Not on the second use, not once a fake is needed, not once somebody announces
the swap. This breaks with the canon deliberately, and the spec says so out loud rather than glossing
it: the literature grounds abstraction in needing a test seam, and this house does not.

The rule of three governs **duplication**, never a boundary. Do not extract a shared helper before the
third caller, because until then you are guessing at the shape. A boundary carries no such uncertainty.

**How many: as few as the conversations you actually have.**

- Name the port for the **conversation**, never the technology: `Store`, never `PostgresStore`.
- **Ports speak domain types only.** A database-driver type or a wire format in a signature is a hole in the
  wall with a curtain over it.
- **Two ports that name one counterparty are one port.** The cheap check is a directory listing when the
  counterparty is reached one way. It breaks when the same counterparty is reached two ways — their
  queue for the request, their bucket for the document — and then the shared prefix in the port names is
  the only signal left. Shared counterparty is the signal; shared technology is noise.
- **The rule stops where a merge forces you to prefix.** Stores sharing one physical table can still be
  separate ports. What united them was the table, and which table a row lands in is the adapter's call.
- **A port that exists to contain a violation of the signature rule is the violation.** Model the
  missing fields on the entity instead.

## Wiring

**Dependency injection is a parameter, not a container.** A use case receives its ports and never
constructs an adapter. When it needs a second port, the parameters become a struct built once at the
root; from then on the signature stops changing as ports are added.

**Only the composition root constructs.** One place knows which concrete adapters exist. A branch there
on configuration is the root doing its job; a branch on anything else is application logic trying to
escape. No DI container: the root calling constructors in order is
the complete feature set, and the compiler checks it.

## The shared library

Transport machinery several adapters share (an HTTP client, a queue consumer, a database engine) is a
**library, not a layer**. Name it for what it is: `libs/http/`, never `libs/infrastructure/http/`, which
names the layer twice and the thing once.

⚠️ **No port and no adapter goes in there.** A port is a contract the core owns and the core lives in
the service. Move a store port up and its domain types follow, then the types those reference, and a
service that never touches that domain ends up compiling it. The service is one drawer and the library
is the other. There is no third.

## A fake is a real adapter

`memory/` and `mock/` are adapter directories like any other, not test-only code. An in-memory store is
the second implementation that proves the port is a port, and a mock adapter can legitimately carry a
journey in production while the real API is unreleased.

**The contract test lives at the port and runs against every implementation.** That is the only thing
that checks two adapters behave the same. See the `testing` skill for the shape.

## The deterministic core

Same seed plus same commands ⇒ same state and same hash, on every machine. Seven rules, argued in full
in the spec:

1. **No floats in state.** Integers or fixed point.
2. **Seed the randomness, behind a port.** OS entropy kills replay. Security tokens still come from the
   OS at the edge; the state never does.
3. **Ordered maps only.** Hash-map iteration order is unspecified in most languages and deliberately randomised in some.
4. **Total order on commands before applying.** Sort, then apply.
5. **Derive IDs, never draw them.** `hash(seed, key)`, not a v4 UUID.
6. **State is a fold.** Persist = seed + log; restore = replay.
7. **Hash the state every step.** Diverged state always shows as diverged hashes, and the first differing step says where to look.

## Verification

Layer violations are cheap to grep. ⚠️ `grep` exits 1 when it finds nothing, so a CI step running these
bare **fails when clean and passes when dirty** — wrap each in `! grep -q …`. Adjust the imports to the
stack:

```bash
grep -rnE '^\s*(import|from)\s+(sqlalchemy|fastapi|requests|boto3)\b' src/domain/   # must be empty
grep -rn  'from .adapters'                             src/application/  # must be empty
grep -rnE 'uuid4|random\.|datetime\.(now|utcnow)|time\.time' src/domain/          # must be empty
```

⚠️ **Structural ports have no `implements` to grep for.** A `Protocol` in Python or an interface in
Go is satisfied by shape, so text search cannot enumerate a port's implementations or prove that only
the root constructs one. And where the type checker is optional, an unannotated call site is checked by
nothing at all. Walk the syntax tree instead. The domain imports no adapter. Only use cases touch a
port. Only the root constructs one. No use case imports another use case. `import-linter` (Python),
`go-arch-lint` (Go) and ArchUnit do this; a few hundred lines of your own does too.

## Anti-patterns

- `adapters/*` imported in `application/` or `domain/`.
- An ORM, HTTP client or SDK call inside `domain/`.
- Business logic in an HTTP handler or a CLI command.
- A use case returning a framework type. Return a domain error and let the adapter map it.
- A port signature carrying an infrastructure type.
- A port abstracted only once a second implementation showed up.

## When not to do this

A prototype you will throw away, and pretending otherwise is how prototypes stop shipping. A pure
library with no I/O, because it has no boundary to abstract in the first place. That is the whole list.

## The project records its own decisions

This skill holds what is true in every project. What is true in **this** one goes in
`docs/architecture/ARCHITECTURE.md`: what already holds, when it was decided, where it diverges from
the spec and why, and the gaps it still has.

A rules file nobody opens governs nothing. A record of what the code already does gets read by the
person about to break it.
