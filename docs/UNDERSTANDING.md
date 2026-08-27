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
All behavioral thresholds, time windows, retry limits, and cooldown durations must be externalized into a single configuration file (e.g., `config.json`). 

- **Rule**: Absolutely no tunable values or policy thresholds may be hardcoded into implementation logic.
- **Format**: File format is our choice, but must fully capture all parameters needed by the policy engine.

- **Source**: BRIEF

## Outputs
The engine must produce two required outputs:

### 1. Primary Decision Log (`decisions.jsonl`)
- Exactly one output line per input record in `outcomes.jsonl`.
- Output records must preserve the exact input order.
- Each record must contain at least:
  - `id` (string): Matching the input record ID.
  - `action` (string): The policy action taken.
  - `provider_state` (string): The health state of the provider when evaluated.
  - `reason` (string): Deterministic rationale for the action taken.

Example structure:
```json
{"id":"c001","action":"...","provider_state":"...","reason":"..."}
```

The vocabulary for `action`, `provider_state`, and `reason` is defined by us in `POLICY.md`. Once documented, it is fixed and immutable.

- **Source**: BRIEF

### 2. Provider Outage / Stopped Periods Report
- A second output showing, per provider, the exact time periods during which the engine stopped calling each provider and when calling resumed.
- Filename, structure, and schema are ours to define in `POLICY.md`.

- **Source**: BRIEF

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

## What We Need To Decide
The BRIEF explicitly leaves all policy behavior decisions to us. We must deliberately decide, specify, and justify answers to the following 19 questions in `POLICY.md`:

1. **What counts as a failure?** *(TO BE DECIDED)*
2. **Is a slow success considered a failure?** *(TO BE DECIDED)*
3. **Is a timeout treated differently from an explicit error?** *(TO BE DECIDED)*
4. **How many failures trigger the circuit breaker to open?** *(TO BE DECIDED)*
5. **What time window or evaluation interval is used?** *(TO BE DECIDED)*
6. **Is the threshold count-based, rate-based, or sliding-window-based?** *(TO BE DECIDED)*
7. **Is the circuit breaker scoped per provider or globally?** *(TO BE DECIDED)*
8. **What happens when a provider has never been seen before?** *(TO BE DECIDED)*
9. **How long does a provider remain stopped (cooldown duration)?** *(TO BE DECIDED)*
10. **What happens after the cooldown expires?** *(TO BE DECIDED)*
11. **Is probing handled via a single probe request or multiple probe calls?** *(TO BE DECIDED)*
12. **What happens if a probe call succeeds?** *(TO BE DECIDED)*
13. **What happens if a probe call fails?** *(TO BE DECIDED)*
14. **How many retries are allowed per call?** *(TO BE DECIDED)*
15. **What is the initial retry delay?** *(TO BE DECIDED)*
16. **How is backoff calculated (constant, linear, exponential)?** *(TO BE DECIDED)*
17. **How is retry backoff kept strictly deterministic?** *(TO BE DECIDED)*
18. **What happens when a record with an unknown status is encountered?** *(TO BE DECIDED)*
19. **What happens when records arrive with out-of-order timestamps?** *(TO BE DECIDED)*

## Important Distinction

To maintain strict specification discipline, the project separates context into three distinct tiers:

### Tier A: Mandatory BRIEF Requirements
Hard constraints imposed by the assignment that cannot be changed or relaxed (e.g., fixed JSONL fields, 1:1 input/output ordering, file-based execution, determinism, testability on clean clone, mutation-testing resilience).

### Tier B: Our Policy Decisions
Intentional engineering choices that we formulate, justify, document in `POLICY.md`, and implement in the engine (e.g., failure classification, retry budgets, circuit breaker thresholds, probe policies, output schema for stopped periods). These are never attributed to the instructor.

### Tier C: Assignment Inquiries
Questions regarding grading mechanics or external evaluation constraints if genuine ambiguity exists in the BRIEF.
