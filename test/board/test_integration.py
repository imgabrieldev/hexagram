import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from board_test_helper import Board, SYNC_PATH


def has_kanban():
    return shutil.which("kanban") is not None


def cards(board, name):
    out = subprocess.check_output(["kanban", board, "card", "list", "--board", name])
    return json.loads(out.decode("utf-8"))["data"]["items"]


class IntegrationCase(unittest.TestCase):
    def setUp(self):
        if not has_kanban():
            self.skipTest("kanban not on PATH")
        self.dir = tempfile.mkdtemp()
        self.docs = os.path.join(self.dir, "docs")
        self.board = os.path.join(self.dir, ".kanban.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, rel, text):
        path = os.path.join(self.docs, *rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path


class SmokeTest(IntegrationCase):
    def test_a_pitch_becomes_a_card_and_gets_its_uuid_back(self):
        pitch = self.write(("pitches", "thing.md"),
                           "---\nstatus: active\n---\n\n# Pitch — Thing\n\nbody\n")
        Board.init(self.board, "Work", "HEX")

        Board.sync(self.docs, self.board, "Work")

        with open(pitch, encoding="utf-8") as fh:
            data, _ = Board.Frontmatter.parse(fh.read())
        self.assertIsNotNone(data.get("kanban"))
        items = cards(self.board, "Work")
        self.assertEqual(1, len(items))
        self.assertEqual("Pitch — Thing", items[0]["title"])
        self.assertEqual(data["kanban"], items[0]["id"])


class SinglePassLinkTest(IntegrationCase):
    def test_one_sync_creates_cards_and_links_them(self):
        self.write(("pitches", "alpha.md"), "---\nstatus: active\n---\n\n# Alpha\n")
        self.write(("plans", "alpha", "slice-01-a.md"), "# Slice 01\n")
        Board.init(self.board, "Work", "HEX")

        r = Board.sync(self.docs, self.board, "Work")

        self.assertEqual(2, r.created)
        self.assertEqual(1, r.linked, "a single sync must link, not need a second run")

        again = Board.sync(self.docs, self.board, "Work")
        self.assertEqual(0, again.created)
        self.assertEqual(0, again.linked)


class RebuildTest(IntegrationCase):
    def test_deleting_the_board_and_re_syncing_reproduces_it_with_statuses(self):
        self.write(("pitches", "alpha.md"), "---\nstatus: active\n---\n\n# Alpha\n")
        self.write(("plans", "alpha", "slice-01-a.md"), "---\nstatus: done\n---\n\n# Slice 01\n")
        Board.init(self.board, "W", "HEX")
        Board.sync(self.docs, self.board, "W")

        os.remove(self.board)
        Board.init(self.board, "W", "HEX")
        r = Board.sync(self.docs, self.board, "W")

        self.assertEqual(2, r.created, "a wiped board must be re-created from the files")
        self.assertEqual(1, r.linked)
        by_title = {c["title"]: Board.canonical_status(c["status"])
                    for c in cards(self.board, "W")}
        self.assertEqual("done", by_title["Slice 01"], "status must survive the rebuild")
        self.assertEqual("in_progress", by_title["Alpha"])


class PrefixTest(IntegrationCase):
    def test_init_sets_the_prefix_atomically_and_numbering_stays_clean(self):
        Board.init(self.board, "Work", "HEX")
        for i in range(3):
            subprocess.run(["kanban", self.board, "card", "create", "--board", "Work",
                            "--column", "TODO", "--title", "c{}".format(i)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        nums = sorted(c["card_number"] for c in cards(self.board, "Work"))

        self.assertEqual([1, 2, 3], nums)
        self.assertEqual(len(set(nums)), len(nums),
                         "duplicate card_number means the prefix trigger was hit")


class CorruptBoardTest(unittest.TestCase):
    # The sync is immune to the upstream numbering defect only because it never
    # addresses a card by PREFIX-N. This is that claim, as a test.
    def test_reconcile_is_correct_even_with_duplicate_numbers(self):
        from datetime import datetime, timezone
        docs = [Board.Doc(path="a.md", kind="pitch", title="A", status="done",
                          uuid="u-a", body="", data={},
                          mtime=datetime.fromtimestamp(9999, timezone.utc))]
        cards_ = [{"id": "u-a", "status": "Todo", "card_number": 1,
                   "updated_at": "1970-01-01T00:00:00Z"},
                  {"id": "u-b", "status": "Todo", "card_number": 1,
                   "updated_at": "1970-01-01T00:00:00Z"}]

        ops = Board.reconcile(docs, cards_)

        self.assertEqual("u-a", next(o for o in ops if o.kind == "set_status").uuid)
        self.assertEqual(["u-b"], [o.uuid for o in ops if o.kind == "orphan"])


class GracefulAbsenceTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def digest(self, root):
        acc = []
        for base, _, names in os.walk(root):
            for n in sorted(names):
                p = os.path.join(base, n)
                with open(p, "rb") as fh:
                    acc.append(p + hashlib.sha256(fh.read()).hexdigest())
        return "".join(sorted(acc))

    def test_missing_binary_exits_127_and_touches_nothing(self):
        docs = os.path.join(self.dir, "docs", "pitches")
        os.makedirs(docs)
        with open(os.path.join(docs, "a.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nstatus: active\n---\n\n# A\n")

        before = self.digest(self.dir)
        # NOT PATH="": the interpreter itself has to stay reachable. /usr/bin:/bin
        # has python3 and does not have kanban, which is exactly the state under test.
        env = dict(os.environ, PATH="/usr/bin:/bin")
        proc = subprocess.run([sys.executable, SYNC_PATH,
                               os.path.join(self.dir, "docs"),
                               os.path.join(self.dir, ".kanban.json"), "Work"],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        self.assertEqual(127, proc.returncode)
        self.assertIn(b"cargo install kanban-cli", proc.stdout)
        self.assertEqual(before, self.digest(self.dir),
                         "a failed run must not modify the docs tree")


if __name__ == "__main__":
    unittest.main()
