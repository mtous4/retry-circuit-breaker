#  Retry & Circuit Breaker Policy Engine


## 1. Setup & Installation

### Requirements
- Python 3.10+
- `pytest` (for running the automated test suite)

### Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 2. Running Automated Tests

To run the full suite of unit, boundary, state transition, and mutation-killing tests:
```bash
pytest
```

---

## 3. Running the Policy Engine CLI

The application processes `outcomes.jsonl` using rules configured in `config.json` and emits `decisions.jsonl` and `stopped_periods.json`:

```bash
python -m src.main --outcomes outcomes.jsonl --config config.json --decisions decisions.jsonl --stopped-periods stopped_periods.json
```

Or using default arguments:
```bash
python -m src.main
```

---

## 4. Input & Output Formats

### Input 1: `outcomes.jsonl`
JSON Lines format representing historical call attempts:
```json
{"id": "call_001", "provider": "openai", "started_at": "2026-09-01T10:00:00.000Z", "status": "ok", "latency_ms": 320}
{"id": "call_002", "provider": "openai", "started_at": "2026-09-01T10:00:01.000Z", "status": "timeout", "latency_ms": 5000}
```

### Input 2: `config.json`
Tunable configuration parameters:
```json
{
  "failure_threshold": 3,
  "cooldown_ms": 30000,
  "slow_threshold_ms": 5000,
  "max_retries": 1,
  "retry_delay_ms": 1000
}
```

### Output 1: `decisions.jsonl`
1:1 decision record emitted per input record:
```json
{"id": "call_001", "action": "attempt", "provider_state": "CLOSED", "reason": "healthy_call_attempt"}
{"id": "call_002", "action": "retry", "provider_state": "CLOSED", "reason": "timeout_retry"}
```

### Output 2: `stopped_periods.json`
Summary of all provider outage intervals:
```json
{
  "openai": [
    {
      "stopped_at": "2026-09-01T10:00:03.000Z",
      "resumed_at": "2026-09-01T10:00:33.000Z",
      "duration_ms": 30000
    }
  ]
}
```
