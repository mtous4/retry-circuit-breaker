"""
Tests for Retrospective Retry Semantics and Budget Boundaries (Category E).
Derived strictly from docs/POLICY.md §4.1, §5.1, §6 and docs/SCENARIOS.md.

Target Mutations:
- Emitting `retry` action when provider is `OPEN`.
- Emitting `retry` action on slow `ok` or unrecognized status.
- Ignoring `max_retries = 0` configuration.
- Wrong reason mapping between error (`transient_error_retry`) and timeout (`timeout_retry`).
"""

import pytest
from src.engine import PolicyEngine
from src.config import PolicyConfig
from src.models import CallOutcome


@pytest.fixture
def default_engine(default_config) -> PolicyEngine:
    config = PolicyConfig(**default_config)
    return PolicyEngine(config)


class TestRetryPolicy:

    def test_transient_error_retried_on_closed_provider(self, default_engine):
        """SCEN-E01: Error on healthy provider emits action='retry' and reason='transient_error_retry'."""
        record = CallOutcome(id="c040", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100)
        decision = default_engine.process_record(record)
        
        assert decision.action == "retry"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "transient_error_retry"

    def test_transient_timeout_retried_on_closed_provider(self, default_engine):
        """SCEN-E02: Timeout on healthy provider emits action='retry' and reason='timeout_retry'."""
        record = CallOutcome(id="c041", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="timeout", latency_ms=5000)
        decision = default_engine.process_record(record)
        
        assert decision.action == "retry"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "timeout_retry"

    def test_retries_disabled_emits_give_up(self):
        """
        SCEN-E03: When max_retries is 0, transient failure emits action='give_up' and reason='max_retries_exceeded'.
        Target Mutation: `max_retries >= 1` condition removed or defaulting to retry.
        """
        config = PolicyConfig(
            failure_threshold=3,
            cooldown_ms=30000,
            slow_threshold_ms=5000,
            max_retries=0,  # 0 retries permitted
            retry_delay_ms=1000
        )
        engine = PolicyEngine(config)
        
        record = CallOutcome(id="c042", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100)
        decision = engine.process_record(record)
        
        assert decision.action == "give_up"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "max_retries_exceeded"

    def test_failure_tripping_breaker_emits_give_up(self, default_engine):
        """
        SCEN-E04: 3rd failure trips breaker to OPEN and emits action='give_up' (retrying open breaker prohibited).
        Target Mutation: Emitting `retry` action when resulting state is `OPEN`.
        """
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="error", latency_ms=100))
        
        # 3rd failure trips circuit
        d3 = default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:02.000Z", status="error", latency_ms=100))
        
        assert d3.action == "give_up"
        assert d3.provider_state == "OPEN"
        assert d3.reason == "max_retries_exceeded"

    def test_slow_success_never_retried(self, default_engine):
        """
        SCEN-E05: A slow success delivers response as 'attempt', NEVER 'retry'.
        Target Mutation: Retrying on all failures regardless of status ok.
        """
        record = CallOutcome(id="c044", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="ok", latency_ms=6500)
        decision = default_engine.process_record(record)
        
        assert decision.action == "attempt"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "slow_success_degradation"

    def test_unknown_status_never_retried(self, default_engine):
        """SCEN-B06: An unknown status delivers action='attempt', NEVER 'retry'."""
        record = CallOutcome(id="c045", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="custom_failure_code", latency_ms=100)
        decision = default_engine.process_record(record)
        
        assert decision.action == "attempt"
        assert decision.provider_state == "CLOSED"
        assert decision.reason == "unrecognized_status_failure"
