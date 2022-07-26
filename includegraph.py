#!/usr/bin/env python3
"""Generate the C preprocessor header dependency graph from a Clang compilation database."""
import argparse
import collections
import concurrent.futures
import functools
import json
import logging
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, TextIO

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
DEFAULT_LEVEL = "INFO"


# Keys: "directory", "file", "arguments"
CompilationDatabaseEntry = Dict[str, str]
CompilationDatabase = Iterable[CompilationDatabaseEntry]
# Keys: "linenumber" -> str, "filename" -> str, "tags" -> Tuple[int]
Linemarker = Dict[str, str]


@dataclass
class IncludeGraphNode:
    """A node in an include dependency graph.

    Represents a file; either a source file, or a header, and several attributes thereof.
    """

    # Absolute path
    filename: str
    # Whether it's a compiled source file, or an included header file
    is_source_file: bool = True
    # Whether this is a system header
    is_system_header: bool = False
    # Useful for trimming down the _massive_ system header graph to something useful for a developer
    # That is, useful for ignoring system headers included by other system headers.
    is_first_level_system_header: bool = False
    # compilation_failed: bool
    num_in_edges: int = 0

    def __hash__(self):
        """Determine node uniqueness only by its filename."""
        return hash(self.filename)

    def __lt__(self, other):
        return self.filename < other.filename

    def __repr__(self):
        return self.filename


# source -> targets
IncludeGraph = Dict[IncludeGraphNode, Set[IncludeGraphNode]]


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
    parser.add_argument("--jobs", "-j", default=None, type=int, help="Number of parallel jobs")
    parser.add_argument(
        "--full-system",
        action="store_true",
        default=False,
        help="Output the _full_ system header dependency graph, not just the first level",
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


def load_compilation_database(compilation_database: Path) -> CompilationDatabase:
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


def normalize_command_to_arguments(
    source_entry: CompilationDatabaseEntry,
) -> Optional[CompilationDatabaseEntry]:
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


def invoke_compiler(source_entry: CompilationDatabaseEntry) -> subprocess.Popen:
    """Run the command specified by the compilation database entry."""
    directory = source_entry["directory"]
    arguments = source_entry["arguments"]
    logging.debug("Invoking compiler with: %s", arguments)
    # TODO: discard stderr
    return subprocess.Popen(arguments, cwd=directory, stdout=subprocess.PIPE)


# See: https://gcc.gnu.org/onlinedocs/cpp/Preprocessor-Output.html
LINEMARKER_PATTERN = re.compile(rb'^#\s+(?P<linenumber>\d+)\s+"(?P<filename>.*)"\s*(?P<flags>.*$)?')
LINEMARKER_FLAG_FILE_START = 1
LINEMARKER_FLAG_FILE_END = 2
LINEMARKER_FLAG_SYSTEM_HEADER = 3
LINEMARKER_FLAG_EXTERN_C = 4


def parse_linemarkers_from_match(match: re.Match) -> Linemarker:
    """Turn the regex matches into a 'nice' data structure."""
    parsed = {}
    raw = match.groupdict()

    parsed["linenumber"] = raw["linenumber"].decode("utf-8")
    parsed["filename"] = raw["filename"].decode("utf-8")

    flags = raw["flags"].decode("utf-8").split()
    parsed["flags"] = tuple(int(f) for f in flags)

    return parsed


def parse_linemarkers_from_preprocessor_output(proc: subprocess.Popen) -> Iterable[Linemarker]:
    """Parse the preprocessor linemarkers from the compiler stdout output."""
    for line in proc.stdout:
        match = LINEMARKER_PATTERN.match(line)
        if match is not None:
            linemarker = parse_linemarkers_from_match(match)
            yield linemarker
    proc.wait()
    if proc.returncode != 0:
        logging.error("Failed on args: %s", proc.args)
        # sys.exit(1)


def preprocess_source_file(source_entry: CompilationDatabaseEntry) -> Iterable[Linemarker]:
    """Invoke the preprocessor and parse its stdout to build the include graph.

    Assumes "-o" has been removed from the arguments and "-E" has been added. Munges through the
    compiler's stdout to find and parse preprocessor linemarkers.
    """
    proc = invoke_compiler(source_entry)
    linemarkers = parse_linemarkers_from_preprocessor_output(proc)
    return linemarkers


def get_tu_linemarkers(source_entry: CompilationDatabaseEntry) -> Iterable[Linemarker]:
    """Get the preprocessor linemarkers from the given translation unit database entry."""
    # Normalize "command" -> "arguments"
    source_entry = normalize_command_to_arguments(source_entry)
    # Strip out -o so that we can parse the stdout output with the linemarkers
    source_entry["arguments"] = strip_output_argument(source_entry["arguments"])
    # Instrument with -E
    source_entry["arguments"] += ["-E"]
    # Parse compiler output
    linemarkers = preprocess_source_file(source_entry)

    return linemarkers


def get_project_linemarkers(database: CompilationDatabase) -> Iterable[Linemarker]:
    """Get the linemarkers from the given compilation database."""
    for entry in database:
        entry_linemarkers = get_tu_linemarkers(entry)
        # Mark the start of a new translation unit with a sentinel value
        yield None
        yield from entry_linemarkers


def build_header_dependency_graph(
    linemarkers: Iterable[Linemarker], full_system: bool
) -> IncludeGraph:
    """Build a dependency graph from a set of preprocessor linemarkers."""
    graph = collections.defaultdict(set)
    stack: List[IncludeGraphNode] = []
    for linemarker in linemarkers:
        if linemarker is None:
            stack.clear()
            continue

        filename = linemarker["filename"]
        flags = linemarker["flags"]

        current_node = IncludeGraphNode(filename=filename)

        current_node.is_system_header = 3 in flags
        current_node.is_first_level_system_header = current_node.is_system_header
        if current_node.is_system_header and stack and stack[-1].is_system_header:
            current_node.is_first_level_system_header = False
        current_node.is_source_file = False

        # The start of a new translation unit
        if not stack:
            current_node.is_source_file = True
            stack.append(current_node)
            if current_node not in graph:
                graph[current_node] = set()

        # Ignore the linemarkers without flags. They either seem to be <built-in>, <command-line>,
        # or a duplicate of the start of the translation unit.
        if not flags:
            continue

        if 1 in flags:
            source = stack[-1]
            target = current_node
            stack.append(current_node)
            if (
                full_system
                or not current_node.is_system_header
                or current_node.is_first_level_system_header
            ):
                logging.debug("Adding: %s -> %s", source, target)
                graph[source].add(target)

                # Need to ensure that every node is added to the graph as a proper source node, not
                # just a target.
                if target not in graph:
                    graph[target] = set()

        if 2 in flags:
            _ = stack.pop()

    return graph


def build_graph_for_tu(entry: CompilationDatabaseEntry, idx, total, full_system) -> IncludeGraph:
    logging.info("(%d/%d) Processing dependencies for '%s'...", idx, total, entry["file"])
    linemarkers = get_tu_linemarkers(entry)
    graph = build_header_dependency_graph(linemarkers, full_system)
    logging.debug("(%d/%d) Processed dependencies for '%s'.", idx, total, entry["file"])
    return graph


def build_graphs_in_parallel(
    database: CompilationDatabase, full_system: bool, jobs: int
) -> Iterable[IncludeGraph]:
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=jobs)
    total = len(database)
    futures = {
        executor.submit(build_graph_for_tu, entry, idx + 1, total, full_system): entry
        for idx, entry in enumerate(database)
    }

    for future in concurrent.futures.as_completed(futures):
        entry = futures[future]
        try:
            subgraph = future.result()
            yield subgraph
        except BaseException as e:
            logging.error("Failed to generate dependency graph for '%s'", entry["file"], exc_info=e)


def merge_two_graphs(lhs: IncludeGraph, rhs: IncludeGraph) -> IncludeGraph:
    result = lhs
    for key, value in rhs.items():
        result[key] = result[key].union(value)
    return result


def merge_graphs(subgraphs: Iterable[IncludeGraph]) -> IncludeGraph:
    return functools.reduce(merge_two_graphs, subgraphs)


def output_dep_graph_tgf(graph: IncludeGraph, output: TextIO):
    """Output the include graph in TGF format."""
    node: IncludeGraphNode
    for node in graph.keys():
        # attributes aren't allowed to have commas.
        attributes = f"is_source_file={node.is_source_file}, is_system_header={node.is_system_header}, is_first_level_system_header={node.is_first_level_system_header}"
        print(f'"{node.filename}"\t"{attributes}"', file=output)
    print("#", file=output)
    source: IncludeGraphNode
    targets: Set[IncludeGraphNode]
    for source, targets in graph.items():
        for target in targets:
            print(f'"{source.filename}"\t"{target.filename}"', file=output)


def main(args):
    database_path = Path(args.compilation_database)
    database = load_compilation_database(database_path)
    logging.debug("Successfully loaded compilation database from '%s'", database_path)

    jobs = args.jobs or os.cpu_count()
    subgraphs = build_graphs_in_parallel(database, args.full_system, jobs)
    graph = merge_graphs(subgraphs)
    output_dep_graph_tgf(graph, args.output)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(module)s - %(levelname)s - %(message)s",
        level=LOG_LEVELS.get(args.log_level),
        stream=sys.stderr,
    )
    main(args)
