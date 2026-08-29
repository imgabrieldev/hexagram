# frozen_string_literal: true

require "minitest/autorun"
require_relative "../../skills/board/sync"

class ReconcileTest < Minitest::Test
  def doc(path:, status:, uuid: nil)
    Board::Doc.new(path: path, kind: :pitch, title: "T", status: status,
                   uuid: uuid, body: "", data: {})
  end

  # `card list` returns TitleCase ("InProgress"), which is NOT what `card get`
  # or the REST API return. The fake uses the list shape on purpose: an earlier
  # fake used "in_progress" here, the unit test passed, and the real sync
  # reported "2 updated" on every run forever.
  def card(id:, status:)
    { "id" => id, "status" => status, "title" => "T" }
  end

  def test_unlinked_doc_creates
    ops = Board.reconcile(docs: [doc(path: "a.md", status: "todo")], cards: [])
    assert_equal [:create], ops.map(&:kind)
    assert_equal "a.md", ops.first.path
  end

  def test_linked_and_equal_is_a_no_op
    ops = Board.reconcile(docs: [doc(path: "a.md", status: "doing", uuid: "u1")],
                          cards: [card(id: "u1", status: "InProgress")])
    assert_empty ops
  end

  def test_status_differing_in_the_file_moves_the_card
    ops = Board.reconcile(docs: [doc(path: "a.md", status: "done", uuid: "u1")],
                          cards: [card(id: "u1", status: "Todo")])
    assert_equal [:set_status], ops.map(&:kind)
    assert_equal "u1", ops.first.uuid
    assert_equal "done", ops.first.status
  end

  def test_a_card_nothing_points_at_is_reported_not_deleted
    ops = Board.reconcile(docs: [], cards: [card(id: "ghost", status: "Todo")])
    assert_equal [:orphan], ops.map(&:kind)
  end

  def test_two_docs_claiming_one_uuid_conflict_and_neither_is_written
    ops = Board.reconcile(
      docs: [doc(path: "a.md", status: "todo", uuid: "u1"),
             doc(path: "b.md", status: "done", uuid: "u1")],
      cards: [card(id: "u1", status: "Todo")]
    )
    assert_equal [:conflict], ops.map(&:kind)
    assert_equal %w[a.md b.md], ops.first.paths.sort
    refute_includes ops.map(&:kind), :set_status
  end

  def test_a_doc_pointing_at_a_missing_card_is_recreated
    ops = Board.reconcile(docs: [doc(path: "a.md", status: "done", uuid: "gone")], cards: [])
    assert_equal [:create], ops.map(&:kind)
    assert_equal "a.md", ops.first.path
  end
end

class LinkTest < Minitest::Test
  def slice(uuid:)
    Board::Doc.new(path: "s.md", kind: :slice, title: "S", status: "todo",
                   uuid: uuid, body: "", data: {}, parent_path: "p.md")
  end

  # Both cards are in the fake on purpose. An edge needs two live cards, and an
  # earlier fake that listed only the child described a state that cannot exist
  # -- it passed while the real sync crashed rebuilding a wiped board.
  def test_links_a_child_to_its_parent_when_the_edge_is_missing
    ops = Board.reconcile(
      docs: [slice(uuid: "child")],
      cards: [{ "id" => "child", "status" => "Todo" },
              { "id" => "parent", "status" => "Todo" }],
      parents: { "s.md" => "parent" }, edges: []
    )
    link = ops.find { |o| o.kind == :link }
    refute_nil link
    assert_equal "parent", link.parent_uuid
    assert_equal "child", link.uuid
  end

  def test_a_child_whose_parent_card_is_gone_is_not_linked
    ops = Board.reconcile(
      docs: [slice(uuid: "child")],
      cards: [{ "id" => "child", "status" => "Todo" }],
      parents: { "s.md" => "vanished" }, edges: []
    )
    assert_nil ops.find { |o| o.kind == :link }
  end

  def test_does_not_relink_an_edge_that_already_exists
    ops = Board.reconcile(
      docs: [slice(uuid: "child")],
      cards: [{ "id" => "child", "status" => "Todo" },
              { "id" => "parent", "status" => "Todo" }],
      parents: { "s.md" => "parent" }, edges: [%w[parent child]]
    )
    assert_nil ops.find { |o| o.kind == :link }
  end
end

class DirectionTest < Minitest::Test
  def doc_at(time, status)
    Board::Doc.new(path: "a.md", kind: :pitch, title: "T", status: status,
                   uuid: "u1", body: "", data: {}, mtime: time)
  end

  def card_at(time, status)
    { "id" => "u1", "status" => status, "updated_at" => time.utc.iso8601 }
  end

  def test_a_newer_card_writes_the_file
    ops = Board.reconcile(docs: [doc_at(Time.at(1000), "todo")],
                          cards: [card_at(Time.at(2000), "InProgress")])
    assert_equal [:write_file], ops.map(&:kind)
    assert_equal "doing", ops.first.status
  end

  def test_a_newer_file_moves_the_card
    ops = Board.reconcile(docs: [doc_at(Time.at(2000), "done")],
                          cards: [card_at(Time.at(1000), "Todo")])
    assert_equal [:set_status], ops.map(&:kind)
  end

  def test_a_tie_prefers_the_file
    ops = Board.reconcile(docs: [doc_at(Time.at(1000), "done")],
                          cards: [card_at(Time.at(1000), "Todo")])
    assert_equal [:set_status], ops.map(&:kind)
  end
end

class ColumnPlacementTest < Minitest::Test
  COLUMNS = [{ "id" => "c-todo", "name" => "TODO", "default_status" => "todo" },
             { "id" => "c-doing", "name" => "Doing", "default_status" => "in_progress" },
             { "id" => "c-done", "name" => "Complete", "default_status" => "done" },
             { "id" => "c-review", "name" => "In Review", "default_status" => nil }].freeze

  def doc(status)
    Board::Doc.new(path: "a.md", kind: :pitch, title: "T", status: status,
                   uuid: "u1", body: "", data: {}, mtime: Time.at(9999))
  end

  def card(status, column)
    { "id" => "u1", "status" => status, "column_id" => column,
      "updated_at" => "1970-01-01T00:00:00Z" }
  end

  def test_a_card_in_a_column_that_disagrees_is_moved
    ops = Board.reconcile(docs: [doc("doing")], cards: [card("InProgress", "c-todo")],
                          columns: COLUMNS)
    move = ops.find { |o| o.kind == :move }
    refute_nil move
    assert_equal "c-doing", move.column_id
  end

  def test_a_card_already_in_the_right_column_is_left_alone
    ops = Board.reconcile(docs: [doc("doing")], cards: [card("InProgress", "c-doing")],
                          columns: COLUMNS)
    assert_nil ops.find { |o| o.kind == :move }
  end

  # A column with no default_status is a deliberate choice -- "In Review" is
  # somewhere a human parked the card. Dragging it out because its status maps
  # elsewhere would be the tool fighting its user.
  def test_a_card_in_a_column_with_no_default_status_stays_put
    ops = Board.reconcile(docs: [doc("doing")], cards: [card("InProgress", "c-review")],
                          columns: COLUMNS)
    assert_nil ops.find { |o| o.kind == :move }
  end

  def test_no_matching_column_means_no_move
    ops = Board.reconcile(docs: [doc("blocked")], cards: [card("Blocked", "c-todo")],
                          columns: COLUMNS)
    assert_nil ops.find { |o| o.kind == :move }
  end
end
