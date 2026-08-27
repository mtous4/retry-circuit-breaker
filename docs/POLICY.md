# Policy Specification (Draft & Proposed Decisions)



## Purpose
To define a strictly deterministic, reproducible, and verifiable policy engine that evaluates historical API call logs to model provider health, execute circuit-breaking, enforce retry limits, and log stopped intervals.

- **Source**: Our policy decision

---

## Failure Definition
A call outcome is classified as a **Failure** if any of the following conditions are met:
1. `status == "error"`
2. `status == "timeout"`
3. `status == "ok"` AND `latency_ms > slow_threshold_ms` (slow success degradation)
4. Any unrecognized / unknown status string.

- **Source**: Our policy decision

---

## Failure Threshold
The circuit breaker trips from `CLOSED` to `OPEN` when a provider accumulates `failure_threshold` consecutive failures.
- **Proposed Value**: `3` (configured via `failure_threshold` in `config.json`).
- **Source**: Our policy decision

---

## Failure Window
- **Proposed Policy**: **Continuous consecutive sequence**. The failure counter increments on every failure and resets to 0 on any fast success (`status == "ok"` AND `latency_ms <= slow_threshold_ms`).
- **Source**: Our policy decision

---

## Circuit Breaker Scope
- **Proposed Policy**: **Per-provider isolation**. Each provider maintains its own independent state machine, counters, timers, and stopped intervals. An outage in provider `alpha` has zero impact on provider `beta`.
- **Source**: Our policy decision

---

## Open-Circuit Behavior
When a provider is in the `OPEN` state and cooldown has not elapsed:
- Incoming calls are refused upfront without attempting execution.
- **Output Action**: `refuse`
- **Provider State**: `OPEN`
- **Reason**: `circuit_open_refusal`
- **Source**: Our policy decision

---

## Cooldown
- **Proposed Policy**: Fixed configurable duration in milliseconds.
- **Proposed Value**: `30000` (30 seconds, configured via `cooldown_ms` in `config.json`).
- **Timing Rule**: A provider remains `OPEN` until a call arrives at `current_time >= opened_at + cooldown_ms`.
- **Source**: Our policy decision

---

## Probe Behavior
When the cooldown period has elapsed (`current_time >= opened_at + cooldown_ms`):
- The provider transitions to `HALF_OPEN`.
- Exactly **one probe call** is admitted to test provider recovery.
- **Output Action**: `probe`
- **Provider State**: `HALF_OPEN`
- **Reason**: `probe_call_attempt`
- **Source**: Our policy decision

---

## Probe Success
If the probe call succeeds (`status == "ok"` AND `latency_ms <= slow_threshold_ms`):
- Provider transitions immediately to `CLOSED`.
- `consecutive_failures` is reset to 0.
- Active stopped period is closed, recording `resumed_at`.
- **Reason**: `probe_success_recovery`
- **Source**: Our policy decision

---

## Probe Failure
If the probe call fails (`error`, `timeout`, slow `ok`, or unknown status):
- Provider transitions immediately back to `OPEN`.
- A new cooldown period begins from the probe call timestamp (`opened_at = probe_started_at`).
- **Reason**: `probe_failure_reopen`
- **Source**: Our policy decision

---

## Retry Policy & Eligibility
Retries are permitted only when all of the following conditions are met:
1. The call outcome was a transient failure (`error` or `timeout`).
2. The target provider is currently `CLOSED` (healthy).
3. The call has not exceeded `max_retries`.
*(Slow successes and unrecognized statuses are never retried).*

- **Source**: Our policy decision

---

## Retry Count
- **Proposed Policy**: Maximum retries permitted per call.
- **Proposed Value**: `1` retry (configured via `max_retries` in `config.json`).
- **Source**: Our policy decision

---

## Retry Backoff
- **Proposed Policy**: Fixed deterministic delay.
- **Proposed Value**: `1000` ms (configured via `retry_delay_ms` in `config.json`).
- **Source**: Our policy decision

---

## Determinism
- **Proposed Policy**: Pure deterministic logic with zero random jitter.
- The engine produces byte-for-byte identical output on every run across all platforms.
- **Source**: Our policy decision

---

## Unknown Providers
- When a call for an unseen provider arrives, the engine automatically initializes an isolated state machine for that provider in the `CLOSED` state with `consecutive_failures = 0`.
- **Source**: Our policy decision

---

## Unknown Statuses
- Unrecognized status values are treated as unretryable failures.
- Increments provider failure count and outputs `action: "attempt"` with `reason: "unrecognized_status_failure"`.
- Preserves 1:1 input/output cardinality without crashing.
- **Source**: Our policy decision

---

## Out-of-Order Timestamps
- Records are processed strictly in file arrival order to maintain 1:1 line ordering in `decisions.jsonl`.
- Time tracking uses monotonic maximum observed timestamps to evaluate cooldown boundaries.
- **Source**: Our policy decision

---

## Configuration (`config.json`)
All tunable parameters live exclusively in `config.json`:
```json
{
  "failure_threshold": 3,
  "cooldown_ms": 30000,
  "slow_threshold_ms": 5000,
  "max_retries": 1,
  "retry_delay_ms": 1000
}
```

- **Source**: Our policy decision

---

## Action Vocabulary
| Action | Definition |
| :--- | :--- |
| `attempt` | Normal execution of an API call to a healthy provider |
| `retry` | Re-issuing an eligible failed call within retry budget |
| `give_up` | Abandoning further execution after retry exhaustion or non-retryable failure |
| `refuse` | Rejecting a call upfront because provider circuit is `OPEN` |
| `probe` | Test call admitted during `HALF_OPEN` state after cooldown expiry |

- **Source**: Our policy decision

---

## Provider State Vocabulary
| State | Definition |
| :--- | :--- |
| `CLOSED` | Provider is healthy; normal traffic flows |
| `OPEN` | Provider is unhealthy; calls are refused |
| `HALF_OPEN` | Cooldown expired; evaluating a single probe call |

- **Source**: Our policy decision

---

## Reason Vocabulary
| Reason Code | Definition |
| :--- | :--- |
| `healthy_call_attempt` | Normal call executed to a healthy provider |
| `probe_call_attempt` | Probe call executed during `HALF_OPEN` state |
| `probe_success_recovery` | Successful probe restoring provider to `CLOSED` |
| `probe_failure_reopen` | Failed probe tripping provider back to `OPEN` |
| `circuit_open_refusal` | Call refused because provider circuit is currently `OPEN` |
| `transient_error_retry` | Call failed with error and is eligible for retry |
| `timeout_retry` | Call timed out and is eligible for retry |
| `max_retries_exceeded` | Call failed after exhausting all allowed retries |
| `slow_success_degradation` | Call succeeded but exceeded latency threshold |
| `unrecognized_status_failure` | Unrecognized status handled as unretryable failure |

- **Source**: Our policy decision

---

## Processing Rules
1. **Arrival Order**: Read each line from `outcomes.jsonl` sequentially.
2. **Provider Resolution**: Lookup or initialize provider state machine.
3. **Breaker Assessment**: Check current state and evaluate timestamp against cooldown.
4. **Action Determination**: Determine whether to attempt, probe, refuse, or retry.
5. **Outcome Evaluation & Transition**: Update failure counters, state transitions, and stopped period tracking.
6. **Output Emission**: Write decision record to `decisions.jsonl`.
7. **Summary Report**: On stream completion, emit `stopped_periods.json`.

- **Source**: Our policy decision

---

## Decision Rationale
- **Simplicity**: Minimized state explosion to 3 states and consecutive counting.
- **Predictability**: 100% deterministic rules allow rapid mental calculation during live walkthroughs.
- **Mutation Resistance**: Explicit boundaries ($N$, $N-1$, $T_{\text{cooldown}}$) with clear killing tests.
- **Source**: Our policy decision
