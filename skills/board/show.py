#!/usr/bin/env python3
"""Draws the board as columns of cards, for a terminal.

    python3 show.py <board-file> <board-name>            the board
    python3 show.py <board-file> <board-name> --next     the next card, with its Done when

PORTABILITY. Same target as sync.py: the python3 that ships with macOS, which is
3.9. No f-strings with ``=``, no ``match``, no ``X | Y`` annotations, stdlib only.

READ-ONLY, and that is the design rather than a limitation. Moving a card is a
``status:`` edit in the markdown followed by ``sync.py``, so that a move lands in
``git diff`` instead of only in a JSON file nobody reviews. A renderer that could
also write would quietly become the second source of truth this skill exists to
avoid.

It reads through the ``kanban`` binary rather than parsing the board file: the CLI
is the contract, the file layout is not.
"""
import json
import shutil
import subprocess
import sys
import textwrap

ORDER = ("TODO", "Doing", "Complete")
GAP = 3
MIN_CARD = 22


class Kanban:
    def __init__(self, board_file):
        self.board_file = board_file

    def __call__(self, *args):
        try:
            out = subprocess.run(["kanban", self.board_file] + list(args),
                                 capture_output=True, text=True, check=True).stdout
        except FileNotFoundError:
            sys.exit("kanban is not on PATH — see install.md beside this file")
        except subprocess.CalledProcessError as err:
            sys.exit("kanban {}: {}".format(" ".join(args), err.stderr.strip()))
        return json.loads(out)["data"]


def identifier(prefix, card):
    """`PREFIX-N`, for DISPLAY ONLY.

    ⚠️ Never address a card by this string. Upstream renumbers cards if a board's
    prefix changes after cards exist, so the identifier is not stable; uuid is.
    A CI check in this repo enforces that, and this function is the one place the
    form is allowed to appear.
    """
    number = card["card_number"]  # board-id-ok: printed, never passed back
    return "{}-{}".format(prefix, number) if prefix else str(number)


def card_box(card, width, prefix, epics):
    inner = width - 4
    ident = identifier(prefix, card)
    # An epic is a container: its column reports the aggregate of its children
    # rather than its own work. Unmarked, a Doing holding one epic and one task
    # reads as two things in progress, which is the opposite of what it means.
    tag = "EPIC" if card["id"] in epics else ""
    head = ident.ljust(max(0, inner - len(tag))) + tag

    title = card["title"]
    # Hexagram titles tend to read "Checkpoint 1 — Scaffold, …". Splitting on the
    # em dash gives a heading and a body, which scans better than wrapping the
    # whole string as one paragraph. Titles without one simply wrap.
    if " — " in title:
        lead, rest = title.split(" — ", 1)
    else:
        lead, rest = title, ""

    body = [lead[:inner]]
    if rest:
        body += textwrap.wrap(rest, inner) or [""]

    lines = ["╭" + "─" * (width - 2) + "╮", "│ " + head[:inner].ljust(inner) + " │"]
    lines += ["│ " + line.ljust(inner) + " │" for line in body]
    lines.append("╰" + "─" * (width - 2) + "╯")
    return lines


def state(api, board_name):
    board = next(b for b in api("board", "list")["items"] if b["name"] == board_name)
    columns = api("column", "list", "--board", board["id"])["items"]
    cards = api("card", "list", "--page-size", "100")["items"]
    return board, columns, cards


def render(api, board_name):
    board, columns, cards = state(api, board_name)

    by_column = {}
    for card in cards:
        by_column.setdefault(card["column_id"], []).append(card)
    for group in by_column.values():
        group.sort(key=lambda c: c["card_number"])  # board-id-ok: ordering only

    # There is no `relation list` on the shipped CLI — children are asked for one
    # card at a time. Verified against the binary, not read from docs.
    epics = set()
    for card in cards:
        if api("relation", "children", card["id"]):
            epics.add(card["id"])

    ordered = sorted(columns, key=lambda c: ORDER.index(c["name"])
                     if c["name"] in ORDER else len(ORDER))

    term = shutil.get_terminal_size((100, 24)).columns
    width = max(MIN_CARD, (term - GAP * (len(ordered) - 1)) // len(ordered))

    blocks = []
    for column in ordered:
        group = by_column.get(column["id"], [])
        lines = ["{} · {}".format(column["name"].upper(), len(group)), "─" * width]
        if not group:
            lines += ["", "  (empty)"]
        for card in group:
            lines += card_box(card, width, board.get("card_prefix"), epics)
        blocks.append(lines)

    tall = max(len(b) for b in blocks)
    for block in blocks:
        block.extend([""] * (tall - len(block)))
    for row in zip(*blocks):
        print((" " * GAP).join(cell.ljust(width) for cell in row).rstrip())


def show_next(api, board_name):
    """The next card AND its acceptance, in one command.

    `card list` returns no description, so finding what to do next and what proves
    it done otherwise costs two calls and a uuid copied between them.
    """
    board, columns, cards = state(api, board_name)
    todo = next((c["id"] for c in columns
                 if str(c.get("default_status")) == "todo"), None)
    waiting = sorted((c for c in cards if c["column_id"] == todo),
                     key=lambda c: c["card_number"])  # board-id-ok: ordering only
    if not waiting:
        print("nothing waiting in the todo column")
        return
    card = api("card", "get", waiting[0]["id"])
    print("{}  {}\n".format(identifier(board.get("card_prefix"), card), card["title"]))
    print(card.get("description") or "(no description — the document has no `## Done when`)")


def main(argv):
    args = [a for a in argv if a != "--next"]
    if len(args) < 2:
        sys.stderr.write("usage: show.py <board-file> <board-name> [--next]\n")
        return 2
    api = Kanban(args[0])
    if "--next" in argv:
        show_next(api, args[1])
    else:
        render(api, args[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
