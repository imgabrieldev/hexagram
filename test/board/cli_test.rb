# frozen_string_literal: true

require "minitest/autorun"
require "tmpdir"
require "digest"
require "fileutils"
require "json"
require "rbconfig"
require_relative "../../skills/board/sync"

class CliTest < Minitest::Test
  SYNC = File.expand_path("../../skills/board/sync.rb", __dir__)

  def tree_digest(dir)
    Dir.glob(File.join(dir, "**", "*")).sort.map do |f|
      File.file?(f) ? Digest::SHA256.file(f).hexdigest : f
    end.join
  end

  def test_missing_binary_exits_127_and_touches_nothing
    Dir.mktmpdir do |dir|
      docs = File.join(dir, "docs")
      FileUtils.mkdir_p(File.join(docs, "pitches"))
      File.write(File.join(docs, "pitches", "a.md"), "---\nstatus: active\n---\n\n# A\n")

      before = tree_digest(dir)
      # NOT PATH="/nonexistent": the macOS system ruby shells out to `uname` at
      # boot, so an empty PATH kills the interpreter before sync.rb runs and the
      # test passes for the wrong reason. /usr/bin:/bin has ruby and not kanban.
      out = IO.popen({ "PATH" => "/usr/bin:/bin" },
                     [RbConfig.ruby, SYNC, docs, File.join(dir, ".kanban.json"), "Work"],
                     err: [:child, :out], &:read)
      status = $?.exitstatus

      assert_equal 127, status
      assert_match(/cargo install kanban-cli/, out)
      assert_equal before, tree_digest(dir), "a failed run must not modify the docs tree"
    end
  end
  def test_init_sets_the_prefix_atomically_and_numbering_stays_clean
    skip "kanban not on PATH" unless system("command -v kanban > /dev/null 2>&1")

    Dir.mktmpdir do |dir|
      board = File.join(dir, ".kanban.json")
      Board.init(board_file: board, board_name: "Work", prefix: "HEX")
      3.times do |i|
        system("kanban", board, "card", "create", "--board", "Work",
               "--column", "TODO", "--title", "c#{i}", out: File::NULL, err: File::NULL)
      end
      nums = JSON.parse(`kanban #{board} card list --board Work`)["data"]["items"]
                 .map { |c| c["card_number"] }
      assert_equal [1, 2, 3], nums.sort
      assert_equal nums.uniq.length, nums.length,
                   "duplicate card_number means the prefix trigger was hit"
    end
  end

  # The sync is immune to the upstream numbering defect only because it never
  # addresses a card by PREFIX-N. This is that claim, as a test.
  def test_reconcile_is_correct_even_on_a_board_with_duplicate_numbers
    docs = [Board::Doc.new(path: "a.md", kind: :pitch, title: "A", status: "done",
                           uuid: "u-a", body: "", data: {}, mtime: Time.at(9999))]
    cards = [{ "id" => "u-a", "status" => "Todo", "card_number" => 1,
               "updated_at" => "1970-01-01T00:00:00Z" },
             { "id" => "u-b", "status" => "Todo", "card_number" => 1,
               "updated_at" => "1970-01-01T00:00:00Z" }]

    ops = Board.reconcile(docs: docs, cards: cards)

    assert_equal "u-a", ops.find { |o| o.kind == :set_status }.uuid
    assert_equal ["u-b"], ops.select { |o| o.kind == :orphan }.map(&:uuid)
  end
end
