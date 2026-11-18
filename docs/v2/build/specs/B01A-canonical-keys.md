```yaml
id: B01A
title: canonical.py — dict keys validated like values; the fingerprint made deterministic
size: S
model: opus          # see "For the gate": the founder may switch this to the P-24 cheap builder
who: founder         # run by hand: the loop doesn't exist until B05
needs: [B01]
ticks: 2
touches:
  - v2/src/chronos2/core/canonical.py
  - v2/tests/core/test_canonical_keys.py
may_modify_tests: []
adds_dependencies: []
```

# B01A — canonical.py: dict keys validated like values

## Why

B01 shipped `content_hash` with a hole: dict **values** go through `_canonical`, dict
**keys** go through a bare `str()`. Keys are therefore never validated and never
canonicalised, and three things follow [Certain — run, review `B01-r1.md` finding 1]:

- A key of a type the module doesn't know is stringified into the hash **with its memory
  address**, so the same input hashes differently in every process. Three runs of
  `content_hash({Thing(): 1})` gave `c16f45e8…`, `c079c2e0…`, `ec227604…`.
- A naive `datetime` key and a `float("nan")` key each reach a hash instead of raising,
  though B01's spec (Deliver 4) says the function raises on both.
- Two keys that collide under `str()` silently lose one: `{1: "x", "1": "y"}` canonicalises
  to `{"1":"y"}`, with no error.

B01's "Why" calls this module "a stable fingerprint of any piece of data". A fingerprint
that changes between runs is not one. Everything downstream that detects "have we already
looked at this?" stands on it — B09's trial store, B10's trial ontology and honest `N`,
B11's data footprint and compare guard. A fingerprint that drifts turns a repeat trial into
a fresh one, which is the self-deception the trial ontology exists to prevent.

The defect is narrow: it only fires on a dict whose key is not a string or a whole number,
and today's config dicts are string-keyed, so it may never have fired in practice [Likely].
It is fixed now, before B02, because it is a few lines now and because every later build
hashes against this function.

**This build fixes a merged defect.** B01 was reviewed `CHANGES` on this finding and merged
into `v2-build` anyway, by mistake, before the fix (`LEDGER.md` footnote; `CHANGELOG.md`
18 Nov). The record is not tidied away: `v2-build` carried a known defect from `78298f3`
until this build lands.

## Read first

- `docs/v2/build/reviews/B01-r1.md` finding 1 (the evidence above, with line numbers).
- `docs/v2/build/specs/B01-scaffold.md` Deliver item 4 — the contract this restores.
- `v2/src/chronos2/core/canonical.py` as it stands (67 lines; the bug is line 36).
- `BUILD_NOTES.md` §1, the "canonical keys" trap.

## Deliver

1. `_canonical` validates dict keys. **A dict key must be a `str`.** Any other key type
   raises `TypeError`, naming the offending key's type. This single rule closes all three
   leaks at once: an unknown type, a naive `datetime` and a NaN can no longer reach a hash
   as a key, and two keys can no longer collide after conversion because no conversion
   happens.
2. Everything else in `canonical.py` is unchanged: sorted keys, `Decimal` → its string,
   `datetime` → ISO-8601 UTC with `Z`, floats by `repr`, tuples as lists, enums by value,
   and the existing raises on NaN, infinities, naive datetimes, sets and unknown **values**.
   No existing B01 known answer changes: every B01 test uses string keys, so
   `v2/tests/core/test_canonical.py` must still pass **unmodified**.
3. `v2/tests/core/test_canonical_keys.py` — a new file (B01's test file is frozen; this
   build does not touch it) holding the known answers below.

## Steps

1. Commit the known-answer tests below (red: the key tests fail because the keys are
   accepted today, and the stability test passes already — say so in the report).
2. The one-rule change in `_canonical`. Green.
3. Report.

## Known answers and checks

**Keys that must now raise `TypeError`** (each its own test):

| Input | Today [Certain — run] | Required |
|---|---|---|
| `canonical_json({object(): 1})` | returns `{"<object object at 0x…>":1}` | raises `TypeError` |
| `canonical_json({datetime(2026, 4, 1): 1})` | returns `{"2026-04-01 00:00:00":1}` | raises `TypeError` |
| `canonical_json({float("nan"): 1})` | returns `{"nan":1}` | raises `TypeError` |
| `canonical_json({1: "x"})` | returns `{"1":"x"}` | raises `TypeError` |
| `canonical_json({1: "x", "1": "y"})` | returns `{"1":"y"}` — a key silently lost | raises `TypeError` |

**Nested, not only at the top level:** `canonical_json({"a": {"b": {2: 3}}})` raises
`TypeError`. A key check that only runs on the outermost dict is wrong.

**String keys keep working exactly as before** — this is the regression guard on Deliver 2:

- `canonical_json({"b": 1, "a": [1.0, Decimal("0.10")]}) == '{"a":["1.0","0.10"],"b":1}'`
- `content_hash({"b": 1, "a": [1.0, Decimal("0.10")]}) ==`
  `"825348ea6f54adfb39bf21dd3778081fdbdec80f41ea178c1ea5f606770cbb6b"`

  This digest is **hand-checkable without our code** — it is the SHA-256 of the canonical
  JSON string above, and `printf '%s' '{"a":["1.0","0.10"],"b":1}' | sha256sum` prints it
  [Certain — run]. It is a **stability pin**, not an independently derived truth: its job is
  to make any future change to the wire format fail loudly, because a silent change would
  invalidate every fingerprint already stored.

**Determinism across processes** (the regression test for the actual defect): compute
`content_hash({"b": 1, "a": [1.0, Decimal("0.10")]})` in two fresh subprocesses and assert
both equal the digest above. Run the subprocesses with `PYTHONHASHSEED` left at its default
so hash randomisation is in play, as it is in CI.

## Not in this build

- **Widening the allowed key types.** If a later build needs `int`, `Decimal`, `datetime` or
  `Enum` keys, that is a change to this contract and gets its own spec and known answers;
  the caller converts to a string in the meantime. Raising is the safe default and is
  cheaper to widen later than to narrow.
- **The value-side type collision** (`1.0`, `Decimal("1.0")` and `"1.0"` all canonicalise to
  `"1.0"`, so they share a fingerprint). That follows B01's spec as written and is a design
  question for the gate (`CHRONOS_V2.md` §12, O-15), not a defect. Do not change it here.
- The guards (B02); anything else in `canonical.py` or `timeutil.py`.

## Halt if

- Any existing B01 test in `v2/tests/core/test_canonical.py` goes red. It shouldn't: every
  one uses string keys. If one does, the change has reached further than this spec allows —
  stop and say which test and why.
- A caller already in the tree depends on a non-string key. Nothing should; B01 is the only
  code that exists.

## For the gate

- **Open question O-16 (`CHRONOS_V2.md` §12): which model builds this.** The header says
  `model: opus`, matching every other spec in the ladder. The founder's 17 Nov instruction
  (§10) allows a cheaper builder, and proposal P-24 is still logged "Proposed". B01 was
  built on DeepSeek V4 Pro and reviewed `CHANGES` on one finding — the review caught it,
  which is the system working, but the merge misfire means P-24 has **no clean
  measurement** yet. Running B01A on DeepSeek would restart that measurement on a tightly
  specified, known-answer-first change; running it on Opus is the conservative choice for a
  correctness fix in the foundation helper. The founder decides; change the header before
  the build starts rather than deviating from it during.
- **`LEDGER.md`:** B01A's actual ticks and review rounds, and — for P-24 — whether a build
  this tightly specified needed a second round.
- **B03's spec** (`specs/B03-loop-core.md`) decision-table rows 2 and 3 say "B01–B05
  merged". With B01A on the ladder that wording is stale. B03 builds its own frozen ladder
  fixtures, so nothing goes red; the wording wants a one-line fix when B03 is specified or
  at G1.
- **B05's GitHub rules:** require the status file to read `passed` before a pull request
  into `v2-build` can merge. That is what would have stopped the B01 misfire, and it costs
  nothing to add while the rules are being written.
