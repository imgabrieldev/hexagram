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
  Report = Struct.new(:created, :updated, :linked, :written, :orphans, :conflicts,
                      keyword_init: true)

  def self.sync(docs_root:, board_file:, board_name:)
    api = Kanban.new(board_file)
    docs = scan_pitches(docs_root)
    cards = api.run("card", "list", "--board", board_name).fetch("items")
    report = Report.new(created: 0, updated: 0, linked: 0, written: 0,
                        orphans: [], conflicts: [])

    reconcile(docs: docs, cards: cards).each do |op|
      case op.kind
      when :create
        uuid = api.create_card(
          board: board_name, column: "TODO", title: op.doc.title,
          status: STATUS_TO_KANBAN.fetch(op.doc.status, "todo"), description: op.doc.path
        )
        write_back(op.doc, "kanban" => uuid)
        report.created += 1
      when :set_status
        api.run("card", "update", op.uuid, "--status",
                STATUS_TO_KANBAN.fetch(op.status, "todo"))
        report.updated += 1
      when :orphan   then report.orphans << op.uuid
      when :conflict then report.conflicts << op.paths
      end
    end

    report
  end

  # Rewrites one file's frontmatter, preserving key order and body.
  def self.write_back(doc, updates)
    data = doc.data.merge(updates)
    File.write(doc.path, Frontmatter.render(data, doc.body))
  end

  # `card list` returns TitleCase with no separator ("InProgress"); `card get`
  # and the REST API return snake_case ("in_progress"). Downcasing alone is not
  # enough -- "inprogress" != "in_progress" -- and getting that wrong makes
  # every linked card look changed on every run. The underscore has to go too.
  def self.same_status?(from_card, want)
    from_card.to_s.downcase.delete("_") == want.to_s.downcase.delete("_")
  end

  Op = Struct.new(:kind, :path, :paths, :uuid, :status, :doc, keyword_init: true)

  # Pure: (docs, cards) -> [Op]. No IO, no process, no clock.
  def self.reconcile(docs:, cards:)
    by_id = cards.each_with_object({}) { |c, h| h[c["id"]] = c }
    claimed = Hash.new { |h, k| h[k] = [] }
    docs.each { |d| claimed[d.uuid] << d.path if d.uuid }

    ops = []
    seen = {}

    docs.each do |d|
      if d.uuid.nil?
        ops << Op.new(kind: :create, path: d.path, doc: d)
        next
      end

      if claimed[d.uuid].length > 1
        ops << Op.new(kind: :conflict, uuid: d.uuid, paths: claimed[d.uuid]) unless seen[d.uuid]
        seen[d.uuid] = true
        next
      end

      card = by_id[d.uuid]
      if card.nil?
        # The file points at a card that no longer exists -- the board was
        # deleted, or rebuilt elsewhere. Re-create and overwrite the link. This
        # is what makes "delete .kanban.json and re-sync" reproduce the board,
        # which is the whole justification for gitignoring it.
        ops << Op.new(kind: :create, path: d.path, doc: d)
        next
      end

      want = STATUS_TO_KANBAN.fetch(d.status, "todo")
      next if same_status?(card["status"], want)

      ops << Op.new(kind: :set_status, uuid: d.uuid, status: d.status, path: d.path, doc: d)
    end

    linked = docs.map(&:uuid).compact
    cards.reject { |c| linked.include?(c["id"]) }
         .each { |c| ops << Op.new(kind: :orphan, uuid: c["id"]) }

    ops
  end
end

if $PROGRAM_NAME == __FILE__
  docs_root, board_file, board_name = ARGV
  abort "usage: sync.rb <docs-root> <board-file> <board-name>" unless board_name

  begin
    r = Board.sync(docs_root: docs_root, board_file: board_file, board_name: board_name)
    puts "#{r.created} created, #{r.updated} updated"
    r.orphans.each   { |u| warn "orphan card (not deleted): #{u}" }
    r.conflicts.each { |ps| warn "conflict: #{ps.join(' and ')} claim the same card" }
    exit(r.conflicts.empty? ? 0 : 1)
  rescue Board::Kanban::Missing
    warn "kanban is not on PATH. Install it with: cargo install kanban-cli"
    exit 127
  end
end
