# frozen_string_literal: true
#
# Runs every test file in one process.
#
# `ruby -Itest test/board/a_test.rb test/board/b_test.rb` does NOT do this:
# ruby loads the first file as the main script and leaves the rest in ARGV, so
# only the first file's tests run and the command looks green while most of the
# suite never executed. Found the honest way, by counting runs.
#
#   ruby test/run.rb

require File.expand_path("../skills/board/sync", __dir__)

Dir[File.expand_path("**/*_test.rb", __dir__)].sort.each { |f| require f }
