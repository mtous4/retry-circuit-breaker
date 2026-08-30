"""
Tests for Circuit Breaker Lifecycle and Cooldown Boundaries (Category D).
Derived strictly from docs/POLICY.md §3.7, §4.2, §5.2, §6 and docs/SCENARIOS.md.

Target Mutations:
- `current_time >= cooldown_until` mutated to `>` (probe denied at exact boundary).
- `current_time >= cooldown_until` mutated to `<` or inverted boolean.
- Resetting cooldown to initial `opened_at` on probe failure instead of probe call timestamp.
- Failing to reset failure count on probe success.
"""

import pytest
from src.engine import PolicyEngine
from src.config import PolicyConfig
from src.models import CallOutcome


@pytest.fixture
def default_engine(default_config) -> PolicyEngine:
    config = PolicyConfig(**default_config)
    return PolicyEngine(config)


class TestCircuitBreaker:

    def test_call_refused_during_cooldown(self, default_engine):
        """SCEN-D01: Call arriving halfway through cooldown period is refused."""
        # Trip breaker at 10:00:02
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:02.000Z", status="error", latency_ms=100))
        
        # Call at 10:00:15 (cooldown is 30s -> expires at 10:00:32)
        d4 = default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:15.000Z", status="ok", latency_ms=100))
        
        assert d4.action == "refuse"
        assert d4.provider_state == "OPEN"
        assert d4.reason == "circuit_open_refusal"

    def test_cooldown_minus_one_ms_is_refused(self, default_engine):
        """
        SCEN-D02: Call arriving at exactly opened_at + cooldown_ms - 1ms MUST be refused.
        Target Mutation: `current_time < cooldown_until` mutated to `<=`.
        """
        # Trip at 10:00:00.000Z -> cooldown until 10:00:30.000Z
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        
        # Call at 10:00:29.999Z (1ms before expiry)
        d4 = default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:29.999Z", status="ok", latency_ms=100))
        assert d4.action == "refuse"
        assert d4.provider_state == "OPEN"
        assert d4.reason == "circuit_open_refusal"

    def test_cooldown_exact_expiry_admits_probe(self, default_engine):
        """
        SCEN-D03: Call arriving at exactly opened_at + cooldown_ms MUST be evaluated as probe.
        Target Mutation: `current_time >= cooldown_until` mutated to `current_time > cooldown_until`.
        """
        # Trip at 10:00:00.000Z -> cooldown until 10:00:30.000Z
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        
        # Call at 10:00:30.000Z (exact expiry)
        d4 = default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:30.000Z", status="ok", latency_ms=200))
        
        assert d4.action == "probe"
        assert d4.provider_state == "CLOSED"
        assert d4.reason == "probe_success_recovery"
        
        provider = default_engine.get_provider_state("alpha")
        assert provider.state == "CLOSED"
        assert provider.consecutive_failures == 0

    def test_probe_failure_re_trips_breaker(self, default_engine):
        """
        SCEN-D04: A failed probe re-trips state to OPEN and starts a new cooldown window.
        Target Mutation: Failing to start a new cooldown timer or keeping provider in CLOSED/HALF_OPEN.
        """
        # Trip at 10:00:00.000Z -> cooldown until 10:00:30.000Z
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        
        # Probe call at 10:00:30.000Z times out
        d4 = default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:30.000Z", status="timeout", latency_ms=5000))
        
        assert d4.action == "probe"
        assert d4.provider_state == "OPEN"
        assert d4.reason == "probe_failure_reopen"
        
        provider = default_engine.get_provider_state("alpha")
        assert provider.state == "OPEN"
        assert provider.consecutive_failures == 4
        
        # Subsequent call at 10:00:45.000Z (during 2nd cooldown: expires 10:01:00.000Z) is refused
        d5 = default_engine.process_record(CallOutcome(id="c5", provider="alpha", started_at="2026-09-01T10:00:45.000Z", status="ok", latency_ms=100))
        assert d5.action == "refuse"
        assert d5.provider_state == "OPEN"
        assert d5.reason == "circuit_open_refusal"

    def test_slow_success_probe_fails_probe(self, default_engine):
        """Probe call returning status ok but exceeding slow_threshold_ms is a probe failure."""
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        
        # Probe call at 10:00:30.000Z has latency 5001ms (> 5000ms threshold)
        d4 = default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:30.000Z", status="ok", latency_ms=5001))
        
        assert d4.action == "probe"
        assert d4.provider_state == "OPEN"
        assert d4.reason == "probe_failure_reopen"

    def test_configurable_cooldown_duration(self):
        """Configuration check: changing cooldown_ms to 10000ms (10s) expires probe at +10s."""
        custom_config = PolicyConfig(
            failure_threshold=3,
            cooldown_ms=10000,  # 10s cooldown
            slow_threshold_ms=5000,
            max_retries=1,
            retry_delay_ms=1000
        )
        engine = PolicyEngine(custom_config)
        
        engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        
        # At 10:00:09.999Z -> refused
        d4 = engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:09.999Z", status="ok", latency_ms=100))
        assert d4.action == "refuse"
        
        # At 10:00:10.000Z -> probe admitted
        d5 = engine.process_record(CallOutcome(id="c5", provider="alpha", started_at="2026-09-01T10:00:10.000Z", status="ok", latency_ms=200))
        assert d5.action == "probe"
        assert d5.provider_state == "CLOSED"
