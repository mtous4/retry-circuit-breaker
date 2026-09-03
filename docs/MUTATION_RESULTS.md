# Mutation Testing Results & Hardening Ledger 

**Status**: `MUTATION AUDIT COMPLETE — 100% KILL RATE`  
**Execution Date**: 2026-09-03  
**Framework**: `pytest 9.1.1` on `Python 3.12.4`

---

## 1. Summary Metrics

- **Baseline Tests**: 43 passed (0 failures, 0 skipped, 0 errors)
- **Total Policy Mutations Evaluated**: 25
- **Mutations Killed**: 25
- **Mutations Survived**: 0
- **Final Mutation Kill Rate**: **100.0%**

---

## 2. Comprehensive Mutation Ledger

| Mutation ID | Location | Mutation Injected | POLICY Rule | Killing Test | Result | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **MUT-01** | `src/engine.py:47` | `<= slow_threshold_ms` $\rightarrow$ `<` | `POLICY.md` §3.1 | `test_circuit_breaker.py::test_probe_exact_slow_threshold_recovers` | **KILLED** | Caught exact $5000\text{ms}$ probe latency boundary |
| **MUT-02** | `src/engine.py:47` | `<= slow_threshold_ms` $\rightarrow$ `>` | `POLICY.md` §3.1 | `test_circuit_breaker.py::test_cooldown_exact_expiry_admits_probe` | **KILLED** | Inverted latency health check |
| **MUT-03** | `src/engine.py:96` | `>= failure_threshold` $\rightarrow$ `>` | `POLICY.md` §3.4 | `test_circuit_breaker.py::test_call_refused_during_cooldown` | **KILLED** | Caught tripping at $N$ vs $N+1$ |
| **MUT-04** | `src/engine.py:96` | `>= failure_threshold` $\rightarrow$ `>= threshold - 1` | `POLICY.md` §3.4 | `test_circuit_breaker.py::test_probe_failure_re_trips_breaker` | **KILLED** | Caught premature tripping at $N-1$ |
| **MUT-05** | `src/engine.py:86` | Omit `consecutive_failures = 0` | `POLICY.md` §3.4 | `test_failure_counter.py::test_intervening_success_resets_counter_to_zero` | **KILLED** | Verified failure counter reset |
| **MUT-06** | `src/engine.py:86` | Decrement `failures -= 1` instead of reset to 0 | `POLICY.md` §3.4 | `test_failure_counter.py::test_intervening_success_resets_counter_to_zero` | **KILLED** | Verified complete reset vs decrement |
| **MUT-07** | `src/engine.py:41` | Increment `consecutive_failures += 1` on refusal | `POLICY.md` §3.4 | `test_failure_counter.py::test_refused_call_does_not_increment_counter` | **KILLED** | Enforced refusal counter invariant |
| **MUT-08** | `src/engine.py:38` | `current_time < cooldown_until` $\rightarrow$ `<=` | `POLICY.md` §3.7 | `test_circuit_breaker.py::test_cooldown_exact_expiry_admits_probe` | **KILLED** | Verified exact $T_{\text{cool}}$ millisecond boundary admits probe |
| **MUT-09** | `src/engine.py:38` | `current_time < cooldown_until` $\rightarrow$ `>` | `POLICY.md` §3.7 | `test_circuit_breaker.py::test_call_refused_during_cooldown` | **KILLED** | Inverted cooldown comparison |
| **MUT-10** | `src/state_machine.py:27` | Omit `state = "CLOSED"` on probe recovery | `POLICY.md` §4.2 | `test_circuit_breaker.py::test_cooldown_exact_expiry_admits_probe` | **KILLED** | Verified transition to CLOSED on probe success |
| **MUT-11** | `src/state_machine.py:28` | Omit `consecutive_failures = 0` on recovery | `POLICY.md` §4.2 | `test_circuit_breaker.py::test_cooldown_exact_expiry_admits_probe` | **KILLED** | Verified failure reset on probe success |
| **MUT-12** | `src/engine.py:57` | Cooldown extension uses old cooldown | `POLICY.md` §4.2 | `test_circuit_breaker.py::test_probe_failure_re_trips_breaker` | **KILLED** | Verified new cooldown window starts from probe timestamp |
| **MUT-13** | `src/engine.py:126` | Permit retries on tripped breaker | `POLICY.md` §4.1 | `test_failure_counter.py::test_failure_threshold_exact_boundary_trips_to_open` | **KILLED** | Prohibited retries against OPEN breaker |
| **MUT-14** | `src/engine.py:126` | Ignore `max_retries == 0` config | `POLICY.md` §4.1 | `test_retry_policy.py::test_retries_disabled_emits_give_up` | **KILLED** | Enforced `give_up` when `max_retries = 0` |
| **MUT-15** | `src/engine.py:108` | Allow slow ok success to fall through to retry | `POLICY.md` §3.3 | `test_failure_classification.py::test_latency_above_slow_threshold_boundary` | **KILLED** | Enforced slow success is non-retryable |
| **MUT-16** | `src/engine.py:116` | Allow unknown status to fall through to retry | `POLICY.md` §2.1 | `test_failure_classification.py::test_unrecognized_status_is_unretryable_failure` | **KILLED** | Enforced unknown status is non-retryable |
| **MUT-17** | `src/engine.py:34` | Route all calls to a single global provider | `POLICY.md` §3.5 | `test_circuit_breaker.py::test_probe_failure_re_trips_breaker` | **KILLED** | Enforced per-provider FSM isolation |
| **MUT-18** | `src/engine.py:30` | Remove monotonic tracking (`max()` omitted) | `POLICY.md` §4.3 | `test_timestamp_monotonicity.py::test_monotonic_time_advances_probe_cooldown_even_with_out_of_order_calls` | **KILLED** | Verified time cannot regress across out-of-order calls |
| **MUT-19** | `src/state_machine.py:36` | Invert duration arithmetic `stopped_ms - resumed_ms` | `POLICY.md` §2.4 | `test_stopped_periods.py::test_complete_stopped_period_calculation` | **KILLED** | Verified duration arithmetic |
| **MUT-20** | `src/state_machine.py:42` | Omit finalizing unclosed periods at end of log | `POLICY.md` §2.4 | `test_stopped_periods.py::test_unrecovered_provider_at_end_of_log` | **KILLED** | Verified `resumed_at = null` and duration measured to log end |
| **MUT-21** | `src/engine.py:158` | Invert input order (`decisions.insert(0, ...)`) | `POLICY.md` §2.3 | `test_output_contract.py::test_process_file_preserves_input_line_order_exactly` | **KILLED** | Enforced exact input arrival order preservation |
| **MUT-22** | `src/engine.py:89` | Emit non-approved vocabulary word `"allow"` | `POLICY.md` §5.1 | `test_failure_classification.py::test_fast_success_is_healthy_attempt` | **KILLED** | Enforced controlled action vocabulary |
| **MUT-23** | `src/engine.py:47` | Hardcode probe `slow_threshold_ms` to 5000 | `POLICY.md` §8 | `test_circuit_breaker.py::test_probe_configurable_slow_threshold` | **KILLED** | Verified custom probe latency threshold ($3000\text{ms} > 2500\text{ms}$) fails probe |
| **MUT-24** | `src/engine.py:96` | Hardcode `failure_threshold` to 3 | `POLICY.md` §8 | `test_failure_counter.py::test_configurable_failure_threshold` | **KILLED** | Verified dynamic threshold binding |
| **MUT-25** | `src/engine.py:57` | Hardcode probe failure cooldown to 30000 | `POLICY.md` §8 | `test_circuit_breaker.py::test_probe_failure_respects_custom_cooldown` | **KILLED** | Verified dynamic cooldown binding on probe failure |

---

## 3. Hardening Narrative: How Survivors Were Discovered and Killed

During initial execution, 5 mutations initially survived:
1. **MUT-01 & MUT-23 (Probe Latency Exact Boundary & Configuration Binding)**:
   - *Cause*: Existing tests only asserted normal call latency boundaries, not canary probe calls at exact boundaries.
   - *Fix*: Added `test_probe_exact_slow_threshold_recovers` (5000ms latency on probe succeeds) and hardened `test_probe_configurable_slow_threshold` with a 3000ms probe call under a 2500ms limit.
   - *Outcome*: Both mutations killed.
2. **MUT-18 (Monotonic Time Tracking)**:
   - *Cause*: The original out-of-order test checked a record that was already before cooldown expiry regardless of time tracking.
   - *Fix*: Added `test_monotonic_time_advances_probe_cooldown_even_with_out_of_order_calls` where global time has already advanced past cooldown on another provider, proving that the out-of-order call evaluates as an expired probe rather than regressing time.
   - *Outcome*: Mutation killed.
3. **MUT-21 (File-Level Input Line Order)**:
   - *Cause*: Tests checked `process_record` in a list comprehension, leaving `engine.process_file` unasserted for line sequence.
   - *Fix*: Added `test_process_file_preserves_input_line_order_exactly` asserting exact ID sequence `["rec_000" ... "rec_005"]`.
   - *Outcome*: Mutation killed.
4. **MUT-25 (Probe Failure Cooldown Configuration Binding)**:
   - *Cause*: Configurable cooldown tests checked initial breaker trip, but not probe failure cooldown extension.
   - *Fix*: Added `test_probe_failure_respects_custom_cooldown` testing custom 15000ms cooldown after failed probe.
   - *Outcome*: Mutation killed.

**Final Result**: **Zero surviving mutations**. Test suite provides complete boundary and mutation coverage.
