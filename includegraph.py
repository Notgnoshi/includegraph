#!/usr/bin/env python3
"""Generate the C preprocessor header dependency graph from a Clang compilation database."""
import argparse
import collections
import json
import logging
import pathlib
import re
import shlex
import subprocess
import sys
from typing import Dict, Iterable, List, Optional, TextIO, Tuple

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
DEFAULT_LEVEL = "DEBUG"


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
        "--output",
        "-o",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="The file to save the output to. Defaults to stdout.",
    )
    parser.add_argument(
        "--output-format",
        "-O",
        type=str,
        default="tree",
        choices=["graphviz", "tree"],
        help="The output format for the parsed header dependency graph.",
    )
    # TODO: Trim common prefix from output?
    # TODO: Does not passing --all-includes preclude circular dependency detection?
    parser.add_argument(
        "--all-includes",
        "-a",
        action="store_true",
        default=False,
        help="Ignore header guards and show all includes",
    )
    parser.add_argument(
        "--system-headers",
        "-s",
        action="store_true",
        default=False,
        help="Keep system headers in the generated graph",
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


def load_compilation_database(compilation_database: pathlib.Path) -> Dict:
    """Load the compilation database from the given path."""
    database = None
    try:
        database = json.load(compilation_database.open())
    except json.JSONDecodeError as e:
        logging.critical(
            "Failed to load compilation database from %s", compilation_database, exc_info=e
        )
        sys.exit(1)
    if not isinstance(database, list):
        logging.critical(
            "Expected compilation database to be an array of objects. Got: %s", database
        )
        sys.exit(1)

    return database


def normalize_command_to_arguments(source_entry: Dict) -> Optional[Dict]:
    """Normalize and validate the given database entry.

    See: https://clang.llvm.org/docs/JSONCompilationDatabase.html
    """
    if "directory" not in source_entry:
        logging.error("Missing required 'directory' key in %s", source_entry)
        return None
    if "file" not in source_entry:
        logging.error("Missing required 'file' key in %s", source_entry)
        return None
    if "command" in source_entry:
        command = source_entry["command"]
        del source_entry["command"]
        arguments = shlex.split(command)
        source_entry["arguments"] = arguments
    if "arguments" not in source_entry:
        logging.error("Missing required 'arguments' key in %s", source_entry)
        return None
    return source_entry


def strip_output_argument(arguments: List[str]) -> List[str]:
    """Strip any "-o" flags (and arguments) to the compiler."""
    # Strip both "-o", "value" and "-o=value"
    stripped_args = []
    arguments = iter(arguments)
    for arg in arguments:
        if arg.startswith("-o"):
            if arg == "-o":
                # skip the next argument (the -o flag's value)
                next(arguments, None)
            # skip this argument
            continue
        stripped_args.append(arg)
    return stripped_args


def invoke_compiler(source_entry) -> subprocess.Popen:
    """Run the command specified by the compilation database entry."""
    directory = source_entry["directory"]
    arguments = source_entry["arguments"]
    logging.debug("Invoking compiler with: %s", arguments)
    return subprocess.Popen(arguments, cwd=directory, stdout=subprocess.PIPE)


# See: https://gcc.gnu.org/onlinedocs/cpp/Preprocessor-Output.html
LINEMARKER_PATTERN = re.compile(rb'^#\s+(?P<linenumber>\d+)\s+(?P<filename>".*")\s*(?P<flags>.*$)?')


def parse_linemarkers_from_preprocessor_output(proc: subprocess.Popen) -> Dict[bytes, bytes]:
    """Parse the preprocessor linemarkers from the compiler stdout output."""
    for line in proc.stdout:
        match = LINEMARKER_PATTERN.match(line)
        if match is not None:
            linemarker = match.groupdict()
            logging.debug("Linemarker: %s", linemarker)
            yield linemarker


def parse_source_file_includes(source_entry: Dict) -> Iterable[Dict]:
    """Invoke the preprocessor and parse its stdout to build the include graph.

    Assumes "-o" has been removed from the arguments and "-E" has been added. Munges through the
    compiler's stdout to find and parse preprocessor linemarkers.
    """
    logging.info("Parsing includes from: %s", source_entry["file"])
    proc = invoke_compiler(source_entry)
    linemarkers = parse_linemarkers_from_preprocessor_output(proc)
    # Exhaust iterable
    list(linemarkers)

    return []


def get_tu_includes(source_entry: Dict) -> Iterable[Dict]:
    """Get the #includes from the given translation unit from the compilation database."""
    # Normalize "command" -> "arguments"
    source_entry = normalize_command_to_arguments(source_entry)
    # Strip out -o so that we can parse the stdout output with the linemarkers
    source_entry["arguments"] = strip_output_argument(source_entry["arguments"])
    # Instrument with -E
    source_entry["arguments"] += ["-E"]
    # Parse compiler output
    parsed_includes = parse_source_file_includes(source_entry)

    return parsed_includes


def get_project_includes(database: List[Dict]) -> Iterable[Dict]:
    """Get the #includes from the given compilation database."""
    for entry in database:
        entry_headers = get_tu_includes(entry)
        yield from entry_headers


def build_header_dependency_graph(includes: Iterable[Dict]) -> Dict:
    """Build a dependency graph from a set of FileInclusion objects."""
    graph = collections.defaultdict(list)
    for include in includes:
        # TODO: Depends on output format from get_tu_includes
        pass
    return graph


def topological_sort(graph: Dict[str, List[str]]) -> List[str]:
    """Topologically sort the keys of a graph."""
    sorted_keys = []
    seen = set()

    def recursive_helper(node: str):
        for neighbor in graph.get(node, []):
            if neighbor not in seen:
                seen.add(neighbor)
                recursive_helper(neighbor)
        if node not in sorted_keys:
            sorted_keys.append(node)

    for key in graph.keys():
        recursive_helper(key)
    return sorted_keys


def output_dep_graph_tree(graph: Dict, file: TextIO):
    """Output the include graph as a tree.

    Example:
        example1.cpp
            foo.h
            bar.h
            private.h
                circular.h

    Each level of indentation will be a single tab character.
    """

    def recursive_dfs_helper(graph: Dict, source: str, file: TextIO, depth: int, path=[]):
        indent = "\t" * depth
        print(f"{indent}{source}", file=file)
        if source not in path:
            path.append(source)
            if source not in graph:
                return path
            for neighbor in graph[source]:
                path = recursive_dfs_helper(graph, neighbor, file, depth + 1, path)
        return path

    # Don't crash on an empty graph
    if not graph:
        return

    # Get a top-level candidate (is not depended on by anything else) to print first at depth=0
    sorted_keys = topological_sort(graph)
    root = sorted_keys[-1]

    recursive_dfs_helper(graph, root, file, depth=0)


def output_dep_graph_graphviz(graph: Dict, file: TextIO):
    """Output the include graph in Graphviz format."""
    print("digraph header_graph {", file=file)
    for source, targets in graph.items():
        for target in targets:
            print(f'\t"{source}" -> "{target}";', file=file)
    print("}", file=file)


def output_dep_graph(graph: Dict, file: TextIO, format: str):
    if format == "tree":
        output_dep_graph_tree(graph, file)
    elif format == "graphviz":
        output_dep_graph_graphviz(graph, file)


def main(args):
    database_path = pathlib.Path(args.compilation_database)
    database = load_compilation_database(database_path)
    logging.debug("Successfully loaded compilation database from '%s'", database_path)
    includes = get_project_includes(database)
    include_graph = build_header_dependency_graph(includes)
    output_dep_graph(include_graph, args.output, args.output_format)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=LOG_LEVELS.get(args.log_level),
        stream=sys.stderr,
    )
    logging = logging.getLogger(name=__file__)
    main(args)
