#!/usr/bin/env ruby
#
# Everything about this repo that `claude plugin validate` does not look at.
# Runnable by hand: ruby .github/scripts/check-skills.rb
#
# The CLI validates the JSON manifests against its own Zod schema. It never
# parses SKILL.md frontmatter as YAML, never compares `name:` to the directory
# the file sits in, and never reads a fenced code block. Each of those three
# has already shipped a defect here, and each was found by hand.
#
# Ruby rather than Python for one reason: ubuntu-latest ships Ruby 3.2 with
# Psych in the stdlib and does NOT ship PyYAML. The Python version of this file
# costs a `pip install pyyaml` — an extra step and a network round trip — to do
# the same work.
#
# PORTABILITY. This runs on the runner (Ruby 3.2 / Psych 5) and on the author's
# Mac (Ruby 2.6 / Psych 3.1, the system ruby — the same machine whose BSD
# tooling skills/init-project already warns about). Two rules keep it working
# on both, and both were learned by breaking it:
#
#   * `YAML.safe_load(string)` with ONE positional argument and nothing else.
#     `YAML.safe_load_file` does not exist before Psych 3.3, and safe_load's
#     options went positional -> keyword-only in Psych 4. A single positional
#     string is the one call shape that means the same thing in both.
#   * `File.read(path, encoding: "UTF-8")`. Without it a runner with a
#     non-UTF-8 locale raises `invalid byte sequence in US-ASCII` on the first
#     em-dash in a skill.

require "yaml"

Dir.chdir(ARGV[0]) if ARGV[0]

CI = !ENV["GITHUB_ACTIONS"].nil?
$errors = 0

def report(kind, file, line, msg)
  $errors += 1 if kind == "error"
  where = line ? "#{file}:#{line}" : file
  # The annotation form puts the message on the diff itself; the text repeats
  # the location so a local run without GITHUB_ACTIONS is still readable.
  if CI
    puts "::#{kind} file=#{file}#{line ? ",line=#{line}" : ''}::#{where}  #{msg}"
  else
    puts "#{kind == 'error' ? 'ERR ' : 'warn'} #{where}  #{msg}"
  end
end

# A plain `def`, not the 3.0 endless form: this file has to parse under the
# Mac's system Ruby 2.6 as well as the runner's 3.2.
def err(file, line, msg)
  report("error", file, line, msg)
end

skill_files = Dir.glob("skills/*/SKILL.md").sort
abort("no skills/*/SKILL.md found — run this from the repo root") if skill_files.empty?
SKILLS = skill_files.map { |f| File.basename(File.dirname(f)) }

# ---------------------------------------------------------------- frontmatter
#
# The defect this exists for:
#
#     description: Use when checking: formatting, lint rules and types ...
#
# An unquoted YAML scalar cannot contain ": ". Two descriptions shipped like
# this. Nothing complained: the runtime keys a skill by its directory, so it
# loaded anyway, and `claude plugin validate --strict` printed
# "Validation passed". The description is what makes a skill findable, so a
# description that does not parse is a skill that quietly stops being offered.
#
# Anthropic hit the same gap and answered it the same way — claude-plugins-
# official runs .github/scripts/validate-frontmatter.ts, a real YAML parse, as
# a SECOND workflow beside `claude plugin validate`, for exactly this reason.

skill_files.each do |file|
  dir  = File.basename(File.dirname(file))
  text = File.read(file, encoding: "UTF-8")

  unless text.start_with?("---\n")
    err(file, 1, "no YAML frontmatter — the file must open with ---")
    next
  end
  close = text.index("\n---", 3)
  unless close
    err(file, 1, "frontmatter block is never closed by ---")
    next
  end

  begin
    fm = YAML.safe_load(text[4...close])
  rescue StandardError => e
    detail = e.message.gsub(/\s+/, " ").strip
    # Psych counts lines from the start of the block it was handed; +1 puts the
    # number back in the file so the annotation lands on the right line.
    detail = detail.sub(/line (\d+)/) { "line #{Regexp.last_match(1).to_i + 1}" }
    line   = detail[/line (\d+)/, 1]
    err(file, line, "frontmatter is not valid YAML: #{detail}")
    next
  end

  unless fm.is_a?(Hash)
    err(file, 1, "frontmatter is not a mapping")
    next
  end

  # The runtime keys a skill by its DIRECTORY, so a wrong `name:` is invisible
  # from the outside: `claude plugin details` still lists all 14 and still says
  # enabled. Every cross-reference in the docs points at the directory name,
  # which is then a lie about the file it names. Nothing else will flag it.
  name = fm["name"].to_s
  if name.strip.empty?
    err(file, nil, "frontmatter has no `name:`")
  elsif name != dir
    err(file, nil, "name: #{name.inspect} does not match its directory #{dir.inspect}")
  end

  desc = fm["description"].to_s
  if desc.strip.empty?
    err(file, nil, "frontmatter has no `description:` — without one the skill is never offered")
  elsif desc.length > 1024
    err(file, nil, "description is #{desc.length} chars; the limit is 1024")
  end
end

# ------------------------------------------------------------ cross-references
#
# The defect: a reorder left `see the X skill` pointing at a name that no
# longer existed. Deliberately narrow — two shapes, both unambiguous, both
# resolvable against the filesystem with no network:
#
#   hexagram:<name>    the invocation form, as the README writes it
#   `<name>` skill     the prose form, as the skills write it
#
# A general markdown link checker is the version of this that gets deleted: it
# needs the network, it rate-limits, and skills legitimately name paths that do
# not exist yet.

DOCS = (skill_files + Dir.glob("skills/*/*.md") + ["README.md"])
       .uniq.select { |f| File.exist?(f) }.sort

DOCS.each do |file|
  File.read(file, encoding: "UTF-8").each_line.with_index(1) do |line, n|
    line.scan(/hexagram:([a-z][a-z0-9-]*)/) do |m|
      err(file, n, "references hexagram:#{m[0]} — there is no skills/#{m[0]}/") unless SKILLS.include?(m[0])
    end
    line.scan(/`([a-z][a-z0-9-]*)` skill\b/) do |m|
      err(file, n, "references the `#{m[0]}` skill — there is no skills/#{m[0]}/") unless SKILLS.include?(m[0])
    end
  end
end

# -------------------------------------------------------------------- fences
#
# Two rules over the same extracted bash. They catch different things and
# neither subsumes the other.

def bash_fences(file)
  out, open, start, buf = [], false, nil, nil
  File.read(file, encoding: "UTF-8").each_line.with_index(1) do |line, n|
    if open
      if line =~ /^\s*```\s*$/ then out << [start, buf]; open = false
      else buf << [n, line.chomp]
      end
    elsif line =~ /^\s*```(bash|sh|shell|console)\s*$/
      open, start, buf = true, n, []
    end
  end
  out
end

# Strip anything a bracket could legitimately hide inside, so the placeholder
# rule stays exact. Comments first — a comment may contain an unbalanced quote.
def strip_noise(s)
  s.sub(/(^|\s)#.*$/, '\1').gsub(/'[^']*'/, "''").gsub(/"[^"]*"/, '""')
end

# `<` opening a word that starts with a letter, and that is not `<<` (heredoc),
# `<(` (process substitution), `<=`, or a numbered fd like `2<`.
PLACEHOLDER = /(?<![<\d\w])<(?![<(=])\s*[A-Za-z]/

# EVERY markdown a skill ships, not only its SKILL.md. `board/install.md` is the
# reason: it exists to be EXECUTED by Claude on someone else's machine, so a fence
# that does not parse there is worse than one in prose — and until this glob
# widened, no check opened that file at all.
markdown = DOCS

# RULE 1 — the placeholder that reads as a redirect.
#
#     claude plugin install <name>@hexagram --scope user
#
# `bash -n` exits 0 on that line: `<` is a legal input redirection, so it is
# valid syntax. shellcheck exits 0 too, at every severity including -S error.
# It fails only when a reader pastes it, as `name: No such file or directory`.
# A naive grep for <...> is too noisy — skills/naming quotes regexes full of
# angle brackets — so quoted spans and comments come off first. On this repo
# that is the difference between 11 hits with 3 false and 8 hits with 0 false.
markdown.each do |file|
  bash_fences(file).each do |_start, lines|
    lines.each do |n, line|
      next if line.strip.empty?
      next unless strip_noise(line) =~ PLACEHOLDER
      err(file, n, "placeholder <...> in a bash fence: bash reads this as a redirect, not a " \
                   "blank to fill in, and a reader who pastes it gets \"No such file or " \
                   "directory\". Quote it or use $VAR.  #{line.strip}")
    end
  end
end

# RULE 2 — what `bash -n` does catch, and the reason it stays: a fence
# containing `export VAR=<its name>` is a hard syntax error, and shipped.
#
# `bash`, never `sh`. ubuntu's /bin/sh is dash, and dash rejects process
# substitution: `done < <(ls)` is idiomatic bash and a syntax error under dash.
# Naming the wrong shell here turns a correct repo red for no reason.
markdown.each do |file|
  bash_fences(file).each do |start, lines|
    src = lines.map { |_n, l| l }.join("\n")
    next if src.strip.empty?
    # Rule 1 already reported every <placeholder>; neutralise them so one
    # defect is not reported twice under two different explanations.
    src = src.gsub(/<[A-Za-z][A-Za-z0-9 _.\/-]*>/, "PLACEHOLDER")
    IO.popen(["bash", "-n"], "w", err: File::NULL) { |io| io.write(src) }
    err(file, start, "this bash fence has a syntax error (bash -n)") unless $?.success?
  end
end

# --------------------------------------------------------------------- report

if $errors.zero?
  puts "OK  #{skill_files.length} skills, #{markdown.length} markdown files"
  exit 0
end
warn "\n#{$errors} error(s)"
exit 1
