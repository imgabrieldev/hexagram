# frozen_string_literal: true

require "minitest/autorun"
require_relative "../../skills/board/sync"

class FrontmatterTest < Minitest::Test
  WITH = "---\ntags:\n  - pitch\nstatus: active\n---\n\n# Title\n\nbody --- with dashes\n"

  def test_parses_a_block
    data, body = Board::Frontmatter.parse(WITH)
    assert_equal({ "tags" => ["pitch"], "status" => "active" }, data)
    assert body.start_with?("\n# Title")
  end

  def test_no_frontmatter_returns_empty_hash_and_whole_text
    text = "# Just a slice\n\n## Done when\n\n`rake test` is green\n"
    data, body = Board::Frontmatter.parse(text)
    assert_equal({}, data)
    assert_equal text, body
  end

  def test_round_trip_is_identity
    data, body = Board::Frontmatter.parse(WITH)
    again_data, again_body = Board::Frontmatter.parse(Board::Frontmatter.render(data, body))
    assert_equal data, again_data
    assert_equal body, again_body
  end

  def test_render_onto_a_bare_file_keeps_the_body
    text = "# Just a slice\n\nprose\n"
    out = Board::Frontmatter.render({ "status" => "todo", "kanban" => "u-1" }, text)
    data, body = Board::Frontmatter.parse(out)
    assert_equal({ "status" => "todo", "kanban" => "u-1" }, data)
    assert_equal text, body
  end
end

class DocTest < Minitest::Test
  def test_title_comes_from_the_first_heading
    doc = Board::Doc.from(path: "docs/pitches/board.md",
                          text: "---\nstatus: active\n---\n\n# Pitch — Board\n\nbody\n",
                          kind: :pitch)
    assert_equal "Pitch — Board", doc.title
    assert_equal "active", doc.status
    assert_nil doc.uuid
  end

  def test_title_falls_back_to_the_filename_stem
    doc = Board::Doc.from(path: "docs/pitches/no-heading.md", text: "just prose\n", kind: :pitch)
    assert_equal "no-heading", doc.title
  end
end
