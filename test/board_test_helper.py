"""Puts skills/board on the import path so tests can `from board_test_helper import Board`."""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_BOARD = os.path.join(os.path.dirname(_HERE), "skills", "board")
_SYNC = os.path.join(_BOARD, "sync.py")
_SHOW = os.path.join(_BOARD, "show.py")
_WEB = os.path.join(_BOARD, "web.py")
_MARKDOWN = os.path.join(_BOARD, "markdown.py")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


Board = _load("board_sync", _SYNC)
Show = _load("board_show", _SHOW)
# The renderer's own path, so a test can read its source and assert it stays
# read-only. `__file__` is unreliable for a module loaded this way.
Show.SOURCE_PATH = _SHOW

# web.py puts its own directory on sys.path so it can import the two modules
# beside it. Loading it here therefore has to happen after that is possible,
# which it is: the insert runs at import time inside the module itself.
Web = _load("board_web", _WEB)
Web.SOURCE_PATH = _WEB
Markdown = _load("board_markdown", _MARKDOWN)

SYNC_PATH = _SYNC
SHOW_PATH = _SHOW
WEB_PATH = _WEB
