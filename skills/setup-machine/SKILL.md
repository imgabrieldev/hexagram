---
name: setup-machine
disable-model-invocation: true
description: Use when setting up Claude Code on a new machine, or when checking whether an existing setup still matches the house plugin set. Reports what is already there, says what would land before landing it, installs the set from plugins.json, and turns off the MCP servers this machine does not want.
---

# setup-machine

Bring a machine up to the house plugin set. **Report before changing, and change nothing that was
not asked for.** Run on a machine that is already set up, this must be a no-op that prints a diff.

The set lives in `plugins.json` beside this file. **Edit that, not this.** It records facts about
each plugin: what it `delivers`, what it `requires` on PATH and the `install` that provides it,
whether it `ships_mcp` and over what `transport`, and any `caveat` that cannot be checked.

## The one decision this skill exists to make

A plugin is installed for what it delivers — skills, commands, agents, hooks, an LSP declaration.
An MCP server is the part that is not free: whatever its transport, it pays for its tool definitions
in **every context window** and holds a connection to authenticate and keep alive.

So the question is never "install this plugin or not". It is **"keep this plugin's servers or not"**,
and Claude Code answers it directly:

```jsonc
// ~/.claude/settings.json
"deniedMcpServers": [
  { "serverName": "plugin:cloudflare:cloudflare-api" }
]
```

The plugin still installs, its skills still load, and that server never starts.

⚠️ **Only the exact name works.** Measured: `plugin:cloudflare:*`, a bare `cloudflare-api`, and
`{"pluginName": "cloudflare"}` each deny nothing and fail silently — five servers before, five
after. The name is `plugin:<plugin>:<server>`, exactly as `claude mcp list` prints it. Because a
typo is indistinguishable from a decision, **generate this list; never type it.**

⚠️ **This is per SERVER, not per plugin.** That matters: `cloudflare` ships five servers of which one
answers unauthenticated and four do not, so the right answer is to deny four and keep one — a
distinction no plugin-level switch can express.

## 1. Report what is there

```bash
for t in claude git python3 curl; do command -v "$t" >/dev/null || echo "MISSING: $t"; done
claude plugin list
claude mcp list
```

Resolve the manifest once; every block below uses `$MANIFEST`:

```bash
MANIFEST="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/setup-machine/plugins.json}"
[ -f "${MANIFEST:-}" ] || MANIFEST="$(python3 -c '
import json, pathlib
d = json.load(open(pathlib.Path.home() / ".claude/plugins/installed_plugins.json"))
e = d["plugins"].get("hexagram@hexagram") or []
print(e[0]["installPath"] + "/skills/setup-machine/plugins.json" if e else "")')"
```

⚠️ **Never find the installed version by picking the newest cache directory.** An update leaves the
old one in place with the same mtime, so `ls -t` chooses by tie-break and is wrong about half the
time. `installed_plugins.json` is the record of what is loaded.

Compare against `$MANIFEST` and report three sets: **present**, **missing**, and **installed but not
in the manifest**. Report the third rather than removing it — unlisted usually means a deliberate
local addition.

## 2. Say what would land, before it lands

The set is a large change to make to someone's editor on their behalf. Print it first, derived —
**never quote a number from this document, which ages**:

```bash
python3 - "$MANIFEST" <<'PY'
import json, shutil, sys
m = json.load(open(sys.argv[1]))
for p in m["plugins"]:
    miss = [b for b in p.get("requires", []) if not shutil.which(b)]
    line = f"{p['name']:24} {','.join(p.get('delivers', ['?'])):28}"
    if miss:            line += f"MISSING {','.join(miss)} — fix: {p.get('install', '(none recorded)')}"
    if p.get("caveat"): line += f"  [{p['caveat']}]"
    print(line)
print(f"\n{len(m['plugins'])} plugins, "
      f"{sum(1 for p in m['plugins'] if 'hooks' in p.get('delivers', []))} of which register hooks, "
      f"{sum(len(p.get('mcp_servers', [])) for p in m['plugins'])} MCP servers between them")
PY
```

Then say out loud, in one line each:

- **which register hooks.** A hook runs on every session whether or not anyone invokes the plugin.
- **which are missing a binary**, what each is waiting for, and what that actually costs. It is not
  the same everywhere: an LSP plugin with no language server delivers nothing at all, while
  `hexagram` loses exactly one skill and keeps the other fifteen. The `caveat` says which.
- **any `caveat`.** These are costs that cannot be checked, only stated — `security-guidance` is the
  one to read aloud: it builds a Python venv on first run (180s timeout), and spawns a hook process
  on every prompt, every file edit, and every Bash call. Worth having; not worth discovering by
  noticing sessions got slower.

⚠️ **Do not state a skill count.** The manifest records *what kind* of thing each plugin delivers,
not how many, and on a fresh machine nothing is cached yet — any number here would be invented.
Count in step 5, after installing, where counting is possible.

## 3. Install the whole set

```bash
claude plugin marketplace list | grep -q claude-plugins-official \
  || claude plugin marketplace add anthropics/claude-plugins-official

INSTALLED="$(claude plugin list)"
for name in $(python3 -c 'import json,sys
print("\n".join(p["name"] for p in json.load(open(sys.argv[1]))["plugins"]))' "$MANIFEST"); do
  case "$INSTALLED" in *"$name@claude-plugins-official"*) continue ;; esac
  claude plugin install "$name@claude-plugins-official" --yes
done
```

⚠️ **Never write `<name>` inside a runnable block.** `bash -n` accepts it — `<` is a redirection, not
a syntax error — so the line looks fine, runs, fails with `name: No such file or directory`, and
never reaches `claude`. A placeholder that passes the syntax check is worse than one that does not.

## 4. Decide which servers to keep

Everything is installed and every server is on. Now turn off the ones this machine does not need.

**Ask the person one question:** *do you run an MCP aggregator — one server fronting several others,
like MetaMCP or mcp-proxy — and if so, which of these does it already serve?* Nothing here can
answer that; `claude mcp list` shows servers but not scope, and cannot tell an aggregator from an
ordinary server. **Never invent its URL and never install one.**

Then find out which actually work, because a server that cannot answer is pure cost:

```bash
python3 - "$MANIFEST" <<'PY'
import json, sys
for p in json.load(open(sys.argv[1]))["plugins"]:
    for s in p.get("mcp_servers", []):
        print(f"plugin:{p['name']}:{s}")
PY
claude mcp list        # shows ✔ Connected / ! Needs authentication per server
```

**Deny a server when the aggregator already serves it, or when it needs credentials nobody is going
to supply.** Keep it when it answers and nothing else provides it.

Generate the list — exact names, from the manifest, with the keepers excluded:

```bash
KEEP="cloudflare-docs"          # space-separated bare server names to keep; edit this line
python3 - "$MANIFEST" "$KEEP" <<'PY'
import json, sys
keep = set(sys.argv[2].split())
deny = [{"serverName": f"plugin:{p['name']}:{s}"}
        for p in json.load(open(sys.argv[1]))["plugins"]
        for s in p.get("mcp_servers", []) if s not in keep]
print(json.dumps({"deniedMcpServers": deny}, indent=2))
PY
```

Merge that array into `~/.claude/settings.json` **with a JSON tool, never by replacing the key** — it
very likely already holds unrelated entries, and overwriting it silently re-enables whatever was
there.

⚠️ **Say what each denial costs, before writing it.** A denied server whose capability nothing else
provides is a capability the machine no longer has. That is a fine trade when the server was dead
anyway; it is a bad one made silently. Print the list and the reason for each, then write.

Restart for it to take effect, and verify with `claude mcp list`.

## 5. Report

- the three sets from step 1, and what changed
- which plugins landed **inert**, and the binary each waits for
- every server denied, and why — duplicated by the aggregator, or unauthenticated and unused
- every server kept, so the list reads as a decision rather than a leftover
- **what needs a restart.** Plugin, hook and MCP changes apply to the next session, so the work is
  done *and* not yet visible. Saying only one half of that is misleading either way.

## Regenerating the manifest

Do not hand-edit the plugin list. Derive it:

```bash
python3 - "$MANIFEST" "$HOME/.claude/plugins" > /tmp/plugins.new.json <<'PY'
import json, pathlib, re, sys

man, root = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
up  = root / "cache/claude-plugins-official"
mkt = json.load(open(root / "marketplaces/claude-plugins-official/.claude-plugin/marketplace.json"))
by  = {p["name"]: p for p in mkt["plugins"]}
d   = json.load(open(man))

def newest(name):
    dirs = [x for x in (up / name).glob("*") if x.is_dir()] if (up / name).is_dir() else []
    # Version-sort: lexicographically "0.8.3" beats "0.20.0" and you read a stale version.
    return max(dirs, default=None,
               key=lambda x: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", x.name)])

for e in d["plugins"]:
    n, meta, r = e["name"], by.get(e["name"], {}), newest(e["name"])
    if not r:
        print(f"# not in cache, left unchanged: {n}", file=sys.stderr)
        continue
    dl, servers, transport = [], [], []
    if list(r.glob("skills/*/SKILL.md")):      dl.append("skills")
    if list(r.glob("commands/**/*.md")):       dl.append("commands")
    if list(r.glob("agents/*.md")):            dl.append("agents")
    if (r / "hooks" / "hooks.json").is_file(): dl.append("hooks")
    pj   = r / ".claude-plugin" / "plugin.json"
    decl = json.load(open(pj)).get("mcpServers") if pj.is_file() else None
    files = [r / decl] if isinstance(decl, str) else \
            [r / x for x in decl] if isinstance(decl, list) else []
    if (r / ".mcp.json").is_file(): files.append(r / ".mcp.json")
    for f in files:
        if not pathlib.Path(f).is_file(): continue
        for k, v in json.load(open(f)).get("mcpServers", {}).items():
            servers.append(k)
            transport.append(v.get("type") or ("stdio" if v.get("command") else "?"))
    if isinstance(decl, dict): servers.extend(decl)
    if meta.get("lspServers"): dl.append("lsp")
    if servers: dl.append("mcp")
    e["delivers"], e["ships_mcp"] = dl or ["nothing"], bool(servers)
    e["mcp_servers"] = sorted(set(servers))
    if servers: e["transport"] = sorted(set(transport))
    else:       e.pop("transport", None)

print(json.dumps(d, indent=2))
PY
diff <(python3 -m json.tool "$MANIFEST") <(python3 -m json.tool /tmp/plugins.new.json) \
  && echo "no change" || echo "review the diff, then: cp /tmp/plugins.new.json $MANIFEST"
```

⚠️ **`mcp_servers` is what the deny list is generated from**, so a wrong entry there is a server that
silently stays on. Read `plugin.json`'s `mcpServers` field, not a root `.mcp.json` — supabase
declares its server at `./agents/claude/.mcp.json`, and a root-only check finds nothing and reports a
strip that never happened.

⚠️ **`requires`, `install` and `caveat` cannot be derived** and are kept by hand. `requires` holds
binary names a `which` can test. `install` holds the command that provides them, so that a missing
binary is reported with its fix attached rather than as a dead end — measure it against the machine
before recording it, the way the two LSP entries were resolved through their symlinks. `caveat` holds a cost that cannot be tested — a version floor, a runtime
expense — and is printed in step 2 rather than checked, because a check that cannot fail correctly is
worse than an honest sentence.

## What this skill used to do, and why it does not

It used to derive MCP-stripped **forks**: copy each plugin out of the cache, delete its `.mcp.json`,
publish a second marketplace of the copies, install from there, and re-derive the whole tree on a
schedule so upstream fixes arrived.

`deniedMcpServers` does the same job in one settings key, and does it better:

| | forks | `deniedMcpServers` |
|---|---|---|
| granularity | whole plugin | **one server** |
| moving parts | a script, a second marketplace, a scheduled job, machine-local config, prune, heal | a list |
| upstream fixes | arrive when the job re-derives | arrive with `claude plugin update` |
| worst failure | a partial copy installs cleanly, delivers nothing, and keeps its MCP server | a typo denies nothing |

⚠️ **The fork mechanism's failures are the general shape of derived artefacts, and worth remembering
even though the code is gone.** A `cp -R` that died partway left a directory holding `plugin.json`
and `.mcp.json` and no skills; it installed fine, so the swap removed the working upstream copy and
the machine kept the very server the mechanism existed to remove. Pruning a fork whose plugin was
installed left that plugin loading nothing at all. Both were invisible to reading and to `bash -n`,
and surfaced only by running the thing against the real CLI.

**A derived artefact nobody re-verifies looks exactly like one that works.** Prefer the mechanism the
platform maintains over the one you keep current yourself.
