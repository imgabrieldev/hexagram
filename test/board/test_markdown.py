"""The markdown subset. Pure functions, so no fixtures and no filesystem.

Every case here is a defect that was actually produced by rendering the 89 slice
documents on the author's machine, not a hypothetical.
"""
import unittest

from board_test_helper import Markdown as M


class InlineTest(unittest.TestCase):
    def test_bold_survives_a_code_span_inside_it(self):
        # Splitting on backticks first severs the ** pair. This shape appears in
        # 55 of 89 documents, so the bug hid in plain sight on most pages.
        self.assertEqual(M.inline("**`pnpm lint` runs**"),
                         "<strong><code>pnpm lint</code> runs</strong>")

    def test_a_double_backtick_span_keeps_its_inner_backticks(self):
        # The form used when the code itself contains a backtick. Matching the
        # single-backtick pattern first ate its innards and produced garbage.
        self.assertEqual(M.inline("in the form `` - `path` ``."),
                         "in the form <code>- `path`</code>.")

    def test_code_content_is_escaped(self):
        self.assertEqual(M.inline("`a > b`"), "<code>a &gt; b</code>")

    def test_markup_in_prose_is_escaped(self):
        self.assertIn("&lt;script&gt;", M.inline("<script>x</script>"))

    def test_a_link_is_the_callers_decision(self):
        keep = M.inline("[docs](https://example.com)", lambda t: t)
        self.assertIn('href="https://example.com"', keep)
        # Returning nothing drops the link and keeps the text, which is what a
        # renderer should do with a scheme it was not asked to follow.
        self.assertEqual(M.inline("[x](javascript:alert(1))", lambda t: ""), "x")

    def test_no_resolver_means_no_links_at_all(self):
        self.assertEqual(M.inline("[x](y)"), "[x](y)")


class ListTest(unittest.TestCase):
    def test_a_nested_list_sits_inside_its_item(self):
        # A <ul> whose child is a <ul> renders in every browser and parses in
        # none. The nested list belongs inside the <li> above it.
        out = M.blocks("- a\n- b\n  - nested\n- c")
        self.assertIn("<li>b<ul><li>nested</li></ul></li>", out)
        self.assertNotIn("</li><ul>", out)

    def test_emphasis_wraps_across_a_continuation_line(self):
        # Converting each line on its own severed the pair and left the
        # asterisks on the page. The raw text is joined before conversion.
        out = M.blocks("- it measures **26 files, 10,269 lines\n  and 6 more**.")
        self.assertIn("<strong>26 files, 10,269 lines and 6 more</strong>", out)
        self.assertNotIn("**", out)

    def test_a_numbered_list_is_an_ol(self):
        self.assertIn("<ol><li>one</li><li>two</li></ol>",
                      M.blocks("1. one\n2. two"))


class BlockTest(unittest.TestCase):
    def test_a_fence_keeps_its_language_and_escapes_its_body(self):
        out = M.blocks("```bash\necho 'a > b'\n```")
        self.assertIn('data-lang="bash"', out)
        self.assertIn("&gt;", out)
        self.assertNotIn("```", out)

    def test_a_table_drops_the_separator_and_heads_with_the_first_row(self):
        out = M.blocks("| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<th>a</th><th>b</th>", out)
        self.assertIn("<td>1</td><td>2</td>", out)
        self.assertNotIn("---", out)

    def test_a_wide_table_can_scroll_without_the_page_scrolling(self):
        self.assertIn('class="scrollx"', M.blocks("| a |\n|---|\n| 1 |"))

    def test_a_blockquote_joins_its_lines(self):
        self.assertEqual(M.blocks("> one\n> two"),
                         "<blockquote>one two</blockquote>")

    def test_a_warning_paragraph_is_marked(self):
        # These documents open callouts with the sign; a stylesheet can only
        # treat it as one if the renderer says which paragraph it was.
        self.assertIn('<p class="warn">', M.blocks("⚠️ careful"))
        self.assertIn("<p>", M.blocks("ordinary"))

    def test_headings_below_h2_are_kept(self):
        # h1 and h2 are the page's own; the document's own start at h3.
        self.assertIn("<h3>Deeper</h3>", M.blocks("### Deeper"))


if __name__ == "__main__":
    unittest.main()
