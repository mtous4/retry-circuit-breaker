"""
Tests for Multi-Provider Isolation and Independent State Machines (Category F).
Derived strictly from docs/POLICY.md §3.5, §6 and docs/SCENARIOS.md.

Target Mutations:
- Shared global failure counter across providers.
- Shared global breaker state.
- Provider state cross-contamination.
"""

import pytest
from src.engine import PolicyEngine
from src.config import PolicyConfig
from src.models import CallOutcome


@pytest.fixture
def default_engine(default_config) -> PolicyEngine:
    config = PolicyConfig(**default_config)
    return PolicyEngine(config)


class TestProviderIsolation:

    def test_provider_a_open_does_not_affect_provider_b(self, default_engine):
        """
        SCEN-F01: When provider alpha trips to OPEN, provider beta remains completely unaffected in CLOSED.
        Target Mutation: Global circuit breaker state machine singleton.
        """
        # Alpha experiences 3 failures -> trips to OPEN
        default_engine.process_record(CallOutcome(id="a1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="a2", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="a3", provider="alpha", started_at="2026-09-01T10:00:02.000Z", status="error", latency_ms=100))
        
        assert default_engine.get_provider_state("alpha").state == "OPEN"
        
        # Beta receives normal healthy call
        db = default_engine.process_record(CallOutcome(id="b1", provider="beta", started_at="2026-09-01T10:00:03.000Z", status="ok", latency_ms=200))
        assert db.action == "attempt"
        assert db.provider_state == "CLOSED"
        assert db.reason == "healthy_call_attempt"
        assert default_engine.get_provider_state("beta").state == "CLOSED"
        assert default_engine.get_provider_state("beta").consecutive_failures == 0
        
        # Next call to Alpha is refused while Beta is unaffected
        da4 = default_engine.process_record(CallOutcome(id="a4", provider="alpha", started_at="2026-09-01T10:00:04.000Z", status="ok", latency_ms=200))
        assert da4.action == "refuse"
        assert da4.provider_state == "OPEN"

    def test_interleaved_multi_provider_failure_counting(self, default_engine):
        """Interleaved calls across 3 providers maintain separate failure counters."""
        # Interleaved trace:
        # A fail (A:1), B ok (B:0), C fail (C:1), A fail (A:2), C fail (C:2), B fail (B:1)
        default_engine.process_record(CallOutcome(id="1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="2", provider="beta", started_at="2026-09-01T10:00:01.000Z", status="ok", latency_ms=100))
        default_engine.process_record(CallOutcome(id="3", provider="gamma", started_at="2026-09-01T10:00:02.000Z", status="timeout", latency_ms=5000))
        default_engine.process_record(CallOutcome(id="4", provider="alpha", started_at="2026-09-01T10:00:03.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="5", provider="gamma", started_at="2026-09-01T10:00:04.000Z", status="timeout", latency_ms=5000))
        default_engine.process_record(CallOutcome(id="6", provider="beta", started_at="2026-09-01T10:00:05.000Z", status="error", latency_ms=100))
        
        assert default_engine.get_provider_state("alpha").consecutive_failures == 2
        assert default_engine.get_provider_state("beta").consecutive_failures == 1
        assert default_engine.get_provider_state("gamma").consecutive_failures == 2
        
        assert default_engine.get_provider_state("alpha").state == "CLOSED"
        assert default_engine.get_provider_state("beta").state == "CLOSED"
        assert default_engine.get_provider_state("gamma").state == "CLOSED"

    def test_independent_recovery_cycles(self, default_engine):
        """Alpha and Beta enter and exit cooldown independently without interference."""
        # Alpha trips at 10:00:00.000Z -> cooldown until 10:00:30.000Z
        for i in range(3):
            default_engine.process_record(CallOutcome(id=f"a{i}", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        
        # Beta trips at 10:00:10.000Z -> cooldown until 10:00:40.000Z
        for i in range(3):
            default_engine.process_record(CallOutcome(id=f"b{i}", provider="beta", started_at="2026-09-01T10:00:10.000Z", status="error", latency_ms=100))
            
        assert default_engine.get_provider_state("alpha").state == "OPEN"
        assert default_engine.get_provider_state("beta").state == "OPEN"
        
        # At 10:00:30.000Z: Alpha probe succeeds -> Alpha becomes CLOSED
        da_probe = default_engine.process_record(CallOutcome(id="ap", provider="alpha", started_at="2026-09-01T10:00:30.000Z", status="ok", latency_ms=200))
        assert da_probe.action == "probe"
        assert da_probe.provider_state == "CLOSED"
        assert default_engine.get_provider_state("alpha").state == "CLOSED"
        
        # At 10:00:30.000Z: Beta is still in cooldown (expires at 10:00:40) -> Beta call refused!
        db_call = default_engine.process_record(CallOutcome(id="bc", provider="beta", started_at="2026-09-01T10:00:30.000Z", status="ok", latency_ms=200))
        assert db_call.action == "refuse"
        assert db_call.provider_state == "OPEN"
        assert default_engine.get_provider_state("beta").state == "OPEN"
