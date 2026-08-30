"""
File output writers for decisions.jsonl and stopped_periods.json.
Derived strictly from docs/POLICY.md §2.3, §2.4.
"""

from pathlib import Path
import json
from typing import Dict, List, Union
from src.models import DecisionRecord


def write_decisions_jsonl(decisions: List[DecisionRecord], output_path: Union[Path, str]) -> None:
    """Writes decision records to a JSON Lines file in input order."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for decision in decisions:
            f.write(json.dumps(decision.to_dict()) + "\n")


def write_stopped_periods_json(stopped_periods: Dict[str, List[dict]], output_path: Union[Path, str]) -> None:
    """Writes the stopped periods report dictionary as formatted JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stopped_periods, f, indent=2)
        f.write("\n")
