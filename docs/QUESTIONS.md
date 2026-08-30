# Questions and Policy Decision Matrix

## A. Assignment Questions (from BRIEF)

### 1. Delivery and Schema of Provider Stopped Periods Output
- **Question**: Does the second output showing provider stopped periods require a specific filename, file format, or pre-set schema, and how must it be generated?
- **Status**: Clear in BRIEF
- **Answer**: The BRIEF explicitly states: *"Plus a second output showing, per provider, the periods during which you would have stopped calling it. Name and shape are yours."* and *"One documented command turns an outcomes.jsonl plus your config into your outputs."* We define the filename (`stopped_periods.json`) and data structure in `POLICY.md`, and generate both outputs with a single CLI command.
- **Source**: BRIEF

### 2. Dependencies and Execution Environment
- **Question**: Are third-party Python packages permitted in `requirements.txt`?
- **Status**: Clear in BRIEF
- **Answer**: Standard third-party Python libraries (such as `pydantic` or `pytest`) are permitted as long as `pip install -r requirements.txt` followed by `pytest` executes successfully from the repo root on a clean clone, with zero network calls and zero database interactions.
- **Source**: BRIEF

### 3. Record Cardinality and Sequencing in `decisions.jsonl`
- **Question**: Can the engine reorder, omit, or batch decisions when writing `decisions.jsonl`?
- **Status**: Clear in BRIEF
- **Answer**: No. The BRIEF strictly mandates: *"`decisions.jsonl`, exactly one line per input record, in input order."* No filtering, batching, or reordering is allowed.
- **Source**: BRIEF

---

## B. Approved Policy Decisions

> [!NOTE]
> All items below represent our finalized, approved policy design. Per the BRIEF, these are **our policy decisions**, not instructor mandates.

---

### Decision 1: Failure Definition
- **Question**: What call outcome statuses classify an upstream call as a provider health failure?
- **Options considered**:
  - **Option A**: Only explicit `error` and `timeout`.
  - **Option B**: Explicit `error`, `timeout`, and slow `ok` (where `latency_ms > slow_threshold_ms`).
  - **Option C**: Only explicit `error`.
- **Final Decision**: **Option B** (`error`, `timeout`, and slow `ok` where `latency_ms > slow_threshold_ms`).
- **Why**: In LLM gateways, an upstream provider that takes excessive time to return `ok` causes thread starvation and queue backups. Treating severe latency as a health failure prevents cascading gateway outages.
- **Trade-offs**: Adds a latency threshold configuration parameter (`slow_threshold_ms`), but accurately models real-world API degradation.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 2: Slow Success Handling & Boundary
- **Question**: If a call succeeds (`status: "ok"`) but is slow, how is the threshold boundary defined (`>` vs. `>=`), and how does the engine handle the call vs. provider health?
- **Options considered**:
  - **Option A**: Strict inequality `latency_ms > slow_threshold_ms`; call action is `attempt` (response delivered), provider failure counter increments by 1.
  - **Option B**: Non-strict inequality `latency_ms >= slow_threshold_ms`; call action is `attempt`, provider failure counter increments.
  - **Option C**: Retry the slow call to seek a faster response.
- **Final Decision**: **Option A** (Strict inequality `latency_ms > slow_threshold_ms`; deliver as `attempt`, increment failure counter).
- **Why**: LLM completions are stateful, costly, and non-idempotent. Once a valid response is generated, it must be returned to the client; re-issuing a retry would be wasteful and duplicate billing.
- **Trade-offs**: Downstream receives a high-latency response, but the gateway proactively protects future traffic.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 3: Failure Measurement Strategy
- **Question**: What mathematical mechanism determines when a provider is unhealthy?
- **Options considered**:
  - **Option A**: **Consecutive failure count** (counter increments on failure, resets to 0 on any fast success).
  - **Option B**: **Sliding time window count** ($N$ failures within the last $W$ seconds).
  - **Option C**: **Sliding time window rate %** ($>X\%$ failure rate over window $W$ with minimum volume $V$).
- **Final Decision**: **Option A** (Consecutive failure count).
- **Why**: Maximizes determinism, testability, and predictability during the live walkthrough prediction scenarios without mental calculation errors.
- **Trade-offs**: Less sensitive to intermittent flapping errors, but guarantees rock-solid predictability and zero state ambiguity.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 4: Failure Threshold
- **Question**: How many consecutive failures are required to trip the circuit breaker from `CLOSED` to `OPEN`?
- **Options considered**:
  - **Option A**: `failure_threshold = 3` consecutive failures.
  - **Option B**: `failure_threshold = 5` consecutive failures.
  - **Option C**: `failure_threshold = 1` consecutive failure (instant trip).
- **Final Decision**: **Option A** (`failure_threshold = 3`, configurable in `config.json`).
- **Why**: 3 consecutive failures is canonical resilience engineering standard: filters out transient single blips while quickly reacting to sustained outages.
- **Trade-offs**: Tunable via `config.json` without modifying code logic.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 5: Failure Window Semantics
- **Question**: How does time windowing apply if consecutive failures are chosen?
- **Options considered**:
  - **Option A**: **Pure sequential window** (consecutive count persists across call sequence regardless of time delta until reset by a fast success or breaker trip).
  - **Option B**: **Time-decayed consecutive window** (failures expire if interval between consecutive calls exceeds $T_{\text{decay}}$).
- **Final Decision**: **Option A** (Pure sequential consecutive counting; time window parameter is unnecessary).
- **Why**: Maximizes determinism and removes time-drift vulnerabilities during offline log processing.
- **Trade-offs**: Consecutive failures separated by large time gaps still count if no success intervened.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 6: Circuit Breaker Scope & Provider Isolation
- **Question**: Should circuit breaker state machines be tracked per-provider or globally across all providers?
- **Options considered**:
  - **Option A**: **Per-provider scope** (each provider maintains an isolated state machine, counter, and timers).
  - **Option B**: **Global scope** (all providers share one global state machine).
- **Final Decision**: **Option A** (Per-provider isolation).
- **Why**: Upstream LLM providers fail independently; an outage in provider `alpha` must never disrupt healthy calls to provider `beta`.
- **Trade-offs**: Requires dictionary-based state tracking per provider ID.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 7: New / Unseen Provider Handling
- **Question**: What is the initial state and policy when a provider name appears for the very first time in the log?
- **Options considered**:
  - **Option A**: Initialize to `CLOSED` (healthy) with `consecutive_failures = 0`.
  - **Option B**: Initialize to `HALF_OPEN` (probe required).
  - **Option C**: Reject unknown provider.
- **Final Decision**: **Option A** (Initialize to `CLOSED` with 0 failures).
- **Why**: Standard gateway behavior: new upstreams are assumed healthy until evidence shows otherwise.
- **Trade-offs**: The first call is allowed as normal traffic.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 8: OPEN / Stopped State Behavior
- **Question**: When a provider's breaker is `OPEN`, what action and state are emitted for incoming calls before cooldown expires?
- **Options considered**:
  - **Option A**: `action: "refuse"`, `provider_state: "OPEN"`, `reason: "circuit_open_refusal"`.
  - **Option B**: `action: "give_up"`.
  - **Option C**: `action: "attempt"` with fallback.
- **Final Decision**: **Option A** (`action: "refuse"`, `provider_state: "OPEN"`, `reason: "circuit_open_refusal"`).
- **Why**: Directly satisfies the BRIEF's stated outcome *"refuse it outright because we'd already decided that provider was unhealthy"*. Refused calls do not hammer the provider and do not alter failure counters.
- **Trade-offs**: None.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 9: Cooldown Duration & Model
- **Question**: How long does a provider remain in the `OPEN` state before allowing a recovery probe, and is the duration fixed or dynamic?
- **Options considered**:
  - **Option A**: Fixed configurable duration in milliseconds (e.g. `cooldown_ms = 30000` / 30 seconds).
  - **Option B**: Dynamic exponential cooldown per consecutive trip ($cooldown = base \times 2^{trips}$).
- **Final Decision**: **Option A** (Fixed configurable duration: `cooldown_ms = 30000`).
- **Why**: Simplicity, absolute determinism, and direct externalization in `config.json`.
- **Trade-offs**: Non-escalating cooldown, but configurable.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 10: HALF_OPEN / Recovery Probe Transition (Sequential Model)
- **Question**: When does a provider transition from `OPEN` to `HALF_OPEN`, how is the probe selected, and how is it evaluated in a sequential log?
- **Options considered**:
  - **Option A**: The first call arriving at or after `record.started_at >= cooldown_until` transitions the provider to `HALF_OPEN` and is immediately evaluated as the single probe (`action: "probe"`). Its outcome immediately determines whether the provider recovers to `CLOSED` or re-trips to `OPEN`.
  - **Option B**: Allow concurrent asynchronous probes.
- **Final Decision**: **Option A** (Single probe call evaluated sequentially on arrival).
- **Why**: Perfectly aligns with the discrete sequential log model: eliminates imaginary concurrency and race conditions while strictly enforcing canary recovery.
- **Trade-offs**: In sequential event log processing, the probe record's outcome directly dictates the next state transition.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 11: Successful Probe Handling
- **Question**: What state transitions and counter resets occur when a probe call succeeds (`status: "ok"` and `latency_ms <= slow_threshold_ms`)?
- **Options considered**:
  - **Option A**: State transitions immediately to `CLOSED`, `consecutive_failures` resets to 0, cooldown timer clears, active stopped period is closed (`resumed_at = record.started_at`).
  - **Option B**: Require $M$ consecutive probe successes before closing circuit.
- **Final Decision**: **Option A** (Immediate recovery to `CLOSED`, reset failure counter to 0, close stopped period).
- **Why**: Clean, instantaneous recovery; stopped period duration is precisely bounded.
- **Trade-offs**: Fast recovery after one confirmed success.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 12: Failed Probe Handling
- **Question**: What happens when a probe call fails (error, timeout, slow `ok`, or unknown status)?
- **Options considered**:
  - **Option A**: State transitions immediately back to `OPEN`, a new cooldown period starts from `probe_started_at + cooldown_ms`, `consecutive_failures` increments, stopped period continues uninterrupted.
  - **Option B**: Permanent disablement until manual intervention.
- **Final Decision**: **Option A** (Re-trip to `OPEN` with new cooldown starting from probe timestamp).
- **Why**: Standard resilient backoff: a failed probe confirms the provider is still down, warranting an extended cooldown.
- **Trade-offs**: Extends the provider stopped duration.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 13: Retrospective Retry Semantics & Budget
- **Question**: How does the engine decide `action: "retry"` vs. `action: "give_up"` on historical call records using only the fixed BRIEF schema?
- **Options considered**:
  - **Option A**: When an individual call in the log fails with a transient error/timeout: if `max_retries >= 1` and the failure did not trip the circuit to `OPEN`, the engine decides `action: "retry"`. If `max_retries == 0` or the failure tripped the circuit to `OPEN`, the engine decides `action: "give_up"`.
  - **Option B**: Require an extra `call_retries` input field not in the BRIEF.
- **Final Decision**: **Option A** (Pure retrospective decision based on config and breaker state).
- **Why**: Fully compatible with the fixed BRIEF schema; does not assume nonexistent input fields.
- **Trade-offs**: Configurable via `max_retries` in `config.json`.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 14: Retry Eligibility
- **Question**: Which call outcomes are eligible for a retry attempt?
- **Options considered**:
  - **Option A**: Retry only on transient failures (`status: "error"` or `status: "timeout"`), provided target provider is `CLOSED` and retry budget remains. Never retry `ok` (even if slow) or unrecognized statuses.
  - **Option B**: Retry all non-ok statuses including unrecognized ones.
  - **Option C**: Retry slow `ok` calls.
- **Final Decision**: **Option A** (Only transient `error` and `timeout` on healthy `CLOSED` providers).
- **Why**: Retrying a completed slow request causes duplicate execution; retrying against an open circuit defeats the purpose of the breaker.
- **Trade-offs**: Strict eligibility rules.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 15: Retry Delay & Backoff Strategy
- **Question**: How is the delay between retries calculated?
- **Options considered**:
  - **Option A**: Fixed deterministic delay (`retry_delay_ms = 1000`).
  - **Option B**: Linear backoff ($delay = base \times retry$).
  - **Option C**: Exponential backoff ($delay = base \times 2^{retry-1}$).
- **Final Decision**: **Option A** (Fixed deterministic delay: `retry_delay_ms = 1000`).
- **Why**: Simplest, 100% deterministic, zero arithmetic or rounding ambiguity in live walkthrough predictions.
- **Trade-offs**: Constant delay across retries.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 16: Retry and Circuit Breaker Interaction (Unified Health Accounting)
- **Question**: How do retries interact with provider health state, failure counting, and circuit breaker tripping?
- **Options considered**:
  - **Option A**: **Unified Health Accounting**:
    1. Every failed call in the log increments the provider's `consecutive_failures` counter.
    2. Any fast `ok` resets `consecutive_failures` to 0.
    3. If a failure causes `consecutive_failures` to reach `failure_threshold`, the circuit trips `OPEN` and the call action is `give_up`.
    4. Refused calls do NOT touch the provider and do NOT increment `consecutive_failures`.
  - **Option B**: Separate retry failures from circuit breaker health accounting.
- **Final Decision**: **Option A** (Unified Health Accounting).
- **Why**: Fully coherent: provider health reflects every actual interaction with the upstream provider, while refused calls do not cause artificial state changes.
- **Trade-offs**: Clear, consistent interaction rules.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 17: Provider State vs. Call State Separation & `provider_state` Semantics
- **Question**: What does `provider_state` represent in `decisions.jsonl`?
- **Final Decision**:
  - **`provider_state`**: Represents the provider's **resulting health state AFTER evaluating the record**.
  - **3-Tier Hierarchy**:
    - **Call Level (Ephemera)**: `id`, `provider`, `started_at`, `status`, `latency_ms`, decided `action`, decided `reason`.
    - **Provider Level (Stateful Entity)**: `provider_id`, `state` (`CLOSED`, `OPEN`, `HALF_OPEN`), `consecutive_failures`, `opened_at`, `cooldown_until`, `stopped_intervals` list.
    - **System Level (Immutable Configuration)**: `failure_threshold`, `cooldown_ms`, `slow_threshold_ms`, `max_retries`, `retry_delay_ms`.
- **Why**: Eliminates all ambiguity in output logs and cleanly decouples call ephemera from provider lifecycle state.
- **Trade-offs**: Clear modular structure.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 18: Unknown / Unrecognized Status Handling
- **Question**: What should the engine do if a record arrives with an unrecognized status (not `ok`, `error`, `timeout`)?
- **Options considered**:
  - **Option A**: Treat as an unretryable failure (increments provider consecutive failure count, returns `action: "attempt"`, `reason: "unrecognized_status_failure"`).
  - **Option B**: Raise an unhandled exception / crash.
  - **Option C**: Ignore/drop the record.
- **Final Decision**: **Option A** (Treat as unretryable failure, preserve 1:1 ordering).
- **Why**: Preserves 1:1 input/output line cardinality, handles anomalous data safely without crashing, and protects the system by treating unknown signals as failures.
- **Trade-offs**: Unknown statuses degrade provider health.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 19: Out-of-Order Timestamps Handling
- **Question**: How should the engine handle logs where `started_at` timestamps are non-chronological or out-of-order?
- **Options considered**:
  - **Option A**: **Arrival order processing** (process records strictly in arrival order; evaluate cooldowns against monotonic maximum observed timestamp: `current_time = max(max_seen_timestamp, record_timestamp)`).
  - **Option B**: Pre-sort all records by timestamp in memory.
  - **Option C**: Reject out-of-order records.
- **Final Decision**: **Option A** (Process in arrival order with monotonic time tracking).
- **Why**: Strictly preserves the required 1:1 input-order matching in `decisions.jsonl` without reordering overhead. Monotonic timestamp tracking prevents time from moving backward during cooldown evaluation.
- **Trade-offs**: State transitions reflect stream arrival sequence.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 20: Controlled Action Vocabulary
- **Question**: What is the exact, fixed vocabulary for the `action` field in `decisions.jsonl`?
- **Final Decision**:
  - `attempt`: Normal execution of an API call to a provider.
  - `retry`: Policy recommends re-issuing this failed call.
  - `give_up`: Policy recommends abandoning further retries.
  - `refuse`: Rejecting a call upfront because provider circuit is `OPEN`.
  - `probe`: Canary test call evaluating provider recovery.
- **Why**: Exhaustive vocabulary covering all required actions.
- **Trade-offs**: Fixed vocabulary.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 21: Controlled Provider State Vocabulary
- **Question**: What is the exact, fixed vocabulary for the `provider_state` field in `decisions.jsonl`?
- **Final Decision**:
  - `CLOSED`: Provider is healthy; normal traffic flows.
  - `OPEN`: Provider is unhealthy; calls are refused.
  - `HALF_OPEN`: Cooldown expired; provider is evaluating a single probe call.
- **Why**: Mathematically sound 3-state Circuit Breaker model.
- **Trade-offs**: Fixed vocabulary.
- **Source**: Our policy decision
- **Status**: Approved

---

### Decision 22: Controlled Reason Vocabulary
- **Question**: What is the exact, fixed vocabulary for the `reason` field in `decisions.jsonl`?
- **Final Decision**:
  - `healthy_call_attempt`: Call succeeded within latency limits.
  - `slow_success_degradation`: Call succeeded but exceeded `slow_threshold_ms`.
  - `transient_error_retry`: Transient error eligible for retry.
  - `timeout_retry`: Timeout eligible for retry.
  - `max_retries_exceeded`: Call failed and cannot be retried (circuit open or retry budget 0).
  - `circuit_open_refusal`: Call refused due to active breaker cooldown.
  - `probe_success_recovery`: Probe succeeded; circuit restored to healthy.
  - `probe_failure_reopen`: Probe failed; breaker re-tripped to open.
  - `unrecognized_status_failure`: Unrecognized status handled as unretryable failure.
- **Why**: Deterministic, human- and machine-readable explanation taxonomy covering every decision branch.
- **Trade-offs**: Fixed vocabulary.
- **Source**: Our policy decision
- **Status**: Approved
