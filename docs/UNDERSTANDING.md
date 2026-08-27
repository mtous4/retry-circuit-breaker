# Understanding

## Problem
Upstream model provider calls fail periodically (due to errors, timeouts, or high latency). Currently, the gateway repeatedly retries or calls unhealthy providers without restraint, which worsens upstream outages and wastes resources.

## Goal
Build a deterministic policy engine that processes a historical call outcome log (`outcomes.jsonl`) and determines what the policy should have done for every call (attempt, retry, drop/give up, refuse/block). Additionally, calculate and output the exact time periods during which each provider would have been paused/stopped.

## Inputs
- `outcomes.jsonl`: Call outcome records (JSON Lines format). Each record contains at least `id`, `provider`, `started_at`, `status` (e.g. `ok`, `error`, `timeout`, or unknown), and `latency_ms`.
- `config.json`: Single configuration file containing all thresholds, windows, and durations (no hardcoded policy values in logic).

## Outputs
- `decisions.jsonl`: Exactly one record per input record in input order, containing at least `id`, `action`, `provider_state`, and `reason`.
- Provider outage/stopped periods report: A second output detailing the time windows during which each provider was marked stopped/unhealthy.

## Important Constraints
- **No implementation code before POLICY.md exists**: Architecture and policy specification must precede implementation.
- **Determinism**: Same input must produce the identical output every run. (Any jitter or pseudorandomness must be deterministically seeded and documented).
- **Externalized Configuration**: All thresholds, windows, and durations must live in configuration, not in application logic.
- **I/O Isolation**: Files in, files out. No network requests, no database connections.
- **Reproducible Evidence**: Every number in `EVIDENCE.md` must be reproducible by a documented CLI command.
- **Standard Testing**: `pytest` must run from the repository root after `pip install -r requirements.txt`.
- **Single Execution Command**: A single documented command must run the engine on `outcomes.jsonl` plus `config.json` to generate all outputs.

## What Actually Matters
- Designing a clear, defensible, and coherent policy model that is thoroughly documented in `POLICY.md`.
- Robust verification and mutation-resistant test suite that validates boundary conditions and prevents subtle logic bugs.
- Strict predictability: being able to reason about and predict engine decisions on unseen scenarios.
- Flawless third-party reproducibility on a clean clone.

## What Is Our Policy to Decide
- What constitutes a failure (errors, timeouts, latency thresholds).
- Failure thresholds, counting mechanisms (count vs. rate vs. sliding window), and evaluation scopes (per-provider vs. global).
- Circuit breaker state transitions (Closed, Open, Half-Open/Probing).
- Cooldown durations and probe behavior (single probe vs. gradual recovery, success/failure criteria).
- Retry policy (retry eligibility, retry limits, backoff strategies, deterministic jitter handling).
- Handling edge cases (unknown statuses, unseen providers, out-of-order timestamps).
- Standardized vocabulary for `action`, `provider_state`, and `reason`.

## Open Questions
- To be documented and resolved in `QUESTIONS.md` during subsequent policy design phases.
