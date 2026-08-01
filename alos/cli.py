import argparse
import json
import os
import sys

from alos.core.config import ALOSConfig
from alos.core.graph import ALOSStateGraph


def main():
    config = ALOSConfig()
    parser = argparse.ArgumentParser(description="ALOS - Personal Life Autonomous Runtime CLI")
    parser.add_argument("query", nargs="?", help="Task or life logistics prompt for ALOS")
    parser.add_argument(
        "--vault", default=config.vault_dir, help="Path to local Markdown vault directory"
    )
    args = parser.parse_args()

    if not args.query:
        print("ALOS Runtime CLI v0.1.0")
        print("Usage: python -m alos.cli 'Plan my schedule for today'")
        sys.exit(0)

    vault_path = os.path.abspath(args.vault)
    graph = ALOSStateGraph(vault_dir=vault_path, config=config)
    result = graph.run(args.query)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
