# Questions and Policy Decision Matrix

## A. Assignment Questions (from BRIEF)

### 1. Delivery and Schema of Provider Stopped Periods Output
- **Question**: Does the second output showing provider stopped periods require a specific filename, file format, or pre-set schema, and how must it be generated?
- **Status**: Clear in BRIEF
- **Answer**: The BRIEF explicitly states: *"Plus a second output showing, per provider, the periods during which you would have stopped calling it. Name and shape are yours."* and *"One documented command turns an outcomes.jsonl plus your config into your outputs."* We define the filename and data structure in `POLICY.md`, and generate both outputs with a single CLI command.
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

> [!NOTE]
> All items below represent our policy design framework. Per the BRIEF, these are **our policy decisions**, not instructor mandates.

---

### Decision 1: Failure Definition
- **Question**: What call outcome statuses classify an upstream call as a failure for circuit breaker tracking?
- **Options**:
  - **Option A**: Only explicit `error` and `timeout`.
  - **Option B**: Explicit `error`, `timeout`, and slow `ok` (where `latency_ms > slow_threshold_ms`).
  - **Option C**: Only explicit `error`.
- **Advantages**:
  - *Option A*: Simple, directly maps to discrete status strings.
  - *Option B*: Realistically protects the gateway from degraded upstream providers that respond with `ok` but take an excessive amount of time, causing thread starvation.
  - *Option C*: Narrowest scope, but fails to handle timeouts and degraded providers.
- **Disadvantages**:
  - *Option B* requires introducing a configurable latency threshold parameter (`slow_threshold_ms`).
- **Recommended Option**: **Option B** (`error`, `timeout`, and slow `ok` where `latency_ms > slow_threshold_ms`).
- **Reason**: Upstream LLM providers often suffer from degraded generation latency rather than immediate hard errors. Treating pathological latency as a health failure prevents gateway queue buildup.
- **Trade-offs**: Slightly more complex evaluation logic, but provides authentic circuit breaker behavior.
- **Example Scenario**: A call returns `status: "ok"` with `latency_ms: 6500` when `slow_threshold_ms = 5000`.
- **Expected Behavior**: Evaluated as a failure for circuit breaker health counting, but not retried (since response was already delivered).
- **Required Configuration Value**: `slow_threshold_ms` (integer, e.g. `5000`).
- **Mutation Risks**: Mutation of `latency_ms > slow_threshold_ms` to `>=` or `<`.
- **Boundary Tests Needed**: Calls with `latency_ms == slow_threshold_ms` (must be healthy) and `latency_ms == slow_threshold_ms + 1` (must be treated as failure).
- **Source**: Our policy decision

---

### Decision 2: Slow Success Handling
- **Question**: When a call succeeds (`status: "ok"`) but is slow (`latency_ms > slow_threshold_ms`), how should the engine act on the call itself vs. provider health?
- **Options**:
  - **Option A**: Call action is `attempt` (outcome accepted), but provider consecutive failure count increments.
  - **Option B**: Call action is `retry` to get a faster response.
  - **Option C**: Call action is `give_up`.
- **Advantages**:
  - *Option A*: Does not perform redundant duplicate LLM executions when a valid response was already received, while still tracking provider degradation.
- **Disadvantages**:
  - *Option B* wastes tokens and compute on duplicate generations.
- **Recommended Option**: **Option A** (`action: "attempt"`, outcome accepted, consecutive failure count increments).
- **Reason**: LLM calls are expensive and stateful; re-executing an already successful call produces duplicate side effects.
- **Trade-offs**: Downstream receives a slow response, but gateway protects future traffic.
- **Example Scenario**: Input `{"id":"c101","status":"ok","latency_ms":5500}` with `slow_threshold_ms: 5000`.
- **Expected Behavior**: Output `action: "attempt"`, `provider_state: "CLOSED"`, `reason: "slow_success_degradation"`. Provider failure counter increments by 1.
- **Required Configuration Value**: Governed by `slow_threshold_ms`.
- **Mutation Risks**: Inverting check to reset failure counter instead of incrementing.
- **Boundary Tests Needed**: Verify failure counter increments on slow `ok` and does NOT trigger a retry.
- **Source**: Our policy decision

---

### Decision 3: Failure Metric Strategy
- **Question**: What mathematical metric determines when a provider's circuit opens?
- **Options**:
  - **Option A**: **Consecutive failure count** (counter increments on failure, resets to 0 on any fast success).
  - **Option B**: **Sliding time window failure count** ($N$ failures in past $W$ seconds).
  - **Option C**: **Sliding time window failure rate %** ($>X\%$ failure rate over window with minimum volume).
- **Advantages**:
  - *Option A*: Extremely simple, strictly deterministic, completely independent of timestamp density, easy to calculate mentally during the 10-scenario prediction walkthrough.
  - *Option B & C*: More flexible for high-throughput fluctuating traffic, but highly complex, prone to window boundary bugs and float rounding issues in mutation tests.
- **Disadvantages**:
  - *Option A*: A single healthy call resets the failure counter, but this makes state transitions completely unambiguous.
- **Recommended Option**: **Option A** (Consecutive failure count).
- **Reason**: Maximizes determinism, testability, and predictability during the live prediction walkthrough.
- **Trade-offs**: Less sensitive to intermittent fluttering errors, but robust and zero-defect verifiable.
- **Example Scenario**: Calls: `error` (count 1), `error` (count 2), `ok` (count resets to 0), `error` (count 1).
- **Expected Behavior**: Breaker remains `CLOSED` because failures were not consecutive.
- **Required Configuration Value**: `failure_threshold` (integer, e.g. `3`).
- **Mutation Risks**: Counter reset omitted on success or incrementing on success.
- **Boundary Tests Needed**: Sequence `[failure, failure, success, failure, failure]` verifying breaker remains `CLOSED`.
- **Source**: Our policy decision

---

### Decision 4: Failure Threshold
- **Question**: How many consecutive failures are required to trip the circuit breaker to `OPEN`?
- **Options**:
  - **Option A**: 3 consecutive failures.
  - **Option B**: 5 consecutive failures.
  - **Option C**: 1 failure (instant trip).
- **Advantages**:
  - *Option A*: Industry standard balance: filters out transient single blips while quickly reacting to sustained outages.
- **Disadvantages**:
  - *Option C* causes hyperactive tripping; *Option B* delays outage isolation.
- **Recommended Option**: **Option A** (`failure_threshold = 3`, configurable in `config.json`).
- **Reason**: 3 consecutive failures is clean, easy to mentally track in scenarios, and effectively isolates down providers.
- **Trade-offs**: Tunable via `config.json` without modifying logic.
- **Example Scenario**: Provider `alpha` experiences 3 consecutive timeouts.
- **Expected Behavior**: On the 3rd failure, the breaker trips to `OPEN`, recording `opened_at` timestamp. The 4th call is refused.
- **Required Configuration Value**: `failure_threshold` (integer, e.g. `3`).
- **Mutation Risks**: Changing `>= failure_threshold` to `> failure_threshold` or modifying default threshold.
- **Boundary Tests Needed**: Test with exactly 2 failures (remains `CLOSED`), exactly 3 failures (trips to `OPEN`), and 4th call (refused).
- **Source**: Our policy decision

---

### Decision 5: Failure Evaluation Window
- **Question**: Over what time window is the consecutive failure metric evaluated?
- **Options**:
  - **Option A**: **Continuous sequence window** (consecutive count persists across call sequence until a healthy call or breaker trip occurs).
  - **Option B**: **Time-bounded consecutive window** (failures expire if more than $T$ seconds pass between calls).
- **Advantages**:
  - *Option A*: Eliminates time-decay ambiguity, perfectly deterministic across sparse or batch logs.
- **Disadvantages**:
  - *Option B* adds timestamp subtraction logic that can introduce boundary mutations.
- **Recommended Option**: **Option A** (Continuous sequence window based on consecutive calls).
- **Reason**: Keeps the state machine pure, deterministic, and easily predictable.
- **Trade-offs**: Consecutive failures separated by time still count if no success occurred between them.
- **Example Scenario**: Two errors separated by 1 hour, followed immediately by a third error.
- **Expected Behavior**: Breaker trips on the 3rd error.
- **Required Configuration Value**: None beyond `failure_threshold`.
- **Mutation Risks**: Inadvertent time-decay logic insertion.
- **Boundary Tests Needed**: Sequential errors with varying time deltas verifying unbroken counting.
- **Source**: Our policy decision

---

### Decision 6: Circuit Breaker Scope
- **Question**: Should circuit breaker state machines be tracked per-provider or globally?
- **Options**:
  - **Option A**: **Per-provider scope** (each provider has an isolated FSM).
  - **Option B**: **Global scope** (all providers share one state machine).
- **Advantages**:
  - *Option A*: Essential for multi-provider routing: an outage in `alpha` does not disrupt healthy calls to `beta`.
- **Disadvantages**:
  - *Option B* would shut down all providers if one fails, violating basic gateway design.
- **Recommended Option**: **Option A** (Per-provider scope).
- **Reason**: Mandatory for real-world reliability; upstream providers fail independently.
- **Trade-offs**: State is maintained in a provider-keyed dictionary.
- **Example Scenario**: `alpha` fails 3 times and trips `OPEN`. `beta` receives a call.
- **Expected Behavior**: Call to `beta` is allowed (`attempt`) and `beta` state is `CLOSED`. Call to `alpha` is refused.
- **Required Configuration Value**: None (structural architecture).
- **Mutation Risks**: Global state leakage or sharing state instances between provider keys.
- **Boundary Tests Needed**: Interleaved calls `[alpha_err, beta_ok, alpha_err, beta_ok, alpha_err]` verifying `alpha` is `OPEN` while `beta` remains `CLOSED`.
- **Source**: Our policy decision

---

### Decision 7: New / Unseen Provider Behavior
- **Question**: What initial state and policy assumptions apply when a call is encountered for a provider not seen before?
- **Options**:
  - **Option A**: Initialize to `CLOSED` (healthy) with consecutive failures = 0.
  - **Option B**: Initialize to `HALF_OPEN` (probe required).
  - **Option C**: Reject unknown provider.
- **Advantages**:
  - *Option A*: Optimistic discovery; allows seamless addition of new providers without prior registration.
- **Disadvantages**:
  - *Option C* requires predefined provider whitelists not specified in the BRIEF.
- **Recommended Option**: **Option A** (Initialize to `CLOSED` with 0 failures).
- **Reason**: Standard gateway behavior: new upstreams are assumed healthy until evidence shows otherwise.
- **Trade-offs**: First call is allowed as normal traffic.
- **Example Scenario**: First appearance of provider `"gamma"`.
- **Expected Behavior**: Provider state initialized to `CLOSED`, call evaluated as `attempt`.
- **Required Configuration Value**: None.
- **Mutation Risks**: Defaulting to `OPEN` or failing on dictionary key lookup.
- **Boundary Tests Needed**: Assert first call to a new provider name starts in `CLOSED` state.
- **Source**: Our policy decision

---

### Decision 8: OPEN / Stopped State Behavior
- **Question**: When a provider's breaker is `OPEN`, what action is returned for incoming calls before cooldown expires?
- **Options**:
  - **Option A**: `action: "refuse"`, `provider_state: "OPEN"`, `reason: "circuit_open_refusal"`.
  - **Option B**: `action: "give_up"`.
  - **Option C**: `action: "attempt"` with fallback.
- **Advantages**:
  - *Option A*: Explicitly signals refusal upfront without touching the network, directly fulfilling the BRIEF's goal to stop hammering.
- **Disadvantages**:
  - None.
- **Recommended Option**: **Option A** (`action: "refuse"`, `provider_state: "OPEN"`).
- **Reason**: Clear, unambiguous vocabulary and aligns directly with the BRIEF's requirement to refuse unhealthy provider calls.
- **Trade-offs**: None.
- **Example Scenario**: Call arrives 10 seconds after breaker tripped with `cooldown_ms = 30000`.
- **Expected Behavior**: Output: `{"id": "...", "action": "refuse", "provider_state": "OPEN", "reason": "circuit_open_refusal"}`.
- **Required Configuration Value**: None beyond `cooldown_ms`.
- **Mutation Risks**: Returning `attempt` instead of `refuse` or wrong state string.
- **Boundary Tests Needed**: Assert calls arriving during `[opened_at, opened_at + cooldown_ms - 1ms]` are refused.
- **Source**: Our policy decision

---

### Decision 9: Cooldown Duration
- **Question**: How long does a provider remain in the `OPEN` state before allowing a probe call?
- **Options**:
  - **Option A**: Fixed configurable duration in milliseconds (e.g. `cooldown_ms = 30000` / 30 seconds).
  - **Option B**: Dynamic exponential cooldown per consecutive trip.
- **Advantages**:
  - *Option A*: Clean, predictable, easily verifiable in walkthroughs and test assertions.
- **Disadvantages**:
  - *Option B* increases mental complexity during scenario prediction.
- **Recommended Option**: **Option A** (Fixed configurable duration: `cooldown_ms = 30000`).
- **Reason**: Simplicity, absolute determinism, and direct configurability via `config.json`.
- **Trade-offs**: Does not escalate on repeated trips, but configurable.
- **Example Scenario**: Breaker trips at $T = 1000\text{ms}$ with `cooldown_ms = 30000`. Cooldown expires at $T = 31000\text{ms}$.
- **Expected Behavior**: Call at $T = 30999\text{ms}$ is refused; call at $T = 31000\text{ms}$ transitions to probing.
- **Required Configuration Value**: `cooldown_ms` (integer, e.g. `30000`).
- **Mutation Risks**: Off-by-one comparisons (`<` vs `<=`).
- **Boundary Tests Needed**: Calls at $T_{\text{cooldown}} - 1\text{ms}$ (`refuse`) and $T_{\text{cooldown}}$ (`probe`).
- **Source**: Our policy decision

---

### Decision 10: HALF_OPEN Transition & Timing Boundary
- **Question**: When does the transition from `OPEN` to `HALF_OPEN` occur, and what is the exact mathematical boundary?
- **Options**:
  - **Option A**: First incoming call at or after `current_time >= opened_at + cooldown_ms` triggers transition to `HALF_OPEN` and serves as the probe.
  - **Option B**: Immediate background timer transition.
- **Advantages**:
  - *Option A*: Discrete, event-driven, perfectly suited for deterministic offline log processing.
- **Disadvantages**:
  - None for batch/event stream processing.
- **Recommended Option**: **Option A** (`current_time >= opened_at + cooldown_ms`).
- **Reason**: Pure function of event timestamps; no asynchronous background threads or timers required.
- **Trade-offs**: None.
- **Example Scenario**: `opened_at = 10:00:00.000Z`, `cooldown_ms = 30000`. Next call arrives at `10:00:30.000Z`.
- **Expected Behavior**: State becomes `HALF_OPEN`, call is designated as the probe.
- **Required Configuration Value**: Governed by `cooldown_ms`.
- **Mutation Risks**: Changing `>=` to `>`.
- **Boundary Tests Needed**: Exact millisecond boundary test at `opened_at + cooldown_ms`.
- **Source**: Our policy decision

---

### Decision 11: Probe Behavior & Concurrency
- **Question**: How many probe calls are permitted in `HALF_OPEN`, and what action is assigned?
- **Options**:
  - **Option A**: Exactly **one probe call** (`action: "probe"`, `provider_state: "HALF_OPEN"`). Any concurrent/interleaved calls arriving before the probe outcome are refused.
  - **Option B**: Multiple concurrent probes.
- **Advantages**:
  - *Option A*: Strict isolation; prevents a flood of traffic while probing an unstable provider.
- **Disadvantages**:
  - None.
- **Recommended Option**: **Option A** (Single probe call).
- **Reason**: Simplest, safest, and most predictable model.
- **Trade-offs**: In sequential log processing, the single probe record directly dictates the next state transition.
- **Example Scenario**: First record after cooldown arrives for provider in `HALF_OPEN`.
- **Expected Behavior**: Action is `probe`, provider state is `HALF_OPEN`.
- **Required Configuration Value**: None.
- **Mutation Risks**: Allowing normal traffic before probe evaluation.
- **Boundary Tests Needed**: Assert first call after cooldown has `action: "probe"`.
- **Source**: Our policy decision

---

### Decision 12: Probe Success Handling
- **Question**: What happens to provider state and counters when a probe call succeeds (`status: "ok"` and `latency_ms <= slow_threshold_ms`)?
- **Options**:
  - **Option A**: State transitions immediately to `CLOSED`, `consecutive_failures` reset to 0, `cooldown_until` cleared, recorded stopped period closed.
  - **Option B**: Require $M$ consecutive probe successes.
- **Advantages**:
  - *Option A*: Clean, instantaneous recovery, simple mental prediction.
- **Disadvantages**:
  - Single probe recovery could re-expose if provider is flapping, but subsequent failure will trip it again quickly.
- **Recommended Option**: **Option A** (Immediate recovery to `CLOSED`, counter reset to 0).
- **Reason**: Maximum clarity and determinism.
- **Trade-offs**: Fast recovery.
- **Example Scenario**: Probe call returns `status: "ok"`, `latency_ms: 200`.
- **Expected Behavior**: Output: `action: "probe"`, `provider_state: "CLOSED"`, `reason: "probe_success_recovery"`. Next call is standard `attempt`.
- **Required Configuration Value**: None.
- **Mutation Risks**: Forgetting to reset failure counter or leaving state in `HALF_OPEN`.
- **Boundary Tests Needed**: Probe success followed immediately by 2 failures (must remain `CLOSED`) and 3rd failure (trips `OPEN`).
- **Source**: Our policy decision

---

### Decision 13: Probe Failure Handling
- **Question**: What happens when a probe call fails (error, timeout, or slow `ok`)?
- **Options**:
  - **Option A**: State transitions immediately back to `OPEN`, new cooldown window starts from `probe_started_at + cooldown_ms`, `consecutive_failures` maintained/incremented.
  - **Option B**: Permanent disablement.
- **Advantages**:
  - *Option A*: Protects provider for another full cooldown window.
- **Disadvantages**:
  - None.
- **Recommended Option**: **Option A** (Re-trip to `OPEN` with new cooldown).
- **Reason**: Standard resilient backoff.
- **Trade-offs**: Provider remains stopped for another full cooldown interval.
- **Example Scenario**: Probe call returns `status: "timeout"`.
- **Expected Behavior**: Output: `action: "probe"`, `provider_state: "OPEN"`, `reason: "probe_failure_reopen"`. Subsequent calls refused for another `cooldown_ms`.
- **Required Configuration Value**: Governed by `cooldown_ms`.
- **Mutation Risks**: Resetting cooldown timer to old `opened_at` instead of probe timestamp.
- **Boundary Tests Needed**: Verify second cooldown period extends from the probe call timestamp.
- **Source**: Our policy decision

---

### Decision 14: Maximum Retries per Call
- **Question**: How many retries are allowed for a single call?
- **Options**:
  - **Option A**: `max_retries = 1` (1 initial attempt + 1 retry = max 2 total executions).
  - **Option B**: `max_retries = 2`.
  - **Option C**: `max_retries = 0` (no retries).
- **Advantages**:
  - *Option A*: Safe, limits downstream latency multiplication, easy to verify.
- **Disadvantages**:
  - None; configurable via `config.json`.
- **Recommended Option**: **Option A** (`max_retries = 1`, configurable).
- **Reason**: 1 retry is standard for LLM gateways to handle transient blips without exploding latency.
- **Trade-offs**: Configurable in `config.json`.
- **Example Scenario**: A call fails with `timeout`. It has 0 previous retries.
- **Expected Behavior**: Policy action is `retry`. If that retry fails, action becomes `give_up`.
- **Required Configuration Value**: `max_retries` (integer, e.g. `1`).
- **Mutation Risks**: `>= max_retries` mutated to `> max_retries`.
- **Boundary Tests Needed**: Test with 0 retries (allows retry), 1 retry (triggers `give_up`).
- **Source**: Our policy decision

---

### Decision 15: Retry Eligibility
- **Question**: Which call outcomes are eligible for a retry attempt?
- **Options**:
  - **Option A**: Retry only on transient errors (`status: "error"` or `status: "timeout"`), provided target provider is not `OPEN` and retry budget remains. Never retry `ok` (even if slow) or unrecognized statuses.
  - **Option B**: Retry all non-ok statuses including unrecognized ones.
  - **Option C**: Retry slow `ok` calls.
- **Advantages**:
  - *Option A*: Prevents duplicate billing/generation on completed requests, avoids hammering open circuits.
- **Disadvantages**:
  - None.
- **Recommended Option**: **Option A** (Only transient `error` and `timeout` on healthy providers).
- **Reason**: Logical correctness for model gateway operations.
- **Trade-offs**: Non-transient or completed calls are never retried.
- **Example Scenario**: A call to `alpha` returns `timeout` while `alpha` is `CLOSED`.
- **Expected Behavior**: Evaluated as `retry`.
- **Required Configuration Value**: None.
- **Mutation Risks**: Retrying on `ok` or retrying when circuit is `OPEN`.
- **Boundary Tests Needed**: Verify slow `ok` produces `attempt`, never `retry`.
- **Source**: Our policy decision

---

### Decision 16: Retry Delay & Backoff Strategy
- **Question**: How is the delay between retries calculated?
- **Options**:
  - **Option A**: Fixed deterministic delay (`retry_delay_ms = 1000`).
  - **Option B**: Deterministic linear backoff ($delay = base \times retry$).
  - **Option C**: Exponential backoff ($delay = base \times 2^{retry-1}$).
- **Advantages**:
  - *Option A*: Simplest, 100% deterministic, zero arithmetic rounding ambiguity during live walkthrough predictions.
- **Disadvantages**:
  - Fixed delay doesn't scale for large retry counts, but with `max_retries = 1`, fixed delay is ideal.
- **Recommended Option**: **Option A** (Fixed deterministic delay: `retry_delay_ms = 1000`).
- **Reason**: Predictability and simplicity.
- **Trade-offs**: Constant delay.
- **Example Scenario**: Retry scheduled for a timed-out call.
- **Expected Behavior**: Delay recorded/evaluated as exactly `1000ms`.
- **Required Configuration Value**: `retry_delay_ms` (integer, e.g. `1000`).
- **Mutation Risks**: Arithmetic operator mutations.
- **Boundary Tests Needed**: Assert retry delay matches `retry_delay_ms` exactly.
- **Source**: Our policy decision

---

### Decision 17: Timing & Backoff Determinism (Jitter Policy)
- **Question**: How do we handle backoff jitter while obeying the strict determinism rule?
- **Options**:
  - **Option A**: **No jitter** (pure fixed/deterministic timing).
  - **Option B**: Deterministic seeded pseudo-random jitter (using seeded PRNG based on record ID or fixed seed).
- **Advantages**:
  - *Option A*: Eliminates all pseudo-randomness, guarantees identical reproduction across every platform, architecture, and Python version.
- **Disadvantages**:
  - None for retrospective offline evaluation.
- **Recommended Option**: **Option A** (Zero jitter / pure deterministic delay).
- **Reason**: The BRIEF states: *"A non-deterministic engine cannot be graded and cannot be trusted."* Pure deterministic timing eliminates all seed drift risks.
- **Trade-offs**: No jitter, but perfectly deterministic.
- **Example Scenario**: Re-running the engine 100 times on the same input.
- **Expected Behavior**: Byte-for-byte identical output every time.
- **Required Configuration Value**: None.
- **Mutation Risks**: Introducing unseeded `random.random()`.
- **Boundary Tests Needed**: Run engine twice on same dataset and assert exact hash equality.
- **Source**: Our policy decision

---

### Decision 18: Unknown / Unrecognized Status Handling
- **Question**: What should the engine do if a record arrives with an unrecognized status (e.g. `"rate_limited"`, `"502_bad_gateway"`, `"null"`)?
- **Options**:
  - **Option A**: Fail-safe policy: treat as an unretryable failure (increments provider consecutive failure count, returns `action: "attempt"`, `reason: "unrecognized_status_failure"`).
  - **Option B**: Raise an unhandled exception / crash.
  - **Option C**: Drop/ignore the record.
- **Advantages**:
  - *Option A*: Preserves 1:1 input/output cardinality, does not crash on unseen data, and protects the system by treating unknown signals as failures.
- **Disadvantages**:
  - None; handles anomalous logs gracefully.
- **Recommended Option**: **Option A** (Treat as unretryable failure, preserve 1:1 ordering).
- **Reason**: The BRIEF states: *"you should assume you will eventually be handed something that isn't [ok, error, timeout]"* and mandates exactly one output line per input line.
- **Trade-offs**: Unknown statuses degrade provider health.
- **Example Scenario**: Input `{"id":"c999","status":"unknown_code","latency_ms":100}`.
- **Expected Behavior**: Output `action: "attempt"`, `reason: "unrecognized_status_failure"`, failure counter increments.
- **Required Configuration Value**: None.
- **Mutation Risks**: Swallowing unknown statuses as successes or crashing.
- **Boundary Tests Needed**: Pass unknown status string and assert output line generated with failure count increment.
- **Source**: Our policy decision

---

### Decision 19: Out-of-Order Timestamps Handling
- **Question**: How should the engine handle logs where `started_at` timestamps are non-chronological or out-of-order?
- **Options**:
  - **Option A**: **Arrival order processing** (process records sequentially in the order they appear in the file; evaluate cooldowns against highest observed timestamp or current record timestamp).
  - **Option B**: Pre-sort the input file by timestamp in memory.
  - **Option C**: Reject out-of-order records.
- **Advantages**:
  - *Option A*: Strictly preserves the required 1:1 input-order matching in `decisions.jsonl` without reordering overhead.
- **Disadvantages**:
  - If a timestamp goes backward, cooldown comparisons use monotonic time tracking (`max(highest_timestamp, record_timestamp)`).
- **Recommended Option**: **Option A** (Process in input arrival order; maintain monotonic maximum timestamp for time progression).
- **Reason**: Satisfies the hard requirement that `decisions.jsonl` must be generated in exact input order.
- **Trade-offs**: State transitions reflect stream arrival sequence.
- **Example Scenario**: Record 1 at 10:00:05, Record 2 at 10:00:01.
- **Expected Behavior**: Record 1 processed first, Record 2 processed second in output.
- **Required Configuration Value**: None.
- **Mutation Risks**: Reordering output lines.
- **Boundary Tests Needed**: Pass non-monotonic timestamp inputs and assert output preserves exact input sequence.
- **Source**: Our policy decision

---

### Decision 20: Controlled Action Vocabulary
- **Question**: What is the exact, fixed vocabulary for the `action` field in `decisions.jsonl`?
- **Vocabulary**:
  - `attempt`: Normal execution of an API call to a healthy provider.
  - `retry`: Re-issuing an eligible failed call.
  - `give_up`: Abandoning further execution after retry exhaustion or non-retryable failure.
  - `refuse`: Rejecting a call upfront because the provider's circuit is `OPEN`.
  - `probe`: Testing an unhealthy provider after cooldown expiry during `HALF_OPEN`.
- **Reason**: Covers all 4 outcomes required by the BRIEF plus the formal circuit-breaker probe state.
- **Source**: Our policy decision

---

### Decision 21: Controlled Provider State Vocabulary
- **Question**: What is the exact, fixed vocabulary for the `provider_state` field in `decisions.jsonl`?
- **Vocabulary**:
  - `CLOSED`: Provider is healthy; normal traffic flows.
  - `OPEN`: Provider is unhealthy; calls are refused.
  - `HALF_OPEN`: Cooldown expired; provider is evaluating a single probe call.
- **Reason**: Standard, mathematically rigorous 3-state Circuit Breaker model.
- **Source**: Our policy decision

---

### Decision 22: Controlled Reason Vocabulary
- **Question**: What is the exact, fixed vocabulary for the `reason` field in `decisions.jsonl`?
- **Vocabulary**:
  - `healthy_call_attempt`: Normal call to a healthy provider.
  - `probe_call_attempt`: Test call during `HALF_OPEN` state.
  - `probe_success_recovery`: Successful probe restoring provider to `CLOSED`.
  - `probe_failure_reopen`: Failed probe tripping provider back to `OPEN`.
  - `circuit_open_refusal`: Call rejected because breaker is `OPEN`.
  - `transient_error_retry`: Call failed with error and is eligible for retry.
  - `timeout_retry`: Call timed out and is eligible for retry.
  - `max_retries_exceeded`: Call failed after exhausting retry budget.
  - `slow_success_degradation`: Call succeeded but exceeded latency threshold.
  - `unrecognized_status_failure`: Unrecognized status treated as unretryable failure.
- **Reason**: Exhaustive, deterministic explanation codes covering every possible branch.
- **Source**: Our policy decision

---

### Decision 23: Second Output Schema (Stopped Periods Report)
- **Question**: What is the exact filename and structure for the second output showing stopped periods per provider?
- **Options**:
  - **Option A**: `stopped_periods.json` — A JSON file containing a dictionary mapping each provider to a list of stopped interval objects `[{"stopped_at": "...", "resumed_at": "...", "duration_ms": ...}]`.
  - **Option B**: CSV report.
- **Advantages**:
  - *Option A*: Clean, machine-readable, directly serializable, exact timestamps.
- **Recommended Option**: **Option A** (`stopped_periods.json`).
- **Reason**: Clean JSON structure that unambiguously reports exact outage windows per provider.
- **Trade-offs**: None.
- **Source**: Our policy decision
