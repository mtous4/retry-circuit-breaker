"""
Tests for Stopped Period Tracking and stopped_periods.json Generation (Category H).
Derived strictly from docs/POLICY.md §2.4, §4.2, §7 and docs/SCENARIOS.md.

Target Mutations:
- Wrong duration calculation arithmetic.
- Failing to set resumed_at to null for unclosed periods.
- Overwriting stopped period intervals instead of appending to list.
"""

import pytest
from src.engine import PolicyEngine
from src.config import PolicyConfig
from src.models import CallOutcome


@pytest.fixture
def default_engine(default_config) -> PolicyEngine:
    config = PolicyConfig(**default_config)
    return PolicyEngine(config)


class TestStoppedPeriods:

    def test_complete_stopped_period_calculation(self, default_engine):
        """
        SCEN-H01: An outage cycle from trip to probe recovery produces an exact stopped period record.
        """
        # Trip at 10:00:00.000Z
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        
        # Probe success at 10:00:30.000Z
        default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:30.000Z", status="ok", latency_ms=200))
        
        report = default_engine.get_stopped_periods_report()
        assert "alpha" in report
        assert len(report["alpha"]) == 1
        
        period = report["alpha"][0]
        assert period["stopped_at"] == "2026-09-01T10:00:00.000Z"
        assert period["resumed_at"] == "2026-09-01T10:00:30.000Z"
        assert period["duration_ms"] == 30000

    def test_unrecovered_provider_at_end_of_log(self, default_engine):
        """
        SCEN-H02: A provider that remains OPEN until the end of the log has resumed_at=null and duration relative to last record.
        """
        # Trip at 10:00:00.000Z
        default_engine.process_record(CallOutcome(id="c1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c2", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="c3", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        
        # Another call at 10:00:15.000Z (refused) - this is the last record in the log
        default_engine.process_record(CallOutcome(id="c4", provider="alpha", started_at="2026-09-01T10:00:15.000Z", status="ok", latency_ms=100))
        
        report = default_engine.get_stopped_periods_report()
        assert len(report["alpha"]) == 1
        period = report["alpha"][0]
        assert period["stopped_at"] == "2026-09-01T10:00:00.000Z"
        assert period["resumed_at"] is None
        assert period["duration_ms"] == 15000

    def test_multiple_outage_cycles_on_same_provider(self, default_engine):
        """A provider experiencing two separate outages records two distinct stopped periods in array."""
        # Outage 1: 10:00:00 to 10:00:30 (30s)
        for _ in range(3):
            default_engine.process_record(CallOutcome(id="a", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="p1", provider="alpha", started_at="2026-09-01T10:00:30.000Z", status="ok", latency_ms=200))
        
        # Outage 2: 10:01:00 to 10:01:30 (30s)
        for _ in range(3):
            default_engine.process_record(CallOutcome(id="b", provider="alpha", started_at="2026-09-01T10:01:00.000Z", status="error", latency_ms=100))
        default_engine.process_record(CallOutcome(id="p2", provider="alpha", started_at="2026-09-01T10:01:30.000Z", status="ok", latency_ms=200))
        
        report = default_engine.get_stopped_periods_report()
        assert len(report["alpha"]) == 2
        assert report["alpha"][0]["duration_ms"] == 30000
        assert report["alpha"][1]["duration_ms"] == 30000
