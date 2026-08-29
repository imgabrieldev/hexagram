"""Puts skills/board on the import path so tests can `from board_test_helper import Board`."""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_SYNC = os.path.join(os.path.dirname(_HERE), "skills", "board", "sync.py")

_spec = importlib.util.spec_from_file_location("board_sync", _SYNC)
Board = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(Board)

SYNC_PATH = _SYNC
