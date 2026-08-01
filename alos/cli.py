import argparse
import json
import os
import sys

from alos.core.config import ALOSConfig
from alos.core.graph import ALOSStateGraph
from alos.crews.crews.code_quality_crew import CodeQualityCrew
from alos.crews.crews.obsidian_graph_crew import ObsidianGraphSynthesizerCrew
from alos.crews.crews.speckit_architect_crew import SpecKitArchitectCrew


def main():
    config = ALOSConfig()
    parser = argparse.ArgumentParser(description="ALOS - Personal Life Autonomous Runtime CLI")
    subparsers = parser.add_subparsers(dest="subcommand")

    # alos crew run subcommand
    crew_parser = subparsers.add_parser("crew", help="CrewAI agent orchestration commands")
    crew_subparsers = crew_parser.add_subparsers(dest="crew_action")
    run_parser = crew_subparsers.add_parser("run", help="Run a local CrewAI agent crew")
    run_parser.add_argument(
        "--name",
        required=True,
        choices=["speckit_architect", "code_quality", "obsidian_graph"],
        help="Name of crew to run",
    )
    run_parser.add_argument(
        "--goal", default="Standard crew execution task", help="Goal or focus area for the crew"
    )

    parser.add_argument("query", nargs="?", help="Task or life logistics prompt for ALOS")
    parser.add_argument(
        "--vault", default=config.vault_dir, help="Path to local Markdown vault directory"
    )
    args = parser.parse_args()

    if args.subcommand == "crew" and args.crew_action == "run":
        if args.name == "speckit_architect":
            res = SpecKitArchitectCrew().run(goal=args.goal)
        elif args.name == "code_quality":
            res = CodeQualityCrew().run(target_module=args.goal)
        else:
            res = ObsidianGraphSynthesizerCrew().run(vault_dir="vault")
        print(json.dumps(res, indent=2))
        sys.exit(0)

    if not args.query:
        print("ALOS Runtime CLI v0.1.0")
        print("Usage: python -m alos.cli 'Plan my schedule for today'")
        print("Usage: python -m alos.cli crew run --name speckit_architect --goal 'Add user RAG'")
        sys.exit(0)

    vault_path = os.path.abspath(args.vault)
    graph = ALOSStateGraph(vault_dir=vault_path, config=config)
    result = graph.run(args.query)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
