"""Ring 1 pure domain finite-state machine for SpecKit lifecycle transitions (FR-3605)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar

from alos.domain.models.speckit import InvalidStateTransitionError, LifecycleRecord, LifecycleState

_S = LifecycleState
_R = LifecycleRecord
_E = InvalidStateTransitionError


class SpecKitLifecycleFSM:
    """Pure-domain state machine validating and applying SpecKit lifecycle transitions."""

    VALID_TRANSITIONS: ClassVar[dict[_S, frozenset[_S]]] = {
        _S.DRAFT: frozenset({_S.IN_PROGRESS, _S.APPROVED, _S.DEPRECATED}),
        _S.IN_PROGRESS: frozenset({_S.APPROVED, _S.DRAFT, _S.DEPRECATED}),
        _S.APPROVED: frozenset({_S.COMPLETED, _S.DEPRECATED}),
        _S.COMPLETED: frozenset({_S.ARCHIVED, _S.DEPRECATED}),
        _S.DEPRECATED: frozenset({_S.ARCHIVED, _S.DRAFT}),
        _S.ARCHIVED: frozenset({_S.DRAFT, _S.COMPLETED}),
    }

    @classmethod
    def parse_state(cls, target: str | _S) -> _S:
        """Parse a raw state string or enum into a canonical LifecycleState."""
        if isinstance(target, _S):
            return target
        try:
            return _S(target.lower())
        except ValueError as err:
            raise _E(f"Unknown lifecycle state '{target}'.") from err

    @classmethod
    def can_transition(cls, current: _S, target: _S) -> bool:
        """Return True if transitioning from current to target is permitted (self is no-op)."""
        return target == current or target in cls.VALID_TRANSITIONS.get(current, frozenset())

    @classmethod
    def validate_transition(cls, feat: str, cur: _S, tgt: str | _S) -> _S:
        """Validate transition from current to target, raising InvalidStateTransitionError."""
        t = cls.parse_state(tgt)
        if not cls.can_transition(cur, t):
            ok = sorted(s.value for s in cls.VALID_TRANSITIONS.get(cur, frozenset()))
            raise _E(f"Invalid '{feat}' {cur.value}->{t.value}; allowed={ok}")
        return t

    @classmethod
    def apply_transition(cls, rec: _R, tgt: str | _S, reason: str = "") -> _R:
        """Return a new frozen LifecycleRecord after applying a validated state transition."""
        t = cls.validate_transition(rec.feature_name, rec.current_state, tgt)
        now = datetime.now(timezone.utc).isoformat()
        ev = {"from_state": rec.current_state.value, "state": t.value, "timestamp": now}
        ev["reason"] = reason or "State transition executed"
        upd = {"current_state": t, "updated_at": now, "history": [*rec.history, ev]}
        return rec.model_copy(update=upd)
