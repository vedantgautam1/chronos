```yaml
id: B22
title: Sabotage harness — break the code on purpose and count what the tests miss
size: S
model: opus
who: loop
needs: [B08]
ticks: 2
touches:
  - v2/tools/sabotage/**
  - v2/tests/tools/sabotage/**
  - docs/v2/build/sabotage/**
  - docs/v2/BUILD_NOTES.md
may_modify_tests: []
```

# B22 — Sabotage harness

## Why
"All tests pass" says nothing if the tests don't check much. The direct way to find out: change the code slightly, on purpose, many times (flip a `<` to `<=`, turn a `+` into a `-`, replace a constant), and see whether any test notices. A change no test catches is a hole. Every reviewer already does this once per build by hand; gates need it done systematically, by a script, with a number at the end. The blueprint promised this at every gate and the first draft had no build that created it (G0 red team, finding 23).

## Read first
- BLUEPRINT 2.5 (layer 5) and Part 6 (the gate report's "sabotage" section).
- Python's `ast` module docs (the tool rewrites syntax trees; it uses no third-party mutation library, so nothing new is trusted).

## The rules (fixed here)
- **Mutations** (each applied alone, one at a time): comparison flips (`<`↔`<=`, `>`↔`>=`, `==`↔`!=`); arithmetic swaps (`+`↔`-`, `*`↔`/`); a numeric constant `c` (an `int` or `float` literal; `True` and `False` are not numeric constants here) → `c + 1` and, if `c != 0`, → `-c`; `and`↔`or`; `return x` → `return None`; removing a `raise`.
- The tool works on a **temporary copy** of `v2/`; the real tree is never modified. For each mutation it runs only the tests under the matching `v2/tests/<module>/` folder, with a time limit of 3× that folder's normal run time; a timeout counts as caught.
- **Sampling is fixed in advance:** when a module has more candidate mutations than the budget, the sample is drawn with a seed given on the command line and written into the output. A gate uses seed = the gate number.
- Output: `survivors.json` (file, line, the mutation, the code before and after) and a one-page summary: tried, caught, survived, score.
- **A survivor is a finding, not a failure of this build.** At a gate, every survivor is either answered with a new test (in a fix build) or listed in the gate report with the reason it is equivalent (the change doesn't alter behaviour).

## Deliver
1. `v2/tools/sabotage/mutate.py` (generate mutations from a file), `run.py` (apply, test, record), `report.py`.
2. A toy package under `v2/tests/tools/sabotage/toy/` with its own small test file, built so the answer is known.
3. Tests for the tool itself.
4. A first real run on `v2/src/chronos2/stats/`, budget 150 mutations, seed 2; results in `docs/v2/build/sabotage/G2-stats.md`.

## Steps
1. Toy package and the known-answer tests for the tool (red). 2. `mutate.py`. 3. `run.py`, `report.py` → green. 4. The run on `stats/`. 5. Report.

## Known answers and checks
**The toy module**, exactly this (so the answer is known):

```python
def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x

def mean(xs):
    return sum(xs) / len(xs)

def is_adult(age):
    return age >= 18
```

Its tests, exactly these nine: `clamp(-1,0,10)==0`, `clamp(0,0,10)==0`, `clamp(5,0,10)==5`, `clamp(10,0,10)==10`, `clamp(11,0,10)==10`, `mean([1,2,3])==2`, `mean([4])==4`, `is_adult(30) is True`, `is_adult(5) is False`. **The boundary at 18 is deliberately untested.**

Expected, exactly [Certain — the 11 mutations were applied by hand and run, 16 Nov]:
- The rules above produce **11** mutations of this module: 5 in `clamp`, 2 in `mean`, 4 in `is_adult`.
- **7 caught, 4 survive.** The survivors:
  - `age >= 18` → `age > 18`, and `18` → `19`: **a real hole** (nothing tests age 18).
  - `x < lo` → `x <= lo`, and `x > hi` → `x >= hi`: **equivalent**: at the boundary the function returns the same value either way, so no test could ever catch them. The tool can't tell these apart from real holes; a person or a reviewer has to. This is why a survivor is a finding to answer, not a failure.
- `18` → `-18` is caught (the test at age 5 fails).
- Adding the test `is_adult(18) is True` and re-running: **9 caught, 2 survive** (the two equivalent ones).
- Two runs with the same seed list the same mutations in the same order; with a budget of 5, seeds 1 and 2 give different samples (if they happen to coincide, that is reported and the test uses seeds 1 and 3; no other seed is tried).
- After any run, `git status` on the real tree is clean (asserted).
- A mutation that makes a test hang is reported as caught by timeout, and the run continues (tested with a toy `while` loop added in the test for the tool, not in the toy above).

**The run on `stats/`:** the report states tried, caught and survived, and lists every survivor. No pass mark is set here: this is the first measurement, and the bar for later gates is the founder's to set at G2 with this number in hand.

## Not in this build
Running it on anything but `stats/` (each gate audit does that) · fixing survivors (a fix build, if the founder wants one) · mutation of SQL migrations.

## Halt if
- The tool would need to modify the real working tree to work.
- A run of 150 mutations on `stats/` takes more than one tick. Then the budget or the test selection needs a decision.

## For the gate
`BUILD_NOTES.md` §2 (this build edits it): "sabotage runs: `v2/tools/sabotage/`; survivors are findings, answered at gates". The G2 report quotes the `stats/` score and the survivors.
