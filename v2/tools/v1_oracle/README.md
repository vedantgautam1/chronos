# v1 oracle

The **v1-oracle** CI job runs every `dump_*.py` in this folder inside the
**v1** environment (repo root), then fails if any output under
`v2/tests/known_answers/v1_oracle/` changed.

A dump script computes a known answer from the frozen v1 code — a number that
v2 must reproduce — and writes it to
`v2/tests/known_answers/v1_oracle/<name>.json`. They exist so v2's ports can be
checked against v1's outputs without v2 importing v1. The first one is written
by build B06; until then this folder holds no dump scripts and the CI job
passes trivially.
