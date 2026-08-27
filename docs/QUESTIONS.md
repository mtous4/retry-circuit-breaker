# Questions and Decisions Log

## A. Assignment Questions

### 1. Delivery and Schema of Provider Stopped Periods Output
- **Question**: Does the second output showing provider stopped periods require a specific filename, file format, or pre-set schema, and how must it be generated?
- **Status**: Clear in BRIEF
- **Answer**: The BRIEF explicitly states: *"Plus a second output showing, per provider, the periods during which you would have stopped calling it. Name and shape are yours."* Furthermore, *"One documented command turns an outcomes.jsonl plus your config into your outputs."* We will define the filename and data structure in `POLICY.md`, and generate both outputs in one command.
- **Source**: BRIEF

### 2. Dependencies and Execution Environment
- **Question**: Are third-party Python packages permitted in `requirements.txt`?
- **Status**: Clear in BRIEF
- **Answer**: Standard third-party Python libraries are permitted as long as `pip install -r requirements.txt` followed by `pytest` executes successfully from the repo root on a clean clone, with zero network calls and zero database interactions.
- **Source**: BRIEF

### 3. Record Cardinality and Sequencing in `decisions.jsonl`
- **Question**: Can the engine reorder, omit, or batch decisions when writing `decisions.jsonl`?
- **Status**: Clear in BRIEF
- **Answer**: No. The BRIEF strictly requires: *"`decisions.jsonl`, exactly one line per input record, in input order."*
- **Source**: BRIEF

---

## B. Policy Decisions To Discuss

The following 19 decisions are deliberately left to us by the BRIEF. They will be evaluated, decided, and documented in Phase 2 (`POLICY.md`).

### Decision 1: Definition of Failure
- **Decision**: What conditions classify an upstream call outcome as a failure?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 2: Handling Slow Successes (Latency Threshold)
- **Decision**: Should a call with status `ok` that exceeds a latency threshold be classified as a failure or degraded performance?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 3: Timeout vs. Explicit Error Treatment
- **Decision**: Should timeouts be treated identically to explicit errors, or weighted differently in health tracking?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 4: Circuit Breaker Failure Threshold
- **Decision**: How many failures (or what threshold level) trigger the circuit breaker to trip open?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 5: Failure Evaluation Window
- **Decision**: Over what time window or sequence interval are failures evaluated?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 6: Threshold Metric Strategy
- **Decision**: Should breaker tripping be based on consecutive failure count, total failure count within a time window, or error rate percentage?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 7: Circuit Breaker Scope
- **Decision**: Is the circuit breaker state tracked individually per provider or globally across all providers?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 8: Unseen / New Provider Initial State
- **Decision**: What initial state and policy assumptions apply when a call is encountered for a provider not seen before?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 9: Circuit Breaker Cooldown Duration
- **Decision**: How long does a provider remain in the stopped/open state before entering the probing state?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 10: Post-Cooldown State Transition
- **Decision**: What state does a provider transition to once its cooldown timer has elapsed?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 11: Probe Call Strategy
- **Decision**: Does the system admit a single probe call or multiple concurrent probe calls during recovery evaluation?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 12: Probe Success Handling
- **Decision**: What state transitions and counter resets occur when a probe call succeeds?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 13: Probe Failure Handling
- **Decision**: What state transitions and backoff/cooldown adjustments occur when a probe call fails?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 14: Maximum Retries per Call
- **Decision**: What is the maximum number of retry attempts permitted for an individual call?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 15: Initial Retry Delay
- **Decision**: What is the baseline delay before issuing a first retry attempt?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 16: Retry Backoff Strategy
- **Decision**: Which backoff growth function is applied across subsequent retries (constant, linear, exponential)?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 17: Deterministic Backoff and Jitter
- **Decision**: How is backoff jitter made strictly deterministic across runs while preventing herd effects?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 18: Unrecognized / Unknown Status Handling
- **Decision**: How should records with unexpected status values (not `ok`, `error`, `timeout`) be classified and handled?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision

### Decision 19: Out-of-Order Timestamps Handling
- **Decision**: How should the engine process records if `started_at` timestamps are non-monotonic or out of sequential order?
- **Options considered**: TO BE DECIDED
- **Chosen option**: TO BE DECIDED
- **Reason**: TO BE DECIDED
- **Trade-offs**: TO BE DECIDED
- **Source**: Our policy decision
