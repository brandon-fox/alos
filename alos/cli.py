"""Command Line Interface (CLI) entry point for the ALOS runtime and SpecKit integrations."""

import argparse
import json
import os
import sys
import time
from typing import Any

from alos.core.config import ALOSConfig
from alos.core.graph import ALOSStateGraph
from alos.crews.crews.code_quality_crew import CodeQualityCrew
from alos.crews.crews.obsidian_graph_crew import ObsidianGraphSynthesizerCrew
from alos.crews.crews.speckit_architect_crew import SpecKitArchitectCrew
from alos.integrations.speckit.archiver import SpecKitArchiver
from alos.integrations.speckit.lifecycle import SpecKitLifecycleManager
from alos.logs.monitor import ObservabilityServer, RuntimeMonitor
from alos.logs.telemetry import global_tracer


def _handle_speckit_lifecycle(args: argparse.Namespace) -> None:
    manager = SpecKitLifecycleManager()
    res: dict[str, Any] | list[dict[str, Any]]
    if args.action == "list":
        res = manager.list_features(state_filter=args.target_state)
    elif args.action == "transition":
        if not args.feature or not args.target_state:
            print("Error: --feature and --target-state required.", file=sys.stderr)
            sys.exit(1)
        res = manager.transition_state(args.feature, args.target_state, reason=args.reason)
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


def _register_observability_parser(subparsers: Any, config: ALOSConfig) -> None:
    obs_parser = subparsers.add_parser(
        "observability", help="Runtime health, metrics, traces, and HTTP server commands"
    )
    obs_sub = obs_parser.add_subparsers(dest="obs_action")
    obs_sub.add_parser("health", help="Evaluate runtime health and SLO probes")
    metrics_p = obs_sub.add_parser("metrics", help="Export runtime metrics")
    metrics_p.add_argument("--format", choices=["prometheus", "json"], default="prometheus")
    traces_p = obs_sub.add_parser("traces", help="Inspect recent telemetry spans")
    traces_p.add_argument("--limit", type=int, default=50)
    serve_p = obs_sub.add_parser("serve", help="Run loopback observability HTTP server")
    serve_p.add_argument("--host", default=config.observability_host)
    serve_p.add_argument("--port", type=int, default=config.observability_port)
    serve_p.add_argument("--duration", type=float, default=0.0)


def _handle_observability(args: argparse.Namespace, config: ALOSConfig) -> None:
    monitor = RuntimeMonitor(config=config, tracer=global_tracer)
    if args.obs_action == "health":
        report = monitor.check_health()
        print(report.model_dump_json(indent=2))
        sys.exit(1 if report.status == "UNHEALTHY" else 0)
    if args.obs_action == "metrics":
        monitor.collect_runtime_stats()
        out = (
            json.dumps(global_tracer.snapshot(), indent=2)
            if args.format == "json"
            else global_tracer.render_prometheus()
        )
        print(out)
        sys.exit(0)
    if args.obs_action == "traces":
        spans = [s.model_dump() for s in global_tracer.get_spans(limit=args.limit)]
        print(json.dumps(spans, indent=2))
        sys.exit(0)
    if args.obs_action == "serve":
        srv = ObservabilityServer(
            monitor=monitor, tracer=global_tracer, host=args.host, port=args.port
        )
        host, port = srv.start()
        print(json.dumps({"status": "SERVING", "url": f"http://{host}:{port}"}))
        try:
            time.sleep(args.duration if args.duration > 0 else 86400.0)
        except KeyboardInterrupt:
            pass
        finally:
            srv.stop()
        sys.exit(0)
    print("Error: specify observability action {health,metrics,traces,serve}.", file=sys.stderr)
    sys.exit(1)


def _build_parser(config: ALOSConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ALOS - Personal Life Autonomous Runtime CLI")
    subparsers = parser.add_subparsers(dest="subcommand")

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

    speckit_parser = subparsers.add_parser(
        "speckit", help="SpecKit lifecycle and archiving commands"
    )
    speckit_subparsers = speckit_parser.add_subparsers(dest="speckit_action")
    lifecycle_parser = speckit_subparsers.add_parser(
        "lifecycle", help="SpecKit lifecycle management"
    )
    lifecycle_parser.add_argument("--feature", help="Feature specification name")
    lifecycle_parser.add_argument(
        "--action", choices=["status", "transition", "list"], default="status"
    )
    lifecycle_parser.add_argument("--target-state", help="Target state for transition action")
    lifecycle_parser.add_argument("--reason", help="Reason for state transition")

    archive_parser = speckit_subparsers.add_parser("archive", help="SpecKit archiving operations")
    archive_parser.add_argument("--feature", help="Feature specification name")
    archive_parser.add_argument("--restore", action="store_true", help="Restore feature")
    archive_parser.add_argument("--list", action="store_true", help="List archived specifications")

    _register_observability_parser(subparsers, config)
    parser.add_argument("query", nargs="?", help="Task or life logistics prompt for ALOS")
    parser.add_argument("--vault", default=config.vault_dir, help="Path to local vault directory")
    return parser


def main() -> None:
    """Main CLI entry point for executing ALOS queries, CrewAI, SpecKit, and observability."""
    config = ALOSConfig()
    args = _build_parser(config).parse_args()

    if args.subcommand == "speckit":
        if args.speckit_action == "lifecycle":
            _handle_speckit_lifecycle(args)
        elif args.speckit_action == "archive":
            _handle_speckit_archive(args)

    if args.subcommand == "observability":
        _handle_observability(args, config)

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
        print("Usage: python -m alos.cli observability health")
        sys.exit(0)

    vault_path = os.path.abspath(args.vault)
    graph = ALOSStateGraph(vault_dir=vault_path, config=config)
    print(json.dumps(graph.run(args.query), indent=2))


if __name__ == "__main__":
    main()
