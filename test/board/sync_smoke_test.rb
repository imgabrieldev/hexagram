# frozen_string_literal: true

require "minitest/autorun"
require "tmpdir"
require "fileutils"
require "json"
require_relative "../../skills/board/sync"

class SyncSmokeTest < Minitest::Test
  def test_a_pitch_becomes_a_card_and_gets_its_uuid_back
    skip "kanban not on PATH" unless system("command -v kanban > /dev/null 2>&1")

    Dir.mktmpdir do |dir|
      docs = File.join(dir, "docs")
      FileUtils.mkdir_p(File.join(docs, "pitches"))
      pitch = File.join(docs, "pitches", "thing.md")
      File.write(pitch, "---\nstatus: active\n---\n\n# Pitch — Thing\n\nbody\n")

      board = File.join(dir, ".kanban.json")
      system("kanban", board, "init", out: File::NULL, err: File::NULL)
      system("kanban", board, "board", "create", "--name", "Work",
             "--card-prefix", "HEX", "--with-default-columns", out: File::NULL, err: File::NULL)

      Board.sync(docs_root: docs, board_file: board, board_name: "Work")

      data, = Board::Frontmatter.parse(File.read(pitch, encoding: "UTF-8"))
      refute_nil data["kanban"], "the pitch should carry its card uuid"

      cards = JSON.parse(`kanban #{board} card list --board Work`)["data"]["items"]
      assert_equal 1, cards.length
      assert_equal "Pitch — Thing", cards.first["title"]
      assert_equal data["kanban"], cards.first["id"]
    end
  end
end
