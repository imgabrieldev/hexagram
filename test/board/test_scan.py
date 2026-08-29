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
        self.assertEqual("Slice 01 — A", s.title)

    def test_readme_is_not_a_slice(self):
        self.assertFalse(any(d.path.endswith("README.md") for d in Board.scan_slices(self.docs)))

    def test_fractional_names_are_scanned_and_sorted(self):
        names = [os.path.basename(d.path) for d in Board.scan_slices(self.docs)]
        self.assertEqual(["slice-01-a.md", "slice-01b-b.md", "slice-02.1-c.md"], names)

    def test_parent_resolves_to_the_pitch_of_the_same_name(self):
        s = Board.scan_slices(self.docs)[0]
        self.assertEqual(os.path.join(self.docs, "pitches", "board.md"), s.parent_path)

    def test_done_when_becomes_part_of_the_description(self):
        s = [d for d in Board.scan_slices(self.docs) if d.path.endswith("slice-01-a.md")][0]
        desc = Board.description_for(s)
        self.assertIn("`rake test` is green", desc)
        self.assertIn("slice-01-a.md", desc)


class PitchScanTest(TreeCase):
    def test_readme_is_not_a_pitch(self):
        self.write(("pitches", "README.md"), "# Pitches\n\nWhat this folder is for.\n")
        self.write(("pitches", "real.md"), "---\nstatus: active\n---\n\n# Real\n")
        self.write(("pitches", "archive", "old.md"), "---\nstatus: done\n---\n\n# Old\n")

        names = [os.path.basename(d.path) for d in Board.scan_pitches(self.docs)]

        self.assertEqual(["real.md"], names)


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
