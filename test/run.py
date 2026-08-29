#!/usr/bin/env python3
"""Runs every test file in one process.

    python3 test/run.py

`unittest discover` needs the start directory to be an importable package, and
adding __init__.py files to make it one is two files of ceremony for nothing.
This does the path setup itself and loads each test module by name.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "board"))

loader = unittest.TestLoader()
suite = unittest.TestSuite()
for name in sorted(os.listdir(os.path.join(HERE, "board"))):
    if name.startswith("test_") and name.endswith(".py"):
        suite.addTests(loader.loadTestsFromName(name[:-3]))

result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
