import os
import shutil
import tempfile
import unittest

from board_test_helper import Board


class SurgicalWriteTest(unittest.TestCase):
    ORIGINAL = "---\ntags:\n  - plan\n  - area/clients\nstatus: todo\n---\n\n# Plan\n\nbody\n"

    def test_adding_a_key_touches_exactly_one_line(self):
        out = Board.Frontmatter.set(self.ORIGINAL, "kanban", "u-1")
        before, after = self.ORIGINAL.splitlines(True), out.splitlines(True)
        self.assertEqual(["kanban: u-1\n"], [l for l in after if l not in before])
        self.assertEqual([], [l for l in before if l not in after])

    def test_list_indentation_is_preserved(self):
        out = Board.Frontmatter.set(self.ORIGINAL, "kanban", "u-1")
        self.assertIn("tags:\n  - plan\n  - area/clients\n", out)

    def test_updating_an_existing_key_replaces_only_that_line(self):
        out = Board.Frontmatter.set(self.ORIGINAL, "status", "done")
        self.assertIn("status: done\n", out)
        self.assertNotIn("status: todo\n", out)
        self.assertIn("  - area/clients\n", out)

    def test_comments_in_frontmatter_survive(self):
        text = "---\n# why this is here\nstatus: todo\n---\n\nbody\n"
        out = Board.Frontmatter.set(text, "kanban", "u-1")
        self.assertIn("# why this is here\n", out)

    def test_a_bare_file_gets_a_block_and_keeps_its_body(self):
        text = "# Just a plan\n\nbody\n"
        out = Board.Frontmatter.set(text, "kanban", "u-1")
        self.assertEqual("---\nkanban: u-1\n---\n" + text, out)


class WriteBackTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_inserts_a_block_into_a_bare_file_and_keeps_the_body(self):
        path = os.path.join(self.dir, "slice-01-a.md")
        body = "# Slice 01 - A\n\n## Done when\n\n`rake test` is green\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        doc = Board.Doc.from_text(body, path, "slice")

        Board.write_back(doc, {"status": "doing", "kanban": "u1"})

        with open(path, encoding="utf-8") as fh:
            data, out_body = Board.Frontmatter.parse(fh.read())
        self.assertEqual({"status": "doing", "kanban": "u1"}, data)
        self.assertEqual(body, out_body)

    def test_preserves_existing_key_order(self):
        path = os.path.join(self.dir, "p.md")
        text = "---\ntags:\n  - pitch\nstatus: active\nkanban: u1\n---\n\n# P\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        doc = Board.Doc.from_text(text, path, "pitch")

        Board.write_back(doc, {"status": "done"})

        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertLess(content.index("tags:"), content.index("status:"))
        self.assertLess(content.index("status:"), content.index("kanban:"))
        self.assertIn("  - pitch\n", content)


if __name__ == "__main__":
    unittest.main()
