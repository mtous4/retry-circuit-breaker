r"""
Tests for Failure Classification and Latency Boundaries (Category A & B).
Derived strictly from docs/POLICY.md §3.1, §3.2, §5.3 and docs/SCENARIOS.md.

Target Mutations:
- `latency_ms > slow_threshold_ms` mutated to `>=` (kills SCEN-B03 boundary bug).
- `latency_ms > slow_threshold_ms` mutated to `<` or threshold $\pm 1$.
- Inverting boolean `is_failure`.
- Swallowing unknown status strings as successes or crashing.
"""

import pytest
from src.engine import PolicyEngine
from src.config import PolicyConfig
from src.models import CallOutcome


@pytest.fixture
def default_engine(default_config) -> PolicyEngine:
    config = PolicyConfig(**default_config)
    return PolicyEngine(config)


class TestFailureClassification:

    def test_fast_success_is_healthy_attempt(self, default_engine):
        """SCEN-B01: Call with ok and latency well below threshold is healthy."""
        record = CallOutcome(id="c001", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="ok", latency_ms=2500)
        decision = default_engine.process_record(record)
        
        assert decision.id == "c001"
        assert decision.action == "attempt"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "healthy_call_attempt"
        assert default_engine.get_provider_state("alpha").consecutive_failures == 0

    def test_latency_below_slow_threshold_boundary(self, default_engine):
        """SCEN-B02: Latency exactly at slow_threshold_ms - 1 is healthy."""
        record = CallOutcome(id="c002", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="ok", latency_ms=4999)
        decision = default_engine.process_record(record)
        
        assert decision.action == "attempt"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "healthy_call_attempt"
        assert default_engine.get_provider_state("alpha").consecutive_failures == 0

    def test_latency_exact_slow_threshold_boundary(self, default_engine):
        """
        SCEN-B03: Latency exactly equal to slow_threshold_ms (5000ms) MUST be healthy.
        Target Mutation: `latency_ms > slow_threshold_ms` changed to `latency_ms >= slow_threshold_ms`.
        """
        record = CallOutcome(id="c003", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="ok", latency_ms=5000)
        decision = default_engine.process_record(record)
        
        assert decision.action == "attempt"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "healthy_call_attempt"
        assert default_engine.get_provider_state("alpha").consecutive_failures == 0

    def test_latency_above_slow_threshold_boundary(self, default_engine):
        """
        SCEN-B04: Latency exactly equal to slow_threshold_ms + 1 (5001ms) MUST be a degradation failure.
        Target Mutation: `latency_ms > slow_threshold_ms` changed to `<` or threshold modified.
        """
        record = CallOutcome(id="c004", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="ok", latency_ms=5001)
        decision = default_engine.process_record(record)
        
        assert decision.action == "attempt"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "slow_success_degradation"
        assert default_engine.get_provider_state("alpha").consecutive_failures == 1

    def test_explicit_error_status_is_failure(self, default_engine):
        """SCEN-B05: Explicit error status is a failure and increments failure count."""
        record = CallOutcome(id="c005", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=120)
        decision = default_engine.process_record(record)
        
        assert decision.action == "retry"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "transient_error_retry"
        assert default_engine.get_provider_state("alpha").consecutive_failures == 1

    def test_explicit_timeout_status_is_failure(self, default_engine):
        """SCEN-B05: Explicit timeout status is a failure and increments failure count."""
        record = CallOutcome(id="c006", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="timeout", latency_ms=5000)
        decision = default_engine.process_record(record)
        
        assert decision.action == "retry"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "timeout_retry"
        assert default_engine.get_provider_state("alpha").consecutive_failures == 1

    def test_unrecognized_status_is_unretryable_failure(self, default_engine):
        """SCEN-B06: Unrecognized status string is an unretryable failure that increments failure count."""
        record = CallOutcome(id="c007", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="502_bad_gateway", latency_ms=80)
        decision = default_engine.process_record(record)
        
        assert decision.action == "attempt"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "unrecognized_status_failure"
        assert default_engine.get_provider_state("alpha").consecutive_failures == 1

    def test_configurable_slow_threshold(self):
        """Configuration check: changing slow_threshold_ms dynamically changes the boundary."""
        custom_config = PolicyConfig(
            failure_threshold=3,
            cooldown_ms=30000,
            slow_threshold_ms=2000,  # custom 2000ms threshold
            max_retries=1,
            retry_delay_ms=1000
        )
        engine = PolicyEngine(custom_config)
        
        # 2000ms is healthy under custom config
        d1 = engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="ok", latency_ms=2000))
        assert d1.reason == "healthy_call_attempt"
        assert engine.get_provider_state("alpha").consecutive_failures == 0
        
        # 2001ms is failure under custom config
        d2 = engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="ok", latency_ms=2001))
        assert d2.reason == "slow_success_degradation"
        assert engine.get_provider_state("alpha").consecutive_failures == 1
