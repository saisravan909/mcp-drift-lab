from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MutationRecord:
    step_index: int
    action: str
    target: str
    before: Any
    after: Any
    compensated: bool = False


@dataclass
class IdempotencyGuard:
    """Tracks state mutations and performs rollback/compensation when failures occur."""

    records: list[MutationRecord] = field(default_factory=list)
    seen_keys: set[str] = field(default_factory=set)

    def is_duplicate_mutation(self, idempotency_key: str | None) -> bool:
        if not idempotency_key:
            return False
        if idempotency_key in self.seen_keys:
            return True
        self.seen_keys.add(idempotency_key)
        return False

    def record_mutation(
        self,
        step_index: int,
        action: str,
        target: str,
        before: Any,
        after: Any,
        idempotency_key: str | None = None,
    ) -> None:
        if idempotency_key:
            self.seen_keys.add(idempotency_key)
        self.records.append(
            MutationRecord(
                step_index=step_index,
                action=action,
                target=target,
                before=deepcopy(before),
                after=deepcopy(after),
            )
        )

    def rollback_to_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Restore recorded state mutations in reverse order."""
        compensated_count = 0
        for rec in reversed(self.records):
            if rec.compensated:
                continue
            if rec.action == "update_config_flag" and rec.target.startswith("feature_flags."):
                flag_name = rec.target.split(".", 1)[1]
                state.setdefault("feature_flags", {})[flag_name] = deepcopy(rec.before)
                rec.compensated = True
                compensated_count += 1
            elif rec.action == "create_incident_note" and rec.target.startswith("incidents["):
                incidents = state.get("incidents")
                if isinstance(incidents, list) and incidents:
                    incidents.pop()
                    rec.compensated = True
                    compensated_count += 1

        return {
            "triggered": compensated_count > 0,
            "compensated_mutations": compensated_count,
            "total_recorded": len(self.records),
        }

    def has_uncompensated_mutations(self) -> bool:
        return any(not rec.compensated for rec in self.records)
