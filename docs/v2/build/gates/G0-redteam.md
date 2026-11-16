# G0 — Red team of the build blueprint: findings and what was done

**Status: complete for the first pass. The fixes below have not yet had a second independent pass** (see "What this file does not show").

## What this is

Before a plan is adopted, a separate agent that did not write it tries to break it (founder instruction, 16 Nov). The red team here was a fresh session on a different model from the author (Opus; the blueprint was written on Fable), given the repository and one instruction: find what is wrong, unsafe, unbuildable or dishonest in `docs/v2/build/`, and verify numbers by running v1's code, not by reading the plan.

## Log (UTC, 16 Nov 2026)

| When | What |
|---|---|
| about 05:16 | Red team started on blueprint v0.1 (49 builds, specs B01–B18 in the old numbering) |
| before 05:28 | Stopped by the five-hour usage limit before reporting anything. Recorded here as "not complete"; the blueprint's claim that it had been attacked was corrected |
| after the reset | Resumed with its context intact; finished. **Verdict: DO NOT ADOPT as written.** 25 findings: 3 blockers, 16 major, 6 minor |
| same day | Author verified the red team's corrected numbers against v1 by running v1's functions, then redesigned. This file, blueprint v0.2 and the specs are the result |

## The verdict in plain words

The first draft had three ways an unattended AI session could have marked its own work as checked, or changed the rules it was being checked against, without anyone noticing. It also had four test answers that were wrong or that a correct build would have failed by chance, which would have taught the loop to "fix" correct code. Both kinds of error are exactly what this build system exists to prevent, and both were in the plan itself. They were found because the plan was attacked before it was used.

## Findings and what was done

Build numbers are the **new** ones (the mapping from old numbers is below).

### Blockers

| # | Finding | What was done | Where |
|---|---|---|---|
| 1 | **The builder could approve and merge its own work.** It could write the review file and the status file; one row of the loop's decision table merged a branch on a status alone; the "roles" check only bound commits that chose to carry the reviewer's label | Every commit must carry a role. Each role has its own list of paths and of status values it may set. "Passed" or "merged" is refused without a review file naming the current code commit. The decision table merges only when the checks are green on that commit. **Still a guard rail:** nothing proves the reviewer is a different session, because all sessions share one GitHub identity until B05 | `specs/README.md` "Who may write what"; B02 (`roles` guard); B03 rows 13–16; BLUEPRINT 2.2, 2.5 |
| 2 | **The checks ran from the pull request's own code and read the spec from the pull request's own branch.** A build could loosen the check that judged it, or widen its own list of allowed files. Three builds were even told to edit the checks or the workflow | The guard workflow runs on `pull_request_target`: the checking code and the spec both come from the base branch, and pull-request code is never executed by it. The test workflow is written once, in B01, with every job it will need; no later build touches `.github/`. Rule files are listed in `CODEOWNERS` with the founder as owner | B01, B02; BLUEPRINT 2.5 layer 1 |
| 3 | **Every build could edit the master document** ("its own row"; one spec listed the whole file). The document that wins all disagreements was writable by unattended sessions | No build touches the master doc. Builds write a report with a "For the gate" section; the master doc is updated at gates, in a write-up pull request the founder approves. `CLAUDE.md` and master doc §14 now say so | `specs/README.md`; B02 (`protected` guard); `CLAUDE.md` "Build loop"; master doc §14 rule 3 |

### Major

| # | Finding | What was done | Where |
|---|---|---|---|
| 4 | Earlier tests could be switched off without deleting them (a `conftest.py` hook, a pytest option) | New `test_set` guard: the set of collected tests on the branch must contain the base branch's; zero skipped, zero expected-fail; no collection hooks or `addopts` | B02 |
| 5 | **Wrong known answer:** the "laundering" pair (0.5630 / 0.0542) only comes out with the sample skewness and kurtosis passed in; the spec didn't pass them (it would have got 0.56300 / 0.05438 and passed a loose check) | Values pinned to 1e-12 with skew 0.7203182819604969 and kurtosis 16.842229132109118 [Certain — run on v1's fixture with v1's functions], plus a test that the default call gives a *different* number | B10, B20 |
| 6 | **Wrong known answer:** the generator's "planted Sharpe" check used one frame with seed 314, which is a regime world, and one frame is off target by about ±0.5 anyway | Replaced with v1's own test: the mean over 1,000 frames per rung is within ±0.05 of the target | B19 |
| 7 | **Flaky known answer:** the bootstrap cross-check at 5,000 resamples with unpinned seeds would fail a correct build about one run in twenty | 40,000 resamples, seeds pinned, 6% band: the same numbers v1's probe uses [Certain — read in `chronos_math_probe.py`] | B08 |
| 8 | **Wrong known answer:** touchstone T-d's rank was pinned to [20, 80]. A random-entry strategy's rank against a fresh random-entry null is close to uniform, so a correct build fails that about 4 times in 10 | The band is gone. The expectation is the verdict (fails the edge check); the rank is reported | B20 |
| 9 | The fragmentation warning merged lineages transitively, which V2-D34 doesn't say; and its "don't count the same try twice" test could never pass, because a trial's id included its hypothesis | Lineage = the hypothesis plus its direct siblings, as V2-D34 says. New `trial_key` (the try itself, without the hypothesis) makes the duplicate check real. Chains are reported, and the question they raise goes to the founder (O-14) | B10, B18; master doc §12 O-14 |
| 10 | A trial's status was fixed when it was registered, in a table that can't be updated: a run could never go from "started" to "completed", and a run that crashed first was never counted | Trials are registered when they start. What happens next goes into an append-only event table. Honest N counts every registered search trial whatever happened to it | B10 |
| 11 | "One calendar per dataset" would have refused a legitimate check on a sub-window of the same data | The rule is keyed on dataset and window together | B11 |
| 12 | **Gate approval didn't work:** nothing created the tag that meant "approved"; the gate pull request would have failed the scope check; spec corrections and the emergency stop needed pull requests the checks would refuse | A gate is done when its report is on `main`. Branch kinds exist for gate write-ups and spec corrections, both needing the founder's review. The emergency stop is a GitHub issue with a label: no pull request, nothing to block it | B02 (`branch_kind`), B03 (rules; rows 3–4b, 20), B05; BLUEPRINT 2.4, 2.6, Part 6; HANDBOOK §2, §4 |
| 13 | Two sessions could collide: reviews took no claim, claims never renewed, branch names were free text | Every action takes a lock by creating a branch (GitHub refuses a duplicate, so one session wins); the lock renews on each push; branch names are exactly `claude/<id>` | B03 |
| 14 | The cost-vs-moves build chose its minimum holding time on fees alone (against hard rule 3), and its fallback data couldn't get through the data door | The choice is made on fees plus an assumed spread-and-slippage figure, at 2×, shown at three levels (2, 5, 10 bps), and marked provisional until the spike measures it. A Bitstamp loader and instrument mapping exist | B15, B21 |
| 15 | The spread was counted twice: once inside measured slippage, once as its own cost | Slippage is measured against the first print on the same side, so it holds no spread. The cost model states the split | B16, B17 |
| 16 | The seal guard couldn't be delivered as specified (a table the build wasn't allowed to create; a protected migration folder nothing read) | Seal dates live in one protected, founder-owned file created in B02 (a build the founder runs). Builds read it; none may change it | B02, B11, B14 |
| 17 | Two phase-0 builds were about 24 and 23 files each: not one session | Split: scaffold (B01) and guards (B02); loop core (B03) and agents (B04) | LADDER |
| 18 | The first unattended run's "must fail review" probe contradicted its own spec; a decision-table row expected the loop to start a build that had no spec | Probes rewritten: one that must pass, one prepared with a named defect the reviewer must find, one prepared at the point the loop must halt. The table halts on a build with no spec | B03 row 23, B05 |
| 19 | The master doc had been reworded as if proposals P-16–P-19 were approved, and the ladder already depended on one of them | The founder accepted P-16–P-20 on 16 Nov; they are V2-D47–D51. The one sentence the red team objected to (§9 step 2, strict rank) is restored to its original wording with a clarifying note | master doc §9, §10, §12 |

### Minor

| # | Finding | What was done | Where |
|---|---|---|---|
| 20 | One cross-check's expected result was "to be derived by the builder" | Three checks against `ml4t-diagnostic`, each with its expected result stated | B08 |
| 21 | Database attack tests should assert the error class, not just "an error"; a missing primary key; role creation that fails on a second database | Each attack names its error code; `seq` is the primary key; roles are created only if absent | B09 |
| 22 | `CLAUDE.md`'s end-of-session duties contradicted what a reviewer may write | "Build loop" section added to `CLAUDE.md` (for the founder's approval at G0) | `CLAUDE.md` |
| 23 | Missing from the plan: a tool for the sabotage runs the gates promise; a home for proposal P-15; loading the multi-year Kraken history and the nano contract's bars | New builds B22 (sabotage tool) and B42 (Kraken history); nano bars added to B27's card; P-15's check added to B47's card, still the founder's to accept | B22, `BUILD_CARDS.md` |
| 24 | The floating-point tie demonstration was changed once after a first look (from Python's `sum` to `numpy.sum`): a mild breach of "rules before the run" | Recorded as a deviation in the spec. The pass/fail bounds were not moved; the construction is now frozen too | B07 |
| 25 | Wrong line numbers for two v1 functions; one build's "who" differed between two files; "you never need a terminal" next to gate checks that asked for a command | Fixed. A B03 test now fails if the blueprint and the ladder disagree. Gate checks are "open this page, find this line" | B10, B36, BLUEPRINT Part 6, HANDBOOK §4 |

## What the red team checked and found correct

The v1 line counts; the statistics counts (17 functions, 35 tests, 28 probe checks); the pinned statistics values in the stats-core spec; the hand arithmetic in the costs, slippage and cost-vs-moves specs as they then stood; the tie-case numbers with `numpy.sum`; the DSR values in the fragmentation spec.

## Found by the author while fixing (not by the red team)

- The first version of the new sabotage spec (B22) said every change to its toy `clamp` function would be caught. Two of them (`<` to `<=` at a boundary) can never be caught by any test: they don't change behaviour. The expected result was corrected by applying all 11 changes by hand and running them: 7 caught, 4 survive, 2 of those equivalent.
- The master doc says an external SSD is available; the first budget note told the founder to buy one.

Both are the same kind of error the red team found: a confident statement nobody had run.

## What this file does not show

- **The fixes have not been attacked by a second independent pass.** The author wrote them, and an author checking their own fixes is the weakness this whole design is built around.
- **The loop has never run.** Whether the walls hold is tested for real in B05, on GitHub, with the automation's own account, before any real build: it must be shown failing to merge into `main`, failing to approve a pull request, and failing to change a protected value.
- Specs for B23–B54 don't exist yet (cards only), so they haven't been attacked at all.

## Old build numbers → new

| Old | New | | Old | New |
|---|---|---|---|---|
| B01 scaffold and guards | **B01** scaffold + **B02** guards | | B13 costs | B16 |
| B02 loop core | **B03** loop core + **B04** agents | | B14 slippage | B17 |
| B03 first unattended run | B05 | | B15 fragmentation | B18 |
| B04–B06 statistics | B06–B08 | | B16 generator | B19 |
| B07–B09 trial store | B09–B11 | | B17 touchstones | B20 |
| B10–B11 data schema, validate | B12–B13 | | B18 costs vs moves | B21 |
| B12 data door | B14 door + **B15** loaders | | — | **B22** sabotage tool (new) |
| B19–B27 (spike) | B23–B31 | | B28–B37 (collection) | B32–B41 |
| — | **B42** Kraken history load (new) | | B38–B49 (acceptance test) | B43–B54 |

## Walls and guard rails after the redesign

The line-by-line table is BLUEPRINT 2.5. In one sentence: after B02 the checks can't be loosened by the code they judge; after B05 GitHub itself refuses the automation's attempts to move `main`, approve a pull request or change a rule; what remains on trust is that the reviewing session is truly separate from the building one, and that a new test checks as much as its spec says.
