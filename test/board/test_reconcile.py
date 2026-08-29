import unittest
from datetime import datetime, timezone

from board_test_helper import Board


def at(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc)


class ReconcileTest(unittest.TestCase):
    def doc(self, path, status, uuid=None):
        return Board.Doc(path=path, kind="pitch", title="T", status=status,
                         uuid=uuid, body="", data={})

    # `card list` returns TitleCase ("InProgress"), which is NOT what `card get`
    # or the REST API return. The fake uses the list shape on purpose: an earlier
    # fake used "in_progress" here, the unit test passed, and the real sync
    # reported "2 updated" on every run forever.
    def card(self, uuid, status):
        return {"id": uuid, "status": status, "title": "T"}

    def kinds(self, ops):
        return [o.kind for o in ops]

    def test_unlinked_doc_creates(self):
        ops = Board.reconcile([self.doc("a.md", "todo")], [])
        self.assertEqual(["create"], self.kinds(ops))
        self.assertEqual("a.md", ops[0].path)

    def test_linked_and_equal_is_a_no_op(self):
        ops = Board.reconcile([self.doc("a.md", "doing", "u1")],
                              [self.card("u1", "InProgress")])
        self.assertEqual([], ops)

    def test_status_differing_in_the_file_moves_the_card(self):
        ops = Board.reconcile([self.doc("a.md", "done", "u1")],
                              [self.card("u1", "Todo")])
        self.assertEqual(["set_status"], self.kinds(ops))
        self.assertEqual("done", ops[0].status)

    def test_a_card_nothing_points_at_is_reported_not_deleted(self):
        ops = Board.reconcile([], [self.card("ghost", "Todo")])
        self.assertEqual(["orphan"], self.kinds(ops))

    def test_two_docs_claiming_one_uuid_conflict_and_neither_is_written(self):
        ops = Board.reconcile(
            [self.doc("a.md", "todo", "u1"), self.doc("b.md", "done", "u1")],
            [self.card("u1", "Todo")])
        self.assertEqual(["conflict"], self.kinds(ops))
        self.assertEqual(["a.md", "b.md"], sorted(ops[0].paths))
        self.assertNotIn("set_status", self.kinds(ops))

    def test_a_doc_pointing_at_a_missing_card_is_recreated(self):
        ops = Board.reconcile([self.doc("a.md", "done", "gone")], [])
        self.assertEqual(["create"], self.kinds(ops))


class DirectionTest(unittest.TestCase):
    def doc_at(self, when, status):
        return Board.Doc(path="a.md", kind="pitch", title="T", status=status,
                         uuid="u1", body="", data={}, mtime=at(when))

    def card_at(self, when, status):
        return {"id": "u1", "status": status,
                "updated_at": at(when).strftime("%Y-%m-%dT%H:%M:%SZ")}

    def test_a_newer_card_writes_the_file(self):
        ops = Board.reconcile([self.doc_at(1000, "todo")],
                              [self.card_at(2000, "InProgress")])
        self.assertEqual(["write_file"], [o.kind for o in ops])
        self.assertEqual("doing", ops[0].status)

    def test_a_newer_file_moves_the_card(self):
        ops = Board.reconcile([self.doc_at(2000, "done")], [self.card_at(1000, "Todo")])
        self.assertEqual(["set_status"], [o.kind for o in ops])

    def test_a_tie_prefers_the_file(self):
        ops = Board.reconcile([self.doc_at(1000, "done")], [self.card_at(1000, "Todo")])
        self.assertEqual(["set_status"], [o.kind for o in ops])


class ColumnPlacementTest(unittest.TestCase):
    COLUMNS = [{"id": "c-todo", "name": "TODO", "default_status": "todo"},
               {"id": "c-doing", "name": "Doing", "default_status": "in_progress"},
               {"id": "c-done", "name": "Complete", "default_status": "done"},
               {"id": "c-review", "name": "In Review", "default_status": None}]

    def doc(self, status):
        return Board.Doc(path="a.md", kind="pitch", title="T", status=status,
                         uuid="u1", body="", data={}, mtime=at(9999))

    def card(self, status, column):
        return {"id": "u1", "status": status, "column_id": column,
                "updated_at": "1970-01-01T00:00:00Z"}

    def move(self, ops):
        return next((o for o in ops if o.kind == "move"), None)

    def test_a_card_in_a_column_that_disagrees_is_moved(self):
        ops = Board.reconcile([self.doc("doing")], [self.card("InProgress", "c-todo")],
                              columns=self.COLUMNS)
        self.assertEqual("c-doing", self.move(ops).column_id)

    def test_a_card_already_in_the_right_column_is_left_alone(self):
        ops = Board.reconcile([self.doc("doing")], [self.card("InProgress", "c-doing")],
                              columns=self.COLUMNS)
        self.assertIsNone(self.move(ops))

    # A column with no default_status is a deliberate choice -- "In Review" is
    # somewhere a human parked the card. Dragging it out because its status maps
    # elsewhere would be the tool fighting its user.
    def test_a_card_in_a_column_with_no_default_status_stays_put(self):
        ops = Board.reconcile([self.doc("doing")], [self.card("InProgress", "c-review")],
                              columns=self.COLUMNS)
        self.assertIsNone(self.move(ops))

    def test_no_matching_column_means_no_move(self):
        ops = Board.reconcile([self.doc("blocked")], [self.card("Blocked", "c-todo")],
                              columns=self.COLUMNS)
        self.assertIsNone(self.move(ops))


if __name__ == "__main__":
    unittest.main()
