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

class SurgicalWriteTest < Minitest::Test
  ORIGINAL = "---\ntags:\n  - plan\n  - area/clients\nstatus: todo\n---\n\n# Plan\n\nbody\n"

  def test_adding_a_key_touches_exactly_one_line
    out = Board::Frontmatter.set(ORIGINAL, "kanban", "u-1")
    added = out.lines - ORIGINAL.lines
    removed = ORIGINAL.lines - out.lines
    assert_equal ["kanban: u-1\n"], added
    assert_empty removed, "nothing else may be rewritten"
  end

  def test_list_indentation_is_preserved
    out = Board::Frontmatter.set(ORIGINAL, "kanban", "u-1")
    assert_includes out, "tags:\n  - plan\n  - area/clients\n"
  end

  def test_updating_an_existing_key_replaces_only_that_line
    out = Board::Frontmatter.set(ORIGINAL, "status", "done")
    assert_includes out, "status: done\n"
    refute_includes out, "status: todo\n"
    assert_includes out, "  - area/clients\n"
  end

  def test_comments_in_frontmatter_survive
    text = "---\n# why this is here\nstatus: todo\n---\n\nbody\n"
    out = Board::Frontmatter.set(text, "kanban", "u-1")
    assert_includes out, "# why this is here\n"
  end

  def test_a_bare_file_gets_a_block_and_keeps_its_body
    text = "# Just a plan\n\nbody\n"
    out = Board::Frontmatter.set(text, "kanban", "u-1")
    assert_equal "---\nkanban: u-1\n---\n" + text, out
  end
end
