from __future__ import annotations

import argparse
import json

from .analysis import scenario_loads, write_artifacts
from .simulation import run_single_load


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Priority-aware SDN stability threshold analysis for Healthcare IoT systems."
    )
    parser.add_argument("--scenario", choices=["baseline", "stress"], default="baseline")
    parser.add_argument("--policy", choices=["priority", "fifo"], default="priority")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--duration", type=float, default=24.0, help="Seconds simulated at each load point.")
    parser.add_argument("--tag", default="latest", help="Artifact suffix tag, e.g. fifo or trial1.")
    parser.add_argument("--use-rl", action="store_true", help="Enable RL adaptive queue weights.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = []
    for idx, load in enumerate(scenario_loads(args.scenario)):
        rows.append(run_single_load(load, args.policy, seed=args.seed + idx, duration_s=args.duration, use_rl=args.use_rl))
        print(f"load={load:.2f} policy={args.policy} complete")
    summary = write_artifacts(rows, args.scenario, args.policy, args.tag)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
