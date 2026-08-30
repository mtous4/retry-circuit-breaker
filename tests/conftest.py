"""
Shared test fixtures and configuration factories for Project 3 Policy Engine test suite.
"""

import json
from pathlib import Path
from typing import Any, Dict, List
import pytest

# Default configuration defined in docs/POLICY.md §7
DEFAULT_CONFIG_DICT: Dict[str, Any] = {
    "failure_threshold": 3,
    "cooldown_ms": 30000,
    "slow_threshold_ms": 5000,
    "max_retries": 1,
    "retry_delay_ms": 1000,
}


@pytest.fixture
def default_config() -> Dict[str, Any]:
    """Returns a copy of the default policy configuration dictionary."""
    return DEFAULT_CONFIG_DICT.copy()


@pytest.fixture
def make_config_file(tmp_path: Path):
    """Factory fixture to write a config.json with custom overrides."""
    def _create_config(overrides: Dict[str, Any] = None) -> Path:
        cfg = DEFAULT_CONFIG_DICT.copy()
        if overrides:
            cfg.update(overrides)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return config_path
    return _create_config


@pytest.fixture
def make_outcomes_file(tmp_path: Path):
    """Factory fixture to write a JSONL outcomes file."""
    def _create_outcomes(records: List[Dict[str, Any]], filename: str = "outcomes.jsonl") -> Path:
        outcomes_path = tmp_path / filename
        lines = [json.dumps(r) for r in records]
        outcomes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return outcomes_path
    return _create_outcomes


@pytest.fixture
def read_jsonl():
    """Helper to read and parse a JSONL output file into a list of dicts."""
    def _read(file_path: Path) -> List[Dict[str, Any]]:
        with open(file_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    return _read
