# frozen_string_literal: true

require "minitest/autorun"
require "tmpdir"
require_relative "../../skills/board/sync"

class WriteBackTest < Minitest::Test
  def test_inserts_a_block_into_a_bare_file_and_keeps_the_body
    Dir.mktmpdir do |dir|
      path = File.join(dir, "slice-01-a.md")
      body = "# Slice 01 - A\n\n## Done when\n\n`rake test` is green\n"
      File.write(path, body)
      doc = Board::Doc.from(path: path, text: body, kind: :slice)

      Board.write_back(doc, "status" => "doing", "kanban" => "u1")

      data, out_body = Board::Frontmatter.parse(File.read(path, encoding: "UTF-8"))
      assert_equal({ "status" => "doing", "kanban" => "u1" }, data)
      assert_equal body, out_body
    end
  end

  def test_preserves_existing_key_order
    Dir.mktmpdir do |dir|
      path = File.join(dir, "p.md")
      text = "---\ntags:\n  - pitch\nstatus: active\nkanban: u1\n---\n\n# P\n"
      File.write(path, text)
      doc = Board::Doc.from(path: path, text: text, kind: :pitch)

      Board.write_back(doc, "status" => "done")

      assert_equal %w[tags status kanban],
                   Board::Frontmatter.parse(File.read(path, encoding: "UTF-8")).first.keys
    end
  end
end
