"""Unified production CLI entry point for ALOS runtime, compute governor, crews, and SpecKit."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from alos.core.config import ALOSConfig


GOVERNOR_COMMANDS = frozenset(
    {"bootstrap", "doctor", "status", "enqueue", "jobs", "tick", "daemon", "ledger"}
)


def _handle_speckit_lifecycle(args: argparse.Namespace) -> None:
    from alos.integrations.speckit.lifecycle import SpecKitLifecycleManager

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
    from alos.integrations.speckit.archiver import SpecKitArchiver

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


def _resolve_vault_dir(configured: str) -> str:
    from alos.runtime import RuntimePaths

    local = Path(configured)
    if local.exists():
        return str(local.resolve())
    portable = RuntimePaths.resolve().vault_dir
    if portable.exists():
        return str(portable)
    return os.path.abspath(configured)


def _extract_governor_delegation(raw_args: list[str]) -> list[str] | None:
    """If the user invoked a governor/runtime subcommand, reorder global flags and forward."""
    value_flags = {"--home", "--db-url"}
    idx = 0
    while idx < len(raw_args):
        token = raw_args[idx]
        if token in GOVERNOR_COMMANDS:
            return [*raw_args[:idx], token, *raw_args[idx + 1 :]]
        if token in value_flags:
            idx += 2
            continue
        if token.startswith("-"):
            idx += 1
            continue
        return None
    return None


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
    from alos.logs.monitor import ObservabilityServer, RuntimeMonitor
    from alos.logs.telemetry import global_tracer

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


def _build_main_parser(config: ALOSConfig) -> argparse.ArgumentParser:
    epilog = (
        "Runtime & Compute Governor commands (accept --home PATH, --db-url URL, --mock):\n"
        "  bootstrap   Initialize ALOS_HOME, vault templates, and queue schema\n"
        "  doctor      Verify runtime, DB, NVML GPU, Ollama models, and Docker readiness\n"
        "  status      Sample host telemetry and print governor FSM state JSON\n"
        "  enqueue     Enqueue one job or a batch JSON backlog (--file PATH)\n"
        "  jobs        List queued, review_pending, succeeded, or escalated jobs\n"
        "  tick        Execute a single governor + queue poll cycle\n"
        "  daemon      Start standing warm-linger daemon (PID-locked, SIGTERM/SIGBREAK-safe)\n"
        "  ledger      Inspect recent thermal & capacity ledger rows\n"
    )
    parser = argparse.ArgumentParser(
        description="ALOS - Autonomous Local Operating System CLI",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
    archive_parser.add_argument("--restore", action="store_true", help="Restore archived spec")
    archive_parser.add_argument("--list", action="store_true", help="List archived specifications")

    _register_observability_parser(subparsers, config)

    ask_parser = subparsers.add_parser("ask", help="Run dual-loop reasoning query against vault")
    ask_parser.add_argument("query", help="Task or life logistics prompt for ALOS")
    ask_parser.add_argument("--vault", default=config.vault_dir, help="Path to Markdown vault")
    return parser


def _print_banner() -> None:
    print("ALOS Runtime CLI v0.1.0")
    print("Usage: alos bootstrap | doctor | status | enqueue | tick | daemon | ledger")
    print("Usage: alos ask 'Plan my schedule for today'")
    print("Usage: alos crew run --name speckit_architect --goal 'Add user RAG'")


def _run_crew_command(args: argparse.Namespace) -> None:
    if args.name == "speckit_architect":
        from alos.crews.crews.speckit_architect_crew import SpecKitArchitectCrew

        res = SpecKitArchitectCrew().run(goal=args.goal)
    elif args.name == "code_quality":
        from alos.crews.crews.code_quality_crew import CodeQualityCrew

        res = CodeQualityCrew().run(target_module=args.goal)
    else:
        from alos.crews.crews.obsidian_graph_crew import ObsidianGraphSynthesizerCrew

        res = ObsidianGraphSynthesizerCrew().run(vault_dir="vault")
    print(json.dumps(res, indent=2))
    sys.exit(0)


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point supporting unified runtime, governor, crew, and SpecKit commands."""
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw:
        _print_banner()
        sys.exit(0)

    delegated = _extract_governor_delegation(raw)
    if delegated is not None:
        from alos.swarm.queue import main as governor_main

        sys.exit(governor_main(delegated))

    # Backward-compatible shorthand: `alos "Plan my morning"` maps to `alos ask "Plan my morning"`
    known_roots = {"crew", "speckit", "ask", "observability", "-h", "--help"}
    if raw[0] not in known_roots and not raw[0].startswith("-"):
        raw = ["ask", *raw]

    from alos.core.config import ALOSConfig

    config = ALOSConfig()
    args = _build_main_parser(config).parse_args(raw)

    if args.subcommand == "speckit":
        if args.speckit_action == "lifecycle":
            _handle_speckit_lifecycle(args)
        elif args.speckit_action == "archive":
            _handle_speckit_archive(args)

    if args.subcommand == "observability":
        _handle_observability(args, config)

    if args.subcommand == "crew" and args.crew_action == "run":
        _run_crew_command(args)

    from alos.core.graph import ALOSStateGraph

    vault_path = _resolve_vault_dir(str(args.vault))
    graph = ALOSStateGraph(vault_dir=vault_path, config=config)
    print(json.dumps(graph.run(args.query), indent=2))


if __name__ == "__main__":
    main()
