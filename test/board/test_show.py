import io
import os
import sys
import unittest
from contextlib import redirect_stderr

from board_test_helper import Show


CARD = {"id": "u1", "card_number": 7, "title": "Checkpoint 1 — Scaffold and schema"}
PLAIN = {"id": "u2", "card_number": 12, "title": "Something with no dash"}


class IdentifierTest(unittest.TestCase):
    """PREFIX-N is display only — a card is addressed by uuid everywhere else,
    because upstream renumbers if a board's prefix changes after cards exist."""

    def test_uses_the_boards_own_prefix(self):
        # Hardcoding one repo's prefix is the bug this replaced.
        self.assertEqual(Show.identifier("HEX", CARD), "HEX-7")
        self.assertEqual(Show.identifier("IMC", CARD), "IMC-7")

    def test_a_board_with_no_prefix_still_renders(self):
        for empty in (None, ""):
            self.assertEqual(Show.identifier(empty, CARD), "7")


class CardBoxTest(unittest.TestCase):
    def box(self, card, width=32, prefix="HEX", epics=()):
        return Show.card_box(card, width, prefix, set(epics))

    def test_every_line_is_exactly_the_box_width(self):
        # Columns are printed side by side, so one ragged line shears the board.
        for line in self.box(CARD):
            self.assertEqual(len(line), 32, repr(line))

    def test_the_em_dash_splits_heading_from_body(self):
        body = "\n".join(self.box(CARD))
        self.assertIn("Checkpoint 1", body)
        self.assertIn("Scaffold and schema", body)

    def test_a_title_with_no_dash_still_renders(self):
        self.assertIn("Something with no dash", "\n".join(self.box(PLAIN)))

    def test_an_epic_is_marked_and_a_task_is_not(self):
        self.assertIn("EPIC", "\n".join(self.box(CARD, epics=["u1"])))
        self.assertNotIn("EPIC", "\n".join(self.box(CARD)))

    def test_a_long_title_does_not_overflow_the_box(self):
        long = {"id": "u3", "card_number": 1,
                "title": "A — " + "word " * 40}
        for line in self.box(long):
            self.assertEqual(len(line), 32)

    def test_a_narrow_box_does_not_crash_on_the_epic_tag(self):
        # inner width can be smaller than "EPIC"; ljust must not go negative.
        for line in self.box(CARD, width=Show.MIN_CARD, epics=["u1"]):
            self.assertEqual(len(line), Show.MIN_CARD)


class UsageTest(unittest.TestCase):
    def test_too_few_arguments_exits_non_zero(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(Show.main([]), 2)
            self.assertEqual(Show.main(["board.json"]), 2)


class ReadOnlyTest(unittest.TestCase):
    def test_it_never_calls_a_writing_subcommand(self):
        """The renderer must not be able to become a second source of truth.

        Moving a card is a `status:` edit plus sync, so the move lands in a diff.
        """
        source = open(os.path.join(os.path.dirname(Show.__file__), "show.py")
                      if hasattr(Show, "__file__") else Show.SOURCE_PATH,
                      encoding="utf-8").read()
        for verb in ('"create"', '"update"', '"move"', '"delete"', '"add"'):
            self.assertNotIn(verb, source, "show.py must stay read-only")


if __name__ == "__main__":
    unittest.main()
