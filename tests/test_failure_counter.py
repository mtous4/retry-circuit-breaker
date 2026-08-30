"""
Tests for Failure Counter and Threshold Boundaries (Category C).
Derived strictly from docs/POLICY.md §3.3, §3.4, §6 and docs/SCENARIOS.md.

Target Mutations:
- `failures >= failure_threshold` mutated to `failures > failure_threshold` (off-by-one bug).
- `failures >= failure_threshold` mutated to `failures >= failure_threshold - 1` (premature tripping).
- `failures` reset logic omitted on success (`failures = failures` instead of `failures = 0`).
- Incrementing failure counter on refused calls.
"""

import pytest
from src.engine import PolicyEngine
from src.config import PolicyConfig
from src.models import CallOutcome


@pytest.fixture
def default_engine(default_config) -> PolicyEngine:
    config = PolicyConfig(**default_config)
    return PolicyEngine(config)


class TestFailureCounter:

    def test_single_failure_increments_counter(self, default_engine):
        """SCEN-A03: First failure increments failure counter to 1."""
        record = CallOutcome(id="c020", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100)
        default_engine.process_record(record)
        
        provider = default_engine.get_provider_state("alpha")
        assert provider.consecutive_failures == 1
        assert provider.state == "CLOSED"

    def test_intervening_success_resets_counter_to_zero(self, default_engine):
        """
        SCEN-C03: Fast success resets consecutive failure counter from 2 back to 0.
        Target Mutation: Decrementing counter (`failures -= 1`) instead of resetting to 0.
        """
        default_engine.process_record(CallOutcome(id="c021", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c022", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="error", latency_ms=100))
        assert default_engine.get_provider_state("alpha").consecutive_failures == 2
        
        # Fast success arrives
        d3 = default_engine.process_record(CallOutcome(id="c023", provider="alpha", started_at="2026-09-01T10:00:02.000Z", status="ok", latency_ms=200))
        assert d3.action == "attempt"
        assert d3.provider_state == "CLOSED"
        assert d3.reason == "healthy_call_attempt"
        
        provider = default_engine.get_provider_state("alpha")
        assert provider.consecutive_failures == 0
        assert provider.state == "CLOSED"

    def test_failure_threshold_minus_one_remains_closed(self, default_engine):
        """
        SCEN-C01: Failure count at exactly threshold - 1 (2 failures when threshold is 3) MUST remain CLOSED.
        Target Mutation: `failures >= failure_threshold - 1`.
        """
        default_engine.process_record(CallOutcome(id="c024", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        d2 = default_engine.process_record(CallOutcome(id="c025", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="timeout", latency_ms=5000))
        
        assert d2.action == "retry"
        assert d2.provider_state == "CLOSED"
        assert default_engine.get_provider_state("alpha").consecutive_failures == 2
        assert default_engine.get_provider_state("alpha").state == "CLOSED"

    def test_failure_threshold_exact_boundary_trips_to_open(self, default_engine):
        """
        SCEN-C02: Failure count at exactly threshold (3 failures) MUST trip state to OPEN.
        Target Mutation: `failures >= failure_threshold` mutated to `failures > failure_threshold`.
        """
        default_engine.process_record(CallOutcome(id="c026", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c027", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="error", latency_ms=100))
        
        # 3rd failure trips breaker
        d3 = default_engine.process_record(CallOutcome(id="c028", provider="alpha", started_at="2026-09-01T10:00:02.000Z", status="timeout", latency_ms=5000))
        
        assert d3.action == "give_up"
        assert d3.provider_state == "OPEN"
        assert d3.reason == "max_retries_exceeded"
        
        provider = default_engine.get_provider_state("alpha")
        assert provider.consecutive_failures == 3
        assert provider.state == "OPEN"
        assert provider.opened_at == "2026-09-01T10:00:02.000Z"

    def test_refused_call_does_not_increment_counter(self, default_engine):
        """
        SCEN-D01: A call refused while OPEN must NOT increment consecutive_failures.
        Target Mutation: Incrementing failure counter on all processed calls unconditionally.
        """
        # Trip to OPEN
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:02.000Z", status="error", latency_ms=100))
        assert default_engine.get_provider_state("alpha").consecutive_failures == 3
        
        # Call during cooldown is refused
        d4 = default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:10.000Z", status="ok", latency_ms=100))
        assert d4.action == "refuse"
        assert d4.provider_state == "OPEN"
        assert default_engine.get_provider_state("alpha").consecutive_failures == 3  # unchanged!

    def test_configurable_failure_threshold(self):
        """Configuration check: changing failure_threshold to 2 trips on 2nd failure."""
        custom_config = PolicyConfig(
            failure_threshold=2,  # trips on 2 failures
            cooldown_ms=30000,
            slow_threshold_ms=5000,
            max_retries=1,
            retry_delay_ms=1000
        )
        engine = PolicyEngine(custom_config)
        
        d1 = engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        assert d1.provider_state == "CLOSED"
        
        d2 = engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="error", latency_ms=100))
        assert d2.provider_state == "OPEN"
        assert engine.get_provider_state("alpha").state == "OPEN"
