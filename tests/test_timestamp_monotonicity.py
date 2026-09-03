"""
Tests for Timestamp Mechanics and Monotonic Time Tracking (Category G).
Derived strictly from docs/POLICY.md §4.3, §6, §7 and docs/SCENARIOS.md.

Target Mutations:
- Regressing `current_time` when an earlier timestamp arrives.
- Allowing premature cooldown expiry due to out-of-order timestamps.
- Crashing on simultaneous/equal timestamps.
"""

import pytest
from src.engine import PolicyEngine
from src.config import PolicyConfig
from src.models import CallOutcome


@pytest.fixture
def default_engine(default_config) -> PolicyEngine:
    config = PolicyConfig(**default_config)
    return PolicyEngine(config)


class TestTimestampMonotonicity:

    def test_equal_timestamps_processed_sequentially(self, default_engine):
        """SCEN-G01: Multiple records sharing identical timestamps evaluate in input arrival order."""
        records = [
            CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100),
            CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100),
            CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100),
        ]
        
        d1 = default_engine.process_record(records[0])
        d2 = default_engine.process_record(records[1])
        d3 = default_engine.process_record(records[2])
        
        assert d1.action == "retry"
        assert d1.provider_state == "CLOSED"
        assert d2.action == "retry"
        assert d2.provider_state == "CLOSED"
        assert d3.action == "give_up"
        assert d3.provider_state == "OPEN"

    def test_out_of_order_timestamp_maintains_monotonic_time(self, default_engine):
        """
        SCEN-G02: An out-of-order timestamp does NOT regress global current_time.
        Target Mutation: `current_time = record.started_at` without `max()`.
        """
        # Record 1 at 10:00:10 -> trips breaker to OPEN (cooldown until 10:00:40)
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:08.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:09.000Z", status="error", latency_ms=100))
        d3 = default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:10.000Z", status="error", latency_ms=100))
        assert d3.provider_state == "OPEN"
        
        # Record 4 arrives with out-of-order timestamp (10:00:05.000Z < 10:00:10.000Z)
        d4 = default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:05.000Z", status="ok", latency_ms=100))
        
        # Monotonic time is still at least 10:00:10, which is < 10:00:40 cooldown -> call is refused!
        assert d4.action == "refuse"
        assert d4.provider_state == "OPEN"
        assert d4.reason == "circuit_open_refusal"

    def test_timestamp_advancing_forward_after_out_of_order(self, default_engine):
        """After an out-of-order record, future forward timestamps properly expire cooldown."""
        # Trip at 10:00:10 (cooldown until 10:00:40)
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:08.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:09.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:10.000Z", status="error", latency_ms=100))
        
        # Out-of-order record at 10:00:05 (refused)
        default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:05.000Z", status="ok", latency_ms=100))
        
        # Next record arrives at 10:00:40.000Z (cooldown reached!) -> probe admitted
        d5 = default_engine.process_record(CallOutcome(id="c5", provider="alpha", started_at="2026-09-01T10:00:40.000Z", status="ok", latency_ms=200))
        assert d5.action == "probe"
        assert d5.provider_state == "CLOSED"
        assert d5.reason == "probe_success_recovery"

    def test_monotonic_time_advances_probe_cooldown_even_with_out_of_order_calls(self, default_engine):
        """
        SCEN-G02/G03: Monotonic time tracking ensures that once time passes cooldown_until,
        subsequent out-of-order records with earlier timestamps evaluate against current_time >= cooldown_until.
        Target Mutation: `self._max_observed_timestamp = record_time_ms` (time regression).
        """
        # Alpha trips at 10:00:00.000Z -> cooldown until 10:00:30.000Z
        for i in range(3):
            default_engine.process_record(CallOutcome(id=f"c{i}", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        assert default_engine.get_provider_state("alpha").state == "OPEN"
        
        # Traffic on provider Beta advances global time to 10:00:35.000Z
        default_engine.process_record(CallOutcome(id="b1", provider="beta", started_at="2026-09-01T10:00:35.000Z", status="ok", latency_ms=100))
        
        # Out-of-order record arrives for Alpha with raw timestamp 10:00:15.000Z (earlier than cooldown_until 10:00:30)
        # But because global monotonic time is 10:00:35 >= 10:00:30, cooldown has expired -> evaluated as probe!
        d_probe = default_engine.process_record(CallOutcome(id="p_ooo", provider="alpha", started_at="2026-09-01T10:00:15.000Z", status="ok", latency_ms=200))
        assert d_probe.action == "probe"
        assert d_probe.provider_state == "CLOSED"
        assert d_probe.reason == "probe_success_recovery"

