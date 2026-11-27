```yaml
id: B97
title: "Probe: one whole build, unattended"
size: S
model: opus
who: loop
needs: []
ticks: 2
touches:
  - scratch/probe/b97.md
  - scratch/probe/b97_check.sh
may_modify_tests: []
adds_dependencies: []
```

# B97 — probe: one whole build, unattended

## Why

The loop has never run a build by itself. This is the smallest build that is still a whole one: a claim, a known-answer check written before the thing it checks, a report, a separate review that breaks something on purpose, and a merge. It is on the probe ladder (`docs/v2/build/probe/LADDER.probe.yaml`), not the real one, and it works only under `scratch/probe/`, which no one owns. B05B removes this spec once the probes are done.

## Read first

- `docs/v2/build/specs/README.md`, in full. Nothing else is needed.

## Deliver

1. `scratch/probe/b97_check.sh`, exactly as written under "Known answers" below, byte for byte.
2. `scratch/probe/b97.md`: exactly one line, the sentence below followed by one newline (LF), and no other bytes (94 bytes in all):

   ```
   B97 is the first Chronos build the loop ran from start to finish with nobody at the keyboard.
   ```

3. As for every build: `docs/v2/build/status/B97.json`, `docs/v2/build/reports/B97.md` from `templates/report.md`, and one new section at the top of `docs/v2/CHANGELOG.md`.

## Steps

1. **The check first** (builder rule 2). Commit `scratch/probe/b97_check.sh`. Run it from the repository root with `bash scratch/probe/b97_check.sh`. It must fail because `scratch/probe/b97.md` does not exist (`No such file or directory`), not for any other reason. Paste the failing output into the report.
2. **The file.** Commit `scratch/probe/b97.md`. The check prints `B97 known answer: PASS`. Then finish as builder rule 7 says, in the same commit: the three commands from `v2/`, the report, the CHANGELOG section, the status `needs_review`, and the pull request marked ready.

## Known answers and checks

The check, committed in step 1 exactly as follows:

```bash
#!/usr/bin/env bash
# B97's known-answer check (specs/B97-probe-whole-build.md). Exit 0 only if
# scratch/probe/b97.md holds exactly the bytes the spec gives.
set -euo pipefail
want="c758daee7e6c36a38ea6f6720160294e9cfe8931208927e1b3f078f8f71b71fd"
file="$(git rev-parse --show-toplevel)/scratch/probe/b97.md"
got="$(sha256sum "$file" | cut -d' ' -f1)"
if [ "$got" = "$want" ]; then
  echo "B97 known answer: PASS ($got)"
else
  echo "B97 known answer: FAIL: expected $want, got $got"
  exit 1
fi
```

- At the end of step 1: `bash scratch/probe/b97_check.sh` exits non-zero, because the file is missing.
- At the end of step 2: it exits 0 and prints `B97 known answer: PASS (c758daee7e6c36a38ea6f6720160294e9cfe8931208927e1b3f078f8f71b71fd)`.
- `TZ=UTC uv run pytest -q`, `uv run ruff check .` and `uv run python tools/guards/run_all.py`, from `v2/`, pass as they do on `v2-build`. This build adds no Python.
- **For the reviewer's step 3** ("break one thing on purpose"): the thing this build is about is the file. Change one word of `scratch/probe/b97.md` locally, run the check, see it fail, and restore the file.
- **The merge.** B97 is past B06, so reviewer rule 6's "From B06" path applies: on the `MERGE` action the reviewer adds one last commit that writes a B97 row into `LEDGER.md`'s table, directly below B05B's row, and sets the status to `merged`; it waits for green checks, then squash-merges into `v2-build`. Nothing in this build is founder-owned, so the merge needs no one.

## Not in this build

Anything outside `scratch/probe/` and the three files every build writes. Any real work.

## Halt if

Builder rule 9 and reviewer rules as written. In particular: needing any path outside `touches`, or any step that needs the founder present. This build must reach `merged` with no one at the keyboard; if it can't, that is the finding.

## For the gate

Nothing of its own. B05B's report records what this probe showed: the ticks, their times, the actions, and what each cost.
