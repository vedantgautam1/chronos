# S12 deep-pass checks — rules written before running (3 Nov 2026, 19:00 ET)

Both checks use the book's own code (`agentlab-lab-part2`: `ledger.Ledger.measure`, `evalr.sidak_z`) and its 12-candidate pool.

## P-3. Does splitting a search into families lower the bar?
Worlds: 100 no-edge, costless (pure null; seeds 6000-6099). Each of the 12 candidates is measured against the baseline on the development window (days 0-750); statistic = paired daily t (`diff_t`).
A "false find" = at least one candidate clears the bar its counting rule gives it.
Counting rules:
 1. one family of 12 (bar = Šidák(12) = 2.63)
 2. the book's natural families: vol (4), trend (1), session (3), lookback (2), hold (2), each with its own Šidák bar
 3. every candidate its own family (bar = 1.645)
 4. union N across families (bar = Šidák(12)) — the v1 fragmentation-screen fix
Also confirm in the ledger that `attempts(family)` returns 1 under rule 3 while `attempts()` returns 12.
P-3 is supported if rule 3's false-find rate is at least 3x rule 1's. Rule 2 is reported as the realistic middle case.

## P-4. Does a change check without "candidate must make money" accept trade-less changes against a losing baseline?
Worlds: 60 no-edge (seeds 6100-6159) and 60 planted (seeds 6200-6259), costs 2 bps per side (1x) and 4 bps (2x).
Each of the 12 candidates is a proposed change to the live version (= baseline), judged on the validation window (days 750-1125), N = 12 counted.
Rules:
 A. paired t of daily P&L (candidate minus baseline) at 2x costs >= Šidák(12)   [v2 §6 change check as written]
 B. A and the candidate's own net bps per trade at 2x costs > 0                 [P-4]
 B1. A and the candidate's own net bps per trade at 1x costs > 0                [softer P-4]
Report per rule: share of no-edge worlds with >= 1 acceptance; in planted worlds, share with >= 1 truly helpful candidate accepted and share with >= 1 unhelpful candidate accepted; the baseline's own net at 2x costs.
P-4 is supported if rule A accepts something in >= 10% of no-edge worlds and rule B cuts that to <= 3%.
If rule B also cuts acceptance of truly helpful candidates in planted worlds by more than half, P-4 must be softened (B1, or a warning instead of a gate) and I say so.
