"""
Configuration loading and validation for the Policy Engine.
Derived strictly from docs/POLICY.md §8.
"""

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Dict, Union


@dataclass(frozen=True)
class PolicyConfig:
    failure_threshold: int
    cooldown_ms: int
    slow_threshold_ms: int
    max_retries: int
    retry_delay_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.failure_threshold, int) or self.failure_threshold < 1:
            raise ValueError(f"failure_threshold must be an integer >= 1, got {self.failure_threshold}")
        if not isinstance(self.cooldown_ms, int) or self.cooldown_ms < 1000:
            raise ValueError(f"cooldown_ms must be an integer >= 1000, got {self.cooldown_ms}")
        if not isinstance(self.slow_threshold_ms, int) or self.slow_threshold_ms < 100:
            raise ValueError(f"slow_threshold_ms must be an integer >= 100, got {self.slow_threshold_ms}")
        if not isinstance(self.max_retries, int) or self.max_retries < 0:
            raise ValueError(f"max_retries must be an integer >= 0, got {self.max_retries}")
        if not isinstance(self.retry_delay_ms, int) or self.retry_delay_ms < 0:
            raise ValueError(f"retry_delay_ms must be an integer >= 0, got {self.retry_delay_ms}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyConfig":
        required_fields = {
            "failure_threshold",
            "cooldown_ms",
            "slow_threshold_ms",
            "max_retries",
            "retry_delay_ms",
        }
        missing = required_fields - set(data.keys())
        if missing:
            raise ValueError(f"Missing required configuration fields: {sorted(missing)}")
        
        return cls(
            failure_threshold=int(data["failure_threshold"]),
            cooldown_ms=int(data["cooldown_ms"]),
            slow_threshold_ms=int(data["slow_threshold_ms"]),
            max_retries=int(data["max_retries"]),
            retry_delay_ms=int(data["retry_delay_ms"]),
        )

    @classmethod
    def from_file(cls, path: Union[Path, str]) -> "PolicyConfig":
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            raise ValueError("Configuration root must be a JSON object.")
        
        return cls.from_dict(data)
