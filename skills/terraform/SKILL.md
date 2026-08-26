---
name: terraform
description: >-
  Use when writing or reviewing infrastructure as code: stack layout, one directory serving several environments, remote state, when a resource earns its own module, and why infra does NOT use the hexagon.
---

# Infra Rules — OpenTofu

Infra is **not** the hexagon (that is for the code in `apps/`). It follows the Terraform convention: organized, modular, **never a monolithic `main.tf`**.

- **Tool:** OpenTofu (`tofu`), not Terraform. Pin the provider version in `versions.tf`; **commit `.terraform.lock.hcl`**.
- **No comments in `.tf`.** Not a single `#`. The *why* lives in the module README, in the pitch or in the research — not in the HCL. A `description` on a variable/output is not a comment: it is interface, it shows up in the plan, and it stays.
- **State:** remote (S3 + native `use_lockfile` locking, which needs OpenTofu ≥ 1.10), encrypted, versioned. **Never local.** One state `key` per stack.
- **Cloud account:** never a work or client account by accident. Name the intended profile in the project's `CLAUDE.md` and let the stack fail loudly on the wrong one. Provider-level `default_tags` where tags exist (`Project`/`Owner`/`ManagedBy`); each resource adds `Environment`/`Component`. Names per the `naming` skill.
- **Secrets:** by env or SSM Parameter Store — **never** in `.tf` nor in committed state. An identifier (account id, ARN, cluster id) is fine.

## Root layout — one file per subject

```
infra/
├── environments/                     # mirrors apps/, segment for segment
│   ├── <owner>/<project>/            # projects you own
│   │   ├── versions.tf     # terraform{}: required_version, required_providers (pinned), partial backend "s3"
│   │   ├── providers.tf    # provider config
│   │   ├── variables.tf    # root inputs
│   │   ├── outputs.tf      # root outputs
│   │   ├── main.tf         # ONLY module calls + wiring — not 40 resources
│   │   ├── backend.hcl     # bucket and, where the store is not AWS, endpoint; `key` comes from the Makefile
│   │   ├── prod.tfvars
│   │   ├── staging.tfvars
│   │   ├── README.md
│   │   └── .terraform.lock.hcl   # committed
│   ├── <group>/<name>/               # third-party mirror, same shape
│   └── bootstrap/                    # no environment, local state, applied once
└── modules/
    └── <name>/             # reusable/isolated unit
        ├── main.tf
        ├── variables.tf
        ├── outputs.tf
        ├── versions.tf     # its OWN required_providers — see below
        └── README.md
```

**`environments/` mirrors `apps/`.** The owner or the group keeps its segment on
both sides, so one `PROJECT` resolves the app directory and the stack with the
same lookup, and the day a second owner appears nothing has to be reorganised.

**A stack under neither an owner nor a group is not a project.** `bootstrap` is
the only one: it creates the bucket every other stack keeps its state in, so its
own state is local. It has no environment and is applied once. It stays **out of the Makefile** — run it with
`tofu -chdir=infra/environments/bootstrap` directly.

## How it is run

The `Makefile` at the root of the umbrella is the entry point. Nobody types `tofu init` by hand on a stack that has environments.

```bash
make plan  PROJECT=billing ENV=staging
make apply PROJECT=billing ENV=prod
make stacks                            # lists what exists on disk
```

## One directory, several environments

One stack per project, **not** one directory per environment. What separates the environments:

- **partial backend** — `key` outside `versions.tf`, passed in through `-backend-config="key=<owner>/<project>-<env>.tfstate"`
- **`<env>.tfvars`** per environment, with what actually changes (`env`, `hostname`, database size)
- **no `default`** on environment-specific variables — a default lets a `tofu apply` without `-var-file` push prod by accident

⚠️ **Always `tofu init` with `-reconfigure`.** The same directory serves staging and prod; without `-reconfigure` tofu reuses the backend from the last init and you plan against the wrong state. The Makefile does this in every target.

## Modules

- **Every module declares `required_providers`** with the full `source`, even when inheriting the root's config. Without it Terraform infers the provider from the resource prefix and assumes `hashicorp/<name>` — a second phantom provider is born in the lock file, and it does not receive the root's configuration.
- **A resource in a stack root is a module waiting to be written** — a stack's `main.tf` holds module calls and wiring, and nothing else. Same rule the code follows with ports and adapters (the `architecture` skill), in Terraform's vocabulary: a driven boundary is abstracted because it is a boundary, not because a second caller showed up.

  ⚠️ **This one has a window, and it closes at the first apply.** Before the first apply, extracting a resource into a module is a `git mv` — no state, nothing to migrate. After it, the address changes from `resource.x` to `module.y.resource.x`, which is a `moved` block per resource **applied against every state that calls it** — one per calling stack, with `count`/`for_each` indices to get exactly right or it plans a destroy, and the blocks stay until every caller has applied the new version — the vendor docs carve out exactly that case for private modules inside one organisation, which is what these are. So the boundaries get drawn now, deliberately, while it is free. Once state exists, "extract it anyway" stops being obviously right and the trade-off is a real one.

- **A single-resource module is legitimate when the resource *is* the whole conversation and the module adds something the caller would otherwise have to remember** — a `prevent_destroy`, a naming rule, a required companion. A module that only forwards arguments is a passthrough, and it fails a test worth applying: *if the module's name is the resource type minus the vendor prefix, it is adding nothing*. Azure Verified Modules states the same split better than most — one **primary** resource is fine, a wrapper is not. The vendor conflict below is the short form of a longer
  review of the published guidance.

  ⚠️ **This overrides published vendor guidance, deliberately.** OpenTofu's own docs say *"we do not recommend writing modules that are just thin wrappers around single other resource types… just use the resource type directly in the calling module instead"* — and the calling module is the root. HashiCorp ships the same text; AWS repeats it under the heading *"Don't wrap single resources"*; and **Cloudflare** has a section headed *"Avoid modules (or use them sparingly)"*. Note that OpenTofu's text is HashiCorp's, inherited through the fork, and AWS restates it — that is one argument cited three times, plus Cloudflare making a different one about drift in shared modules. The override is deliberate: their reasoning is about shared, versioned, logic-bearing modules, and these are local-path modules with no conditionals, in a provider that renamed 40+ resources in one major and bumped schema_version mid-minor — where a `moved` block written once inside an existing module covers every stack that calls it. But a rule that contradicts the tool's own manual has to say so.

- **Do not re-validate what the provider already validates.** A provider that ships `stringvalidator.OneOfCaseInsensitive` on its enums fires at `validate`, before any plan. ⚠️ Only for **known** values: an enum fed from an unset variable or another resource's attribute is null or unknown at that point and slips through to plan or apply. A `validation` block repeating the same list buys nothing and costs twice: it duplicates an enum that drifts the day Cloudflare adds a region, and a hand-written list is easily **stricter than the provider's** — `contains()` is case-sensitive, so a value the provider accepts case-insensitively gets rejected by the module. Validate what is *yours* (an `env` of `prod|staging`, a cross-variable rule like "this hostname must be inside that zone"); leave the provider's vocabulary to the provider.
- **A module is the default organization** — each block is a module with a clear interface (variables in, outputs out). `hostname-redirect` is the shape that passes the test above: a DNS record plus the rule that gives it meaning, which the caller would otherwise have to remember to pair. `r2-bucket` is the shape that fails it.
- A module receives **inputs**, exposes **outputs**, and has **no hidden coupling**. Name it for the thing (`managed-postgres`), never for the vendor's product name.
- A module is **small and focused** — one responsibility. A module that does too much is the infra version of the god-file.
- The **root** composes modules (the way `bin/` composes adapters): wiring, no business logic.


## Anti-patterns

- Everything in one `main.tf`; a `main.tf` full of raw resources instead of module calls.
- Local state; an unpinned provider; the lock file left out of the commit.
- A secret in `.tf` or in state.
- A hardcoded value that should be a variable (region, domain, account id → `variables.tf`/tfvars).
- A module drawn around a resource instead of around a **conversation**. One `report-archive` with bucket + lifecycle + policy, not three modules; one `hostname-redirect` with the record and the rule that needs it, not two. A single-resource module is fine when the resource *is* the whole conversation — what is not fine is splitting one conversation across several.
- Waiting for a second caller before extracting a module. See above: infra abstracts on the first use.
- A bucket name without an `<env>` segment: staging and prod cannot coexist without it (see the `naming` skill).
- A globally-namespaced bucket without an owner or account discriminator: the name collides with every other tenant's.
