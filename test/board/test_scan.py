import os
import shutil
import tempfile
import unittest

from board_test_helper import Board


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.docs = os.path.join(self.dir, "docs")
        for sub in (("pitches", "archive"), ("plans", "board"),
                    ("superpowers", "plans"), ("superpowers", "specs")):
            os.makedirs(os.path.join(self.docs, *sub))

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, rel, text):
        path = os.path.join(self.docs, *rel)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path


class SliceScanTest(TreeCase):
    def setUp(self):
        TreeCase.setUp(self)
        self.write(("pitches", "board.md"), "---\nstatus: active\n---\n\n# Pitch — Board\n")
        self.write(("plans", "board", "README.md"), "# Plan\n")
        self.write(("plans", "board", "slice-01-a.md"),
                   "# Slice 01 — A\n\n## Done when\n\n`rake test` is green\n")
        self.write(("plans", "board", "slice-01b-b.md"), "# Slice 01b — B\n")
        self.write(("plans", "board", "slice-02.1-c.md"), "# Slice 02.1 — C\n")

    def test_bare_slice_defaults_to_todo(self):
        s = [d for d in Board.scan_slices(self.docs) if d.path.endswith("slice-01-a.md")][0]
        self.assertEqual("todo", s.status)
        self.assertIsNone(s.uuid)
        self.assertEqual("[board] Slice 01 — A", s.title)

    def test_readme_is_not_a_slice(self):
        self.assertFalse(any(d.path.endswith("README.md") for d in Board.scan_slices(self.docs)))

    def test_fractional_names_are_scanned_and_sorted(self):
        names = [os.path.basename(d.path) for d in Board.scan_slices(self.docs)]
        self.assertEqual(["slice-01-a.md", "slice-01b-b.md", "slice-02.1-c.md"], names)

    def test_the_epic_label_prefixes_the_title(self):
        # The pitch of the same name as the directory is the epic, and it reaches
        # the board here rather than as a card of its own.
        s = Board.scan_slices(self.docs)[0]
        self.assertTrue(s.title.startswith("[board] "), s.title)

    def test_a_slice_with_no_pitch_keeps_its_own_title(self):
        os.makedirs(os.path.join(self.docs, "plans", "orphan"))
        self.write(("plans", "orphan", "slice-1-x.md"), "---\nstatus: todo\n---\n\n# Lone slice\n")
        s = [d for d in Board.scan_slices(self.docs) if "orphan" in d.path][0]
        self.assertEqual("Lone slice", s.title)

    def test_the_label_is_not_applied_twice(self):
        # scan runs on every sync; a title already carrying its label must not
        # grow another one.
        once = Board.scan_slices(self.docs)[0].title
        twice = Board.scan_slices(self.docs)[0].title
        self.assertEqual(once, twice)
        self.assertEqual(1, once.count("[board]"))

    def test_a_pitch_can_shorten_its_label(self):
        self.write(("pitches", "board.md"),
                   "---\nstatus: active\nepic: brd\n---\n\n# Pitch — Board\n")
        s = Board.scan_slices(self.docs)[0]
        self.assertTrue(s.title.startswith("[brd] "), s.title)

    def test_done_when_becomes_part_of_the_description(self):
        s = [d for d in Board.scan_slices(self.docs) if d.path.endswith("slice-01-a.md")][0]
        desc = Board.description_for(s)
        self.assertIn("`rake test` is green", desc)
        self.assertIn("slice-01-a.md", desc)


class EpicLabelTest(TreeCase):
    def test_readme_is_not_an_epic_and_archive_is_not_scanned(self):
        self.write(("pitches", "README.md"), "# Pitches\n\nWhat this folder is for.\n")
        self.write(("pitches", "real.md"), "---\nstatus: active\n---\n\n# Real\n")
        self.write(("pitches", "archive", "old.md"), "---\nstatus: done\n---\n\n# Old\n")

        self.assertEqual({"real": "real"}, Board.epic_labels(self.docs))

    def test_the_directory_name_is_the_default_label(self):
        self.write(("pitches", "checkout-flow.md"), "---\nstatus: active\n---\n\n# A long pitch title\n")
        self.assertEqual("checkout-flow", Board.epic_labels(self.docs)["checkout-flow"])

    def test_frontmatter_overrides_it(self):
        self.write(("pitches", "checkout-flow.md"), "---\nstatus: active\nepic: checkout\n---\n\n# A long pitch title\n")
        self.assertEqual("checkout", Board.epic_labels(self.docs)["checkout-flow"])


class SuperpowersPlanScanTest(TreeCase):
    def setUp(self):
        TreeCase.setUp(self)
        self.write(("superpowers", "plans", "2026-07-16-bare.md"),
                   "# Bare Plan — Implementation Plan\n\nbody\n")
        self.write(("superpowers", "plans", "2026-08-11-tagged.md"),
                   "---\ntags:\n  - plan\n  - area/clients\nstatus: todo\n---\n\n# Tagged Plan\n")
        self.write(("superpowers", "specs", "2026-07-16-a-design.md"), "# A Design\n")

    def test_scans_plans_and_not_specs(self):
        names = [os.path.basename(d.path) for d in Board.scan_superpowers_plans(self.docs)]
        self.assertEqual(["2026-07-16-bare.md", "2026-08-11-tagged.md"], names)

    def test_a_bare_plan_defaults_to_todo_and_has_no_parent(self):
        d = [x for x in Board.scan_superpowers_plans(self.docs) if x.path.endswith("bare.md")][0]
        self.assertEqual("plan", d.kind)
        self.assertEqual("todo", d.status)
        self.assertIsNone(d.parent_path)
        self.assertEqual("Bare Plan — Implementation Plan", d.title)

    def test_an_existing_status_is_respected(self):
        d = [x for x in Board.scan_superpowers_plans(self.docs) if x.path.endswith("tagged.md")][0]
        self.assertEqual("todo", d.status)


if __name__ == "__main__":
    unittest.main()
