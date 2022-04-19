#!/usr/bin/env python3
"""Generate the C preprocessor header dependency graph from a Clang compilation database."""
import abc
import argparse
import collections
import json
import logging
import pathlib
import re
import shlex
import subprocess
import sys
from typing import Dict, Iterable, List, Optional, Set, TextIO

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
        "--output",
        "-o",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="The file to save the output to. Defaults to stdout.",
    )
    parser.add_argument(
        "--error-exit",
        "-e",
        action="store_true",
        default=False,
        help="Immediately exit with non-zero status on compilation errors",
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

    # On the same problem project as the rest of the special cases, Qt Creator generated a single
    # "argument" that was actually multiple space-separated arguments. What's worse, was that it
    # began with whitespace, so g++ actually treated _it_ as the source filename (because there
    # weren't leading -'s I guess?)
    new_args = []
    for arg in source_entry["arguments"]:
        args = shlex.split(arg)
        new_args += args
    source_entry["arguments"] = new_args

    # Not a long-term solution. Qt Creator generated a compile_commands.json with arguments it
    # didn't actually pass to the compiler. Will need to instrument plumbing to add/remove arbitrary
    # compiler commandline arguments. Use the same spec as the .clangd YAML file (but use JSON to
    # keep it stdlib only).
    banned_args = ["-m32", "--target=arm-dey-linux-gnueabi"]
    for arg in banned_args:
        if arg in source_entry["arguments"]:
            source_entry["arguments"].remove(arg)

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
    logging.info("Invoking compiler with: %s", arguments)
    return subprocess.Popen(arguments, cwd=directory, stdout=subprocess.PIPE)


# See: https://gcc.gnu.org/onlinedocs/cpp/Preprocessor-Output.html
LINEMARKER_PATTERN = re.compile(rb'^#\s+(?P<linenumber>\d+)\s+"(?P<filename>.*)"\s*(?P<flags>.*$)?')
LINEMARKER_FLAG_FILE_START = 1
LINEMARKER_FLAG_FILE_END = 2
LINEMARKER_FLAG_SYSTEM_HEADER = 3
LINEMARKER_FLAG_EXTERN_C = 4


def parse_linemarkers_from_match(match: re.Match) -> Dict:
    """Turn the regex matches into a 'nice' data structure."""
    parsed = {}
    raw = match.groupdict()

    parsed["linenumber"] = raw["linenumber"].decode("utf-8")
    parsed["filename"] = raw["filename"].decode("utf-8")

    flags = raw["flags"].decode("utf-8").split()
    parsed["flags"] = tuple(int(f) for f in flags)

    return parsed


def parse_linemarkers_from_preprocessor_output(proc: subprocess.Popen, error_exit: bool) -> Dict:
    """Parse the preprocessor linemarkers from the compiler stdout output."""
    for line in proc.stdout:
        match = LINEMARKER_PATTERN.match(line)
        if match is not None:
            yield parse_linemarkers_from_match(match)

    proc.wait()
    if proc.returncode != 0:
        logging.critical("Failed on args: %s", proc.args)
        if error_exit:
            sys.exit(1)


def parse_source_file_linemarkers(source_entry: Dict, error_exit: bool) -> Iterable[Dict]:
    """Invoke the preprocessor and parse its stdout to build the include graph.

    Assumes "-o" has been removed from the arguments and "-E" has been added. Munges through the
    compiler's stdout to find and parse preprocessor linemarkers.
    """
    proc = invoke_compiler(source_entry)
    linemarkers = parse_linemarkers_from_preprocessor_output(proc, error_exit)
    return linemarkers


def get_tu_linemarkers(source_entry: Dict, error_exit: bool) -> Iterable[Dict]:
    """Get the preprocessor linemarkers from the given translation unit database entry."""
    # Normalize "command" -> "arguments"
    source_entry = normalize_command_to_arguments(source_entry)
    # Strip out -o so that we can parse the stdout output with the linemarkers
    source_entry["arguments"] = strip_output_argument(source_entry["arguments"])
    # Instrument with -E
    source_entry["arguments"] += ["-E"]
    # Parse compiler output
    linemarkers = parse_source_file_linemarkers(source_entry, error_exit)

    return linemarkers


def get_project_linemarkers(database: List[Dict], error_exit: bool) -> Iterable[Dict]:
    """Get the linemarkers from the given compilation database."""
    for entry in database:
        entry_linemarkers = get_tu_linemarkers(entry, error_exit)
        # Mark the start of a new translation unit with a sentinel value
        yield None
        yield from entry_linemarkers


# is_system_header: bool
# is_top_level_system_header: bool
# compile_failed: bool
FileAttributes = collections.namedtuple(
    "FileAttributes", ["is_system_header", "is_top_level_system_header", "compile_failed"]
)
# filename: str
# attributes: FileAttributes
GraphNode = collections.namedtuple("GraphNode", ["filename", "attributes"])


def build_header_dependency_graph(linemarkers: Iterable[Dict]) -> Dict:
    """Build a dependency graph from a set of preprocessor linemarkers."""
    graph = collections.defaultdict(set)
    stack = []
    for linemarker in linemarkers:
        if linemarker is None:
            stack.clear()
            continue

        filename = linemarker["filename"]
        flags = linemarker["flags"]
        is_system_header = 3 in flags
        is_top_level_system_header = is_system_header
        if is_system_header and stack and stack[-1].attributes.is_system_header:
            is_top_level_system_header = False
        attributes = FileAttributes(
            is_system_header, is_top_level_system_header, compile_failed=False
        )
        current_linemarker_node = GraphNode(filename=filename, attributes=attributes)
        if current_linemarker_node not in graph:
            graph[current_linemarker_node] = set()

        # The start of a new translation unit
        if not stack:
            stack.append(current_linemarker_node)

        # Special case. I don't know man, the preprocessor generated a linemarker for a directory in
        # one of the projects I tested it on.
        if filename.endswith("/"):
            continue

        # Ignore the linemarkers without flags. They either seem to be <built-in>, <command-line>,
        # or a duplicate of the start of the translation unit.
        if not flags:
            continue

        if 1 in flags:
            source = stack[-1]
            target = current_linemarker_node
            stack.append(target)
            logging.debug("Adding: %s -> %s", source, target)
            graph[source].add(target)

        if 2 in flags:
            _ = stack.pop()

    return graph


class GraphFormatter(abc.ABC):
    """A base class for formatting graphs.

    The interface for this formatter forms a visitor pattern where each node in the node list is
    visited, and then each edge in the edge list is visited.
    """

    def start_node_list(self, graph: Dict[GraphNode, Set[GraphNode]], output: TextIO):
        """Mark the beginning of the node list.

        Also marks the beginning of formatting.
        """

    def visit_node(self, node: GraphNode, output: TextIO):
        """Visit a node in the node list."""

    def finish_node_list(self, graph: Dict[GraphNode, Set[GraphNode]], output: TextIO):
        """Mark the end of the node list."""

    def start_edge_list(self, graph: Dict[GraphNode, Set[GraphNode]], output: TextIO):
        """Mark the beginning of the edge list."""

    def visit_edge(self, source: GraphNode, target: GraphNode, output: TextIO):
        """Visit an edge in the edge list."""

    def finish_edge_list(self, graph: Dict[GraphNode, Set[GraphNode]], output: TextIO):
        """Mark the end of the edge list.

        Also marks the end of formatting.
        """

    def format(self, graph: Dict[GraphNode, Set[GraphNode]], output: TextIO):
        """Serialize the given graph to the given output object."""
        self.start_node_list(graph, output)
        for node in graph.keys():
            self.visit_node(node, output)
        self.finish_node_list(graph, output)
        self.start_edge_list(graph, output)
        for source, targets in graph.items():
            for target in targets:
                self.visit_edge(source, target, output)
        self.finish_edge_list(graph, output)


class SimpleTgfGraphFormatter(GraphFormatter):
    """Output the include graph in Trivial Graph Format.

    https://en.wikipedia.org/wiki/Trivial_Graph_Format
    """

    def visit_node(self, node: GraphNode, output: TextIO):
        print(f'"{node.filename}"\t"{node.attributes}"', file=output)

    def finish_node_list(self, graph: Dict[GraphNode, Set[GraphNode]], output: TextIO):
        print("#", file=output)

    def visit_edge(self, source: GraphNode, target: GraphNode, output: TextIO):
        print(f'"{source.filename}"\t"{target.filename}"', file=output)


def main(args):
    database_path = pathlib.Path(args.compilation_database)
    database = load_compilation_database(database_path)
    logging.debug("Successfully loaded compilation database from '%s'", database_path)
    linemarkers = get_project_linemarkers(database, args.error_exit)
    include_graph = build_header_dependency_graph(linemarkers)
    formatter = SimpleTgfGraphFormatter()
    formatter.format(include_graph, args.output)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=LOG_LEVELS.get(args.log_level),
        stream=sys.stderr,
    )
    main(args)
