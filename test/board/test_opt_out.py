import unittest

from board_test_helper import Board


def doc(**data):
    return Board.Doc.from_text(
        "---\n" + "".join("%s: %s\n" % kv for kv in data.items()) + "---\n\n# A title\n",
        "docs/plans/x/slice-1-a.md", "slice")


class OnBoardTest(unittest.TestCase):
    """`board: false` is what keeps a plan broken into slices from appearing
    twice -- once as itself and once as its children."""

    def test_a_document_with_no_board_key_gets_a_card(self):
        self.assertTrue(Board.on_board(doc(status="todo")))

    def test_board_false_opts_out(self):
        self.assertFalse(Board.on_board(doc(status="todo", board="false")))

    def test_the_other_spellings_opt_out_too(self):
        for value in ("no", "skip", "off", "False", "SKIP", " no "):
            self.assertFalse(Board.on_board(doc(board=value)),
                             "%r should opt out" % value)

    def test_board_true_is_not_an_opt_out(self):
        # Only the negative spellings count, so `board: true` reads as "yes"
        # rather than as an unrecognised value that silently hides the card.
        self.assertTrue(Board.on_board(doc(board="true")))

    def test_an_unrecognised_value_keeps_the_card(self):
        # Failing open matters: a typo in the frontmatter must not make work
        # disappear from the board with no error anywhere.
        self.assertTrue(Board.on_board(doc(board="maybe")))


class DoingWipTest(unittest.TestCase):
    def test_the_doing_limit_is_one(self):
        # One, because the audience is one person. The Kanban Guide requires the
        # control and leaves the number open; this is the personal-kanban default.
        self.assertEqual(Board.DOING_WIP, 1)


if __name__ == "__main__":
    unittest.main()
