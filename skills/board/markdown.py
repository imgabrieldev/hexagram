#!/usr/bin/env python3
"""The slice of markdown these documents actually use, and nothing else.

Not a markdown implementation. The set below was MEASURED across the 89 slice
documents on the author's machine rather than guessed at: fenced code, bullet
lists and inline code in every one of them, bold in 55, numbered lists in 11,
tables in 9, blockquotes in 9, one level of bullet nesting, three code spans in
the double-backtick form, and two links. Anything outside that is passed through
as text, which is the honest outcome for a renderer that does not claim to be
CommonMark.

PORTABILITY. Same target as sync.py and show.py: the python3 that ships with
macOS, which is 3.9. No f-strings, no ``match``, no ``X | Y`` annotations,
stdlib only.

Pure functions, no I/O. Everything here is called with a string and returns a
string, which is why the suite for it needs no fixtures.
"""
import html as html_module
import re

__all__ = ["escape", "inline", "blocks"]


def escape(text):
    return html_module.escape(text or "", quote=True)


def inline(text, link=None):
    """Bold, italics, inline code and links — the inline set these documents use.

    ``link`` is called with a link target and returns an href, or None to drop
    the link and keep its text. Resolving a target is the caller's business: a
    renderer that decided for itself which schemes to follow would be deciding
    it for every caller.
    """
    kept = []

    def stash(match):
        body = match.group(1)
        # CommonMark strips one leading and trailing space inside a code span.
        if body.startswith(" ") and body.endswith(" ") and body.strip():
            body = body[1:-1]
        kept.append(body)
        return "\x00{}\x00".format(len(kept) - 1)

    # A placeholder rather than a split. Splitting on backticks severs a ``**``
    # pair that straddles a code span, and ``**`pnpm lint` runs**`` is a shape
    # 55 of those 89 documents use.
    #
    # The double-backtick form comes FIRST, because it is the one used when the
    # code itself contains a backtick — ``` `` - `path` `` ``` is a real line —
    # and the single-backtick pattern would otherwise match its innards and
    # mangle it.
    out = re.sub(r"``(.+?)``", stash, text)
    out = escape(re.sub(r"`([^`]+)`", stash, out))
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", out)
    if link is not None:
        out = _links(out, link)
    return re.sub(r"\x00(\d+)\x00",
                  lambda m: "<code>{}</code>".format(escape(kept[int(m.group(1))])),
                  out)


def _links(text, link):
    def repl(match):
        label, target = match.group(1), match.group(2)
        href = link(target)
        if not href:
            return label
        return '<a href="{}" rel="noreferrer noopener">{}</a>'.format(
            escape(href), label)
    # ⚠️ `\(([^)]+)\)` stops at the FIRST `)`, so a target that contains one —
    # `alert(1)`, or a Wikipedia `Foo_(bar)` URL — is captured short and the
    # remainder is left on the page as text. One level of nesting is balanced
    # here, which is every such target these documents carry.
    return re.sub(r"\[([^\]]+)\]\(((?:[^()]|\([^()]*\))*)\)", repl, text)


# --------------------------------------------------------------------- blocks
#
# Each handler is given the lines and an index. It returns (html, next_index)
# when it recognises what is there and None when it does not, so the dispatch
# loop below stays flat and every handler stays small enough to read at once.


def _fence(lines, i, link):
    match = re.match(r"^\s*```([A-Za-z0-9+#-]*)\s*$", lines[i])
    if not match:
        return None
    body, i = [], i + 1
    while i < len(lines) and not re.match(r"^\s*```", lines[i]):
        body.append(lines[i])
        i += 1
    return ('<pre data-lang="{}"><code>{}</code></pre>'.format(
        escape(match.group(1)), escape("\n".join(body))), i + 1)


def _heading(lines, i, link):
    match = re.match(r"^(#{3,6})\s+(.*)$", lines[i])
    if not match:
        return None
    level = min(len(match.group(1)), 4)
    return ("<h{0}>{1}</h{0}>".format(level, inline(match.group(2), link)), i + 1)


def _table(lines, i, link):
    if not lines[i].lstrip().startswith("|"):
        return None
    rows = []
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        rows.append(lines[i])
        i += 1
    body = [r for r in rows if not re.match(r"^\|[\s:|-]+\|?\s*$", r)]
    if not body:
        return ("", i)

    def cells(line):
        return [c.strip() for c in line.strip().strip("|").split("|")]

    out = ['<div class="scrollx"><table><thead><tr>']
    out.append("".join("<th>{}</th>".format(inline(c, link))
                       for c in cells(body[0])))
    out.append("</tr></thead><tbody>")
    for row in body[1:]:
        out.append("<tr>{}</tr>".format("".join(
            "<td>{}</td>".format(inline(c, link)) for c in cells(row))))
    out.append("</tbody></table></div>")
    return ("".join(out), i)


def _quote(lines, i, link):
    if not lines[i].startswith(">"):
        return None
    text = []
    while i < len(lines) and lines[i].startswith(">"):
        text.append(lines[i][1:].strip())
        i += 1
    return ("<blockquote>{}</blockquote>".format(inline(" ".join(text), link)), i)


def _gather(lines, i, pattern, capture):
    """Items matching ``pattern``, with wrapped continuation lines folded in.

    ⚠️ The folding happens BEFORE conversion, and that ordering is the point:
    emphasis wraps across these line breaks, and converting each line on its own
    severs the ``**`` pair and leaves the asterisks on the page.
    """
    items = []
    while i < len(lines):
        match = re.match(pattern, lines[i])
        if match:
            items.append(list(capture(match)))
            i += 1
        elif lines[i].strip() and lines[i].startswith("  ") and items:
            items[-1][-1] += " " + lines[i].strip()
            i += 1
        else:
            break
    return items, i


def _bullets(lines, i, link):
    if not re.match(r"^( *)[-*]\s+(.*)$", lines[i]):
        return None
    items, i = _gather(lines, i, r"^( *)[-*]\s+(.*)$",
                       lambda m: (len(m.group(1)), m.group(2)))
    out, depth = [], 0
    for indent, text in items:
        # One level of nesting is all these documents use, so two-space indent
        # is the whole rule rather than a general indent stack.
        want = 1 if indent >= 2 else 0
        if want > depth:
            # ⚠️ The nested list belongs INSIDE the item above it. Appending a
            # bare <ul> makes it a sibling — a <ul> whose child is a <ul> — which
            # every browser renders and no parser accepts, so the item is
            # reopened instead.
            if out and out[-1].endswith("</li>"):
                out[-1] = out[-1][:-len("</li>")]
            out.append("<ul>")
            depth += 1
        while depth > want:
            out.append("</ul></li>")
            depth -= 1
        out.append("<li>{}</li>".format(inline(text, link)))
    out.extend(["</ul></li>"] * depth)
    return ("<ul>" + "".join(out) + "</ul>", i)


def _numbers(lines, i, link):
    if not re.match(r"^\s*\d+\.\s+(.*)$", lines[i]):
        return None
    items, i = _gather(lines, i, r"^\s*\d+\.\s+(.*)$", lambda m: (m.group(1),))
    return ("<ol>{}</ol>".format("".join(
        "<li>{}</li>".format(inline(text, link)) for (text,) in items)), i)


BREAKS = r"^\s*(```|\||>|#{3,6}\s|[-*]\s|\d+\.\s)"


def _paragraph(lines, i, link):
    text = []
    while i < len(lines) and lines[i].strip() and not re.match(BREAKS, lines[i]):
        text.append(lines[i].strip())
        i += 1
    if not text:
        return ("", i + 1)
    # A paragraph opening with the warning sign is a callout in these documents,
    # and it is marked so a stylesheet can treat it as one.
    kind = ' class="warn"' if text[0].startswith("⚠") else ""
    return ("<p{}>{}</p>".format(kind, inline(" ".join(text), link)), i)


HANDLERS = (_fence, _heading, _table, _quote, _bullets, _numbers)


def blocks(text, link=None):
    """Markdown to HTML, for the subset above."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        for handler in HANDLERS:
            got = handler(lines, i, link)
            if got is not None:
                html, i = got
                out.append(html)
                break
        else:
            html, i = _paragraph(lines, i, link)
            out.append(html)
    return "".join(out)
