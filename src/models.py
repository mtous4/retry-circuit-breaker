"""
Data models and ISO timestamp utilities for the Policy Engine.
Derived strictly from docs/POLICY.md §2.1, §2.3, §2.4.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def parse_iso_to_epoch_ms(iso_str: str) -> int:
    """
    Parses an ISO 8601 UTC timestamp (e.g., '2026-09-01T10:00:00.000Z')
    into integer milliseconds since UNIX Epoch.
    """
    # Normalize trailing 'Z' to UTC offset
    clean_str = iso_str.strip()
    if clean_str.endswith("Z"):
        clean_str = clean_str[:-1] + "+00:00"
    
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return int(dt.timestamp() * 1000)


@dataclass(frozen=True)
class CallOutcome:
    """Input record from outcomes.jsonl."""
    id: str
    provider: str
    started_at: str
    status: str
    latency_ms: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallOutcome":
        return cls(
            id=str(data["id"]),
            provider=str(data["provider"]),
            started_at=str(data["started_at"]),
            status=str(data["status"]),
            latency_ms=int(data["latency_ms"]),
        )


@dataclass(frozen=True)
class DecisionRecord:
    """Output record for decisions.jsonl."""
    id: str
    action: str
    provider_state: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "action": self.action,
            "provider_state": self.provider_state,
            "reason": self.reason,
        }


@dataclass
class StoppedPeriod:
    """Stopped / outage period object for stopped_periods.json."""
    stopped_at: str
    resumed_at: Optional[str] = None
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stopped_at": self.stopped_at,
            "resumed_at": self.resumed_at,
            "duration_ms": self.duration_ms,
        }
