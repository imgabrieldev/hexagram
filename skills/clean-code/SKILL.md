---
name: clean-code
description: Use when naming a variable, function, type or file, deciding how big a function or file should get, handling an error, or reviewing code for readability. House style for how code reads.
---

# Clean Code Rules

Cross-cutting rules that apply to every layer. Enforce in code review and pre-PR checks.

## Naming

### Forbidden abbreviations

Avoid cryptic short names. Use the full word.

| Bad | Good |
|---|---|
| `stmt` | `statement` |
| `ctx` (when not a real context type) | `context` / `request_context` |
| `cnt` | `count` |
| `idx` | `index` |
| `cfg` | `config` |
| `req` | `request` (OK as fn parameter `req: Request`) |
| `resp` | `response` |
| `qty` | `quantity` |
| `ph` | `placeholders` |
| `ws` | `workspace` / `websocket` — say which |
| `ts` (when not the literal `Timestamp` type) | `timestamp` / `checked_at` |
| `db2`, `db3` | `secondary_db`, `audit_db` — give it a purpose-revealing name |
| `kv` as a store name | `cache`, `sessions`, `flags` — say what it holds |

### Allowed short names

Canonical and OK:

- `id`, `db` (as a parameter type / binding), `e` (single-line closures), `ok`, `err`, `ms`, `ip` (when it really is an IP)
- Loop counters `i`, `j` in tight numeric loops (rare)
- Language-idiomatic types: `fn`, `impl`, `mod` keywords; `T`, `U`, `K`, `V` for generics

### Function / method names

- `verb_noun` for actions: `create_user`, `archive_order`, `enforce_quota`
- `noun` or `is_x` / `has_x` / `should_x` for predicates: `is_admin`, `has_expired`
- No fluff prefixes: `my_`, `do_`, `handle_xxx_helper` — just say what it does

## Function size

- **Soft limit:** 80 lines per function body. Split if larger.
- **Hard limit:** 200 lines. Refactor blocker — split before merging.

**Handler functions** are the most common offenders. If a handler is over 80 lines, it's doing the use case's work inline — extract.

Exceptions:
- `match` / `switch` arms with many short branches (each arm is 1-3 lines)
- Generated code (don't edit by hand)

## File size

- **Soft limit:** 500 lines. Refactor candidate above this.
- **Hard limit:** 1500 lines. Block PRs that create files this large.

Typical offender: one repository file implementing many port traits. Split per port, and keep the
house layout while doing it — a directory per resource, a file per technology
(`adapters/driven/order_store/postgres.rs`), never one flat `db_orders.rs`. Splitting by
technology instead of by resource trades one problem for a layout the `architecture` skill
forbids.

## Error handling

### Use typed domain errors, not stringly-typed

```
// BAD
fn process() -> Result<(), String> { ... }

// GOOD
enum OrderError {
    NotFound(String),
    UpstreamUnavailable(String),
    DatabaseError(String),
}

fn process() -> Result<(), OrderError> { ... }
```

String errors lose type info and force every caller to do ad-hoc `.to_string()`. A typed enum lets adapters map errors to HTTP / CLI output at the boundary.

### Never `.unwrap()` / `.expect()` / `panic!` on runtime-failable operations

- `request.json().unwrap()` → should return 400
- `params.get("id").unwrap()` → should return 400
- `headers.set(...).unwrap()` → propagate or log + skip

The only `unwrap` allowed is on operations that **provably** cannot fail — compile-time constants, or after explicit validation.

### Ignoring errors requires justification

```
// BAD — silent swallow
let _ = cache.invalidate(key).await;

// GOOD — explicit intent
// best-effort cache invalidate; next read refreshes
let _ = cache.invalidate(key).await;

// GOOD — log on failure
if let Err(e) = cache.invalidate(key).await {
    log::warn!("cache invalidate failed: {e}");
}
```

### Map errors to typed HTTP statuses at the boundary

- Permission denied / resource locked / scope missing → **403**
- Missing / invalid / expired credentials → **401**
- Not found → **404**
- Validation failure → **400**
- Conflict (duplicate, version mismatch) → **409**
- Server error → **5xx**

Keep this mapping in one place per adapter (middleware or shared helper), not scattered across handlers.

## Random IDs and tokens

- **IDs** (non-cryptographic): use `uuid::Uuid::new_v4()` / `crypto.randomUUID()` / `uuid.uuid4()`.
  ⚠️ **Not inside a deterministic core.** There an id is *derived* — `hash(seed, key)` — because a drawn
  one cannot be replayed. See the `architecture` skill; its CI check greps `uuid4` out of `domain/`
- **Security tokens:** use a CSPRNG — `getrandom`, `crypto.getRandomValues()`, `secrets.token_urlsafe()`. Never `Math.random()` / `random.random()` (Mersenne Twister). Rust's `rand::random()` *is* CSPRNG-backed, but say so at the call site with `OsRng` or `getrandom` so the guarantee is visible

## Dead code

Before merging, clean up:

- Handler / endpoint / route with no caller or wiring (orphaned `pub async fn foo_handler(...)` with no route registration)
- Port traits with no implementation or no use case calling them
- An in-memory or canned adapter that no composition root wires and no test injects. ⚠️ Liveness is
  about callers, not about tests: a fake is a production adapter (see the `architecture` skill), so
  "no test uses it" is not the question
- DTO files that just re-export domain types
- Commented-out blocks "for later" — delete or move to a TODO issue

Run dead-code linters when available: `cargo +nightly udeps`, `knip` (JS/TS), `vulture` (Python), `go vet -all ./...`.

## Comments

Default: **no comments**. Good names + small functions are self-documenting.

Write a comment only when the *why* is non-obvious:

- A hidden constraint not visible in the signature
- A subtle invariant the reader would violate by accident
- A workaround for a specific bug (link to the issue)
- Behavior that would surprise a reader

**Don't** write comments that:

- Explain *what* the code does — the code already does
- Reference the current task, fix, or callers (belongs in the PR description)
- Are out-of-date (worse than no comment)

## Testing cross-reference

See the `testing` skill, which requires:

- Every new domain file with executable code has unit tests
- Every new use case has at least one test (happy path + one error case)
- Every new HTTP endpoint has an E2E test
- Pure helpers extracted from framework-bound code get their own unit tests
