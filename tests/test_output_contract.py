"""
Tests for Output Schema Contract, Controlled Vocabularies, and Determinism (Category I & J).
Derived strictly from docs/POLICY.md §2.1, §2.3, §2.4, §5.1, §5.2, §5.3, §8 and docs/SCENARIOS.md.

Target Mutations:
- Reordering output lines.
- Omitting required output fields.
- Using unapproved action, provider_state, or reason strings.
- Non-deterministic output generation across runs.
"""

from pathlib import Path
import json
import pytest
from src.engine import PolicyEngine
from src.config import PolicyConfig
from src.models import CallOutcome

VALID_ACTIONS = {"attempt", "retry", "give_up", "refuse", "probe"}
VALID_STATES = {"CLOSED", "OPEN", "HALF_OPEN"}
VALID_REASONS = {
    "healthy_call_attempt",
    "slow_success_degradation",
    "transient_error_retry",
    "timeout_retry",
    "max_retries_exceeded",
    "circuit_open_refusal",
    "probe_call_attempt",
    "probe_success_recovery",
    "probe_failure_reopen",
    "unrecognized_status_failure",
}


@pytest.fixture
def default_engine(default_config) -> PolicyEngine:
    config = PolicyConfig(**default_config)
    return PolicyEngine(config)


class TestOutputContract:

    def test_strict_one_to_one_cardinality_and_order(self, default_engine):
        """
        SCEN-I01: Exactly one decision record is emitted per input record, strictly preserving input arrival order.
        """
        records = [
            CallOutcome(id="c10", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="ok", latency_ms=100),
            CallOutcome(id="c20", provider="beta", started_at="2026-09-01T10:00:01.000Z", status="error", latency_ms=100),
            CallOutcome(id="c30", provider="alpha", started_at="2026-09-01T10:00:02.000Z", status="ok", latency_ms=100),
            CallOutcome(id="c40", provider="beta", started_at="2026-09-01T10:00:03.000Z", status="ok", latency_ms=100),
        ]
        
        decisions = [default_engine.process_record(r) for r in records]
        
        assert len(decisions) == 4
        assert [d.id for d in decisions] == ["c10", "c20", "c30", "c40"]

    def test_all_emitted_fields_conform_to_controlled_vocabulary(self, default_engine):
        """Verify all output fields strictly adhere to the controlled vocabularies defined in POLICY.md."""
        records = [
            CallOutcome(id="1", provider="alpha", started_at="2026-09-01T10:00:00.000Z", status="ok", latency_ms=100),
            CallOutcome(id="2", provider="alpha", started_at="2026-09-01T10:00:01.000Z", status="ok", latency_ms=5001),
            CallOutcome(id="3", provider="alpha", started_at="2026-09-01T10:00:02.000Z", status="error", latency_ms=100),
            CallOutcome(id="4", provider="alpha", started_at="2026-09-01T10:00:03.000Z", status="timeout", latency_ms=5000),
            CallOutcome(id="5", provider="alpha", started_at="2026-09-01T10:00:10.000Z", status="ok", latency_ms=100),
            CallOutcome(id="6", provider="alpha", started_at="2026-09-01T10:00:33.000Z", status="ok", latency_ms=200),
        ]
        
        for r in records:
            d = default_engine.process_record(r)
            assert d.action in VALID_ACTIONS, f"Invalid action: {d.action}"
            assert d.provider_state in VALID_STATES, f"Invalid provider_state: {d.provider_state}"
            assert d.reason in VALID_REASONS, f"Invalid reason: {d.reason}"

    def test_pure_determinism_across_multiple_runs(self, default_config):
        """
        BRIEF Hard Rule: Same input + same config MUST produce byte-for-byte identical decisions across 10 repeated runs.
        """
        raw_records = [
            {"id": f"c{i}", "provider": "alpha" if i % 2 == 0 else "beta", "started_at": f"2026-09-01T10:00:0{i}.000Z", "status": "error" if i == 2 else "ok", "latency_ms": 100 + i * 50}
            for i in range(8)
        ]
        
        baseline_results = None
        for run_idx in range(10):
            engine = PolicyEngine(PolicyConfig(**default_config))
            run_decisions = [
                engine.process_record(CallOutcome(**r)).to_dict()
                for r in raw_records
            ]
            
            if baseline_results is None:
                baseline_results = run_decisions
            else:
                assert run_decisions == baseline_results, f"Non-deterministic divergence on run {run_idx}"

    def test_process_file_preserves_input_line_order_exactly(self, default_config, make_outcomes_file):
        """
        BRIEF Hard Rule: engine.process_file MUST evaluate records in exact input order and return decisions in identical order.
        Target Mutation: Reversing or shuffling decisions list inside process_file.
        """
        records = [
            {"id": f"rec_{i:03d}", "provider": "alpha", "started_at": f"2026-09-01T10:00:0{i}.000Z", "status": "ok", "latency_ms": 100}
            for i in range(6)
        ]
        outcomes_path = make_outcomes_file(records, "ordered_outcomes.jsonl")
        
        engine = PolicyEngine(PolicyConfig(**default_config))
        decisions = engine.process_file(outcomes_path)
        
        expected_ids = [r["id"] for r in records]
        actual_ids = [d.id for d in decisions]
        assert actual_ids == expected_ids

