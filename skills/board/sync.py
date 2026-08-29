#!/usr/bin/env python3
"""Projects hexagram pitches and plan slices onto a kanban-rs board.

The markdown is the source of truth. The board is a derived view, and the one
field that travels back is ``status:``, so that moving a card produces a diff
you can review instead of state stranded in a JSON file.

PORTABILITY. This must run on the python3 that ships with macOS, which is
3.9 -- NOT the newer one a developer has on PATH. That rules out ``match``
statements and ``X | Y`` annotations, both 3.10+. Verified by running the
suite under /usr/bin/python3.

Stdlib only, deliberately: the plugin is cloned into a cache with no install
step, so anything it imports has to already be on a stranger's machine. That
also means no PyYAML -- which costs nothing here, because the only frontmatter
this reads is flat scalar keys, and the only frontmatter it writes is one line
at a time.
"""

import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

FENCE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)
SCALAR = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*)$")
HEADING = re.compile(r"^#\s+(.+)$", re.M)
DONE_WHEN = re.compile(r"^##\s+Done when\s*\n+(.+?)(?=\n##\s|\Z)", re.S | re.M)

INDEX_FILES = ("README.md",)

# The WIP limit set on the Doing column at init. One, because the audience is one
# person: the personal-kanban recommendation for a single developer is Doing = 1,
# and every hexagram repo already carries the same rule in prose -- "one thing at
# a time", "frozen scope per checkpoint". See `board: false` below for the other
# half of the same idea: what a board must not show.
DOING_WIP = 1

# A document opts out of the board with `board: false` in its frontmatter.
# It exists because a plan broken into slices would otherwise appear twice --
# once as itself and once as its eight children -- and the duplicate is noise
# that no amount of column policy fixes. Name-matching the plan to its slice
# directory was the alternative and it is worse: the names legitimately differ,
# so the magic would work by luck and fail silently.
OPT_OUT = ("false", "no", "skip", "off")

STATUS_TO_KANBAN = {
    "todo": "todo",
    "doing": "in_progress",
    "blocked": "blocked",
    "done": "done",
    "active": "in_progress",  # the vocabulary pitches already use
}
KANBAN_TO_STATUS = {
    "todo": "todo",
    "in_progress": "doing",
    "blocked": "blocked",
    "done": "done",
}
# kanban writes its statuses two ways: `card list` returns TitleCase with no
# separator ("InProgress") while `card get` and the REST API return snake_case
# ("in_progress"). Downcasing alone is not enough -- "inprogress" is not
# "in_progress" -- and getting it wrong made every linked card look changed on
# every run. Strip the separator, then look it up.
CANONICAL_STATUS = {
    "todo": "todo",
    "inprogress": "in_progress",
    "blocked": "blocked",
    "done": "done",
}


def canonical_status(raw):
    return CANONICAL_STATUS.get(str(raw or "").lower().replace("_", ""), "todo")


def same_status(one, other):
    return canonical_status(one) == canonical_status(other)


class Frontmatter:
    """Reads flat scalar keys; writes one line at a time."""

    @staticmethod
    def parse(text):
        """-> (dict, body). A file with no block yields ({}, whole_text).

        Only top-level ``key: value`` lines are read. Indented lines, list
        items and comments are skipped rather than parsed: the only keys this
        program needs are ``status`` and ``kanban``, both flat strings, and a
        hand-rolled parser that tried to do more would be a liability.
        """
        m = FENCE.match(text)
        if not m:
            return {}, text

        data = {}
        for line in m.group(1).splitlines():
            hit = SCALAR.match(line)
            if hit:
                data[hit.group(1)] = hit.group(2).strip().strip("\"'")
        return data, text[m.end():]

    @staticmethod
    def set(text, key, value):
        """Sets ONE key as a line edit, leaving every other byte alone.

        Re-serialising a parsed mapping was the obvious implementation and it
        was wrong: a YAML dumper writes its own indentation, so ``tags:\\n  -
        plan`` came back as ``tags:\\n- plan`` and a one-line change showed up
        in git as five. A round trip through a parser also deletes comments
        inside the block. A document this touches should show exactly the line
        it came to write.
        """
        line = "{}: {}\n".format(key, value)
        m = FENCE.match(text)
        if not m:
            return "---\n" + line + "---\n" + text

        block = m.group(1)
        existing = re.compile(r"^" + re.escape(key) + r":.*\n?", re.M)
        if existing.search(block):
            block = existing.sub(line, block, count=1)
        else:
            block = block.rstrip("\n") + "\n" + line
        return "---\n" + block.rstrip("\n") + "\n" + "---\n" + text[m.end():]


class Doc:
    __slots__ = ("path", "kind", "title", "status", "uuid", "body", "data",
                 "parent_path", "mtime")

    def __init__(self, path, kind, title, status, uuid, body, data,
                 parent_path=None, mtime=None):
        self.path = path
        self.kind = kind
        self.title = title
        self.status = status
        self.uuid = uuid
        self.body = body
        self.data = data
        self.parent_path = parent_path
        self.mtime = mtime

    @classmethod
    def load(cls, path, kind, parent_path=None):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        return cls.from_text(text, path, kind, parent_path,
                             datetime.fromtimestamp(os.path.getmtime(path), timezone.utc))

    @classmethod
    def from_text(cls, text, path, kind, parent_path=None, mtime=None):
        data, body = Frontmatter.parse(text)
        heading = HEADING.search(body)
        default = "todo" if kind in ("slice", "plan") else None
        return cls(
            path=path, kind=kind, body=body, data=data, parent_path=parent_path,
            mtime=mtime,
            title=heading.group(1) if heading else os.path.basename(path)[:-3],
            status=data.get("status") or default,
            uuid=data.get("kanban") or None,
        )


class Op:
    __slots__ = ("kind", "path", "paths", "uuid", "parent_uuid", "status",
                 "column_id", "doc")

    def __init__(self, kind, path=None, paths=None, uuid=None, parent_uuid=None,
                 status=None, column_id=None, doc=None):
        self.kind = kind
        self.path = path
        self.paths = paths
        self.uuid = uuid
        self.parent_uuid = parent_uuid
        self.status = status
        self.column_id = column_id
        self.doc = doc


class Report:
    def __init__(self):
        self.created = 0
        self.updated = 0
        self.moved = 0
        self.linked = 0
        self.written = 0
        self.orphans = []
        self.conflicts = []

    def merge(self, other):
        merged = Report()
        merged.created = self.created + other.created
        merged.updated = self.updated + other.updated
        merged.moved = self.moved + other.moved
        merged.linked = self.linked + other.linked
        merged.written = self.written + other.written
        merged.orphans = other.orphans
        merged.conflicts = self.conflicts + [
            c for c in other.conflicts if c not in self.conflicts
        ]
        return merged


class KanbanMissing(Exception):
    pass


class KanbanFailed(Exception):
    pass


class Kanban:
    def __init__(self, board_file):
        self.board_file = board_file

    def run(self, *args):
        """Every call goes through here: one place parses the
        {success, api_version, data} envelope and one place raises."""
        try:
            proc = subprocess.run(["kanban", self.board_file] + list(args),
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            raise KanbanMissing("kanban is not on PATH")

        if proc.returncode != 0:
            raise KanbanFailed("kanban {} failed".format(" ".join(args)))

        payload = json.loads(proc.stdout.decode("utf-8"))
        if not payload.get("success"):
            raise KanbanFailed(str(payload.get("error")))
        return payload["data"]

    def create_card(self, board, column, title, status, description):
        """`card create` has no --status flag on the shipped 0.9.0 CLI, so
        status is a second call. Verified against the binary, not read from
        the README -- which disagrees with the binary in two other places."""
        card = self.run("card", "create", "--board", board, "--column", column,
                        "--title", title, "--description", description)
        self.run("card", "update", card["id"], "--status", status)
        return card["id"]


# Index files are not pitches. docs/pitches/README.md explains what the folder
# is for and every hexagram repo has one -- scanning it produced a card titled
# "Pitches" on the first real repo this ran against. The slice glob never had
# this problem because it matches slice-*.md.
#
# Root only, deliberately: archive/ and future/ are where a pitch MOVES when it
# stops being current, so a board of active work should not show them.
def scan_pitches(root):
    paths = sorted(glob.glob(os.path.join(root, "pitches", "*.md")))
    return [Doc.load(p, "pitch") for p in paths
            if os.path.basename(p) not in INDEX_FILES]


# The glob is slice-*.md, which is what excludes README.md. The plain
# lexicographic sort is what puts slice-01b between 01 and 02.1 -- do NOT "fix"
# it with a numeric parse: fractional names are deliberate, and normalising them
# throws away the record of what actually happened.
def scan_slices(root):
    docs = []
    for path in sorted(glob.glob(os.path.join(root, "plans", "*", "slice-*.md"))):
        feature = os.path.basename(os.path.dirname(path))
        pitch = os.path.join(root, "pitches", feature + ".md")
        docs.append(Doc.load(path, "slice",
                             parent_path=pitch if os.path.exists(pitch) else None))
    return docs


# Plans written by the superpowers skills live here rather than under
# docs/plans, and they are a single file with the tasks inside instead of a
# directory of slices. So each one is a top-level card with no parent -- there
# is nothing to be a child of, and inventing a synthetic parent would put a box
# on the board that no document backs.
#
# specs/ next door is deliberately not scanned: a spec is a design record, not
# work with a status.
def scan_superpowers_plans(root):
    paths = sorted(glob.glob(os.path.join(root, "superpowers", "plans", "*.md")))
    return [Doc.load(p, "plan") for p in paths
            if os.path.basename(p) not in INDEX_FILES]


def on_board(doc):
    """Pure: does this document want a card?

    A document opts out with `board: false`. ⚠️ It only stops a card being
    CREATED -- nothing here ever deletes, so adding `board: false` to a document
    that already synced leaves the card behind, and the run reports it as an
    orphan. Removing it is a deliberate `kanban card delete`.
    """
    return str(doc.data.get("board", "")).strip().lower() not in OPT_OUT


def description_for(doc):
    """What an agent needs in order to act without opening the file first."""
    hit = DONE_WHEN.search(doc.body)
    done = hit.group(1).strip() if hit else ""
    return "{}\n\nDone when: {}".format(doc.path, done) if done else doc.path


def _card_time(card):
    raw = str(card.get("updated_at") or "")
    try:
        return datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        # An unparseable timestamp must not silently beat the file.
        return datetime.fromtimestamp(0, timezone.utc)


def reconcile(docs, cards, parents=None, edges=None, columns=None):
    """Pure: (docs, cards) -> [Op]. No IO, no process, no clock."""
    parents = parents or {}
    edges = edges or []
    columns = columns or []

    by_id = {c["id"]: c for c in cards}
    claimed = {}
    for d in docs:
        if d.uuid:
            claimed.setdefault(d.uuid, []).append(d.path)

    ops = []
    seen = set()

    for d in docs:
        if d.uuid is None:
            ops.append(Op("create", path=d.path, doc=d))
            continue

        if len(claimed[d.uuid]) > 1:
            if d.uuid not in seen:
                ops.append(Op("conflict", uuid=d.uuid, paths=claimed[d.uuid]))
            seen.add(d.uuid)
            continue

        card = by_id.get(d.uuid)
        if card is None:
            # The file points at a card that no longer exists -- the board was
            # deleted, or rebuilt elsewhere. Re-create and overwrite the link.
            # This is what makes "delete .kanban.json and re-sync" reproduce the
            # board, which is the whole justification for gitignoring it.
            ops.append(Op("create", path=d.path, doc=d))
            continue

        want = STATUS_TO_KANBAN.get(d.status, "todo")

        # Status and column are separate in kanban: setting one does not place
        # the other, and a board where every card sits in TODO is not a board.
        # The column follows the status, because the markdown owns the status.
        home = next((c for c in columns if str(c.get("default_status")) == want), None)
        here = next((c for c in columns if c["id"] == card.get("column_id")), None)
        if home and here and here.get("default_status") is not None \
                and here["id"] != home["id"]:
            ops.append(Op("move", uuid=d.uuid, column_id=home["id"], path=d.path))

        if same_status(card.get("status"), want):
            continue

        # The tie goes to the file, deliberately: markdown is the source of
        # truth, so where the evidence is ambiguous the tool yields. A write_file
        # op also changes the mtime, which stops the next run flapping back.
        if d.mtime is not None and _card_time(card) > d.mtime:
            ops.append(Op("write_file", uuid=d.uuid, path=d.path, doc=d,
                          status=KANBAN_TO_STATUS.get(canonical_status(card.get("status")), "todo")))
        else:
            ops.append(Op("set_status", uuid=d.uuid, status=d.status, path=d.path, doc=d))

    # BOTH cards have to exist before an edge between them can. After a board is
    # wiped, every file still carries its old uuid, so without these two guards
    # this emits a link between two cards that are about to be re-created and
    # kanban rejects it. The re-created pair links on the second pass.
    for d in docs:
        if d.kind != "slice" or not d.uuid or d.uuid not in by_id:
            continue
        parent_uuid = parents.get(d.path)
        if parent_uuid is None or parent_uuid not in by_id:
            continue
        if [parent_uuid, d.uuid] in edges:
            continue
        ops.append(Op("link", uuid=d.uuid, parent_uuid=parent_uuid, path=d.path))

    linked = {d.uuid for d in docs if d.uuid}
    for c in cards:
        if c["id"] not in linked:
            ops.append(Op("orphan", uuid=c["id"]))

    return ops


def write_back(doc, updates):
    """Applies each update as its own line edit, so the diff is one line per key
    actually changed and nothing else in the document moves."""
    with open(doc.path, encoding="utf-8") as fh:
        text = fh.read()
    for key, value in updates.items():
        text = Frontmatter.set(text, key, value)
    with open(doc.path, "w", encoding="utf-8") as fh:
        fh.write(text)


def init(board_file, board_name, prefix):
    """--card-prefix goes in the `board create` call and NOWHERE else. Calling
    `board update --card-prefix` on a board that already holds cards resets the
    card-number sequence and produces duplicate identifiers -- an upstream
    defect, reproduced and isolated to exactly that one operation. Creating the
    board with its prefix means the trigger is never reached. This comment
    stays: the next person to touch it will not have read the research."""
    api = Kanban(board_file)
    if not os.path.exists(board_file):
        api.run("init")
    api.run("board", "create", "--name", board_name,
            "--card-prefix", prefix, "--with-default-columns")

    # Limiting work in progress is the one Kanban practice that is not optional.
    # The Kanban Guide makes it mandatory -- "Kanban system members must
    # explicitly control the number of work items in a workflow from started to
    # finished" -- and without it a board is, in the words of the personal-kanban
    # literature, "a prettier task list": four cards in Doing is not four tasks,
    # it is four unresolved contexts.
    #
    # DOING_WIP is 1 because the audience is one person. The guide leaves the
    # mechanism open -- "any way that Kanban system members deem appropriate" --
    # so this is a default, not a law: `kanban column update <id>
    # --clear-wip-limit` removes it. It is set HERE, at init, and never by the
    # sync, so a limit a human changed later is never quietly overwritten.
    for column in api.run("column", "list", "--board", board_name)["items"]:
        if str(column.get("default_status")) == "in_progress":
            api.run("column", "update", column["id"],
                    "--wip-limit", str(DOING_WIP))
            break


def sync(docs_root, board_file, board_name):
    """A pass that creates cards cannot also link them: the parent's uuid does
    not exist until its card does. So a first pass that created anything is
    followed by a second, which sees the uuids the first one wrote."""
    first = _pass(docs_root, board_file, board_name)
    if first.created == 0:
        return first
    return first.merge(_pass(docs_root, board_file, board_name))


def _pass(docs_root, board_file, board_name):
    api = Kanban(board_file)
    docs = (scan_pitches(docs_root) + scan_slices(docs_root)
            + scan_superpowers_plans(docs_root))
    # Applied here rather than in each scanner: it holds for every kind.
    docs = [d for d in docs if on_board(d)]
    cards = api.run("card", "list", "--board", board_name)["items"]
    columns = api.run("column", "list", "--board", board_name)["items"]
    report = Report()

    by_path = {d.path: d.uuid for d in docs}
    parents = {d.path: by_path[d.parent_path] for d in docs
               if d.parent_path and d.parent_path in by_path}

    # Only ask about parents whose card actually exists. A file can point at a
    # uuid that is gone, and `relation children` on a missing card is an error,
    # not an empty list -- unguarded it aborts the sync before reconcile can
    # re-create anything, which is the case reconcile exists to handle.
    live = {c["id"] for c in cards}
    edges = []
    for pitch in docs:
        if pitch.kind == "pitch" and pitch.uuid in live:
            for child in api.run("relation", "children", pitch.uuid):
                edges.append([pitch.uuid, child["id"]])

    for op in reconcile(docs, cards, parents, edges, columns):
        if op.kind == "create":
            want = STATUS_TO_KANBAN.get(op.doc.status, "todo")
            home = next((c for c in columns
                         if str(c.get("default_status")) == want), columns[0])
            uuid = api.create_card(board_name, home["name"], op.doc.title, want,
                                   description_for(op.doc))
            write_back(op.doc, {"kanban": uuid})
            report.created += 1
        elif op.kind == "set_status":
            api.run("card", "update", op.uuid, "--status",
                    STATUS_TO_KANBAN.get(op.status, "todo"))
            report.updated += 1
        elif op.kind == "move":
            api.run("card", "move", op.uuid, "--column", op.column_id)
            report.moved += 1
        elif op.kind == "write_file":
            write_back(op.doc, {"status": op.status})
            report.written += 1
        elif op.kind == "link":
            # relation add takes POSITIONAL <PARENT> <CHILDREN>... The upstream
            # README documents --parent/--child; those flags do not exist.
            api.run("relation", "add", op.parent_uuid, op.uuid)
            report.linked += 1
        elif op.kind == "orphan":
            report.orphans.append(op.uuid)
        elif op.kind == "conflict":
            report.conflicts.append(op.paths)

    return report


def main(argv):
    args = [a for a in argv if a != "--init"]
    do_init = "--init" in argv
    if len(args) < 3:
        sys.stderr.write(
            "usage: sync.py [--init] <docs-root> <board-file> <board-name> [prefix]\n")
        return 2

    docs_root, board_file, board_name = args[0], args[1], args[2]
    prefix = args[3] if len(args) > 3 else None
    if do_init and not prefix:
        sys.stderr.write("--init needs a prefix\n")
        return 2

    try:
        if do_init:
            init(board_file, board_name, prefix)
        r = sync(docs_root, board_file, board_name)
        print("{} created, {} updated, {} moved, {} written, {} linked".format(
            r.created, r.updated, r.moved, r.written, r.linked))
        for uuid in r.orphans:
            sys.stderr.write("orphan card (not deleted): {}\n".format(uuid))
        for paths in r.conflicts:
            sys.stderr.write("conflict: {} claim the same card\n".format(" and ".join(paths)))
        return 0 if not r.conflicts else 1
    except KanbanMissing:
        sys.stderr.write("kanban is not on PATH, so nothing was read or written.\n"
                         "Install it with: cargo install kanban-cli kanban-mcp\n"
                         "Full instructions, including the Rust toolchain it needs: "
                         "skills/board/install.md\n")
        return 127
    except KanbanFailed as exc:
        sys.stderr.write("kanban rejected a command: {}\n".format(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
