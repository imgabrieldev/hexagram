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
require "time"

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

  Doc = Struct.new(:path, :kind, :title, :status, :uuid, :body, :data, :parent_path, :mtime,
                   keyword_init: true) do
    def self.from(path:, text:, kind:, parent_path: nil, mtime: nil)
      data, body = Frontmatter.parse(text)
      heading = body[/^\#\s+(.+)$/, 1]
      new(path: path, kind: kind, body: body, data: data, parent_path: parent_path, mtime: mtime,
          title: heading || File.basename(path, ".md"),
          status: data["status"] || (kind == :slice ? "todo" : nil),
          uuid: data["kanban"])
    end
  end

  # The glob is slice-*.md, which is what excludes README.md. The plain
  # lexicographic sort is what puts slice-01b between 01 and 02.1 -- do NOT
  # "fix" it with a numeric parse: fractional names are deliberate, and
  # normalising them throws away the record of what actually happened.
  def self.scan_slices(root)
    Dir.glob(File.join(root, "plans", "*", "slice-*.md")).sort.map do |path|
      feature = File.basename(File.dirname(path))
      pitch = File.join(root, "pitches", "#{feature}.md")
      Doc.from(path: path, text: File.read(path, encoding: "UTF-8"), kind: :slice,
               parent_path: (File.exist?(pitch) ? pitch : nil), mtime: File.mtime(path))
    end
  end

  # What an agent needs in order to act without opening the file first.
  def self.description_for(doc)
    done = doc.body[/^\#\#\s+Done when\s*\n+(.+?)(?=\n\#\#\s|\z)/m, 1].to_s.strip
    done.empty? ? doc.path : "#{doc.path}\n\nDone when: #{done}"
  end

  def self.scan_pitches(root)
    Dir.glob(File.join(root, "pitches", "*.md")).sort.map do |path|
      Doc.from(path: path, text: File.read(path, encoding: "UTF-8"), kind: :pitch,
               mtime: File.mtime(path))
    end
  end
  KANBAN_TO_STATUS = { "todo" => "todo", "in_progress" => "doing",
                       "blocked" => "blocked", "done" => "done" }.freeze

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

  # A pass that creates cards cannot also link them: the parent's uuid does not
  # exist until its card does. So a first pass that created anything is followed
  # by a second, which sees the uuids the first one wrote. Converges in two, and
  # the second pass is a no-op whenever the first created nothing.
  # --card-prefix goes in the `board create` call and NOWHERE else. Calling
  # `board update --card-prefix` on a board that already holds cards resets the
  # card-number sequence and produces duplicate identifiers -- an upstream
  # defect, reproduced and isolated to exactly that one operation. Creating the
  # board with its prefix means the trigger is never reached. This comment
  # stays: the next person to touch it will not have read the research.
  def self.init(board_file:, board_name:, prefix:)
    api = Kanban.new(board_file)
    api.run("init") unless File.exist?(board_file)
    api.run("board", "create", "--name", board_name,
            "--card-prefix", prefix, "--with-default-columns")
  end

  def self.sync(docs_root:, board_file:, board_name:)
    first = pass(docs_root: docs_root, board_file: board_file, board_name: board_name)
    return first if first.created.zero?

    second = pass(docs_root: docs_root, board_file: board_file, board_name: board_name)
    Report.new(
      created: first.created + second.created,
      updated: first.updated + second.updated,
      linked: first.linked + second.linked,
      written: first.written + second.written,
      orphans: second.orphans,
      conflicts: (first.conflicts + second.conflicts).uniq
    )
  end

  def self.pass(docs_root:, board_file:, board_name:)
    api = Kanban.new(board_file)
    docs = scan_pitches(docs_root) + scan_slices(docs_root)
    cards = api.run("card", "list", "--board", board_name).fetch("items")
    report = Report.new(created: 0, updated: 0, linked: 0, written: 0,
                        orphans: [], conflicts: [])

    by_path = docs.each_with_object({}) { |d, h| h[d.path] = d.uuid }
    parents = docs.each_with_object({}) do |d, h|
      h[d.path] = by_path[d.parent_path] if d.parent_path
    end
    # Only ask about parents whose card actually exists. A file can point at a
    # uuid that is gone -- the board was deleted, or rebuilt elsewhere -- and
    # `relation children` on a missing card is an error, not an empty list. Left
    # unguarded it aborts the whole sync before reconcile can re-create anything,
    # which is exactly the case reconcile exists to handle.
    live = cards.map { |c| c["id"] }
    edges = docs.select { |d| d.kind == :pitch && live.include?(d.uuid) }.flat_map do |pitch|
      api.run("relation", "children", pitch.uuid).map { |c| [pitch.uuid, c["id"]] }
    end

    reconcile(docs: docs, cards: cards, parents: parents, edges: edges).each do |op|
      case op.kind
      when :create
        uuid = api.create_card(
          board: board_name, column: "TODO", title: op.doc.title,
          status: STATUS_TO_KANBAN.fetch(op.doc.status, "todo"),
          description: description_for(op.doc)
        )
        write_back(op.doc, "kanban" => uuid)
        report.created += 1
      when :set_status
        api.run("card", "update", op.uuid, "--status",
                STATUS_TO_KANBAN.fetch(op.status, "todo"))
        report.updated += 1
      when :write_file
        write_back(op.doc, "status" => op.status)
        report.written += 1
      when :link
        # relation add takes POSITIONAL <PARENT> <CHILDREN>... The upstream
        # README documents --parent/--child; those flags do not exist.
        api.run("relation", "add", op.parent_uuid, op.uuid)
        report.linked += 1
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

  # One place that knows kanban writes its statuses two ways: `card list`
  # returns TitleCase with no separator ("InProgress") while `card get` and the
  # REST API return snake_case ("in_progress"). Downcasing alone is not enough
  # -- "inprogress" != "in_progress" -- and getting it wrong made every linked
  # card look changed on every run. Strip the separator, then look it up.
  CANONICAL_STATUS = { "todo" => "todo", "inprogress" => "in_progress",
                       "blocked" => "blocked", "done" => "done" }.freeze

  def self.canonical_status(raw)
    CANONICAL_STATUS.fetch(raw.to_s.downcase.delete("_"), "todo")
  end

  def self.same_status?(one, other)
    canonical_status(one) == canonical_status(other)
  end

  Op = Struct.new(:kind, :path, :paths, :uuid, :parent_uuid, :status, :doc,
                  keyword_init: true)

  # Pure: (docs, cards) -> [Op]. No IO, no process, no clock.
  def self.reconcile(docs:, cards:, parents: {}, edges: [])
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

      card_time = begin
        Time.iso8601(card["updated_at"].to_s)
      rescue ArgumentError, TypeError
        Time.at(0) # an unparseable timestamp must not silently beat the file
      end

      # The tie goes to the file, deliberately: markdown is the source of truth,
      # so when the evidence is ambiguous the tool yields. A write_file op also
      # changes the mtime, which is what stops the next run flapping back.
      if d.mtime && card_time > d.mtime
        ops << Op.new(kind: :write_file, uuid: d.uuid, path: d.path, doc: d,
                      status: KANBAN_TO_STATUS.fetch(canonical_status(card["status"]), "todo"))
      else
        ops << Op.new(kind: :set_status, uuid: d.uuid, status: d.status, path: d.path, doc: d)
      end
    end

    # BOTH cards have to exist before an edge between them can. After a board is
    # wiped, every file still carries its old uuid, so without these two guards
    # this emits a link between two cards that are about to be re-created and
    # kanban rejects it. The re-created pair links on the second pass, which is
    # what the two-pass sync is for.
    docs.each do |d|
      next unless d.kind == :slice && d.uuid
      next unless by_id.key?(d.uuid)

      parent_uuid = parents[d.path]
      next if parent_uuid.nil? || !by_id.key?(parent_uuid)
      next if edges.include?([parent_uuid, d.uuid])

      ops << Op.new(kind: :link, uuid: d.uuid, parent_uuid: parent_uuid, path: d.path)
    end

    linked = docs.map(&:uuid).compact
    cards.reject { |c| linked.include?(c["id"]) }
         .each { |c| ops << Op.new(kind: :orphan, uuid: c["id"]) }

    ops
  end
end

if $PROGRAM_NAME == __FILE__
  args = ARGV.dup
  do_init = args.delete("--init")
  docs_root, board_file, board_name, prefix = args

  abort "usage: sync.rb [--init] <docs-root> <board-file> <board-name> [prefix]" unless board_name
  abort "--init needs a prefix" if do_init && (prefix.nil? || prefix.empty?)

  begin
    Board.init(board_file: board_file, board_name: board_name, prefix: prefix) if do_init
    r = Board.sync(docs_root: docs_root, board_file: board_file, board_name: board_name)
    puts "#{r.created} created, #{r.updated} updated, #{r.written} written, #{r.linked} linked"
    r.orphans.each   { |u| warn "orphan card (not deleted): #{u}" }
    r.conflicts.each { |ps| warn "conflict: #{ps.join(' and ')} claim the same card" }
    exit(r.conflicts.empty? ? 0 : 1)
  rescue Board::Kanban::Missing
    warn "kanban is not on PATH. Install it with: cargo install kanban-cli"
    exit 127
  rescue Board::Kanban::Failed => e
    warn "kanban rejected a command: #{e.message}"
    exit 1
  end
end
