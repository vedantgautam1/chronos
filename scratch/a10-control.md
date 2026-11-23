# A10 — the control for B05's attack tests

This file exists only so that attack test A10 has something harmless to change.

A10 is the control: a `lane/a10` pull request touching nothing but `scratch/`,
with green checks and no approval, **must merge**. If it is refused, then a
build could not merge its own work either, and one of Deliver 3's settings is
wrong rather than one of the attacks being a wall.

Written by B05's builder session, 23 Nov 2026.
