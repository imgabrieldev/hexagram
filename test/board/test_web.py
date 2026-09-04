"""The HTML rendering: what a card becomes, and what a slice document becomes."""
import os
import unittest

from board_test_helper import Web, Show


def card(number, title, description=None, status="Todo", column="c1"):
    return {"id": "u{}".format(number), "card_number": number, "title": title,
            "description": description, "status": status, "column_id": column}


SLICE = """---
status: doing
kanban: 8cabb3d6
---

> **Blocked on the owner.** A rename is a settings change.

# Slice 2 — Rate limiting

## Delivers

A limiter.

## Done when

`curl` returns 429.

## If stuck

Ask.
"""


class DescriptionTest(unittest.TestCase):
    def test_the_path_and_the_acceptance_come_apart(self):
        doc, rest = Web.split_description(
            "docs/plans/api/slice-2.md\n\nDone when: it returns 429")
        self.assertEqual(doc, "docs/plans/api/slice-2.md")
        self.assertIn("429", rest)

    def test_a_description_that_is_not_a_path_is_all_acceptance(self):
        doc, rest = Web.split_description("just prose")
        self.assertEqual(doc, "")
        self.assertEqual(rest, "just prose")

    def test_no_description_at_all(self):
        self.assertEqual(Web.split_description(None), ("", ""))


class AcceptanceTest(unittest.TestCase):
    def test_a_fence_beside_the_label_is_removed_too(self):
        # `Done when: ```bash` puts the fence on the label's own line, which a
        # rule that only drops whole fence LINES leaves behind.
        out = Web.clean_acceptance("Done when: ```bash\npnpm lint\n```")
        self.assertEqual(out, "pnpm lint")

    def test_the_label_goes_because_the_disclosure_already_says_it(self):
        self.assertEqual(Web.clean_acceptance("Done when: it passes"), "it passes")


class SlugTest(unittest.TestCase):
    def test_a_path_becomes_one_flat_filename(self):
        self.assertEqual(Web.slug("docs/plans/api/slice-01-rate.md"),
                         "docs-plans-api-slice-01-rate.html")

    def test_two_documents_in_different_folders_do_not_collide(self):
        # The whole path is in the name, so `a/slice-01.md` and `b/slice-01.md`
        # cannot land on the same file and silently overwrite each other.
        self.assertNotEqual(Web.slug("a/slice-01.md"), Web.slug("b/slice-01.md"))


class DocumentTest(unittest.TestCase):
    def test_what_sits_before_the_title_is_kept(self):
        # Slices open with a blockquote saying they are blocked or closed.
        # Skipping to the heading dropped exactly that, silently.
        front, title, sections = Web.parse_document(SLICE)
        self.assertEqual(title, "Slice 2 — Rate limiting")
        self.assertEqual(front["status"], "doing")
        loose = "".join(body for name, body in sections if not name)
        self.assertIn("Blocked on the owner", loose)

    def test_sections_keep_their_names(self):
        names = [n for n, _ in Web.parse_document(SLICE)[2] if n]
        self.assertEqual(names, ["Delivers", "Done when", "If stuck"])

    def test_a_document_with_no_frontmatter_still_parses(self):
        front, title, _ = Web.parse_document("# Title\n\nBody.")
        self.assertEqual(front, {})
        self.assertEqual(title, "Title")


class OrderTest(unittest.TestCase):
    def test_the_acceptance_leads_and_the_escape_hatch_trails(self):
        sections = Web.parse_document(SLICE)[2]
        self.assertEqual(Web.section_order(sections),
                         ["Done when", "Delivers", "If stuck"])

    def test_an_unusual_section_keeps_the_documents_own_order(self):
        # Three slices do not use the standard headings and carry their
        # substance in their own. Ranking by a fixed list buried those under a
        # collapsed "If stuck".
        sections = [("Delivers", ""), ("The two options", ""),
                    ("If stuck", ""), ("Done when", "")]
        self.assertEqual(Web.section_order(sections),
                         ["Done when", "Delivers", "The two options", "If stuck"])


class CardTest(unittest.TestCase):
    def html(self, one, docs=()):
        return Web.card_html(one, "JIKAN", list(docs))

    def test_the_identifier_comes_from_show_so_the_rule_has_one_home(self):
        self.assertIn("JIKAN-7", self.html(card(7, "Slice 1 — A")))

    def test_the_epic_label_becomes_a_chip_and_leaves_the_title(self):
        out = self.html(card(3, "[checkout] Slice 2 — Rate limiting"))
        self.assertIn(">checkout<", out)
        self.assertNotIn("[checkout]", out)
        self.assertIn("Rate limiting", out)

    def test_a_blocked_card_is_marked_because_its_column_will_not_show_it(self):
        # status: blocked never moves a card, so by column it is
        # indistinguishable from one not yet picked up.
        out = self.html(card(4, "Slice 1 — A", status="Blocked"))
        self.assertIn("card blocked", out)
        self.assertIn(">blocked<", out)

    def test_only_a_document_that_exists_becomes_a_link(self):
        body = "docs/plans/api/slice-01.md\n\nDone when: ok"
        linked = self.html(card(5, "Slice 1 — A", body),
                           docs=["docs/plans/api/slice-01.md"])
        self.assertIn('href="docs-plans-api-slice-01.html"', linked)
        # A card pointing at a moved file degrades to text, never a dead link.
        self.assertNotIn("<a href", self.html(card(5, "Slice 1 — A", body)))

    def test_a_title_with_no_dash_still_renders(self):
        self.assertIn("Something plain", self.html(card(6, "Something plain")))


class BoardTest(unittest.TestCase):
    def board(self, cards):
        return Web.board_page(
            {"name": "Work", "card_prefix": "JIKAN"},
            [{"id": "c1", "name": "TODO", "position": 0, "default_status": "todo"}],
            cards, [])

    def subtitle(self, cards):
        out = self.board(cards)
        return out.split('<p class="sub">')[1].split("</p>")[0]

    def test_blocked_is_counted_in_the_summary(self):
        self.assertEqual(
            self.subtitle([card(1, "A", status="Blocked"), card(2, "B")]),
            "2 cards · 1 blocked")

    def test_a_board_with_none_blocked_says_nothing_about_it(self):
        self.assertEqual(self.subtitle([card(2, "B")]), "1 card")

    def test_the_page_asks_the_network_for_nothing(self):
        # Everything is inlined so the board works from a file:// path and in a
        # repo with no server anywhere near it.
        out = self.board([card(1, "A")])
        for scheme in ("http://", "https://", "//cdn"):
            self.assertNotIn(scheme, out)


class ReadOnlyTest(unittest.TestCase):
    def test_it_never_calls_a_writing_subcommand(self):
        """The renderer must not be able to become a second source of truth.

        Moving a card is a `status:` edit plus sync, so the move lands in a diff.
        """
        with open(Web.SOURCE_PATH, encoding="utf-8") as handle:
            source = handle.read()
        for verb in ('"create"', '"update"', '"move"', '"delete"', '"add"'):
            self.assertNotIn(verb, source, "web.py must stay read-only")

    def test_it_reads_through_the_cli_rather_than_the_board_file(self):
        with open(Web.SOURCE_PATH, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("json.load", source)
        self.assertIn("show.Kanban", source)


class UsageTest(unittest.TestCase):
    def test_too_few_arguments_is_an_error_and_writes_nothing(self):
        self.assertEqual(Web.main([]), 2)
        self.assertEqual(Web.main(["board.json", "Work"]), 2)


if __name__ == "__main__":
    unittest.main()
