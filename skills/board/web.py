#!/usr/bin/env python3
"""Writes the board, and every slice it names, as HTML you can open in a browser.

    python3 web.py .kanban.json Work out

The same board show.py draws in a terminal, for a screen that has more room than
80 columns — and, because a card's whole reason to exist is the document behind
it, a page per slice beside it. Output is a directory of plain files with no
server, no CDN and no build step: `out/index.html` opens over file:// and every
link in it resolves.

PORTABILITY. Same target as sync.py and show.py: the python3 that ships with
macOS, which is 3.9. No f-strings, no ``match``, no ``X | Y`` annotations,
stdlib only.

READ-ONLY, and that is the design rather than a limitation, for the reason
show.py gives: moving a card is a ``status:`` edit in the markdown followed by
sync.py, so a move lands in ``git diff`` instead of only in a JSON file nobody
reviews. A renderer that could also write would quietly become the second source
of truth the board skill exists to avoid. A test asserts it never calls a writing
subcommand.

It reads through the ``kanban`` binary rather than parsing the board file: the
CLI is the contract, the file layout is not.
"""
import os
import re
import sys

# The two modules beside this one, by absolute path. A skill is run by path
# rather than installed, so the directory this file sits in is not on sys.path
# when it is loaded — as a script or, in the suite, through importlib.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import markdown  # noqa: E402  (the path above has to be set first)
import show      # noqa: E402

ASSETS = ("tokens.css", "board.css", "board.js", "slice.css")
PAGE_SIZE = 100

# The five sections a hexagram slice always has, plus the one it sometimes has.
# The acceptance leads because it is what proves the slice done, and the escape
# hatch trails; everything between keeps the document's own order, because a
# document that does not use these headings carries its substance in its own and
# ranking by a fixed list would bury that under a collapsed "If stuck".
LEAD = ("Done when",)
TRAIL = ("If stuck",)
NOTES = {
    "Done when": "the command whose output is the pass or fail",
    "Delivers": "what exists once this ships",
    "Needs": "what has to be true first",
    "Design constraint": "the rule this slice must not break",
    "Tests": "written alongside the code, never after",
    "If stuck": "the way out, if it does not go as written",
}


def asset(name):
    """One of the stylesheets or scripts beside this file."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def cards_of(api, board_id):
    """Every card on the board, with descriptions.

    ``card list`` omits the description, which is where the document path and the
    ``Done when`` live, so each card is fetched. Measured at roughly 130 cards a
    second, which is cheap enough to keep the CLI as the only contract.
    """
    items, page = [], 1
    while True:
        got = api("card", "list", "--board", board_id,
                  "--page", str(page), "--page-size", str(PAGE_SIZE))
        items.extend(got["items"])
        if page >= got.get("total_pages", 1):
            break
        page += 1
    return [api("card", "get", card["id"]) for card in items]


def split_description(description):
    """A card description is the document path, a blank line, then its acceptance."""
    if not description:
        return "", ""
    parts = description.split("\n", 1)
    head = parts[0].strip()
    rest = parts[1].strip() if len(parts) > 1 else ""
    if head.endswith(".md"):
        return head, rest
    return "", description.strip()


def clean_acceptance(text):
    """The acceptance, without the markdown that only made sense in the document.

    The fence is not always on its own line — ``Done when: ```bash`` puts it
    beside the label — so it is removed wherever it appears, together with the
    language token after it. The label goes too: whatever reveals this text says
    so already.
    """
    text = re.sub(r"```[A-Za-z0-9+#-]*", "", text)
    text = re.sub(r"^\s*Done when\s*:?\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def slug(doc):
    """A flat output filename for a document path, collision-free by construction."""
    return re.sub(r"[^A-Za-z0-9]+", "-", doc[:-3] if doc.endswith(".md") else doc
                  ).strip("-").lower() + ".html"


def parse_document(text):
    """Frontmatter, the ``# Title``, and the ``##`` sections in file order."""
    front, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    front[key.strip()] = value.strip()
            body = text[end + 4:]
    title = ""
    match = re.search(r"^#\s+(.*)$", body, re.M)
    if match:
        title = match.group(1).strip()
        # ⚠️ What sits between the frontmatter and the title is KEPT. Slices open
        # with a blockquote saying they are blocked or closed, and skipping to
        # the heading loses exactly that.
        body = body[:match.start()].rstrip() + "\n\n" + body[match.end():]
    sections, name, buf = [], "", []
    for line in body.split("\n"):
        head = re.match(r"^##\s+(.*)$", line)
        if head:
            if name or [l for l in buf if l.strip()]:
                sections.append((name, "\n".join(buf)))
            name, buf = head.group(1).strip(), []
        else:
            buf.append(line)
    if name or [l for l in buf if l.strip()]:
        sections.append((name, "\n".join(buf)))
    return front, title, sections


# ----------------------------------------------------------------- rendering


def esc(text):
    return markdown.escape(text)


def card_html(card, prefix, docs):
    """One card: a metadata line, the title, and the acceptance behind a summary.

    ⚠️ ``status: blocked`` never moves a card, so a blocked card sits in whatever
    column it was in and, read by column, is indistinguishable from one not yet
    picked up. Marking it is the whole reason the board skill leaves it in place.
    """
    epic, title = show.split_epic(card["title"])
    lead, rest = title.split(" — ", 1) if " — " in title else (title, "")
    doc, acceptance = split_description(card.get("description"))
    blocked = str(card.get("status") or "").lower() == "blocked"

    out = ['<article class="card{}">'.format(" blocked" if blocked else "")]
    out.append('<p class="meta"><span class="id">{}</span>'.format(
        esc(show.identifier(prefix, card))))
    if rest:
        out.append('<span class="lead">{}</span>'.format(esc(lead)))
    if blocked:
        out.append('<span class="chip warn">blocked</span>')
    if epic:
        out.append('<span class="chip">{}</span>'.format(esc(epic)))
    out.append("</p>")

    head = esc(rest or lead)
    if doc and doc in docs:
        head = '<a href="{}">{}</a>'.format(esc(slug(doc)), head)
    out.append('<h3 class="title">{}</h3>'.format(head))

    if acceptance:
        out.append('<details><summary>done when</summary><pre>{}</pre>'
                   '</details>'.format(esc(clean_acceptance(acceptance))))
    if doc:
        out.append('<p class="doc">{}</p>'.format(esc(doc)))
    out.append("</article>")
    return "".join(out)


def board_page(board, columns, cards, docs):
    """The board: one column of cards per column of the board."""
    prefix = board.get("card_prefix")
    by_column = {}
    for card in cards:
        by_column.setdefault(card["column_id"], []).append(card)
    for group in by_column.values():
        group.sort(key=lambda c: c["card_number"])  # board-id-ok: ordering only

    blocked = sum(1 for c in cards
                  if str(c.get("status") or "").lower() == "blocked")
    out = ['<main class="board">']
    for column in sorted(columns, key=lambda c: c["position"]):
        group = by_column.get(column["id"], [])
        role = str(column.get("default_status") or "parked")
        out.append('<section class="col {}"><h2>{} <b>{}</b></h2>'.format(
            esc(role), esc(column["name"]), len(group)))
        if not group:
            out.append('<p class="empty">empty</p>')
        for card in group:
            out.append(card_html(card, prefix, docs))
        out.append("</section>")
    out.append("</main>")

    subtitle = "{} card{}".format(len(cards), "" if len(cards) == 1 else "s")
    if blocked:
        # Named in the summary because a blocked card is invisible by column.
        subtitle += " · {} blocked".format(blocked)
    return shell(esc(board["name"]), esc(board["name"]), subtitle,
                 "".join(out), asset("board.css"), asset("board.js"), "")


def section_order(sections):
    """Acceptance first, escape hatch last, the document's own order between."""
    named = [name for name, _ in sections if name]
    lead = [n for n in LEAD if n in named]
    trail = [n for n in TRAIL if n in named]
    return lead + [n for n in named if n not in lead and n not in trail] + trail


def slice_page(doc, text, docs):
    """One slice document as a page built around the sections it always has."""
    front, title, sections = parse_document(text)
    folder = os.path.dirname(doc)

    def link(target):
        """http(s) is kept; a relative .md becomes the page written for it.

        Anything else keeps its text and loses its link: a document is data, and
        a link inside one is not a reason to follow an arbitrary scheme.
        """
        if re.match(r"^https?://", target):
            return target
        resolved = os.path.normpath(os.path.join(folder, target))
        return slug(resolved) if resolved in docs else ""

    known = dict((name, body) for name, body in sections if name)
    loose = "".join(body for name, body in sections if not name)

    out = []
    if loose.strip():
        out.append('<section class="blk">{}</section>'.format(
            markdown.blocks(loose, link)))
    for name in section_order(sections):
        body = markdown.blocks(known[name], link)
        note = NOTES.get(name, "")
        note_html = '<p class="note">{}</p>'.format(esc(note)) if note else ""
        if name in TRAIL:
            out.append('<details class="blk"><summary>{}</summary>{}</details>'
                       .format(esc(name), body))
            continue
        kind = ""
        if name in LEAD:
            kind = " lead"
        elif name == "Design constraint":
            kind = " warn"
        out.append('<section class="blk{}"><h2>{}</h2>{}{}</section>'.format(
            kind, esc(name), note_html, body))

    status = (front.get("status") or "todo").lower()
    tags = '<span class="tag {0}">{0}</span>'.format(esc(status))
    return shell(esc(title or doc), markdown.inline(title or doc),
                 esc(doc), "".join(out), asset("slice.css"), "",
                 tags, back=True)


def shell(title, heading, subtitle, body, css, js, tags, back=False):
    """The page every rendering here is poured into."""
    home = '<a class="back" href="index.html">&larr; board</a>' if back else ""
    script = "<script>{}</script>".format(js) if js else ""
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{tokens}{css}</style></head><body>
<header>{home}<h1>{heading}</h1><p class="sub">{subtitle}</p>{tags}</header>
{body}
<footer>A view over the markdown, not a second source of truth. To move a card,
edit <code>status:</code> in its document, then run <code>sync.py</code>.</footer>
{script}</body></html>
""".format(title=title, heading=heading, subtitle=subtitle, body=body,
           tokens=asset("tokens.css"), css=css, script=script, tags=tags,
           home=home)


def documents(cards):
    """Every slice document the board names, in card order."""
    seen = []
    for card in cards:
        doc = split_description(card.get("description"))[0]
        if doc and doc not in seen:
            seen.append(doc)
    return seen


def write(out_dir, board_file, board_name):
    """Render the board and its documents into ``out_dir``. Returns what it wrote."""
    api = show.Kanban(board_file)
    boards = api("board", "list")["items"]
    board = next((b for b in boards if b["name"] == board_name), None)
    if board is None:
        sys.exit("no board named {} in {}".format(board_name, board_file))
    columns = api("column", "list", "--board", board["id"])["items"]
    cards = cards_of(api, board["id"])

    # Only documents that are actually on disk become pages, so a card pointing
    # at a moved or deleted file degrades to plain text instead of a dead link.
    docs = [d for d in documents(cards) if os.path.isfile(d)]

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    written = ["index.html"]
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(board_page(board, columns, cards, docs))
    for doc in docs:
        with open(doc, encoding="utf-8") as fh:
            text = fh.read()
        name = slug(doc)
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(slice_page(doc, text, docs))
        written.append(name)

    missing = [d for d in documents(cards) if d not in docs]
    for doc in missing:
        sys.stderr.write("no such document: {} — card left unlinked\n".format(doc))
    return written


def main(argv):
    if len(argv) < 3:
        sys.stderr.write(
            "usage: web.py BOARD-FILE BOARD-NAME OUT-DIR\n")
        return 2
    written = write(argv[2], argv[0], argv[1])
    print("{} pages -> {}".format(len(written), argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
