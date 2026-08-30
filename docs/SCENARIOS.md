# Scenario Matrix & Policy Verification Suite

**Document Status**: `FINAL SCENARIO VERIFICATION SUITE`  
**Purpose**: Comprehensive, deterministic test scenarios covering all boundary conditions, state transitions, retry semantics, provider isolation, timestamp mechanics, and failure modes formalized in `docs/POLICY.md`.

---

## 1. Scenario Schema & Conventions

Every scenario strictly specifies:
- **Scenario ID**: Unique identifier `SCEN-XYY` (e.g. `SCEN-A01`).
- **Purpose**: Specific behavioral rule or boundary being verified.
- **Configuration**: Specific values for `failure_threshold`, `cooldown_ms`, `slow_threshold_ms`, `max_retries`, `retry_delay_ms`.
- **Input Record(s)**: JSONL input line(s) in arrival order.
- **Initial State**: Prior provider state tuple `(state, consecutive_failures, cooldown_until, active_stopped_period)`.
- **Step-by-Step Evaluation**: Trace of mathematical comparisons, guards, and side effects.
- **Expected Output Decision**: `{"id": "...", "action": "...", "provider_state": "...", "reason": "..."}`.
- **Resulting State**: State tuple following record evaluation.
- **Rule(s) Exercised**: References to `POLICY.md` sections.
- **Boundary Classification**: Exact condition (e.g., $N$, $N-1$, $T_{\text{cool}}-1\text{ms}$, $T_{\text{slow}}+1\text{ms}$).
- **Target Mutation**: The code mutation this scenario is designed to catch/kill.

---

## 2. Default Configuration Baseline
Unless explicitly overridden in a scenario, the baseline configuration is:
```json
{
  "failure_threshold": 3,
  "cooldown_ms": 30000,
  "slow_threshold_ms": 5000,
  "max_retries": 1,
  "retry_delay_ms": 1000
}
```

---

## 3. Scenario Matrix by Category

### Category A: Basic Healthy Behavior & Initialization

#### `SCEN-A01`: New Provider First Successful Call
- **Purpose**: Verify dynamic initialization and healthy handling for a new provider.
- **Configuration**: Baseline defaults.
- **Input**: `{"id": "c001", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 450}`
- **Initial State**: `alpha` uninitialized.
- **Step-by-Step Evaluation**:
  1. `alpha` not in state map -> instantiate with `state = "CLOSED"`, `consecutive_failures = 0`.
  2. `current_time` updated to `2026-09-01T10:00:00.000Z` ($1788256800000\text{ms}$).
  3. Pre-execution check: `state == "CLOSED"`.
  4. Classify outcome: `status == "ok"` AND `latency_ms (450) <= slow_threshold_ms (5000)` -> Provider Success.
  5. State side effect: `consecutive_failures = 0`, state remains `CLOSED`.
- **Expected Decision**: `{"id": "c001", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=0, cooldown_until=null)`
- **Rule Exercised**: `POLICY.md` §3.5, §3.6, §5.1, §6
- **Boundary Classification**: Baseline initialization ($0$ failures).
- **Target Mutation**: Initializing state to `"OPEN"` or defaulting failure count to non-zero.

---

#### `SCEN-A02`: Repeated Consecutive Successful Calls
- **Purpose**: Verify failure counter remains 0 on continuous healthy traffic.
- **Configuration**: Baseline defaults.
- **Input**:
  - `{"id": "c001", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 300}`
  - `{"id": "c002", "provider": "alpha", "started_at": "2026-09-01T10:00:01.000Z", "status": "ok", "latency_ms": 250}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Step-by-Step Evaluation**: Both records evaluate to Provider Success; `consecutive_failures` remains 0.
- **Expected Decisions**:
  - `{"id": "c001", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
  - `{"id": "c002", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=0)`
- **Rule Exercised**: `POLICY.md` §3.4, §6
- **Target Mutation**: Counter incrementing on success.

---

#### `SCEN-A03`: Transient Failure Followed Immediately by Success
- **Purpose**: Verify that a single successful call resets `consecutive_failures` back to 0.
- **Configuration**: Baseline defaults.
- **Input**:
  - `{"id": "c001", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}`
  - `{"id": "c002", "provider": "alpha", "started_at": "2026-09-01T10:00:01.000Z", "status": "ok", "latency_ms": 400}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Step-by-Step Evaluation**:
  - Record 1: `status == "error"` -> Provider Failure. `failures` becomes 1. `max_retries >= 1` -> Action `retry`.
  - Record 2: `status == "ok"`, `latency_ms <= 5000` -> Provider Success. `failures` resets from 1 to 0. Action `attempt`.
- **Expected Decisions**:
  - `{"id": "c001", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
  - `{"id": "c002", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=0)`
- **Rule Exercised**: `POLICY.md` §3.4, §4.1, §6
- **Boundary Classification**: Recovery from $1$ failure back to $0$.
- **Target Mutation**: Forgetting to reset failure counter on success (`failures = failures` instead of `failures = 0`).

---

### Category B: Failure Classification & Latency Boundaries

#### `SCEN-B01`: Fast Successful Call (Strictly Below Threshold)
- **Purpose**: Verify `latency_ms < slow_threshold_ms` is healthy.
- **Configuration**: `slow_threshold_ms: 5000`.
- **Input**: `{"id": "c010", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 2500}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**: `2500 <= 5000` -> Provider Success. `failures = 0`.
- **Expected Decision**: `{"id": "c010", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=0)`
- **Rule Exercised**: `POLICY.md` §3.1

---

#### `SCEN-B02`: Latency Boundary Below Threshold ($T_{\text{slow}} - 1\text{ms}$)
- **Purpose**: Boundary test at exactly $4999\text{ms}$ when threshold is $5000\text{ms}$.
- **Configuration**: `slow_threshold_ms: 5000`.
- **Input**: `{"id": "c011", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 4999}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**: `4999 <= 5000` -> Provider Success. `failures = 0`.
- **Expected Decision**: `{"id": "c011", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=0)`
- **Rule Exercised**: `POLICY.md` §3.1, §3.3
- **Boundary Classification**: $T_{\text{slow}} - 1\text{ms}$.
- **Target Mutation**: Off-by-one threshold adjustment.

---

#### `SCEN-B03`: Exact Latency Threshold Boundary ($T_{\text{slow}}$)
- **Purpose**: Verify strict inequality rule: `latency_ms == slow_threshold_ms` is healthy ($5000\text{ms} \le 5000\text{ms}$).
- **Configuration**: `slow_threshold_ms: 5000`.
- **Input**: `{"id": "c012", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 5000}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**: `5000 <= 5000` evaluates to true -> Provider Success. `failures = 0`.
- **Expected Decision**: `{"id": "c012", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=0)`
- **Rule Exercised**: `POLICY.md` §3.1, §3.3
- **Boundary Classification**: $T_{\text{slow}}$ exact boundary.
- **Target Mutation**: Mutating `latency_ms > slow_threshold_ms` to `latency_ms >= slow_threshold_ms`.

---

#### `SCEN-B04`: Latency Boundary Above Threshold ($T_{\text{slow}} + 1\text{ms}$)
- **Purpose**: Verify `latency_ms == slow_threshold_ms + 1` ($5001\text{ms}$) is classified as a degradation failure.
- **Configuration**: `slow_threshold_ms: 5000`, `failure_threshold: 3`.
- **Input**: `{"id": "c013", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 5001}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**:
  1. `status == "ok"` BUT `latency_ms (5001) > slow_threshold_ms (5000)` -> Provider Failure (Slow Success).
  2. `failures` increments from 0 to 1 ($1 < 3$, provider remains `CLOSED`).
  3. Action is `attempt` (outcome delivered), Reason is `slow_success_degradation`.
- **Expected Decision**: `{"id": "c013", "action": "attempt", "provider_state": "CLOSED", "reason": "slow_success_degradation"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=1)`
- **Rule Exercised**: `POLICY.md` §3.1, §3.3, §5.3, §6
- **Boundary Classification**: $T_{\text{slow}} + 1\text{ms}$.
- **Target Mutation**: Mutating `latency_ms > slow_threshold_ms` to `<` or omitting slow success check.

---

#### `SCEN-B05`: Explicit Timeout Failure
- **Purpose**: Verify `status == "timeout"` is a Provider Failure and eligible for retry.
- **Configuration**: Baseline defaults (`max_retries: 1`, `failure_threshold: 3`).
- **Input**: `{"id": "c014", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "timeout", "latency_ms": 5000}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**: `status == "timeout"` -> Failure. `failures` becomes 1. Action `retry`, Reason `timeout_retry`.
- **Expected Decision**: `{"id": "c014", "action": "retry", "provider_state": "CLOSED", "reason": "timeout_retry"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=1)`
- **Rule Exercised**: `POLICY.md` §3.1, §4.1, §5.3

---

#### `SCEN-B06`: Unrecognized / Unknown Status String
- **Purpose**: Verify unrecognized status string is handled as an unretryable failure without crashing.
- **Configuration**: `failure_threshold: 3`.
- **Input**: `{"id": "c015", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "rate_limited_429", "latency_ms": 120}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**:
  1. `status == "rate_limited_429"` not in `["ok", "error", "timeout"]` -> Provider Failure.
  2. `failures` increments to 1.
  3. Action is `attempt` (unretryable), Reason is `unrecognized_status_failure`.
- **Expected Decision**: `{"id": "c015", "action": "attempt", "provider_state": "CLOSED", "reason": "unrecognized_status_failure"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=1)`
- **Rule Exercised**: `POLICY.md` §2.1, §3.1, §5.3, §6
- **Target Mutation**: Swallowing unknown statuses or crashing with unhandled exception.

---

### Category C: Failure Threshold Boundaries ($N-1$, $N$, $N+1$)

#### `SCEN-C01`: Failure Count at Exactly Threshold - 1 ($N-1$)
- **Purpose**: Verify circuit remains `CLOSED` at $N-1$ failures ($2$ failures when threshold is $3$).
- **Configuration**: `failure_threshold: 3`, `max_retries: 1`.
- **Input**:
  - `{"id": "c021", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}`
  - `{"id": "c022", "provider": "alpha", "started_at": "2026-09-01T10:00:01.000Z", "status": "error", "latency_ms": 100}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Step-by-Step Evaluation**:
  - Record 1: `failures` increments to 1 ($1 < 3$) -> `state = CLOSED`, Action `retry`.
  - Record 2: `failures` increments to 2 ($2 < 3$) -> `state = CLOSED`, Action `retry`.
- **Expected Decisions**:
  - `{"id": "c021", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
  - `{"id": "c022", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=2)`
- **Rule Exercised**: `POLICY.md` §3.4, §6
- **Boundary Classification**: $N - 1$ boundary ($2$ failures).
- **Target Mutation**: Changing `failures >= failure_threshold` to `failures >= failure_threshold - 1` (tripping early).

---

#### `SCEN-C02`: Failure Count at Exactly Threshold ($N$)
- **Purpose**: Verify circuit trips from `CLOSED` to `OPEN` on the exact $N$-th consecutive failure ($3$ failures).
- **Configuration**: `failure_threshold: 3`, `cooldown_ms: 30000`, `max_retries: 1`.
- **Input**: `{"id": "c023", "provider": "alpha", "started_at": "2026-09-01T10:00:02.000Z", "status": "timeout", "latency_ms": 5000}`
- **Initial State**: `alpha: (state="CLOSED", failures=2)`
- **Step-by-Step Evaluation**:
  1. `status == "timeout"` -> Failure. `failures` increments from 2 to 3.
  2. Guard check: `failures (3) >= failure_threshold (3)` -> evaluates TRUE.
  3. Breaker trips: `state = "OPEN"`, `opened_at = "2026-09-01T10:00:02.000Z"`, `cooldown_until = 10:00:32.000Z`.
  4. Stopped period opened: `{"stopped_at": "2026-09-01T10:00:02.000Z"}`.
  5. Because circuit tripped to `OPEN`, retries are prohibited -> Action `give_up`, Reason `max_retries_exceeded`.
  6. Emitted `provider_state` is the resulting state: `"OPEN"`.
- **Expected Decision**: `{"id": "c023", "action": "give_up", "provider_state": "OPEN", "reason": "max_retries_exceeded"}`
- **Resulting State**: `alpha: (state="OPEN", failures=3, cooldown_until=1788256832000)`
- **Rule Exercised**: `POLICY.md` §3.1, §3.4, §4.1, §6
- **Boundary Classification**: $N$ exact boundary ($3$ failures).
- **Target Mutation**: Mutating `failures >= failure_threshold` to `failures > failure_threshold` (off-by-one bug).

---

#### `SCEN-C03`: Interleaving Resets Preventing Trip
- **Purpose**: Verify non-consecutive failures do not trip the circuit breaker.
- **Configuration**: `failure_threshold: 3`.
- **Input**:
  - `{"id": "c024", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}` -> failures=1
  - `{"id": "c025", "provider": "alpha", "started_at": "2026-09-01T10:00:01.000Z", "status": "error", "latency_ms": 100}` -> failures=2
  - `{"id": "c026", "provider": "alpha", "started_at": "2026-09-01T10:00:02.000Z", "status": "ok", "latency_ms": 200}` -> failures=0
  - `{"id": "c027", "provider": "alpha", "started_at": "2026-09-01T10:00:03.000Z", "status": "error", "latency_ms": 100}` -> failures=1
  - `{"id": "c028", "provider": "alpha", "started_at": "2026-09-01T10:00:04.000Z", "status": "error", "latency_ms": 100}` -> failures=2
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**: Counter progression: $1 \rightarrow 2 \rightarrow 0 \rightarrow 1 \rightarrow 2$. Provider remains `CLOSED` throughout.
- **Expected Decisions**:
  - `c024`: `{"id": "c024", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
  - `c025`: `{"id": "c025", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
  - `c026`: `{"id": "c026", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
  - `c027`: `{"id": "c027", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
  - `c028`: `{"id": "c028", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=2)`
- **Rule Exercised**: `POLICY.md` §3.4, §6

---

### Category D: Circuit Breaker Lifecycle & Cooldown Boundaries

#### `SCEN-D01`: Call Arriving During Active Cooldown
- **Purpose**: Verify calls arriving while `OPEN` and `current_time < cooldown_until` are refused upfront.
- **Configuration**: Baseline defaults (`cooldown_ms: 30000`).
- **Input**: `{"id": "c030", "provider": "alpha", "started_at": "2026-09-01T10:00:15.000Z", "status": "ok", "latency_ms": 200}`
- **Initial State**: `alpha: (state="OPEN", failures=3, opened_at="10:00:00.000Z", cooldown_until=10:00:30.000Z)`
- **Step-by-Step Evaluation**:
  1. `record.started_at` is `10:00:15.000Z` ($1788256815000\text{ms}$).
  2. Check cooldown: `10:00:15.000Z < 10:00:30.000Z` -> Cooldown active.
  3. Emitted action is `refuse`, state is `OPEN`, reason is `circuit_open_refusal`.
  4. Invariant: `failures` remains 3 (refused calls do not increment counter).
- **Expected Decision**: `{"id": "c030", "action": "refuse", "provider_state": "OPEN", "reason": "circuit_open_refusal"}`
- **Resulting State**: `alpha: (state="OPEN", failures=3, cooldown_until=10:00:30.000Z)`
- **Rule Exercised**: `POLICY.md` §3.4, §3.7, §5.1, §6
- **Target Mutation**: Attempting call instead of refusing, or incrementing failure count on refusal.

---

#### `SCEN-D02`: Cooldown Boundary Immediately Before Expiry ($T_{\text{cool}} - 1\text{ms}$)
- **Purpose**: Verify exact millisecond boundary before cooldown expiry refuses call ($29999\text{ms}$ after opening).
- **Configuration**: Baseline defaults (`opened_at = 10:00:00.000Z`, `cooldown_ms = 30000` -> `cooldown_until = 10:00:30.000Z`).
- **Input**: `{"id": "c031", "provider": "alpha", "started_at": "2026-09-01T10:00:29.999Z", "status": "ok", "latency_ms": 100}`
- **Initial State**: `alpha: (state="OPEN", failures=3, cooldown_until="10:00:30.000Z")`
- **Evaluation**: `10:00:29.999Z < 10:00:30.000Z` evaluates TRUE -> Call refused.
- **Expected Decision**: `{"id": "c031", "action": "refuse", "provider_state": "OPEN", "reason": "circuit_open_refusal"}`
- **Resulting State**: `alpha: (state="OPEN", failures=3)`
- **Rule Exercised**: `POLICY.md` §3.7, §6
- **Boundary Classification**: $T_{\text{cool}} - 1\text{ms}$.
- **Target Mutation**: Mutating `< cooldown_until` to `<= cooldown_until` (allowing probe 1ms early).

---

#### `SCEN-D03`: Exact Cooldown Expiry Boundary ($T_{\text{cool}}$)
- **Purpose**: Verify exact millisecond boundary of cooldown expiry ($30000\text{ms}$) designates record as probe.
- **Configuration**: Baseline defaults (`opened_at = 10:00:00.000Z`, `cooldown_ms = 30000` -> `cooldown_until = 10:00:30.000Z`).
- **Input**: `{"id": "c032", "provider": "alpha", "started_at": "2026-09-01T10:00:30.000Z", "status": "ok", "latency_ms": 250}`
- **Initial State**: `alpha: (state="OPEN", failures=3, cooldown_until="10:00:30.000Z")`
- **Step-by-Step Evaluation**:
  1. `record.started_at` ($10:00:30.000Z$) $\ge cooldown\_until$ ($10:00:30.000Z$) -> Cooldown expired.
  2. Designated as canary probe call.
  3. Outcome evaluation: `status == "ok"` AND `latency_ms (250) <= 5000` -> Probe Success!
  4. State transitions from `HALF_OPEN` to `CLOSED`.
  5. `consecutive_failures` resets to 0. Stopped period closed: `[10:00:00.000Z -> 10:00:30.000Z, 30000ms]`.
  6. Emitted decision: `action = "probe"`, `provider_state = "CLOSED"`, `reason = "probe_success_recovery"`.
- **Expected Decision**: `{"id": "c032", "action": "probe", "provider_state": "CLOSED", "reason": "probe_success_recovery"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=0, cooldown_until=null)`
- **Rule Exercised**: `POLICY.md` §4.2, §5.1, §6
- **Boundary Classification**: $T_{\text{cool}}$ exact boundary.
- **Target Mutation**: Mutating `>= cooldown_until` to `> cooldown_until` (failing to probe at exact boundary).

---

#### `SCEN-D04`: Cooldown Expiry with Probe Failure (Re-Trip)
- **Purpose**: Verify that a failed probe re-trips the breaker to `OPEN` and establishes a new cooldown window.
- **Configuration**: Baseline defaults (`cooldown_ms: 30000`).
- **Input**: `{"id": "c033", "provider": "alpha", "started_at": "2026-09-01T10:00:30.000Z", "status": "timeout", "latency_ms": 5000}`
- **Initial State**: `alpha: (state="OPEN", failures=3, opened_at="10:00:00.000Z", cooldown_until="10:00:30.000Z")`
- **Step-by-Step Evaluation**:
  1. `record.started_at` $\ge cooldown\_until$ -> Cooldown expired; evaluated as probe.
  2. Outcome evaluation: `status == "timeout"` -> Probe Failure!
  3. State transitions from `HALF_OPEN` back to `OPEN`.
  4. `failures` increments from 3 to 4.
  5. New cooldown window: `opened_at = 10:00:30.000Z`, `cooldown_until = 10:01:00.000Z`.
  6. Stopped period remains open (continuous).
  7. Emitted decision: `action = "probe"`, `provider_state = "OPEN"`, `reason = "probe_failure_reopen"`.
- **Expected Decision**: `{"id": "c033", "action": "probe", "provider_state": "OPEN", "reason": "probe_failure_reopen"}`
- **Resulting State**: `alpha: (state="OPEN", failures=4, cooldown_until="10:01:00.000Z")`
- **Rule Exercised**: `POLICY.md` §4.2, §5.3, §6
- **Target Mutation**: Setting new cooldown from old `opened_at` instead of probe timestamp, or closing stopped period on probe failure.

---

#### `SCEN-D05`: Call Arriving After Probe Failure during Second Cooldown
- **Purpose**: Verify calls arriving during the second cooldown period are refused.
- **Configuration**: Baseline defaults.
- **Input**: `{"id": "c034", "provider": "alpha", "started_at": "2026-09-01T10:00:45.000Z", "status": "ok", "latency_ms": 200}`
- **Initial State**: `alpha: (state="OPEN", failures=4, cooldown_until="10:01:00.000Z")`
- **Evaluation**: `10:00:45.000Z < 10:01:00.000Z` -> Cooldown active. Action `refuse`.
- **Expected Decision**: `{"id": "c034", "action": "refuse", "provider_state": "OPEN", "reason": "circuit_open_refusal"}`
- **Resulting State**: `alpha: (state="OPEN", failures=4)`
- **Rule Exercised**: `POLICY.md` §3.7, §6

---

### Category E: Retrospective Retry Semantics & Budget Boundaries

#### `SCEN-E01`: Transient Error with `max_retries = 1`
- **Purpose**: Verify transient error on healthy provider recommends `retry`.
- **Configuration**: `max_retries: 1`, `failure_threshold: 3`.
- **Input**: `{"id": "c040", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**: `status == "error"` -> Failure (`failures = 1`). `failures < 3` -> `state = CLOSED`. `max_retries >= 1` -> Action `retry`, Reason `transient_error_retry`.
- **Expected Decision**: `{"id": "c040", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=1)`
- **Rule Exercised**: `POLICY.md` §4.1, §5.1, §6

---

#### `SCEN-E02`: Transient Timeout with `max_retries = 1`
- **Purpose**: Verify transient timeout on healthy provider recommends `retry`.
- **Configuration**: `max_retries: 1`, `failure_threshold: 3`.
- **Input**: `{"id": "c041", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "timeout", "latency_ms": 5000}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**: Action `retry`, Reason `timeout_retry`, `provider_state = CLOSED`.
- **Expected Decision**: `{"id": "c041", "action": "retry", "provider_state": "CLOSED", "reason": "timeout_retry"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=1)`
- **Rule Exercised**: `POLICY.md` §4.1, §5.1, §6

---

#### `SCEN-E03`: Transient Error when `max_retries = 0` (Retries Disabled)
- **Purpose**: Verify that when `max_retries == 0`, a transient error produces `action: "give_up"`.
- **Configuration**: `max_retries: 0`, `failure_threshold: 3`.
- **Input**: `{"id": "c042", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Step-by-Step Evaluation**:
  1. `status == "error"` -> Failure. `failures` becomes 1 ($1 < 3$).
  2. Check retry budget: `max_retries == 0` -> Retries prohibited.
  3. Action is `give_up`, Reason is `max_retries_exceeded`, `provider_state = "CLOSED"`.
- **Expected Decision**: `{"id": "c042", "action": "give_up", "provider_state": "CLOSED", "reason": "max_retries_exceeded"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=1)`
- **Rule Exercised**: `POLICY.md` §4.1, §5.1, §6
- **Boundary Classification**: `max_retries == 0` boundary.
- **Target Mutation**: Hardcoding retry action regardless of `max_retries` setting.

---

#### `SCEN-E04`: Transient Error Tripping Breaker (Prohibiting Retry)
- **Purpose**: Verify that if a failure trips the breaker to `OPEN`, the action is `give_up` (retrying open breaker forbidden).
- **Configuration**: `max_retries: 1`, `failure_threshold: 3`.
- **Input**: `{"id": "c043", "provider": "alpha", "started_at": "2026-09-01T10:00:02.000Z", "status": "error", "latency_ms": 150}`
- **Initial State**: `alpha: (state="CLOSED", failures=2)`
- **Step-by-Step Evaluation**:
  1. `failures` increments from 2 to 3 ($3 \ge 3$) -> trips breaker to `OPEN`.
  2. Even though `max_retries >= 1`, the circuit just became `OPEN`; retrying against an open circuit is prohibited.
  3. Action is `give_up`, Reason is `max_retries_exceeded`, `provider_state = "OPEN"`.
- **Expected Decision**: `{"id": "c043", "action": "give_up", "provider_state": "OPEN", "reason": "max_retries_exceeded"}`
- **Resulting State**: `alpha: (state="OPEN", failures=3)`
- **Rule Exercised**: `POLICY.md` §4.1, §6
- **Target Mutation**: Emitting `action: "retry"` when `provider_state` is `"OPEN"`.

---

#### `SCEN-E05`: Slow Success is Non-Retryable
- **Purpose**: Verify slow `ok` call emits `attempt` and is never retried.
- **Configuration**: `slow_threshold_ms: 5000`, `max_retries: 1`.
- **Input**: `{"id": "c044", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 6500}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**: Action is `attempt`, Reason `slow_success_degradation`. Never retried.
- **Expected Decision**: `{"id": "c044", "action": "attempt", "provider_state": "CLOSED", "reason": "slow_success_degradation"}`
- **Resulting State**: `alpha: (state="CLOSED", failures=1)`
- **Rule Exercised**: `POLICY.md` §3.3, §4.1

---

### Category F: Multi-Provider Isolation

#### `SCEN-F01`: Provider A OPEN while Provider B Remains Healthy (CLOSED)
- **Purpose**: Verify strict isolation: an outage in `alpha` does not affect `beta`.
- **Configuration**: Baseline defaults.
- **Input**:
  - `{"id": "c051", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}` -> A failures=1
  - `{"id": "c052", "provider": "alpha", "started_at": "2026-09-01T10:00:01.000Z", "status": "error", "latency_ms": 100}` -> A failures=2
  - `{"id": "c053", "provider": "alpha", "started_at": "2026-09-01T10:00:02.000Z", "status": "error", "latency_ms": 100}` -> A trips to OPEN
  - `{"id": "c054", "provider": "beta", "started_at": "2026-09-01T10:00:03.000Z", "status": "ok", "latency_ms": 300}` -> B processed
  - `{"id": "c055", "provider": "alpha", "started_at": "2026-09-01T10:00:04.000Z", "status": "ok", "latency_ms": 200}` -> A refused
- **Initial State**: All providers uninitialized.
- **Expected Decisions**:
  - `c051`: `{"id": "c051", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
  - `c052`: `{"id": "c052", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
  - `c053`: `{"id": "c053", "action": "give_up", "provider_state": "OPEN", "reason": "max_retries_exceeded"}`
  - `c054`: `{"id": "c054", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
  - `c055`: `{"id": "c055", "action": "refuse", "provider_state": "OPEN", "reason": "circuit_open_refusal"}`
- **Resulting State**: `alpha: (state="OPEN", failures=3)`, `beta: (state="CLOSED", failures=0)`
- **Rule Exercised**: `POLICY.md` §3.5, §6
- **Target Mutation**: Sharing failure counter or state globally across providers.

---

### Category G: Timestamp Mechanics & Monotonic Time Tracking

#### `SCEN-G01`: Equal Timestamps (Burst Traffic)
- **Purpose**: Verify multiple calls sharing identical timestamps evaluate deterministically in arrival order.
- **Configuration**: Baseline defaults.
- **Input**:
  - `{"id": "c061", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}`
  - `{"id": "c062", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}`
  - `{"id": "c063", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}`
- **Initial State**: `alpha: (state="CLOSED", failures=0)`
- **Evaluation**:
  - `c061`: failure 1 -> `CLOSED`, `retry`
  - `c062`: failure 2 -> `CLOSED`, `retry`
  - `c063`: failure 3 -> trips `OPEN`, `give_up`, `opened_at = 10:00:00.000Z`, `cooldown_until = 10:00:30.000Z`.
- **Expected Decisions**:
  - `c061`: `{"id": "c061", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
  - `c062`: `{"id": "c062", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
  - `c063`: `{"id": "c063", "action": "give_up", "provider_state": "OPEN", "reason": "max_retries_exceeded"}`
- **Resulting State**: `alpha: (state="OPEN", failures=3)`
- **Rule Exercised**: `POLICY.md` §3.4, §4.3, §6

---

#### `SCEN-G02`: Out-of-Order Timestamp (Monotonic Tracking)
- **Purpose**: Verify non-monotonic input timestamps do not regress time or prematurely expire cooldown.
- **Configuration**: Baseline defaults (`cooldown_ms: 30000`).
- **Input**:
  - `{"id": "c064", "provider": "alpha", "started_at": "2026-09-01T10:00:10.000Z", "status": "error", "latency_ms": 100}` (failures=3 -> trips OPEN, cooldown_until=10:00:40.000Z, max_seen=10:00:10.000Z)
  - `{"id": "c065", "provider": "alpha", "started_at": "2026-09-01T10:00:05.000Z", "status": "ok", "latency_ms": 200}` (out-of-order timestamp: 10:00:05.000Z < max_seen 10:00:10.000Z)
- **Initial State**: `alpha: (state="CLOSED", failures=2)`
- **Step-by-Step Evaluation**:
  - Record 1 (`c064`): trips breaker to `OPEN`. `opened_at = 10:00:10.000Z`, `cooldown_until = 10:00:40.000Z`. `max_seen` updated to `10:00:10.000Z`. Action `give_up`.
  - Record 2 (`c065`): `record.started_at` is `10:00:05.000Z`. Monotonic `current_time = max(10:00:10, 10:00:05) = 10:00:10.000Z`.
  - Cooldown comparison: `current_time (10:00:10) < cooldown_until (10:00:40)` -> Cooldown still active.
  - Action is `refuse`, `provider_state = "OPEN"`, `reason = "circuit_open_refusal"`.
- **Expected Decisions**:
  - `c064`: `{"id": "c064", "action": "give_up", "provider_state": "OPEN", "reason": "max_retries_exceeded"}`
  - `c065`: `{"id": "c065", "action": "refuse", "provider_state": "OPEN", "reason": "circuit_open_refusal"}`
- **Resulting State**: `alpha: (state="OPEN", failures=3, cooldown_until="10:00:40.000Z")`
- **Rule Exercised**: `POLICY.md` §4.3, §6, §7
- **Target Mutation**: Regressing `current_time` on out-of-order records.

---

### Category H: Stopped Period Calculations & Report Generation

#### `SCEN-H01`: Complete Closed Outage Cycle
- **Purpose**: Verify stopped period is recorded with exact `stopped_at`, `resumed_at`, and `duration_ms`.
- **Configuration**: `cooldown_ms: 30000`.
- **Input**:
  - `{"id": "c071", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}` (trip to OPEN)
  - `{"id": "c072", "provider": "alpha", "started_at": "2026-09-01T10:00:30.000Z", "status": "ok", "latency_ms": 200}` (probe success)
- **Initial State**: `alpha: (state="CLOSED", failures=2)`
- **Evaluation**:
  - `c071` trips breaker: `stopped_at = "2026-09-01T10:00:00.000Z"`.
  - `c072` succeeds as probe: `resumed_at = "2026-09-01T10:00:30.000Z"`.
  - Stopped period closed: `duration_ms = 1788256830000 - 1788256800000 = 30000ms`.
- **Expected `stopped_periods.json` Output**:
  ```json
  {
    "alpha": [
      {
        "stopped_at": "2026-09-01T10:00:00.000Z",
        "resumed_at": "2026-09-01T10:00:30.000Z",
        "duration_ms": 30000
      }
    ]
  }
  ```
- **Rule Exercised**: `POLICY.md` §2.4, §4.2, §7

---

#### `SCEN-H02`: Provider Unrecovered at End of Log
- **Purpose**: Verify unclosed stopped period has `resumed_at: null` and duration measured to last log record.
- **Configuration**: Baseline defaults.
- **Input**:
  - `{"id": "c073", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "error", "latency_ms": 100}` (trips OPEN)
  - `{"id": "c074", "provider": "alpha", "started_at": "2026-09-01T10:00:10.000Z", "status": "ok", "latency_ms": 100}` (refused)
- **Initial State**: `alpha: (state="CLOSED", failures=2)`
- **Evaluation**: Log ends while `alpha` is `OPEN`. Final record is at `10:00:10.000Z` ($10000\text{ms}$ after `stopped_at`).
- **Expected `stopped_periods.json` Output**:
  ```json
  {
    "alpha": [
      {
        "stopped_at": "2026-09-01T10:00:00.000Z",
        "resumed_at": null,
        "duration_ms": 10000
      }
    ]
  }
  ```
- **Rule Exercised**: `POLICY.md` §2.4

---

### Category I: Output Schema & Cardinality Invariants

#### `SCEN-I01`: Strict 1:1 Input-to-Output Line Preservation
- **Purpose**: Verify that 4 input records produce exactly 4 output records in identical sequence.
- **Configuration**: Baseline defaults.
- **Input**:
  - `{"id": "c081", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 100}`
  - `{"id": "c082", "provider": "beta", "started_at": "2026-09-01T10:00:01.000Z", "status": "error", "latency_ms": 100}`
  - `{"id": "c083", "provider": "alpha", "started_at": "2026-09-01T10:00:02.000Z", "status": "ok", "latency_ms": 100}`
  - `{"id": "c084", "provider": "beta", "started_at": "2026-09-01T10:00:03.000Z", "status": "ok", "latency_ms": 100}`
- **Expected `decisions.jsonl`**:
  ```json
  {"id":"c081","action":"attempt","provider_state":"CLOSED","reason":"healthy_call_attempt"}
  {"id":"c082","action":"retry","provider_state":"CLOSED","reason":"transient_error_retry"}
  {"id":"c083","action":"attempt","provider_state":"CLOSED","reason":"healthy_call_attempt"}
  {"id":"c084","action":"attempt","provider_state":"CLOSED","reason":"healthy_call_attempt"}
  ```
- **Rule Exercised**: `POLICY.md` §2.3

---

## 4. Top 10 Prediction-Practice Scenarios (Walkthrough Training)

The following 10 multi-step scenarios demonstrate the systematic 8-step mental reasoning rubric for predicting unseen scenarios during the instructor walkthrough:

### Practice Scenario 1: Tripping on Latency Degradation
- **Input Stream**:
  1. `{"id": "p01", "provider": "alpha", "started_at": "10:00:00.000Z", "status": "ok", "latency_ms": 5500}`
  2. `{"id": "p02", "provider": "alpha", "started_at": "10:00:01.000Z", "status": "ok", "latency_ms": 6000}`
  3. `{"id": "p03", "provider": "alpha", "started_at": "10:00:02.000Z", "status": "ok", "latency_ms": 5200}`
  4. `{"id": "p04", "provider": "alpha", "started_at": "10:00:03.000Z", "status": "ok", "latency_ms": 200}`
- **Reasoning**:
  - `p01`: `5500 > 5000` -> failure 1 -> `("attempt", "CLOSED", "slow_success_degradation")`
  - `p02`: `6000 > 5000` -> failure 2 -> `("attempt", "CLOSED", "slow_success_degradation")`
  - `p03`: `5200 > 5000` -> failure 3 $\ge 3$ -> trips `OPEN` -> `("attempt", "OPEN", "slow_success_degradation")`. Cooldown until `10:00:32`.
  - `p04`: Arrives at `10:00:03 < 10:00:32` -> refused -> `("refuse", "OPEN", "circuit_open_refusal")`.

---

### Practice Scenario 2: Error Tripping and Give-Up
- **Input Stream**:
  1. `{"id": "p11", "provider": "alpha", "started_at": "10:00:00.000Z", "status": "error", "latency_ms": 100}`
  2. `{"id": "p12", "provider": "alpha", "started_at": "10:00:01.000Z", "status": "error", "latency_ms": 100}`
  3. `{"id": "p13", "provider": "alpha", "started_at": "10:00:02.000Z", "status": "error", "latency_ms": 100}`
- **Reasoning**:
  - `p11`: failure 1 ($1 < 3$) -> `("retry", "CLOSED", "transient_error_retry")`
  - `p12`: failure 2 ($2 < 3$) -> `("retry", "CLOSED", "transient_error_retry")`
  - `p13`: failure 3 ($3 \ge 3$) -> trips `OPEN`. Retries prohibited -> `("give_up", "OPEN", "max_retries_exceeded")`.

---

### Practice Scenario 3: Single Probe Recovery
- **Input Stream**:
  1. Provider `alpha` tripped at `10:00:00.000Z` (`cooldown_until = 10:00:30.000Z`).
  2. `{"id": "p21", "provider": "alpha", "started_at": "10:00:30.000Z", "status": "ok", "latency_ms": 400}`
  3. `{"id": "p22", "provider": "alpha", "started_at": "10:00:31.000Z", "status": "ok", "latency_ms": 300}`
- **Reasoning**:
  - `p21`: Arrives at exact cooldown boundary $\ge 10:00:30$. Evaluated as probe. `status == "ok"` AND `400 <= 5000` -> probe success! State restored to `CLOSED`, failures reset to 0. Emitted: `("probe", "CLOSED", "probe_success_recovery")`.
  - `p22`: Provider is now `CLOSED` with 0 failures -> `("attempt", "CLOSED", "healthy_call_attempt")`.

---

### Practice Scenario 4: Probe Failure and Re-Tripping Cooldown
- **Input Stream**:
  1. Provider `alpha` tripped at `10:00:00.000Z` (`cooldown_until = 10:00:30.000Z`).
  2. `{"id": "p31", "provider": "alpha", "started_at": "10:00:30.000Z", "status": "timeout", "latency_ms": 5000}`
  3. `{"id": "p32", "provider": "alpha", "started_at": "10:00:40.000Z", "status": "ok", "latency_ms": 200}`
- **Reasoning**:
  - `p31`: Arrives $\ge 10:00:30$. Evaluated as probe. `timeout` -> probe failure! Re-trips `OPEN`. New cooldown until `10:01:00.000Z` ($10:00:30 + 30\text{s}$). Failures=4. Emitted: `("probe", "OPEN", "probe_failure_reopen")`.
  - `p32`: Arrives at `10:00:40 < 10:01:00` -> refused -> `("refuse", "OPEN", "circuit_open_refusal")`.

---

### Practice Scenario 5: Success Immediately Interleaving Failures
- **Input Stream**:
  1. `{"id": "p41", "provider": "alpha", "started_at": "10:00:00.000Z", "status": "error", "latency_ms": 100}`
  2. `{"id": "p42", "provider": "alpha", "started_at": "10:00:01.000Z", "status": "error", "latency_ms": 100}`
  3. `{"id": "p43", "provider": "alpha", "started_at": "10:00:02.000Z", "status": "ok", "latency_ms": 200}`
  4. `{"id": "p44", "provider": "alpha", "started_at": "10:00:03.000Z", "status": "error", "latency_ms": 100}`
- **Reasoning**:
  - `p41`: failures=1 -> `("retry", "CLOSED", "transient_error_retry")`
  - `p42`: failures=2 -> `("retry", "CLOSED", "transient_error_retry")`
  - `p43`: fast `ok` -> failures reset to 0 -> `("attempt", "CLOSED", "healthy_call_attempt")`
  - `p44`: failures=1 -> `("retry", "CLOSED", "transient_error_retry")`. Breaker remains `CLOSED`.

---

### Practice Scenario 6: Exact Cooldown Boundary Millisecond Discrimination
- **Input Stream**:
  - `alpha` tripped at `10:00:00.000Z` (`cooldown_until = 10:00:30.000Z`).
  1. `{"id": "p51", "provider": "alpha", "started_at": "10:00:29.999Z", "status": "ok", "latency_ms": 200}`
  2. `{"id": "p52", "provider": "alpha", "started_at": "10:00:30.000Z", "status": "ok", "latency_ms": 200}`
- **Reasoning**:
  - `p51`: `10:00:29.999Z < 10:00:30.000Z` -> Cooldown active -> `("refuse", "OPEN", "circuit_open_refusal")`.
  - `p52`: `10:00:30.000Z >= 10:00:30.000Z` -> Cooldown expired -> evaluated as probe -> `("probe", "CLOSED", "probe_success_recovery")`.

---

### Practice Scenario 7: Out-of-Order Timestamps with Active Breaker
- **Input Stream**:
  1. `{"id": "p61", "provider": "alpha", "started_at": "10:00:10.000Z", "status": "error", "latency_ms": 100}` (trips breaker, cooldown until `10:00:40`)
  2. `{"id": "p62", "provider": "alpha", "started_at": "10:00:05.000Z", "status": "ok", "latency_ms": 100}`
  3. `{"id": "p63", "provider": "alpha", "started_at": "10:00:40.000Z", "status": "ok", "latency_ms": 100}`
- **Reasoning**:
  - `p61`: trips breaker -> `("give_up", "OPEN", "max_retries_exceeded")`. `max_seen = 10:00:10`.
  - `p62`: timestamp is `10:00:05`. Monotonic `current_time = max(10:00:10, 10:00:05) = 10:00:10 < 10:00:40` -> `("refuse", "OPEN", "circuit_open_refusal")`.
  - `p63`: timestamp is `10:00:40`. `current_time = 10:00:40 >= 10:00:40` -> probe success -> `("probe", "CLOSED", "probe_success_recovery")`.

---

### Practice Scenario 8: Unknown Status String
- **Input Stream**:
  1. `{"id": "p71", "provider": "alpha", "started_at": "10:00:00.000Z", "status": "502_bad_gateway", "latency_ms": 100}`
  2. `{"id": "p72", "provider": "alpha", "started_at": "10:00:01.000Z", "status": "ok", "latency_ms": 100}`
- **Reasoning**:
  - `p71`: unrecognized status -> Provider Failure, unretryable -> `("attempt", "CLOSED", "unrecognized_status_failure")`. failures=1.
  - `p72`: fast `ok` -> failures reset to 0 -> `("attempt", "CLOSED", "healthy_call_attempt")`.

---

### Practice Scenario 9: Two Independent Providers Interleaved
- **Input Stream**:
  1. `{"id": "p81", "provider": "alpha", "started_at": "10:00:00.000Z", "status": "error", "latency_ms": 100}`
  2. `{"id": "p82", "provider": "beta", "started_at": "10:00:01.000Z", "status": "error", "latency_ms": 100}`
  3. `{"id": "p83", "provider": "alpha", "started_at": "10:00:02.000Z", "status": "error", "latency_ms": 100}`
  4. `{"id": "p84", "provider": "alpha", "started_at": "10:00:03.000Z", "status": "error", "latency_ms": 100}`
  5. `{"id": "p85", "provider": "beta", "started_at": "10:00:04.000Z", "status": "ok", "latency_ms": 200}`
- **Reasoning**:
  - `p81`: alpha failures=1 -> `("retry", "CLOSED", "transient_error_retry")`
  - `p82`: beta failures=1 -> `("retry", "CLOSED", "transient_error_retry")`
  - `p83`: alpha failures=2 -> `("retry", "CLOSED", "transient_error_retry")`
  - `p84`: alpha failures=3 -> trips alpha to `OPEN` -> `("give_up", "OPEN", "max_retries_exceeded")`
  - `p85`: beta fast `ok` -> beta failures reset to 0 -> `("attempt", "CLOSED", "healthy_call_attempt")`. (Alpha remains `OPEN`).

---

### Practice Scenario 10: Retries Disabled in Configuration (`max_retries = 0`)
- **Input Stream** (`max_retries: 0`):
  1. `{"id": "p91", "provider": "alpha", "started_at": "10:00:00.000Z", "status": "error", "latency_ms": 100}`
- **Reasoning**:
  - `p91`: error occurs. `failures = 1 < 3` (`state = CLOSED`). But `max_retries == 0` -> retries disabled. Emitted: `("give_up", "CLOSED", "max_retries_exceeded")`.
