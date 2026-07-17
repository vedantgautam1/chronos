"""Sealed-range registry — enforces invariant I4 (the holdout is sealed).

A sealed range is data that must not be looked at, queried, or used for
ANY purpose except one pre-registered final evaluation (Atropos). The
registry records WHICH ranges are sealed; get_bars() (access.py) is the
enforcement point — it refuses any request that overlaps a sealed range
unless the caller presents a FinalEvaluationToken.

This is deliberately a small, primitive registry (one JSON file), same
spirit as the Mnemosyne stub: the INVARIANT is not deferred, only the
storage sophistication is. seal() is strictly additive — there is no
unseal/remove method — so a seal, once recorded, can only be added to,
never quietly undone by this module.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chronos.oceanus.model import Timeframe

# configs/ holds durable, git-tracked operational metadata (see also
# configs/binance_fees.md) — unlike data/, which is gitignored and
# re-derivable. A seal registry is NOT re-derivable: losing it silently
# un-seals a holdout, so it lives in the tracked location by default.
DEFAULT_SEAL_PATH = Path(__file__).resolve().parents[3] / "configs" / "sealed_ranges.json"


def _require_utc(moment: datetime, name: str) -> None:
    if moment.tzinfo is None:
        raise ValueError(f"{name} is naive (no timezone): {moment}")
    if moment.utcoffset() != timedelta(0):
        raise ValueError(f"{name} is not UTC: {moment}")


@dataclass(frozen=True)
class SealedRange:
    """One sealed holdout range. Immutable once created."""

    symbol: str
    timeframe: Timeframe
    start: datetime
    end: datetime
    sealed_at: datetime
    reason: str

    def __post_init__(self) -> None:
        _require_utc(self.start, "start")
        _require_utc(self.end, "end")
        _require_utc(self.sealed_at, "sealed_at")
        if self.start >= self.end:
            raise ValueError(f"start ({self.start}) must be before end ({self.end})")
        if not self.reason.strip():
            raise ValueError("reason must be non-empty")

    def overlaps(self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime) -> bool:
        """True if [start, end) intersects this sealed range at all,
        for the same symbol and timeframe."""
        if symbol != self.symbol or timeframe != self.timeframe:
            return False
        return start < self.end and self.start < end

    def to_json(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "sealed_at": self.sealed_at.isoformat(),
            "reason": self.reason,
        }

    @staticmethod
    def from_json(payload: dict) -> "SealedRange":
        return SealedRange(
            symbol=payload["symbol"],
            timeframe=Timeframe(payload["timeframe"]),
            start=datetime.fromisoformat(payload["start"]),
            end=datetime.fromisoformat(payload["end"]),
            sealed_at=datetime.fromisoformat(payload["sealed_at"]),
            reason=payload["reason"],
        )


@dataclass(frozen=True)
class FinalEvaluationToken:
    """The key that unlocks sealed data.

    This is opened EXACTLY ONCE, for Atropos's single, pre-registered
    final evaluation against the sealed holdout — not to "just check"
    something, not for a second look, not for a quick peek during
    development. Constructing this object is itself a significant,
    auditable act: every use is logged with its `reason` at the point
    sealed data is served. If you are constructing one of these outside
    of that single final evaluation, stop and reconsider.
    """

    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("FinalEvaluationToken.reason must be non-empty")


class SealRegistry:
    """Loads/saves the sealed-range list. seal() is strictly additive —
    there is no method to remove or edit a seal once recorded."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else DEFAULT_SEAL_PATH
        self._ranges: list[SealedRange] = self._load()

    def _load(self) -> list[SealedRange]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text())
        return [SealedRange.from_json(entry) for entry in payload]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([r.to_json() for r in self._ranges], indent=2))

    def seal(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime, reason: str
    ) -> SealedRange:
        """Record a new sealed range and persist it. Additive only."""
        sealed = SealedRange(
            symbol=symbol, timeframe=timeframe, start=start, end=end,
            sealed_at=datetime.now(timezone.utc), reason=reason,
        )
        self._ranges.append(sealed)
        self._save()
        return sealed

    def is_sealed(self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime) -> bool:
        """True if [start, end) overlaps ANY sealed range for this symbol/timeframe."""
        return any(r.overlaps(symbol, timeframe, start, end) for r in self._ranges)

    def overlapping(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[SealedRange]:
        """Every sealed range [start, end) intersects — for error messages."""
        return [r for r in self._ranges if r.overlaps(symbol, timeframe, start, end)]

    def sealed_ranges(self) -> list[SealedRange]:
        """A copy of every current seal. Mutating this list does not
        touch the registry; re-read to get the originals."""
        return list(self._ranges)
