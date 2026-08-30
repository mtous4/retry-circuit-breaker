"""
Finite State Machine (FSM) tracking health lifecycle for an individual provider.
Derived strictly from docs/POLICY.md §3.4, §3.5, §4.2, §6.
"""

from typing import List, Optional
from src.models import StoppedPeriod, parse_iso_to_epoch_ms


class ProviderFSM:
    """Encapsulates the 3-state Circuit Breaker FSM and stopped period history for a single provider."""

    def __init__(self, provider_id: str) -> None:
        self.provider_id: str = provider_id
        self.state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.consecutive_failures: int = 0
        self.opened_at: Optional[str] = None
        self.cooldown_until: int = 0  # epoch ms
        self.stopped_intervals: List[StoppedPeriod] = []
        self._active_stopped_period: Optional[StoppedPeriod] = None

    def open_circuit(self, opened_at_iso: str, cooldown_until_ms: int) -> None:
        """Transitions provider to OPEN, sets cooldown timer, and opens a stopped period if not already open."""
        self.state = "OPEN"
        self.opened_at = opened_at_iso
        self.cooldown_until = cooldown_until_ms
        if self._active_stopped_period is None:
            self._active_stopped_period = StoppedPeriod(stopped_at=opened_at_iso)
            self.stopped_intervals.append(self._active_stopped_period)

    def recover_circuit(self, resumed_at_iso: str) -> None:
        """Transitions provider to CLOSED, resets failure count, and closes active stopped period."""
        self.state = "CLOSED"
        self.consecutive_failures = 0
        self.opened_at = None
        self.cooldown_until = 0
        
        if self._active_stopped_period is not None:
            self._active_stopped_period.resumed_at = resumed_at_iso
            stopped_ms = parse_iso_to_epoch_ms(self._active_stopped_period.stopped_at)
            resumed_ms = parse_iso_to_epoch_ms(resumed_at_iso)
            self._active_stopped_period.duration_ms = max(0, resumed_ms - stopped_ms)
            self._active_stopped_period = None

    def re_trip_circuit(self, probe_started_at_iso: str, new_cooldown_until_ms: int) -> None:
        """Re-trips breaker to OPEN after failed probe, updating cooldown timer while keeping active stopped period open."""
        self.state = "OPEN"
        self.consecutive_failures += 1
        self.opened_at = probe_started_at_iso
        self.cooldown_until = new_cooldown_until_ms
        # Active stopped period continues without closing

    def finalize_stopped_periods(self, final_record_epoch_ms: int) -> List[dict]:
        """Closes any pending unrecovered stopped period at the end of the log and returns JSON-serializable list."""
        if self._active_stopped_period is not None and self._active_stopped_period.resumed_at is None:
            stopped_ms = parse_iso_to_epoch_ms(self._active_stopped_period.stopped_at)
            self._active_stopped_period.duration_ms = max(0, final_record_epoch_ms - stopped_ms)
        
        return [period.to_dict() for period in self.stopped_intervals]
