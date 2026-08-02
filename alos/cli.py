"""Command Line Interface (CLI) entry point for the ALOS runtime and SpecKit integrations."""

import argparse
import json
import os
import sys
from typing import Any

from alos.core.config import ALOSConfig
from alos.core.graph import ALOSStateGraph
from alos.crews.crews.code_quality_crew import CodeQualityCrew
from alos.crews.crews.obsidian_graph_crew import ObsidianGraphSynthesizerCrew
from alos.crews.crews.speckit_architect_crew import SpecKitArchitectCrew
from alos.integrations.speckit.archiver import SpecKitArchiver
from alos.integrations.speckit.lifecycle import SpecKitLifecycleManager


def _handle_speckit_lifecycle(args: argparse.Namespace) -> None:
    manager = SpecKitLifecycleManager()
    res: dict[str, Any] | list[dict[str, Any]]
    if args.action == "list":
        res = manager.list_features(state_filter=args.target_state)
    elif args.action == "transition":
        if not args.feature or not args.target_state:
            print("Error: --feature and --target-state required.", file=sys.stderr)
            sys.exit(1)
        res = manager.transition_state(
            args.feature, args.target_state, reason=args.reason
        )
    elif args.feature:
        res = manager.get_status(args.feature)
    else:
        res = manager.list_features()
    print(json.dumps(res, indent=2))
    sys.exit(0)


def _handle_speckit_archive(args: argparse.Namespace) -> None:
    archiver = SpecKitArchiver()
    res: dict[str, Any] | list[dict[str, Any]]
    if args.list:
        res = archiver.list_archived_features()
    elif args.restore:
        if not args.feature:
            print("Error: --feature is required for restore action.", file=sys.stderr)
            sys.exit(1)
        res = archiver.restore_feature(args.feature)
    else:
        if not args.feature:
            print("Error: --feature is required for archive action.", file=sys.stderr)
            sys.exit(1)
        res = archiver.archive_feature(args.feature)
    print(json.dumps(res, indent=2))
    sys.exit(0)


def main() -> None:
    """Main CLI entry point for executing ALOS queries and CrewAI commands."""
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

    # alos speckit subcommand
    speckit_parser = subparsers.add_parser(
        "speckit", help="SpecKit lifecycle and archiving commands"
    )
    speckit_subparsers = speckit_parser.add_subparsers(dest="speckit_action")

    lifecycle_parser = speckit_subparsers.add_parser(
        "lifecycle", help="SpecKit lifecycle management"
    )
    lifecycle_parser.add_argument(
        "--feature", help="Feature specification name (e.g. 027-speckit-lifecycle-archiving)"
    )
    lifecycle_parser.add_argument(
        "--action",
        choices=["status", "transition", "list"],
        default="status",
        help="Lifecycle action to perform",
    )
    lifecycle_parser.add_argument("--target-state", help="Target state for transition action")
    lifecycle_parser.add_argument("--reason", help="Reason for state transition")

    archive_parser = speckit_subparsers.add_parser(
        "archive", help="SpecKit archiving operations"
    )
    archive_parser.add_argument(
        "--feature", help="Feature specification name to archive or restore"
    )
    archive_parser.add_argument(
        "--restore", action="store_true", help="Restore feature specification"
    )
    archive_parser.add_argument(
        "--list", action="store_true", help="List archived specifications"
    )

    parser.add_argument("query", nargs="?", help="Task or life logistics prompt for ALOS")
    parser.add_argument(
        "--vault", default=config.vault_dir, help="Path to local Markdown vault directory"
    )
    args = parser.parse_args()

    if args.subcommand == "speckit":
        if args.speckit_action == "lifecycle":
            _handle_speckit_lifecycle(args)
        elif args.speckit_action == "archive":
            _handle_speckit_archive(args)

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
