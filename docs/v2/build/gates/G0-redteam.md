# G0 — Red team of the build blueprint: findings and what was done

**Status: three passes. First pass (whole draft): do not adopt. Second pass (the fixes): do not adopt, for the loop's enforcement only; the statistics and data fixes held. Third pass (builds B02–B05 as redesigned): see the last section.**

## What this is

Before a plan is adopted, a separate agent that did not write it tries to break it (founder instruction, 16 Nov). The red team here was a fresh session on a different model from the author (Opus; the blueprint was written on Fable), given the repository and one instruction: find what is wrong, unsafe, unbuildable or dishonest in `docs/v2/build/`, and verify numbers by running v1's code, not by reading the plan.

## Log (UTC, 16 Nov 2026)

| When | What |
|---|---|
| about 05:16 | Red team started on blueprint v0.1 (49 builds, specs B01–B18 in the old numbering) |
| before 05:28 | Stopped by the five-hour usage limit before reporting anything. Recorded here as "not complete"; the blueprint's claim that it had been attacked was corrected |
| after the reset | Resumed with its context intact; finished. **Verdict: DO NOT ADOPT as written.** 25 findings: 3 blockers, 16 major, 6 minor |
| same day | Author verified the red team's corrected numbers against v1 by running v1's functions, then redesigned: blueprint v0.2 |
| about 12:30 | **Second pass**, a fresh agent that had seen neither draft being written, on v0.2. **Verdict: DO NOT ADOPT.** 18 findings: 1 blocker, 14 major, 3 minor. Every number it re-ran matched. The loop's enforcement did not hold |
| same day | Author confirmed the two GitHub facts behind the blocker on GitHub's own changelog, then redesigned builds B02–B05: blueprint v0.3 |

## The verdict in plain words

The first draft had three ways an unattended AI session could have marked its own work as checked, or changed the rules it was being checked against, without anyone noticing. It also had four test answers that were wrong or that a correct build would have failed by chance, which would have taught the loop to "fix" correct code. Both kinds of error are exactly what this build system exists to prevent, and both were in the plan itself. They were found because the plan was attacked before it was used.

## Findings and what was done

Build numbers are the **new** ones (the mapping from old numbers is below).

### Blockers

| # | Finding | What was done | Where |
|---|---|---|---|
| 1 | **The builder could approve and merge its own work.** It could write the review file and the status file; one row of the loop's decision table merged a branch on a status alone; the "roles" check only bound commits that chose to carry the reviewer's label | Every commit must carry a role. Each role has its own list of paths and of status values it may set. "Passed" or "merged" is refused without a review file naming the current code commit. The decision table merges only when the checks are green on that commit. **This is a tripwire, not a wall** (second pass, finding 2): the role is a label a session puts on its own commit, and builder and reviewer share one GitHub account even after B05 | `specs/README.md` "Who may write what"; B02 (`roles` guard); B03 rows 13–16; BLUEPRINT 2.2, 2.5 |
| 2 | **The checks ran from the pull request's own code and read the spec from the pull request's own branch.** A build could loosen the check that judged it, or widen its own list of allowed files. Three builds were even told to edit the checks or the workflow | *First answer (v0.2), which the second pass showed to be wrong:* run the guards on `pull_request_target`. *Answer now (v0.3):* the guards run on the ordinary `pull_request` event; the guard code and the spec are checked out from the base commit; rule files are founder-owned, which from B05 means GitHub won't merge a change to them without the founder. See second pass, finding 1 | B01, B02; BLUEPRINT 2.5 layer 1 |
| 3 | **Every build could edit the master document** ("its own row"; one spec listed the whole file). The document that wins all disagreements was writable by unattended sessions | No build touches the master doc. Builds write a report with a "For the gate" section; the master doc is updated at gates, in a write-up pull request the founder approves. `CLAUDE.md` and master doc §14 now say so | `specs/README.md`; B02 (`protected` guard); `CLAUDE.md` "Build loop"; master doc §14 rule 3 |

### Major

| # | Finding | What was done | Where |
|---|---|---|---|
| 4 | Earlier tests could be switched off without deleting them (a `conftest.py` hook, a pytest option) | New `test_set` guard: existing test files are frozen (compared from the base branch); pytest hooks and options are banned by a text scan; the collected tests must contain the base branch's, with zero skipped and zero expected-fail. The gate audit re-runs the previous gate's tests unmodified | B02; BLUEPRINT 2.5 |
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
| 19 | The master doc had been reworded as if proposals P-16–P-19 were approved, and the ladder already depended on one of them | The founder accepted P-16–P-19 on 16 Nov; they are V2-D47–D50 (P-20 was delegated and is not locked: second pass, finding 18). The one sentence the red team objected to (§9 step 2, strict rank) is restored to its original wording with a clarifying note | master doc §9, §10, §12 |

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
- Several builds share a tests folder, so "stay inside your listed files" did not stop a later build from loosening an earlier build's assertion in place. Existing test files are now frozen outright.
- The master doc says an external SSD is available; the first budget note told the founder to buy one.

The first and third are the same kind of error the red team found: a confident statement nobody had run. The second is a hole the first pass didn't reach, which is the argument for a second pass.

## Second pass (on v0.2): findings and what was done

A fresh agent on a different model from the author, told not to trust the "what was done" column above and to verify against the specs. It ran v1's code where it could.

**What held.** Every number it re-ran came out exactly as the specs say: the fixture's hash and statistics, the laundering pair (0.563048882547666 and 0.05423064441493044), the slippage tape, the cost-vs-moves hand arithmetic, the sabotage toy (11 changes: 7 caught, 4 survive), the bootstrap band and the generator test against v1's own files. Of the first pass's 25 findings it judged 13 closed, 8 partly closed, 3 closed but with a new problem introduced, 1 not checked.

**What didn't.** The enforcement around the loop.

| # | Severity | Finding | What was done | Where |
|---|---|---|---|---|
| 1 | **Blocker** | **The guards would never have run.** v0.2 put them on GitHub's `pull_request_target` event "so they come from the base branch". Since 8 Dec 2025 GitHub takes that workflow from the repository's default branch (`main`) whatever the base is, and from 2 Dec 2026 blocks the event in public repositories by default. The guard file would have sat on `v2-build`, never run, and every pull request would have waited forever for a required check: the loop jams before G1 | Both facts confirmed on GitHub's changelog by the author [Certain]. Guards moved to the ordinary `pull_request` event; guard code and spec checked out from the base commit; read-only token, no secrets. The workflow file then travels with the pull request, so what protects it is the founder's required review of `.github/` (from B05). The spec now tells the builder to read GitHub's docs fresh and not design from memory, because that is how this error was made | B02; BLUEPRINT 2.5 |
| 2 | Major | **A builder can pass its own work, before and after B05.** The reviewer's label is self-declared and both roles are one GitHub account | Accepted as true and written down as such everywhere: tripwire plus guard rail, not a wall. The gate audit checks each review against the session each commit came from. The only real wall is a reviewer with its own identity, or the founder merging each build: both are offered to the founder at G1 | `specs/README.md`; BLUEPRINT 2.2, 2.5; B05 "Halt if" |
| 3 | Major | **`main` could move on an approval the founder never gave for that content:** the automation can approve a pull request the founder opened; or add commits after he approved | `main`'s rules now require a code owner's review (only the founder is one), dismiss approvals when anything is pushed, and require the last push to be approved by someone else. All founder-opened pull requests are closed before B05. Attack tests A1–A3 | B05 |
| 4 | Major | **An instruction file planted in a source folder** (`v2/src/…/CLAUDE.md`) would be read by later sessions, and nothing looked for it | Banned by a check, founder-owned at any depth, forbidden in the rules, and attacked (A8) | B02 (`plumbing`), `CODEOWNERS`, `specs/README.md`, `CLAUDE.md`, B05 |
| 5 | Major | **Earlier tests could still be neutralised** without editing them: a hook built from strings, patching a module from a new test file, a plugin added as a library | A new job re-runs the earlier tests **from the base branch's copy of the tests folder**, so nothing the pull request put there is present. Existing test files and oracle scripts are frozen. Libraries can only be added if the spec names them, and the library list is founder-owned. What remains (defeating a test from inside new *source* code) is stated in a table in B02 with what catches it | B02 (`earlier-tests`, `frozen_files`, `plumbing`) |
| 6 | Major | **A required check could be satisfied by a status the automation posts itself** | Required checks are pinned to GitHub Actions as their source; both workflows get a read-only token. Attack tests A4–A5 | B01, B02, B05 |
| 7 | Major | **The first unattended run's probes couldn't pass the checks** (branch names, spec location, ladder, a file outside its allowed list) | Probes are real builds B97–B99 with real specs added by a founder-approved correction, run against their own small ladder, and removed afterwards; measurements go in the report | B05; B03 (`--ladder`) |
| 8 | Major | **The rules contradicted the specs:** "nobody on a build branch changes a workflow, the guards, `CLAUDE.md`", yet B01, B02 and B04 must. A builder told to halt on contradictions would halt | The rule now reads: only if the build's own spec lists the path | `specs/README.md`, `CLAUDE.md` |
| 9 | Major | **A founder build would block the loop for days, and the loop would resume it unattended** when its lock went stale (an unattended session on a broker paper-trading build) | Founder builds are never started, resumed or counted as active by the loop. Builds waiting only for the founder's review are parked | B03 rules; rows 28, 34–36 |
| 10 | Major | **Taking over a stale lock wasn't atomic,** and a slow session could keep pushing after losing its lock | Takeover is a non-forced update from the stale commit (first wins); the holder checks the lock before every push; both races are proved locally and once on GitHub | B03 |
| 11 | Major | **The loop's tests were tied to the live ladder,** so a routine ladder change would turn a frozen test red and halt everything | The decision table runs on frozen copies of the ladder; only two tests read the live files | B03 |
| 12 | Major | **`main` and the working line would drift apart** with no permitted way to bring them together | Each gate write-up merges `main` in; a `doc/…` branch kind exists for document changes between gates | B02, B03; BLUEPRINT 2.4 |
| 13 | Major | **The emergency stop could be closed by the automation; an oracle script could be emptied by a later build** | The loop honours a stop only if the repository owner closed it; `/resume` never closes one; attack A11. Existing oracle scripts are frozen | B03 row 30, B04, B05, B02 |
| 14 | Major | **B02's proofs on GitHub proved nothing** (a build id with no spec fails for the wrong reason) | The proofs use a real id whose spec is on the base branch, with the expected result of each stated | B02 step 6 |
| 15 | Major | **The walls table still called tripwires and guard rails walls** | Rewritten. Three words with fixed meanings; a wall is claimed only where an attack test exists, and only once it has been refused | BLUEPRINT 2.5; HANDBOOK §0, §9 |
| 16 | Minor | Gaps in the loop's decision table (a build with no spec halting every tick; closed-without-merging cases; a stale review lock; the waiting list asserted exactly; counts a builder could under-report) | Rows added; the waiting list is asserted as "includes"; review rounds are counted by the script from review files; the tick count is stated to be self-reported | B03 |
| 17 | Minor | One synthetic check left its sample length to the builder; at one year it fails a correct build about 1 time in 8 | Length fixed at five years, tolerances set from the standard error, and run once | B21 |
| 18 | Minor | `hypothesis_id` undefined; two seeds unnamed; booleans counted as numbers; a "zero" with no tolerance; lint could be switched off; P-20 recorded as a locked decision although the founder had only delegated it | All fixed. P-20 is now an instruction row, to be confirmed by the founder at G1; it is not a decision | B10, B22, B17, B02, master doc §10, §12 |

**What the author takes from two failed passes.** Both times the plan described protection it did not have, and both times the gap was in the part that polices the builders, not in the part that does statistics. The second time the cause was designing GitHub behaviour from memory. The response in v0.3 is to claim less: the working line gets tripwires, `main` gets walls, and a wall counts only after B05 has attacked it on GitHub and been refused.

## What this file does not show

- Whether GitHub really offers every setting B05 relies on, on this account type. The second pass rated them [Likely]; B05 reads each back through the API and halts with options if one is missing.
- **The loop has never run.** Whether the walls hold is tested for real in B05, on GitHub, with the automation's own account, before any real build: eleven named attacks, each of which must be refused.
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

## Walls, tripwires and guard rails after v0.3

The line-by-line table is BLUEPRINT 2.5. In one sentence: on the working line the checks are tripwires that catch mistakes and shortcuts; `main`, the rule files and the emergency stop become walls at B05 if, and only if, GitHub refuses the eleven attacks; what stays on trust is that the reviewing session is separate from the building one, and that new code doesn't defeat a test from the inside. Those two are what the gate audits exist to catch.
