# Questions and Policy Decision Matrix

## A. Assignment Questions (from BRIEF)

### 1. Delivery and Schema of Provider Stopped Periods Output
- **Question**: Does the second output showing provider stopped periods require a specific filename, file format, or pre-set schema, and how must it be generated?
- **Status**: Clear in BRIEF
- **Answer**: The BRIEF explicitly states: *"Plus a second output showing, per provider, the periods during which you would have stopped calling it. Name and shape are yours."* and *"One documented command turns an outcomes.jsonl plus your config into your outputs."* We will define the filename (`stopped_periods.json`) and data structure in `POLICY.md`, and generate both outputs with a single CLI command.
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

## B. Policy Decision Matrix (Our Decisions)

> [!IMPORTANT]
> **Status of all items below**: `PENDING REVIEW` / `RECOMMENDATION — REQUIRES REVIEW`
> Per the BRIEF, these are **our policy decisions**, not instructor mandates. No policy decision is finalized until explicitly approved.

---

### Decision 1: Failure Definition
- **Question**: What call outcome statuses classify an upstream call as a provider health failure?
- **Options considered**:
  - **Option A**: Only explicit `error` and `timeout`.
  - **Option B**: Explicit `error`, `timeout`, and slow `ok` (where `latency_ms > slow_threshold_ms`).
  - **Option C**: Only explicit `error`.
- **Advantages**:
  - *Option A*: Minimalistic, directly matches explicit failure string literals.
  - *Option B*: Realistically protects the gateway from upstream thread pool exhaustion and resource starvation caused by degraded, slow-responding model providers.
  - *Option C*: Easiest to implement, but ignores timeouts and severe latency degradation.
- **Disadvantages**:
  - *Option B* introduces a latency threshold configuration parameter (`slow_threshold_ms`) that requires boundary verification.
- **Recommendation**: **Option B** (`error`, `timeout`, and slow `ok` where `latency_ms > slow_threshold_ms`) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: In LLM gateways, an upstream provider that takes 10+ seconds to return `ok` can be just as catastrophic as an outright error. Classifying severe latency as a health failure prevents cascading gateway queue backups.
- **Trade-offs**: Adds a latency threshold parameter, but accurately models real-world API degradation.
- **Example Scenario**: Input record: `{"id": "c101", "provider": "alpha", "started_at": "...", "status": "ok", "latency_ms": 6200}` with `slow_threshold_ms: 5000`.
- **Expected Behavior**: Evaluated as a failure for provider health tracking (increments consecutive failure count), but call result is delivered as `attempt` (not retried).
- **Required Configuration Value**: `slow_threshold_ms` (integer, e.g. `5000`).
- **Mutation Risks**: Inverting operator (`>` changed to `>=` or `<`).
- **Boundary Tests Needed**: Calls with `latency_ms == slow_threshold_ms` (must be healthy) vs. `latency_ms == slow_threshold_ms + 1` (must count as failure).
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 2: Slow Success Handling & Boundary
- **Question**: If a call succeeds (`status: "ok"`) but is slow, how is the threshold boundary defined (`>` vs. `>=`), and how does the engine handle the call vs. provider health?
- **Options considered**:
  - **Option A**: Strict inequality `latency_ms > slow_threshold_ms`; call action is `attempt` (response delivered), provider failure counter increments by 1.
  - **Option B**: Non-strict inequality `latency_ms >= slow_threshold_ms`; call action is `attempt`, provider failure counter increments.
  - **Option C**: Retry the slow call to seek a faster response.
- **Advantages**:
  - *Option A*: Clear standard boundary: exactly meeting the threshold is acceptable; exceeding it is degraded. Delivering the response avoids duplicate billing and LLM token generation.
- **Disadvantages**:
  - *Option C* causes duplicate billing and non-idempotent side effects for an already fulfilled LLM prompt.
- **Recommendation**: **Option A** (Strict inequality `latency_ms > slow_threshold_ms`; deliver as `attempt`, increment failure counter) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: LLM completions are stateful, costly, and non-idempotent. Once a valid response is generated, it must be returned to the client; re-issuing a retry would be wasteful.
- **Trade-offs**: Downstream receives a high-latency response, but the gateway proactively protects future traffic.
- **Example Scenario**: `slow_threshold_ms = 5000`. Call 1: `latency_ms = 5000` -> healthy. Call 2: `latency_ms = 5001` -> degraded failure.
- **Expected Behavior**: Call 1 leaves failure counter at 0. Call 2 increments failure counter to 1, with reason `slow_success_degradation`.
- **Required Configuration Value**: `slow_threshold_ms` (integer, e.g. `5000`).
- **Mutation Risks**: Mutating `>` to `>=` or `<`.
- **Boundary Tests Needed**: Assert `latency_ms = slow_threshold_ms` produces reason `healthy_call_attempt` while `slow_threshold_ms + 1` produces `slow_success_degradation`.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 3: Failure Measurement Strategy
- **Question**: What mathematical mechanism determines when a provider is unhealthy?
- **Options considered**:
  - **Option A**: **Consecutive failure count** (counter increments on failure, resets to 0 on any fast success).
  - **Option B**: **Sliding time window count** ($N$ failures within the last $W$ seconds).
  - **Option C**: **Sliding time window rate %** ($>X\%$ failure rate over window $W$ with minimum call volume $V$).
- **Advantages**:
  - *Option A*: Extremely simple, strictly deterministic, independent of timestamp distribution/density, effortless to calculate mentally during the 10-scenario prediction walkthrough.
  - *Option B & C*: Better suited for fluctuating production traffic, but introduce sliding window state complexity, floating-point rounding bugs, and edge-case vulnerabilities in mutation tests.
- **Disadvantages**:
  - *Option A*: A single healthy response resets the failure counter. However, this creates completely unambiguous state transitions.
- **Recommendation**: **Option A** (Consecutive failure count) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Predictability and simplicity are paramount for passing mutation tests and nailing the 10 walkthrough prediction scenarios without mental calculation errors.
- **Trade-offs**: Ignores intermittent/flapping failure patterns (e.g. failure-success-failure), but guarantees rock-solid predictability.
- **Example Scenario**: Stream of calls to `alpha`: `[error, error, ok, error, error]`.
- **Expected Behavior**: Counter progression: $1 \rightarrow 2 \rightarrow 0 \rightarrow 1 \rightarrow 2$. Breaker remains `CLOSED`.
- **Required Configuration Value**: Governed by `failure_threshold`.
- **Mutation Risks**: Counter reset on success omitted or changed to decrement ($counter - 1$).
- **Boundary Tests Needed**: Test alternating sequence `[fail, ok, fail, ok]` verifying counter never reaches 2.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 4: Failure Threshold
- **Question**: How many consecutive failures are required to trip the circuit breaker from `CLOSED` to `OPEN`?
- **Options considered**:
  - **Option A**: `failure_threshold = 3` consecutive failures.
  - **Option B**: `failure_threshold = 5` consecutive failures.
  - **Option C**: `failure_threshold = 1` consecutive failure (instant trip).
- **Advantages**:
  - *Option A*: Canonical resilience engineering default: filters out transient single/double blips while reacting swiftly to real outages.
- **Disadvantages**:
  - *Option C* is overly sensitive (tripping on single blips); *Option B* delays outage containment.
- **Recommendation**: **Option A** (`failure_threshold = 3`, configurable in `config.json`) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: 3 consecutive failures is easy to track, quick to test, and standard in production gateway architectures.
- **Trade-offs**: Tunable via `config.json` without modifying code logic.
- **Example Scenario**: Provider `beta` experiences 3 consecutive timeouts at $T_1, T_2, T_3$.
- **Expected Behavior**: On the 3rd failure, the breaker trips to `OPEN`, recording `opened_at = T_3`. The 4th call at $T_4$ is refused.
- **Required Configuration Value**: `failure_threshold` (integer, e.g. `3`).
- **Mutation Risks**: Mutating `>= failure_threshold` to `>` or threshold $\pm 1$.
- **Boundary Tests Needed**: Sequences of exactly 2 failures (remains `CLOSED`), exactly 3 failures (trips `OPEN`), and 4th call (refused).
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 5: Failure Window Semantics
- **Question**: How does time windowing apply if consecutive failures are chosen?
- **Options considered**:
  - **Option A**: **Pure sequential window** (consecutive count persists across call sequence regardless of time delta until reset by a fast success or breaker trip).
  - **Option B**: **Time-decayed consecutive window** (failures expire if interval between consecutive calls exceeds $T_{\text{decay}}$).
- **Advantages**:
  - *Option A*: Eliminates time-decay ambiguity and arbitrary decay parameters; 100% deterministic across both fast streams and sparse batch logs.
- **Disadvantages**:
  - *Option B* introduces time-subtraction logic and edge cases when timestamps have long gaps.
- **Recommendation**: **Option A** (Pure sequential consecutive counting; time window parameter is unnecessary) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Maximizes determinism and removes time-drift vulnerabilities during offline log processing.
- **Trade-offs**: Two errors separated by an hour with no intervening calls still count as 2 consecutive failures.
- **Example Scenario**: Error at 10:00:00, error at 11:00:00, error at 12:00:00 (no other calls).
- **Expected Behavior**: Breaker trips `OPEN` on the 3rd error at 12:00:00.
- **Required Configuration Value**: None (pure sequential count).
- **Mutation Risks**: Inadvertent introduction of unconfigured time decay.
- **Boundary Tests Needed**: Assert consecutive failures separated by large time intervals increment counter identically to rapid bursts.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 6: Circuit Breaker Scope & Provider Isolation
- **Question**: Should circuit breaker state machines be tracked per-provider or globally across all providers?
- **Options considered**:
  - **Option A**: **Per-provider scope** (each provider maintains an isolated state machine, counter, and timers).
  - **Option B**: **Global scope** (all providers share one global state machine).
- **Advantages**:
  - *Option A*: Mandatory for multi-provider routing: an outage in `alpha` must never block healthy calls to `beta` or `gamma`.
- **Disadvantages**:
  - *Option B* would cause catastrophic blast radius, shutting down entire gateway if one provider fails.
- **Recommendation**: **Option A** (Per-provider isolation) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Upstream LLM providers are independent external vendors; isolating health tracking per provider is fundamental to gateway design.
- **Trade-offs**: Requires dictionary-based state tracking per provider ID.
- **Example Scenario**: Stream: `[alpha_err, alpha_err, alpha_err, beta_ok, alpha_call]`.
- **Expected Behavior**: `alpha` trips `OPEN` on call 3. `beta_ok` is accepted as `attempt` in `CLOSED` state. Call 5 to `alpha` is refused.
- **Required Configuration Value**: None (structural architecture).
- **Mutation Risks**: Leaking state between provider keys or using a global counter singleton.
- **Boundary Tests Needed**: Interleaved calls across multiple providers verifying state mutations in one provider never affect another.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 7: New / Unseen Provider Handling
- **Question**: What is the initial state and policy when a provider name appears for the very first time in the log?
- **Options considered**:
  - **Option A**: Initialize to `CLOSED` (healthy) with `consecutive_failures = 0`.
  - **Option B**: Initialize to `HALF_OPEN` (probe required).
  - **Option C**: Reject unknown provider.
- **Advantages**:
  - *Option A*: Optimistic discovery; allows dynamic introduction of new providers without static pre-registration.
- **Disadvantages**:
  - *Option C* requires predefined provider whitelists not specified in the BRIEF.
- **Recommendation**: **Option A** (Initialize to `CLOSED` with 0 failures) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Standard gateway behavior: new upstreams are assumed healthy until evidence shows otherwise.
- **Trade-offs**: The first call is allowed as normal traffic.
- **Example Scenario**: First appearance of provider `"deepseek"`.
- **Expected Behavior**: Provider initialized in `CLOSED` state, call processed normally as `attempt`.
- **Required Configuration Value**: None.
- **Mutation Risks**: Defaulting to `OPEN` or failing on dictionary key lookup.
- **Boundary Tests Needed**: Assert first call to an unseen provider ID starts in `CLOSED` state.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 8: OPEN / Stopped State Behavior
- **Question**: When a provider's breaker is `OPEN`, what action and state are emitted for incoming calls before cooldown expires?
- **Options considered**:
  - **Option A**: `action: "refuse"`, `provider_state: "OPEN"`, `reason: "circuit_open_refusal"`.
  - **Option B**: `action: "give_up"`.
  - **Option C**: `action: "attempt"` with fallback.
- **Advantages**:
  - *Option A*: Explicitly signals refusal upfront without touching the network, directly fulfilling the BRIEF's goal to stop hammering failing providers.
- **Disadvantages**:
  - None.
- **Recommendation**: **Option A** (`action: "refuse"`, `provider_state: "OPEN"`, `reason: "circuit_open_refusal"`) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Perfectly aligns with the BRIEF's stated outcome *"refuse it outright because we'd already decided that provider was unhealthy"*.
- **Trade-offs**: None.
- **Example Scenario**: Call arrives at $T = 15000\text{ms}$ after breaker opened at $T = 0\text{ms}$ with `cooldown_ms = 30000`.
- **Expected Behavior**: Output: `{"id": "...", "action": "refuse", "provider_state": "OPEN", "reason": "circuit_open_refusal"}`.
- **Required Configuration Value**: None beyond `cooldown_ms`.
- **Mutation Risks**: Returning `attempt` or `give_up` instead of `refuse`.
- **Boundary Tests Needed**: Assert all calls arriving during `[opened_at, opened_at + cooldown_ms - 1ms]` produce `refuse`.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 9: Cooldown Duration & Model
- **Question**: How long does a provider remain in the `OPEN` state before allowing a recovery probe, and is the duration fixed or dynamic?
- **Options considered**:
  - **Option A**: Fixed configurable duration in milliseconds (e.g. `cooldown_ms = 30000` / 30 seconds).
  - **Option B**: Dynamic exponential cooldown per consecutive trip ($cooldown = base \times 2^{trips}$).
- **Advantages**:
  - *Option A*: Clean, predictable, easily verifiable in test assertions and live walkthrough scenarios.
- **Disadvantages**:
  - *Option B* increases mental complexity during walkthrough scenario prediction.
- **Recommendation**: **Option A** (Fixed configurable duration: `cooldown_ms = 30000`) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Simplicity, absolute determinism, and direct externalization in `config.json`.
- **Trade-offs**: Does not escalate on repeated trips, but can be configured to any value.
- **Example Scenario**: Breaker trips at $T = 1000\text{ms}$ with `cooldown_ms = 30000`. Cooldown expires at $T = 31000\text{ms}$.
- **Expected Behavior**: Call at $T = 30999\text{ms}$ is refused; call at $T = 31000\text{ms}$ transitions to probing.
- **Required Configuration Value**: `cooldown_ms` (integer, e.g. `30000`).
- **Mutation Risks**: Off-by-one comparisons (`<` vs `<=`).
- **Boundary Tests Needed**: Calls at $T_{\text{cooldown}} - 1\text{ms}$ (`refuse`) vs. $T_{\text{cooldown}}$ (`probe`).
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 10: HALF_OPEN / Recovery Probe Transition
- **Question**: When does a provider transition from `OPEN` to `HALF_OPEN`, how many probe calls are admitted, and what action is assigned?
- **Options considered**:
  - **Option A**: The first call arriving at or after `current_time >= opened_at + cooldown_ms` triggers transition to `HALF_OPEN` and is designated as the single probe (`action: "probe"`). All subsequent calls while probe is pending are refused.
  - **Option B**: Allow multiple concurrent probes in `HALF_OPEN`.
  - **Option C**: Automatically transition to `CLOSED` immediately upon cooldown expiry without a probe.
- **Advantages**:
  - *Option A*: Safely tests upstream recovery with a single isolated canary request; prevents traffic surges against an impaired upstream.
- **Disadvantages**:
  - None.
- **Recommendation**: **Option A** (Single probe call on first arrival at `current_time >= opened_at + cooldown_ms`) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Classic, robust circuit breaker pattern: exactly one probe determines whether the circuit closes or reopens.
- **Trade-offs**: In sequential event log processing, the probe record's outcome directly triggers the next state transition.
- **Example Scenario**: `opened_at = 10:00:00.000Z`, `cooldown_ms = 30000`. Next call arrives at `10:00:30.000Z`.
- **Expected Behavior**: Provider state becomes `HALF_OPEN`, call action is `probe`, reason is `probe_call_attempt`.
- **Required Configuration Value**: Governed by `cooldown_ms`.
- **Mutation Risks**: Changing `>=` to `>` or allowing normal `attempt` before probe completes.
- **Boundary Tests Needed**: Call at exact millisecond `opened_at + cooldown_ms` must be `probe`.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 11: Successful Probe Handling
- **Question**: What state transitions and counter resets occur when a probe call succeeds (`status: "ok"` and `latency_ms <= slow_threshold_ms`)?
- **Options considered**:
  - **Option A**: State transitions immediately to `CLOSED`, `consecutive_failures` resets to 0, cooldown timer clears, active stopped period is closed (`resumed_at = probe_timestamp`).
  - **Option B**: Require $M$ consecutive probe successes before closing circuit.
- **Advantages**:
  - *Option A*: Clear, deterministic, instantaneous recovery; stopped period duration is precisely bounded.
- **Disadvantages**:
  - Single probe recovery could quickly trip again if provider is fluttering, but subsequent failure will immediately protect the system.
- **Recommendation**: **Option A** (Immediate recovery to `CLOSED`, reset failure counter to 0, close stopped period) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Maximum clarity and mental predictability during scenario prediction.
- **Trade-offs**: Fast recovery after one confirmed success.
- **Example Scenario**: Probe call returns `status: "ok"`, `latency_ms: 250`.
- **Expected Behavior**: Output: `action: "probe"`, `provider_state: "CLOSED"`, `reason: "probe_success_recovery"`. Next call is standard `attempt`.
- **Required Configuration Value**: None.
- **Mutation Risks**: Omitting counter reset or failing to transition state back to `CLOSED`.
- **Boundary Tests Needed**: Probe success followed by 2 errors (remains `CLOSED`) and 3rd error (trips `OPEN`).
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 12: Failed Probe Handling
- **Question**: What happens when a probe call fails (error, timeout, slow `ok`, or unknown status)?
- **Options considered**:
  - **Option A**: State transitions immediately back to `OPEN`, a new cooldown period starts from `probe_started_at + cooldown_ms`, `consecutive_failures` remains at/above threshold, stopped period continues.
  - **Option B**: Permanent disablement until manual intervention.
- **Advantages**:
  - *Option A*: Protects the upstream provider for another full cooldown window without manual operator intervention.
- **Disadvantages**:
  - None.
- **Recommendation**: **Option A** (Re-trip to `OPEN` with new cooldown starting from probe timestamp) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Standard resilient backoff: a failed probe confirms the provider is still down, warranting an extended cooldown.
- **Trade-offs**: Extends the provider stopped duration.
- **Example Scenario**: Probe call at $T = 30000\text{ms}$ returns `status: "timeout"`.
- **Expected Behavior**: Output: `action: "probe"`, `provider_state: "OPEN"`, `reason: "probe_failure_reopen"`. Next cooldown expires at $T = 60000\text{ms}$. Calls between 30001ms and 59999ms are refused.
- **Required Configuration Value**: Governed by `cooldown_ms`.
- **Mutation Risks**: Resetting cooldown timer to the original `opened_at` instead of probe timestamp.
- **Boundary Tests Needed**: Verify second cooldown period is evaluated relative to probe timestamp.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 13: Retry Count Budget
- **Question**: What is the maximum number of retries permitted for a single call?
- **Options considered**:
  - **Option A**: `max_retries = 1` (1 initial attempt + 1 retry = max 2 total executions per call).
  - **Option B**: `max_retries = 2` (1 initial + 2 retries = max 3 total executions).
  - **Option C**: `max_retries = 0` (no retries).
- **Advantages**:
  - *Option A*: Handles transient blips while strictly bounding tail latency overhead and preventing retry storms.
- **Disadvantages**:
  - None; configurable via `config.json`.
- **Recommendation**: **Option A** (`max_retries = 1`, configurable) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: 1 retry is standard for LLM gateways to handle transient blips without doubling upstream load.
- **Trade-offs**: Configurable in `config.json`.
- **Example Scenario**: Call fails with `status: "timeout"`. Previous retry count is 0.
- **Expected Behavior**: Policy action is `retry`. If that retry also fails, action becomes `give_up`.
- **Required Configuration Value**: `max_retries` (integer, e.g. `1`).
- **Mutation Risks**: Mutating `>= max_retries` to `>` or altering counter logic.
- **Boundary Tests Needed**: Assert call with 0 retries produces `retry`; call with 1 retry produces `give_up`.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 14: Retry Eligibility
- **Question**: Which call outcomes are eligible for a retry attempt?
- **Options considered**:
  - **Option A**: Retry only on transient failures (`status: "error"` or `status: "timeout"`), provided target provider is not `OPEN` and retry budget remains. Never retry `ok` (even if slow) or unrecognized statuses.
  - **Option B**: Retry all non-ok statuses including unrecognized ones.
  - **Option C**: Retry slow `ok` calls.
- **Advantages**:
  - *Option A*: Prevents duplicate billing/generation on completed requests, avoids hammering open circuits.
- **Disadvantages**:
  - None.
- **Recommendation**: **Option A** (Only transient `error` and `timeout` on healthy providers) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Retrying a completed slow request causes duplicate execution; retrying against an open circuit defeats the purpose of the breaker.
- **Trade-offs**: Strict eligibility criteria.
- **Example Scenario**: Call to `alpha` returns `status: "ok"` with `latency_ms: 6000` (`slow_threshold_ms: 5000`).
- **Expected Behavior**: Action is `attempt` (outcome accepted), NOT `retry`.
- **Required Configuration Value**: None.
- **Mutation Risks**: Allowing retries on `ok` status or when circuit is `OPEN`.
- **Boundary Tests Needed**: Assert slow `ok` produces `attempt`, never `retry`.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 15: Retry Delay & Backoff Strategy
- **Question**: How is the delay between retries calculated?
- **Options considered**:
  - **Option A**: Fixed deterministic delay (`retry_delay_ms = 1000`).
  - **Option B**: Linear backoff ($delay = base \times retry$).
  - **Option C**: Exponential backoff ($delay = base \times 2^{retry-1}$).
- **Advantages**:
  - *Option A*: Simplest, 100% deterministic, zero arithmetic rounding ambiguity during live walkthrough predictions.
- **Disadvantages**:
  - Fixed delay doesn't scale for large retry counts, but with `max_retries = 1`, fixed delay is optimal.
- **Recommendation**: **Option A** (Fixed deterministic delay: `retry_delay_ms = 1000`) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Predictability, simplicity, and direct configurability.
- **Trade-offs**: Constant delay across retries.
- **Example Scenario**: Retry scheduled for a timed-out call.
- **Expected Behavior**: Delay evaluated as exactly `1000ms`.
- **Required Configuration Value**: `retry_delay_ms` (integer, e.g. `1000`).
- **Mutation Risks**: Arithmetic operator mutations.
- **Boundary Tests Needed**: Assert retry delay matches `retry_delay_ms` exactly.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 16: Retry and Circuit Breaker Interaction
- **Question**: How do retries interact with provider health state, failure counting, and circuit breaker tripping?
- **Options considered**:
  - **Option A**: **Unified Health Accounting**:
    1. Every failed attempt/retry to a provider counts as a failure toward that provider's `consecutive_failures`.
    2. Any successful attempt/retry resets `consecutive_failures` to 0.
    3. If a call failure causes the provider to trip to `OPEN`, any pending retry for that call is aborted/refused (`give_up` / `refuse`).
    4. Refused calls (calls rejected while circuit is `OPEN`) do NOT increment `consecutive_failures` (they are dropped upfront without touching the provider).
  - **Option B**: Separate retry failures from circuit breaker health accounting.
- **Advantages**:
  - *Option A*: Fully coherent: provider health reflects every actual interaction with the upstream provider, while refused calls do not cause artificial state changes.
- **Disadvantages**:
  - Requires clear sequencing between call retry evaluation and provider state update.
- **Recommendation**: **Option A** (Unified Health Accounting) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Logically sound and defensible: if an upstream provider fails a retry, it really failed, so the failure count must increment. If a circuit is open, refusing a call does not hammer the provider, so it does not add new failures.
- **Trade-offs**: Clear, consistent interaction rules.
- **Example Scenario**: Call 1 fails (count 1, retried). Retry fails (count 2, gives up). Call 2 fails (count 3 -> trips `OPEN`). Call 3 arrives (refused, count stays 3).
- **Expected Behavior**: Call 1 produces `retry` then `give_up`. Call 2 trips breaker. Call 3 is `refuse`.
- **Required Configuration Value**: None beyond `failure_threshold` and `max_retries`.
- **Mutation Risks**: Incrementing failure counter on refused calls or omitting failure increment on retry failures.
- **Boundary Tests Needed**: Test sequence where retry failure triggers circuit breaker trip.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 17: Provider State vs. Call State Separation
- **Question**: How are per-call data, per-provider health state, and system configuration isolated?
- **Specification**:
  - **Call Level (Ephemera)**: `id`, `provider`, `started_at`, `status`, `latency_ms`, `call_retry_count`, decided `action`, decided `reason`.
  - **Provider Level (Stateful Entity)**: `provider_id`, `state` (`CLOSED`, `OPEN`, `HALF_OPEN`), `consecutive_failures`, `opened_at`, `cooldown_until`, `stopped_intervals` list.
  - **System Level (Immutable Configuration)**: `failure_threshold`, `cooldown_ms`, `slow_threshold_ms`, `max_retries`, `retry_delay_ms`.
- **Advantages**:
  - Clean separation of concerns; eliminates global state leakage and thread/instance coupling.
- **Recommendation**: Adopt this strict 3-tier hierarchy — `RECOMMENDATION — REQUIRES REVIEW`.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 18: Unknown / Unrecognized Status Handling
- **Question**: What should the engine do if a record arrives with an unrecognized status (not `ok`, `error`, `timeout`)?
- **Options considered**:
  - **Option A**: Treat as an unretryable failure (increments provider consecutive failure count, returns `action: "attempt"`, `reason: "unrecognized_status_failure"`).
  - **Option B**: Raise an unhandled exception / crash.
  - **Option C**: Ignore/drop the record.
- **Advantages**:
  - *Option A*: Preserves 1:1 input/output line cardinality, handles anomalous data safely without crashing, and protects the system by treating unknown signals as failures.
- **Disadvantages**:
  - None.
- **Recommendation**: **Option A** (Treat as unretryable failure, preserve 1:1 ordering) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: The BRIEF warns that unrecognized statuses will appear and strictly mandates 1:1 input-to-output record mapping.
- **Trade-offs**: Unknown statuses degrade provider health.
- **Example Scenario**: Input `{"id": "c999", "status": "rate_limited_429", "latency_ms": 100}`.
- **Expected Behavior**: Output `action: "attempt"`, `reason: "unrecognized_status_failure"`, failure counter increments by 1.
- **Required Configuration Value**: None.
- **Mutation Risks**: Treating unknown statuses as `ok` or crashing.
- **Boundary Tests Needed**: Pass unknown status string and assert output line generated with failure count increment.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 19: Out-of-Order Timestamps Handling
- **Question**: How should the engine handle logs where `started_at` timestamps are non-chronological or out-of-order?
- **Options considered**:
  - **Option A**: **Arrival order processing** (process records strictly in the order they appear in `outcomes.jsonl`; evaluate cooldowns against monotonic maximum observed timestamp: `current_time = max(max_seen_timestamp, record_timestamp)`).
  - **Option B**: Pre-sort all records by timestamp in memory.
  - **Option C**: Reject out-of-order records.
- **Advantages**:
  - *Option A*: Strictly preserves the required 1:1 input-order matching in `decisions.jsonl` without reordering overhead. Monotonic timestamp tracking prevents time from moving backward during cooldown evaluation.
- **Disadvantages**:
  - None.
- **Recommendation**: **Option A** (Process in arrival order with monotonic time tracking) — `RECOMMENDATION — REQUIRES REVIEW`.
- **Reason**: Satisfies the hard requirement that `decisions.jsonl` must be generated in exact input order.
- **Trade-offs**: State transitions reflect stream arrival sequence.
- **Example Scenario**: Record 1 at 10:00:05, Record 2 at 10:00:01.
- **Expected Behavior**: Record 1 processed first, Record 2 processed second in output.
- **Required Configuration Value**: None.
- **Mutation Risks**: Reordering output lines or regressing cooldown timers.
- **Boundary Tests Needed**: Pass non-monotonic timestamp inputs and assert output preserves exact input sequence.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 20: Controlled Action Vocabulary
- **Question**: What is the exact, fixed vocabulary for the `action` field in `decisions.jsonl`?
- **Vocabulary**:
  - `attempt`: Normal execution of an API call to a healthy provider.
  - `retry`: Re-issuing an eligible failed call within retry budget.
  - `give_up`: Abandoning further execution after retry exhaustion or non-retryable failure.
  - `refuse`: Rejecting a call upfront because provider circuit is `OPEN`.
  - `probe`: Test call admitted during `HALF_OPEN` state after cooldown expiry.
- **Reason**: Covers all 4 outcomes mentioned in the BRIEF plus the canonical circuit-breaker probe state.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 21: Controlled Provider State Vocabulary
- **Question**: What is the exact, fixed vocabulary for the `provider_state` field in `decisions.jsonl`?
- **Vocabulary**:
  - `CLOSED`: Provider is healthy; normal traffic flows.
  - `OPEN`: Provider is unhealthy; calls are refused.
  - `HALF_OPEN`: Cooldown expired; provider is evaluating a single probe call.
- **Reason**: Standard, mathematically rigorous 3-state Circuit Breaker model.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW

---

### Decision 22: Controlled Reason Vocabulary
- **Question**: What is the exact, fixed vocabulary for the `reason` field in `decisions.jsonl`?
- **Vocabulary**:
  - `healthy_call_attempt`: Normal call executed to a healthy provider.
  - `probe_call_attempt`: Probe call executed during `HALF_OPEN` state.
  - `probe_success_recovery`: Successful probe restoring provider to `CLOSED`.
  - `probe_failure_reopen`: Failed probe tripping provider back to `OPEN`.
  - `circuit_open_refusal`: Call refused because provider circuit is currently `OPEN`.
  - `transient_error_retry`: Call failed with error and is eligible for retry.
  - `timeout_retry`: Call timed out and is eligible for retry.
  - `max_retries_exceeded`: Call failed after exhausting all allowed retries.
  - `slow_success_degradation`: Call succeeded but exceeded latency threshold.
  - `unrecognized_status_failure`: Unrecognized status handled as unretryable failure.
- **Reason**: Deterministic, human- and machine-readable explanation taxonomy covering every decision branch.
- **Source**: Our policy analysis
- **Status**: PENDING REVIEW
