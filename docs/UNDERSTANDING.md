# Understanding

## Problem
Our API gateway calls upstream model providers to fulfill requests. In production environments, these upstream providers periodically fail—experiencing explicit errors, connection/request timeouts, or severe latency degradation. 

Currently, the gateway continues to send requests to failing providers without restraint ("hammering" them). This uncontrolled traffic worsens upstream outages, cascades failures across downstream systems, and wastes compute and operational resources.

- **Source**: BRIEF

## Goal
The goal of this project is to build a deterministic **policy engine** that consumes historical call outcome logs and retrospectively evaluates what policy actions *should* have been taken for every individual call.

For every call record in the log, the engine must decide among the following high-level outcomes:
- **attempt it**: Allow the call to proceed to the provider as normal.
- **retry it**: Issue a retry attempt following an initial failure under allowed retry constraints.
- **give up on it**: Terminate further attempts on the request after exhausting retries or encountering non-retryable conditions.
- **refuse it because the provider was already considered unhealthy**: Reject the call upfront without attempting it because the target provider's circuit is currently open/stopped.

Additionally, across the entire log duration, the engine must track provider health transitions and compute the exact time periods during which each provider was marked stopped and when it resumed operation.

- **Source**: BRIEF

## Input
The engine operates on a fixed input file:

- **`outcomes.jsonl`**: A JSON Lines file containing one call outcome per line.

Each record contains at least the following fields:
- `id` (string): Unique identifier for the call.
- `provider` (string): Target upstream provider name.
- `started_at` (string): ISO 8601 timestamp representing when the call started.
- `status` (string): Outcome status of the call. Known statuses explicitly mentioned are:
  - `ok`
  - `error`
  - `timeout`
  *(The BRIEF explicitly requires handling cases where unrecognized/unknown statuses appear).*
- `latency_ms` (integer/number): Response latency in milliseconds.

Example record:
```json
{"id":"c001","provider":"alpha","started_at":"2026-09-01T10:00:00.000Z","status":"ok","latency_ms":420}
```

- **Source**: BRIEF

## Configuration
All behavioral thresholds, time windows, retry limits, and cooldown durations must be externalized into a single configuration file (`config.json`). 

- **Rule**: Absolutely no tunable values or policy thresholds may be hardcoded into implementation logic.
- **Format**: JSON format capturing all parameters needed by the policy engine.

- **Source**: BRIEF

## Outputs
The engine must produce two required outputs:

### 1. Primary Decision Log (`decisions.jsonl`)
- Exactly one output line per input record in `outcomes.jsonl`.
- Output records must preserve the exact input order.
- Each record must contain at least:
  - `id` (string): Matching the input record ID.
  - `action` (string): The policy action taken (`attempt`, `retry`, `give_up`, `refuse`, `probe`).
  - `provider_state` (string): The health state of the provider when evaluated (`CLOSED`, `OPEN`, `HALF_OPEN`).
  - `reason` (string): Deterministic rationale for the action taken.

Example structure:
```json
{"id":"c001","action":"attempt","provider_state":"CLOSED","reason":"healthy_call_attempt"}
```

The vocabulary for `action`, `provider_state`, and `reason` is strictly defined in `POLICY.md`. Once documented, it is fixed and immutable.

- **Source**: BRIEF

### 2. Provider Outage / Stopped Periods Report (`stopped_periods.json`)
- A second output showing, per provider, the exact time periods during which the engine stopped calling each provider and when calling resumed.
- Structured JSON format defined in `POLICY.md`.

- **Source**: BRIEF & Our policy decision

## Hard Requirements
The following requirements are explicitly mandated by the BRIEF:

1. **No Implementation Before Specification**: No implementation code may be written before `POLICY.md` is fully defined and documented.
2. **Strict Determinism**: Same input must produce identical output every single run. If pseudorandom jitter is used in backoff models, it must be deterministically seeded and documented.
3. **Externalized Configuration**: All thresholds, windows, counts, and durations must reside in the configuration file, never in code logic.
4. **Pure File I/O**: Files in, files out.
5. **No Network Access**: The engine must execute entirely offline without making network requests.
6. **No Database**: No database systems, external services, or persistent storage daemons.
7. **Clean Clone Testability**: `pip install -r requirements.txt` followed by `pytest` from the repository root must execute the full test suite successfully on a fresh clone.
8. **Single Execution Command**: One documented CLI command must execute the application on `outcomes.jsonl` plus the configuration file to generate both outputs.
9. **Reproducible Verification**: Every numeric value reported in `EVIDENCE.md` must be reproducible via a documented command.

- **Source**: BRIEF

## Policy Decisions Summary (Formalized in `POLICY.md`)
The 19 policy dimensions left to our decision by the BRIEF have been fully decided, approved, and formalized in `POLICY.md`:

1. **Failure Definition**: Explicit errors, timeouts, slow successes (`latency_ms > slow_threshold_ms`), and unrecognized statuses.
2. **Slow Success Handling**: Delivered as `attempt` (outcome accepted), but increments consecutive failure count.
3. **Timeout vs. Error**: Handled identically for failure counting; distinct reason codes for transparency.
4. **Failure Threshold**: Configurable threshold (default `3` consecutive failures) triggering `CLOSED -> OPEN`.
5. **Failure Metric & Window**: Continuous consecutive sequence (resets to 0 on any fast success).
6. **Breaker Scope**: Strict per-provider state isolation.
7. **New Provider**: Initialized to `CLOSED` with 0 failures.
8. **OPEN State**: Refuses incoming calls (`action: "refuse"`, `reason: "circuit_open_refusal"`).
9. **Cooldown**: Configurable duration (default `30000ms` / 30s) during which calls are refused.
10. **HALF_OPEN Transition**: First call arriving at `current_time >= opened_at + cooldown_ms` becomes the single probe.
11. **Probe Strategy**: Exactly one probe call evaluated; other calls refused while pending.
12. **Probe Success**: Restores state to `CLOSED`, resets failure count to 0, closes stopped period.
13. **Probe Failure**: Re-trips to `OPEN` with new cooldown starting from probe timestamp.
14. **Max Retries**: Configurable limit (default `1` retry; max 2 total attempts per call).
15. **Retry Eligibility**: Only transient errors and timeouts on `CLOSED` providers within retry budget.
16. **Retry Delay**: Configurable fixed deterministic delay (default `1000ms`).
17. **Determinism & Jitter**: Zero jitter / pure deterministic delay.
18. **Unknown Status**: Handled as unretryable failure (`action: "attempt"`, increments failure count).
19. **Stream Sequencing**: Processed in input arrival order with monotonic maximum timestamp tracking.

## Important Distinction

To maintain strict specification discipline, the project separates context into three distinct tiers:

### Tier A: Mandatory BRIEF Requirements
Hard constraints imposed by the assignment that cannot be changed or relaxed (e.g., fixed JSONL fields, 1:1 input/output ordering, file-based execution, determinism, testability on clean clone, mutation-testing resilience).

### Tier B: Our Policy Decisions
Intentional engineering choices that we formulated, justified, documented in `POLICY.md`, and will implement in the engine (e.g., failure classification, retry budgets, circuit breaker thresholds, probe policies, output schema for stopped periods). These are never attributed to the instructor.

### Tier C: Assignment Inquiries
Questions regarding grading mechanics or external evaluation constraints if genuine ambiguity exists in the BRIEF.
