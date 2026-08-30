"""
Core Policy Engine executing retrospective call outcome evaluations.
Derived strictly from docs/POLICY.md §6, §7.
"""

from pathlib import Path
import json
from typing import Dict, List, Union
from src.config import PolicyConfig
from src.models import CallOutcome, DecisionRecord, parse_iso_to_epoch_ms
from src.state_machine import ProviderFSM


class PolicyEngine:
    """Deterministic policy engine evaluating historical API call logs against circuit breaker and retry rules."""

    def __init__(self, config: PolicyConfig) -> None:
        self.config: PolicyConfig = config
        self._providers: Dict[str, ProviderFSM] = {}
        self._max_observed_timestamp: int = 0
        self._final_record_timestamp_ms: int = 0

    def get_provider_state(self, provider_id: str) -> ProviderFSM:
        """Returns the FSM for a provider, initializing in CLOSED state if not yet seen."""
        if provider_id not in self._providers:
            self._providers[provider_id] = ProviderFSM(provider_id=provider_id)
        return self._providers[provider_id]

    def process_record(self, record: CallOutcome) -> DecisionRecord:
        """
        Evaluates a single CallOutcome record and emits exactly one DecisionRecord
        strictly following the 7-step algorithm in docs/POLICY.md §7.
        """
        # Step 1 & 2: Parse timestamp and maintain monotonic time tracking
        record_time_ms = parse_iso_to_epoch_ms(record.started_at)
        self._max_observed_timestamp = max(self._max_observed_timestamp, record_time_ms)
        self._final_record_timestamp_ms = max(self._final_record_timestamp_ms, record_time_ms)
        
        # Step 3: Lookup or initialize provider FSM
        provider = self.get_provider_state(record.provider)

        # Step 4: Handle OPEN state
        if provider.state == "OPEN":
            if self._max_observed_timestamp < provider.cooldown_until:
                # Cooldown still active: refuse call upfront
                return DecisionRecord(
                    id=record.id,
                    action="refuse",
                    provider_state="OPEN",
                    reason="circuit_open_refusal",
                )
            else:
                # Cooldown expired: evaluate record as the single canary recovery probe
                is_probe_success = (
                    record.status == "ok"
                    and record.latency_ms <= self.config.slow_threshold_ms
                )
                if is_probe_success:
                    provider.recover_circuit(resumed_at_iso=record.started_at)
                    return DecisionRecord(
                        id=record.id,
                        action="probe",
                        provider_state="CLOSED",
                        reason="probe_success_recovery",
                    )
                else:
                    new_cooldown_until = record_time_ms + self.config.cooldown_ms
                    provider.re_trip_circuit(
                        probe_started_at_iso=record.started_at,
                        new_cooldown_until_ms=new_cooldown_until,
                    )
                    return DecisionRecord(
                        id=record.id,
                        action="probe",
                        provider_state="OPEN",
                        reason="probe_failure_reopen",
                    )

        # Step 5: Handle CLOSED state (Normal traffic evaluation)
        is_success = (
            record.status == "ok"
            and record.latency_ms <= self.config.slow_threshold_ms
        )

        if is_success:
            provider.consecutive_failures = 0
            return DecisionRecord(
                id=record.id,
                action="attempt",
                provider_state="CLOSED",
                reason="healthy_call_attempt",
            )
        else:
            # Provider Failure
            provider.consecutive_failures += 1
            tripped = provider.consecutive_failures >= self.config.failure_threshold
            
            if tripped:
                cooldown_until = record_time_ms + self.config.cooldown_ms
                provider.open_circuit(
                    opened_at_iso=record.started_at,
                    cooldown_until_ms=cooldown_until,
                )
            
            resulting_state = provider.state

            # Determine Action & Reason Code
            if record.status == "ok":
                # Slow success degradation
                return DecisionRecord(
                    id=record.id,
                    action="attempt",
                    provider_state=resulting_state,
                    reason="slow_success_degradation",
                )
            elif record.status not in ["error", "timeout"]:
                # Unrecognized status failure
                return DecisionRecord(
                    id=record.id,
                    action="attempt",
                    provider_state=resulting_state,
                    reason="unrecognized_status_failure",
                )
            else:
                # Transient error or timeout
                if tripped or self.config.max_retries == 0:
                    return DecisionRecord(
                        id=record.id,
                        action="give_up",
                        provider_state=resulting_state,
                        reason="max_retries_exceeded",
                    )
                else:
                    reason_code = "transient_error_retry" if record.status == "error" else "timeout_retry"
                    return DecisionRecord(
                        id=record.id,
                        action="retry",
                        provider_state="CLOSED",
                        reason=reason_code,
                    )

    def process_file(self, outcomes_path: Union[Path, str]) -> List[DecisionRecord]:
        """Reads and evaluates an entire outcomes.jsonl file line by line."""
        path = Path(outcomes_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        
        decisions: List[DecisionRecord] = []
        with open(path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    record = CallOutcome.from_dict(data)
                except Exception as e:
                    raise ValueError(f"Malformed input on line {line_idx} of {path}: {e}") from e
                
                decision = self.process_record(record)
                decisions.append(decision)
        
        return decisions

    def get_stopped_periods_report(self) -> Dict[str, List[dict]]:
        """Generates the full stopped periods dictionary across all tracked providers."""
        report: Dict[str, List[dict]] = {}
        for provider_id, provider_fsm in sorted(self._providers.items()):
            intervals = provider_fsm.finalize_stopped_periods(self._final_record_timestamp_ms)
            if intervals:
                report[provider_id] = intervals
        return report
