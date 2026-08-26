---
name: diagrams
description: Use when creating, editing or reviewing an architecture diagram. Covers C4 notation, Excalidraw inside an Obsidian vault, whether a generator or your hands own the file, and the binding trap that draws every arrow through its own boxes.
---

# Diagram Rules — Excalidraw, C4, and who owns the file

House style for **architecture diagrams**. Canonical notation: **C4** —
<https://c4model.com/diagrams/notation>, Simon Brown.

## Where a diagram lives

**`docs/architecture/diagrams/*.excalidraw.md`, rendered by the Obsidian Excalidraw plugin**
(zsviczian, one install per vault). ⚠️ A plain `*.excalidraw` opens in the plugin's *compatibility
mode*, and the plugin fields below (`rawText`, `hasTextLink`) exist only in the markdown form. A
generator that emits raw JSON should keep it as the auto-exported sibling, not the file of record. The vault is the product; a diagram that
lives anywhere else is a diagram that goes stale in a tab. Embed it in a note with
`![[diagram-name]]`.

⚠️ **The `excalidraw` MCP is the wrong tool here, and it is worth knowing why before
reaching for it.** It is an OAuth connector that draws on **hosted excalidraw.com** —
so what it produces is a diagram in the cloud, not a file the vault can render. It
also exposes only `authenticate` / `complete_authentication` until somebody completes
the browser flow, which makes it look broken rather than inapplicable. Local plugin,
local file, no MCP.

## Every diagram declares its owner — a generator, or your hands

Both are legitimate. What is not legitimate is a file that is unclear about which,
because the failure mode is silent: you hand-tune a diagram, someone re-runs the
generator, and the work is gone with no conflict, and a diff no reviewer will read.

| | **generated** | **hand-owned** |
|---|---|---|
| source of truth | a script in `tools/` | the `.excalidraw` file itself |
| you edit | the script, then re-run | the file, in Obsidian |
| C4 obligations enforced by | assertions in the generator | the checklist at the bottom of this file |
| marked by | the generator named in the note that embeds it | a line in the embedding note saying it is hand-owned |

**Never both.** Promoting a hand-owned diagram to generated means writing the
generator and accepting that hand edits stop; demoting a generated one means deleting
the generator and saying so in the note. Both are cheap. What is expensive is
discovering the question after losing an afternoon of nudging boxes.

⚠️ **If you find yourself wanting both** — generated content, hand-tuned positions —
the answer is to split them: the generator owns boxes, labels and arrows, and reads
coordinates from a small checked-in layout file a human edits. Worth building **only
once you have wanted it twice**; until then the fork above is enough.

### When to generate

- The diagram restates data that already exists in the repo (a module graph, a stack's
  resources, a provider list) — then hand-drawing it is transcription, and transcription
  drifts.
- It is large enough that a reviewer cannot check it by eye.
- It must not regress: the generator can **assert** (see *The assertions*).

**A generated diagram is reviewable and a hand-drawn one is not** — a several-thousand-line JSON
diff tells a reviewer nothing, while a twenty-line change to the generator tells them
everything. That is the real argument, and it only applies where a reviewer exists.

**Derive ids, seeds and nonces from stable keys; never draw them.**
`sha256("id:" + key)` truncated, `sha256("s:" + key) % 2**31` for the seed, a fixed
`updated` stamp. The result is that regenerating produces a **byte-identical file** and
git sees no churn — verify with `diff -q` after every change.

### When to draw by hand

- One-off, explanatory, or the shape *is* the thinking — a sketch of an idea, a
  whiteboard replacement, anything where nudging is the point.
- Fewer than a dozen elements, where the generator costs more than it saves.

Hand-drawing is not a lesser mode. It is the mode Excalidraw exists for.

## ⚠️ The Excalidraw trap — and why it does not bite you when editing by hand

> **A bound arrow is NOT re-routed when the scene loads.**

Excalidraw renders an arrow's `points` **exactly as stored**, and only recalculates
them when a bound element is moved, resized or rotated (`updateBoundElements()`). So
`startBinding` + `endBinding` do **not** clip an arrow to its boxes' edges on load —
they only promise it will follow *later*, if someone happens to drag something.

**This is a writing-by-program problem only.** Open the file in Obsidian, nudge a box,
and the arrows snap to their edges correctly — hand-editing *repairs* this geometry
rather than breaking it. The trap bites exactly one case: a file written by a script
and never opened, where centre-to-centre points draw every arrow straight through both
boxes while every structural check about bindings still passes.

**So a generator computes every endpoint on the element's edge itself.** One helper
returns the absolute point *and* the `fixedPoint` ratio the binding needs, from the
same call, so the geometry and the binding cannot disagree:

```python
def anchor(el, side, t=0.5, gap=8):
    """Absolute point on an element edge, plus the fixedPoint ratio the binding needs."""
    x, y, w, h = el["x"], el["y"], el["width"], el["height"]
    return {
        "r": ((x + w + gap, y + h * t),   [1, t]),
        "l": ((x - gap,     y + h * t),   [0, t]),
        "t": ((x + w * t,   y - gap),     [t, 0]),
        "b": ((x + w * t,   y + h + gap), [t, 1]),
    }[side]
```

⚠️ **Those are scene coordinates, and an arrow's `points` are element-local with `points[0] == [0, 0]`.**
Excalidraw normalises on load when they are not, silently rewriting the arrow's `x`, `y`, `width` and
`height`: the same class of silent geometry bug this section exists to prevent. Subtract the first
anchor from every point and let that anchor *be* the arrow origin:

```python
(ax, ay), start_ratio = anchor(src, "r")
(bx, by), end_ratio   = anchor(dst, "l")
arrow["x"], arrow["y"] = ax, ay
arrow["points"] = [[0, 0], [bx - ax, by - ay]]     # elbow corners go in between
```

⚠️ **Do not assume the binding's `gap` and your drawn offset are coupled.** Excalidraw renders stored
`points` verbatim, and which binding fields a build actually reads has changed between versions. Mirror
the field set and the values of a file already in your vault, rendered by the plugin build you have,
rather than trusting any published schema.

## Arrows are elbowed, and never cross a box

**Elbowed** — orthogonal, 90° corners:

```json
{
  "type": "arrow",
  "elbowed": true,
  "fixedSegments": [],
  "startIsSpecial": false,
  "endIsSpecial": false,
  "startBinding": { "elementId": "…", "focus": 0, "gap": 8, "fixedPoint": [1, 0.5] },
  "endBinding":   { "elementId": "…", "focus": 0, "gap": 8, "fixedPoint": [0, 0.5] }
}
```

`fixedPoint` is a **local ratio, not a scene coordinate**: `[0, 0]` is top-left,
`[1, 1]` bottom-right, so `[1, 0.5]` is the middle of the right edge.

⚠️ **Assert the path is orthogonal.** An elbow arrow with a diagonal segment is not an
elbow arrow, and Excalidraw will not correct it. Every consecutive pair of points must
differ on exactly one axis.

✅ **This degrades well.** If a plugin build does not honour `elbowed`, an
already-orthogonal point list renders as an ordinary multi-point arrow with the same
corners. Nothing looks wrong.

**Never over a box** — route through empty lanes. Prefer a single straight run in a
gap; take one turn when you must; never two turns to reach somewhere a re-layout would
have reached in zero.

## Layout: a wide label needs a wide gap

The failure mode is arithmetic, and it is the one that looks like carelessness.

An arrow label is centred on the arrow. Two lines at `fontSize: 11` is about **28px tall** (11 × 1.25
× 2) and, at ~22 characters a line, roughly **120–145px wide**. Put boxes 60–90px apart and the label
spills into both of them, every time, no matter how the arrow is routed.

| | |
|---|---|
| **box pitch** | box width **+ 160px**, or measure your longest label and add 20% |
| **arrow label** | ≤ 22 characters per line, 2 lines |
| **the general rule** | **a wide label needs a long run to sit on; stacking buys height cheaply** |

Vertical gaps are cheaper than horizontal ones — a two-line label needs 28px of height
against ~130px of width — so when space is tight, stack.

## Text is bound, in both directions

⚠️ **`label` does not exist in raw Excalidraw JSON.** A labelled shape is *two*
elements that point at each other:

| the shape | the text |
|---|---|
| `boundElements: [{"type": "text", "id": …}]` | `containerId: <shape id>` |
| | `originalText`, `rawText`, `lineHeight: 1.25` |
| | `autoResize: false` + explicit `width` when you pre-wrap the lines yourself |
| | `verticalAlign: "middle"`, `textAlign: "center"` |

The same applies to an arrow's label — `containerId` points at the **arrow**.

`rawText` and `hasTextLink` are Obsidian-plugin fields. **Mirror the schema of a file
already in the vault** rather than Excalidraw's upstream docs: read one element of each
type and copy its exact key set.

**`index` does not decide z-order — array order does.** Excalidraw keeps `index` in sync with the
array and regenerates it when the two disagree. It is a `fractional-indexing` key, not a counter:
`a0010` is rejected as an invalid order key, so a hand-rolled sequence dies at the tenth element and
triggers a full regeneration, which destroys the byte-identical guarantee above. **Omit `index` and let
Excalidraw assign valid ones.** Emit shapes before the arrows that bind them; that ordering is what
actually matters.

## C4: what every element and every line must carry

Quoted, because these are the rules and not suggestions. They apply to a hand-drawn
diagram exactly as much as to a generated one — only the enforcement differs.

| rule | c4model.com |
|---|---|
| type | *"The type of every element should be explicitly specified (e.g. Person, Software System, Container or Component)."* |
| description | *"Every element should have a short description, to provide an 'at a glance' view of key responsibilities."* |
| technology | *"Every container and component should have a technology explicitly specified."* |
| direction | *"Every line should represent a unidirectional relationship."* |
| label | *"Every line should be labelled, the label being consistent with the direction and intent of the relationship."* — and, per the same page, *"ideally avoiding single words like 'Uses'"* |
| protocol | between containers, the technology/protocol is *"explicitly labelled"* |
| key | *"All diagrams should have a key/legend to make the notation explicit."* Plus a title naming the diagram's type and scope |

**Arrow direction is the dependency, not the data flow.** A component that reads from
a feed points **at** the feed, even when the bytes travel the other way and even when
it means drawing right-to-left.

⚠️ **Two genuine relationships between the same pair need two lines**, because a
bidirectional line is forbidden. Separate them with different `fixedPoint` ratios
(`0.26` and `0.74`) or their labels land on top of each other.

### Deployment belongs in its own diagram

> *"a container is an application or a data store"*

Nodes, clustering, replica counts and machine names are **not** containers. C4 puts
them in a **deployment diagram**, and obeying that is what keeps workloads from being
confused with the machines they run on — a distinction that leaks into resource names
the moment the diagram blurs it.

### Accessibility is the type rule, not a palette rule

C4 imposes no shapes or colours, but requires colour coding to be *"consistent"* and to
survive colour blindness and black-and-white printing.

**The cheapest way to satisfy that is a rule C4 already imposes: write the type in the
box.** `[Container · Rust]`, `[Software System · external]`, `[Deployment Node · t3.small]`.
Then colour is reinforcement and nothing depends on it. Do not build a legend that maps
hues to meanings and call it done.

## The assertions

**For a generated diagram this is the load-bearing part.** A generator that cannot fail
is a generator that will ship the same mistake twice.

```python
assert_no_crossings()   # every segment vs every filled box → exit 1
assert_text_fits()      # label taller/wider than its container → exit 1
```

Plus the inline orthogonality assert per arrow.

**Look at the output.** Structural validation passes on diagrams that are visibly
broken. What catches those is rendering an approximate SVG from the **stored points**
and reading it:

```bash
python3 tools/render-"$name".py
# then render an SVG from the stored geometry; on macOS:
qlmanage -t -s 2400 -o "$outdir" preview.svg
```

⚠️ A preview that draws arrows centre-to-centre will *hide* this class of bug — the
preview must use the same `points` Excalidraw will.

## A note on other engines

If a diagram is text-source and you never need to nudge it, **D2 with `--layout elk`**
does the orthogonal routing and crossing avoidance for free — no anchor helper, no
crossing assertion, no layout arithmetic. Commit the `.d2` beside the rendered `.svg`.

The trade is exactly the one this file is organised around: you edit text and cannot
place a box, so it wins where Excalidraw's hand-editing is not wanted, and loses where
it is. The C4 obligations above are engine-agnostic and apply either way.

## Checklist

**Every diagram:**

- [ ] every box: type, description, and — if a container — technology
- [ ] every arrow: one direction, labelled, protocol named
- [ ] arrow direction is the dependency, not the data flow
- [ ] title and key present; deployment split into its own diagram
- [ ] rendered and **looked at**

**Additionally, if generated:**

- [ ] a script in `tools/` owns it, and re-running is byte-identical
- [ ] every arrow endpoint on an edge with a gap, `fixedPoint` from the same call
- [ ] every arrow elbowed and orthogonal, asserted
- [ ] no arrow crosses a box, and the assertion proves it
- [ ] box pitch ≥ width + 160px, arrow labels ≤ 22 chars a line
- [ ] the preview renders from the **stored** points

## Sources

- [C4 notation](https://c4model.com/diagrams/notation) · [container diagram](https://c4model.com/diagrams/container) · [diagram types](https://c4model.com/diagrams)
- [Excalidraw scene content schema](https://plus.excalidraw.com/docs/api/scene-content-schema) · [element binding system](https://deepwiki.com/excalidraw/excalidraw/3.2-element-binding-system) · [building elbow arrows](https://plus.excalidraw.com/blog/building-elbow-arrows-part-one) · [elbow arrow segments PR](https://github.com/excalidraw/excalidraw/pull/8952)
- [Obsidian Excalidraw plugin](https://github.com/zsviczian/obsidian-excalidraw-plugin) · [its file formats](https://deepwiki.com/zsviczian/obsidian-excalidraw-plugin/3.1-file-formats-and-conversion)
- [D2](https://d2lang.com/) · [ELK layout](https://d2lang.com/tour/elk)
