"""Environment checks for the v2 project.

The v2 environment must run Python 3.14 (V2-D45), import its own package
(``chronos2``), and stay fully separate from the frozen v1 ``chronos`` package.
"""

import importlib.util
import sys


def test_python_is_314():
    assert sys.version_info[:2] == (3, 14)


def test_import_chronos2():
    import chronos2

    assert chronos2.__name__ == "chronos2"


def test_v1_chronos_is_not_importable():
    assert importlib.util.find_spec("chronos") is None
