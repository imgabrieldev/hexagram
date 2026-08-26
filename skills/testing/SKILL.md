---
name: testing
description: Use when writing a test, deciding what to test at which layer, choosing between a fake and real infrastructure, or checking whether a test actually kills the mutant its own name describes.
---

# Testing Rules

When implementing a feature, endpoint, or use case, **write tests as part of the implementation**. Tests ship with the code — they are not a follow-up task.

## What to test

### Layer 1: Domain unit tests (mandatory)

Every `domain/` file with executable code needs tests covering:

- Entity validation, constructors, serialization
- Business rules and calculations
- Error cases and edge conditions
- Pure helpers (date formatters, slug normalizers, score calculators, parsers)

Zero mocks required — domain is pure, tests call functions with fixture inputs.

### Layer 2: Use case tests (mandatory)

Every file under `application/` needs at least:

- One happy-path test
- One error-case test (what happens when a dependency fails)

Tests use **mock port implementations** — never hit real DB / cache / queue / external APIs.

Pick one layout per project and stick to it:

- **Inline:** `#[cfg(test)]` mod / `describe(...)` block at the bottom of `application/create_user.rs`
- **Centralized:** `tests/application/` or `tests/integration.rs` with one file per use case

### Layer 3: Integration tests (when applicable)

For adapters:

- DB operations against a test database (separate from dev)
- External APIs against a recorded fixture or local mock server
- Full pipeline tests: extract → transform → persist → query

### Layer 4: E2E / smoke tests (mandatory for new public endpoints)

Any new public or internal HTTP endpoint gets at minimum:

- Happy path
- Auth guard (401 / 403)
- Main error case (400 / 404 / 409)

Run E2E against staging / a fresh local environment, never against production.

## Fakes are adapters, not test code

An in-memory implementation of a port is a **driven adapter like any other**: it lives beside the real
implementation under the resource it serves, it is compiled into the binary, and it is the second implementation that
proves the port is a port. Do not gate it behind test-only compilation — a canned adapter can
legitimately serve a path in production before the real one exists.

```
adapters/driven/order_store/
├── memory.rs      the fake
└── postgres.rs    the real one
```

Grouped by **resource**, not by technology, so the second implementation lands beside the first where
the comparison is easy to read. See the `architecture` skill.

## The contract test lives at the port

One suite, written against the port, run against **every** implementation. It is the only thing that
checks two adapters behave the same, and it is what makes swapping one for the other a decision rather
than a gamble.

```
tests/ports/driven/order_store.rs     ← runs twice: memory, postgres
```

The fake passes it because it is an implementation, not because it was written to agree with the test.


## Prove it with a mutant

A green test proves the code passes *that* test. It does not prove the test asserts the right thing.
The question that separates proof from decoration is: **if I break what this test says it protects,
does it go red?**

Break it on purpose, then count how many tests die **and in which files**. A test that does not kill
the mutant its own name describes is **worse than no test** — it occupies the place of the proof, and
nobody looks again.

The four failures that catch the most:

- **One-sided anchor.** An assertion that matches the right value *and* a wrong neighbour. Ask whether
  the fixture distinguishes the right key from the wrong one, or whether both give the same result.
- **A comment with two claims needs two mutants.** One of the two is usually never measured.
- **The nail must hold the query, not a copy of it.** Holding a hand-written copy of the SQL, or even
  the exported constant, does not hold what production ran.
- **Some behaviour no final state distinguishes** — the order of two writes, an unawaited promise. It
  dies only to a test that watches the *sequence*, or the moment of resolution.

Report the deterministic part of a count: a number that varies between runs is information about the
test, not noise. And distrust a mutant that kills too much, because a crash, path shadowing and
cross-test poisoning all inflate it. Look at **which** tests fell.

## Extract pure helpers for testability

If a function calls framework types (HTTP `Response`, DB `Connection`, SDK clients), it's hard to unit-test. Extract the pure logic:

```
// BAD — can't test without a real HTTP response
fn map_auth_error(err: Error) -> HttpResponse { ... }

// GOOD — pure function, testable
enum AuthErrorKind { Incomplete, Forbidden, Unauthorized }

fn classify_auth_error(msg: &str) -> AuthErrorKind {
    if msg.contains("incomplete") { return AuthErrorKind::Incomplete; }
    if msg.contains("Permission") { return AuthErrorKind::Forbidden; }
    AuthErrorKind::Unauthorized
}

// Wrapper maps to HTTP — not unit-tested (integration handles it)
fn map_auth_error(err: Error) -> HttpResponse {
    match classify_auth_error(&err.to_string()) {
        AuthErrorKind::Incomplete => HttpResponse::Forbidden().json(...),
        // ...
    }
}
```

Same pattern for any pure transformation currently requires a framework type input.

## Rules

- Test both **happy path AND error cases** (minimum one each per use case)
- Name tests descriptively: `test_create_order_rejects_duplicate_ref`, not `test_1`
- Use async test runners where needed: `#[tokio::test]`, `@pytest.mark.asyncio`, Jest's default
- Mock external APIs — **never hit real third parties** in unit or integration tests
- Use a **separate test database** for integration tests (never shared with dev)
- **No placeholder tests.** `assert!(true)` or empty `describe()` blocks are dead code — delete or write real tests
- New use case shipped without a test: **blocked** at pre-PR review
- E2E tests run fast enough to block on CI; integration tests might run on a schedule if slow

## Common violations to avoid

- "We'll add tests later" — tests ship with the code, full stop
- A use-case test that reaches real infrastructure instead of the in-memory adapter
- Placeholder tests (`fn test_compilation() { assert!(true); }`) — delete them
- New endpoint without an E2E test
- Pure logic buried inside framework-bound functions — extract and test the pure part
- A test whose name describes a mutant it does not kill
- A causal claim in a comment with no mutant behind it
- A use case test that constructs its own adapter instead of receiving one — importing the in-memory
  adapter to *inject* it is the point; constructing a real one inside the test is what defeats DI

## Fast test loop

Aim for a single-command test run that covers domain + use cases in <5 seconds. If it's slower:

- Split domain tests (fast) from integration tests (slow) into separate commands
- Run fast tests on save (watch mode), slow tests on commit / CI
- Profile: `cargo test -- --report-time`, `pytest --durations=10`, etc.

Slow tests kill the TDD loop — guard them behind a marker (`#[ignore]`, `@pytest.mark.slow`, `describe.skip`) and run them separately.
