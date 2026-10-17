import argparse
import logging
import sys
from pathlib import Path

from agent_engine.config import load_settings
from agent_engine.errors import ConfigError, InvalidInput
from agent_engine.input_processor import parse_input
from agent_engine.logging_setup import setup_logging

log = logging.getLogger("signalpost.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent_engine.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="check the input file (stub for now)")
    run.add_argument("--input", required=True, type=Path)
    args = parser.parse_args(argv)

    setup_logging()
    try:
        load_settings()
        result = parse_input(args.input.read_bytes())
    except (ConfigError, InvalidInput, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Accepted: {len(result.accepted)}")
    print(f"Rejected: {len(result.rejected)}")
    print(f"Duplicates merged: {result.duplicates_merged}")
    for item in result.rejected:
        print(f"  line {item.line}: {item.value!r} ({item.reason})")
    log.info("input checked", extra={"fields": {"file": str(args.input), "accepted": len(result.accepted)}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
