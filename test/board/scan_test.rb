# frozen_string_literal: true

require "minitest/autorun"
require "tmpdir"
require "fileutils"
require_relative "../../skills/board/sync"

class ScanTest < Minitest::Test
  def with_tree
    Dir.mktmpdir do |dir|
      docs = File.join(dir, "docs")
      FileUtils.mkdir_p(File.join(docs, "pitches"))
      FileUtils.mkdir_p(File.join(docs, "plans", "board"))
      File.write(File.join(docs, "pitches", "board.md"),
                 "---\nstatus: active\n---\n\n# Pitch — Board\n")
      File.write(File.join(docs, "plans", "board", "README.md"), "# Plan\n")
      File.write(File.join(docs, "plans", "board", "slice-01-a.md"),
                 "# Slice 01 — A\n\n## Done when\n\n`rake test` is green\n")
      File.write(File.join(docs, "plans", "board", "slice-01b-b.md"), "# Slice 01b — B\n")
      File.write(File.join(docs, "plans", "board", "slice-02.1-c.md"), "# Slice 02.1 — C\n")
      yield docs
    end
  end

  def test_bare_slice_defaults_to_todo
    with_tree do |docs|
      s = Board.scan_slices(docs).find { |d| d.path.end_with?("slice-01-a.md") }
      assert_equal "todo", s.status
      assert_nil s.uuid
      assert_equal "Slice 01 — A", s.title
    end
  end

  def test_readme_is_not_a_slice
    with_tree { |docs| refute(Board.scan_slices(docs).any? { |d| d.path.end_with?("README.md") }) }
  end

  def test_fractional_names_are_scanned_and_sorted
    with_tree do |docs|
      names = Board.scan_slices(docs).map { |d| File.basename(d.path) }
      assert_equal %w[slice-01-a.md slice-01b-b.md slice-02.1-c.md], names
    end
  end

  def test_parent_resolves_to_the_pitch_of_the_same_name
    with_tree do |docs|
      s = Board.scan_slices(docs).first
      assert_equal File.join(docs, "pitches", "board.md"), s.parent_path
    end
  end

  def test_done_when_becomes_part_of_the_description
    with_tree do |docs|
      s = Board.scan_slices(docs).find { |d| d.path.end_with?("slice-01-a.md") }
      assert_includes Board.description_for(s), "`rake test` is green"
      assert_includes Board.description_for(s), "slice-01-a.md"
    end
  end
end

class PitchScanTest < Minitest::Test
  def test_readme_is_not_a_pitch
    Dir.mktmpdir do |dir|
      docs = File.join(dir, "docs")
      FileUtils.mkdir_p(File.join(docs, "pitches", "archive"))
      File.write(File.join(docs, "pitches", "README.md"), "# Pitches\n\nWhat this folder is for.\n")
      File.write(File.join(docs, "pitches", "real.md"), "---\nstatus: active\n---\n\n# Real\n")
      File.write(File.join(docs, "pitches", "archive", "old.md"), "---\nstatus: done\n---\n\n# Old\n")

      names = Board.scan_pitches(docs).map { |d| File.basename(d.path) }

      assert_equal ["real.md"], names
    end
  end
end
