#!/usr/bin/env ruby
# frozen_string_literal: true
#
# Projects hexagram pitches and plan slices onto a kanban-rs board.
#
# The markdown is the source of truth. The board is a derived view, and the one
# field that travels back is `status:`, so that moving a card produces a diff
# you can review instead of state stranded in a JSON file.
#
# PORTABILITY, the same two rules as .github/scripts/check-skills.rb, for the
# same reasons, both learned by breaking it:
#
#   * YAML.safe_load(string) with ONE positional argument. safe_load_file does
#     not exist before Psych 3.3, and safe_load's options went positional ->
#     keyword-only in Psych 4. A single positional string is the one call shape
#     that means the same thing on Psych 3.1 and on Psych 5.
#   * File.read(path, encoding: "UTF-8"). Without it a runner with a different
#     default external encoding reads the file as ASCII-8BIT and every match
#     fails.
#
# This file must also PARSE on Ruby 2.6, which rules out endless methods
# (`def foo(x) = ...`), rightward assignment, hash shorthand `{x:}` and
# Data.define. That list exists because the first draft used the first one.

require "yaml"
require "json"

module Board
  module Frontmatter
    FENCE = /\A---\r?\n(.*?)\r?\n---\r?\n?/m.freeze

    # -> [Hash, String]. A file with no block yields [{}, whole_text].
    def self.parse(text)
      m = FENCE.match(text)
      return [{}, text] unless m

      [YAML.safe_load(m[1]) || {}, m.post_match]
    end

    # Key order is whatever the caller put in the Hash.
    def self.render(data, body)
      return body if data.empty?

      "---\n" + YAML.dump(data).sub(/\A---\r?\n/, "") + "---\n" + body
    end
  end

  Doc = Struct.new(:path, :kind, :title, :status, :uuid, :body, :data, keyword_init: true) do
    def self.from(path:, text:, kind:)
      data, body = Frontmatter.parse(text)
      heading = body[/^\#\s+(.+)$/, 1]
      new(path: path, kind: kind, body: body, data: data,
          title: heading || File.basename(path, ".md"),
          status: data["status"], uuid: data["kanban"])
    end
  end

  def self.scan_pitches(root)
    Dir.glob(File.join(root, "pitches", "*.md")).sort.map do |path|
      Doc.from(path: path, text: File.read(path, encoding: "UTF-8"), kind: :pitch)
    end
  end
  STATUS_TO_KANBAN = {
    "todo" => "todo", "doing" => "in_progress",
    "blocked" => "blocked", "done" => "done",
    "active" => "in_progress" # the vocabulary pitches already use
  }.freeze

  class Kanban
    class Missing < StandardError; end
    class Failed < StandardError; end

    def initialize(file)
      @file = file
    end

    # Every call goes through here, so there is one place that parses the
    # {success, api_version, data} envelope and one place that raises.
    def run(*args)
      out = IO.popen(["kanban", @file, *args], err: File::NULL, &:read)
      raise Failed, "kanban #{args.join(' ')} failed" unless $?.success?

      payload = JSON.parse(out)
      raise Failed, payload["error"].to_s unless payload["success"]

      payload["data"]
    rescue Errno::ENOENT
      raise Missing, "kanban is not on PATH"
    end

    # `card create` has no --status flag on the shipped 0.9.0 CLI, so status is
    # a second call. Verified against the binary, not read from the README --
    # the upstream README disagrees with the binary in two other places.
    def create_card(board:, column:, title:, status:, description:)
      id = run("card", "create", "--board", board, "--column", column,
               "--title", title, "--description", description).fetch("id")
      run("card", "update", id, "--status", status)
      id
    end
  end
  def self.sync(docs_root:, board_file:, board_name:)
    api = Kanban.new(board_file)
    scan_pitches(docs_root).each do |doc|
      next if doc.uuid # already linked; slice 02 handles the rest

      uuid = api.create_card(
        board: board_name, column: "TODO", title: doc.title,
        status: STATUS_TO_KANBAN.fetch(doc.status, "todo"),
        description: doc.path
      )
      write_back(doc, "kanban" => uuid)
    end
  end

  # Rewrites one file's frontmatter, preserving key order and body.
  def self.write_back(doc, updates)
    data = doc.data.merge(updates)
    File.write(doc.path, Frontmatter.render(data, doc.body))
  end
end
