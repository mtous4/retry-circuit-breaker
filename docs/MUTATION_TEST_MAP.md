# Mutation Testing Verification Map 



## 1. Overview & Mutation Testing Philosophy
Per the **Project 3 BRIEF**, the test suite is evaluated by introducing subtle synthetic defects (operator flips, off-by-one constants, inverted booleans, removed negations) into the codebase and running the test suite. 

**Standard**: Every mutation below MUST be caught and killed by at least one dedicated boundary test. Zero survivors are permitted.

---

## 2. Mutation-to-Test Traceability Matrix

| Mutation ID | Policy Rule | Formal Condition / Operator | Injected Mutation Risk | Assigned Killing Test Case(s) | Expected Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **MUT-01** | **Slow Latency Boundary** | `latency_ms > slow_threshold_ms` | Invert operator to `latency_ms >= slow_threshold_ms` (treating exact threshold as failure) | `test_failure_classification.py::test_latency_exact_slow_threshold_boundary` | **KILLED** (Asserts exact $5000\text{ms}$ is healthy) |
| **MUT-02** | **Slow Latency Threshold** | `latency_ms > slow_threshold_ms` | Invert operator to `latency_ms < slow_threshold_ms` or threshold $+1$ | `test_failure_classification.py::test_latency_above_slow_threshold_boundary` | **KILLED** (Asserts $5001\text{ms}$ is degradation failure) |
| **MUT-03** | **Failure Tripping Operator** | `consecutive_failures >= failure_threshold` | Change `>=` to `>` (requiring $N+1$ failures to trip) | `test_failure_counter.py::test_failure_threshold_exact_boundary_trips_to_open` | **KILLED** (Asserts 3rd failure trips to `OPEN`) |
| **MUT-04** | **Premature Tripping** | `consecutive_failures >= failure_threshold` | Change `>= failure_threshold` to `>= failure_threshold - 1` (tripping early) | `test_failure_counter.py::test_failure_threshold_minus_one_remains_closed` | **KILLED** (Asserts 2 failures remain `CLOSED`) |
| **MUT-05** | **Failure Counter Reset** | `consecutive_failures = 0` on fast `ok` | Omit reset or decrement (`failures -= 1`) instead of setting to 0 | `test_failure_counter.py::test_intervening_success_resets_counter_to_zero` | **KILLED** (Asserts counter resets from 2 to 0 on single success) |
| **MUT-06** | **Refused Call Invariant** | Refused calls do NOT increment failure counter | Increment counter on refused calls (`failures += 1`) | `test_failure_counter.py::test_refused_call_does_not_increment_counter` | **KILLED** (Asserts counter remains 3 after refused call) |
| **MUT-07** | **Cooldown Pre-Expiry** | `current_time < cooldown_until` | Change `<` to `<=` (refusing calls at exact expiry) | `test_circuit_breaker.py::test_cooldown_minus_one_ms_is_refused` | **KILLED** (Asserts $T_{\text{cool}}-1\text{ms}$ is refused) |
| **MUT-08** | **Cooldown Exact Expiry** | `current_time >= cooldown_until` | Change `>=` to `>` (denying probe at exact millisecond boundary) | `test_circuit_breaker.py::test_cooldown_exact_expiry_admits_probe` | **KILLED** (Asserts exact millisecond admits probe) |
| **MUT-09** | **Probe Recovery State** | `state = "CLOSED"` and `failures = 0` on probe success | Leave state in `HALF_OPEN` or forget to reset failure counter | `test_circuit_breaker.py::test_cooldown_exact_expiry_admits_probe` | **KILLED** (Asserts `provider_state == "CLOSED"` and `failures == 0`) |
| **MUT-10** | **Probe Failure Re-Trip** | `state = "OPEN"` and start new cooldown from probe timestamp | Reset cooldown to old `opened_at` or leave state in `CLOSED` | `test_circuit_breaker.py::test_probe_failure_re_trips_breaker` | **KILLED** (Asserts provider is `OPEN` and call at $+15\text{s}$ is refused) |
| **MUT-11** | **Retry on Open Breaker** | Prohibit retries when provider is `OPEN` | Emit `action: "retry"` instead of `action: "give_up"` when 3rd failure trips breaker | `test_retry_policy.py::test_failure_tripping_breaker_emits_give_up` | **KILLED** (Asserts 3rd failure emits `give_up` with reason `max_retries_exceeded`) |
| **MUT-12** | **Retries Disabled Boundary** | `max_retries == 0` | Emit `action: "retry"` regardless of `max_retries = 0` setting | `test_retry_policy.py::test_retries_disabled_emits_give_up` | **KILLED** (Asserts error emits `give_up` when `max_retries = 0`) |
| **MUT-13** | **Slow Success Non-Retry** | Never retry `ok` status | Emit `action: "retry"` for slow `ok` calls | `test_retry_policy.py::test_slow_success_never_retried` | **KILLED** (Asserts slow `ok` emits `attempt`) |
| **MUT-14** | **Unknown Status Non-Retry** | Never retry unknown status strings | Emit `action: "retry"` for unknown status strings | `test_retry_policy.py::test_unknown_status_never_retried` | **KILLED** (Asserts unknown status emits `attempt`) |
| **MUT-15** | **Provider Isolation** | Isolated FSM per provider name | Global state singleton / shared failure counter across all providers | `test_provider_isolation.py::test_provider_a_open_does_not_affect_provider_b` | **KILLED** (Asserts Beta is `CLOSED` when Alpha is `OPEN`) |
| **MUT-16** | **Monotonic Time Regression** | `current_time = max(max_seen, record.started_at)` | `current_time = record.started_at` without `max()` | `test_timestamp_monotonicity.py::test_out_of_order_timestamp_maintains_monotonic_time` | **KILLED** (Asserts out-of-order record cannot regress time) |
| **MUT-17** | **Stopped Period Tracking** | Record exact `duration_ms = resumed_at - stopped_at` | Invert subtraction or hardcode duration | `test_stopped_periods.py::test_complete_stopped_period_calculation` | **KILLED** (Asserts exact $30000\text{ms}$ duration) |
| **MUT-18** | **Unclosed Stopped Period** | `resumed_at = null` for providers open at end of log | Omit open period or set fake resumed timestamp | `test_stopped_periods.py::test_unrecovered_provider_at_end_of_log` | **KILLED** (Asserts `resumed_at is None` and duration measured to last record) |
| **MUT-19** | **Output Line Preservation** | Emit 1 decision per input in exact input order | Reorder lines or omit records | `test_output_contract.py::test_strict_one_to_one_cardinality_and_order` | **KILLED** (Asserts exact input ID order `["c10", "c20", "c30", "c40"]`) |
| **MUT-20** | **Controlled Vocabularies** | Restrict output to approved vocabulary strings | Emit arbitrary strings (e.g. `"allow"`, `"pass"`, `"open"`) | `test_output_contract.py::test_all_emitted_fields_conform_to_controlled_vocabulary` | **KILLED** (Validates all strings against strict sets) |
| **MUT-21** | **Determinism Invariant** | Byte-for-byte identical output on every run | Introduce unseeded random jitter or non-deterministic hash ordering | `test_output_contract.py::test_pure_determinism_across_multiple_runs` | **KILLED** (Asserts 10 runs produce identical decision outputs) |
| **MUT-22** | **Configuration Parameter Binding** | Read thresholds from configuration object | Hardcode threshold constants in code | `test_failure_classification.py::test_configurable_slow_threshold`<br>`test_failure_counter.py::test_configurable_failure_threshold`<br>`test_circuit_breaker.py::test_configurable_cooldown_duration` | **KILLED** (Proves dynamic behavior on altered configs) |
