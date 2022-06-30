#!/usr/bin/env python3
"""Convert TGF graphs to Graphviz format."""
import argparse
import logging
import sys
from pathlib import Path

# This is kind of hacky, but there's two other options:
# 1. duplicate the shared stuff and hope they stay in sync
# 2. add an includegraph library, and require it gets installed in order to use the scripts
# I don't like the first option because it's a maintenance nightmare, but I also don't like the
# second option because it increases the friction to use these tools.
repo_root = Path(__file__).resolve().parent
repo_root = str(repo_root)
sys.path.insert(0, repo_root)
try:
    from includegraph import IncludeGraph, IncludeGraphNode
except ImportError:
    logging.critical("Failed to import types from includegraph.py.")
    raise

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
DEFAULT_LEVEL = "INFO"


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="The file to read input from. Defaults to stdin.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="The file to save the output to. Defaults to stdout.",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        type=str,
        default=DEFAULT_LEVEL,
        choices=LOG_LEVELS.keys(),
        help=f"Set the logging output level. Defaults to {DEFAULT_LEVEL}.",
    )
    return parser.parse_args()


def main(args):
    pass


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=LOG_LEVELS.get(args.log_level),
        stream=sys.stderr,
    )
    main(args)
