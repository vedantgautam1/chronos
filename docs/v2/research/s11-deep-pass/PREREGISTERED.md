# S11 deep-pass checks — rules written before running (3 Nov 2026, 18:40 ET)

## A. False-lesson rate of the corrected lesson miner under the null
Book claim (Part 1, ch. 9): corrected miner reports a lesson in 1 of 30 no-structure worlds (3.3%), "close to the 5% a significance level of 0.05 allows".
Test: the book's own code (`mine_lessons`, min_n=30, Bonferroni) on 300 no-structure worlds (seeds 5000-5299), first 1,000 days, same setup as the book.
- Holds if the rate is <= 7%.
- Fails if the rate is > 10%.
- In between: "slightly above nominal".

## B. Replication gate for my retrieval re-implementation
My vectorised copy of `retrieve`/`recommend` must reproduce the book's E2 on the same seeds (900-919, planted):
Spearman within +-0.005 of 0.3065 and skip gain within +-0.05 bps of 5.697. If not, results C are not used.

## C. Does the retrieval result depend on indexing exactly the planted variables?
The world plants two effects: hidden calm/turbulent state (memory sees it through a 50/500 vol ratio) and "first 4 bars of the day" (memory's session key is exactly bar < 4).
Variants, same 20 planted seeds, same k=25, min_n=15, t threshold 2:
 1. published keys (= B)
 2. session cut at bar < 2 (mis-specified)
 3. session cut at bar < 8 (mis-specified)
 4. no session key at all (the condition was never thought of)
 5. published keys + 4 irrelevant 3-level keys, weight 2 each (memory indexes conditions it can't tell are irrelevant)
 6. only irrelevant keys (4 random keys + trend) — retrieval is effectively "recent similar-by-nothing"
Plus variant 5 on 20 no-structure worlds (seeds 920-939) as a control: must stay near zero.
Reading: variants 2-5 keeping >= 80% of the published Spearman and skip gain = "robust to key choice"; < 50% = "result depends on knowing the mechanism".
