"""Phase 6 — append-only record store + persistent monotonic trial counter.

This is the Mnemosyne STUB: the storage is deliberately primitive (one
JSONL file + one counter file), but the invariants are fully enforced —
they were never deferred, only the storage sophistication was:

- APPEND-ONLY: records can be added and read. There is no update method,
  no delete method, no way to rewrite a line. Immutability is by
  construction, not by discipline.
- EVERY TRIAL COUNTED (I6): the counter is persisted to disk and
  incremented BEFORE execution, so crashed runs count. The count is what
  makes the Deflated Sharpe honest later — an understated trial count is
  how selection bias sneaks back in.

The full Mnemosyne (schema, indexing, querying) arrives later as its own
component and will migrate this file's contents.
"""

import json
from pathlib import Path
from typing import Mapping


class RecordStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._records_path = self.root / "runs.jsonl"
        self._counter_path = self.root / "trial_counter.txt"

    def next_trial_index(self) -> int:
        """Advance and persist the monotonic trial counter. Called BEFORE
        execution so that a run which crashes has already been counted."""
        current = 0
        if self._counter_path.exists():
            current = int(self._counter_path.read_text().strip())
        advanced = current + 1
        self._counter_path.write_text(str(advanced))
        return advanced

    @property
    def trial_count(self) -> int:
        if not self._counter_path.exists():
            return 0
        return int(self._counter_path.read_text().strip())

    def append(self, record: Mapping) -> None:
        """Append one immutable record. There is no corresponding update
        or delete — this is the store's entire write surface."""
        line = json.dumps(record, sort_keys=True, default=str)
        with open(self._records_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read_all(self) -> list[dict]:
        """Fresh copies of every record. Mutating what this returns does
        not — cannot — touch the store; re-reading gives the originals."""
        if not self._records_path.exists():
            return []
        with open(self._records_path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
