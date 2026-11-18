"""Known-answer tests for dict-key validation in ``chronos2.core.canonical``.

B01 shipped ``content_hash`` with dict keys passing through a bare ``str()``
while values went through ``_canonical``. These tests pin the fix (B01A): a
dict key must be a ``str``; any other key type raises ``TypeError``. The
string-key regression guards here also pin the wire format, so a future change
to how a value is rendered fails loudly instead of silently invalidating every
fingerprint already stored.
"""

import os
import subprocess
import sys
from datetime import datetime
from decimal import Decimal

import pytest

from chronos2.core.canonical import canonical_json, content_hash

_STABILITY_DIGEST = "825348ea6f54adfb39bf21dd3778081fdbdec80f41ea178c1ea5f606770cbb6b"


def test_dict_key_object_raises_typeerror():
    with pytest.raises(TypeError):
        canonical_json({object(): 1})


def test_dict_key_naive_datetime_raises_typeerror():
    with pytest.raises(TypeError):
        canonical_json({datetime(2026, 4, 1): 1})


def test_dict_key_nan_raises_typeerror():
    with pytest.raises(TypeError):
        canonical_json({float("nan"): 1})


def test_dict_key_int_raises_typeerror():
    with pytest.raises(TypeError):
        canonical_json({1: "x"})


def test_dict_key_int_str_collision_raises_typeerror():
    with pytest.raises(TypeError):
        canonical_json({1: "x", "1": "y"})


def test_dict_key_nested_raises_typeerror():
    # The key check must recurse, not run only on the outermost dict.
    with pytest.raises(TypeError):
        canonical_json({"a": {"b": {2: 3}}})


def test_canonical_json_string_keys_unchanged():
    assert (
        canonical_json({"b": 1, "a": [1.0, Decimal("0.10")]})
        == '{"a":["1.0","0.10"],"b":1}'
    )


def test_content_hash_string_keys_stability_pin():
    # The SHA-256 of the canonical JSON string above; hand-checkable with
    # printf '%s' '{"a":["1.0","0.10"],"b":1}' | sha256sum.
    assert (
        content_hash({"b": 1, "a": [1.0, Decimal("0.10")]})
        == _STABILITY_DIGEST
    )


def test_content_hash_deterministic_across_processes():
    # The regression test for the actual defect: a fingerprint must not depend
    # on the process. Run in two fresh subprocesses with PYTHONHASHSEED left
    # unset, so hash randomisation is in play as it is in CI.
    code = (
        "from decimal import Decimal; "
        "from chronos2.core.canonical import content_hash; "
        'print(content_hash({"b": 1, "a": [1.0, Decimal("0.10")]}))'
    )
    env = dict(os.environ)
    env.pop("PYTHONHASHSEED", None)
    for _ in range(2):
        run = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == _STABILITY_DIGEST
