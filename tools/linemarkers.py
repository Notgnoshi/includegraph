#!/usr/bin/env python3
"""Get the linemarkers for every source file in a compilation database.

Saves the linemarkers in a file next to the source file they were parsed from.
"""
import argparse
import logging
import pathlib
import sys
from typing import Dict, Iterable, List

REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))
from includegraph import get_tu_linemarkers, load_compilation_database

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
        "compilation_database",
        metavar="compilation-database",
        type=str,
        help="The path to the compilation database.",
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


def save_linemarkers(entry: Dict, linemarkers: Iterable[Dict]):
    source_file = entry["file"]
    linemarker_file = source_file + ".txt"
    with open(linemarker_file, "w") as f:
        for linemarker in linemarkers:
            lineno = linemarker["linenumber"]
            filename = linemarker["filename"]
            flags = " ".join(str(f) for f in linemarker["flags"])
            reconstructed = f'# {lineno} "{filename}" {flags}\n'
            f.write(reconstructed)


def save_all_linemarkers(db: List[Dict]):
    for entry in db:
        linemarkers = get_tu_linemarkers(entry)
        save_linemarkers(entry, linemarkers)


def main(args):
    path = pathlib.Path(args.compilation_database)
    database = load_compilation_database(path)
    save_all_linemarkers(database)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=LOG_LEVELS.get(args.log_level),
        stream=sys.stderr,
    )
    main(args)
