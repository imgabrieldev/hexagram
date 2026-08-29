import unittest

from board_test_helper import Board


class FrontmatterTest(unittest.TestCase):
    WITH = "---\ntags:\n  - pitch\nstatus: active\n---\n\n# Title\n\nbody --- with dashes\n"

    def test_parses_flat_keys(self):
        data, body = Board.Frontmatter.parse(self.WITH)
        self.assertEqual("active", data["status"])
        self.assertTrue(body.startswith("\n# Title"))

    def test_indented_list_items_are_skipped_not_misread(self):
        data, _ = Board.Frontmatter.parse(self.WITH)
        self.assertNotIn("- pitch", data)
        self.assertIn("tags", data)

    def test_no_frontmatter_returns_empty_and_whole_text(self):
        text = "# Just a slice\n\n## Done when\n\n`rake test` is green\n"
        data, body = Board.Frontmatter.parse(text)
        self.assertEqual({}, data)
        self.assertEqual(text, body)

    def test_set_is_visible_to_parse_and_leaves_the_body_alone(self):
        _, body = Board.Frontmatter.parse(self.WITH)
        data, again = Board.Frontmatter.parse(Board.Frontmatter.set(self.WITH, "kanban", "u-1"))
        self.assertEqual("u-1", data["kanban"])
        self.assertEqual("active", data["status"])
        self.assertEqual(body, again)

    def test_set_onto_a_bare_file_keeps_the_body(self):
        text = "# Just a slice\n\nprose\n"
        out = Board.Frontmatter.set(Board.Frontmatter.set(text, "status", "todo"), "kanban", "u-1")
        data, body = Board.Frontmatter.parse(out)
        self.assertEqual({"status": "todo", "kanban": "u-1"}, data)
        self.assertEqual(text, body)


class DocTest(unittest.TestCase):
    def test_title_from_the_first_heading(self):
        doc = Board.Doc.from_text("---\nstatus: active\n---\n\n# Pitch — Board\n\nbody\n",
                                  "docs/pitches/board.md", "pitch")
        self.assertEqual("Pitch — Board", doc.title)
        self.assertEqual("active", doc.status)
        self.assertIsNone(doc.uuid)

    def test_title_falls_back_to_the_filename_stem(self):
        doc = Board.Doc.from_text("just prose\n", "docs/pitches/no-heading.md", "pitch")
        self.assertEqual("no-heading", doc.title)


if __name__ == "__main__":
    unittest.main()
