# Policy Specification — Retry & Circuit Breaker Policy Engine

**Document Status**: `FINAL FORMALIZED SPECIFICATION (AMENDED)`  
**Governing Authority**: Approved by Project Owner  
**Source Discipline**: Explicitly tags every rule as `Source: BRIEF` or `Source: Our policy decision`.

---

## 1. Purpose & Engine Architecture
This document specifies the exact, deterministic policy governing the **Retry & Circuit Breaker Policy Engine**.

- **Retrospective Log Evaluation**: The engine operates as an offline evaluation policy engine. It reads historical API call outcome logs (`outcomes.jsonl`) sequentially and determines, for each individual call record, what policy action the gateway *should have taken* (`attempt`, `retry`, `give_up`, `refuse`, or `probe`), along with the resulting provider health state and explanatory reason.
- **Provider Outage Tracking**: Over the full duration of the log, the engine tracks provider health transitions and emits a structured report (`stopped_periods.json`) detailing the exact stopped/outage time intervals for each provider.
- **Reproducibility Guarantee**: Any independent developer or test suite implementing this specification will produce byte-for-byte identical output for any given `outcomes.jsonl` and `config.json`.
- **Source**: Our policy decision

---

## 2. Fixed Interface Contract

### 2.1. Input File: `outcomes.jsonl`
The engine processes a single input file formatted as JSON Lines (one JSON object per line).
- **Record Schema**: Each record contains strictly the following fields from the BRIEF:
  - `id` (`string`): Unique identifier for the call.
  - `provider` (`string`): Identifier of the target upstream model provider.
  - `started_at` (`string`): ISO 8601 UTC timestamp of call initiation (e.g., `"2026-09-01T10:00:00.000Z"`).
  - `status` (`string`): Call outcome status. Known statuses: `"ok"`, `"error"`, `"timeout"`. (Unrecognized statuses may appear and are handled deterministically).
  - `latency_ms` (`integer`): Call duration in milliseconds ($\ge 0$).
- **No Extra Fields Required**: The engine does not require or assume any non-standard fields (such as client-side retry counts) in the input records.
- **Source**: BRIEF

### 2.2. Configuration File: `config.json`
All tunable parameters, thresholds, and durations reside exclusively in `config.json`.
- **Rule**: Absolutely no tunable policy values or durations may be hardcoded into implementation logic.
- **Source**: BRIEF

### 2.3. Output 1: `decisions.jsonl`
- **Cardinality**: Exactly one output line per input record in `outcomes.jsonl`.
- **Ordering**: Output records strictly preserve the exact input file arrival order.
- **Record Schema**: Each line is a JSON object containing:
  - `id` (`string`): Matching the input record's `id`.
  - `action` (`string`): Policy action decided for the call (from controlled vocabulary).
  - `provider_state` (`string`): Provider health state **after** evaluating the record (from controlled vocabulary).
  - `reason` (`string`): Deterministic explanation code (from controlled vocabulary).
- **Source**: BRIEF

### 2.4. Output 2: Provider Stopped Periods Report (`stopped_periods.json`)
- **File Name**: `stopped_periods.json`
- **Schema**: A JSON object mapping each provider string to an array of stopped interval objects:
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
- **Unclosed Stopped Periods**: If the log ends while a provider is in the `OPEN` state, `resumed_at` is set to `null` and `duration_ms` is computed as `last_record_timestamp - stopped_at`.
- **Source**: Our policy decision (shape and file name chosen per BRIEF allowance)

---

## 3. Core Definitions & Semantic Clarifications

### 3.1. `provider_state` Definition
> **Explicit Rule**: In `decisions.jsonl`, `provider_state` represents the provider's **resulting health state AFTER evaluating the record** (i.e. the state of the provider following the processing of the call outcome and any state transition it triggered).

- **Source**: Our policy decision

### 3.2. Failure Classification
A call outcome is classified as a **Provider Failure** if any of the following mutually exclusive conditions evaluate to true:
1. `status == "error"`
2. `status == "timeout"`
3. `status == "ok"` AND `latency_ms > slow_threshold_ms` (Slow Success Degradation)
4. `status` is unrecognized (not `"ok"`, `"error"`, or `"timeout"`).

A call outcome is classified as a **Provider Success (Healthy)** if and only if:
- `status == "ok"` AND `latency_ms <= slow_threshold_ms`.

- **Source**: Our policy decision

### 3.3. Slow Success Boundary
- **Operator**: Strict inequality (`latency_ms > slow_threshold_ms`).
- **Behavior**: A slow success is a completed call. The response is delivered to the caller (`action: "attempt"`). However, because upstream latency exceeded the threshold, it increments the provider's `consecutive_failures` counter.
- **No Retries for Slow Success**: A slow success is never retried because a valid response was already generated.
- **Source**: Our policy decision

### 3.4. Failure Metric & Consecutive Counting
- **Metric**: Consecutive failure count (`consecutive_failures`).
- **Increment Rule**: Increments by 1 on every Provider Failure during `CLOSED` or `HALF_OPEN` state.
- **Reset Rule**: Resets immediately to `0` upon any Provider Success (`status == "ok"` AND `latency_ms <= slow_threshold_ms`).
- **Refused Calls**: Refused calls do NOT touch the provider and do NOT increment `consecutive_failures`.
- **Source**: Our policy decision

### 3.5. Circuit Breaker Scope & Provider Isolation
- **Scope**: **Per-provider isolation**. Each provider name maintains an independent finite state machine with its own `consecutive_failures`, `state`, `opened_at`, `cooldown_until`, and stopped intervals list.
- **Isolation Invariant**: Failures or state transitions in provider `alpha` have zero effect on provider `beta`.
- **New Providers**: Unseen providers dynamically initialize in `CLOSED` state with `consecutive_failures = 0`.
- **Source**: Our policy decision

---

## 4. Retrospective Retry & Breaker Semantics

### 4.1. Retrospective Retry Interpretation
In this retrospective policy engine, each record in `outcomes.jsonl` represents an individual call outcome presented to the gateway.
- When an individual call fails with a transient failure (`error` or `timeout`):
  - If `max_retries >= 1` AND the failure did not trip the provider's circuit breaker (provider remains `CLOSED`), the engine decides **`action: "retry"`** (Reason: `"transient_error_retry"` or `"timeout_retry"`). This signifies: *The gateway policy recommends that this failed call should have been retried.*
  - If `max_retries == 0` (retries disabled in config), the engine decides **`action: "give_up"`** (Reason: `"max_retries_exceeded"`).
  - If the failure was the $N$-th consecutive failure that caused the provider's circuit to trip to `OPEN`, the engine decides **`action: "give_up"`** (Reason: `"max_retries_exceeded"`), because retrying against a blown circuit is prohibited.
- **Source**: Our policy decision

### 4.2. Retrospective Probe Semantics (Sequential Log Model)
Because `outcomes.jsonl` is processed line-by-line in sequential arrival order without real-time concurrency:
1. **Probe Eligibility**: When a provider is in the `OPEN` state, any record arriving with `record.started_at < cooldown_until` is refused upfront (`action: "refuse"`, `provider_state: "OPEN"`, `reason: "circuit_open_refusal"`).
2. **Single Probe Selection**: The very first record arriving with `record.started_at >= cooldown_until` transitions the provider into `HALF_OPEN` and serves as the single canary **Probe Call**.
3. **Immediate Outcome Evaluation**: Because the record already contains its outcome (`status` and `latency_ms`), its outcome is evaluated immediately:
   - **Probe Success** (`status == "ok"` AND `latency_ms <= slow_threshold_ms`):
     - Provider transitions immediately to `CLOSED`.
     - `consecutive_failures` resets to 0.
     - Active stopped period is closed (`resumed_at = record.started_at`, `duration_ms = resumed_at - stopped_at`).
     - Emitted Decision: `action = "probe"`, `provider_state = "CLOSED"`, `reason = "probe_success_recovery"`.
   - **Probe Failure** (`error`, `timeout`, slow `ok`, or unknown status):
     - Provider transitions immediately back to `OPEN`.
     - `consecutive_failures` increments.
     - A new cooldown period is started from the probe timestamp: `opened_at = record.started_at`, `cooldown_until = opened_at + cooldown_ms`.
     - Active stopped period continues uninterrupted.
     - Emitted Decision: `action = "probe"`, `provider_state = "OPEN"`, `reason = "probe_failure_reopen"`.
4. **Next Record**: The subsequent record in the log will evaluate against the resulting state (`CLOSED` if probe succeeded, or `OPEN` with the new cooldown if probe failed).
- **Source**: Our policy decision

### 4.3. Stream Sequencing & Out-of-Order Timestamps
- **Arrival Order**: Records are processed in the strict sequential order of their appearance in `outcomes.jsonl`.
- **Monotonic Time Tracking**: To prevent non-chronological or out-of-order input timestamps from regressing time during cooldown evaluation, the engine tracks:
  $$\text{current\_time} = \max(\text{max\_observed\_timestamp}, \text{record.started\_at})$$
- **Stopped Period Timestamps**: `stopped_at` and `resumed_at` record the raw ISO timestamps of the tripping record and successful probe record respectively. `duration_ms` is computed as $\max(0, \text{epoch\_ms}(resumed\_at) - \text{epoch\_ms}(stopped\_at))$.
- **Source**: Our policy decision

---

## 5. Controlled Vocabularies

### 5.1. Action Vocabulary
| Action | Definition | When Emitted |
| :--- | :--- | :--- |
| `attempt` | Normal execution of a call to a provider | Call to `CLOSED` provider; delivers success, slow success, or unretryable failure. |
| `retry` | Policy recommends re-issuing this failed call | Transient `error` or `timeout` when `max_retries >= 1` and provider remains `CLOSED`. |
| `give_up` | Policy recommends abandoning further retries | Transient failure when `max_retries == 0` or when failure tripped circuit to `OPEN`. |
| `refuse` | Upfront rejection of call without provider interaction | Incoming call while provider is `OPEN` and cooldown is active. |
| `probe` | Canary test call evaluating provider recovery | First incoming call arriving after cooldown expiry. |

- **Source**: Our policy decision

### 5.2. Provider State Vocabulary
| Provider State | Definition | Invariants |
| :--- | :--- | :--- |
| `CLOSED` | Provider is healthy; normal traffic flows | `consecutive_failures < failure_threshold`. `cooldown_until == null`. |
| `OPEN` | Provider is unhealthy; traffic is blocked | `consecutive_failures >= failure_threshold`. Cooldown timer is active. |
| `HALF_OPEN` | Transient state during probe evaluation | Admitting the canary probe call to test recovery. |

- **Source**: Our policy decision

### 5.3. Reason Vocabulary
| Reason Code | Definition | Valid `(action, provider_state)` |
| :--- | :--- | :--- |
| `healthy_call_attempt` | Call succeeded within latency limits | `("attempt", "CLOSED")` |
| `slow_success_degradation` | Call succeeded but exceeded `slow_threshold_ms` | `("attempt", "CLOSED")` or `("attempt", "OPEN")` |
| `transient_error_retry` | Transient error eligible for retry | `("retry", "CLOSED")` |
| `timeout_retry` | Timeout eligible for retry | `("retry", "CLOSED")` |
| `max_retries_exceeded` | Call failed and cannot be retried (circuit open or retry budget 0) | `("give_up", "CLOSED")` or `("give_up", "OPEN")` |
| `circuit_open_refusal` | Call refused due to active breaker cooldown | `("refuse", "OPEN")` |
| `probe_success_recovery` | Probe succeeded; circuit restored to healthy | `("probe", "CLOSED")` |
| `probe_failure_reopen` | Probe failed; breaker re-tripped to open | `("probe", "OPEN")` |
| `unrecognized_status_failure` | Unrecognized status handled as unretryable failure | `("attempt", "CLOSED")` or `("attempt", "OPEN")` |

- **Source**: Our policy decision

---

## 6. Formal State Transition Table

The Circuit Breaker Finite State Machine (FSM) is defined formally by $(S, E, \delta, A)$ where `provider_state` in the output represents **Next State** (the state after evaluation).

| Prior State | Incoming Event & Outcome | Guard Condition | Action | Next State (`provider_state`) | Counter Changes | Timer / Stopped Period Side Effects | Reason Code |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`CLOSED`** | `status == "ok"` AND `latency_ms <= slow_threshold_ms` | None | `attempt` | `CLOSED` | `failures = 0` | None | `healthy_call_attempt` |
| **`CLOSED`** | `status == "ok"` AND `latency_ms > slow_threshold_ms` | `failures + 1 < threshold` | `attempt` | `CLOSED` | `failures += 1` | None | `slow_success_degradation` |
| **`CLOSED`** | `status == "ok"` AND `latency_ms > slow_threshold_ms` | `failures + 1 >= threshold` | `attempt` | `OPEN` | `failures += 1` | `opened_at = record.started_at`<br>`cooldown_until = opened_at + cooldown_ms`<br>Open stopped period | `slow_success_degradation` |
| **`CLOSED`** | `status == "error"` | `max_retries >= 1` AND `failures + 1 < threshold` | `retry` | `CLOSED` | `failures += 1` | None | `transient_error_retry` |
| **`CLOSED`** | `status == "timeout"` | `max_retries >= 1` AND `failures + 1 < threshold` | `retry` | `CLOSED` | `failures += 1` | None | `timeout_retry` |
| **`CLOSED`** | `status in ["error", "timeout"]` | `max_retries == 0` AND `failures + 1 < threshold` | `give_up` | `CLOSED` | `failures += 1` | None | `max_retries_exceeded` |
| **`CLOSED`** | `status in ["error", "timeout"]` | `failures + 1 >= threshold` (trips breaker) | `give_up` | `OPEN` | `failures += 1` | `opened_at = record.started_at`<br>`cooldown_until = opened_at + cooldown_ms`<br>Open stopped period | `max_retries_exceeded` |
| **`CLOSED`** | Unknown status | `failures + 1 < threshold` | `attempt` | `CLOSED` | `failures += 1` | None | `unrecognized_status_failure` |
| **`CLOSED`** | Unknown status | `failures + 1 >= threshold` | `attempt` | `OPEN` | `failures += 1` | `opened_at = record.started_at`<br>`cooldown_until = opened_at + cooldown_ms`<br>Open stopped period | `unrecognized_status_failure` |
| **`OPEN`** | Any incoming call | `current_time < cooldown_until` | `refuse` | `OPEN` | None (counter unchanged) | None | `circuit_open_refusal` |
| **`OPEN`** | First call arriving at `current_time >= cooldown_until` | Probe outcome: `ok` AND `latency_ms <= slow_threshold_ms` | `probe` | `CLOSED` | `failures = 0` | `resumed_at = record.started_at`<br>Close stopped period | `probe_success_recovery` |
| **`OPEN`** | First call arriving at `current_time >= cooldown_until` | Probe outcome: `error`, `timeout`, slow `ok`, or unknown | `probe` | `OPEN` | `failures += 1` | `opened_at = record.started_at`<br>`cooldown_until = opened_at + cooldown_ms`<br>Stopped period continues | `probe_failure_reopen` |

- **Source**: Our policy decision

---

## 7. End-to-End Call Processing Algorithm

```
Initialize provider_states = {} // Dictionary mapping provider name to ProviderFSM
Initialize max_observed_timestamp = 0

For each line record R in outcomes.jsonl:
    1. Parse R = { id, provider, started_at, status, latency_ms }
    2. record_time_ms = parse_iso_to_epoch_ms(R.started_at)
    3. max_observed_timestamp = max(max_observed_timestamp, record_time_ms)
    
    4. If R.provider not in provider_states:
           provider_states[R.provider] = ProviderFSM(state="CLOSED", failures=0, cooldown_until=0, stopped_intervals=[])
       provider = provider_states[R.provider]

    5. If provider.state == "OPEN":
           If max_observed_timestamp < provider.cooldown_until:
               // Cooldown still active: refuse call
               EMIT Decision(id=R.id, action="refuse", provider_state="OPEN", reason="circuit_open_refusal")
               CONTINUE to next line
           Else:
               // Cooldown expired: evaluate R as the single recovery probe
               is_probe_success = (R.status == "ok" and R.latency_ms <= config.slow_threshold_ms)
               If is_probe_success:
                   provider.state = "CLOSED"
                   provider.failures = 0
                   provider.close_stopped_period(resumed_at=R.started_at)
                   EMIT Decision(id=R.id, action="probe", provider_state="CLOSED", reason="probe_success_recovery")
               Else:
                   provider.state = "OPEN"
                   provider.failures += 1
                   provider.opened_at = R.started_at
                   provider.cooldown_until = record_time_ms + config.cooldown_ms
                   EMIT Decision(id=R.id, action="probe", provider_state="OPEN", reason="probe_failure_reopen")
               CONTINUE to next line

    6. Provider is CLOSED (Normal traffic evaluation):
       is_success = (R.status == "ok" and R.latency_ms <= config.slow_threshold_ms)
       
       If is_success:
           provider.failures = 0
           EMIT Decision(id=R.id, action="attempt", provider_state="CLOSED", reason="healthy_call_attempt")
       Else:
           // Provider Failure
           provider.failures += 1
           tripped = (provider.failures >= config.failure_threshold)
           If tripped:
               provider.state = "OPEN"
               provider.opened_at = R.started_at
               provider.cooldown_until = record_time_ms + config.cooldown_ms
               provider.open_stopped_period(stopped_at=R.started_at)

           // Determine Action & Reason
           If R.status == "ok": // slow success
               EMIT Decision(id=R.id, action="attempt", provider_state=provider.state, reason="slow_success_degradation")
           Else If R.status not in ["error", "timeout"]: // unrecognized status
               EMIT Decision(id=R.id, action="attempt", provider_state=provider.state, reason="unrecognized_status_failure")
           Else: // transient error or timeout
               If tripped or config.max_retries == 0:
                   EMIT Decision(id=R.id, action="give_up", provider_state=provider.state, reason="max_retries_exceeded")
               Else:
                   reason_code = "transient_error_retry" if R.status == "error" else "timeout_retry"
                   EMIT Decision(id=R.id, action="retry", provider_state="CLOSED", reason=reason_code)

On stream completion:
    Write all provider stopped intervals to stopped_periods.json
```

- **Source**: Our policy decision

---

## 8. Configuration Specification (`config.json`)

All tunable parameters reside in `config.json`:

| Field Name | Type | Unit | Default | Constraints | Description & Behavioral Effect |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `failure_threshold` | `integer` | count | `3` | $\ge 1$ | Consecutive failures required to trip circuit from `CLOSED` to `OPEN`. |
| `cooldown_ms` | `integer` | ms | `30000` | $\ge 1000$ | Duration provider remains `OPEN` before admitting a recovery probe. |
| `slow_threshold_ms` | `integer` | ms | `5000` | $\ge 100$ | Latency boundary above which `status: "ok"` is treated as a health failure. |
| `max_retries` | `integer` | count | `1` | $\ge 0$ | Maximum retries allowed per call for transient errors/timeouts. |
| `retry_delay_ms` | `integer` | ms | `1000` | $\ge 0$ | Fixed deterministic delay preceding a retry. |

- **Source**: Our policy decision

---

## 9. Concrete Worked Examples

### Example 1: Healthy Call Progression
- **Input**: `{"id": "c001", "provider": "alpha", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 350}`
- **Prior State**: `alpha` is `CLOSED`, `failures = 0`.
- **Decision Output**: `{"id": "c001", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
- **Resulting State**: `alpha` is `CLOSED`, `failures = 0`.

### Example 2: Slow Success Boundary
- **Input**: `{"id": "c002", "provider": "alpha", "started_at": "2026-09-01T10:00:01.000Z", "status": "ok", "latency_ms": 5001}` (`slow_threshold_ms = 5000`)
- **Prior State**: `alpha` is `CLOSED`, `failures = 0`.
- **Decision Output**: `{"id": "c002", "action": "attempt", "provider_state": "CLOSED", "reason": "slow_success_degradation"}`
- **Resulting State**: `alpha` is `CLOSED`, `failures = 1`.

### Example 3: Transient Error with Retry Allowed
- **Input**: `{"id": "c003", "provider": "alpha", "started_at": "2026-09-01T10:00:02.000Z", "status": "error", "latency_ms": 120}` (`max_retries = 1`, `failure_threshold = 3`)
- **Prior State**: `alpha` is `CLOSED`, `failures = 1`.
- **Decision Output**: `{"id": "c003", "action": "retry", "provider_state": "CLOSED", "reason": "transient_error_retry"}`
- **Resulting State**: `alpha` is `CLOSED`, `failures = 2`.

### Example 4: Failure Threshold Tripping Breaker to OPEN
- **Input**: `{"id": "c004", "provider": "alpha", "started_at": "2026-09-01T10:00:03.000Z", "status": "timeout", "latency_ms": 5000}` (`failure_threshold = 3`)
- **Prior State**: `alpha` is `CLOSED`, `failures = 2`.
- **Decision Output**: `{"id": "c004", "action": "give_up", "provider_state": "OPEN", "reason": "max_retries_exceeded"}`
- **Resulting State**: `alpha` is `OPEN`, `failures = 3`, `opened_at = 10:00:03.000Z`, `cooldown_until = 10:00:33.000Z`.

### Example 5: Call Refusal during Active Cooldown
- **Input**: `{"id": "c005", "provider": "alpha", "started_at": "2026-09-01T10:00:15.000Z", "status": "ok", "latency_ms": 200}`
- **Prior State**: `alpha` is `OPEN`, `cooldown_until = 10:00:33.000Z`.
- **Decision Output**: `{"id": "c005", "action": "refuse", "provider_state": "OPEN", "reason": "circuit_open_refusal"}`
- **Resulting State**: `alpha` remains `OPEN`, `failures = 3` (unchanged).

### Example 6: Cooldown Expiry & Probe Success Recovery
- **Input**: `{"id": "c006", "provider": "alpha", "started_at": "2026-09-01T10:00:33.000Z", "status": "ok", "latency_ms": 250}`
- **Prior State**: `alpha` is `OPEN`, `cooldown_until = 10:00:33.000Z` (cooldown elapsed).
- **Decision Output**: `{"id": "c006", "action": "probe", "provider_state": "CLOSED", "reason": "probe_success_recovery"}`
- **Resulting State**: `alpha` is `CLOSED`, `failures = 0`, stopped period closed:
  `{"stopped_at": "2026-09-01T10:00:03.000Z", "resumed_at": "2026-09-01T10:00:33.000Z", "duration_ms": 30000}`.

### Example 7: Cooldown Expiry & Probe Failure Re-Trip
- **Input**: `{"id": "c007", "provider": "alpha", "started_at": "2026-09-01T10:00:33.000Z", "status": "error", "latency_ms": 100}`
- **Prior State**: `alpha` is `OPEN`, `cooldown_until = 10:00:33.000Z` (cooldown elapsed).
- **Decision Output**: `{"id": "c007", "action": "probe", "provider_state": "OPEN", "reason": "probe_failure_reopen"}`
- **Resulting State**: `alpha` is `OPEN`, `failures = 4`, `opened_at = 10:00:33.000Z`, `cooldown_until = 10:01:03.000Z`. Stopped period continues.

### Example 8: Provider Isolation
- **Input**: `{"id": "c008", "provider": "beta", "started_at": "2026-09-01T10:00:34.000Z", "status": "ok", "latency_ms": 200}` while `alpha` is `OPEN`.
- **Prior State**: `alpha` is `OPEN`, `beta` is `CLOSED`.
- **Decision Output**: `{"id": "c008", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}`
- **Resulting State**: `alpha` remains `OPEN`, `beta` is `CLOSED`.

---

## 10. Traceability Matrix

| Area | Governing Rule | Source | Origin & Justification |
| :--- | :--- | :--- | :--- |
| **Input Schema** | `id`, `provider`, `started_at`, `status`, `latency_ms` | BRIEF | Fixed interface defined in BRIEF §Fixed interface |
| **Output 1 Schema** | `id`, `action`, `provider_state`, `reason` (1:1 input order) | BRIEF | Fixed interface defined in BRIEF §Fixed interface |
| **Output 2 Delivery** | `stopped_periods.json` reporting stopped intervals per provider | Our policy decision | Defined per BRIEF §Fixed interface allowance |
| **Config Boundary** | All tunable thresholds/durations in `config.json` | BRIEF | Hard requirement defined in BRIEF §Fixed interface & §Hard rules |
| **Offline Isolation** | Pure file I/O, no network, no database | BRIEF | Hard requirement defined in BRIEF §Hard rules |
| **Determinism** | Byte-for-byte identical output on every run | BRIEF | Hard requirement defined in BRIEF §Hard rules |
| **`provider_state`** | Represents provider state AFTER processing record | Our policy decision | Resolves ambiguity; matches FSM resulting state |
| **Failure Definition** | `error`, `timeout`, slow `ok` (`> slow_threshold_ms`), unknown status | Our policy decision | Protects against degraded generation latency in LLMs |
| **Metric & Threshold** | Trip on $N$ consecutive failures; reset on fast `ok` | Our policy decision | Pure determinism for the 10-scenario prediction walkthrough |
| **Sequential Probe** | First record at $\ge cooldown\_until$ evaluated immediately as probe | Our policy decision | Matches discrete sequential log arrival model without concurrency |
| **Monotonic Time** | Cooldowns use $\max(max\_seen\_timestamp, record.started\_at)$ | Our policy decision | Prevents non-monotonic input timestamps from regressing timers |
