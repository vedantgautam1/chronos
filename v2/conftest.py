"""B03 step 0 proof (c): the conftest trick, which the earlier-tests job must ignore.

This is red-team finding f's first trick: a conftest ABOVE the tests folder whose
hook silently drops an earlier build's test. Run from this tree it works. The
`earlier-tests` job takes only v2/src/chronos2, v2/migrations, v2/pyproject.toml
and v2/uv.lock from the pull request, so this file is never present there -- the
dropped test still runs, and the job must stay GREEN with the same test count.
"""


def pytest_collection_modifyitems(config, items):
    items[:] = [i for i in items if "test_require_utc_rejects_naive" not in i.nodeid]
