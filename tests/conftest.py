"""Pytest configuration shared by the test suite."""

import pathlib
import sys


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
root_str = str(PROJECT_ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
