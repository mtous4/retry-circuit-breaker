# Policy Specification (Draft & Proposed Policy)

> [!IMPORTANT]
> **Document Status**: `PROPOSED POLICY — PENDING REVIEW`
> This document contains the proposed policy specification formulated during Phase 2. Every section below is explicitly marked as **`PROPOSED — NOT YET APPROVED`**. 
> Per the BRIEF, these are **our policy decisions**, not instructor mandates. They will be formalized into the binding state machine in Phase 3 upon user review and approval.

---

## Proposed Policy — Pending Review

### 1. Purpose
- **Status**: PROPOSED — NOT YET APPROVED
- To define a deterministic, reproducible, and verifiable policy engine that evaluates historical API call logs to model provider health, execute circuit breaking, enforce retry limits, and log stopped intervals.
- **Source**: Our policy analysis

---

### 2. Failure Definition (Decision 1 & 2)
- **Status**: PROPOSED — NOT YET APPROVED
- A call outcome is classified as a provider health failure if:
  1. `status == "error"`
  2. `status == "timeout"`
  3. `status == "ok"` AND `latency_ms > slow_threshold_ms` (slow success degradation)
  4. Status is unrecognized / unknown.
- Slow successes (`status == "ok"` with `latency_ms > slow_threshold_ms`) deliver the response as `action: "attempt"`, but increment the provider's consecutive failure count.
- **Source**: Our policy analysis

---

### 3. Failure Threshold (Decision 4)
- **Status**: PROPOSED — NOT YET APPROVED
- The circuit breaker trips from `CLOSED` to `OPEN` when a provider accumulates `failure_threshold` consecutive failures.
- **Proposed Default**: `3` consecutive failures (configurable via `failure_threshold` in `config.json`).
- **Source**: Our policy analysis

---

### 4. Failure Window & Metric (Decision 3 & 5)
- **Status**: PROPOSED — NOT YET APPROVED
- **Metric**: Consecutive failure count.
- **Window**: Continuous sequence. Counter increments on any failure and resets to 0 on any fast success (`status == "ok"` AND `latency_ms <= slow_threshold_ms`). No time window decay is applied, guaranteeing 100% determinism across sparse/batch logs.
- **Source**: Our policy analysis

---

### 5. Circuit Breaker Scope (Decision 6)
- **Status**: PROPOSED — NOT YET APPROVED
- **Scope**: Per-provider isolation. Each provider maintains an independent finite state machine, failure counter, cooldown timer, and stopped intervals list. Outages in one provider never affect another.
- **Source**: Our policy analysis

---

### 6. New Provider Handling (Decision 7)
- **Status**: PROPOSED — NOT YET APPROVED
- When a call for an unseen provider arrives, the engine dynamically initializes an isolated state machine for that provider in the `CLOSED` state with `consecutive_failures = 0`.
- **Source**: Our policy analysis

---

### 7. OPEN State Behavior (Decision 8)
- **Status**: PROPOSED — NOT YET APPROVED
- When a provider is in the `OPEN` state and cooldown has not elapsed (`current_time < opened_at + cooldown_ms`):
  - Incoming calls are refused upfront without attempting execution.
  - **Action**: `refuse`
  - **Provider State**: `OPEN`
  - **Reason**: `circuit_open_refusal`
- Refused calls do NOT count as new failures (they are rejected upfront).
- **Source**: Our policy analysis

---

### 8. Cooldown Duration (Decision 9)
- **Status**: PROPOSED — NOT YET APPROVED
- Fixed configurable duration in milliseconds.
- **Proposed Default**: `30000` ms (30 seconds, configured via `cooldown_ms` in `config.json`).
- **Source**: Our policy analysis

---

### 9. HALF_OPEN & Probe Behavior (Decision 10)
- **Status**: PROPOSED — NOT YET APPROVED
- When cooldown has elapsed (`current_time >= opened_at + cooldown_ms`):
  - The provider transitions to `HALF_OPEN`.
  - Exactly **one probe call** is admitted to test provider recovery.
  - **Action**: `probe`
  - **Provider State**: `HALF_OPEN`
  - **Reason**: `probe_call_attempt`
- Any calls arriving while a probe is pending are refused.
- **Source**: Our policy analysis

---

### 10. Probe Success Handling (Decision 11)
- **Status**: PROPOSED — NOT YET APPROVED
- If the probe call succeeds (`status == "ok"` AND `latency_ms <= slow_threshold_ms`):
  - Provider transitions immediately to `CLOSED`.
  - `consecutive_failures` is reset to 0.
  - The active stopped period is closed, recording `resumed_at = probe_started_at`.
  - **Reason**: `probe_success_recovery`
- **Source**: Our policy analysis

---

### 11. Probe Failure Handling (Decision 12)
- **Status**: PROPOSED — NOT YET APPROVED
- If the probe call fails (error, timeout, slow `ok`, or unknown status):
  - Provider transitions immediately back to `OPEN`.
  - A new cooldown period begins from the probe call timestamp (`opened_at = probe_started_at`).
  - Active stopped period continues.
  - **Reason**: `probe_failure_reopen`
- **Source**: Our policy analysis

---

### 12. Retry Policy & Eligibility (Decision 14 & 16)
- **Status**: PROPOSED — NOT YET APPROVED
- Retries are permitted ONLY when:
  1. The call outcome was a transient failure (`status == "error"` or `status == "timeout"`).
  2. The target provider is currently `CLOSED` (healthy).
  3. The call has not exceeded `max_retries`.
- Slow successes and unknown statuses are never retried.
- Every executed attempt/retry that fails increments the provider's `consecutive_failures`.
- **Source**: Our policy analysis

---

### 13. Retry Count (Decision 13)
- **Status**: PROPOSED — NOT YET APPROVED
- Maximum retries allowed per call: `1` (configured via `max_retries` in `config.json`).
- **Source**: Our policy analysis

---

### 14. Retry Backoff & Timing Determinism (Decision 15 & 17)
- **Status**: PROPOSED — NOT YET APPROVED
- Fixed deterministic delay: `1000` ms (configured via `retry_delay_ms` in `config.json`).
- Zero pseudo-random jitter is used, guaranteeing byte-for-byte reproducibility across runs and environments.
- **Source**: Our policy analysis

---

### 15. Unknown Statuses Handling (Decision 18)
- **Status**: PROPOSED — NOT YET APPROVED
- Unrecognized status values are treated as unretryable failures.
- Increments provider failure count and outputs `action: "attempt"` with `reason: "unrecognized_status_failure"`.
- Preserves 1:1 input/output line cardinality without crashing.
- **Source**: Our policy analysis

---

### 16. Out-of-Order Timestamps (Decision 19)
- **Status**: PROPOSED — NOT YET APPROVED
- Records are processed strictly in arrival order to preserve 1:1 input ordering in `decisions.jsonl`.
- Monotonic maximum timestamp tracking (`current_time = max(max_seen_time, record_time)`) is used for cooldown boundary evaluation.
- **Source**: Our policy analysis

---

### 17. Configuration Model (`config.json`)
- **Status**: PROPOSED — NOT YET APPROVED
- All tunable parameters reside exclusively in `config.json`:
```json
{
  "failure_threshold": 3,
  "cooldown_ms": 30000,
  "slow_threshold_ms": 5000,
  "max_retries": 1,
  "retry_delay_ms": 1000
}
```
- Zero tunable constants hardcoded in logic.
- **Source**: Our policy analysis

---

### 18. Controlled Vocabulary Specifications (Decisions 20, 21, 22)
- **Status**: PROPOSED — NOT YET APPROVED

#### Action Vocabulary
| Action | Definition |
| :--- | :--- |
| `attempt` | Normal execution of an API call to a healthy provider |
| `retry` | Re-issuing an eligible failed call within retry budget |
| `give_up` | Abandoning further execution after retry exhaustion or non-retryable failure |
| `refuse` | Rejecting a call upfront because provider circuit is `OPEN` |
| `probe` | Test call admitted during `HALF_OPEN` state after cooldown expiry |

#### Provider State Vocabulary
| State | Definition |
| :--- | :--- |
| `CLOSED` | Provider is healthy; normal traffic flows |
| `OPEN` | Provider is unhealthy; calls are refused |
| `HALF_OPEN` | Cooldown expired; provider is evaluating a single probe call |

#### Reason Vocabulary
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

- **Source**: Our policy analysis

---

### 19. Second Output Schema (Decision 23)
- **Status**: PROPOSED — NOT YET APPROVED
- File: `stopped_periods.json`
- Schema:
```json
{
  "alpha": [
    {
      "stopped_at": "2026-09-01T10:00:02.000Z",
      "resumed_at": "2026-09-01T10:00:32.000Z",
      "duration_ms": 30000
    }
  ]
}
```
- **Source**: Our policy analysis
