"""
CLI Entrypoint for the Retry & Circuit Breaker Policy Engine.
Executes the full pipeline from outcomes.jsonl + config.json to decisions.jsonl + stopped_periods.json.
"""

import argparse
import sys
from pathlib import Path
from src.config import PolicyConfig
from src.engine import PolicyEngine
from src.reporter import write_decisions_jsonl, write_stopped_periods_json


def run_pipeline(
    outcomes_path: str = "outcomes.jsonl",
    config_path: str = "config.json",
    decisions_path: str = "decisions.jsonl",
    stopped_periods_path: str = "stopped_periods.json",
) -> int:
    """Executes the policy engine pipeline and generates both output files."""
    try:
        config = PolicyConfig.from_file(config_path)
    except Exception as e:
        print(f"Error loading configuration '{config_path}': {e}", file=sys.stderr)
        return 1

    engine = PolicyEngine(config)

    try:
        decisions = engine.process_file(outcomes_path)
    except Exception as e:
        print(f"Error processing outcomes file '{outcomes_path}': {e}", file=sys.stderr)
        return 1

    stopped_periods = engine.get_stopped_periods_report()

    try:
        write_decisions_jsonl(decisions, decisions_path)
        write_stopped_periods_json(stopped_periods, stopped_periods_path)
    except Exception as e:
        print(f"Error writing output files: {e}", file=sys.stderr)
        return 1

    print(f"Successfully evaluated {len(decisions)} calls.")
    print(f"Wrote decisions to '{decisions_path}' and stopped periods to '{stopped_periods_path}'.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry & Circuit Breaker Policy Engine")
    parser.add_argument("--outcomes", default="outcomes.jsonl", help="Path to input outcomes.jsonl")
    parser.add_argument("--config", default="config.json", help="Path to input config.json")
    parser.add_argument("--decisions", default="decisions.jsonl", help="Path to output decisions.jsonl")
    parser.add_argument("--stopped-periods", default="stopped_periods.json", help="Path to output stopped_periods.json")
    
    args = parser.parse_args()
    exit_code = run_pipeline(
        outcomes_path=args.outcomes,
        config_path=args.config,
        decisions_path=args.decisions,
        stopped_periods_path=args.stopped_periods,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
